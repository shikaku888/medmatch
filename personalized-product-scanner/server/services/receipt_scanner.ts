/**
 * Receipt & cart audit — local OCR (Tesseract.js) + rule-based analysis.
 * Replaces the Gemini receipt parser. Item identification goes through the
 * MedMatch backend (input normalizer + 7-layer interaction engine); allergen
 * detection is keyword-based against each family member's profile.
 */
import type { UserProfile, FamilyProfile, ReceiptAuditResult, ParsedReceiptItem } from '../../src/types';
import { ocrImageToText } from './ocr';
import { analyzeIngredientSafety } from './ingredient_safety';
import { normalizeIngredient, analyzeMedications } from './medmatch_client';

export type { ParsedReceiptItem, ReceiptAuditResult };

const MEDICATION_RE = /\b(mg|mcg|tablet|tablets|capsule|capsules|ibuprofen|paracetamol|acetaminophen|aspirin|warfarin|statin|metformin|omeprazole|amoxicillin|antibiotic)\b/i;
const SUPPLEMENT_RE = /\b(vitamin|omega|probiotic|supplement|herbal|extract|multivitamin|zinc|magnesium|calcium|coq10|ginseng|turmeric|echinacea)\b/i;
const COSMETIC_RE = /\b(shampoo|soap|cream|lotion|serum|cleanser|toothpaste|deodorant|cosmetic|skincare|sunscreen)\b/i;
const HOUSEHOLD_RE = /\b(detergent|cleaner|paper towel|tissue|trash|sponge|bleach|dish soap|fabric)\b/i;
const RECEIPT_NOISE_RE = /(total|subtotal|change|cash|card|visa|mastercard|debit|credit|tax|receipt|invoice|thank|store #|till|terminal|balance|points|saved|coupon|\$\s?\d)/i;
const PRICE_TAIL_RE = /[\s\d.,$€£]*$/;
const QTY_PREFIX_RE = /^\d+\s*[xX*]\s*/;

function classifyLine(line: string): ParsedReceiptItem['productType'] {
  if (MEDICATION_RE.test(line)) return 'medication';
  if (SUPPLEMENT_RE.test(line)) return 'supplement';
  if (COSMETIC_RE.test(line)) return 'cosmetic';
  if (HOUSEHOLD_RE.test(line)) return 'household';
  return 'food';
}

const ALLERGEN_KEYS: [RegExp, string][] = [
  [/\bmilk|dairy|lactose|whey|cheese|yogurt\b/i, 'Milk'],
  [/\begg|mayo(nnaise)?\b/i, 'Egg'],
  [/\bpeanut\b/i, 'Peanuts'],
  [/\balmond|cashew|walnut|hazelnut|pecan|pistachio|nut\b/i, 'Tree Nuts'],
  [/\bsoy|soya|tofu|edamame\b/i, 'Soy'],
  [/\bwheat|gluten|bread|pasta|barley|rye\b/i, 'Gluten / Wheat'],
  [/\bsalmon|tuna|fish\b/i, 'Fish'],
  [/\bshrimp|crab|lobster|shellfish|squid|mussel|oyster|clam\b/i, 'Shellfish'],
  [/\bsesame\b/i, 'Sesame'],
  [/\bcelery\b/i, 'Celery'],
];

function detectAllergens(line: string): string[] {
  const found: string[] = [];
  for (const [re, label] of ALLERGEN_KEYS) {
    if (re.test(line)) found.push(label);
  }
  return found;
}

function memberAllergenOverlap(item: ParsedReceiptItem, member: FamilyProfile | UserProfile): string[] {
  const known = [...(member.allergies || []), ...(member.customAllergens || [])].map((a) => a.toLowerCase());
  if (!known.length) return [];
  const haystack = [item.name, ...(item.detectedAllergens || [])].join(' ').toLowerCase();
  return known.filter((k) => k && haystack.includes(k));
}

function statusFromCounts(majorCount: number, allergenHits: number, flagged: number): { status: ParsedReceiptItem['status']; score: number } {
  if (allergenHits > 0 || majorCount > 0) return { status: 'danger', score: Math.max(5, 40 - majorCount * 10) };
  if (flagged > 1) return { status: 'caution', score: 60 };
  return { status: 'safe', score: 90 };
}

function parseReceiptLines(text: string): string[] {
  return text
    .split(/\r?\n/)
    .map((l) => l.replace(/\s+/g, ' ').trim())
    .filter((l) => l.length >= 3 && /\p{L}{3,}/u.test(l))
    .filter((l) => !RECEIPT_NOISE_RE.test(l))
    .slice(0, 24);
}

async function auditItem(
  rawLine: string,
  index: number,
  activeProfile: UserProfile,
  familyMembers: FamilyProfile[]
): Promise<ParsedReceiptItem & { hitLabel: string | null }> {
  const name = rawLine.replace(QTY_PREFIX_RE, '').replace(PRICE_TAIL_RE, '').replace(/\s+/g, ' ').trim() || `Item ${index + 1}`;
  const productType = classifyLine(rawLine);
  const detectedAllergens = detectAllergens(rawLine);
  const safety = analyzeIngredientSafety([name]);
  const flaggedAdditives = safety.filter((s) => s.hazardLevel !== 'safe').map((s) => s.name);

  // Identify the item in the medical database (Lớp 1 normalizer).
  // Strip dosage forms first: "Warfarin 5mg tablets" → "Warfarin".
  const lookupName = name
    .replace(/\b\d+(?:\.\d+)?\s*(mg|mcg|g|iu|ml)\b.*$/i, '')
    .replace(/\b(tablets?|capsules?|softgels?|gummies|drops|syrup|oil)\b/gi, '')
    .replace(/\s+/g, ' ').trim();
  const hit = productType === 'medication' || productType === 'supplement'
    ? await normalizeIngredient(lookupName)
    : null;

  const members = [{ ...activeProfile, name: activeProfile.name || 'You' } as UserProfile, ...familyMembers];
  const affected = new Set<string>();
  let allergenHitTotal = 0;
  let worstMajor = 0;
  let warningReason = '';

  for (const member of members.slice(0, 6)) {
    const allergenHits = memberAllergenOverlap({ name, detectedAllergens } as ParsedReceiptItem, member as FamilyProfile);
    let majorCount = 0;
    if (hit && (member.medications || []).length) {
      try {
        const analysis = await analyzeMedications(
          [{ name: hit.label, kind: hit.kind, matched: { kind: hit.kind, id: hit.id } }],
          { age: member.age, gender: member.gender, kidneyFunction: member.kidneyFunction, liverFunction: member.liverFunction }
        );
        majorCount = analysis.interactions.filter((i) => i.severity === 'major').length;
        if (majorCount > 0) {
          warningReason = `Interacts with ${member.name}'s medications (${analysis.interactions.filter((i) => i.severity === 'major').map((i) => `${i.a?.label || ''}×${i.b?.label || ''}`).filter(Boolean).join(', ')})`.trim();
        }
      } catch {
        // backend unreachable — allergen checks still apply
      }
    }
    if (allergenHits.length) {
      allergenHitTotal++;
      affected.add(member.name || 'Member');
      if (!warningReason) warningReason = `Contains ${allergenHits.join(', ')} — allergen for ${member.name}`;
    }
    if (majorCount > 0) affected.add(member.name || 'Member');
    worstMajor = Math.max(worstMajor, majorCount);
  }
  const { status, score } = statusFromCounts(worstMajor, allergenHitTotal, flaggedAdditives.length);
  const hitLabel = hit ? hit.label : null;
  return {
    id: `item_${index + 1}`,
    name,
    category: productType === 'food' ? 'Grocery' : productType.charAt(0).toUpperCase() + productType.slice(1),
    productType,
    ingredientsSummary: hitLabel ? hitLabel : (productType === 'medication' || productType === 'supplement' ? name : ''),
    detectedAllergens,
    flaggedAdditives,
    status,
    score,
    affectedFamilyMembers: [...affected],
    warningReason: warningReason || (flaggedAdditives.length >= 2 ? `Flagged additives: ${flaggedAdditives.slice(0, 3).join(', ')}` : undefined),
    hitLabel,
  };
}

export async function auditReceipt(
  input: {
    imageBase64?: string;
    mimeType?: string;
    receiptText?: string;
    storeNameHint?: string;
  },
  activeProfile: UserProfile,
  allFamilyProfiles: FamilyProfile[]
): Promise<ReceiptAuditResult> {
  const text = (input.receiptText && input.receiptText.trim().length > 5)
    ? input.receiptText
    : await ocrImageToText(input.imageBase64 || '', input.mimeType || 'image/jpeg');

  const lines = parseReceiptLines(text);
  const audited: (ParsedReceiptItem & { hitLabel: string | null })[] = [];
  for (let i = 0; i < Math.min(lines.length, 12); i++) {
    audited.push(await auditItem(lines[i], i, activeProfile, allFamilyProfiles));
  }

  // In-cart cross-check: interactions BETWEEN receipt items
  // (e.g. Warfarin × St John's Wort bought together). Per-member medication
  // checks already ran inside auditItem.
  const identified = audited.filter((a) => a.hitLabel);
  if (identified.length >= 2) {
    try {
      const analysis = await analyzeMedications(
        identified.map((a) => ({ name: a.hitLabel! })),
        { age: activeProfile.age, gender: activeProfile.gender, kidneyFunction: activeProfile.kidneyFunction, liverFunction: activeProfile.liverFunction }
      );
      for (const inter of analysis.interactions) {
        if (inter.severity !== 'major' && inter.severity !== 'moderate') continue;
        const la = (inter.a?.label || '').toLowerCase();
        const lb = (inter.b?.label || '').toLowerCase();
        const other = (label: string) => (label === la ? inter.b?.label : inter.a?.label);
        for (const a of audited) {
          const lbl = (a.hitLabel || '').toLowerCase();
          if (!lbl || (lbl !== la && lbl !== lb)) continue;
          a.status = inter.severity === 'major' ? 'danger' : a.status === 'danger' ? 'danger' : 'caution';
          a.score = Math.min(a.score, inter.severity === 'major' ? 20 : 50);
          a.affectedFamilyMembers = [...new Set([...a.affectedFamilyMembers, activeProfile.name || 'You'])];
          a.warningReason = `In-cart interaction: ${inter.a?.label} × ${inter.b?.label} [${inter.severity}]${inter.mechanism ? ` — ${inter.mechanism}` : ''}. Also affects: ${other(lbl)}`;
        }
      }
    } catch {
      // backend unreachable — keep allergen-only audit
    }
  }
  const items: ParsedReceiptItem[] = audited;

  const safeCount = items.filter((i) => i.status === 'safe').length;
  const flagged = items.filter((i) => i.status === 'caution').length;
  const danger = items.filter((i) => i.status === 'danger').length;
  const overallScore = items.length ? Math.round(items.reduce((sum, i) => sum + i.score, 0) / items.length) : 100;
  const ultraProcessed = items.filter((i) => i.flaggedAdditives.length >= 3).length;

  const familyImpactSummary: string[] = [];
  for (const item of items) {
    for (const member of item.affectedFamilyMembers) {
      familyImpactSummary.push(`${member}: avoid "${item.name}" — ${item.warningReason || 'flagged in audit'}`);
    }
  }

  return {
    storeName: input.storeNameHint || lines[0] || 'Unknown store',
    auditDate: new Date().toISOString(),
    totalItemsCount: items.length,
    overallScore,
    status: danger > 0 ? 'danger' : flagged > 0 ? 'caution' : 'safe',
    safeItemsCount: safeCount,
    flaggedItemsCount: flagged,
    highRiskCount: danger,
    ultraProcessedPercentage: items.length ? Math.round((ultraProcessed / items.length) * 100) : 0,
    keyAllergensFound: [...new Set(items.flatMap((i) => i.detectedAllergens))],
    criticalAdditivesFound: [...new Set(items.flatMap((i) => i.flaggedAdditives))].slice(0, 8),
    familyImpactSummary: [...new Set(familyImpactSummary)].slice(0, 12),
    items,
  };
}

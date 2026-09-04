/**
 * Local rule-based product parser — replaces Gemini Vision structured extraction.
 * Input: raw OCR/text of a label. Output: ParsedProduct (same contract the
 * frontend already consumes from /api/scan/image and /api/scan/text).
 */
import type { NutritionFacts } from '../../src/types';
import { ocrImageToText } from './ocr';

export interface ParsedProduct {
  productName: string;
  brand?: string;
  productType: 'food' | 'cosmetic';
  ingredientsText: string;
  ingredientsList: string[];
  hasIngredientSection?: boolean;
  allergens: string[];
  labels: string[];
  nutrition?: NutritionFacts;
}

const LABEL_PATTERNS: [RegExp, string][] = [
  [/\bvegan\b/i, 'Vegan'],
  [/\bvegetarian\b/i, 'Vegetarian'],
  [/\bgluten[\s-]*free\b/i, 'Gluten-Free'],
  [/\borganic\b/i, 'Organic'],
  [/\bkosher\b/i, 'Kosher'],
  [/\bhalal\b/i, 'Halal'],
  [/\bhypoallergenic\b/i, 'Hypoallergenic'],
  [/\bnon[\s-]*gmo\b/i, 'Non-GMO'],
  [/\bsugar[\s-]*free\b/i, 'Sugar-Free'],
  [/\bparaben[\s-]*free\b/i, 'Paraben-Free'],
  [/\bfragrance[\s-]*free\b/i, 'Fragrance-Free'],
  [/\bdermatologist( tested| approved)?\b/i, 'Dermatologist Tested'],
];

const ALLERGEN_PATTERNS: [RegExp, string][] = [
  [/\b(milk|dairy|lactose|whey|casein)\b/i, 'Milk'],
  [/\b(egg|albumin)\b/i, 'Egg'],
  [/\bpeanut(s)?\b/i, 'Peanuts'],
  [/\b(almond|cashew|walnut|hazelnut|pecan|pistachio|macadamia|brazil nut|tree nut)\b/i, 'Tree Nuts'],
  [/\b(soy|soya|soybean)\b/i, 'Soy'],
  [/\b(wheat|gluten|barley|rye|spelt)\b/i, 'Gluten / Wheat'],
  [/\b(fish|cod|salmon|tuna)\b/i, 'Fish'],
  [/\b(shellfish|shrimp|crab|lobster|crayfish|mollusk|clam|mussel|oyster|squid)\b/i, 'Shellfish'],
  [/\bsesame\b/i, 'Sesame'],
  [/\bmustard\b/i, 'Mustard'],
  [/\bcelery\b/i, 'Celery'],
  [/\b(sulphite|sulfite)\b/i, 'Sulphites'],
];

const COSMETIC_RE = /\b(serum|cleanser|moisturi[sz]er|shampoo|conditioner|lotion|cream|skin|skincare|hair|cosmetic|spf|sunscreen|retinol|niacinamide|toner|balm|deodorant|makeup|mascara)\b/i;
const INGREDIENT_SECTION_RE = /\b(ingredients?|thành phần|composition|contains|inactive ingredients)\b/i;
const NOISE_LINE_RE = /^(product|brand|net wt|made in|best before|lot|exp)\b/i;

const FREE_CLAIM_RE = /\b[\p{L}][\p{L}\s-]{0,20}[\s-]*free\b/giu;

function detectAllergens(text: string): string[] {
  // "gluten-free", "dairy-free"... are safety claims, not allergen content
  const content = text.replace(FREE_CLAIM_RE, ' ');
  const found: string[] = [];
  for (const [re, label] of ALLERGEN_PATTERNS) {
    if (re.test(content)) found.push(label);
  }
  return found;
}

function detectLabels(text: string): string[] {
  const found: string[] = [];
  for (const [re, label] of LABEL_PATTERNS) {
    if (re.test(text)) found.push(label);
  }
  return found;
}

function splitIngredients(section: string): string[] {
  const cleaned = section
    // drop dosage/percent tokens that pollute ingredient names
    .replace(/\d+(?:\.\d+)?\s*(%|mg|mcg|µg|ug|g|kg|ml|iu)\b/gi, ' ')
    // E-number codes and bare numbers inside parens add noise
    .replace(/\((?:[^)]*\bE\s?\d{3,4}[a-z]?\b[^)]*|[^)]*\d[^)]*)\)/gi, ' ');
  const parts = cleaned
    .split(/[,;•|·\u2022\n\u2028\u2029]|\bdelivers\b|\bcontains\b(?!\s*(?:no|nothing))/gi)
    .map((p) => p
      .replace(INGREDIENT_SECTION_RE, ' ')
      .replace(/^[^\p{L}]+|[^\p{L}\)\]]+$/gu, ' ')
      .replace(/\s+/g, ' ')
      .trim())
    .filter((p) => {
      if (p.length < 2 || p.length > 64) return false;
      if (!/\p{L}{3,}/u.test(p)) return false; // needs a real word
      if (NOISE_LINE_RE.test(p)) return false;
      // allergen-statement fragments, not ingredients: "none", "Gluten free. Vegan"
      if (/^(none|nothing)\b/i.test(p)) return false;
      if (/^[\p{L}\s-]*free\b/giu.test(p)) return false;
      return true;
    });
  // dedupe case-insensitive, preserve order
  const seen = new Set<string>();
  const out: string[] = [];
  for (const p of parts) {
    const key = p.toLowerCase();
    if (!seen.has(key)) {
      seen.add(key);
      out.push(p);
    }
  }
  return out.slice(0, 60);
}

function detectBrand(lines: string[]): string | undefined {
  const brandLine = lines.find((l) => /^(brand|by|manufactured by|distributed by)\b/i.test(l));
  if (brandLine) return brandLine.replace(/^(brand|by|manufactured by|distributed by)\s*[:\-]?\s*/i, '').replace(/\s+/g, ' ').trim();
  return undefined;
}

/** Parse raw ingredient-list text (from OCR or user typing) into a structured product. */
export function parseIngredientsText(rawText: string, suggestedName?: string): ParsedProduct {
  const raw = (rawText || '').trim();
  const lines = raw.split(/\r?\n/).map((l) => l.replace(/\s+/g, ' ').trim()).filter(Boolean);

  // Product name: first line that is not an ingredient-section header / noise.
  let productName = suggestedName?.trim() || '';
  if (!productName) {
    const nameLine = lines.find((l) => !INGREDIENT_SECTION_RE.test(l) && l.length >= 3 && l.length <= 90);
    productName = nameLine ? nameLine.replace(/^product\s*[:\-]\s*/i, '') : 'Scanned product';
  }

  // Brand: explicit "Brand:" line, else nothing (OCR rarely yields a clean company line).
  const brand = detectBrand(lines);
  const headerIdx = lines.findIndex((l) => INGREDIENT_SECTION_RE.test(l));
  const hasIngredientSection = headerIdx >= 0;
  const ingredientsText = hasIngredientSection
    ? lines.slice(headerIdx).join(', ').replace(/^[^:]*:\s*/, '')
    : lines.join(', ');
  const ingredientsList = splitIngredients(ingredientsText);

  return {
    productName,
    brand,
    productType: COSMETIC_RE.test(raw) ? 'cosmetic' : 'food',
    ingredientsText,
    ingredientsList,
    hasIngredientSection,
    allergens: detectAllergens(raw),
    labels: detectLabels(raw),
  };
}

/** Parse a product label photo: local OCR → rule-based structuring. No API key. */
export async function parseProductImage(imageBase64: string, mimeType = 'image/jpeg'): Promise<ParsedProduct> {
  const text = await ocrImageToText(imageBase64, mimeType);
  if (!text) {
    return {
      productName: 'Unreadable label',
      productType: 'food',
      ingredientsText: '',
      ingredientsList: [],
      allergens: [],
      labels: [],
    };
  }
  return parseIngredientsText(text);
}

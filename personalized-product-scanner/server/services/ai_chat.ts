/**
 * Rule-based health advisor — replaces the Gemini dietitian chat.
 * Every sentence is synthesized from the structured MedMatch 7-layer analysis
 * already attached to the product, so answers are deterministic, source-backed
 * and need no API key. The medical verdict always comes from the engine, never
 * from a language model.
 */
import type { ProductScanResult, UserProfile, MedMatchAnalysis } from '../../src/types';

const SEVERITY_RANK: Record<string, number> = {
  contraindicated: 0,
  major: 1,
  moderate: 2,
  minor: 3,
  mild: 3,
  evidence: 4,
};

const SEVERITY_WORD: Record<string, string> = {
  contraindicated: 'CONTRAINDICATED',
  major: 'MAJOR',
  moderate: 'Moderate',
  minor: 'Minor',
  mild: 'Minor',
  evidence: 'Evidence-only',
};

function worstSeverity(medMatch?: MedMatchAnalysis): string | null {
  const levels = (medMatch?.interactions || []).map((i) => i.severity).filter(Boolean) as string[];
  if (!levels.length) return null;
  return levels.sort((a, b) => (SEVERITY_RANK[a] ?? 9) - (SEVERITY_RANK[b] ?? 9))[0];
}

function interactionLines(medMatch: MedMatchAnalysis | undefined, limit: number): string[] {
  const rows = [...(medMatch?.interactions || [])]
    .sort((a, b) => (SEVERITY_RANK[a.severity as string] ?? 9) - (SEVERITY_RANK[b.severity as string] ?? 9))
    .slice(0, limit);
  return rows.map((i) => {
    const sev = SEVERITY_WORD[i.severity as string] || 'Info';
    const pair = i.a?.label && i.b?.label ? `${i.a.label} × ${i.b.label}` : 'Combination';
    const why = i.mechanism || i.effect || '';
    const act = i.action ? ` Action: ${i.action}` : '';
    return `- [${sev}] ${pair} — ${why}.${act}`;
  });
}

function depletionLines(medMatch: MedMatchAnalysis): string[] {
  const out: string[] = [];
  for (const d of medMatch.depletions || []) {
    out.push(`- ${d.ingredient} (${d.severity})${d.mechanism ? ` — ${d.mechanism}` : ''}`);
  }
  for (const e of medMatch.electrolytes || []) {
    out.push(`- Electrolyte: ${e.electrolyte} — ${(e.reasons || []).join(' ')} ${e.secondary_risk || ''}`.trim());
  }
  return out;
}

function profileRiskLines(medMatch: MedMatchAnalysis): string[] {
  const out: string[] = [];
  for (const q of medMatch.qt_risk || []) {
    out.push(`- QT prolongation risk: ${String(q.level).toUpperCase()} — groups: ${(q.qt_classes || []).join(', ') || 'n/a'}${q.factors?.length ? `; patient factors: ${q.factors.join(', ')}` : ''}`);
  }
  for (const b of medMatch.beers || []) {
    out.push(`- Beers Criteria (65+): ${b.label} [${b.level}] — ${b.note}`);
  }
  for (const c of medMatch.cascades || []) {
    out.push(`- Enzyme cascade (inferred, trust ${c.trust}): ${c.chain.map((s) => `${s.label} (${s.role})`).join(' → ')}`);
  }
  return out;
}

function scheduleLines(medMatch: MedMatchAnalysis): string[] {
  return (medMatch.schedule || []).map((s) => `- ${s.a} and ${s.b}: take at least ${s.min_hours} hours apart (${s.reason})`);
}

function allergenLines(product: ProductScanResult, profile: UserProfile): string[] {
  const declared = product.allergens || [];
  const userAllergies = [...(profile.allergies || []), ...(profile.customAllergens || [])];
  const hits = declared.filter((a) => userAllergies.some((u) => a.toLowerCase().includes(u.toLowerCase()) || u.toLowerCase().includes(a.toLowerCase())));
  const lines: string[] = [];
  if (declared.length) lines.push(`- Declared allergens on label: ${declared.join(', ')}.`);
  if (hits.length) lines.push(`- ⚠ Matches YOUR profile: ${hits.join(', ')} — avoid this product.`);
  if (profile.dietType) {
    lines.push(`- Diet: ${profile.dietType}. Check the label badges for compliance (the scan result lists them).`);
  }
  return lines;
}

function overviewLines(product: ProductScanResult, medMatch?: MedMatchAnalysis): string[] {
  const lines: string[] = [];
  const interactions = medMatch?.interactions || [];
  const worst = worstSeverity(medMatch);
  lines.push(`Product: ${product.productName || 'unnamed scan'} (${product.productType || 'food'}).`);
  if (worst) {
    lines.push(`Overall interaction picture: worst finding is ${SEVERITY_WORD[worst] || worst}, ${interactions.length} documented finding(s) across ${medMatch?.matched?.length || 0} recognized items.`);
  } else {
    lines.push('No documented interactions were found for this product in the MedMatch database.');
  }
  for (const line of interactionLines(medMatch, 3)) lines.push(line);
  if (medMatch?.depletions?.length) lines.push(`- Nutrient depletion watch: ${medMatch.depletions.map((d) => d.ingredient).join(', ')}.`);
  return lines;
}

const DISCLAIMER = 'This is reference information from public databases, not medical advice — confirm with your doctor or pharmacist.';

export async function askMedMatchAdvisor(
  question: string,
  productContext: ProductScanResult,
  userProfile: UserProfile
): Promise<string> {
  const q = (question || '').toLowerCase();
  const medMatch = productContext?.medMatch;
  const sections: string[] = [];

  const wants = (...keys: string[]) => keys.some((k) => q.includes(k));

  if (!productContext || (!medMatch && !(productContext.ingredientsList || []).length)) {
    return 'I can only reason from a scanned product — scan a label or barcode first, then ask me about it.\n\n' + DISCLAIMER;
  }

  if (wants('interact', 'danger', 'safe', 'combine', 'warning', 'risk') || !q) {
    const lines = overviewLines(productContext, medMatch);
    if (lines.length > 2) sections.push('Interaction picture:\n' + lines.join('\n'));
  }
  if (wants('nutrient', 'deplet', 'vitamin', 'mineral', 'coq10', 'b12', 'magnesium', 'potassium')) {
    const lines = medMatch ? depletionLines(medMatch) : [];
    sections.push(lines.length
      ? 'Nutrient & electrolyte depletion:\n' + lines.join('\n')
      : 'Nutrient & electrolyte depletion:\n- No depletion data flags for these ingredients.');
  }
  if (wants('schedule', 'when ', 'timing', 'morning', 'evening', 'hours apart')) {
    const lines = medMatch ? scheduleLines(medMatch) : [];
    sections.push(lines.length
      ? 'Scheduling:\n' + lines.join('\n')
      : 'Scheduling:\n- No absorption-type conflicts that timing can defuse.');
  }
  if (wants('qt', 'heart', 'rhythm', 'palpitation', 'torsades')) {
    const lines = medMatch ? profileRiskLines(medMatch).filter((l) => l.includes('QT')) : [];
    sections.push(lines.length
      ? 'QT / rhythm risk:\n' + lines.join('\n')
      : 'QT / rhythm risk:\n- No QT-prolonging drugs detected in this combination.');
  }
  if (wants('beers', 'senior', 'older', 'elderly', '65')) {
    const lines = medMatch ? profileRiskLines(medMatch).filter((l) => l.includes('Beers')) : [];
    sections.push(lines.length
      ? 'Older-adult safety (Beers 2023):\n' + lines.join('\n')
      : 'Older-adult safety (Beers 2023):\n- No Beers Criteria flags for this combination.');
  }
  if (wants('allerg', 'diet', 'vegan', 'gluten', 'lactose', 'avoid')) {
    const lines = allergenLines(productContext, userProfile);
    if (lines.length) sections.push('Allergen & diet check:\n' + lines.join('\n'));
  }
  if (wants('alternative', 'swap', 'replace', 'instead', 'substitute')) {
    sections.push('Alternatives:\n- Open the Smart Swaps tab — every candidate there is re-verified against your medication list by the 7-layer engine before it is shown.');
  }
  if (!sections.length) {
    sections.push('Overview:\n' + overviewLines(productContext, medMatch).join('\n'));
  }

  sections.push(DISCLAIMER);
  return sections.join('\n\n');
}

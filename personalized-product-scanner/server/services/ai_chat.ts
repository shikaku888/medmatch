import { GoogleGenAI } from '@google/genai';
import { ProductScanResult, UserProfile, MedMatchAnalysis } from '../../src/types';

let aiClient: GoogleGenAI | null = null;

function getGenAI(): GoogleGenAI {
  if (!aiClient) {
    aiClient = new GoogleGenAI({
      apiKey: process.env.GEMINI_API_KEY,
      httpOptions: {
        headers: {
          'User-Agent': 'aistudio-build'
        }
      }
    });
  }
  return aiClient;
}

/** Render the authoritative MedMatch engine verdict for the AI advisory prompt. */
function formatMedMatchContext(medMatch?: MedMatchAnalysis): string {
  if (!medMatch) return '- No MedMatch analysis on file for this product.';
  const parts: string[] = [];
  const interactions = medMatch.interactions || [];
  parts.push(`- Interaction alerts on file: ${interactions.length}`);
  for (const it of interactions.slice(0, 12)) {
    const sev = it.severity ? it.severity.toUpperCase() : 'EVIDENCE';
    const detail = it.effect || it.mechanism || '';
    const src = it.source ? ` (source: ${it.source}${it.doi ? `, DOI ${it.doi}` : ''})` : '';
    parts.push(`  * [${sev}] ${it.a.label} × ${it.b.label}${detail ? ' — ' + detail : ''}${src}`);
  }
  if (medMatch.depletions?.length) {
    parts.push(`- Nutrient depletions: ${medMatch.depletions.map(d => `${d.ingredient} (${d.severity})`).join(', ')}`);
  }
  if (medMatch.qt_risk?.length) {
    parts.push(`- QT prolongation risk: ${medMatch.qt_risk.map(q => q.level).join(', ')} — classes: ${medMatch.qt_risk.flatMap(q => q.qt_classes || []).join(', ') || 'n/a'}`);
  }
  if (medMatch.beers?.length) {
    parts.push(`- Beers Criteria flags (65+): ${medMatch.beers.map(b => `${b.label} [${b.level}]`).join(', ')}`);
  }
  if (medMatch.cascades?.length) {
    parts.push(`- Enzyme cascade chains detected: ${medMatch.cascades.length} (${medMatch.cascades.map(c => (c.enzymes || []).join(' -> ')).join('; ')})`);
  }
  if (medMatch.schedule?.length) {
    parts.push(`- Schedule conflicts: ${medMatch.schedule.map(s => `${s.a} × ${s.b}: ${s.reason}`).join('; ')}`);
  }
  if (medMatch.electrolytes?.length) {
    parts.push(`- Electrolyte flags: ${medMatch.electrolytes.map(e => e.electrolyte).join(', ')}`);
  }
  return parts.join('\n');
}

export async function askGeminiDietitian(
  question: string,
  productContext: ProductScanResult,
  userProfile: UserProfile
): Promise<string> {
  try {
    const ai = getGenAI();

    const userProfileSummary = `
- Allergies: ${userProfile.allergies.join(', ') || 'None'}
- Custom Allergens: ${userProfile.customAllergens.join(', ') || 'None'}
- Diet Type: ${userProfile.dietType}
- Medical/Skin Conditions: ${userProfile.specialConditions.join(', ') || 'None'}
- Current Medications: ${userProfile.medications?.join(', ') || 'None'}
- Age: ${userProfile.age ?? 'Not provided'}
`;

    const productSummary = `
- Name: ${productContext.productName}
- Brand: ${productContext.brand || 'Unknown'}
- Type: ${productContext.productType}
- Ingredients: ${productContext.ingredientsText || productContext.ingredientsList?.join(', ') || 'None'}
- Warnings: ${productContext.matchAssessment.warnings.map(w => `${w.title}: ${w.message}`).join(' | ') || 'None'}
- Score: ${productContext.matchAssessment.score}/100
- Nutrition: ${JSON.stringify(productContext.nutrition || {})}
`;

    const medMatchSummary = formatMedMatchContext(productContext.medMatch);

    const prompt = `You are the supplementary AI Health Advisor inside MedMatch AI, a drug & supplement interaction checker.
The user just scanned a product and is asking a follow-up question.

AUTHORITATIVE CONTEXT — verdicts from the MedMatch 7-layer engine on verified databases (SUPP.AI, DDInter, DailyMed, openFDA FAERS, RxNorm). This is the source of truth for safety:
${medMatchSummary}

USER PROFILE:
${userProfileSummary}

SCANNED PRODUCT:
${productSummary}

USER QUESTION:
"${question}"

STRICT ROLE RULES:
1. NEVER invent, downgrade, or contradict the MedMatch verdicts above. If your general knowledge disagrees with an alert, defer to the alert and say so.
2. Your job is explanation and education only: clarify what an alert means, the biology in plain language, usage tips, and what to ask a doctor or pharmacist.
3. You are NOT the safety authority. Never present your answer as a medical alert, diagnosis, or clearance.
4. If the question needs a decision (start/stop/change medication or supplement), direct the user to the alerts above and a healthcare professional.
5. Answer accurately and concisely (max 3-4 short paragraphs or bullet points). End with one short line reminding the user that this chat is supplementary AI guidance, not a medical alert.`;

    const response = await ai.models.generateContent({
      model: 'gemini-3.7-flash',
      contents: prompt,
    });

    return response.text?.trim() || 'I could not generate an answer at this time. Please try again.';
  } catch (err: any) {
    console.error('AI Dietitian error:', err);
    return 'Our clinical AI advisory is momentarily unavailable. Please check your network connection and try again.';
  }
}

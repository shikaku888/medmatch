import { GoogleGenAI } from '@google/genai';
import { ProductScanResult, UserProfile } from '../../src/types';

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

    const prompt = `You are an empathetic, world-class Board-Certified Clinical Dietitian, Toxicologist, and Product Safety Expert.
The user is asking a question regarding a product they just scanned:

USER PROFILE:
${userProfileSummary}

SCANNED PRODUCT:
${productSummary}

USER QUESTION:
"${question}"

Provide an accurate, concise, grounded, and practical answer (max 3-4 short paragraphs or bullet points).
Explain biological/clinical reasoning in plain language. If relevant, suggest safe usage tips or ingredient alternatives. Always maintain professional medical disclaimer etiquette when appropriate.`;

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

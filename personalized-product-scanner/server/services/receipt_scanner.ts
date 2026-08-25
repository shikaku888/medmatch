import { GoogleGenAI, Type } from '@google/genai';
import { UserProfile, FamilyProfile, SafeSwapRecommendation } from '../../src/types';
import { DEMO_PRODUCTS } from '../demoData';
import { MARKET_PRODUCTS } from '../marketPresets';
import { analyzeIngredientSafety } from './ingredient_safety';

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

export interface ParsedReceiptItem {
  id: string;
  name: string;
  category: string;
  quantity?: number;
  estimatedPrice?: string;
  productType: 'food' | 'cosmetic' | 'household' | 'medication' | 'supplement';
  ingredientsSummary: string;
  detectedAllergens: string[];
  flaggedAdditives: string[];
  novaGroup?: number;
  status: 'safe' | 'caution' | 'danger';
  score: number; // 0-100
  affectedFamilyMembers: string[]; // Names of family members who should avoid this item
  warningReason?: string;
  suggestedSwap?: {
    name: string;
    brand: string;
    whyBetter: string;
  };
}

export interface ReceiptAuditResult {
  storeName: string;
  auditDate: string;
  totalItemsCount: number;
  overallScore: number; // 0-100
  status: 'safe' | 'caution' | 'danger';
  safeItemsCount: number;
  flaggedItemsCount: number;
  highRiskCount: number;
  ultraProcessedPercentage: number;
  keyAllergensFound: string[];
  criticalAdditivesFound: string[];
  familyImpactSummary: string[];
  items: ParsedReceiptItem[];
}

export async function parseAndAuditReceiptWithGemini(
  input: {
    imageBase64?: string;
    mimeType?: string;
    receiptText?: string;
    storeNameHint?: string;
  },
  activeProfile: UserProfile,
  allFamilyProfiles: FamilyProfile[]
): Promise<ReceiptAuditResult> {
  const ai = getGenAI();

  const familyContext = allFamilyProfiles.map(p => ({
    name: p.name,
    role: p.role,
    age: p.age,
    allergies: p.allergies || [],
    diet: p.dietType,
    conditions: p.specialConditions || [],
    currentMedications: p.medications || []
  }));

  const systemPrompt = `You are an expert Clinical Toxicologist & Pharmacy-Grocery Receipt Auditor.
Your task is to analyze a receipt / shopping cart (either from an OCR image or receipt text) that may contain groceries, personal care, cosmetics, AND medications or dietary supplements.
1. Extract ALL purchased items. Classify each productType as 'food', 'cosmetic', 'household', 'medication' (OTC or prescription) or 'supplement' (vitamins, minerals, herbals).
2. For each item:
   - Identify standard common ingredients, additives (e.g. E-numbers, artificial colorants, high sodium, trans fats, preservatives like BHT/Parabens, endocrine disruptors). For medications/supplements, list active ingredients in ingredientsSummary.
   - Check conflicts against ANY household member:
     Active User: ${activeProfile.name || 'User'} (Allergies: ${activeProfile.allergies.join(', ') || 'None'}, Diet: ${activeProfile.dietType}, Conditions: ${activeProfile.specialConditions?.join(', ') || 'None'}, Medications: ${(activeProfile.medications || []).join(', ') || 'None'}, Age: ${activeProfile.age ?? 'n/a'})
     Full Household Profiles: ${JSON.stringify(familyContext)}
   - For 'medication'/'supplement' items: flag known interactions with any member's currentMedications or conditions (e.g. warfarin vs vitamin K supplements, NSAIDs vs hypertension; decongestants vs blood pressure). Put the interaction in warningReason and name affected members in affectedFamilyMembers. Mark status 'danger' for serious interaction risk, 'caution' for minor/uncertain.
   - For food/cosmetic items: status 'danger' only for severe allergy or high toxicity.
   - Assign a suitability score (0-100). NOVA group (1-4) for food only; omit for medications/supplements.
   - If an item is flagged ('caution' or 'danger'), suggest a specific safer 'suggestedSwap' (e.g. swap Nutella with SunButter, swap a decongestant for a saline spray, swap a vitamin-K heavy supplement for a K-free formula).
3. Compute overall cart score, ultra-processed ratio, and top family-wide warnings (medication interactions first, then allergies).`;

  let response;

  if (input.imageBase64) {
    const imagePart = {
      inlineData: {
        data: input.imageBase64.replace(/^data:[^;]+;base64,/, ''),
        mimeType: input.mimeType || 'image/jpeg'
      }
    };
    response = await ai.models.generateContent({
      model: 'gemini-3.7-flash',
      contents: {
        parts: [
          imagePart,
          { text: `${systemPrompt}\n\nParse this receipt image and return the structured audit JSON.` }
        ]
      },
      config: {
        responseMimeType: 'application/json',
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            storeName: { type: Type.STRING },
            overallScore: { type: Type.NUMBER },
            status: { type: Type.STRING, enum: ['safe', 'caution', 'danger'] },
            ultraProcessedPercentage: { type: Type.NUMBER },
            familyImpactSummary: {
              type: Type.ARRAY,
              items: { type: Type.STRING }
            },
            items: {
              type: Type.ARRAY,
              items: {
                type: Type.OBJECT,
                properties: {
                  name: { type: Type.STRING },
                  category: { type: Type.STRING },
                  quantity: { type: Type.NUMBER },
                  estimatedPrice: { type: Type.STRING },
                  productType: { type: Type.STRING, enum: ['food', 'cosmetic', 'household', 'medication', 'supplement'] },
                  ingredientsSummary: { type: Type.STRING },
                  detectedAllergens: {
                    type: Type.ARRAY,
                    items: { type: Type.STRING }
                  },
                  flaggedAdditives: {
                    type: Type.ARRAY,
                    items: { type: Type.STRING }
                  },
                  novaGroup: { type: Type.NUMBER },
                  status: { type: Type.STRING, enum: ['safe', 'caution', 'danger'] },
                  score: { type: Type.NUMBER },
                  affectedFamilyMembers: {
                    type: Type.ARRAY,
                    items: { type: Type.STRING }
                  },
                  warningReason: { type: Type.STRING },
                  suggestedSwap: {
                    type: Type.OBJECT,
                    properties: {
                      name: { type: Type.STRING },
                      brand: { type: Type.STRING },
                      whyBetter: { type: Type.STRING }
                    }
                  }
                },
                required: ['name', 'category', 'status', 'score', 'ingredientsSummary']
              }
            }
          },
          required: ['storeName', 'overallScore', 'status', 'items', 'familyImpactSummary']
        }
      }
    });
  } else {
    const textPrompt = `${systemPrompt}\n\nReceipt Text / Grocery Order:\n"""\n${input.receiptText || 'Supermarket Grocery Receipt'}\n"""\n\nStore hint: ${input.storeNameHint || 'Supermarket'}`;
    response = await ai.models.generateContent({
      model: 'gemini-3.7-flash',
      contents: textPrompt,
      config: {
        responseMimeType: 'application/json',
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            storeName: { type: Type.STRING },
            overallScore: { type: Type.NUMBER },
            status: { type: Type.STRING, enum: ['safe', 'caution', 'danger'] },
            ultraProcessedPercentage: { type: Type.NUMBER },
            familyImpactSummary: {
              type: Type.ARRAY,
              items: { type: Type.STRING }
            },
            items: {
              type: Type.ARRAY,
              items: {
                type: Type.OBJECT,
                properties: {
                  name: { type: Type.STRING },
                  category: { type: Type.STRING },
                  quantity: { type: Type.NUMBER },
                  estimatedPrice: { type: Type.STRING },
                  productType: { type: Type.STRING, enum: ['food', 'cosmetic', 'household', 'medication', 'supplement'] },
                  ingredientsSummary: { type: Type.STRING },
                  detectedAllergens: {
                    type: Type.ARRAY,
                    items: { type: Type.STRING }
                  },
                  flaggedAdditives: {
                    type: Type.ARRAY,
                    items: { type: Type.STRING }
                  },
                  novaGroup: { type: Type.NUMBER },
                  status: { type: Type.STRING, enum: ['safe', 'caution', 'danger'] },
                  score: { type: Type.NUMBER },
                  affectedFamilyMembers: {
                    type: Type.ARRAY,
                    items: { type: Type.STRING }
                  },
                  warningReason: { type: Type.STRING },
                  suggestedSwap: {
                    type: Type.OBJECT,
                    properties: {
                      name: { type: Type.STRING },
                      brand: { type: Type.STRING },
                      whyBetter: { type: Type.STRING }
                    }
                  }
                },
                required: ['name', 'category', 'status', 'score', 'ingredientsSummary']
              }
            }
          },
          required: ['storeName', 'overallScore', 'status', 'items', 'familyImpactSummary']
        }
      }
    });
  }

  const rawJson = response.text?.trim() || '{}';
  const parsed = JSON.parse(rawJson);

  // Format and enrich items
  const items: ParsedReceiptItem[] = (parsed.items || []).map((item: any, idx: number) => ({
    id: `item_${Date.now()}_${idx}`,
    name: item.name || 'Unnamed Grocery Item',
    category: item.category || 'Pantry Item',
    quantity: item.quantity || 1,
    estimatedPrice: item.estimatedPrice,
    productType: item.productType || 'food',
    ingredientsSummary: item.ingredientsSummary || 'Standard ingredient mix',
    detectedAllergens: item.detectedAllergens || [],
    flaggedAdditives: item.flaggedAdditives || [],
    novaGroup: item.novaGroup || 3,
    status: item.status || (item.score < 50 ? 'danger' : item.score < 80 ? 'caution' : 'safe'),
    score: typeof item.score === 'number' ? item.score : 70,
    affectedFamilyMembers: item.affectedFamilyMembers || [],
    warningReason: item.warningReason,
    suggestedSwap: item.suggestedSwap
  }));

  const safeCount = items.filter(i => i.status === 'safe').length;
  const flaggedCount = items.filter(i => i.status === 'caution').length;
  const highRiskCount = items.filter(i => i.status === 'danger').length;

  const allergensSet = new Set<string>();
  const additivesSet = new Set<string>();
  items.forEach(i => {
    i.detectedAllergens.forEach(a => allergensSet.add(a));
    i.flaggedAdditives.forEach(ad => additivesSet.add(ad));
  });

  return {
    storeName: parsed.storeName || input.storeNameHint || 'Grocery Store',
    auditDate: new Date().toISOString(),
    totalItemsCount: items.length,
    overallScore: Math.round(parsed.overallScore || (items.length > 0 ? items.reduce((a, b) => a + b.score, 0) / items.length : 80)),
    status: parsed.status || (highRiskCount > 0 ? 'danger' : flaggedCount > 1 ? 'caution' : 'safe'),
    safeItemsCount: safeCount,
    flaggedItemsCount: flaggedCount,
    highRiskCount: highRiskCount,
    ultraProcessedPercentage: Math.round(parsed.ultraProcessedPercentage || (items.filter(i => (i.novaGroup || 1) >= 4).length / (items.length || 1) * 100)),
    keyAllergensFound: Array.from(allergensSet),
    criticalAdditivesFound: Array.from(additivesSet),
    familyImpactSummary: parsed.familyImpactSummary || [
      `${safeCount} out of ${items.length} items meet optimal family biological safety criteria.`
    ],
    items
  };
}

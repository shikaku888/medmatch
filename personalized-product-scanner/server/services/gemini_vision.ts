import { GoogleGenAI, Type } from '@google/genai';
import { NutritionFacts, ProductScanResult } from '../../src/types';

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

export interface GeminiParsedProduct {
  productName: string;
  brand?: string;
  productType: 'food' | 'cosmetic';
  ingredientsText: string;
  ingredientsList: string[];
  allergens: string[];
  labels: string[];
  nutrition?: NutritionFacts;
}

export async function parseProductImageWithGemini(
  base64Data: string,
  mimeType: string = 'image/jpeg'
): Promise<GeminiParsedProduct> {
  const ai = getGenAI();

  const prompt = `Analyze this product label, package, or ingredient list photo.
Extract the product name, brand, product type ('food' or 'cosmetic'), complete ingredient text, array of distinct ingredients, declared allergens, declared dietary/safety labels (e.g. vegan, gluten-free, organic, kosher, halal, hypoallergenic), and nutrition facts if available.
Be rigorous and accurate with ingredient names.`;

  const imagePart = {
    inlineData: {
      data: base64Data.replace(/^data:[^;]+;base64,/, ''),
      mimeType
    }
  };

  const response = await ai.models.generateContent({
    model: 'gemini-3.7-flash',
    contents: {
      parts: [imagePart, { text: prompt }]
    },
    config: {
      responseMimeType: 'application/json',
      responseSchema: {
        type: Type.OBJECT,
        properties: {
          productName: { type: Type.STRING, description: 'Product title' },
          brand: { type: Type.STRING, description: 'Brand or manufacturer' },
          productType: { type: Type.STRING, enum: ['food', 'cosmetic'], description: 'Food or cosmetic product' },
          ingredientsText: { type: Type.STRING, description: 'Full verbatim ingredient text' },
          ingredientsList: {
            type: Type.ARRAY,
            items: { type: Type.STRING },
            description: 'Clean list of individual ingredients'
          },
          allergens: {
            type: Type.ARRAY,
            items: { type: Type.STRING },
            description: 'Detected or declared allergens (milk, peanuts, wheat, soy, fragrance, etc.)'
          },
          labels: {
            type: Type.ARRAY,
            items: { type: Type.STRING },
            description: 'Certified or declared claims: vegan, organic, gluten-free, kosher, etc.'
          },
          nutrition: {
            type: Type.OBJECT,
            properties: {
              energyKcal: { type: Type.NUMBER },
              sugars: { type: Type.NUMBER },
              salt: { type: Type.NUMBER },
              sodium: { type: Type.NUMBER },
              fat: { type: Type.NUMBER },
              saturatedFat: { type: Type.NUMBER },
              proteins: { type: Type.NUMBER },
              carbohydrates: { type: Type.NUMBER },
              fiber: { type: Type.NUMBER },
              servingSize: { type: Type.STRING }
            }
          }
        },
        required: ['productName', 'productType', 'ingredientsText', 'ingredientsList']
      }
    }
  });

  const rawJson = response.text?.trim() || '{}';
  const parsed = JSON.parse(rawJson) as GeminiParsedProduct;
  return parsed;
}

export async function parseRawIngredientsTextWithGemini(
  rawText: string,
  suggestedName?: string
): Promise<GeminiParsedProduct> {
  const ai = getGenAI();

  const prompt = `Analyze this ingredient list text:
"${rawText}"
Product Name: ${suggestedName || 'Scanned Product'}

Parse product details: identify if it is 'food' or 'cosmetic', full ingredient text, structured ingredients list array, potential allergens, and dietary labels.`;

  const response = await ai.models.generateContent({
    model: 'gemini-3.7-flash',
    contents: prompt,
    config: {
      responseMimeType: 'application/json',
      responseSchema: {
        type: Type.OBJECT,
        properties: {
          productName: { type: Type.STRING },
          brand: { type: Type.STRING },
          productType: { type: Type.STRING, enum: ['food', 'cosmetic'] },
          ingredientsText: { type: Type.STRING },
          ingredientsList: {
            type: Type.ARRAY,
            items: { type: Type.STRING }
          },
          allergens: {
            type: Type.ARRAY,
            items: { type: Type.STRING }
          },
          labels: {
            type: Type.ARRAY,
            items: { type: Type.STRING }
          }
        },
        required: ['productName', 'productType', 'ingredientsText', 'ingredientsList']
      }
    }
  });

  const rawJson = response.text?.trim() || '{}';
  return JSON.parse(rawJson) as GeminiParsedProduct;
}

import { GoogleGenAI, Type } from '@google/genai';
import { ProductScanResult, UserProfile, SafeSwapRecommendation } from '../../src/types';
import { DEMO_PRODUCTS } from '../demoData';

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
export async function generateSafeSwaps(
  currentProduct: ProductScanResult,
  userProfile: UserProfile
): Promise<SafeSwapRecommendation[]> {
  try {
    const ai = getGenAI();

    const userConditions = [
      ...userProfile.allergies.map(a => `Allergy: ${a}`),
      ...userProfile.customAllergens.map(a => `Custom allergy: ${a}`),
      `Diet: ${userProfile.dietType}`,
      ...userProfile.specialConditions.map(c => `Condition: ${c}`)
    ].join(', ');

    const prompt = `You are an expert clinical dietitian and toxicologist.
The user scanned: "${currentProduct.productName}" (Brand: "${currentProduct.brand || 'Unknown'}", Type: "${currentProduct.productType}").
Current flags: ${currentProduct.matchAssessment.warnings.map(w => w.title).join('; ') || 'None'}.
User constraints: ${userConditions || 'Standard healthy preferences'}.

Recommend 3 real-world, commercial healthier, safer, and 100% compliant ALTERNATIVE products ("Safe Swaps") that the user can buy in grocery stores or pharmacies.
Ensure the recommendations completely avoid the user's allergies and match their diet.`;

    const response = await ai.models.generateContent({
      model: 'gemini-3.7-flash',
      contents: prompt,
      config: {
        responseMimeType: 'application/json',
        responseSchema: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              id: { type: Type.STRING },
              name: { type: Type.STRING, description: 'Real brand and product name' },
              brand: { type: Type.STRING },
              productType: { type: Type.STRING, enum: ['food', 'cosmetic'] },
              category: { type: Type.STRING },
              score: { type: Type.INTEGER, description: 'Compatibility score 85-99' },
              whyBetter: { 
                type: Type.ARRAY, 
                items: { type: Type.STRING },
                description: 'Key reasons why this is safer than the scanned item'
              },
              keyBenefits: {
                type: Type.ARRAY,
                items: { type: Type.STRING },
                description: 'Health, nutrition, or skin benefits'
              },
              cleanHighlights: {
                type: Type.ARRAY,
                items: { type: Type.STRING },
                description: 'e.g. Non-GMO, Organic, Fragrance-Free, Nut-Free, Keto-Certified'
              },
              priceRange: { type: Type.STRING, description: 'e.g. $ - Affordable or $$ - Moderate' },
              certificationBadges: {
                type: Type.ARRAY,
                items: { type: Type.STRING }
              },
              activeIngredients: {
                type: Type.ARRAY,
                items: { type: Type.STRING },
                description: 'Main active ingredients or notable actives of the recommended product (for foods: key ingredients like Milk, Soy, Hazelnut; for supplements/cosmetics: active compounds like St John Wort extract, Retinol, Vitamin K). Needed to cross-check drug interactions.'
              }
            },
            required: ['name', 'brand', 'productType', 'score', 'whyBetter', 'keyBenefits', 'cleanHighlights', 'activeIngredients']
          }
        }
      }
    });

    const rawJson = response.text?.trim() || '[]';
    const parsed = JSON.parse(rawJson) as SafeSwapRecommendation[];
    if (parsed && parsed.length > 0) {
      return parsed.map((item, idx) => ({
        ...item,
        id: item.id || `swap_${Date.now()}_${idx}`,
        score: Math.max(85, Math.min(99, item.score || 92))
      }));
    }
  } catch (err) {
    console.warn('Gemini Safe Swaps generation fallback:', err);
  }

  // Fallback curated swaps if API fails
  if (currentProduct.productType === 'food') {
    return [
      {
        id: 'swap_fb_1',
        name: 'Organic Whole Oat Milk (Unsweetened)',
        brand: 'Oatly / Califia Farms',
        productType: 'food',
        category: 'Dairy Alternative',
        score: 95,
        whyBetter: ['Zero dairy or lactose', 'Zero added sugars', 'Glyphosate residue-free certified'],
        keyBenefits: ['Fortified with Vitamin B12 and D', 'Clean single-digit ingredient deck'],
        cleanHighlights: ['Certified Vegan', 'Dairy-Free', 'Nut-Free facility'],
        priceRange: '$$ - Average',
        activeIngredients: ['Oats', 'Water'],
        certificationBadges: ['USDA Organic', 'Non-GMO Project']
      },
      {
        id: 'swap_fb_2',
        name: 'Roasted Sunflower Seed Butter (Creamy)',
        brand: 'SunButter',
        productType: 'food',
        category: 'Nut Butter Alternative',
        score: 98,
        whyBetter: ['100% Free of Top 8 Allergens', 'Zero peanuts or tree nuts', 'School safe'],
        keyBenefits: ['7g Plant Protein per serving', 'Rich in Vitamin E and Magnesium'],
        cleanHighlights: ['Peanut-Free', 'Tree Nut-Free', 'Kosher'],
        priceRange: '$ - Affordable',
        activeIngredients: ['Sunflower Seeds', 'Salt'],
        certificationBadges: ['Certified Gluten-Free', 'School Safe']
      },
      {
        id: 'swap_fb_3',
        name: 'Artisan Ancient Grain Sourdough',
        brand: 'Base Culture / Simple Mills',
        productType: 'food',
        category: 'Bakery',
        score: 91,
        whyBetter: ['Naturally fermented', 'Zero high-fructose corn syrup or bleached flour'],
        keyBenefits: ['Gentle on digestion', 'Lower glycemic spike'],
        cleanHighlights: ['Gluten-Free Option', 'Non-GMO', 'No Artificial Preservatives'],
        priceRange: '$$ - Moderate',
        activeIngredients: ['Ancient Grain Flour', 'Sourdough Culture', 'Water', 'Salt'],
        certificationBadges: ['Non-GMO Verified']
      }
    ];
  } else {
    return [
      {
        id: 'swap_fb_c1',
        name: 'Toleriane Double Repair Matte Face Moisturizer',
        brand: 'La Roche-Posay',
        productType: 'cosmetic',
        category: 'Skincare',
        score: 97,
        whyBetter: ['100% Fragrance-Free', 'No drying alcohol or essential oils', 'Non-comedogenic'],
        keyBenefits: ['Ceramide-3 + Niacinamide barrier repair', 'Prebiotic thermal water'],
        cleanHighlights: ['Dermatologist Tested', 'Sensitive Skin Safe', 'Oil-Free'],
        priceRange: '$$ - Mid Tier',
        activeIngredients: ['Ceramide-3', 'Niacinamide', 'Thermal Spring Water', 'Glycerin'],
        certificationBadges: ['National Eczema Association Accepted']
      },
      {
        id: 'swap_fb_c2',
        name: 'Ultra Gentle Hydrating Daily Cleanser',
        brand: 'Vanicream / CeraVe',
        productType: 'cosmetic',
        category: 'Cleanser',
        score: 99,
        whyBetter: ['Free of parabens, sulfates, formaldehyde releasers', 'Zero botanical allergens'],
        keyBenefits: ['Maintains skin lipid mantle', 'Safe for eczema and rosacea'],
        cleanHighlights: ['Fragrance-Free', 'Preservative-Free', 'Hypoallergenic'],
        priceRange: '$ - Value',
        activeIngredients: ['Glycerin', 'Cetearyl Alcohol', 'Ceramide-3'],
        certificationBadges: ['National Eczema Association']
      }
    ];
  }
}

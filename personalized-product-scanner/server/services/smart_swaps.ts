/**
 * Data-driven safe swaps — replaces the Gemini suggestion engine.
 * Candidates come from the iDISK 69K-product catalog via the MedMatch backend
 * (/api/products); server.ts then re-verifies every candidate against the
 * user's medication list with the 7-layer engine before display. A small
 * curated fallback covers food/cosmetic categories the catalog doesn't have.
 */
import type { ProductScanResult, UserProfile, SafeSwapRecommendation } from '../../src/types';
import { medMatchFetch } from './medmatch_client';

interface IdiskProduct {
  dsp_id: string;
  name: string;
  company: string;
  ingredients: string[];
}

const CURATED_FOOD_SWAPS: SafeSwapRecommendation[] = [
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
    certificationBadges: ['USDA Organic', 'Non-GMO Project'],
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
    certificationBadges: ['Certified Gluten-Free', 'School Safe'],
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
    certificationBadges: ['Non-GMO Verified'],
  },
];

const CURATED_COSMETIC_SWAPS: SafeSwapRecommendation[] = [
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
    certificationBadges: ['National Eczema Association Accepted'],
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
    certificationBadges: ['National Eczema Association'],
  },
];

async function searchIdisk(query: string, limit = 6): Promise<IdiskProduct[]> {
  try {
    const { results } = await medMatchFetch<{ results: IdiskProduct[] }>(
      `/api/products?q=${encodeURIComponent(query)}&limit=${limit}`
    );
    return results || [];
  } catch {
    return [];
  }
}

function forbiddenTokens(profile: UserProfile, product: ProductScanResult): string[] {
  const meds = (profile.medications || []).map((m) => m.toLowerCase());
  const avoided = (product.medMatch?.interactions || [])
    .flatMap((i) => [i.a?.label, i.b?.label])
    .filter(Boolean)
    .map((l) => (l as string).toLowerCase());
  return [...new Set([...meds, ...avoided])];
}
/** Anchor ingredients the swap must replace (matched entities beat raw strings). */
function swapAnchors(product: ProductScanResult): string[] {
  const anchors: string[] = [];
  for (const m of product.medMatch?.matched || []) {
    if (m.label && !anchors.includes(m.label)) anchors.push(m.label);
  }
  for (const ing of (product.ingredientsList || []).slice(0, 10)) {
    const word = ing.replace(/\s*\d+(?:\.\d+)?\s*(mg|mcg|iu|%)\b.*$/i, '').trim();
    if (word.length >= 4 && !anchors.some((a) => a.toLowerCase() === word.toLowerCase())) anchors.push(word);
    if (anchors.length >= 3) break;
  }
  return anchors.slice(0, 3);
}

export async function generateSafeSwaps(
  currentProduct: ProductScanResult,
  userProfile: UserProfile
): Promise<SafeSwapRecommendation[]> {
  const anchors = swapAnchors(currentProduct);
  const forbidden = forbiddenTokens(userProfile, currentProduct);
  const seen = new Set<string>();
  const candidates: SafeSwapRecommendation[] = [];

  for (const anchor of anchors) {
    const query = anchor.split(/\s+/).slice(-1)[0];
    const anchorKey = anchor.toLowerCase();
    const pool = await searchIdisk(query, 8);
    for (const p of pool) {
      const nameKey = p.name.toLowerCase();
      if (seen.has(nameKey)) continue;
      const ingredients = (p.ingredients || []).map((i) => i.toLowerCase());
      // a swap must NOT contain the anchor we are replacing, nor any user medication token
      if (nameKey.includes(anchorKey) || ingredients.some((i) => i.includes(anchorKey))) continue;
      if (ingredients.some((i) => forbidden.some((f) => f && (i.includes(f) || nameKey.includes(f))))) continue;
      if (ingredients.every((i) => !i) && !/vitamin|omega|probiotic|extract|herb/i.test(nameKey)) continue;
      seen.add(nameKey);
      candidates.push({
        id: p.dsp_id,
        name: p.name,
        brand: p.company || 'iDISK catalog',
        productType: 'food',
        category: `Alternative to ${anchor}`,
        score: 88,
        whyBetter: [
          `Does not contain ${anchor}`,
          'Catalog entry verified against your medication list below',
        ],
        keyBenefits: (p.ingredients || []).slice(0, 4),
        cleanHighlights: ['Interaction-checked by MedMatch engine'],
        activeIngredients: (p.ingredients || []).slice(0, 6),
      });
      if (candidates.length >= 5) break;
    }
    if (candidates.length >= 5) break;
  }

  if (candidates.length) return candidates;
  return currentProduct.productType === 'food' ? CURATED_FOOD_SWAPS : CURATED_COSMETIC_SWAPS;
}

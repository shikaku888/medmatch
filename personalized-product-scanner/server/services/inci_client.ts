import { CosmeticProfile } from '../../src/types';

// Standard INCI Safety & Sensitivity Dictionary
const FRAGRANCE_NAMES = [
  'fragrance', 'parfum', 'perfume', 'linalool', 'limonene', 'citronellol', 
  'geraniol', 'eugenol', 'cinnamal', 'hydroxycitronellal', 'coumarin', 'benzyl alcohol'
];

const PARABEN_NAMES = [
  'methylparaben', 'propylparaben', 'butylparaben', 'ethylparaben', 'isobutylparaben', 'paraben'
];

const SULFATE_NAMES = [
  'sodium lauryl sulfate', 'sls', 'sodium laureth sulfate', 'sles', 'ammonium lauryl sulfate',
  'sodium coco-sulfate', 'sulfate'
];

const DRYING_ALCOHOL_NAMES = [
  'alcohol denat', 'denatured alcohol', 'isopropyl alcohol', 'sd alcohol', 'ethanol'
];

const RETINOID_NAMES = [
  'retinol', 'retinal', 'retinaldehyde', 'retinyl palmitate', 'tretinoin', 'adapalene', 'tazarotene'
];

const SALICYLIC_NAMES = [
  'salicylic acid', 'betaine salicylate', 'willow bark extract'
];

const COMEDOGENIC_RATINGS: Record<string, number> = {
  'isopropyl myristate': 5,
  'isopropyl isostearate': 5,
  'myristyl myristate': 5,
  'coconut oil': 4,
  'cocos nucifera oil': 4,
  'cocoa butter': 4,
  'lauric acid': 4,
  'wheat germ oil': 5,
  'algae extract': 4,
  'acetylated lanolin': 4,
  'palm oil': 4,
  'shea butter': 1,
  'jojoba oil': 2,
  'squalane': 1,
  'mineral oil': 0,
  'glycerin': 0,
  'hyaluronic acid': 0,
  'niacinamide': 0,
  'ceramide': 0
};

export function analyzeCosmeticIngredients(ingredientsList: string[], ingredientsText: string): CosmeticProfile {
  const textLower = (ingredientsText + ' ' + ingredientsList.join(' ')).toLowerCase();

  const hasFragrance = FRAGRANCE_NAMES.some(f => textLower.includes(f));
  const hasParabens = PARABEN_NAMES.some(p => textLower.includes(p));
  const hasSulfates = SULFATE_NAMES.some(s => textLower.includes(s));
  const hasAlcohol = DRYING_ALCOHOL_NAMES.some(a => textLower.includes(a));
  const hasRetinoids = RETINOID_NAMES.some(r => textLower.includes(r));
  const hasSalicylicAcid = SALICYLIC_NAMES.some(sa => textLower.includes(sa));

  // Calculate highest comedogenic rating
  let maxComedogenic = 0;
  for (const ing of ingredientsList) {
    const ingLower = ing.toLowerCase().trim();
    for (const [key, rating] of Object.entries(COMEDOGENIC_RATINGS)) {
      if (ingLower.includes(key)) {
        if (rating > maxComedogenic) maxComedogenic = rating;
      }
    }
  }

  const summaryParts: string[] = [];
  if (hasFragrance) summaryParts.push('Contains fragrance/essential allergens');
  if (hasParabens) summaryParts.push('Contains preservative parabens');
  if (hasSulfates) summaryParts.push('Contains surfactants/sulfates');
  if (hasAlcohol) summaryParts.push('Contains drying alcohol');
  if (hasRetinoids) summaryParts.push('Contains active Vitamin A/Retinoids');
  if (hasSalicylicAcid) summaryParts.push('Contains BHA/Salicylic Acid');
  if (maxComedogenic >= 3) summaryParts.push(`Pore-clogging potential (rating ${maxComedogenic}/5)`);

  return {
    category: 'Cosmetic / Personal Care',
    comedogenicRating: maxComedogenic,
    hasFragrance,
    hasParabens,
    hasSulfates,
    hasAlcohol,
    hasRetinoids,
    hasSalicylicAcid,
    safetySummary: summaryParts.length > 0 ? summaryParts.join(' • ') : 'Clean formulation without common cosmetic irritants'
  };
}

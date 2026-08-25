import { db } from '../db';
import { NutritionFacts, ProductScanResult, SupportedCountry, UkTrafficLight, CleanScoreBreakdown } from '../../src/types';

export interface RawOffProduct {
  code?: string;
  product_name?: string;
  product_name_en?: string;
  product_name_fr?: string;
  product_name_de?: string;
  product_name_es?: string;
  product_name_it?: string;
  brands?: string;
  image_url?: string;
  image_front_url?: string;
  ingredients_text?: string;
  ingredients_text_en?: string;
  ingredients_text_fr?: string;
  ingredients_text_de?: string;
  ingredients_text_es?: string;
  ingredients_text_it?: string;
  ingredients?: Array<{ id: string; text: string; percent_estimate?: number }>;
  allergens_tags?: string[];
  allergens?: string;
  labels_tags?: string[];
  labels?: string;
  nutriments?: Record<string, any>;
  nova_group?: number;
  nutriscore_grade?: string;
  ecoscore_grade?: string;
  categories_tags?: string[];
  countries_tags?: string[];
}

/**
 * Client for Multi-Region Open Food Facts and Open Beauty Facts (US, UK, FR, DE, IT, ES, VN)
 */
export async function getProductFromOFF(barcode: string, country?: SupportedCountry): Promise<{
  productName: string;
  brand?: string;
  countryOfOrigin?: string;
  productType: 'food' | 'cosmetic';
  imageUrl?: string;
  ingredientsText: string;
  ingredientsList: string[];
  allergens: string[];
  labels: string[];
  nutrition?: NutritionFacts;
  cleanScoreBreakdown?: CleanScoreBreakdown;
  categories?: string[];
  source: 'openfoodfacts' | 'openbeautyfacts';
} | null> {
  const cleanBarcode = barcode.trim();
  const targetCountry = country || 'US';
  const cacheKey = `off:barcode:${cleanBarcode}:${targetCountry}`;
  
  const cached = db.getCache<any>(cacheKey);
  if (cached) {
    return cached;
  }

  const countryPrefixMap: Record<SupportedCountry, string> = {
    US: 'us',
    UK: 'uk',
    FR: 'fr',
    DE: 'de',
    IT: 'it',
    ES: 'es'
  };

  const domainPrefix = countryPrefixMap[targetCountry] || 'world';

  // 1. Try Country-Specific Open Food Facts, fallback to world
  const offEndpoints = [
    `https://${domainPrefix}.openfoodfacts.org/api/v2/product/${cleanBarcode}.json`,
    `https://world.openfoodfacts.org/api/v2/product/${cleanBarcode}.json`
  ];

  for (const offUrl of offEndpoints) {
    try {
      const res = await fetch(offUrl, {
        headers: {
          'User-Agent': 'MedMatch-SafeScanner/2.0 (multicountry-compliance; contact: support@productscanner.app)'
        },
        signal: AbortSignal.timeout(4500)
      });

      if (res.ok) {
        const data = await res.json();
        if (data.status === 1 && data.product) {
          const p: RawOffProduct = data.product;
          const result = parseOffProduct(p, cleanBarcode, 'food');
          db.setCache(cacheKey, result);
          return result;
        }
      }
    } catch (err) {
      console.warn(`OpenFoodFacts fetch error for ${cleanBarcode} at ${offUrl}:`, err);
    }
  }

  // 2. Try Open Beauty Facts for cosmetics / personal care
  try {
    const obfUrl = `https://world.openbeautyfacts.org/api/v2/product/${cleanBarcode}.json`;
    const res = await fetch(obfUrl, {
      headers: {
        'User-Agent': 'MedMatch-SafeScanner/2.0 (cosmetic-radar; contact: support@productscanner.app)'
      },
      signal: AbortSignal.timeout(4500)
    });

    if (res.ok) {
      const data = await res.json();
      if (data.status === 1 && data.product) {
        const p: RawOffProduct = data.product;
        const result = parseOffProduct(p, cleanBarcode, 'cosmetic');
        db.setCache(cacheKey, result);
        return result;
      }
    }
  } catch (err) {
    console.warn(`OpenBeautyFacts fetch error for ${cleanBarcode}:`, err);
  }

  return null;
}

function parseOffProduct(p: RawOffProduct, barcode: string, forcedType?: 'food' | 'cosmetic') {
  const name = p.product_name || p.product_name_en || p.product_name_fr || p.product_name_de || p.product_name_es || p.product_name_it || 'Scanned Product';
  const brand = p.brands;
  const imageUrl = p.image_front_url || p.image_url;
  const ingredientsText = p.ingredients_text || p.ingredients_text_en || p.ingredients_text_fr || p.ingredients_text_de || p.ingredients_text_es || p.ingredients_text_it || '';
  
  // Parse ingredient list
  let ingredientsList: string[] = [];
  if (Array.isArray(p.ingredients) && p.ingredients.length > 0) {
    ingredientsList = p.ingredients.map(i => i.text || i.id.replace(/^[a-z]+:/, '')).filter(Boolean);
  } else if (ingredientsText) {
    ingredientsList = ingredientsText
      .split(/[,;\n\(\)\[\]•]/)
      .map(s => s.trim())
      .filter(s => s.length > 1 && !s.toLowerCase().startsWith('contains'));
  }

  // Parse allergens
  const allergens: string[] = [];
  if (Array.isArray(p.allergens_tags)) {
    for (const tag of p.allergens_tags) {
      const clean = tag.replace(/^[a-z]{2}:/, '').toLowerCase().trim();
      if (clean && !allergens.includes(clean)) allergens.push(clean);
    }
  } else if (typeof p.allergens === 'string') {
    p.allergens.split(',').forEach(a => {
      const clean = a.trim().toLowerCase();
      if (clean && !allergens.includes(clean)) allergens.push(clean);
    });
  }

  // Parse labels (vegan, vegetarian, organic, bio, halal, kosher, gluten-free, etc.)
  const labels: string[] = [];
  if (Array.isArray(p.labels_tags)) {
    for (const tag of p.labels_tags) {
      const clean = tag.replace(/^[a-z]{2}:/, '').toLowerCase().trim();
      if (clean && !labels.includes(clean)) labels.push(clean);
    }
  }

  // Detect cosmetic vs food
  const categories = p.categories_tags || [];
  const isCosmetic = forcedType === 'cosmetic' || 
    categories.some(c => c.includes('cosmetic') || c.includes('beauty') || c.includes('skin') || c.includes('hair') || c.includes('care') || c.includes('cream') || c.includes('shampoo'));

  const nutriments = p.nutriments || {};
  const fat = nutriments['fat_100g'] ?? nutriments['fat'];
  const satFat = nutriments['saturated-fat_100g'] ?? nutriments['saturated-fat'];
  const sugars = nutriments['sugars_100g'] ?? nutriments['sugars'];
  const salt = nutriments['salt_100g'] ?? nutriments['salt'];
  const sodium = nutriments['sodium_100g'] ?? nutriments['sodium'] ?? (salt ? salt / 2.5 : undefined);
  const energyKcal = nutriments['energy-kcal_100g'] ?? nutriments['energy-kcal'] ?? (nutriments['energy_100g'] ? Math.round(nutriments['energy_100g'] / 4.184) : undefined);
  const carbs = nutriments['carbohydrates_100g'] ?? nutriments['carbohydrates'];
  const fiber = nutriments['fiber_100g'] ?? nutriments['fiber'];
  const proteins = nutriments['proteins_100g'] ?? nutriments['proteins'];

  // UK Traffic Light calculation (UK FSA standard per 100g)
  const ukTrafficLight: UkTrafficLight = {
    fatLevel: fat !== undefined ? (fat <= 3.0 ? 'low' : fat > 17.5 ? 'high' : 'med') : undefined,
    satFatLevel: satFat !== undefined ? (satFat <= 1.5 ? 'low' : satFat > 5.0 ? 'high' : 'med') : undefined,
    sugarsLevel: sugars !== undefined ? (sugars <= 5.0 ? 'low' : sugars > 22.5 ? 'high' : 'med') : undefined,
    saltLevel: salt !== undefined ? (salt <= 0.3 ? 'low' : salt > 1.5 ? 'high' : 'med') : undefined
  };

  // US Daily Values reference (2000 kcal diet)
  const usDVs = {
    caloriesPercent: energyKcal ? Math.round((energyKcal / 2000) * 100) : undefined,
    fatPercent: fat ? Math.round((fat / 78) * 100) : undefined,
    satFatPercent: satFat ? Math.round((satFat / 20) * 100) : undefined,
    sodiumPercent: sodium ? Math.round(((sodium * 1000) / 2300) * 100) : undefined,
    carbsPercent: carbs ? Math.round((carbs / 275) * 100) : undefined,
    fiberPercent: fiber ? Math.round((fiber / 28) * 100) : undefined
  };

  const nutriscoreGrade = (p.nutriscore_grade?.toLowerCase() as any) || undefined;
  const ecoscoreGrade = (p.ecoscore_grade?.toLowerCase() as any) || undefined;

  const nutrition: NutritionFacts = {
    energyKcal,
    sugars,
    salt,
    sodium,
    fat,
    saturatedFat: satFat,
    proteins,
    carbohydrates: carbs,
    fiber,
    novaGroup: p.nova_group || nutriments['nova-group'],
    nutriscoreGrade,
    ecoscoreGrade,
    ukTrafficLight,
    usDVs
  };

  // Yuka-Style Clean Score calculation (60% Nutrition + 30% Additives + 10% Organic Bio)
  let nutritionPoints = 40; // Default C
  if (nutriscoreGrade === 'a') nutritionPoints = 60;
  else if (nutriscoreGrade === 'b') nutritionPoints = 50;
  else if (nutriscoreGrade === 'c') nutritionPoints = 35;
  else if (nutriscoreGrade === 'd') nutritionPoints = 20;
  else if (nutriscoreGrade === 'e') nutritionPoints = 10;

  // Bio bonus (10 pts)
  const isOrganic = labels.some(l => l.includes('organic') || l.includes('bio') || l.includes('ab-agriculture-biologique') || l.includes('usda'));
  const organicPoints = isOrganic ? 10 : 0;

  // Additives quality initial base 30 pts
  const additivePoints = 30;
  const totalScore = Math.min(100, Math.max(5, nutritionPoints + organicPoints + additivePoints));

  let ratingLevel: CleanScoreBreakdown['ratingLevel'] = 'good';
  if (totalScore >= 75) ratingLevel = 'excellent';
  else if (totalScore >= 50) ratingLevel = 'good';
  else if (totalScore >= 25) ratingLevel = 'mediocre';
  else ratingLevel = 'bad';

  const cleanScoreBreakdown: CleanScoreBreakdown = {
    totalScore,
    nutritionalQualityScore: nutritionPoints,
    additivesSafetyScore: additivePoints,
    organicBioBonus: organicPoints,
    ratingLevel
  };

  const countries = p.countries_tags || [];
  const countryOfOrigin = countries.length > 0 ? countries[0].replace('en:', '').toUpperCase() : undefined;

  return {
    productName: name,
    brand,
    countryOfOrigin,
    productType: (isCosmetic ? 'cosmetic' : 'food') as 'food' | 'cosmetic',
    imageUrl,
    ingredientsText,
    ingredientsList,
    allergens,
    labels,
    nutrition: isCosmetic ? undefined : nutrition,
    cleanScoreBreakdown: isCosmetic ? undefined : cleanScoreBreakdown,
    categories,
    source: (isCosmetic ? 'openbeautyfacts' : 'openfoodfacts') as 'openfoodfacts' | 'openbeautyfacts'
  };
}


import { db } from '../db';
import { NutritionFacts } from '../../src/types';

/**
 * USDA FoodData Central Client
 * Fallback for US-centric food products when Open Food Facts doesn't have the barcode
 */
export async function searchUSDAFood(query: string): Promise<{
  productName: string;
  brand?: string;
  productType: 'food';
  ingredientsText: string;
  ingredientsList: string[];
  allergens: string[];
  labels: string[];
  nutrition?: NutritionFacts;
  source: 'usda';
} | null> {
  const cacheKey = `usda:search:${query.toLowerCase().trim()}`;
  const cached = db.getCache<any>(cacheKey);
  if (cached) return cached;

  const apiKey = process.env.USDA_API_KEY || 'DEMO_KEY';
  const url = `https://api.nal.usda.gov/fdc/v1/foods/search?query=${encodeURIComponent(query)}&pageSize=1&api_key=${apiKey}`;

  try {
    const res = await fetch(url, {
      headers: {
        'User-Agent': 'PersonalizedProductScanner/1.0'
      },
      signal: AbortSignal.timeout(5000)
    });

    if (res.ok) {
      const data = await res.json();
      const food = data?.foods?.[0];
      if (food) {
        const ingredientsText = food.ingredients || '';
        const ingredientsList = ingredientsText
          .split(/[,;]/)
          .map((s: string) => s.trim())
          .filter((s: string) => s.length > 1);

        const nutrients = food.foodNutrients || [];
        const findNutrient = (nameOrNum: string | number) => {
          const item = nutrients.find((n: any) => 
            (n.nutrientName && n.nutrientName.toLowerCase().includes(String(nameOrNum).toLowerCase())) ||
            n.nutrientNumber === String(nameOrNum)
          );
          return item ? item.value : undefined;
        };

        const nutrition: NutritionFacts = {
          energyKcal: findNutrient('energy') ?? findNutrient(208),
          proteins: findNutrient('protein') ?? findNutrient(203),
          fat: findNutrient('total lipid') ?? findNutrient(204),
          carbohydrates: findNutrient('carbohydrate') ?? findNutrient(205),
          sugars: findNutrient('sugars') ?? findNutrient(269),
          sodium: findNutrient('sodium') ?? findNutrient(307),
          fiber: findNutrient('fiber') ?? findNutrient(291)
        };

        const result = {
          productName: food.description || query,
          brand: food.brandOwner || food.brandName,
          productType: 'food' as const,
          ingredientsText,
          ingredientsList,
          allergens: [],
          labels: [],
          nutrition,
          source: 'usda' as const
        };

        db.setCache(cacheKey, result);
        return result;
      }
    }
  } catch (err) {
    console.warn(`USDA lookup error for "${query}":`, err);
  }

  return null;
}

import { UserProfile, MatchWarning, ProductScanResult, CosmeticProfile, CrossReactivityAlert, RoutineAuditCheckResult } from '../../src/types';
import { getPubMedResearch } from './pubmed_client';
import { detectCrossReactivities } from './cross_reactivity';
import { extractSkincareActives, analyzeSkincareRoutineConflicts } from './skincare_conflicts';
import { db } from '../db';

const ALLERGEN_SYNONYMS: Record<string, string[]> = {
  peanut: ['peanut', 'arachis', 'groundnut', 'monkey nut', 'peanut butter', 'peanut oil', 'arachis hypogaea'],
  tree_nut: ['almond', 'cashew', 'walnut', 'hazelnut', 'pecan', 'pistachio', 'macadamia', 'brazil nut', 'chestnut', 'prunus dulcis', 'anacardium'],
  milk: ['milk', 'dairy', 'whey', 'casein', 'caseinate', 'lactose', 'butter', 'cream', 'cheese', 'ghee', 'curd', 'yogurt', 'milkfat', 'skimmed milk', 'lactalbumin', 'sodium caseinate'],
  gluten: ['gluten', 'wheat', 'barley', 'rye', 'spelt', 'kamut', 'malt', 'semolina', 'durum', 'farina', 'graham flour', 'triticale', 'wheat flour', 'wheat starch'],
  egg: ['egg', 'albumin', 'ovalbumin', 'globulin', 'lysozyme', 'mayonnaise', 'yolk', 'egg white', 'ovomucin', 'ovovitellin'],
  soy: ['soy', 'soya', 'soybean', 'tofu', 'edamame', 'tamari', 'miso', 'tempeh', 'soy lecithin', 'glycine max', 'hydrolyzed soy protein'],
  fish: ['fish', 'salmon', 'tuna', 'cod', 'anchovy', 'tilapia', 'halibut', 'mackerel', 'sardine', 'fish oil', 'fish sauce', 'isinglass'],
  shellfish: ['shellfish', 'crustacean', 'shrimp', 'prawn', 'crab', 'lobster', 'crawfish', 'clam', 'mussel', 'oyster', 'scallop', 'squid', 'calamari', 'octopus', 'mollusc'],
  sesame: ['sesame', 'tahini', 'sesamum indicum', 'benne', 'sesame oil', 'sesame seed'],
  sulfite: ['sulfite', 'sulphite', 'sulfur dioxide', 'e220', 'e221', 'e222', 'e223', 'e224', 'e228', 'sodium metabisulfite', 'potassium metabisulfite'],
  mustard: ['mustard', 'sinapis alba', 'brassica nigra'],
  celery: ['celery', 'celeriac', 'apium graveolens'],
  lupin: ['lupin', 'lupine', 'lupinus'],
  mollusc: ['mollusc', 'mollusk', 'snail', 'slug', 'squid', 'clam', 'oyster', 'mussel'],
  fragrance: ['fragrance', 'parfum', 'perfume', 'linalool', 'limonene', 'citronellol', 'geraniol', 'eugenol', 'cinnamal', 'hydroxycitronellal', 'coumarin'],
  parabens: ['methylparaben', 'propylparaben', 'butylparaben', 'ethylparaben', 'isobutylparaben', 'paraben'],
  sulfates: ['sodium lauryl sulfate', 'sls', 'sodium laureth sulfate', 'sles', 'ammonium lauryl sulfate', 'sodium coco-sulfate'],
  alcohol: ['alcohol denat', 'denatured alcohol', 'isopropyl alcohol', 'sd alcohol', 'ethanol'],
  essential_oils: ['essential oil', 'lavender oil', 'tea tree oil', 'eucalyptus oil', 'citrus peel oil', 'peppermint oil', 'rosemary oil'],
  retinoid: ['retinol', 'retinal', 'retinaldehyde', 'retinyl palmitate', 'tretinoin', 'adapalene', 'tazarotene'],
  salicylic_acid: ['salicylic acid', 'betaine salicylate', 'willow bark extract']
};

const NON_VEGAN_INGREDIENTS = [
  'meat', 'beef', 'pork', 'chicken', 'poultry', 'lamb', 'bacon', 'ham', 'gelatin', 'carmine', 'cochineal',
  'e120', 'casein', 'whey', 'lactose', 'honey', 'beeswax', 'cera alba', 'lard', 'tallow', 'collagen',
  'keratin', 'lanolin', 'shellac', 'isinglass', 'fish oil', 'anchovy', 'duck fat', 'animal fat'
];

const NON_VEGETARIAN_INGREDIENTS = [
  'meat', 'beef', 'pork', 'chicken', 'poultry', 'lamb', 'bacon', 'ham', 'gelatin', 'carmine', 'cochineal',
  'e120', 'lard', 'tallow', 'collagen', 'isinglass', 'anchovy', 'animal fat', 'rennet'
];

const NON_HALAL_INGREDIENTS = [
  'pork', 'bacon', 'ham', 'lard', 'swine', 'porcine', 'gelatin (pork)', 'alcohol', 'ethanol', 'wine',
  'beer', 'rum', 'brandy', 'carmine', 'e120'
];

const NON_KOSHER_INGREDIENTS = [
  'pork', 'bacon', 'ham', 'lard', 'shellfish', 'shrimp', 'crab', 'lobster', 'clam', 'oyster', 'crawfish',
  'catfish', 'eel', 'carmine', 'e120'
];

const PREGNANCY_RISK_INGREDIENTS = [
  { name: 'retinol', risk: 'high', reason: 'High-dose Vitamin A derivatives have clinical teratogenic risks during pregnancy.' },
  { name: 'retinal', risk: 'high', reason: 'Retinoids are medically contraindicated during pregnancy.' },
  { name: 'retinyl palmitate', risk: 'high', reason: 'Retinoid derivative caution during pregnancy.' },
  { name: 'tretinoin', risk: 'high', reason: 'Prescription/strong retinoid strictly contraindicated in pregnancy.' },
  { name: 'hydroquinone', risk: 'high', reason: 'High skin absorption rate; contraindicated during pregnancy.' },
  { name: 'salicylic acid', risk: 'medium', reason: 'High concentrations of BHA are recommended to be limited during pregnancy.' },
  { name: 'unpasteurized', risk: 'high', reason: 'Listeria contamination risk in unpasteurized food products.' },
  { name: 'saccharin', risk: 'low', reason: 'Artificial sweetener that crosses placenta slowly.' }
];

export async function assessProductMatch(
  product: {
    productName: string;
    productType: 'food' | 'cosmetic';
    ingredientsText: string;
    ingredientsList: string[];
    allergens: string[];
    labels: string[];
    nutrition?: any;
    cosmetic?: CosmeticProfile;
  },
  userProfile: UserProfile
): Promise<{
  status: 'safe' | 'caution' | 'warning' | 'danger';
  score: number;
  summary: string;
  warnings: MatchWarning[];
  safeHighlights: string[];
  crossReactivityAlerts?: CrossReactivityAlert[];
  skincareActiveCheck?: RoutineAuditCheckResult;
}> {
  const warnings: MatchWarning[] = [];
  const safeHighlights: string[] = [];
  const fullText = (product.ingredientsText + ' ' + product.ingredientsList.join(' ') + ' ' + product.allergens.join(' ')).toLowerCase();
  const labelsClean = product.labels.map(l => l.toLowerCase().trim());

  // 1. ALLERGY MATCHING (Level: High / Danger)
  const userAllergies = [...userProfile.allergies];
  
  for (const allergyKey of userAllergies) {
    const synonyms = ALLERGEN_SYNONYMS[allergyKey] || [allergyKey.toLowerCase()];
    let matchedSynonym: string | null = null;

    // Check declared allergens first
    for (const declared of product.allergens) {
      const decClean = declared.toLowerCase();
      if (synonyms.some(s => decClean.includes(s) || s.includes(decClean))) {
        matchedSynonym = declared;
        break;
      }
    }

    // Check ingredients list & text
    if (!matchedSynonym) {
      for (const syn of synonyms) {
        // Word boundary match or substring check
        const regex = new RegExp(`\\b${syn}\\b`, 'i');
        if (regex.test(fullText) || fullText.includes(syn)) {
          matchedSynonym = syn;
          break;
        }
      }
    }

    if (matchedSynonym) {
      warnings.push({
        id: `warn_allergy_${allergyKey}`,
        level: 'high',
        category: 'allergy',
        title: `Allergy Conflict: Contains ${allergyKey.replace('_', ' ').toUpperCase()}`,
        message: `This product contains "${matchedSynonym}", which directly conflicts with your declared ${allergyKey.replace('_', ' ')} allergy.`,
        matchedItem: matchedSynonym,
        explanation: `Immediate risk of allergic reaction. You have active avoidance configured for this allergen.`
      });
    }
  }

  // Custom user allergens
  for (const custom of userProfile.customAllergens) {
    const cleanCustom = custom.trim().toLowerCase();
    if (cleanCustom.length > 1 && fullText.includes(cleanCustom)) {
      warnings.push({
        id: `warn_custom_${cleanCustom}`,
        level: 'high',
        category: 'allergy',
        title: `Custom Sensitivity Alert: "${custom}"`,
        message: `Found "${custom}" in the product ingredients list.`,
        matchedItem: custom,
        explanation: `Matches your custom-added sensitivity filter.`
      });
    }
  }

  // 2. DIET TYPE MATCHING (Level: Medium / Orange)
  const diet = userProfile.dietType;

  if (diet === 'vegan') {
    const isExplicitVegan = labelsClean.some(l => l.includes('vegan') || l.includes('100% plant'));
    if (!isExplicitVegan) {
      const nonVeganFound: string[] = [];
      for (const item of NON_VEGAN_INGREDIENTS) {
        if (fullText.includes(item)) {
          nonVeganFound.push(item);
        }
      }
      if (nonVeganFound.length > 0) {
        warnings.push({
          id: 'warn_diet_vegan_conflict',
          level: 'medium',
          category: 'diet',
          title: 'Not Suitable for Vegan Diet',
          message: `Contains animal-derived ingredients: ${nonVeganFound.slice(0, 3).join(', ')}.`,
          matchedItem: nonVeganFound[0],
          explanation: `Incompatible with strict vegan lifestyle.`
        });
      } else if (product.productType === 'food') {
        warnings.push({
          id: 'warn_diet_vegan_unverified',
          level: 'low',
          category: 'diet',
          title: 'Unverified Vegan Status',
          message: 'No animal products detected directly, but lacks certified vegan labeling.',
          matchedItem: 'vegan certification'
        });
      }
    } else {
      safeHighlights.push('Certified Vegan product');
    }
  } else if (diet === 'vegetarian') {
    const nonVegFound = NON_VEGETARIAN_INGREDIENTS.filter(item => fullText.includes(item));
    if (nonVegFound.length > 0) {
      warnings.push({
        id: 'warn_diet_vegetarian_conflict',
        level: 'medium',
        category: 'diet',
        title: 'Not Suitable for Vegetarian Diet',
        message: `Contains meat or animal derivative: ${nonVegFound.slice(0, 3).join(', ')}.`,
        matchedItem: nonVegFound[0]
      });
    } else {
      safeHighlights.push('Vegetarian friendly formulation');
    }
  } else if (diet === 'halal') {
    const isHalalCertified = labelsClean.some(l => l.includes('halal'));
    const nonHalalFound = NON_HALAL_INGREDIENTS.filter(item => fullText.includes(item));
    if (nonHalalFound.length > 0) {
      warnings.push({
        id: 'warn_diet_halal_conflict',
        level: 'high',
        category: 'diet',
        title: 'Non-Halal Ingredient Detected',
        message: `Contains restricted ingredient: ${nonHalalFound.join(', ')}.`,
        matchedItem: nonHalalFound[0]
      });
    } else if (!isHalalCertified && product.productType === 'food') {
      safeHighlights.push('No obvious pork or alcohol ingredients found');
    }
  } else if (diet === 'kosher') {
    const isKosherCertified = labelsClean.some(l => l.includes('kosher') || l.includes('ou') || l.includes('parve') || l.includes('k'));
    const nonKosherFound = NON_KOSHER_INGREDIENTS.filter(item => fullText.includes(item));
    if (nonKosherFound.length > 0) {
      warnings.push({
        id: 'warn_diet_kosher_conflict',
        level: 'high',
        category: 'diet',
        title: 'Non-Kosher Ingredient Detected',
        message: `Contains restricted ingredient: ${nonKosherFound.join(', ')}.`,
        matchedItem: nonKosherFound[0]
      });
    } else if (isKosherCertified) {
      safeHighlights.push('Kosher certified');
    }
  } else if (diet === 'keto') {
    const carbs = product.nutrition?.carbohydrates ?? 0;
    const sugars = product.nutrition?.sugars ?? 0;
    if (carbs > 15 || sugars > 5) {
      warnings.push({
        id: 'warn_diet_keto',
        level: 'medium',
        category: 'nutrition',
        title: 'High Carb Content for Ketogenic Diet',
        message: `Contains ${carbs}g total carbs (${sugars}g sugar) per 100g, exceeding typical strict keto limits.`,
        matchedItem: `${carbs}g carbs`
      });
    } else if (product.nutrition) {
      safeHighlights.push('Low carb profile compatible with Keto');
    }
  } else if (diet === 'diabetic' || diet === 'low_sugar') {
    const sugars = product.nutrition?.sugars ?? 0;
    const hasHighFructose = fullText.includes('high fructose') || fullText.includes('glucose syrup') || fullText.includes('corn syrup');
    if (sugars > 12 || hasHighFructose) {
      warnings.push({
        id: 'warn_diabetic_sugar',
        level: 'medium',
        category: 'nutrition',
        title: 'Elevated Sugar / High-Glycemic Index',
        message: `Contains ${sugars > 0 ? sugars + 'g sugar/100g' : 'high-glycemic syrups'} which can trigger rapid blood glucose spikes.`,
        matchedItem: hasHighFructose ? 'High Fructose Corn Syrup' : `${sugars}g Sugar`
      });
    } else if (product.nutrition && sugars <= 4) {
      safeHighlights.push('Low sugar formulation (<4g/100g)');
    }
  } else if (diet === 'gluten_free') {
    const isGlutenFreeCert = labelsClean.some(l => l.includes('gluten-free') || l.includes('sans gluten'));
    const glutenSynonyms = ALLERGEN_SYNONYMS['gluten'];
    const hasGluten = glutenSynonyms.some(s => fullText.includes(s));
    if (hasGluten) {
      warnings.push({
        id: 'warn_gluten_free_diet',
        level: 'high',
        category: 'diet',
        title: 'Contains Gluten Grain',
        message: 'Product contains wheat, barley, rye or gluten ingredients.',
        matchedItem: 'Gluten'
      });
    } else if (isGlutenFreeCert) {
      safeHighlights.push('Certified Gluten-Free');
    }
  }

  // 3. SPECIAL CONDITIONS
  const conditions = userProfile.specialConditions || [];

  if (conditions.includes('pregnant') || conditions.includes('nursing')) {
    for (const pRisk of PREGNANCY_RISK_INGREDIENTS) {
      if (fullText.includes(pRisk.name)) {
        warnings.push({
          id: `warn_pregnancy_${pRisk.name}`,
          level: pRisk.risk as 'high' | 'medium' | 'low',
          category: 'condition',
          title: `Pregnancy Caution: ${pRisk.name.toUpperCase()}`,
          message: pRisk.reason,
          matchedItem: pRisk.name,
          explanation: `Obstetric & dermatological guidelines advise avoiding or restricting this substance during pregnancy/lactation.`
        });
      }
    }
  }

  if (conditions.includes('sensitive_skin') || conditions.includes('eczema')) {
    if (product.cosmetic?.hasFragrance || fullText.includes('fragrance') || fullText.includes('parfum')) {
      warnings.push({
        id: 'warn_sensitive_fragrance',
        level: 'medium',
        category: 'condition',
        title: 'Sensitizing Fragrance / Parfum Detected',
        message: 'Contains synthetic perfumes or fragrance allergens that frequently trigger eczema flare-ups and contact dermatitis.',
        matchedItem: 'Fragrance / Parfum'
      });
    }
    if (product.cosmetic?.hasAlcohol || fullText.includes('alcohol denat')) {
      warnings.push({
        id: 'warn_sensitive_alcohol',
        level: 'medium',
        category: 'condition',
        title: 'Drying Denatured Alcohol',
        message: 'Drying alcohols disrupt the skin lipid barrier in sensitive and eczema-prone skin.',
        matchedItem: 'Alcohol Denat'
      });
    }
  }

  if (conditions.includes('hypertension') || diet === 'low_sodium') {
    const sodium = product.nutrition?.sodium ?? (product.nutrition?.salt ? product.nutrition.salt * 400 : 0);
    if (sodium > 500) {
      warnings.push({
        id: 'warn_hypertension_sodium',
        level: 'medium',
        category: 'nutrition',
        title: 'High Sodium Warning for Hypertension',
        message: `Contains approx ${Math.round(sodium)}mg sodium per 100g (over 25% of daily recommended allowance).`,
        matchedItem: `${Math.round(sodium)}mg Sodium`
      });
    }
  }

  if (conditions.includes('acne_prone') && product.cosmetic) {
    if ((product.cosmetic.comedogenicRating || 0) >= 4) {
      warnings.push({
        id: 'warn_acne_comedogenic',
        level: 'low',
        category: 'condition',
        title: 'High Comedogenic Potential (Rating 4-5/5)',
        message: 'Contains ingredients with high probability of clogging pores for acne-prone skin types.',
        matchedItem: 'Pore-clogging lipids'
      });
    }
  }

  // 4. NOVA ULTRA-PROCESSED / NUTRITION GENERAL CHECK
  if (product.nutrition?.novaGroup === 4) {
    warnings.push({
      id: 'warn_nova_group_4',
      level: 'low',
      category: 'nutrition',
      title: 'NOVA Group 4: Ultra-Processed Food',
      message: 'Formulated with industrial ingredients, emulsifiers, and flavor enhancers.',
      matchedItem: 'Ultra-processed food'
    });
  }

  // 5. CROSS-REACTIVITY ALLERGY MATRIX CHECK
  const crossReactivityAlerts = detectCrossReactivities(
    userProfile.allergies,
    userProfile.customAllergens,
    product.ingredientsText,
    product.ingredientsList,
    product.allergens
  );

  for (const crossAlert of crossReactivityAlerts) {
    warnings.push({
      id: `warn_cross_allergy_${crossAlert.triggerItem.toLowerCase().replace(/[^a-z0-9]/g, '_')}`,
      level: crossAlert.clinicalCrossRisk === 'very_high' ? 'high' : 'medium',
      category: 'allergy',
      title: `Biological Cross-Reactivity (${crossAlert.riskPercentageRange}): ${crossAlert.triggerItem}`,
      message: `${crossAlert.syndromeName} - Due to sensitization to ${crossAlert.primaryAllergen}. Homologous ${crossAlert.scientificProteinFamily} protein structures may trigger cross-reactive immune responses.`,
      matchedItem: crossAlert.triggerItem,
      explanation: `${crossAlert.clinicalAdvice}. ${crossAlert.cookingEffect || ''}`
    });
  }

  // 6. COSMECEUTICAL ACTIVE & ROUTINE CONFLICT CHECK (For cosmetics)
  let skincareActiveCheck: RoutineAuditCheckResult | undefined = undefined;

  if (product.productType === 'cosmetic') {
    const activesFound = extractSkincareActives(product.ingredientsText, product.ingredientsList);
    if (activesFound.length > 0) {
      const currentRoutine = db.getRoutine();
      skincareActiveCheck = analyzeSkincareRoutineConflicts(currentRoutine, activesFound);

      // If severe routine conflicts exist with current shelf, generate warnings
      for (const conflict of skincareActiveCheck.conflicts) {
        warnings.push({
          id: `warn_skincare_conflict_${conflict.ruleTitle.toLowerCase().replace(/[^a-z0-9]/g, '_')}`,
          level: conflict.severity === 'high' ? 'medium' : 'low',
          category: 'condition',
          title: `Active Skincare Conflict: ${conflict.ruleTitle}`,
          message: `${conflict.riskDescription} (${conflict.activeA} vs ${conflict.activeB})`,
          matchedItem: conflict.activeA,
          explanation: `${conflict.solutionRecommendation} Timing Guide: ${conflict.timingGuide}`
        });
      }

      for (const syn of skincareActiveCheck.synergies) {
        safeHighlights.push(`Synergistic Pairing: ${syn.ruleTitle}`);
      }
    }
  }

  // Fetch PubMed research evidence for high and medium severity flags
  for (const warning of warnings) {
    if (warning.level === 'high' || warning.level === 'medium') {
      try {
        const queryTerm = warning.matchedItem || warning.title;
        warning.research = await getPubMedResearch(queryTerm, warning.category);
      } catch (err) {
        console.warn('Could not fetch PubMed research for warning:', err);
      }
    }
  }

  // Calculate Personal Fit Score (0 - 100)
  let score = 100;
  const highCount = warnings.filter(w => w.level === 'high').length;
  const medCount = warnings.filter(w => w.level === 'medium').length;
  const lowCount = warnings.filter(w => w.level === 'low').length;

  score -= highCount * 45;
  score -= medCount * 20;
  score -= lowCount * 5;
  score = Math.max(0, Math.min(100, score));

  // Determine overall status
  let status: 'safe' | 'caution' | 'warning' | 'danger' = 'safe';
  let summary = 'Excellent match for your personal profile with zero flagged allergens or restrictions.';

  if (highCount > 0) {
    status = 'danger';
    summary = `Direct Conflict Detected: Contains ${highCount} high-risk allergen(s) or contraindication(s) matching your profile.`;
  } else if (medCount > 0) {
    status = 'warning';
    summary = `Caution Advised: ${medCount} dietary or health condition restriction(s) flagged.`;
  } else if (lowCount > 0) {
    status = 'caution';
    summary = `Minor Notes: Formulated safely, but contains ${lowCount} item(s) you may want to note.`;
  }

  if (safeHighlights.length === 0 && status === 'safe') {
    safeHighlights.push('No declared allergens matching your profile');
    safeHighlights.push(`Compatible with ${userProfile.dietType} diet`);
  }

  return {
    status,
    score,
    summary,
    warnings,
    safeHighlights,
    crossReactivityAlerts,
    skincareActiveCheck
  };
}

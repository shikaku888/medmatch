import { SkincareActiveItem, SkincareConflictWarning, UserRoutineProduct, RoutineAuditCheckResult } from '../../src/types';

// Dictionary of skincare actives keywords and their categories
const ACTIVE_KEYWORDS: { pattern: RegExp; name: string; category: SkincareActiveItem['category']; role: string }[] = [
  // Retinoids
  { pattern: /\b(retinol)\b/i, name: 'Retinol', category: 'retinoid', role: 'Cellular renewal, collagen synthesis stimulation' },
  { pattern: /\b(retinal|retinaldehyde)\b/i, name: 'Retinal', category: 'retinoid', role: 'Next-gen retinoid, faster conversion than Retinol' },
  { pattern: /\b(tretinoin|adapalene|tazarotene)\b/i, name: 'Prescription Retinoid', category: 'retinoid', role: 'Medical-grade retinoid for acne and deep anti-aging' },
  { pattern: /\b(retinyl palmitate)\b/i, name: 'Retinyl Palmitate', category: 'retinoid', role: 'Gentle retinoid ester derivative' },

  // Direct Exfoliating Acids
  { pattern: /\b(salicylic acid|betaine salicylate)\b/i, name: 'Salicylic Acid (BHA)', category: 'bha', role: 'Lipid-soluble, pore-clearing, anti-inflammatory' },
  { pattern: /\b(glycolic acid)\b/i, name: 'Glycolic Acid (AHA)', category: 'aha', role: 'Small-molecule AHA, epidermal resurfacing, brightening' },
  { pattern: /\b(lactic acid)\b/i, name: 'Lactic Acid (AHA)', category: 'aha', role: 'Gentle AHA, moisturizing and skin smoothing' },
  { pattern: /\b(mandelic acid)\b/i, name: 'Mandelic Acid (AHA)', category: 'aha', role: 'Larger-molecule AHA for sensitive skin' },
  { pattern: /\b(gluconolactone|lactobionic acid)\b/i, name: 'PHA (Gluconolactone)', category: 'pha', role: 'Next-gen polyhydroxy exfoliant, antioxidant, barrier-safe' },

  // Vitamin C
  { pattern: /\b(ascorbic acid|l-ascorbic acid)\b/i, name: 'L-Ascorbic Acid (Pure Vitamin C)', category: 'vitamin_c_pure', role: 'Potent antioxidant, hyperpigmentation fading, collagen boost (pH < 3.5)' },
  { pattern: /\b(ethyl ascorbic acid|ascorbyl glucoside|sodium ascorbyl phosphate|magnesium ascorbyl phosphate|tetrahexyldecyl ascorbate)\b/i, name: 'Vitamin C Derivative (EAA/SAP)', category: 'vitamin_c_derivative', role: 'Stable Vitamin C derivative, low irritation' },

  // Vitamin B3 (Niacinamide)
  { pattern: /\b(niacinamide|nicotinamide)\b/i, name: 'Niacinamide (Vitamin B3)', category: 'niacinamide', role: 'Barrier ceramide synthesis, sebum regulation, tone evening' },

  // Benzoyl Peroxide
  { pattern: /\b(benzoyl peroxide)\b/i, name: 'Benzoyl Peroxide (BPO)', category: 'benzoyl_peroxide', role: 'Antibacterial against C. acnes, inflammatory acne treatment' },

  // Copper Peptides
  { pattern: /\b(copper tripeptide-1|ghk-cu|copper peptide)\b/i, name: 'Copper Tripeptide-1 (GHK-Cu)', category: 'copper_peptide', role: 'Tissue remodeling, extracellular matrix restoration' },

  // Brightening & Specialty
  { pattern: /\b(hydroquinone)\b/i, name: 'Hydroquinone', category: 'hydroquinone', role: 'Tyrosinase inhibitor for severe hyperpigmentation/melasma' },
  { pattern: /\b(azelaic acid|potassium azeloyl diglycinate)\b/i, name: 'Azelaic Acid', category: 'azelaic_acid', role: 'Anti-inflammatory, redness and Rosacea relief, blemish reduction' },

  // Barrier & Soothing
  { pattern: /\b(ceramide np|ceramide ap|ceramide eop|ceramide|phytosphingosine)\b/i, name: 'Ceramides Complex', category: 'barrier_ceramide', role: 'Epidermal lipid barrier repair, moisture locking, anti-TEWL' },
  { pattern: /\b(sodium hyaluronate|hyaluronic acid|hydrolyzed hyaluronic acid)\b/i, name: 'Hyaluronic Acid (HA)', category: 'hyaluronic_acid', role: 'Multi-depth humectant hydration, skin plumping' },

  // Sunscreen Filters
  { pattern: /\b(zinc oxide|titanium dioxide)\b/i, name: 'Mineral UV Filter (Zinc/Titanium)', category: 'physical_sunscreen', role: 'Broad spectrum inorganic physical UV reflective filter' },
  { pattern: /\b(avobenzone|homosalate|octisalate|octocrylene|tinosorb|uvinul)\b/i, name: 'Chemical UV Filters', category: 'chemical_sunscreen', role: 'Organic chemical UV absorbing filter' }
];

export function extractSkincareActives(ingredientsText: string, ingredientsList: string[] = []): SkincareActiveItem[] {
  const full = (ingredientsText + ' ' + ingredientsList.join(' ')).toLowerCase();
  const detected: SkincareActiveItem[] = [];
  const addedNames = new Set<string>();

  for (const item of ACTIVE_KEYWORDS) {
    if (item.pattern.test(full) && !addedNames.has(item.name)) {
      addedNames.add(item.name);
      detected.push({
        name: item.name,
        category: item.category,
        role: item.role
      });
    }
  }

  return detected;
}

// Skincare Collision & Synergy Knowledge Base
const CONFLICT_MATRIX: {
  pair: [SkincareActiveItem['category'], SkincareActiveItem['category']];
  severity: 'high' | 'medium' | 'caution' | 'synergy';
  ruleTitle: string;
  riskDescription: string;
  solutionRecommendation: string;
  timingGuide: string;
  phClash?: boolean;
  barrierDamageRisk?: boolean;
}[] = [
  {
    pair: ['retinoid', 'bha'],
    severity: 'high',
    ruleTitle: 'Exfoliation Collision: Retinoid + BHA (Salicylic Acid)',
    riskDescription: 'Both actives accelerate cellular turnover and penetration. Using both in the same evening routine risks severe barrier compromise, erythema, peeling, and trans-epidermal water loss.',
    solutionRecommendation: 'Adopt Skin Cycling or alternate nights: Use BHA on night 1, Retinoid on night 2, followed by recovery nights.',
    timingGuide: 'Separate: BHA in AM (with SPF50) or on alternating evenings from Retinoids.',
    barrierDamageRisk: true
  },
  {
    pair: ['retinoid', 'aha'],
    severity: 'high',
    ruleTitle: 'Potent Acid Clash: Retinoid + AHA (Glycolic/Lactic Acid)',
    riskDescription: 'AHA loosens stratum corneum desmosomes while Retinoid accelerates basal layer cell division, compounding irritation and risk of chemical burn.',
    solutionRecommendation: 'Alternate on different nights. Always apply barrier-repair moisturizers with Ceramides.',
    timingGuide: 'Always alternate nights; never layer directly on top of each other.',
    barrierDamageRisk: true
  },
  {
    pair: ['retinoid', 'benzoyl_peroxide'],
    severity: 'high',
    ruleTitle: 'Oxidative Deactivation: Retinoid + Benzoyl Peroxide (BPO)',
    riskDescription: 'Benzoyl Peroxide is a strong oxidizing agent that can degrade and inactivate standard Retinol molecules while causing extreme dryness.',
    solutionRecommendation: 'Use Benzoyl Peroxide as a spot treatment in AM and apply Retinoid across face in PM.',
    timingGuide: 'BPO: Morning | Retinoid: Evening.'
  },
  {
    pair: ['vitamin_c_pure', 'aha'],
    severity: 'medium',
    ruleTitle: 'Low pH Overload: L-Ascorbic Acid + AHA Direct Acids',
    riskDescription: 'Both L-Ascorbic Acid and AHA require very low pH (<3.5) to penetrate. Layering together induces acute pH shock, stinging, and redness.',
    solutionRecommendation: 'Move Pure Vitamin C to your morning routine to boost antioxidant UV defense, and keep AHA for night routines.',
    timingGuide: 'Vitamin C: Morning (with SPF50+) | AHA: Evening.',
    phClash: true
  },
  {
    pair: ['vitamin_c_pure', 'bha'],
    severity: 'medium',
    ruleTitle: 'Acid Overload: L-Ascorbic Acid + BHA (Salicylic Acid)',
    riskDescription: 'Combining multiple strong low-pH acids simultaneously can strip the natural acid mantle and elevate UV sensitivity.',
    solutionRecommendation: 'Use Vitamin C in the morning and BHA at night, or alternate days.',
    timingGuide: 'Vitamin C: Morning | BHA: Evening.',
    phClash: true
  },
  {
    pair: ['copper_peptide', 'vitamin_c_pure'],
    severity: 'high',
    ruleTitle: 'Peptide Breakdown: Copper Peptides (GHK-Cu) + Pure Vitamin C',
    riskDescription: 'Copper ions (Cu2+) oxidize ascorbic acid molecules, neutralizing Vitamin C antioxidant efficacy and cleaving peptide bonds.',
    solutionRecommendation: 'Never mix in the same routine step. Use Vitamin C in the morning and Copper Peptide in the evening.',
    timingGuide: 'Vitamin C: Morning | Copper Peptide: Evening.'
  },
  {
    pair: ['copper_peptide', 'aha'],
    severity: 'medium',
    ruleTitle: 'Peptide Bond Cleavage: Copper Peptide + AHA/BHA',
    riskDescription: 'Strong acidic environments from AHA/BHA denature copper peptide amino acid chains, diminishing collagen stimulation.',
    solutionRecommendation: 'Use exfoliating acids on days when Copper Peptides are not applied.',
    timingGuide: 'Alternate days or apply in opposite morning/evening routines.'
  },
  {
    pair: ['benzoyl_peroxide', 'hydroquinone'],
    severity: 'caution',
    ruleTitle: 'Temporary Skin Staining Risk: BPO + Hydroquinone',
    riskDescription: 'Oxidative reactions between BPO and Hydroquinone can create temporary dark surface staining on the skin.',
    solutionRecommendation: 'Do not layer directly over the same surface area.',
    timingGuide: 'Separate into different times of day or switch to Azelaic Acid for brightening.'
  },

  // SYNERGIES
  {
    pair: ['niacinamide', 'retinoid'],
    severity: 'synergy',
    ruleTitle: 'Golden Synergy: Niacinamide + Retinoid',
    riskDescription: 'Highly compatible and protective. Niacinamide stimulates natural ceramide synthesis, soothing irritation and reducing retinoid-induced redness by up to 60%.',
    solutionRecommendation: 'Apply Niacinamide serum first to cushion the barrier, then follow with Retinoid or barrier cream.',
    timingGuide: 'Safe and beneficial to combine in Evening routines.'
  },
  {
    pair: ['vitamin_c_pure', 'physical_sunscreen'],
    severity: 'synergy',
    ruleTitle: 'Photo-Protection Synergy: Vitamin C + Sunscreen',
    riskDescription: 'Vitamin C neutralizes free radicals generated by UV rays that penetrate sunscreen filters, doubling defense against photo-aging and dark spots.',
    solutionRecommendation: 'Apply Vitamin C serum every morning before sunscreen application.',
    timingGuide: 'Standard Morning routine best practice.'
  },
  {
    pair: ['barrier_ceramide', 'retinoid'],
    severity: 'synergy',
    ruleTitle: 'Barrier Cushion Synergy: Ceramides + Retinoid',
    riskDescription: 'Ceramides reinforce the lipid barrier vulnerable during retinization, preventing trans-epidermal water loss (TEWL).',
    solutionRecommendation: 'Use the Sandwich Technique (Moisturizer -> Retinoid -> Moisturizer) for sensitive skin.',
    timingGuide: 'Evening routine cushion.'
  },
  {
    pair: ['hyaluronic_acid', 'aha'],
    severity: 'synergy',
    ruleTitle: 'Multi-Depth Hydration: Hyaluronic Acid + AHA/BHA',
    riskDescription: 'HA floods newly exfoliated cellular layers with moisture, ensuring supple plumpness without post-acid dehydration.',
    solutionRecommendation: 'Apply HA serum 5-10 minutes after acid exfoliation.',
    timingGuide: 'Safe for both AM & PM.'
  }
];

export function analyzeSkincareRoutineConflicts(
  routineProducts: UserRoutineProduct[],
  newProductActives: SkincareActiveItem[] = []
): RoutineAuditCheckResult {
  const allActives: { active: SkincareActiveItem; sourceProduct: string; time: 'am' | 'pm' | 'both' }[] = [];

  // 1. Gather all actives from existing routine
  routineProducts.forEach(prod => {
    prod.activeIngredients.forEach(ingName => {
      const detected = extractSkincareActives(ingName);
      if (detected.length > 0) {
        detected.forEach(d => allActives.push({ active: d, sourceProduct: prod.name, time: prod.timeOfDay }));
      } else {
        // Fallback generic active item
        allActives.push({
          active: { name: ingName, category: 'aha', role: 'Active ingredient' },
          sourceProduct: prod.name,
          time: prod.timeOfDay
        });
      }
    });
  });

  // 2. Add new product actives if inspecting
  newProductActives.forEach(act => {
    allActives.push({
      active: act,
      sourceProduct: 'Scanned Product',
      time: 'both'
    });
  });

  const conflicts: SkincareConflictWarning[] = [];
  const synergies: SkincareConflictWarning[] = [];

  // 3. Test every pair
  for (let i = 0; i < allActives.length; i++) {
    for (let j = i + 1; j < allActives.length; j++) {
      const itemA = allActives[i];
      const itemB = allActives[j];

      for (const rule of CONFLICT_MATRIX) {
        const matchesForward = rule.pair[0] === itemA.active.category && rule.pair[1] === itemB.active.category;
        const matchesReverse = rule.pair[1] === itemA.active.category && rule.pair[0] === itemB.active.category;

        if (matchesForward || matchesReverse) {
          const warningObj: SkincareConflictWarning = {
            activeA: `${itemA.active.name} (${itemA.sourceProduct})`,
            activeB: `${itemB.active.name} (${itemB.sourceProduct})`,
            severity: rule.severity,
            ruleTitle: rule.ruleTitle,
            riskDescription: rule.riskDescription,
            solutionRecommendation: rule.solutionRecommendation,
            timingGuide: rule.timingGuide,
            phClash: rule.phClash,
            barrierDamageRisk: rule.barrierDamageRisk
          };

          if (rule.severity === 'synergy') {
            if (!synergies.some(s => s.ruleTitle === rule.ruleTitle)) {
              synergies.push(warningObj);
            }
          } else {
            if (!conflicts.some(c => c.ruleTitle === rule.ruleTitle)) {
              conflicts.push(warningObj);
            }
          }
        }
      }
    }
  }

  // Calculate routine score
  let safetyScore = 100;
  const highConflicts = conflicts.filter(c => c.severity === 'high').length;
  const medConflicts = conflicts.filter(c => c.severity === 'medium' || c.severity === 'caution').length;
  safetyScore -= highConflicts * 30;
  safetyScore -= medConflicts * 15;
  safetyScore = Math.max(20, Math.min(100, safetyScore));

  const skinCyclingGuide = [
    {
      dayOrTime: 'Night 1 (Exfoliation)',
      instructions: 'Deep cleanse -> AHA/BHA Exfoliant -> Barrier Ceramide Cream.',
      productsUsed: ['BHA / AHA Exfoliant', 'Barrier Cream']
    },
    {
      dayOrTime: 'Night 2 (Targeted Retinoid)',
      instructions: 'Gentle cleanse -> Niacinamide Serum -> Retinol / Retinal -> Moisture lock.',
      productsUsed: ['Retinol / Retinal', 'Niacinamide', 'Moisturizer']
    },
    {
      dayOrTime: 'Nights 3 & 4 (Barrier Recovery)',
      instructions: 'Pause all direct acids & retinoids. Apply multi-depth HA + Peptides + Rich Ceramide cream.',
      productsUsed: ['Hyaluronic Acid', 'Peptide / Panthenol', 'Ceramide Cream']
    },
    {
      dayOrTime: 'Every Morning',
      instructions: 'Cleanse -> Vitamin C / Niacinamide Serum -> Broad Spectrum Sunscreen SPF 50+.',
      productsUsed: ['Vitamin C / Niacinamide', 'Sunscreen SPF50+']
    }
  ];

  return {
    conflictCount: conflicts.length,
    synergyCount: synergies.length,
    overallRoutineSafetyScore: safetyScore,
    conflicts,
    synergies,
    activeIngredientsFound: newProductActives,
    skinCyclingGuide
  };
}


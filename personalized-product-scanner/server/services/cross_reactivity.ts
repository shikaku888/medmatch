import { CrossReactivityAlert, CrossReactivityRule } from '../../src/types';

export const CROSS_REACTIVITY_RULES: CrossReactivityRule[] = [
  {
    id: 'birch_pollen_oas',
    sourceKey: 'birch_pollen',
    sourceName: 'Birch Tree Pollen (Betula / Bet v 1)',
    syndromeName: 'Oral Allergy Syndrome / Pollen Food Allergy (OAS / PFAS)',
    proteinFamily: 'Bet v 1 Homologs (PR-10 Pathogenesis-Related Protein)',
    mechanism: 'Bet v 1 protein in birch pollen shares high 3D structural homology (>70% identity) with defense proteins in Rosaceae and Apiaceae families.',
    symptoms: ['Oropharyngeal itching and tingling', 'Mild lip and tongue swelling', 'Prickling sensation when chewing raw fruit'],
    cookingEffect: 'PR-10 proteins are heat-labile. Cooking, pasteurization, canning, or microwave heating denatures the protein epitope, making it safe for most sensitized individuals.',
    crossItems: [
      { name: 'Apple (Mal d 1)', riskPercent: '75% - 90%', riskLevel: 'very_high', notes: 'Most common cross-reactive fruit in birch pollen allergic patients' },
      { name: 'Hazelnut (Cor a 1.04)', riskPercent: '60% - 80%', riskLevel: 'very_high', notes: 'Can cause mild oral symptoms or severe reactions if consumed in large amounts' },
      { name: 'Peach & Plum (Pru p 1)', riskPercent: '50% - 70%', riskLevel: 'high', notes: 'Peel contains higher protein concentrations than pulp' },
      { name: 'Pear & Cherry', riskPercent: '40% - 60%', riskLevel: 'medium', notes: 'Reactivity typically reduced when peeled or baked' },
      { name: 'Carrot & Celery (Dau c 1 / Api g 1)', riskPercent: '40% - 60%', riskLevel: 'medium', notes: 'Celery also contains heat-stable lipid transfer proteins' },
      { name: 'Kiwi & Soy (Gly m 4)', riskPercent: '30% - 50%', riskLevel: 'moderate', notes: 'Unheated soy milk can trigger systemic allergic reactions' },
      { name: 'Almond (Pru du 1)', riskPercent: '30% - 45%', riskLevel: 'moderate', notes: 'Bet v 1 mediated mild oral cross-reactivity' }
    ]
  },
  {
    id: 'latex_fruit_syndrome',
    sourceKey: 'latex',
    sourceName: 'Natural Rubber Latex (Hevea brasiliensis)',
    syndromeName: 'Latex-Fruit Allergy Syndrome',
    proteinFamily: 'Hevein-like Class I Chitinases (Hev b 6.02) & Beta-1,3-Glucanases',
    mechanism: 'Antigenic epitopes in plant defense endochitinases show high cross-reactivity with Hev b antigens from natural rubber latex.',
    symptoms: ['Acute urticaria / hives', 'Allergic rhinitis and conjunctivitis', 'Bronchospasm or dyspnea after ingestion'],
    cookingEffect: 'Class I chitinase proteins possess moderate heat resistance. Standard cooking may not completely eliminate the risk of reaction.',
    crossItems: [
      { name: 'Banana (Mus a 2)', riskPercent: '70% - 85%', riskLevel: 'very_high', notes: 'Highest antigenic concordance in the latex-fruit syndrome' },
      { name: 'Avocado (Pers a 1)', riskPercent: '60% - 80%', riskLevel: 'very_high', notes: 'Frequently triggers reactions even in small amounts (guacamole, sauces)' },
      { name: 'Chestnut (Cas s 1)', riskPercent: '50% - 70%', riskLevel: 'high', notes: 'May trigger systemic allergic symptoms' },
      { name: 'Kiwi (Act d 1 / Act d 2)', riskPercent: '40% - 60%', riskLevel: 'high', notes: 'Mucosal irritation and perioral swelling' },
      { name: 'Papaya & Fig', riskPercent: '30% - 50%', riskLevel: 'medium', notes: 'Contains papain and related cross-reactive endoproteases' },
      { name: 'Tomato & Passion Fruit', riskPercent: '25% - 40%', riskLevel: 'moderate', notes: 'Mild cross-reactive IgE antibody binding' }
    ]
  },
  {
    id: 'cmpa_mammalian_milk',
    sourceKey: 'milk',
    sourceName: "Cow's Milk Protein Allergy (CMPA)",
    syndromeName: 'Mammalian Milk Cross-Reactivity',
    proteinFamily: 'Alpha-S1 Casein, Beta-Casein & Beta-Lactoglobulin',
    mechanism: 'Over 90% of cow milk protein allergic patients cross-react with goat, sheep, and buffalo milk due to >85% amino acid sequence homology.',
    symptoms: ['Eczema and atopic dermatitis flares', 'Reflux, abdominal colic, diarrhea', 'Wheezing and respiratory distress'],
    cookingEffect: 'Casein is heat-stable and survives boiling. Beta-lactoglobulin reactivity is only slightly reduced when baked at >180°C.',
    crossItems: [
      { name: 'Goat Milk', riskPercent: '90% - 95%', riskLevel: 'very_high', notes: 'Do NOT substitute cow milk with goat milk in CMPA patients' },
      { name: 'Sheep Milk & Pecorino Cheese', riskPercent: '90% - 95%', riskLevel: 'very_high', notes: 'Casein structure is almost completely identical' },
      { name: 'Buffalo Milk & Mozzarella di Bufala', riskPercent: '80% - 90%', riskLevel: 'very_high', notes: 'High potential for severe allergic cross-reactivity' },
      { name: 'Beef meat (Bovine Serum Albumin - BSA)', riskPercent: '10% - 20%', riskLevel: 'moderate', notes: 'Occurs in a minority of milk-allergic patients sensitized to BSA' }
    ]
  },
  {
    id: 'peanut_legumes_matrix',
    sourceKey: 'peanut',
    sourceName: 'Peanut (Arachis hypogaea)',
    syndromeName: 'Legume & Botanical Seed Cross-Reactivity Matrix',
    proteinFamily: 'Vicilin (7S globulin), Legumin (11S) & 2S Albumin',
    mechanism: 'Peanuts are botanically legumes (Fabaceae). Seed storage proteins (2S albumin, 7S globulin) share homologous epitopes with other legumes and seeds.',
    symptoms: ['Angioedema, dyspnea', 'Systemic urticaria and flushing', 'Acute gastrointestinal distress'],
    cookingEffect: 'Peanut allergens (Ara h 1, 2, 6) are extremely heat and gastric acid resistant. High-temperature roasting actually increases immunogenicity.',
    crossItems: [
      { name: 'Lupin / Lupine Flour', riskPercent: '30% - 50%', riskLevel: 'high', notes: 'Common in European baked goods, specialty pastas, and waffles' },
      { name: 'Fenugreek (Trigonella foenum-graecum)', riskPercent: '25% - 45%', riskLevel: 'medium', notes: 'Found in curry powders, Indian seasonings, lactation herbal teas' },
      { name: 'Soybean', riskPercent: '10% - 25%', riskLevel: 'moderate', notes: 'Most patients tolerate highly refined soybean oil' },
      { name: 'Green Pea & Lentil', riskPercent: '15% - 30%', riskLevel: 'moderate', notes: 'Commonly presents as mild gastrointestinal symptoms' }
    ]
  },
  {
    id: 'tree_nut_cross_pairs',
    sourceKey: 'tree_nut',
    sourceName: 'Tree Nuts (Cashew, Walnut, Almond, Pistachio, Hazelnut)',
    syndromeName: 'Botanical Tree Nut Pair Cross-Reactivity',
    proteinFamily: '2S Albumins & 11S Globulins (Anacardiaceae / Juglandaceae)',
    mechanism: 'Cashew and pistachio belong to Anacardiaceae with ~90% clinical cross-reactivity. Walnut and pecan belong to Juglandaceae with ~90% cross-reactivity.',
    symptoms: ['Severe anaphylaxis', 'Laryngeal edema / airway constriction', 'Facial and periorbital edema'],
    cookingEffect: 'Tree nut 2S albumins are exceptionally heat-stable and resist standard household cooking temperatures.',
    crossItems: [
      { name: 'Cashew ↔ Pistachio', riskPercent: '85% - 95%', riskLevel: 'very_high', notes: 'Cashew-allergic individuals almost universally react to pistachios' },
      { name: 'Walnut ↔ Pecan', riskPercent: '85% - 95%', riskLevel: 'very_high', notes: 'Jug r 1 and Cpa l 1 proteins share virtually identical structures' },
      { name: 'Almond ↔ Hazelnut', riskPercent: '30% - 50%', riskLevel: 'medium', notes: 'Moderate botanical cross-reactivity within tree nut families' }
    ]
  },
  {
    id: 'crustacean_shellfish_matrix',
    sourceKey: 'shellfish',
    sourceName: 'Crustaceans & Shellfish (Shrimp, Crab, Lobster)',
    syndromeName: 'Invertebrate Tropomyosin Cross-Reactivity Syndrome',
    proteinFamily: 'Muscle Protein Tropomyosin (Cra c 1, Pan b 1, Pen a 1)',
    mechanism: 'Tropomyosin is an ultra-conserved muscle contractile protein across arthropods and mollusks. Shrimp/crab allergic individuals frequently cross-react with squid, snails, and oysters.',
    symptoms: ['Laryngeal constriction', 'Cutaneous erythema and hypotension', 'Nausea, abdominal cramping, and vomiting'],
    cookingEffect: 'Tropomyosin is one of the most heat- and protease-stable food allergens known; boiling or grilling will not inactivate it.',
    crossItems: [
      { name: 'Shrimp ↔ Crab ↔ Lobster', riskPercent: '80% - 95%', riskLevel: 'very_high', notes: 'Near universal cross-reactivity across crustacean species' },
      { name: 'Squid & Octopus (Cephalopods)', riskPercent: '50% - 75%', riskLevel: 'high', notes: 'Mollusks share homologous tropomyosin peptide chains' },
      { name: 'Clams, Mussels, Snails, Oysters (Bivalves/Gastropods)', riskPercent: '40% - 65%', riskLevel: 'high', notes: 'Marine mollusk group with high tropomyosin homology' }
    ]
  }
];

export function detectCrossReactivities(
  userAllergies: string[],
  customAllergens: string[] = [],
  ingredientsText: string,
  ingredientsList: string[] = [],
  declaredAllergens: string[] = []
): CrossReactivityAlert[] {
  const alerts: CrossReactivityAlert[] = [];
  const fullText = (ingredientsText + ' ' + ingredientsList.join(' ') + ' ' + declaredAllergens.join(' ')).toLowerCase();
  
  const allUserAllergies = [...userAllergies, ...customAllergens.map(c => c.toLowerCase())];

  for (const rule of CROSS_REACTIVITY_RULES) {
    const hasSourceAllergy = allUserAllergies.some(a => 
      a === rule.sourceKey || 
      a.includes(rule.sourceKey) || 
      rule.sourceName.toLowerCase().includes(a)
    );

    if (hasSourceAllergy) {
      for (const item of rule.crossItems) {
        const itemKeywords = item.name.toLowerCase().split(/[\s\(\)\/↔]+/).filter(w => w.length > 2);
        
        const isPresentInProduct = itemKeywords.some(kw => {
          if (kw === 'and' || kw === 'notes' || kw === 'milk' || kw === 'seed') return false;
          const regex = new RegExp(`\\b${kw}\\b`, 'i');
          return regex.test(fullText);
        });

        if (isPresentInProduct) {
          alerts.push({
            primaryAllergen: rule.sourceName,
            triggerItem: item.name,
            syndromeName: rule.syndromeName,
            clinicalCrossRisk: item.riskLevel,
            riskPercentageRange: item.riskPercent,
            mechanismExplanation: rule.mechanism,
            scientificProteinFamily: rule.proteinFamily,
            clinicalAdvice: item.notes,
            cookingEffect: rule.cookingEffect
          });
        }
      }
    }
  }

  return alerts;
}

export function getAllCrossReactivityRules(): CrossReactivityRule[] {
  return CROSS_REACTIVITY_RULES;
}


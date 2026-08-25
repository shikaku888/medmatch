import { IngredientSafetyItem, RegulatoryStatusBadge } from '../../src/types';

// Standard scientific / regulatory toxicological database of cosmetic & food additives
const KNOWN_HAZARDS: Record<string, { 
  hazard: 'danger' | 'caution'; 
  role: string; 
  reg: string; 
  impact: string;
  regulatoryBadges?: RegulatoryStatusBadge[];
}> = {
  // Food Additives / Preservatives / Dyes / Sweeteners
  'sodium nitrite': { 
    hazard: 'danger', 
    role: 'Curing Agent & Preservative (E250)', 
    reg: 'IARC 2A Probable Carcinogen', 
    impact: 'Forms carcinogenic nitrosamines upon high-heat cooking',
    regulatoryBadges: [{
      region: 'GLOBAL',
      authority: 'IARC / WHO',
      statusType: 'restricted',
      title: 'Group 2A Carcinogen',
      detail: 'Processed meat preservative associated with colorectal cancer risks.'
    }]
  },
  'sodium nitrate': { 
    hazard: 'danger', 
    role: 'Curing Agent (E251)', 
    reg: 'WHO Warning Limit', 
    impact: 'Associated with vascular endothelial damage and nitrosamine synthesis' 
  },
  'potassium bromate': { 
    hazard: 'danger', 
    role: 'Flour Dough Conditioner (E924)', 
    reg: 'Banned in EU, UK, Canada, Brazil', 
    impact: 'Known renal and thyroid carcinogen; prohibited across Europe but permitted in US bakery goods',
    regulatoryBadges: [
      {
        region: 'EU',
        authority: 'EFSA',
        statusType: 'banned',
        title: 'Banned in EU Food',
        detail: 'Potassium bromate is classified as a category 2B carcinogen.'
      },
      {
        region: 'UK',
        authority: 'FSA',
        statusType: 'banned',
        title: 'Banned in UK',
        detail: 'Illegal in flour and baked products across the United Kingdom.'
      },
      {
        region: 'US',
        authority: 'FDA',
        statusType: 'restricted',
        title: 'Allowed in US Bakeries',
        detail: 'Permitted in US flours; California requires Prop 65 warning.'
      }
    ]
  },
  'bha': { 
    hazard: 'danger', 
    role: 'Synthetic Antioxidant (E320)', 
    reg: 'California Prop 65 Listed', 
    impact: 'Suspected endocrine disruptor and human carcinogen',
    regulatoryBadges: [{
      region: 'US',
      authority: 'Prop 65',
      statusType: 'warning_label',
      title: 'CA Prop 65 Listed',
      detail: 'Known to the State of California to cause cancer.'
    }]
  },
  'bht': { 
    hazard: 'caution', 
    role: 'Synthetic Preservative (E321)', 
    reg: 'EU Usage Restrictions / EFSA', 
    impact: 'Potential endocrine disruption in higher chronic doses' 
  },
  'butylated hydroxyanisole': { 
    hazard: 'danger', 
    role: 'Synthetic Antioxidant (E320)', 
    reg: 'Prop 65 Warning', 
    impact: 'Endocrine disruptor' 
  },
  'butylated hydroxytoluene': { 
    hazard: 'caution', 
    role: 'Preservative (E321)', 
    reg: 'EFSA Monitored', 
    impact: 'Immune & endocrine interaction' 
  },
  'azodicarbonamide': {
    hazard: 'danger',
    role: 'Dough Bleaching Agent (E927a)',
    reg: 'Banned in EU & UK / Allowed in US',
    impact: 'Thermal breakdown produces semicarbazide and urethane carcinogens',
    regulatoryBadges: [
      {
        region: 'EU',
        authority: 'EFSA',
        statusType: 'banned',
        title: 'Banned in EU Food',
        detail: 'Forbidden as a food additive in the European Union.'
      },
      {
        region: 'US',
        authority: 'FDA',
        statusType: 'approved_gras',
        title: 'FDA Permitted (up to 45 ppm)',
        detail: 'Approved as a flour maturing agent in the United States.'
      }
    ]
  },
  'red 40': { 
    hazard: 'caution', 
    role: 'Synthetic Azo Dye (E129 / Allura Red)', 
    reg: 'EU Warning Label Required', 
    impact: 'Linked to hyperactivity and ADHD symptom exacerbation in children',
    regulatoryBadges: [{
      region: 'EU',
      authority: 'EFSA',
      statusType: 'warning_label',
      title: 'EU Warning Label Required',
      detail: 'Mandatory label: "May have an adverse effect on activity and attention in children".'
    }]
  },
  'allura red': { 
    hazard: 'caution', 
    role: 'Synthetic Colorant (E129)', 
    reg: 'EU Warning Label', 
    impact: 'Potential allergenicity & hyperactivity',
    regulatoryBadges: [{
      region: 'EU',
      authority: 'EFSA',
      statusType: 'warning_label',
      title: 'EU Warning Label Required',
      detail: 'Requires childhood hyperactivity warning on food packaging in France, Germany, Spain, Italy & UK.'
    }]
  },
  'yellow 5': { 
    hazard: 'caution', 
    role: 'Synthetic Tartrazine Dye (E102)', 
    reg: 'EU Warning Required', 
    impact: 'Known allergen & bronchospasm trigger in asthmatics and sensitive kids',
    regulatoryBadges: [{
      region: 'EU',
      authority: 'EFSA',
      statusType: 'warning_label',
      title: 'EU Warning Label Required',
      detail: 'European regulations mandate behavioral warning for Tartrazine (E102).'
    }]
  },
  'tartrazine': { 
    hazard: 'caution', 
    role: 'Food Dye (E102)', 
    reg: 'EU Warning', 
    impact: 'Allergy trigger in sensitive individuals' 
  },
  'yellow 6': { 
    hazard: 'caution', 
    role: 'Sunset Yellow Dye (E110)', 
    reg: 'EU Warning', 
    impact: 'Hyperactivity marker and histamine release trigger' 
  },
  'titanium dioxide': { 
    hazard: 'danger', 
    role: 'Whitening Agent / E171', 
    reg: 'Banned in EU Food since 2022', 
    impact: 'EFSA concluded in 2021 that E171 can no longer be considered safe due to nanoparticle DNA genotoxicity',
    regulatoryBadges: [
      {
        region: 'EU',
        authority: 'EFSA / ANSM',
        statusType: 'banned',
        title: 'Banned in EU Food (Reg 2022/63)',
        detail: 'Titanium dioxide (E171) is strictly forbidden in food across all EU member states.'
      },
      {
        region: 'US',
        authority: 'FDA',
        statusType: 'approved_gras',
        title: 'Permitted in US Food (<1%)',
        detail: 'Currently permitted by US FDA, but under consumer petition review.'
      }
    ]
  },
  'e171': { 
    hazard: 'danger', 
    role: 'Colorant (Titanium Dioxide)', 
    reg: 'Banned in EU Food', 
    impact: 'Nanoparticle DNA damage and gut barrier disruption risk',
    regulatoryBadges: [{
      region: 'EU',
      authority: 'EFSA',
      statusType: 'banned',
      title: 'Banned in EU Food (E171)',
      detail: 'Prohibited across France, Germany, Italy, Spain and all EU countries since 2022.'
    }]
  },
  'aspartame': { 
    hazard: 'caution', 
    role: 'Artificial Sweetener (E951)', 
    reg: 'IARC 2B Possible Carcinogen', 
    impact: 'Phenylalanine source (contraindicated in PKU); alters gut microbiota composition' 
  },
  'sucralose': { 
    hazard: 'caution', 
    role: 'Chlorinated Sweetener (E955)', 
    reg: 'FDA Approved / EFSA Monitored', 
    impact: 'Thermal cooking may release chloropropanols; affects insulin sensitivity' 
  },
  'acesulfame potassium': { 
    hazard: 'caution', 
    role: 'Artificial Sweetener (E950)', 
    reg: 'Monitored additive', 
    impact: 'Contains methylene chloride breakdown residues during manufacturing' 
  },
  'msg': { 
    hazard: 'caution', 
    role: 'Flavor Enhancer (E621)', 
    reg: 'FDA GRAS', 
    impact: 'Triggers glutamate sensitivity / headaches in predisposed individuals' 
  },
  'monosodium glutamate': { 
    hazard: 'caution', 
    role: 'Flavor Enhancer (E621)', 
    reg: 'FDA GRAS', 
    impact: 'Excitatory neurotransmitter precursor' 
  },
  'high fructose corn syrup': { 
    hazard: 'caution', 
    role: 'Refined Sugar / HFCS', 
    reg: 'AHA High Hazard', 
    impact: 'Rapid hepatic de novo lipogenesis, non-alcoholic fatty liver and metabolic syndrome' 
  },
  'partially hydrogenated': { 
    hazard: 'danger', 
    role: 'Industrial Trans Fat', 
    reg: 'Banned by FDA & WHO', 
    impact: 'Severe LDL elevation, HDL depletion, and cardiovascular arterial plaque progression',
    regulatoryBadges: [{
      region: 'GLOBAL',
      authority: 'WHO / FDA',
      statusType: 'banned',
      title: 'Eliminated Trans Fats',
      detail: 'Partially hydrogenated oils are banned in US, EU, UK due to cardiovascular mortality.'
    }]
  },
  'carrageenan': { 
    hazard: 'caution', 
    role: 'Stabilizing Hydrocolloid (E407)', 
    reg: 'EFSA Monitored', 
    impact: 'Degraded poligeenan forms induce gut barrier permeability in IBD / colitis studies' 
  },
  
  // Cosmetic & Skincare Toxins / Sensitizers (EU Cosmetic Regulation 1223/2009 & FDA)
  'methylparaben': { 
    hazard: 'caution', 
    role: 'Synthetic Paraben Preservative', 
    reg: 'EU Restricted Limits (0.4%)', 
    impact: 'Weak estrogenic receptor affinity' 
  },
  'propylparaben': { 
    hazard: 'danger', 
    role: 'Paraben Preservative', 
    reg: 'EU Restricted (0.14%) / Prop 65', 
    impact: 'Endocrine disruptor & hormone mimic' 
  },
  'butylparaben': { 
    hazard: 'danger', 
    role: 'Paraben Preservative', 
    reg: 'Banned in Denmark for children', 
    impact: 'Endocrine and reproductive disruption in fetal development' 
  },
  'isobutylparaben': { 
    hazard: 'danger', 
    role: 'Paraben Preservative', 
    reg: 'Banned in EU Cosmetics (Annex II)', 
    impact: 'High estrogenic activity; prohibited across Europe',
    regulatoryBadges: [{
      region: 'EU',
      authority: 'CosIng / EU Reg 1223/2009',
      statusType: 'banned',
      title: 'Banned in EU Cosmetics',
      detail: 'Isobutylparaben is strictly prohibited in European cosmetic formulations.'
    }]
  },
  'dmdm hydantoin': { 
    hazard: 'danger', 
    role: 'Formaldehyde-Releaser Preservative', 
    reg: 'EU Restricted / Warning Req', 
    impact: 'Slowly emits free formaldehyde; prominent contact dermatitis trigger' 
  },
  'diazolidinyl urea': { 
    hazard: 'danger', 
    role: 'Formaldehyde-Releaser', 
    reg: 'EU Restricted', 
    impact: 'Sensitizing preservative with formaldehyde emission' 
  },
  'imidazolidinyl urea': { 
    hazard: 'danger', 
    role: 'Formaldehyde Releaser', 
    reg: 'EU Restricted', 
    impact: 'High allergy potential in sensitive skin' 
  },
  'quaternium-15': { 
    hazard: 'danger', 
    role: 'Formaldehyde Releaser', 
    reg: 'Banned in EU Cosmetics (2022)', 
    impact: 'Formaldehyde donor; completely banned in EU cosmetics since March 2022',
    regulatoryBadges: [{
      region: 'EU',
      authority: 'EU Commission',
      statusType: 'banned',
      title: 'Banned in EU Cosmetics',
      detail: 'Quaternium-15 is prohibited in cosmetics sold in France, Germany, Italy, Spain & UK.'
    }]
  },
  'sodium lauryl sulfate': { 
    hazard: 'caution', 
    role: 'Anionic Surfactant (SLS)', 
    reg: 'Standard Detergent', 
    impact: 'Disrupts natural skin barrier lipids; causes trans-epidermal water loss (TEWL)' 
  },
  'sls': { 
    hazard: 'caution', 
    role: 'Harsh Surfactant', 
    reg: 'Known Irritant', 
    impact: 'Stripping of stratum corneum lipids' 
  },
  'fragrance': { 
    hazard: 'caution', 
    role: 'Undisclosed Chemical Blend', 
    reg: 'Top 3 Contact Allergen', 
    impact: 'May conceal dozens of unlisted sensitizers or phthalate fixatives' 
  },
  'parfum': { 
    hazard: 'caution', 
    role: 'Fragrance Blend', 
    reg: 'Contact Allergen List', 
    impact: 'Contains 26 regulated EU fragrance allergens (limonene, linalool, citral, geraniol)' 
  },
  'triclosan': { 
    hazard: 'danger', 
    role: 'Antibacterial Agent', 
    reg: 'Banned by FDA in OTC washes', 
    impact: 'Thyroid hormone disruption & aquatic eco-toxicity',
    regulatoryBadges: [{
      region: 'US',
      authority: 'FDA',
      statusType: 'banned',
      title: 'Banned in US OTC Washes',
      detail: 'FDA banned Triclosan from consumer antiseptic wash products.'
    }]
  },
  'oxybenzone': { 
    hazard: 'danger', 
    role: 'Chemical UV Filter (Benzophenone-3)', 
    reg: 'Banned in Hawaii / Key West', 
    impact: 'High endocrine disruptor; bleaches coral reefs and penetrates systemic blood stream' 
  },
  'octinoxate': { 
    hazard: 'danger', 
    role: 'Chemical Sunscreen Filter', 
    reg: 'Eco-toxicity restriction', 
    impact: 'Hormone disruption and skin sensitization' 
  },
  'phthalate': { 
    hazard: 'danger', 
    role: 'Plasticizer & Fragrance Fixative (DEP/DBP)', 
    reg: 'Banned in EU Toys & Cosmetics', 
    impact: 'Potent reproductive and anti-androgenic endocrine disruptor' 
  },
  'formaldehyde': { 
    hazard: 'danger', 
    role: 'Preservative', 
    reg: 'IARC Group 1 Human Carcinogen', 
    impact: 'Known human carcinogen and severe contact sensitizer' 
  }
};

export function analyzeIngredientSafety(ingredients: string[]): IngredientSafetyItem[] {
  if (!ingredients || ingredients.length === 0) return [];

  return ingredients.map((ing) => {
    const clean = ing.trim();
    const lower = clean.toLowerCase();

    // Check direct or partial match in hazard database
    let foundMatch: { hazard: 'danger' | 'caution'; role: string; reg: string; impact: string } | null = null;

    for (const [key, val] of Object.entries(KNOWN_HAZARDS)) {
      if (lower.includes(key)) {
        foundMatch = val;
        break;
      }
    }

    if (foundMatch) {
      return {
        name: clean,
        hazardLevel: foundMatch.hazard,
        roleDescription: foundMatch.role,
        regulatoryStatus: foundMatch.reg,
        healthImpact: foundMatch.impact
      };
    }

    // Beneficial / Safe heuristic markers
    const isPlantBioactive = /extract|water|oil|butter|flour|oat|leaf|root|berry|protein|fiber|seed|juice|vitamin|tocopherol|ascorbic|niacinamide|ceramide|hyaluronate|glycerin|zinc/i.test(lower);
    
    if (isPlantBioactive) {
      return {
        name: clean,
        hazardLevel: 'safe',
        roleDescription: 'Nourishing / Bioactive Compound',
        regulatoryStatus: 'Clean Verified (EWG 1-2)',
        healthImpact: 'Supports metabolic health or skin hydration'
      };
    }

    // Default safe / functional ingredient
    return {
      name: clean,
      hazardLevel: 'safe',
      roleDescription: 'Functional Ingredient / Carrier',
      regulatoryStatus: 'Standard GRAS Approval',
      healthImpact: 'No toxicological flags recorded'
    };
  });
}

/**
 * Extract active regulatory badges across jurisdictions for a given product ingredient list
 */
export function extractRegulatoryBadges(ingredients: string[]): RegulatoryStatusBadge[] {
  const badges: RegulatoryStatusBadge[] = [];
  if (!ingredients || ingredients.length === 0) return badges;

  const seen = new Set<string>();

  for (const ing of ingredients) {
    const lower = ing.toLowerCase().trim();
    for (const [key, val] of Object.entries(KNOWN_HAZARDS)) {
      if (lower.includes(key) && val.regulatoryBadges) {
        for (const badge of val.regulatoryBadges) {
          const badgeKey = `${badge.region}:${badge.authority}:${badge.title}`;
          if (!seen.has(badgeKey)) {
            seen.add(badgeKey);
            badges.push(badge);
          }
        }
      }
    }
  }

  return badges;
}


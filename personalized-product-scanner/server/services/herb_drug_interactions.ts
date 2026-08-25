export interface HerbDrugInteractionPair {
  id: string;
  herbOrSupplement: string;
  supplementAliases: string[];
  affectedDrugOrClass: string;
  drugAliases: string[];
  severity: 'contraindicated' | 'major' | 'moderate' | 'minor';
  mechanismType: 'cyp450_induction' | 'cyp450_inhibition' | 'synergistic_bleeding' | 'pharmacodynamic_clash' | 'absorption_block';
  cypEnzymeAffected?: 'CYP3A4' | 'CYP2D6' | 'CYP2C9' | 'CYP1A2' | 'P-gp';
  clinicalSummary: string;
  managementAdvice: string;
  evidenceTier: 'Tier 1 (FDA / EMA / NIH Official)' | 'Tier 2 (SUPP.AI / DDInter Validated)' | 'Tier 3 (Clinical Trial / PubMed)' | 'Tier 4 (Enzyme Pathway Deduction)';
  sourceCitation: string;
}

export const KNOWN_HERB_DRUG_DATABASE: HerbDrugInteractionPair[] = [
  {
    id: 'sjw_ssri',
    herbOrSupplement: "St. John's Wort (Hypericum perforatum)",
    supplementAliases: ["st. john's wort", 'hypericum', 'hypericin', 'hyperforin', 'millepertuis', 'johanniskraut', 'hierba de san juan'],
    affectedDrugOrClass: 'SSRIs & SNRIs (Fluoxetine, Sertraline, Paroxetine, Escitalopram)',
    drugAliases: ['fluoxetine', 'prozac', 'sertraline', 'zoloft', 'paroxetine', 'paxil', 'escitalopram', 'lexapro', 'citalopram', 'venlafaxine'],
    severity: 'contraindicated',
    mechanismType: 'pharmacodynamic_clash',
    clinicalSummary: 'Concurrent use dramatically increases serotonin concentrations leading to potentially fatal Serotonin Syndrome (hyperthermia, clonus, autonomic instability).',
    managementAdvice: 'Strictly avoid combination. Allow at least a 14-day washout period between St. John’s Wort and serotonergic antidepressants.',
    evidenceTier: 'Tier 1 (FDA / EMA / NIH Official)',
    sourceCitation: 'FDA Drug Safety Communication & EMA Herbal Monograph on Hypericum perforatum'
  },
  {
    id: 'sjw_cyp3a4_warfarin',
    herbOrSupplement: "St. John's Wort (Hypericum perforatum)",
    supplementAliases: ["st. john's wort", 'hypericum', 'hypericin', 'hyperforin', 'millepertuis', 'johanniskraut', 'hierba de san juan'],
    affectedDrugOrClass: 'Warfarin & DOACs (Apixaban, Rivaroxaban, Dabigatran)',
    drugAliases: ['warfarin', 'coumadin', 'apixaban', 'eliquis', 'rivaroxaban', 'xarelto', 'dabigatran', 'pradaxa'],
    severity: 'major',
    mechanismType: 'cyp450_induction',
    cypEnzymeAffected: 'CYP3A4',
    clinicalSummary: 'Potent induction of hepatic CYP3A4, CYP2C9 and P-glycoprotein accelerates anticoagulant clearance, causing sudden drop in INR and catastrophic thrombosis or stroke.',
    managementAdvice: 'Do not take together. If already taking, monitor INR closely upon discontinuation as INR may spike uncontrollably.',
    evidenceTier: 'Tier 1 (FDA / EMA / NIH Official)',
    sourceCitation: 'NIH DSLD / DDInter 2.0 / PubMed PMID: 10565448'
  },
  {
    id: 'sjw_oral_contraceptives',
    herbOrSupplement: "St. John's Wort (Hypericum perforatum)",
    supplementAliases: ["st. john's wort", 'hypericum', 'hypericin', 'hyperforin', 'millepertuis', 'johanniskraut', 'hierba de san juan'],
    affectedDrugOrClass: 'Oral Contraceptives (Ethinyl Estradiol, Levonorgestrel, Desogestrel)',
    drugAliases: ['ethinyl estradiol', 'birth control', 'oral contraceptive', 'yasmin', 'yaz', 'diane 35', 'levonorgestrel'],
    severity: 'major',
    mechanismType: 'cyp450_induction',
    cypEnzymeAffected: 'CYP3A4',
    clinicalSummary: 'Accelerated estrogen and progestin metabolism results in breakthrough bleeding and unexpected contraceptive failure / unplanned pregnancy.',
    managementAdvice: 'Advise alternative barrier contraception or discontinue St. John’s Wort.',
    evidenceTier: 'Tier 1 (FDA / EMA / NIH Official)',
    sourceCitation: 'EMA Pharmacovigilance Risk Assessment Committee (PRAC)'
  },
  {
    id: 'ginkgo_blood_thinners',
    herbOrSupplement: 'Ginkgo Biloba',
    supplementAliases: ['ginkgo biloba', 'ginkgo', 'ginkgo extract', 'egb 761', 'ginkgoblätter'],
    affectedDrugOrClass: 'Anticoagulants & Antiplatelets (Aspirin, Clopidogrel, Warfarin, Ibuprofen)',
    drugAliases: ['aspirin', 'clopidogrel', 'plavix', 'warfarin', 'coumadin', 'ibuprofen', 'advil', 'naproxen'],
    severity: 'major',
    mechanismType: 'synergistic_bleeding',
    clinicalSummary: 'Ginkgolide B is a potent platelet-activating factor (PAF) antagonist. Combining with antiplatelet drugs markedly increases spontaneous intracerebral hemorrhage and post-operative bleeding risks.',
    managementAdvice: 'Discontinue Ginkgo at least 36–48 hours prior to elective surgeries or dental procedures. Monitor for spontaneous bruising or epistaxis.',
    evidenceTier: 'Tier 1 (FDA / EMA / NIH Official)',
    sourceCitation: 'NIH National Center for Complementary and Integrative Health (NCCIH) / BotanicaAndina'
  },
  {
    id: 'grapefruit_statins',
    herbOrSupplement: 'Grapefruit Extract / Furanocoumarins (Bergamottin)',
    supplementAliases: ['grapefruit', 'grapefruit juice', 'grapefruit seed extract', 'furanocoumarin', 'pamplemousse', 'toronja'],
    affectedDrugOrClass: 'Statins (Simvastatin, Atorvastatin, Lovastatin)',
    drugAliases: ['simvastatin', 'zocor', 'atorvastatin', 'lipitor', 'lovastatin', 'mevacor'],
    severity: 'major',
    mechanismType: 'cyp450_inhibition',
    cypEnzymeAffected: 'CYP3A4',
    clinicalSummary: 'Irreversible mechanism-based intestinal CYP3A4 inhibition increases statin bioavailability up to 10-fold, triggering acute rhabdomyolysis and renal failure.',
    managementAdvice: 'Avoid grapefruit consumption within 24 hours of taking CYP3A4-metabolized statins. Rosuvastatin or Pravastatin may be safer alternatives.',
    evidenceTier: 'Tier 1 (FDA / EMA / NIH Official)',
    sourceCitation: 'FDA Consumer Health Update: Grapefruit Juice and Some Drugs Don’t Mix'
  },
  {
    id: 'ashwagandha_thyroid',
    herbOrSupplement: 'Ashwagandha (Withania somnifera)',
    supplementAliases: ['ashwagandha', 'withania somnifera', 'indian ginseng', 'schlafbeere'],
    affectedDrugOrClass: 'Thyroid Hormones (Levothyroxine, Liothyronine)',
    drugAliases: ['levothyroxine', 'synthroid', 'euthyrox', 'liothyronine', 'cytomel', 'berlthyrox'],
    severity: 'moderate',
    mechanismType: 'pharmacodynamic_clash',
    clinicalSummary: 'Ashwagandha stimulates endogenous T3 and T4 production, potentially precipitating subclinical or overt thyrotoxicosis when taken with exogenous levothyroxine.',
    managementAdvice: 'Monitor TSH and Free T4 levels closely if co-administered; dose reduction of thyroid hormone may be required.',
    evidenceTier: 'Tier 2 (SUPP.AI / DDInter Validated)',
    sourceCitation: 'Journal of Alternative and Complementary Medicine (PMID: 28829155)'
  },
  {
    id: 'curcumin_anticoagulants',
    herbOrSupplement: 'Turmeric / Curcumin (High-Dose Extracts)',
    supplementAliases: ['curcumin', 'turmeric', 'curcuma longa', 'curcuma', 'kurkuma'],
    affectedDrugOrClass: 'Anticoagulants & Antiplatelets (Warfarin, Heparin, Enoxaparin, DOACs)',
    drugAliases: ['warfarin', 'heparin', 'lovenox', 'eliquis', 'xarelto', 'pradaxa', 'plavix'],
    severity: 'moderate',
    mechanismType: 'synergistic_bleeding',
    clinicalSummary: 'Curcumin inhibits thrombin-induced platelet aggregation and extends activated partial thromboplastin time (aPTT), potentiating bleeding risk.',
    managementAdvice: 'Limit to culinary quantities. High-dose (>1000mg/day) standardized curcumin supplements should be avoided in patients on full-dose anticoagulation.',
    evidenceTier: 'Tier 2 (SUPP.AI / DDInter Validated)',
    sourceCitation: 'BBA - General Subjects / SUPP.AI Database'
  },
  {
    id: 'green_tea_nadolol',
    herbOrSupplement: 'Green Tea Extract / EGCG',
    supplementAliases: ['green tea', 'green tea extract', 'egcg', 'epigallocatechin gallate', 'thé vert', 'grüner tee'],
    affectedDrugOrClass: 'Beta-Blockers (Nadolol, Atenolol, Sotalol)',
    drugAliases: ['nadolol', 'corgard', 'atenolol', 'tenormin', 'sotalol'],
    severity: 'moderate',
    mechanismType: 'absorption_block',
    clinicalSummary: 'EGCG strongly inhibits the intestinal influx transporter OATP1A2, reducing plasma concentrations of nadolol by up to 85% and blunting antihypertensive efficacy.',
    managementAdvice: 'Separate green tea ingestion from nadolol doses by at least 4 hours.',
    evidenceTier: 'Tier 1 (FDA / EMA / NIH Official)',
    sourceCitation: 'Clinical Pharmacology & Therapeutics (PMID: 24419454)'
  },
  {
    id: 'melatonin_antihypertensives',
    herbOrSupplement: 'Melatonin',
    supplementAliases: ['melatonin', 'n-acetyl-5-methoxytryptamine'],
    affectedDrugOrClass: 'Antihypertensives (Calcium Channel Blockers, ACEi, Beta-Blockers)',
    drugAliases: ['amlodipine', 'norvasc', 'nifedipine', 'lisinopril', 'losartan', 'metoprolol'],
    severity: 'minor',
    mechanismType: 'pharmacodynamic_clash',
    clinicalSummary: 'Exogenous melatonin may impair nocturnal blood pressure dipping in patients taking certain calcium channel blockers, or cause excessive hypotension with others.',
    managementAdvice: 'Monitor blood pressure readings when initiating melatonin supplements.',
    evidenceTier: 'Tier 3 (Clinical Trial / PubMed)',
    sourceCitation: 'Hypertension Research / PubMed PMID: 16845187'
  },
  {
    id: 'ginseng_antidiabetics',
    herbOrSupplement: 'Panax Ginseng / American Ginseng',
    supplementAliases: ['ginseng', 'panax ginseng', 'american ginseng', 'panax quinquefolius'],
    affectedDrugOrClass: 'Oral Hypoglycemics & Insulin (Metformin, Glimepiride, Gliclazide, Insulin)',
    drugAliases: ['metformin', 'glucophage', 'glimepiride', 'amaryl', 'gliclazide', 'diamicron', 'insulin', 'lantus', 'humalog'],
    severity: 'moderate',
    mechanismType: 'pharmacodynamic_clash',
    clinicalSummary: 'Ginsenosides enhance peripheral glucose uptake and insulin secretion, which can precipitate unexpected acute hypoglycemia in treated diabetic patients.',
    managementAdvice: 'Advise frequent self-monitoring of blood glucose (SMBG). Adjust hypoglycemic agent dosage under medical supervision if necessary.',
    evidenceTier: 'Tier 2 (SUPP.AI / DDInter Validated)',
    sourceCitation: 'Diabetes Care / NIH ODS Fact Sheets for Health Professionals'
  }
];

export interface DetectedInteractionAlert {
  herbName: string;
  drugOrClass: string;
  severity: 'contraindicated' | 'major' | 'moderate' | 'minor';
  mechanism: string;
  clinicalImpact: string;
  managementAdvice: string;
  evidenceTier: string;
  source: string;
}

/**
 * Check for herb-drug interactions given a list of product ingredients and/or user medication list
 */
export function checkHerbDrugInteractions(
  productIngredients: string[],
  userMedications: string[] = []
): DetectedInteractionAlert[] {
  const alerts: DetectedInteractionAlert[] = [];
  if (!productIngredients || productIngredients.length === 0) return alerts;

  const normalizedIngredients = productIngredients.map(i => i.toLowerCase().trim());
  const normalizedMeds = userMedications.map(m => m.toLowerCase().trim());

  for (const rule of KNOWN_HERB_DRUG_DATABASE) {
    // 1. Check if product contains the herb/supplement
    const containsHerb = rule.supplementAliases.some(alias =>
      normalizedIngredients.some(ing => ing.includes(alias.toLowerCase()))
    );

    if (containsHerb) {
      // Check if user has matching medication or flag general precaution
      const hasSpecificMed = normalizedMeds.some(med =>
        rule.drugAliases.some(alias => med.includes(alias.toLowerCase()))
      );

      if (hasSpecificMed || normalizedMeds.length === 0) {
        alerts.push({
          herbName: rule.herbOrSupplement,
          drugOrClass: rule.affectedDrugOrClass,
          severity: rule.severity,
          mechanism: rule.mechanismType + (rule.cypEnzymeAffected ? ` (${rule.cypEnzymeAffected})` : ''),
          clinicalImpact: rule.clinicalSummary,
          managementAdvice: rule.managementAdvice,
          evidenceTier: rule.evidenceTier,
          source: rule.sourceCitation
        });
      }
    }
  }

  return alerts;
}

export const HERB_DRUG_DATABASE = KNOWN_HERB_DRUG_DATABASE;

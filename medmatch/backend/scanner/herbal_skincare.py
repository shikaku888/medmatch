"""Herb-drug interaction reference + skincare routine conflict engine.

Ported from personalized-product-scanner/server/services/{herb_drug_interactions,skincare_conflicts}.ts — do not diverge.
"""
from __future__ import annotations

import re

KNOWN_HERB_DRUG_DATABASE: list[dict] = [{'id': 'sjw_ssri',
  'herbOrSupplement': "St. John's Wort (Hypericum perforatum)",
  'supplementAliases': ["st. john's wort",
                        'hypericum',
                        'hypericin',
                        'hyperforin',
                        'millepertuis',
                        'johanniskraut',
                        'hierba de san juan'],
  'affectedDrugOrClass': 'SSRIs & SNRIs (Fluoxetine, Sertraline, Paroxetine, Escitalopram)',
  'drugAliases': ['fluoxetine',
                  'prozac',
                  'sertraline',
                  'zoloft',
                  'paroxetine',
                  'paxil',
                  'escitalopram',
                  'lexapro',
                  'citalopram',
                  'venlafaxine'],
  'severity': 'contraindicated',
  'mechanismType': 'pharmacodynamic_clash',
  'clinicalSummary': 'Concurrent use dramatically increases serotonin concentrations leading to potentially '
                     'fatal Serotonin Syndrome (hyperthermia, clonus, autonomic instability).',
  'managementAdvice': 'Strictly avoid combination. Allow at least a 14-day washout period between St. John’s '
                      'Wort and serotonergic antidepressants.',
  'evidenceTier': 'Tier 1 (FDA / EMA / NIH Official)',
  'sourceCitation': 'FDA Drug Safety Communication & EMA Herbal Monograph on Hypericum perforatum'},
 {'id': 'sjw_cyp3a4_warfarin',
  'herbOrSupplement': "St. John's Wort (Hypericum perforatum)",
  'supplementAliases': ["st. john's wort",
                        'hypericum',
                        'hypericin',
                        'hyperforin',
                        'millepertuis',
                        'johanniskraut',
                        'hierba de san juan'],
  'affectedDrugOrClass': 'Warfarin & DOACs (Apixaban, Rivaroxaban, Dabigatran)',
  'drugAliases': ['warfarin',
                  'coumadin',
                  'apixaban',
                  'eliquis',
                  'rivaroxaban',
                  'xarelto',
                  'dabigatran',
                  'pradaxa'],
  'severity': 'major',
  'mechanismType': 'cyp450_induction',
  'cypEnzymeAffected': 'CYP3A4',
  'clinicalSummary': 'Potent induction of hepatic CYP3A4, CYP2C9 and P-glycoprotein accelerates '
                     'anticoagulant clearance, causing sudden drop in INR and catastrophic thrombosis or '
                     'stroke.',
  'managementAdvice': 'Do not take together. If already taking, monitor INR closely upon discontinuation as '
                      'INR may spike uncontrollably.',
  'evidenceTier': 'Tier 1 (FDA / EMA / NIH Official)',
  'sourceCitation': 'NIH DSLD / DDInter 2.0 / PubMed PMID: 10565448'},
 {'id': 'sjw_oral_contraceptives',
  'herbOrSupplement': "St. John's Wort (Hypericum perforatum)",
  'supplementAliases': ["st. john's wort",
                        'hypericum',
                        'hypericin',
                        'hyperforin',
                        'millepertuis',
                        'johanniskraut',
                        'hierba de san juan'],
  'affectedDrugOrClass': 'Oral Contraceptives (Ethinyl Estradiol, Levonorgestrel, Desogestrel)',
  'drugAliases': ['ethinyl estradiol',
                  'birth control',
                  'oral contraceptive',
                  'yasmin',
                  'yaz',
                  'diane 35',
                  'levonorgestrel'],
  'severity': 'major',
  'mechanismType': 'cyp450_induction',
  'cypEnzymeAffected': 'CYP3A4',
  'clinicalSummary': 'Accelerated estrogen and progestin metabolism results in breakthrough bleeding and '
                     'unexpected contraceptive failure / unplanned pregnancy.',
  'managementAdvice': 'Advise alternative barrier contraception or discontinue St. John’s Wort.',
  'evidenceTier': 'Tier 1 (FDA / EMA / NIH Official)',
  'sourceCitation': 'EMA Pharmacovigilance Risk Assessment Committee (PRAC)'},
 {'id': 'ginkgo_blood_thinners',
  'herbOrSupplement': 'Ginkgo Biloba',
  'supplementAliases': ['ginkgo biloba', 'ginkgo', 'ginkgo extract', 'egb 761', 'ginkgoblätter'],
  'affectedDrugOrClass': 'Anticoagulants & Antiplatelets (Aspirin, Clopidogrel, Warfarin, Ibuprofen)',
  'drugAliases': ['aspirin',
                  'clopidogrel',
                  'plavix',
                  'warfarin',
                  'coumadin',
                  'ibuprofen',
                  'advil',
                  'naproxen'],
  'severity': 'major',
  'mechanismType': 'synergistic_bleeding',
  'clinicalSummary': 'Ginkgolide B is a potent platelet-activating factor (PAF) antagonist. Combining with '
                     'antiplatelet drugs markedly increases spontaneous intracerebral hemorrhage and '
                     'post-operative bleeding risks.',
  'managementAdvice': 'Discontinue Ginkgo at least 36–48 hours prior to elective surgeries or dental '
                      'procedures. Monitor for spontaneous bruising or epistaxis.',
  'evidenceTier': 'Tier 1 (FDA / EMA / NIH Official)',
  'sourceCitation': 'NIH National Center for Complementary and Integrative Health (NCCIH) / BotanicaAndina'},
 {'id': 'grapefruit_statins',
  'herbOrSupplement': 'Grapefruit Extract / Furanocoumarins (Bergamottin)',
  'supplementAliases': ['grapefruit',
                        'grapefruit juice',
                        'grapefruit seed extract',
                        'furanocoumarin',
                        'pamplemousse',
                        'toronja'],
  'affectedDrugOrClass': 'Statins (Simvastatin, Atorvastatin, Lovastatin)',
  'drugAliases': ['simvastatin', 'zocor', 'atorvastatin', 'lipitor', 'lovastatin', 'mevacor'],
  'severity': 'major',
  'mechanismType': 'cyp450_inhibition',
  'cypEnzymeAffected': 'CYP3A4',
  'clinicalSummary': 'Irreversible mechanism-based intestinal CYP3A4 inhibition increases statin '
                     'bioavailability up to 10-fold, triggering acute rhabdomyolysis and renal failure.',
  'managementAdvice': 'Avoid grapefruit consumption within 24 hours of taking CYP3A4-metabolized statins. '
                      'Rosuvastatin or Pravastatin may be safer alternatives.',
  'evidenceTier': 'Tier 1 (FDA / EMA / NIH Official)',
  'sourceCitation': 'FDA Consumer Health Update: Grapefruit Juice and Some Drugs Don’t Mix'},
 {'id': 'ashwagandha_thyroid',
  'herbOrSupplement': 'Ashwagandha (Withania somnifera)',
  'supplementAliases': ['ashwagandha', 'withania somnifera', 'indian ginseng', 'schlafbeere'],
  'affectedDrugOrClass': 'Thyroid Hormones (Levothyroxine, Liothyronine)',
  'drugAliases': ['levothyroxine', 'synthroid', 'euthyrox', 'liothyronine', 'cytomel', 'berlthyrox'],
  'severity': 'moderate',
  'mechanismType': 'pharmacodynamic_clash',
  'clinicalSummary': 'Ashwagandha stimulates endogenous T3 and T4 production, potentially precipitating '
                     'subclinical or overt thyrotoxicosis when taken with exogenous levothyroxine.',
  'managementAdvice': 'Monitor TSH and Free T4 levels closely if co-administered; dose reduction of thyroid '
                      'hormone may be required.',
  'evidenceTier': 'Tier 2 (SUPP.AI / DDInter Validated)',
  'sourceCitation': 'Journal of Alternative and Complementary Medicine (PMID: 28829155)'},
 {'id': 'curcumin_anticoagulants',
  'herbOrSupplement': 'Turmeric / Curcumin (High-Dose Extracts)',
  'supplementAliases': ['curcumin', 'turmeric', 'curcuma longa', 'curcuma', 'kurkuma'],
  'affectedDrugOrClass': 'Anticoagulants & Antiplatelets (Warfarin, Heparin, Enoxaparin, DOACs)',
  'drugAliases': ['warfarin', 'heparin', 'lovenox', 'eliquis', 'xarelto', 'pradaxa', 'plavix'],
  'severity': 'moderate',
  'mechanismType': 'synergistic_bleeding',
  'clinicalSummary': 'Curcumin inhibits thrombin-induced platelet aggregation and extends activated partial '
                     'thromboplastin time (aPTT), potentiating bleeding risk.',
  'managementAdvice': 'Limit to culinary quantities. High-dose (>1000mg/day) standardized curcumin '
                      'supplements should be avoided in patients on full-dose anticoagulation.',
  'evidenceTier': 'Tier 2 (SUPP.AI / DDInter Validated)',
  'sourceCitation': 'BBA - General Subjects / SUPP.AI Database'},
 {'id': 'green_tea_nadolol',
  'herbOrSupplement': 'Green Tea Extract / EGCG',
  'supplementAliases': ['green tea',
                        'green tea extract',
                        'egcg',
                        'epigallocatechin gallate',
                        'thé vert',
                        'grüner tee'],
  'affectedDrugOrClass': 'Beta-Blockers (Nadolol, Atenolol, Sotalol)',
  'drugAliases': ['nadolol', 'corgard', 'atenolol', 'tenormin', 'sotalol'],
  'severity': 'moderate',
  'mechanismType': 'absorption_block',
  'clinicalSummary': 'EGCG strongly inhibits the intestinal influx transporter OATP1A2, reducing plasma '
                     'concentrations of nadolol by up to 85% and blunting antihypertensive efficacy.',
  'managementAdvice': 'Separate green tea ingestion from nadolol doses by at least 4 hours.',
  'evidenceTier': 'Tier 1 (FDA / EMA / NIH Official)',
  'sourceCitation': 'Clinical Pharmacology & Therapeutics (PMID: 24419454)'},
 {'id': 'melatonin_antihypertensives',
  'herbOrSupplement': 'Melatonin',
  'supplementAliases': ['melatonin', 'n-acetyl-5-methoxytryptamine'],
  'affectedDrugOrClass': 'Antihypertensives (Calcium Channel Blockers, ACEi, Beta-Blockers)',
  'drugAliases': ['amlodipine', 'norvasc', 'nifedipine', 'lisinopril', 'losartan', 'metoprolol'],
  'severity': 'minor',
  'mechanismType': 'pharmacodynamic_clash',
  'clinicalSummary': 'Exogenous melatonin may impair nocturnal blood pressure dipping in patients taking '
                     'certain calcium channel blockers, or cause excessive hypotension with others.',
  'managementAdvice': 'Monitor blood pressure readings when initiating melatonin supplements.',
  'evidenceTier': 'Tier 3 (Clinical Trial / PubMed)',
  'sourceCitation': 'Hypertension Research / PubMed PMID: 16845187'},
 {'id': 'ginseng_antidiabetics',
  'herbOrSupplement': 'Panax Ginseng / American Ginseng',
  'supplementAliases': ['ginseng', 'panax ginseng', 'american ginseng', 'panax quinquefolius'],
  'affectedDrugOrClass': 'Oral Hypoglycemics & Insulin (Metformin, Glimepiride, Gliclazide, Insulin)',
  'drugAliases': ['metformin',
                  'glucophage',
                  'glimepiride',
                  'amaryl',
                  'gliclazide',
                  'diamicron',
                  'insulin',
                  'lantus',
                  'humalog'],
  'severity': 'moderate',
  'mechanismType': 'pharmacodynamic_clash',
  'clinicalSummary': 'Ginsenosides enhance peripheral glucose uptake and insulin secretion, which can '
                     'precipitate unexpected acute hypoglycemia in treated diabetic patients.',
  'managementAdvice': 'Advise frequent self-monitoring of blood glucose (SMBG). Adjust hypoglycemic agent '
                      'dosage under medical supervision if necessary.',
  'evidenceTier': 'Tier 2 (SUPP.AI / DDInter Validated)',
  'sourceCitation': 'Diabetes Care / NIH ODS Fact Sheets for Health Professionals'}]

HERB_DRUG_DATABASE = KNOWN_HERB_DRUG_DATABASE

# (matching algorithm from TS checkHerbDrugInteractions)
def check_herb_drug_interactions(
    product_ingredients: list[str],
    user_medications: list[str] | None = None,
) -> list[dict]:
    """Check for herb-drug interactions given product ingredients and user medications."""
    alerts: list[dict] = []
    if not product_ingredients:
        return alerts
    meds = [m.lower().strip() for m in (user_medications or [])]
    ings = [i.lower().strip() for i in product_ingredients]

    for rule in KNOWN_HERB_DRUG_DATABASE:
        # 1. Check if product contains the herb/supplement
        contains_herb = any(
            alias.lower() in ing for alias in rule["supplementAliases"] for ing in ings
        )
        if contains_herb:
            has_specific_med = any(
                alias.lower() in med for alias in rule["drugAliases"] for med in meds
            )
            if has_specific_med or len(meds) == 0:
                alerts.append(
                    {
                        "herbName": rule["herbOrSupplement"],
                        "drugOrClass": rule["affectedDrugOrClass"],
                        "severity": rule["severity"],
                        "mechanism": rule["mechanismType"]
                        + (f" ({rule['cypEnzymeAffected']})" if rule.get("cypEnzymeAffected") else ""),
                        "clinicalImpact": rule["clinicalSummary"],
                        "managementAdvice": rule["managementAdvice"],
                        "evidenceTier": rule["evidenceTier"],
                        "source": rule["sourceCitation"],
                    }
                )
    return alerts


ACTIVE_KEYWORDS: list[dict] = [
    # Retinoids
    {"pattern": re.compile(r"\b(retinol)\b", re.I), "name": "Retinol", "category": "retinoid", "role": "Cellular renewal, collagen synthesis stimulation"},
    {"pattern": re.compile(r"\b(retinal|retinaldehyde)\b", re.I), "name": "Retinal", "category": "retinoid", "role": "Next-gen retinoid, faster conversion than Retinol"},
    {"pattern": re.compile(r"\b(tretinoin|adapalene|tazarotene)\b", re.I), "name": "Prescription Retinoid", "category": "retinoid", "role": "Medical-grade retinoid for acne and deep anti-aging"},
    {"pattern": re.compile(r"\b(retinyl palmitate)\b", re.I), "name": "Retinyl Palmitate", "category": "retinoid", "role": "Gentle retinoid ester derivative"},
    # Direct Exfoliating Acids
    {"pattern": re.compile(r"\b(salicylic acid|betaine salicylate)\b", re.I), "name": "Salicylic Acid (BHA)", "category": "bha", "role": "Lipid-soluble, pore-clearing, anti-inflammatory"},
    {"pattern": re.compile(r"\b(glycolic acid)\b", re.I), "name": "Glycolic Acid (AHA)", "category": "aha", "role": "Small-molecule AHA, epidermal resurfacing, brightening"},
    {"pattern": re.compile(r"\b(lactic acid)\b", re.I), "name": "Lactic Acid (AHA)", "category": "aha", "role": "Gentle AHA, moisturizing and skin smoothing"},
    {"pattern": re.compile(r"\b(mandelic acid)\b", re.I), "name": "Mandelic Acid (AHA)", "category": "aha", "role": "Larger-molecule AHA for sensitive skin"},
    {"pattern": re.compile(r"\b(gluconolactone|lactobionic acid)\b", re.I), "name": "PHA (Gluconolactone)", "category": "pha", "role": "Next-gen polyhydroxy exfoliant, antioxidant, barrier-safe"},
    # Vitamin C
    {"pattern": re.compile(r"\b(ascorbic acid|l-ascorbic acid)\b", re.I), "name": "L-Ascorbic Acid (Pure Vitamin C)", "category": "vitamin_c_pure", "role": "Potent antioxidant, hyperpigmentation fading, collagen boost (pH < 3.5)"},
    {"pattern": re.compile(r"\b(ethyl ascorbic acid|ascorbyl glucoside|sodium ascorbyl phosphate|magnesium ascorbyl phosphate|tetrahexyldecyl ascorbate)\b", re.I), "name": "Vitamin C Derivative (EAA/SAP)", "category": "vitamin_c_derivative", "role": "Stable Vitamin C derivative, low irritation"},
    # Vitamin B3 (Niacinamide)
    {"pattern": re.compile(r"\b(niacinamide|nicotinamide)\b", re.I), "name": "Niacinamide (Vitamin B3)", "category": "niacinamide", "role": "Barrier ceramide synthesis, sebum regulation, tone evening"},
    # Benzoyl Peroxide
    {"pattern": re.compile(r"\b(benzoyl peroxide)\b", re.I), "name": "Benzoyl Peroxide (BPO)", "category": "benzoyl_peroxide", "role": "Antibacterial against C. acnes, inflammatory acne treatment"},
    # Copper Peptides
    {"pattern": re.compile(r"\b(copper tripeptide-1|ghk-cu|copper peptide)\b", re.I), "name": "Copper Tripeptide-1 (GHK-Cu)", "category": "copper_peptide", "role": "Tissue remodeling, extracellular matrix restoration"},
    # Brightening & Specialty
    {"pattern": re.compile(r"\b(hydroquinone)\b", re.I), "name": "Hydroquinone", "category": "hydroquinone", "role": "Tyrosinase inhibitor for severe hyperpigmentation/melasma"},
    {"pattern": re.compile(r"\b(azelaic acid|potassium azeloyl diglycinate)\b", re.I), "name": "Azelaic Acid", "category": "azelaic_acid", "role": "Anti-inflammatory, redness and Rosacea relief, blemish reduction"},
    # Barrier & Soothing
    {"pattern": re.compile(r"\b(ceramide np|ceramide ap|ceramide eop|ceramide|phytosphingosine)\b", re.I), "name": "Ceramides Complex", "category": "barrier_ceramide", "role": "Epidermal lipid barrier repair, moisture locking, anti-TEWL"},
    {"pattern": re.compile(r"\b(sodium hyaluronate|hyaluronic acid|hydrolyzed hyaluronic acid)\b", re.I), "name": "Hyaluronic Acid (HA)", "category": "hyaluronic_acid", "role": "Multi-depth humectant hydration, skin plumping"},
    # Sunscreen Filters
    {"pattern": re.compile(r"\b(zinc oxide|titanium dioxide)\b", re.I), "name": "Mineral UV Filter (Zinc/Titanium)", "category": "physical_sunscreen", "role": "Broad spectrum inorganic physical UV reflective filter"},
    {"pattern": re.compile(r"\b(avobenzone|homosalate|octisalate|octocrylene|tinosorb|uvinul)\b", re.I), "name": "Chemical UV Filters", "category": "chemical_sunscreen", "role": "Organic chemical UV absorbing filter"},
]


def extract_skincare_actives(ingredients_text: str, ingredients_list: list[str] | None = None) -> list[dict]:
    full = (ingredients_text + " " + " ".join(ingredients_list or [])).lower()
    detected: list[dict] = []
    added_names: set[str] = set()

    for item in ACTIVE_KEYWORDS:
        if item["pattern"].search(full) and item["name"] not in added_names:
            added_names.add(item["name"])
            detected.append({"name": item["name"], "category": item["category"], "role": item["role"]})

    return detected


CONFLICT_MATRIX: list[dict] = [
    {
        "pair": ["retinoid", "bha"],
        "severity": "high",
        "ruleTitle": "Exfoliation Collision: Retinoid + BHA (Salicylic Acid)",
        "riskDescription": "Both actives accelerate cellular turnover and penetration. Using both in the same evening routine risks severe barrier compromise, erythema, peeling, and trans-epidermal water loss.",
        "solutionRecommendation": "Adopt Skin Cycling or alternate nights: Use BHA on night 1, Retinoid on night 2, followed by recovery nights.",
        "timingGuide": "Separate: BHA in AM (with SPF50) or on alternating evenings from Retinoids.",
        "barrierDamageRisk": True,
    },
    {
        "pair": ["retinoid", "aha"],
        "severity": "high",
        "ruleTitle": "Potent Acid Clash: Retinoid + AHA (Glycolic/Lactic Acid)",
        "riskDescription": "AHA loosens stratum corneum desmosomes while Retinoid accelerates basal layer cell division, compounding irritation and risk of chemical burn.",
        "solutionRecommendation": "Alternate on different nights. Always apply barrier-repair moisturizers with Ceramides.",
        "timingGuide": "Always alternate nights; never layer directly on top of each other.",
        "barrierDamageRisk": True,
    },
    {
        "pair": ["retinoid", "benzoyl_peroxide"],
        "severity": "high",
        "ruleTitle": "Oxidative Deactivation: Retinoid + Benzoyl Peroxide (BPO)",
        "riskDescription": "Benzoyl Peroxide is a strong oxidizing agent that can degrade and inactivate standard Retinol molecules while causing extreme dryness.",
        "solutionRecommendation": "Use Benzoyl Peroxide as a spot treatment in AM and apply Retinoid across face in PM.",
        "timingGuide": "BPO: Morning | Retinoid: Evening.",
    },
    {
        "pair": ["vitamin_c_pure", "aha"],
        "severity": "medium",
        "ruleTitle": "Low pH Overload: L-Ascorbic Acid + AHA Direct Acids",
        "riskDescription": "Both L-Ascorbic Acid and AHA require very low pH (<3.5) to penetrate. Layering together induces acute pH shock, stinging, and redness.",
        "solutionRecommendation": "Move Pure Vitamin C to your morning routine to boost antioxidant UV defense, and keep AHA for night routines.",
        "timingGuide": "Vitamin C: Morning (with SPF50+) | AHA: Evening.",
        "phClash": True,
    },
    {
        "pair": ["vitamin_c_pure", "bha"],
        "severity": "medium",
        "ruleTitle": "Acid Overload: L-Ascorbic Acid + BHA (Salicylic Acid)",
        "riskDescription": "Combining multiple strong low-pH acids simultaneously can strip the natural acid mantle and elevate UV sensitivity.",
        "solutionRecommendation": "Use Vitamin C in the morning and BHA at night, or alternate days.",
        "timingGuide": "Vitamin C: Morning | BHA: Evening.",
        "phClash": True,
    },
    {
        "pair": ["copper_peptide", "vitamin_c_pure"],
        "severity": "high",
        "ruleTitle": "Peptide Breakdown: Copper Peptides (GHK-Cu) + Pure Vitamin C",
        "riskDescription": "Copper ions (Cu2+) oxidize ascorbic acid molecules, neutralizing Vitamin C antioxidant efficacy and cleaving peptide bonds.",
        "solutionRecommendation": "Never mix in the same routine step. Use Vitamin C in the morning and Copper Peptide in the evening.",
        "timingGuide": "Vitamin C: Morning | Copper Peptide: Evening.",
    },
    {
        "pair": ["copper_peptide", "aha"],
        "severity": "medium",
        "ruleTitle": "Peptide Bond Cleavage: Copper Peptide + AHA/BHA",
        "riskDescription": "Strong acidic environments from AHA/BHA denature copper peptide amino acid chains, diminishing collagen stimulation.",
        "solutionRecommendation": "Use exfoliating acids on days when Copper Peptides are not applied.",
        "timingGuide": "Alternate days or apply in opposite morning/evening routines.",
    },
    {
        "pair": ["benzoyl_peroxide", "hydroquinone"],
        "severity": "caution",
        "ruleTitle": "Temporary Skin Staining Risk: BPO + Hydroquinone",
        "riskDescription": "Oxidative reactions between BPO and Hydroquinone can create temporary dark surface staining on the skin.",
        "solutionRecommendation": "Do not layer directly over the same surface area.",
        "timingGuide": "Separate into different times of day or switch to Azelaic Acid for brightening.",
    },
    # SYNERGIES
    {
        "pair": ["niacinamide", "retinoid"],
        "severity": "synergy",
        "ruleTitle": "Golden Synergy: Niacinamide + Retinoid",
        "riskDescription": "Highly compatible and protective. Niacinamide stimulates natural ceramide synthesis, soothing irritation and reducing retinoid-induced redness by up to 60%.",
        "solutionRecommendation": "Apply Niacinamide serum first to cushion the barrier, then follow with Retinoid or barrier cream.",
        "timingGuide": "Safe and beneficial to combine in Evening routines.",
    },
    {
        "pair": ["vitamin_c_pure", "physical_sunscreen"],
        "severity": "synergy",
        "ruleTitle": "Photo-Protection Synergy: Vitamin C + Sunscreen",
        "riskDescription": "Vitamin C neutralizes free radicals generated by UV rays that penetrate sunscreen filters, doubling defense against photo-aging and dark spots.",
        "solutionRecommendation": "Apply Vitamin C serum every morning before sunscreen application.",
        "timingGuide": "Standard Morning routine best practice.",
    },
    {
        "pair": ["barrier_ceramide", "retinoid"],
        "severity": "synergy",
        "ruleTitle": "Barrier Cushion Synergy: Ceramides + Retinoid",
        "riskDescription": "Ceramides reinforce the lipid barrier vulnerable during retinization, preventing trans-epidermal water loss (TEWL).",
        "solutionRecommendation": "Use the Sandwich Technique (Moisturizer -> Retinoid -> Moisturizer) for sensitive skin.",
        "timingGuide": "Evening routine cushion.",
    },
    {
        "pair": ["hyaluronic_acid", "aha"],
        "severity": "synergy",
        "ruleTitle": "Multi-Depth Hydration: Hyaluronic Acid + AHA/BHA",
        "riskDescription": "HA floods newly exfoliated cellular layers with moisture, ensuring supple plumpness without post-acid dehydration.",
        "solutionRecommendation": "Apply HA serum 5-10 minutes after acid exfoliation.",
        "timingGuide": "Safe for both AM & PM.",
    },
]

_SKIN_CYCLING_GUIDE = [
    {
        "dayOrTime": "Night 1 (Exfoliation)",
        "instructions": "Deep cleanse -> AHA/BHA Exfoliant -> Barrier Ceramide Cream.",
        "productsUsed": ["BHA / AHA Exfoliant", "Barrier Cream"],
    },
    {
        "dayOrTime": "Night 2 (Targeted Retinoid)",
        "instructions": "Gentle cleanse -> Niacinamide Serum -> Retinol / Retinal -> Moisture lock.",
        "productsUsed": ["Retinol / Retinal", "Niacinamide", "Moisturizer"],
    },
    {
        "dayOrTime": "Nights 3 & 4 (Barrier Recovery)",
        "instructions": "Pause all direct acids & retinoids. Apply multi-depth HA + Peptides + Rich Ceramide cream.",
        "productsUsed": ["Hyaluronic Acid", "Peptide / Panthenol", "Ceramide Cream"],
    },
    {
        "dayOrTime": "Every Morning",
        "instructions": "Cleanse -> Vitamin C / Niacinamide Serum -> Broad Spectrum Sunscreen SPF 50+.",
        "productsUsed": ["Vitamin C / Niacinamide", "Sunscreen SPF50+"],
    },
]


def analyze_skincare_routine_conflicts(
    routine_products: list[dict],
    new_product_actives: list[dict] | None = None,
) -> dict:
    new_product_actives = new_product_actives or []
    all_actives: list[dict] = []

    # 1. Gather all actives from existing routine
    for prod in routine_products or []:
        for ing_name in prod.get("activeIngredients") or []:
            detected = extract_skincare_actives(ing_name)
            if detected:
                for d in detected:
                    all_actives.append({"active": d, "sourceProduct": prod["name"], "time": prod["timeOfDay"]})
            else:
                # Fallback generic active item
                all_actives.append(
                    {
                        "active": {"name": ing_name, "category": "aha", "role": "Active ingredient"},
                        "sourceProduct": prod["name"],
                        "time": prod["timeOfDay"],
                    }
                )

    for act in new_product_actives:
        if isinstance(act, str):
            detected = extract_skincare_actives(act)
            candidates = detected or [{"name": act, "category": "aha", "role": "Active ingredient"}]
        else:
            candidates = [act]
        for active in candidates:
            if not isinstance(active, dict) or not active.get("category"):
                continue
            all_actives.append({"active": active, "sourceProduct": "Scanned Product", "time": "both"})

    conflicts: list[dict] = []
    synergies: list[dict] = []

    # 3. Test every pair
    for i in range(len(all_actives)):
        for j in range(i + 1, len(all_actives)):
            item_a, item_b = all_actives[i], all_actives[j]

            for rule in CONFLICT_MATRIX:
                matches_forward = rule["pair"][0] == item_a["active"]["category"] and rule["pair"][1] == item_b["active"]["category"]
                matches_reverse = rule["pair"][1] == item_a["active"]["category"] and rule["pair"][0] == item_b["active"]["category"]

                if matches_forward or matches_reverse:
                    warning_obj = {
                        "activeA": f"{item_a['active']['name']} ({item_a['sourceProduct']})",
                        "activeB": f"{item_b['active']['name']} ({item_b['sourceProduct']})",
                        "severity": rule["severity"],
                        "ruleTitle": rule["ruleTitle"],
                        "riskDescription": rule["riskDescription"],
                        "solutionRecommendation": rule["solutionRecommendation"],
                        "timingGuide": rule["timingGuide"],
                        "phClash": rule.get("phClash"),
                        "barrierDamageRisk": rule.get("barrierDamageRisk"),
                    }

                    if rule["severity"] == "synergy":
                        if not any(s["ruleTitle"] == rule["ruleTitle"] for s in synergies):
                            synergies.append(warning_obj)
                    elif not any(c["ruleTitle"] == rule["ruleTitle"] for c in conflicts):
                            conflicts.append(warning_obj)

    # Calculate routine score
    safety_score = 100
    high_conflicts = sum(1 for c in conflicts if c["severity"] == "high")
    med_conflicts = sum(1 for c in conflicts if c["severity"] in ("medium", "caution"))
    safety_score -= high_conflicts * 30
    safety_score -= med_conflicts * 15
    safety_score = max(20, min(100, safety_score))

    return {
        "conflictCount": len(conflicts),
        "synergyCount": len(synergies),
        "overallRoutineSafetyScore": safety_score,
        "conflicts": conflicts,
        "synergies": synergies,
        "activeIngredientsFound": new_product_actives,
        "skinCyclingGuide": _SKIN_CYCLING_GUIDE,
    }

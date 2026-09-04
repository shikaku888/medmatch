"""Personalized product matching — ported from personalized-product-scanner/server/services/{matcher,cross_reactivity,ingredient_safety}.ts — do not diverge."""
from __future__ import annotations

import re

from backend.scanner.ext_clients import get_pubmed_research
from backend.scanner.herbal_skincare import extract_skincare_actives, analyze_skincare_routine_conflicts
from backend.scanner.storage import get_user_db

_KNOWN_HAZARDS: dict[str, dict] = {'sodium nitrite': {'hazard': 'danger',
                    'role': 'Curing Agent & Preservative (E250)',
                    'reg': 'IARC 2A Probable Carcinogen',
                    'impact': 'Forms carcinogenic nitrosamines upon high-heat cooking',
                    'regulatoryBadges': [{'region': 'GLOBAL',
                                          'authority': 'IARC / WHO',
                                          'statusType': 'restricted',
                                          'title': 'Group 2A Carcinogen',
                                          'detail': 'Processed meat preservative associated with '
                                                    'colorectal cancer risks.'}]},
 'sodium nitrate': {'hazard': 'danger',
                    'role': 'Curing Agent (E251)',
                    'reg': 'WHO Warning Limit',
                    'impact': 'Associated with vascular endothelial damage and nitrosamine synthesis'},
 'potassium bromate': {'hazard': 'danger',
                       'role': 'Flour Dough Conditioner (E924)',
                       'reg': 'Banned in EU, UK, Canada, Brazil',
                       'impact': 'Known renal and thyroid carcinogen; prohibited across Europe but '
                                 'permitted in US bakery goods',
                       'regulatoryBadges': [{'region': 'EU',
                                             'authority': 'EFSA',
                                             'statusType': 'banned',
                                             'title': 'Banned in EU Food',
                                             'detail': 'Potassium bromate is classified as a category 2B '
                                                       'carcinogen.'},
                                            {'region': 'UK',
                                             'authority': 'FSA',
                                             'statusType': 'banned',
                                             'title': 'Banned in UK',
                                             'detail': 'Illegal in flour and baked products across the '
                                                       'United Kingdom.'},
                                            {'region': 'US',
                                             'authority': 'FDA',
                                             'statusType': 'restricted',
                                             'title': 'Allowed in US Bakeries',
                                             'detail': 'Permitted in US flours; California requires Prop '
                                                       '65 warning.'}]},
 'bha': {'hazard': 'danger',
         'role': 'Synthetic Antioxidant (E320)',
         'reg': 'California Prop 65 Listed',
         'impact': 'Suspected endocrine disruptor and human carcinogen',
         'regulatoryBadges': [{'region': 'US',
                               'authority': 'Prop 65',
                               'statusType': 'warning_label',
                               'title': 'CA Prop 65 Listed',
                               'detail': 'Known to the State of California to cause cancer.'}]},
 'bht': {'hazard': 'caution',
         'role': 'Synthetic Preservative (E321)',
         'reg': 'EU Usage Restrictions / EFSA',
         'impact': 'Potential endocrine disruption in higher chronic doses'},
 'butylated hydroxyanisole': {'hazard': 'danger',
                              'role': 'Synthetic Antioxidant (E320)',
                              'reg': 'Prop 65 Warning',
                              'impact': 'Endocrine disruptor'},
 'butylated hydroxytoluene': {'hazard': 'caution',
                              'role': 'Preservative (E321)',
                              'reg': 'EFSA Monitored',
                              'impact': 'Immune & endocrine interaction'},
 'azodicarbonamide': {'hazard': 'danger',
                      'role': 'Dough Bleaching Agent (E927a)',
                      'reg': 'Banned in EU & UK / Allowed in US',
                      'impact': 'Thermal breakdown produces semicarbazide and urethane carcinogens',
                      'regulatoryBadges': [{'region': 'EU',
                                            'authority': 'EFSA',
                                            'statusType': 'banned',
                                            'title': 'Banned in EU Food',
                                            'detail': 'Forbidden as a food additive in the European '
                                                      'Union.'},
                                           {'region': 'US',
                                            'authority': 'FDA',
                                            'statusType': 'approved_gras',
                                            'title': 'FDA Permitted (up to 45 ppm)',
                                            'detail': 'Approved as a flour maturing agent in the United '
                                                      'States.'}]},
 'red 40': {'hazard': 'caution',
            'role': 'Synthetic Azo Dye (E129 / Allura Red)',
            'reg': 'EU Warning Label Required',
            'impact': 'Linked to hyperactivity and ADHD symptom exacerbation in children',
            'regulatoryBadges': [{'region': 'EU',
                                  'authority': 'EFSA',
                                  'statusType': 'warning_label',
                                  'title': 'EU Warning Label Required',
                                  'detail': 'Mandatory label: "May have an adverse effect on activity and '
                                            'attention in children".'}]},
 'allura red': {'hazard': 'caution',
                'role': 'Synthetic Colorant (E129)',
                'reg': 'EU Warning Label',
                'impact': 'Potential allergenicity & hyperactivity',
                'regulatoryBadges': [{'region': 'EU',
                                      'authority': 'EFSA',
                                      'statusType': 'warning_label',
                                      'title': 'EU Warning Label Required',
                                      'detail': 'Requires childhood hyperactivity warning on food '
                                                'packaging in France, Germany, Spain, Italy & UK.'}]},
 'yellow 5': {'hazard': 'caution',
              'role': 'Synthetic Tartrazine Dye (E102)',
              'reg': 'EU Warning Required',
              'impact': 'Known allergen & bronchospasm trigger in asthmatics and sensitive kids',
              'regulatoryBadges': [{'region': 'EU',
                                    'authority': 'EFSA',
                                    'statusType': 'warning_label',
                                    'title': 'EU Warning Label Required',
                                    'detail': 'European regulations mandate behavioral warning for '
                                              'Tartrazine (E102).'}]},
 'tartrazine': {'hazard': 'caution',
                'role': 'Food Dye (E102)',
                'reg': 'EU Warning',
                'impact': 'Allergy trigger in sensitive individuals'},
 'yellow 6': {'hazard': 'caution',
              'role': 'Sunset Yellow Dye (E110)',
              'reg': 'EU Warning',
              'impact': 'Hyperactivity marker and histamine release trigger'},
 'titanium dioxide': {'hazard': 'danger',
                      'role': 'Whitening Agent / E171',
                      'reg': 'Banned in EU Food since 2022',
                      'impact': 'EFSA concluded in 2021 that E171 can no longer be considered safe due to '
                                'nanoparticle DNA genotoxicity',
                      'regulatoryBadges': [{'region': 'EU',
                                            'authority': 'EFSA / ANSM',
                                            'statusType': 'banned',
                                            'title': 'Banned in EU Food (Reg 2022/63)',
                                            'detail': 'Titanium dioxide (E171) is strictly forbidden in '
                                                      'food across all EU member states.'},
                                           {'region': 'US',
                                            'authority': 'FDA',
                                            'statusType': 'approved_gras',
                                            'title': 'Permitted in US Food (<1%)',
                                            'detail': 'Currently permitted by US FDA, but under consumer '
                                                      'petition review.'}]},
 'e171': {'hazard': 'danger',
          'role': 'Colorant (Titanium Dioxide)',
          'reg': 'Banned in EU Food',
          'impact': 'Nanoparticle DNA damage and gut barrier disruption risk',
          'regulatoryBadges': [{'region': 'EU',
                                'authority': 'EFSA',
                                'statusType': 'banned',
                                'title': 'Banned in EU Food (E171)',
                                'detail': 'Prohibited across France, Germany, Italy, Spain and all EU '
                                          'countries since 2022.'}]},
 'aspartame': {'hazard': 'caution',
               'role': 'Artificial Sweetener (E951)',
               'reg': 'IARC 2B Possible Carcinogen',
               'impact': 'Phenylalanine source (contraindicated in PKU); alters gut microbiota '
                         'composition'},
 'sucralose': {'hazard': 'caution',
               'role': 'Chlorinated Sweetener (E955)',
               'reg': 'FDA Approved / EFSA Monitored',
               'impact': 'Thermal cooking may release chloropropanols; affects insulin sensitivity'},
 'acesulfame potassium': {'hazard': 'caution',
                          'role': 'Artificial Sweetener (E950)',
                          'reg': 'Monitored additive',
                          'impact': 'Contains methylene chloride breakdown residues during manufacturing'},
 'msg': {'hazard': 'caution',
         'role': 'Flavor Enhancer (E621)',
         'reg': 'FDA GRAS',
         'impact': 'Triggers glutamate sensitivity / headaches in predisposed individuals'},
 'monosodium glutamate': {'hazard': 'caution',
                          'role': 'Flavor Enhancer (E621)',
                          'reg': 'FDA GRAS',
                          'impact': 'Excitatory neurotransmitter precursor'},
 'high fructose corn syrup': {'hazard': 'caution',
                              'role': 'Refined Sugar / HFCS',
                              'reg': 'AHA High Hazard',
                              'impact': 'Rapid hepatic de novo lipogenesis, non-alcoholic fatty liver and '
                                        'metabolic syndrome'},
 'partially hydrogenated': {'hazard': 'danger',
                            'role': 'Industrial Trans Fat',
                            'reg': 'Banned by FDA & WHO',
                            'impact': 'Severe LDL elevation, HDL depletion, and cardiovascular arterial '
                                      'plaque progression',
                            'regulatoryBadges': [{'region': 'GLOBAL',
                                                  'authority': 'WHO / FDA',
                                                  'statusType': 'banned',
                                                  'title': 'Eliminated Trans Fats',
                                                  'detail': 'Partially hydrogenated oils are banned in US, '
                                                            'EU, UK due to cardiovascular mortality.'}]},
 'carrageenan': {'hazard': 'caution',
                 'role': 'Stabilizing Hydrocolloid (E407)',
                 'reg': 'EFSA Monitored',
                 'impact': 'Degraded poligeenan forms induce gut barrier permeability in IBD / colitis '
                           'studies'},
 'methylparaben': {'hazard': 'caution',
                   'role': 'Synthetic Paraben Preservative',
                   'reg': 'EU Restricted Limits (0.4%)',
                   'impact': 'Weak estrogenic receptor affinity'},
 'propylparaben': {'hazard': 'danger',
                   'role': 'Paraben Preservative',
                   'reg': 'EU Restricted (0.14%) / Prop 65',
                   'impact': 'Endocrine disruptor & hormone mimic'},
 'butylparaben': {'hazard': 'danger',
                  'role': 'Paraben Preservative',
                  'reg': 'Banned in Denmark for children',
                  'impact': 'Endocrine and reproductive disruption in fetal development'},
 'isobutylparaben': {'hazard': 'danger',
                     'role': 'Paraben Preservative',
                     'reg': 'Banned in EU Cosmetics (Annex II)',
                     'impact': 'High estrogenic activity; prohibited across Europe',
                     'regulatoryBadges': [{'region': 'EU',
                                           'authority': 'CosIng / EU Reg 1223/2009',
                                           'statusType': 'banned',
                                           'title': 'Banned in EU Cosmetics',
                                           'detail': 'Isobutylparaben is strictly prohibited in European '
                                                     'cosmetic formulations.'}]},
 'dmdm hydantoin': {'hazard': 'danger',
                    'role': 'Formaldehyde-Releaser Preservative',
                    'reg': 'EU Restricted / Warning Req',
                    'impact': 'Slowly emits free formaldehyde; prominent contact dermatitis trigger'},
 'diazolidinyl urea': {'hazard': 'danger',
                       'role': 'Formaldehyde-Releaser',
                       'reg': 'EU Restricted',
                       'impact': 'Sensitizing preservative with formaldehyde emission'},
 'imidazolidinyl urea': {'hazard': 'danger',
                         'role': 'Formaldehyde Releaser',
                         'reg': 'EU Restricted',
                         'impact': 'High allergy potential in sensitive skin'},
 'quaternium-15': {'hazard': 'danger',
                   'role': 'Formaldehyde Releaser',
                   'reg': 'Banned in EU Cosmetics (2022)',
                   'impact': 'Formaldehyde donor; completely banned in EU cosmetics since March 2022',
                   'regulatoryBadges': [{'region': 'EU',
                                         'authority': 'EU Commission',
                                         'statusType': 'banned',
                                         'title': 'Banned in EU Cosmetics',
                                         'detail': 'Quaternium-15 is prohibited in cosmetics sold in '
                                                   'France, Germany, Italy, Spain & UK.'}]},
 'sodium lauryl sulfate': {'hazard': 'caution',
                           'role': 'Anionic Surfactant (SLS)',
                           'reg': 'Standard Detergent',
                           'impact': 'Disrupts natural skin barrier lipids; causes trans-epidermal water '
                                     'loss (TEWL)'},
 'sls': {'hazard': 'caution',
         'role': 'Harsh Surfactant',
         'reg': 'Known Irritant',
         'impact': 'Stripping of stratum corneum lipids'},
 'fragrance': {'hazard': 'caution',
               'role': 'Undisclosed Chemical Blend',
               'reg': 'Top 3 Contact Allergen',
               'impact': 'May conceal dozens of unlisted sensitizers or phthalate fixatives'},
 'parfum': {'hazard': 'caution',
            'role': 'Fragrance Blend',
            'reg': 'Contact Allergen List',
            'impact': 'Contains 26 regulated EU fragrance allergens (limonene, linalool, citral, '
                      'geraniol)'},
 'triclosan': {'hazard': 'danger',
               'role': 'Antibacterial Agent',
               'reg': 'Banned by FDA in OTC washes',
               'impact': 'Thyroid hormone disruption & aquatic eco-toxicity',
               'regulatoryBadges': [{'region': 'US',
                                     'authority': 'FDA',
                                     'statusType': 'banned',
                                     'title': 'Banned in US OTC Washes',
                                     'detail': 'FDA banned Triclosan from consumer antiseptic wash '
                                               'products.'}]},
 'oxybenzone': {'hazard': 'danger',
                'role': 'Chemical UV Filter (Benzophenone-3)',
                'reg': 'Banned in Hawaii / Key West',
                'impact': 'High endocrine disruptor; bleaches coral reefs and penetrates systemic blood '
                          'stream'},
 'octinoxate': {'hazard': 'danger',
                'role': 'Chemical Sunscreen Filter',
                'reg': 'Eco-toxicity restriction',
                'impact': 'Hormone disruption and skin sensitization'},
 'phthalate': {'hazard': 'danger',
               'role': 'Plasticizer & Fragrance Fixative (DEP/DBP)',
               'reg': 'Banned in EU Toys & Cosmetics',
               'impact': 'Potent reproductive and anti-androgenic endocrine disruptor'},
 'formaldehyde': {'hazard': 'danger',
                  'role': 'Preservative',
                  'reg': 'IARC Group 1 Human Carcinogen',
                  'impact': 'Known human carcinogen and severe contact sensitizer'}}

_LOCALIZED_HAZARDS: dict[str, dict] = {
    "着色料": {
        "hazard": "caution", "role": "Food Colorant (Japanese label category)",
        "reg": "Specific additive not identified", "impact": "The label identifies a colorant category; the exact additive and individual sensitivity require verification.",
    },
    "保存料": {
        "hazard": "caution", "role": "Preservative (Japanese label category)",
        "reg": "Specific additive not identified", "impact": "The label identifies a preservative category; the exact additive and permitted use require verification.",
    },
    "酸化防止剤": {
        "hazard": "caution", "role": "Antioxidant (Japanese label category)",
        "reg": "Specific additive not identified", "impact": "The label identifies an antioxidant category; the exact additive requires verification.",
    },
    "甘味料": {
        "hazard": "caution", "role": "Sweetener (Japanese label category)",
        "reg": "Specific additive not identified", "impact": "The label identifies a sweetener category; the exact additive and suitability require verification.",
    },
    "香料": {
        "hazard": "caution", "role": "Flavoring (Japanese label category)",
        "reg": "Specific additive not identified", "impact": "The label identifies a flavoring category; the exact additive requires verification.",
    },
    "増粘剤": {
        "hazard": "caution", "role": "Thickener (Japanese label category)",
        "reg": "Specific additive not identified", "impact": "The label identifies a thickener category; the exact additive requires verification.",
    },
    "乳化剤": {
        "hazard": "caution", "role": "Emulsifier (Japanese label category)",
        "reg": "Specific additive not identified", "impact": "The label identifies an emulsifier category; the exact additive requires verification.",
    },
}

_ALL_HAZARDS = {**_KNOWN_HAZARDS, **_LOCALIZED_HAZARDS}

ALLERGEN_SYNONYMS: dict[str, list[str]] = {'peanut': ['peanut',
            '落花生',
            'らっかせい',
            'ピーナッツ',
            'arachis',
            'groundnut',
            'monkey nut',
            'peanut butter',
            'peanut oil',
            'arachis hypogaea'],
 'tree_nut': ['almond',
              'cashew',
              'walnut',
              'hazelnut',
              'pecan',
              'pistachio',
              'macadamia',
              'brazil nut',
              'chestnut',
              'prunus dulcis',
              'anacardium'],
 'milk': ['milk',
          'dairy',
          'whey',
          'casein',
          'caseinate',
          'lactose',
          'butter',
          'cream',
          'cheese',
          'ghee',
          'curd',
          'yogurt',
          'milkfat',
          'skimmed milk',
          'lactalbumin',
          'sodium caseinate'],
 'gluten': ['gluten',
            'wheat',
            'barley',
            'rye',
            'spelt',
            'kamut',
            'malt',
            'semolina',
            'durum',
            'farina',
            'graham flour',
            'triticale',
            'wheat flour',
            'wheat starch'],
 'egg': ['egg',
         'albumin',
         'ovalbumin',
         'globulin',
         'lysozyme',
         'mayonnaise',
         'yolk',
         'egg white',
         'ovomucin',
         'ovovitellin'],
 'soy': ['soy',
         'soya',
         'soybean',
         'tofu',
         'edamame',
         'tamari',
         'miso',
         'tempeh',
         'soy lecithin',
         'glycine max',
         'hydrolyzed soy protein'],
 'fish': ['fish',
          'salmon',
          'tuna',
          'cod',
          'anchovy',
          'tilapia',
          'halibut',
          'mackerel',
          'sardine',
          'fish oil',
          'fish sauce',
          'isinglass'],
 'shellfish': ['shellfish',
               'crustacean',
               'shrimp',
               'prawn',
               'crab',
               'lobster',
               'crawfish',
               'clam',
               'mussel',
               'oyster',
               'scallop',
               'squid',
               'calamari',
               'octopus',
               'mollusc'],
 'sesame': ['sesame', 'tahini', 'sesamum indicum', 'benne', 'sesame oil', 'sesame seed'],
 'sulfite': ['sulfite',
             'sulphite',
             'sulfur dioxide',
             'e220',
             'e221',
             'e222',
             'e223',
             'e224',
             'e228',
             'sodium metabisulfite',
             'potassium metabisulfite'],
 'mustard': ['mustard', 'sinapis alba', 'brassica nigra'],
 'celery': ['celery', 'celeriac', 'apium graveolens'],
 'lupin': ['lupin', 'lupine', 'lupinus'],
 'mollusc': ['mollusc', 'mollusk', 'snail', 'slug', 'squid', 'clam', 'oyster', 'mussel'],
 'fragrance': ['fragrance',
               'parfum',
               'perfume',
               'linalool',
               'limonene',
               'citronellol',
               'geraniol',
               'eugenol',
               'cinnamal',
               'hydroxycitronellal',
               'coumarin'],
 'parabens': ['methylparaben',
              'propylparaben',
              'butylparaben',
              'ethylparaben',
              'isobutylparaben',
              'paraben'],
 'sulfates': ['sodium lauryl sulfate',
              'sls',
              'sodium laureth sulfate',
              'sles',
              'ammonium lauryl sulfate',
              'sodium coco-sulfate'],
 'alcohol': ['alcohol denat', 'denatured alcohol', 'isopropyl alcohol', 'sd alcohol', 'ethanol'],
 'essential_oils': ['essential oil',
                    'lavender oil',
                    'tea tree oil',
                    'eucalyptus oil',
                    'citrus peel oil',
                    'peppermint oil',
                    'rosemary oil'],
 'retinoid': ['retinol',
              'retinal',
              'retinaldehyde',
              'retinyl palmitate',
              'tretinoin',
              'adapalene',
              'tazarotene'],
 'salicylic_acid': ['salicylic acid', 'betaine salicylate', 'willow bark extract']}

# Japanese label vocabulary. These terms are intentionally additive: the
# English profile keys remain the stable API, while Japanese ingredient OCR can
# trigger the same allergy rules.
ALLERGEN_SYNONYMS["peanut"].extend(["落花生", "らっかせい", "ピーナッツ"])
ALLERGEN_SYNONYMS["tree_nut"].extend(["木の実", "ナッツ", "アーモンド", "カシューナッツ", "くるみ", "ヘーゼルナッツ"])
ALLERGEN_SYNONYMS["milk"].extend(["乳", "乳成分", "乳製品", "牛乳", "乳糖"])
ALLERGEN_SYNONYMS["egg"].extend(["卵", "鶏卵", "卵白", "卵黄"])
ALLERGEN_SYNONYMS["soy"].extend(["大豆", "枝豆", "しょうゆ", "醤油", "味噌", "みそ"])
ALLERGEN_SYNONYMS["fish"].extend(["魚", "魚介"])
ALLERGEN_SYNONYMS["shellfish"].extend(["えび", "エビ", "かに", "カニ", "甲殻類"])
ALLERGEN_SYNONYMS["sesame"].extend(["ごま", "ゴマ", "胡麻"])
ALLERGEN_SYNONYMS["mustard"].extend(["からし", "カラシ", "辛子"])
ALLERGEN_SYNONYMS["celery"].extend(["セロリ"])
ALLERGEN_SYNONYMS["sulfite"].extend(["亜硫酸", "二酸化硫黄"])
ALLERGEN_SYNONYMS["gelatin"] = ALLERGEN_SYNONYMS.get("gelatin", []) + ["ゼラチン"]

DRUG_ALLERGY_GROUPS: dict[str, list[str]] = {
    "penicillin": [
        "penicillin",
        "amoxicillin",
        "ampicillin",
        "oxacillin",
        "piperacillin",
    ],
}

NON_VEGAN_INGREDIENTS = ['meat',
 'beef',
 'pork',
 'chicken',
 'poultry',
 'lamb',
 'bacon',
 'ham',
 'gelatin',
 'carmine',
 'cochineal',
 'e120',
 'casein',
 'whey',
 'lactose',
 'honey',
 'beeswax',
 'cera alba',
 'lard',
 'tallow',
 'collagen',
 'keratin',
 'lanolin',
 'shellac',
 'isinglass',
 'fish oil',
 'anchovy',
 'duck fat',
 'animal fat']

NON_VEGETARIAN_INGREDIENTS = ['meat',
 'beef',
 'pork',
 'chicken',
 'poultry',
 'lamb',
 'bacon',
 'ham',
 'gelatin',
 'carmine',
 'cochineal',
 'e120',
 'lard',
 'tallow',
 'collagen',
 'isinglass',
 'anchovy',
 'animal fat',
 'rennet']

NON_HALAL_INGREDIENTS = ['pork',
 'bacon',
 'ham',
 'lard',
 'swine',
 'porcine',
 'gelatin (pork)',
 'alcohol',
 'ethanol',
 'wine',
 'beer',
 'rum',
 'brandy',
 'carmine',
 'e120']

NON_KOSHER_INGREDIENTS = ['pork',
 'bacon',
 'ham',
 'lard',
 'shellfish',
 'shrimp',
 'crab',
 'lobster',
 'clam',
 'oyster',
 'crawfish',
 'catfish',
 'eel',
 'carmine',
 'e120']

PREGNANCY_RISK_INGREDIENTS = [{'name': 'retinol',
  'risk': 'high',
  'reason': 'High-dose Vitamin A derivatives have clinical teratogenic risks during pregnancy.'},
 {'name': 'retinal', 'risk': 'high', 'reason': 'Retinoids are medically contraindicated during pregnancy.'},
 {'name': 'retinyl palmitate', 'risk': 'high', 'reason': 'Retinoid derivative caution during pregnancy.'},
 {'name': 'tretinoin',
  'risk': 'high',
  'reason': 'Prescription/strong retinoid strictly contraindicated in pregnancy.'},
 {'name': 'hydroquinone',
  'risk': 'high',
  'reason': 'High skin absorption rate; contraindicated during pregnancy.'},
 {'name': 'salicylic acid',
  'risk': 'medium',
  'reason': 'High concentrations of BHA are recommended to be limited during pregnancy.'},
 {'name': 'unpasteurized',
  'risk': 'high',
  'reason': 'Listeria contamination risk in unpasteurized food products.'},
 {'name': 'saccharin', 'risk': 'low', 'reason': 'Artificial sweetener that crosses placenta slowly.'}]

CROSS_REACTIVITY_RULES: list[dict] = [{'id': 'birch_pollen_oas',
  'sourceKey': 'birch_pollen',
  'sourceName': 'Birch Tree Pollen (Betula / Bet v 1)',
  'syndromeName': 'Oral Allergy Syndrome / Pollen Food Allergy (OAS / PFAS)',
  'proteinFamily': 'Bet v 1 Homologs (PR-10 Pathogenesis-Related Protein)',
  'mechanism': 'Bet v 1 protein in birch pollen shares high 3D structural homology (>70% identity) with '
               'defense proteins in Rosaceae and Apiaceae families.',
  'symptoms': ['Oropharyngeal itching and tingling',
               'Mild lip and tongue swelling',
               'Prickling sensation when chewing raw fruit'],
  'cookingEffect': 'PR-10 proteins are heat-labile. Cooking, pasteurization, canning, or microwave heating '
                   'denatures the protein epitope, making it safe for most sensitized individuals.',
  'crossItems': [{'name': 'Apple (Mal d 1)',
                  'riskPercent': '75% - 90%',
                  'riskLevel': 'very_high',
                  'notes': 'Most common cross-reactive fruit in birch pollen allergic patients'},
                 {'name': 'Hazelnut (Cor a 1.04)',
                  'riskPercent': '60% - 80%',
                  'riskLevel': 'very_high',
                  'notes': 'Can cause mild oral symptoms or severe reactions if consumed in large amounts'},
                 {'name': 'Peach & Plum (Pru p 1)',
                  'riskPercent': '50% - 70%',
                  'riskLevel': 'high',
                  'notes': 'Peel contains higher protein concentrations than pulp'},
                 {'name': 'Pear & Cherry',
                  'riskPercent': '40% - 60%',
                  'riskLevel': 'medium',
                  'notes': 'Reactivity typically reduced when peeled or baked'},
                 {'name': 'Carrot & Celery (Dau c 1 / Api g 1)',
                  'riskPercent': '40% - 60%',
                  'riskLevel': 'medium',
                  'notes': 'Celery also contains heat-stable lipid transfer proteins'},
                 {'name': 'Kiwi & Soy (Gly m 4)',
                  'riskPercent': '30% - 50%',
                  'riskLevel': 'moderate',
                  'notes': 'Unheated soy milk can trigger systemic allergic reactions'},
                 {'name': 'Almond (Pru du 1)',
                  'riskPercent': '30% - 45%',
                  'riskLevel': 'moderate',
                  'notes': 'Bet v 1 mediated mild oral cross-reactivity'}]},
 {'id': 'latex_fruit_syndrome',
  'sourceKey': 'latex',
  'sourceName': 'Natural Rubber Latex (Hevea brasiliensis)',
  'syndromeName': 'Latex-Fruit Allergy Syndrome',
  'proteinFamily': 'Hevein-like Class I Chitinases (Hev b 6.02) & Beta-1,3-Glucanases',
  'mechanism': 'Antigenic epitopes in plant defense endochitinases show high cross-reactivity with Hev b '
               'antigens from natural rubber latex.',
  'symptoms': ['Acute urticaria / hives',
               'Allergic rhinitis and conjunctivitis',
               'Bronchospasm or dyspnea after ingestion'],
  'cookingEffect': 'Class I chitinase proteins possess moderate heat resistance. Standard cooking may not '
                   'completely eliminate the risk of reaction.',
  'crossItems': [{'name': 'Banana (Mus a 2)',
                  'riskPercent': '70% - 85%',
                  'riskLevel': 'very_high',
                  'notes': 'Highest antigenic concordance in the latex-fruit syndrome'},
                 {'name': 'Avocado (Pers a 1)',
                  'riskPercent': '60% - 80%',
                  'riskLevel': 'very_high',
                  'notes': 'Frequently triggers reactions even in small amounts (guacamole, sauces)'},
                 {'name': 'Chestnut (Cas s 1)',
                  'riskPercent': '50% - 70%',
                  'riskLevel': 'high',
                  'notes': 'May trigger systemic allergic symptoms'},
                 {'name': 'Kiwi (Act d 1 / Act d 2)',
                  'riskPercent': '40% - 60%',
                  'riskLevel': 'high',
                  'notes': 'Mucosal irritation and perioral swelling'},
                 {'name': 'Papaya & Fig',
                  'riskPercent': '30% - 50%',
                  'riskLevel': 'medium',
                  'notes': 'Contains papain and related cross-reactive endoproteases'},
                 {'name': 'Tomato & Passion Fruit',
                  'riskPercent': '25% - 40%',
                  'riskLevel': 'moderate',
                  'notes': 'Mild cross-reactive IgE antibody binding'}]},
 {'id': 'cmpa_mammalian_milk',
  'sourceKey': 'milk',
  'sourceName': "Cow's Milk Protein Allergy (CMPA)",
  'syndromeName': 'Mammalian Milk Cross-Reactivity',
  'proteinFamily': 'Alpha-S1 Casein, Beta-Casein & Beta-Lactoglobulin',
  'mechanism': 'Over 90% of cow milk protein allergic patients cross-react with goat, sheep, and buffalo '
               'milk due to >85% amino acid sequence homology.',
  'symptoms': ['Eczema and atopic dermatitis flares',
               'Reflux, abdominal colic, diarrhea',
               'Wheezing and respiratory distress'],
  'cookingEffect': 'Casein is heat-stable and survives boiling. Beta-lactoglobulin reactivity is only '
                   'slightly reduced when baked at >180°C.',
  'crossItems': [{'name': 'Goat Milk',
                  'riskPercent': '90% - 95%',
                  'riskLevel': 'very_high',
                  'notes': 'Do NOT substitute cow milk with goat milk in CMPA patients'},
                 {'name': 'Sheep Milk & Pecorino Cheese',
                  'riskPercent': '90% - 95%',
                  'riskLevel': 'very_high',
                  'notes': 'Casein structure is almost completely identical'},
                 {'name': 'Buffalo Milk & Mozzarella di Bufala',
                  'riskPercent': '80% - 90%',
                  'riskLevel': 'very_high',
                  'notes': 'High potential for severe allergic cross-reactivity'},
                 {'name': 'Beef meat (Bovine Serum Albumin - BSA)',
                  'riskPercent': '10% - 20%',
                  'riskLevel': 'moderate',
                  'notes': 'Occurs in a minority of milk-allergic patients sensitized to BSA'}]},
 {'id': 'peanut_legumes_matrix',
  'sourceKey': 'peanut',
  'sourceName': 'Peanut (Arachis hypogaea)',
  'syndromeName': 'Legume & Botanical Seed Cross-Reactivity Matrix',
  'proteinFamily': 'Vicilin (7S globulin), Legumin (11S) & 2S Albumin',
  'mechanism': 'Peanuts are botanically legumes (Fabaceae). Seed storage proteins (2S albumin, 7S '
               'globulin) share homologous epitopes with other legumes and seeds.',
  'symptoms': ['Angioedema, dyspnea', 'Systemic urticaria and flushing', 'Acute gastrointestinal distress'],
  'cookingEffect': 'Peanut allergens (Ara h 1, 2, 6) are extremely heat and gastric acid resistant. '
                   'High-temperature roasting actually increases immunogenicity.',
  'crossItems': [{'name': 'Lupin / Lupine Flour',
                  'riskPercent': '30% - 50%',
                  'riskLevel': 'high',
                  'notes': 'Common in European baked goods, specialty pastas, and waffles'},
                 {'name': 'Fenugreek (Trigonella foenum-graecum)',
                  'riskPercent': '25% - 45%',
                  'riskLevel': 'medium',
                  'notes': 'Found in curry powders, Indian seasonings, lactation herbal teas'},
                 {'name': 'Soybean',
                  'riskPercent': '10% - 25%',
                  'riskLevel': 'moderate',
                  'notes': 'Most patients tolerate highly refined soybean oil'},
                 {'name': 'Green Pea & Lentil',
                  'riskPercent': '15% - 30%',
                  'riskLevel': 'moderate',
                  'notes': 'Commonly presents as mild gastrointestinal symptoms'}]},
 {'id': 'tree_nut_cross_pairs',
  'sourceKey': 'tree_nut',
  'sourceName': 'Tree Nuts (Cashew, Walnut, Almond, Pistachio, Hazelnut)',
  'syndromeName': 'Botanical Tree Nut Pair Cross-Reactivity',
  'proteinFamily': '2S Albumins & 11S Globulins (Anacardiaceae / Juglandaceae)',
  'mechanism': 'Cashew and pistachio belong to Anacardiaceae with ~90% clinical cross-reactivity. Walnut '
               'and pecan belong to Juglandaceae with ~90% cross-reactivity.',
  'symptoms': ['Severe anaphylaxis',
               'Laryngeal edema / airway constriction',
               'Facial and periorbital edema'],
  'cookingEffect': 'Tree nut 2S albumins are exceptionally heat-stable and resist standard household '
                   'cooking temperatures.',
  'crossItems': [{'name': 'Cashew ↔ Pistachio',
                  'riskPercent': '85% - 95%',
                  'riskLevel': 'very_high',
                  'notes': 'Cashew-allergic individuals almost universally react to pistachios'},
                 {'name': 'Walnut ↔ Pecan',
                  'riskPercent': '85% - 95%',
                  'riskLevel': 'very_high',
                  'notes': 'Jug r 1 and Cpa l 1 proteins share virtually identical structures'},
                 {'name': 'Almond ↔ Hazelnut',
                  'riskPercent': '30% - 50%',
                  'riskLevel': 'medium',
                  'notes': 'Moderate botanical cross-reactivity within tree nut families'}]},
 {'id': 'crustacean_shellfish_matrix',
  'sourceKey': 'shellfish',
  'sourceName': 'Crustaceans & Shellfish (Shrimp, Crab, Lobster)',
  'syndromeName': 'Invertebrate Tropomyosin Cross-Reactivity Syndrome',
  'proteinFamily': 'Muscle Protein Tropomyosin (Cra c 1, Pan b 1, Pen a 1)',
  'mechanism': 'Tropomyosin is an ultra-conserved muscle contractile protein across arthropods and '
               'mollusks. Shrimp/crab allergic individuals frequently cross-react with squid, snails, and '
               'oysters.',
  'symptoms': ['Laryngeal constriction',
               'Cutaneous erythema and hypotension',
               'Nausea, abdominal cramping, and vomiting'],
  'cookingEffect': 'Tropomyosin is one of the most heat- and protease-stable food allergens known; boiling '
                   'or grilling will not inactivate it.',
  'crossItems': [{'name': 'Shrimp ↔ Crab ↔ Lobster',
                  'riskPercent': '80% - 95%',
                  'riskLevel': 'very_high',
                  'notes': 'Near universal cross-reactivity across crustacean species'},
                 {'name': 'Squid & Octopus (Cephalopods)',
                  'riskPercent': '50% - 75%',
                  'riskLevel': 'high',
                  'notes': 'Mollusks share homologous tropomyosin peptide chains'},
                 {'name': 'Clams, Mussels, Snails, Oysters (Bivalves/Gastropods)',
                  'riskPercent': '40% - 65%',
                  'riskLevel': 'high',
                  'notes': 'Marine mollusk group with high tropomyosin homology'}]}]


def get_all_cross_reactivity_rules() -> list[dict]:
    return CROSS_REACTIVITY_RULES


def detect_cross_reactivities(
    user_allergies: list[str],
    custom_allergens: list[str] | None = None,
    ingredients_text: str = "",
    ingredients_list: list[str] | None = None,
    declared_allergens: list[str] | None = None,
) -> list[dict]:
    alerts: list[dict] = []
    full_text = (ingredients_text + " " + " ".join(ingredients_list or []) + " " + " ".join(declared_allergens or [])).lower()
    all_user_allergies = list(user_allergies or []) + [c.lower() for c in (custom_allergens or [])]

    for rule in CROSS_REACTIVITY_RULES:
        # TS: a === rule.sourceKey || a.includes(rule.sourceKey) || rule.sourceName.toLowerCase().includes(a)
        has_source_allergy = any(
            (a == rule["sourceKey"]) or (rule["sourceKey"] in a) or (bool(a) and a in rule["sourceName"].lower())
            for a in all_user_allergies
        )

        if has_source_allergy:
            for item in rule["crossItems"]:
                item_keywords = [w for w in re.split(r"[\s\(\)/\u2194]+", item["name"].lower()) if len(w) > 2]
                is_present = False
                for kw in item_keywords:
                    if kw in ("and", "notes", "milk", "seed"):
                        continue
                    if re.search(rf"\b{re.escape(kw)}\b", full_text):
                        is_present = True
                        break
                if is_present:
                    alerts.append(
                        {
                            "primaryAllergen": rule["sourceName"],
                            "triggerItem": item["name"],
                            "syndromeName": rule["syndromeName"],
                            "clinicalCrossRisk": item["riskLevel"],
                            "riskPercentageRange": item["riskPercent"],
                            "mechanismExplanation": rule["mechanism"],
                            "scientificProteinFamily": rule["proteinFamily"],
                            "clinicalAdvice": item["notes"],
                            "cookingEffect": rule["cookingEffect"],
                        }
                    )
    return alerts

_PLANT_BIOACTIVE = re.compile(
    r"extract|water|oil|butter|flour|oat|leaf|root|berry|protein|fiber|seed|juice|vitamin|tocopherol|ascorbic|niacinamide|ceramide|hyaluronate|glycerin|zinc",
    re.I,
)

def analyze_ingredient_safety(ingredients: list[str]) -> list[dict]:
    if not ingredients:
        return []

    out: list[dict] = []
    for ing in ingredients:
        clean = ing.strip()
        lower = clean.lower()

        found_match = None
        for key, val in _ALL_HAZARDS.items():
            if key in lower:
                found_match = val
                break

        if found_match:
            out.append(
                {
                    "name": clean,
                    "hazardLevel": found_match["hazard"],
                    "roleDescription": found_match["role"],
                    "regulatoryStatus": found_match["reg"],
                    "healthImpact": found_match["impact"],
                }
            )
            continue

        if _PLANT_BIOACTIVE.search(lower):
            out.append(
                {
                    "name": clean,
                    "hazardLevel": "safe",
                    "roleDescription": "Nourishing / Bioactive Compound",
                    "regulatoryStatus": "Clean Verified (EWG 1-2)",
                    "healthImpact": "Supports metabolic health or skin hydration",
                }
            )
            continue

        out.append(
            {
                "name": clean,
                "hazardLevel": "safe",
                "regulatoryStatus": "Standard GRAS Approval",
                "healthImpact": "No toxicological flags recorded",
            }
        )
    return out


def extract_regulatory_badges(ingredients: list[str]) -> list[dict]:
    badges: list[dict] = []
    if not ingredients:
        return badges

    seen: set[str] = set()
    for ing in ingredients:
        lower = ing.lower().strip()
        for key, val in _ALL_HAZARDS.items():
            if key in lower and val.get("regulatoryBadges"):
                for badge in val["regulatoryBadges"]:
                    badge_key = f"{badge['region']}:{badge['authority']}:{badge['title']}"
                    if badge_key not in seen:
                        seen.add(badge_key)
                        badges.append(badge)
    return badges


async def assess_product_match(product: dict, user_profile: dict) -> dict:
    warnings: list[dict] = []
    safe_highlights: list[str] = []
    full_text = (
        str(product.get("ingredientsText") or "")
        + " "
        + " ".join(product.get("ingredientsList") or [])
        + " "
        + " ".join(product.get("allergens") or [])
    ).lower()
    labels_clean = [l.lower().strip() for l in product.get("labels") or []]

    # 1. ALLERGY MATCHING (Level: High / Danger)
    for allergy_key in list(user_profile.get("allergies") or []):
        allergy_name = str(allergy_key).casefold().strip()
        drug_synonyms = DRUG_ALLERGY_GROUPS.get(allergy_name)
        if drug_synonyms:
            matched_drug = next(
                (
                    synonym
                    for synonym in drug_synonyms
                    if re.search(rf"\b{re.escape(synonym)}\b", full_text)
                ),
                None,
            )
            if matched_drug:
                warnings.append(
                    {
                        "id": f"warn_drug_allergy_{allergy_name}",
                        "level": "high",
                        "category": "allergy",
                        "title": f"Drug Allergy Conflict: {allergy_name.upper()}",
                        "message": (
                            f'This product contains "{matched_drug}", which belongs '
                            f"to the {allergy_name} drug allergy group."
                        ),
                        "matchedItem": matched_drug,
                        "explanation": (
                            "Penicillin-class cross-reactivity can cause serious allergic "
                            "reactions; confirm the product with a clinician or pharmacist."
                        ),
                    }
                )
                continue
        matched_synonym = None
        synonyms = ALLERGEN_SYNONYMS.get(allergy_name) or [allergy_name]

        # Check declared allergens first
        for declared in product.get("allergens") or []:
            dec_clean = declared.lower()
            if any(s in dec_clean or dec_clean in s for s in synonyms):
                matched_synonym = declared
                break

        # Check ingredients list & text
        if not matched_synonym:
            for syn in synonyms:
                if syn and (re.search(rf"\b{re.escape(syn)}\b", full_text) or syn in full_text):
                    matched_synonym = syn
                    break

        if matched_synonym:
            warnings.append(
                {
                    "id": f"warn_allergy_{allergy_key}",
                    "level": "high",
                    "category": "allergy",
                    "title": f"Allergy Conflict: Contains {allergy_key.replace('_', ' ').upper()}",
                    "message": f'This product contains "{matched_synonym}", which directly conflicts with your declared {allergy_key.replace("_", " ")} allergy.',
                    "matchedItem": matched_synonym,
                    "explanation": "Immediate risk of allergic reaction. You have active avoidance configured for this allergen.",
                }
            )

    # Custom user allergens
    for custom in user_profile.get("customAllergens") or []:
        clean_custom = custom.strip().lower()
        if len(clean_custom) > 1 and clean_custom in full_text:
            warnings.append(
                {
                    "id": f"warn_custom_{clean_custom}",
                    "level": "high",
                    "category": "allergy",
                    "title": f'Custom Sensitivity Alert: "{custom}"',
                    "message": f'Found "{custom}" in the product ingredients list.',
                    "matchedItem": custom,
                    "explanation": "Matches your custom-added sensitivity filter.",
                }
            )

    # 2. DIET TYPE MATCHING (Level: Medium / Orange)
    diet = user_profile.get("dietType")
    nutrition = product.get("nutrition") or {}

    def _nut(key, default=0):
        v = nutrition.get(key)
        return default if v is None else v

    if diet == "vegan":
        is_explicit_vegan = any(("vegan" in l) or ("100% plant" in l) for l in labels_clean)
        if is_explicit_vegan:
            safe_highlights.append("Certified Vegan product")
        else:
            non_vegan_found = [item for item in NON_VEGAN_INGREDIENTS if item in full_text]
            if non_vegan_found:
                warnings.append(
                    {
                        "id": "warn_diet_vegan_conflict",
                        "level": "medium",
                        "category": "diet",
                        "title": "Not Suitable for Vegan Diet",
                        "message": f"Contains animal-derived ingredients: {', '.join(non_vegan_found[:3])}.",
                        "matchedItem": non_vegan_found[0],
                        "explanation": "Incompatible with strict vegan lifestyle.",
                    }
                )
            elif product.get("productType") == "food":
                warnings.append(
                    {
                        "id": "warn_diet_vegan_unverified",
                        "level": "low",
                        "category": "diet",
                        "title": "Unverified Vegan Status",
                        "message": "No animal products detected directly, but lacks certified vegan labeling.",
                        "matchedItem": "vegan certification",
                    }
                )
    elif diet == "vegetarian":
        non_veg_found = [item for item in NON_VEGETARIAN_INGREDIENTS if item in full_text]
        if non_veg_found:
            warnings.append(
                {
                    "id": "warn_diet_vegetarian_conflict",
                    "level": "medium",
                    "category": "diet",
                    "title": "Not Suitable for Vegetarian Diet",
                    "message": f"Contains meat or animal derivative: {', '.join(non_veg_found[:3])}.",
                    "matchedItem": non_veg_found[0],
                }
            )
        else:
            safe_highlights.append("Vegetarian friendly formulation")
    elif diet == "halal":
        is_halal_certified = any("halal" in l for l in labels_clean)
        non_halal_found = [item for item in NON_HALAL_INGREDIENTS if item in full_text]
        if non_halal_found:
            warnings.append(
                {
                    "id": "warn_diet_halal_conflict",
                    "level": "high",
                    "category": "diet",
                    "title": "Non-Halal Ingredient Detected",
                    "message": f"Contains restricted ingredient: {', '.join(non_halal_found)}.",
                    "matchedItem": non_halal_found[0],
                }
            )
        elif not is_halal_certified and product.get("productType") == "food":
            safe_highlights.append("No obvious pork or alcohol ingredients found")
    elif diet == "kosher":
        is_kosher_certified = any(("kosher" in l) or ("ou" in l) or ("parve" in l) or ("k" in l) for l in labels_clean)
        non_kosher_found = [item for item in NON_KOSHER_INGREDIENTS if item in full_text]
        if non_kosher_found:
            warnings.append(
                {
                    "id": "warn_diet_kosher_conflict",
                    "level": "high",
                    "category": "diet",
                    "title": "Non-Kosher Ingredient Detected",
                    "message": f"Contains restricted ingredient: {', '.join(non_kosher_found)}.",
                    "matchedItem": non_kosher_found[0],
                }
            )
        elif is_kosher_certified:
            safe_highlights.append("Kosher certified")
    elif diet == "keto":
        carbs = _nut("carbohydrates", 0) or 0
        sugars = _nut("sugars", 0) or 0
        if carbs > 15 or sugars > 5:
            warnings.append(
                {
                    "id": "warn_diet_keto",
                    "level": "medium",
                    "category": "nutrition",
                    "title": "High Carb Content for Ketogenic Diet",
                    "message": f"Contains {carbs}g total carbs ({sugars}g sugar) per 100g, exceeding typical strict keto limits.",
                    "matchedItem": f"{carbs}g carbs",
                }
            )
        elif nutrition:
            safe_highlights.append("Low carb profile compatible with Keto")
    elif diet in ("diabetic", "low_sugar"):
        sugars = _nut("sugars", 0) or 0
        has_high_fructose = ("high fructose" in full_text) or ("glucose syrup" in full_text) or ("corn syrup" in full_text)
        if sugars > 12 or has_high_fructose:
            warnings.append(
                {
                    "id": "warn_diabetic_sugar",
                    "level": "medium",
                    "category": "nutrition",
                    "title": "Elevated Sugar / High-Glycemic Index",
                    "message": f"Contains {(str(sugars) + 'g sugar/100g') if sugars > 0 else 'high-glycemic syrups'} which can trigger rapid blood glucose spikes.",
                    "matchedItem": "High Fructose Corn Syrup" if has_high_fructose else f"{sugars}g Sugar",
                }
            )
        elif nutrition and sugars <= 4:
            safe_highlights.append("Low sugar formulation (<4g/100g)")
    elif diet == "gluten_free":
        is_gf_cert = any(("gluten-free" in l) or ("sans gluten" in l) for l in labels_clean)
        gluten_synonyms = ALLERGEN_SYNONYMS["gluten"]
        has_gluten = any(s in full_text for s in gluten_synonyms)
        if has_gluten:
            warnings.append(
                {
                    "id": "warn_gluten_free_diet",
                    "level": "high",
                    "category": "diet",
                    "title": "Contains Gluten Grain",
                    "message": "Product contains wheat, barley, rye or gluten ingredients.",
                    "matchedItem": "Gluten",
                }
            )
        elif is_gf_cert:
            safe_highlights.append("Certified Gluten-Free")

    # 3. SPECIAL CONDITIONS
    conditions = user_profile.get("specialConditions") or []
    cosmetic = product.get("cosmetic") or {}

    if ("pregnant" in conditions) or ("nursing" in conditions):
        for p_risk in PREGNANCY_RISK_INGREDIENTS:
            if p_risk["name"] in full_text:
                warnings.append(
                    {
                        "id": f"warn_pregnancy_{p_risk['name']}",
                        "level": p_risk["risk"],
                        "category": "condition",
                        "title": f"Pregnancy Caution: {p_risk['name'].upper()}",
                        "message": p_risk["reason"],
                        "matchedItem": p_risk["name"],
                        "explanation": "Obstetric & dermatological guidelines advise avoiding or restricting this substance during pregnancy/lactation.",
                    }
                )

    if ("sensitive_skin" in conditions) or ("eczema" in conditions):
        if cosmetic.get("hasFragrance") or ("fragrance" in full_text) or ("parfum" in full_text):
            warnings.append(
                {
                    "id": "warn_sensitive_fragrance",
                    "level": "medium",
                    "category": "condition",
                    "title": "Sensitizing Fragrance / Parfum Detected",
                    "message": "Contains synthetic perfumes or fragrance allergens that frequently trigger eczema flare-ups and contact dermatitis.",
                    "matchedItem": "Fragrance / Parfum",
                }
            )
        if cosmetic.get("hasAlcohol") or ("alcohol denat" in full_text):
            warnings.append(
                {
                    "id": "warn_sensitive_alcohol",
                    "level": "medium",
                    "category": "condition",
                    "title": "Drying Denatured Alcohol",
                    "message": "Drying alcohols disrupt the skin lipid barrier in sensitive and eczema-prone skin.",
                    "matchedItem": "Alcohol Denat",
                }
            )

    if ("hypertension" in conditions) or diet == "low_sodium":
        sodium = nutrition.get("sodium")
        if sodium is None and nutrition.get("salt"):
            sodium = nutrition["salt"] * 400
        sodium = sodium or 0
        if sodium > 500:
            warnings.append(
                {
                    "id": "warn_hypertension_sodium",
                    "level": "medium",
                    "category": "nutrition",
                    "title": "High Sodium Warning for Hypertension",
                    "message": f"Contains approx {round(sodium)}mg sodium per 100g (over 25% of daily recommended allowance).",
                    "matchedItem": f"{round(sodium)}mg Sodium",
                }
            )

    if ("acne_prone" in conditions) and product.get("cosmetic"):
        if (cosmetic.get("comedogenicRating") or 0) >= 4:
            warnings.append(
                {
                    "id": "warn_acne_comedogenic",
                    "level": "low",
                    "category": "condition",
                    "title": "High Comedogenic Potential (Rating 4-5/5)",
                    "message": "Contains ingredients with high probability of clogging pores for acne-prone skin types.",
                    "matchedItem": "Pore-clogging lipids",
                }
            )

    # 4. NOVA ULTRA-PROCESSED / NUTRITION GENERAL CHECK
    if nutrition.get("novaGroup") == 4:
        warnings.append(
            {
                "id": "warn_nova_group_4",
                "level": "low",
                "category": "nutrition",
                "title": "NOVA Group 4: Ultra-Processed Food",
                "message": "Formulated with industrial ingredients, emulsifiers, and flavor enhancers.",
                "matchedItem": "Ultra-processed food",
            }
        )

    # 5. CROSS-REACTIVITY ALLERGY MATRIX CHECK
    cross_alerts = detect_cross_reactivities(
        user_profile.get("allergies") or [],
        user_profile.get("customAllergens"),
        str(product.get("ingredientsText") or ""),
        product.get("ingredientsList") or [],
        product.get("allergens") or [],
    )

    for cross_alert in cross_alerts:
        slug = re.sub(r"[^a-z0-9]", "_", cross_alert["triggerItem"].lower())
        warnings.append(
            {
                "id": f"warn_cross_allergy_{slug}",
                "level": "high" if cross_alert["clinicalCrossRisk"] == "very_high" else "medium",
                "category": "allergy",
                "title": f"Biological Cross-Reactivity ({cross_alert['riskPercentageRange']}): {cross_alert['triggerItem']}",
                "message": f"{cross_alert['syndromeName']} - Due to sensitization to {cross_alert['primaryAllergen']}. Homologous {cross_alert['scientificProteinFamily']} protein structures may trigger cross-reactive immune responses.",
                "matchedItem": cross_alert["triggerItem"],
                "explanation": f"{cross_alert['clinicalAdvice']}. {cross_alert.get('cookingEffect') or ''}",
            }
        )

    # 6. COSMECEUTICAL ACTIVE & ROUTINE CONFLICT CHECK (For cosmetics)
    skincare_active_check = None
    if product.get("productType") == "cosmetic":
        actives_found = extract_skincare_actives(str(product.get("ingredientsText") or ""), product.get("ingredientsList") or [])
        if actives_found:
            current_routine = get_user_db().get_routine()
            skincare_active_check = analyze_skincare_routine_conflicts(current_routine, actives_found)

            for conflict in skincare_active_check["conflicts"]:
                slug = re.sub(r"[^a-z0-9]", "_", conflict["ruleTitle"].lower())
                warnings.append(
                    {
                        "id": f"warn_skincare_conflict_{slug}",
                        "level": "medium" if conflict["severity"] == "high" else "low",
                        "category": "condition",
                        "title": f"Active Skincare Conflict: {conflict['ruleTitle']}",
                        "message": f"{conflict['riskDescription']} ({conflict['activeA']} vs {conflict['activeB']})",
                        "matchedItem": conflict["activeA"],
                        "explanation": f"{conflict['solutionRecommendation']} Timing Guide: {conflict['timingGuide']}",
                    }
                )

            for syn in skincare_active_check["synergies"]:
                safe_highlights.append(f"Synergistic Pairing: {syn['ruleTitle']}")

    # Fetch PubMed research evidence for high and medium severity flags
    import asyncio as _asyncio

    for warning in warnings:
        if warning["level"] in ("high", "medium"):
            try:
                query_term = warning.get("matchedItem") or warning["title"]
                warning["research"] = await get_pubmed_research(query_term, warning["category"])
            except Exception as err:
                print("Could not fetch PubMed research for warning:", err)

    # Calculate Personal Fit Score (0 - 100)
    score = 100
    high_count = sum(1 for w in warnings if w["level"] == "high")
    med_count = sum(1 for w in warnings if w["level"] == "medium")
    low_count = sum(1 for w in warnings if w["level"] == "low")

    score -= high_count * 45
    score -= med_count * 20
    score -= low_count * 5
    score = max(0, min(100, score))

    status = "safe"
    summary = "Excellent match for your personal profile with zero flagged allergens or restrictions."

    if high_count > 0:
        status = "danger"
        summary = f"Direct Conflict Detected: Contains {high_count} high-risk allergen(s) or contraindication(s) matching your profile."
    elif med_count > 0:
        status = "warning"
        summary = f"Caution Advised: {med_count} dietary or health condition restriction(s) flagged."
    elif low_count > 0:
        status = "caution"
        summary = f"Minor Notes: Formulated safely, but contains {low_count} item(s) you may want to note."

    if len(safe_highlights) == 0 and status == "safe":
        safe_highlights.append("No declared allergens matching your profile")
        safe_highlights.append(f"Compatible with {user_profile.get('dietType')} diet")

    return {
        "status": status,
        "score": score,
        "summary": summary,
        "warnings": warnings,
        "safeHighlights": safe_highlights,
        "crossReactivityAlerts": cross_alerts,
        "skincareActiveCheck": skincare_active_check,
    }

import { DemoProductItem } from './demoData';
import { SupportedCountry } from '../src/types';

export interface SupermarketStore {
  id: string;
  name: string;
  country: SupportedCountry | 'GLOBAL';
  logoBadge: string;
  accentColor: string;
  categories: string[];
  description: string;
}

export const SUPERMARKET_STORES: SupermarketStore[] = [
  // 🇺🇸 US
  {
    id: 'traderjoes',
    name: "Trader Joe's",
    country: 'US',
    logoBadge: 'TJ',
    accentColor: '#ea580c',
    categories: ['Clean Snacks', 'Plant Milk & Dairy', 'Dips & Spreads', 'Organic Pantry'],
    description: 'Iconic clean-label grocery known for preservative-free snacks, organic staples, and specialty diet options.'
  },
  {
    id: 'wholefoods',
    name: 'Whole Foods Market',
    country: 'US',
    logoBadge: 'WFM',
    accentColor: '#006747',
    categories: ['USDA Organic', 'Clean Meat & Seafood', 'Superfoods & Supplements', 'Body Care'],
    description: 'Gold-standard organic grocer banning 300+ artificial preservatives, hydrogenated fats and high-fructose corn syrup.'
  },
  {
    id: 'costco_us',
    name: 'Costco Wholesale (Kirkland)',
    country: 'US',
    logoBadge: 'COSTCO',
    accentColor: '#2563eb',
    categories: ['Bulk Pantry', 'Kirkland Signature', 'Organic Nuts', 'Vitamins & Supplements'],
    description: 'Leading US bulk retailer with high-grade Kirkland Signature organic staples and family essentials.'
  },

  // 🇬🇧 UK
  {
    id: 'tesco',
    name: 'Tesco (UK)',
    country: 'UK',
    logoBadge: 'TESCO',
    accentColor: '#00539f',
    categories: ['Tesco Finest', 'Plant Chef', 'Fresh & Dairy', 'Free From Gluten'],
    description: 'UK’s leading supermarket with comprehensive FSA traffic light nutritional labeling and Free-From allergens ranges.'
  },
  {
    id: 'sainsburys',
    name: "Sainsbury's & M&S",
    country: 'UK',
    logoBadge: 'JS',
    accentColor: '#d66a00',
    categories: ['Taste the Difference', 'Organic Groceries', 'Dairy & Bakery', 'Healthy Ready Meals'],
    description: 'Premium British supermarket offering clean ingredient standards and certified sustainable sourcing.'
  },
  {
    id: 'boots_uk',
    name: 'Boots Pharmacy',
    country: 'UK',
    logoBadge: 'BOOTS',
    accentColor: '#002f6c',
    categories: ['Dermocosmetics', 'Vitamins & Supplements', 'Sensitive Skincare', 'Sun Protection'],
    description: 'The United Kingdom’s flagship health and beauty pharmacy retailer.'
  },

  // 🇫🇷 FR
  {
    id: 'carrefour_fr',
    name: 'Carrefour Bio & Hyper',
    country: 'FR',
    logoBadge: 'CRF',
    accentColor: '#004e9a',
    categories: ['Carrefour BIO (AB)', 'Produits Laitiers & Fromages', 'Épicerie Fine', 'Sans Gluten'],
    description: 'Leader de la grande distribution en France, pionnier du Nutri-Score et de l’agriculture biologique (Label AB).'
  },
  {
    id: 'monoprix_fr',
    name: 'Monoprix Gourmet',
    country: 'FR',
    logoBadge: 'MPX',
    accentColor: '#e30613',
    categories: ['Monoprix Gourmet', 'Cosmétiques Propres', 'Bio & Diététique', 'Snacks Sains'],
    description: 'Enseigne urbaine française haut de gamme privilégiant les produits sans additifs controversés et cosmétiques certifiés Cosmébio.'
  },

  // 🇩🇪 DE
  {
    id: 'rewe_de',
    name: 'REWE Bio & Edeka',
    country: 'DE',
    logoBadge: 'REWE',
    accentColor: '#cc0000',
    categories: ['REWE Bio (Bioland/Demeter)', 'Vegane Produkte', 'Molkerei & Käse', 'Glutenfrei'],
    description: 'Führende deutsche Supermarktkette mit strengen Bio-Standards (Bioland, Demeter) und Nutri-Score Transparenz.'
  },
  {
    id: 'dm_drogerie',
    name: 'dm-drogerie markt (Balea / Alverde)',
    country: 'DE',
    logoBadge: 'dm',
    accentColor: '#7b1fa2',
    categories: ['Naturkosmetik (Alverde)', 'Dermokosmetik (Balea Med)', 'dmBio Lebensmittel', 'Nahrungsergänzung'],
    description: 'Europas beliebtester Drogeriemarkt für zertifizierte Naturkosmetik und saubere Nahrungsergänzungsmittel.'
  },

  // 🇮🇹 IT
  {
    id: 'conad_it',
    name: 'Conad Sapori & Dintorni',
    country: 'IT',
    logoBadge: 'CONAD',
    accentColor: '#e20613',
    categories: ['Sapori & Dintorni (DOP/IGP)', 'Verso Natura Bio', 'Pasta & Cereali', 'Latticini'],
    description: 'Rete leader italiana per eccellenze enogastronomiche, filiera controllata e linea biologica certificata.'
  },
  {
    id: 'coop_italia',
    name: 'Coop Italia (Vivi Verde)',
    country: 'IT',
    logoBadge: 'COOP.IT',
    accentColor: '#d32f2f',
    categories: ['Vivi Verde Bio', 'Bene.sì Salute', 'Olio & Condimenti', 'Cura Persona'],
    description: 'Cooperativa storica italiana all’avanguardia nell’eliminazione di olio di palma e pesticidi controversi.'
  },

  // 🇪🇸 ES
  {
    id: 'mercadona_es',
    name: 'Mercadona (Hacendado / Deliplus)',
    country: 'ES',
    logoBadge: 'MCD',
    accentColor: '#008744',
    categories: ['Hacendado Sin Gluten', 'Deliplus Dermocosmética', 'Lácteos & Proteínas', 'Frutos Secos'],
    description: 'Cadena líder en España famosa por su estricto etiquetado de alérgenos y productos saludables Hacendado.'
  }
];

export interface MarketProductItem extends DemoProductItem {
  storeId: string;
  country: SupportedCountry | 'GLOBAL';
  priceUsd?: number;
  priceEur?: number;
  priceGbp?: number;
  safetyTier: 'clean' | 'caution' | 'high_risk';
  familyCompatibilityScore: number;
  highlightTag: string;
}

export const MARKET_PRODUCTS: MarketProductItem[] = [
  // 🇺🇸 US - Trader Joe's & Whole Foods
  {
    barcode: '0098421004123',
    name: "Trader Joe's Organic Creamy Peanut Butter (Valencia)",
    brand: "Trader Joe's",
    type: 'food',
    category: 'Dips & Spreads',
    storeId: 'traderjoes',
    country: 'US',
    image: 'https://images.unsplash.com/photo-1590080875515-8a3a8dc5735e?w=400&auto=format&fit=crop&q=80',
    ingredientsText: 'Organic dry roasted Valencia peanuts, sea salt.',
    ingredientsList: ['Organic Dry Roasted Valencia Peanuts', 'Sea Salt'],
    allergens: ['peanut'],
    labels: ['USDA Organic', 'Non-GMO', 'No Added Sugar', 'Gluten-Free', 'Kosher'],
    safetyTier: 'clean',
    familyCompatibilityScore: 96,
    highlightTag: '100% Organic • Zero Palm Oil',
    priceUsd: 3.49,
    nutrition: {
      energyKcal: 590,
      sugars: 3.2,
      fat: 50.0,
      saturatedFat: 6.8,
      proteins: 26.0,
      carbohydrates: 18.0,
      fiber: 8.0,
      salt: 0.35,
      sodium: 0.14,
      novaGroup: 1,
      nutriscoreGrade: 'a',
      ecoscoreGrade: 'a'
    }
  },
  {
    barcode: '0099482431201',
    name: '365 Whole Foods Organic Almondmilk Unsweetened',
    brand: '365 by Whole Foods Market',
    type: 'food',
    category: 'Plant Milk & Dairy',
    storeId: 'wholefoods',
    country: 'US',
    image: 'https://images.unsplash.com/photo-1563636619-e9143da7973b?w=400&auto=format&fit=crop&q=80',
    ingredientsText: 'Organic almondmilk (filtered water, organic almonds), calcium carbonate, sea salt, potassium citrate, organic locust bean gum, gellan gum, vitamin A palmitate, ergocalciferol (vitamin D2), d-alpha tocopherol (vitamin E).',
    ingredientsList: ['Filtered Water', 'Organic Almonds', 'Calcium Carbonate', 'Sea Salt', 'Potassium Citrate', 'Organic Locust Bean Gum', 'Gellan Gum', 'Vitamin A', 'Vitamin D2', 'Vitamin E'],
    allergens: ['tree_nut'],
    labels: ['USDA Organic', 'Vegan', 'Non-GMO Project Verified', 'Dairy-Free', 'No Carrageenan'],
    safetyTier: 'clean',
    familyCompatibilityScore: 94,
    highlightTag: 'No Added Sugar • Carrageenan-Free',
    priceUsd: 2.99,
    nutrition: {
      energyKcal: 30,
      sugars: 0.0,
      fat: 2.5,
      saturatedFat: 0.2,
      proteins: 1.0,
      carbohydrates: 1.0,
      fiber: 1.0,
      salt: 0.4,
      sodium: 0.16,
      novaGroup: 3,
      nutriscoreGrade: 'b',
      ecoscoreGrade: 'b'
    }
  },

  // 🇬🇧 UK - Tesco & Boots
  {
    barcode: '5057753901234',
    name: 'Tesco Free From Gluten & Wheat Seeded Bread',
    brand: 'Tesco Free From',
    type: 'food',
    category: 'Free From Gluten',
    storeId: 'tesco',
    country: 'UK',
    image: 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400&auto=format&fit=crop&q=80',
    ingredientsText: 'Water, tapioca starch, rice flour, mixed seeds (11%) (sunflower seeds, brown linseed, golden linseed, poppy seeds), potato starch, bamboo fiber, rapeseed oil, yeast, psyllium husk powder, egg white powder, salt, hydroxypropyl methyl cellulose.',
    ingredientsList: ['Water', 'Tapioca Starch', 'Rice Flour', 'Sunflower Seeds', 'Linseed', 'Poppy Seeds', 'Potato Starch', 'Bamboo Fiber', 'Rapeseed Oil', 'Yeast', 'Psyllium Husk', 'Egg White Powder', 'Salt', 'HPMC (E464)'],
    allergens: ['egg'],
    labels: ['Gluten-Free Certified', 'High Fiber', 'Dairy-Free', 'Vegetarian'],
    safetyTier: 'clean',
    familyCompatibilityScore: 91,
    highlightTag: 'Celiac Safe • UK FSA Green Traffic Light',
    priceGbp: 1.95,
    nutrition: {
      energyKcal: 245,
      sugars: 1.8,
      fat: 7.2,
      saturatedFat: 0.8,
      proteins: 5.5,
      carbohydrates: 36.0,
      fiber: 9.1,
      salt: 0.85,
      sodium: 0.34,
      novaGroup: 3,
      nutriscoreGrade: 'b',
      ecoscoreGrade: 'b',
      ukTrafficLight: {
        fatLevel: 'med',
        satFatLevel: 'low',
        sugarsLevel: 'low',
        saltLevel: 'med'
      }
    }
  },

  // 🇫🇷 FR - Carrefour Bio & Monoprix
  {
    barcode: '3560070548123',
    name: 'Carrefour Bio Flocons d’Avoine Complète Sans Gluten',
    brand: 'Carrefour BIO',
    type: 'food',
    category: 'Carrefour BIO (AB)',
    storeId: 'carrefour_fr',
    country: 'FR',
    image: 'https://images.unsplash.com/photo-1586495777744-4413f21062fa?w=400&auto=format&fit=crop&q=80',
    ingredientsText: 'Flocons d’avoine complète issus de l’agriculture biologique française 100%.',
    ingredientsList: ['Avoine Complète Biologique (100%)'],
    allergens: [],
    labels: ['Agriculture Biologique (AB)', 'Certifié Bio Europe', 'Nutri-Score A', 'Sans Sucres Ajoutés', 'Riche en Fibres'],
    safetyTier: 'clean',
    familyCompatibilityScore: 98,
    highlightTag: 'Nutri-Score A • Éco-Score A • Label AB',
    priceEur: 1.85,
    nutrition: {
      energyKcal: 368,
      sugars: 1.0,
      fat: 7.0,
      saturatedFat: 1.2,
      proteins: 13.5,
      carbohydrates: 58.7,
      fiber: 10.0,
      salt: 0.02,
      sodium: 0.01,
      novaGroup: 1,
      nutriscoreGrade: 'a',
      ecoscoreGrade: 'a'
    }
  },
  {
    barcode: '3337875597123',
    name: 'La Roche-Posay Toleriane Dermallergo Crème Apaisante',
    brand: 'La Roche-Posay',
    type: 'cosmetic',
    category: 'Cosmétiques Propres',
    storeId: 'monoprix_fr',
    country: 'FR',
    image: 'https://images.unsplash.com/photo-1556228720-195a672e8a03?w=400&auto=format&fit=crop&q=80',
    ingredientsText: 'Aqua/Water, Isocetyl Stearate, Squalane, Butyrospermum Parkii Butter / Shea Butter, Dimethicone, Glycerin, Aluminum Starch Octenylsuccinate, Pentylene Glycol, PEG-100 Stearate, Glyceryl Stearate, Cetyl Alcohol, Sphingobioma, Neurosensine.',
    ingredientsList: ['Eau Thermale La Roche-Posay', 'Squalan Végétal', 'Beurre de Karité Bio', 'Glycérine', 'Sphingobioma (Probiotique)', 'Neurosensine'],
    allergens: [],
    labels: ['Sans Parfum', 'Sans Conservateur', 'Sans Alcool', 'Hypoallergénique', 'Emballage Ultra-Hermétique'],
    safetyTier: 'clean',
    familyCompatibilityScore: 98,
    highlightTag: '0% Parfum • Brevet Sphingobioma',
    priceEur: 19.50,
    cosmetic: {
      category: 'Soins Visage Peaux Réactives',
      comedogenicRating: 1,
      hasFragrance: false,
      hasParabens: false,
      hasSulfates: false,
      hasAlcohol: false,
      safetySummary: 'Formule dermatologique ultra-épurée testée sur peaux allergiques selon les directives ANSM/EU.'
    }
  },

  // 🇩🇪 DE - REWE Bio & dm-drogerie
  {
    barcode: '4388844051234',
    name: 'REWE Bio Reine Buttermilch (Bioland)',
    brand: 'REWE Bio',
    type: 'food',
    category: 'REWE Bio (Bioland/Demeter)',
    storeId: 'rewe_de',
    country: 'DE',
    image: 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400&auto=format&fit=crop&q=80',
    ingredientsText: 'Reine Bio-Buttermilch aus deutscher Bioland-Landwirtschaft.',
    ingredientsList: ['Reine Buttermilch (Bioland zertifiziert)'],
    allergens: ['milk'],
    labels: ['Bioland Zertifiziert', 'Nutri-Score A', 'Deutsches Bio-Siegel', 'Ohne Gentechnik'],
    safetyTier: 'clean',
    familyCompatibilityScore: 95,
    highlightTag: 'Bioland Qualität • Fettarm',
    priceEur: 0.99,
    nutrition: {
      energyKcal: 38,
      sugars: 4.2,
      fat: 0.5,
      saturatedFat: 0.3,
      proteins: 3.4,
      carbohydrates: 4.2,
      fiber: 0.0,
      salt: 0.13,
      sodium: 0.05,
      novaGroup: 1,
      nutriscoreGrade: 'a',
      ecoscoreGrade: 'a'
    }
  },
  {
    barcode: '4058172931234',
    name: 'Balea Med Ultra Sensitive Totes Meer Barriere-Creme',
    brand: 'dm Balea Med',
    type: 'cosmetic',
    category: 'Dermokosmetik (Balea Med)',
    storeId: 'dm_drogerie',
    country: 'DE',
    image: 'https://images.unsplash.com/photo-1608248597359-009161a07bb5?w=400&auto=format&fit=crop&q=80',
    ingredientsText: 'Aqua, Glycerin, Caprylic/Capric Triglyceride, Maris Sal (Totes Meer Salz), Panthenol, Ceramide NP, Tocopherol, Allantoin.',
    ingredientsList: ['Aqua', 'Glycerin', 'Panthenol (Pro-Vitamin B5)', 'Totes Meer Salz', 'Ceramide NP', 'Allantoin', 'Vitamin E'],
    allergens: [],
    labels: ['Deutscher Allergie- und Asthmabund (DAAB)', 'Mikroplastikfrei', 'Ohne Parfum', 'Vegan'],
    safetyTier: 'clean',
    familyCompatibilityScore: 97,
    highlightTag: 'DAAB Geprüft • Mit Ceramiden & B5',
    priceEur: 3.95,
    cosmetic: {
      category: 'Medizinische Hautpflege',
      comedogenicRating: 0,
      hasFragrance: false,
      hasParabens: false,
      hasSulfates: false,
      hasAlcohol: false,
      safetySummary: 'DAAB-geprüft für hochsensible und zu Neurodermitis neigende Haut.'
    }
  },

  // 🇮🇹 IT - Conad & Coop Italia
  {
    barcode: '8003170061234',
    name: 'Conad Verso Natura Bio Passata di Pomodoro 100% Italiano',
    brand: 'Conad Verso Natura Bio',
    type: 'food',
    category: 'Verso Natura Bio',
    storeId: 'conad_it',
    country: 'IT',
    image: 'https://images.unsplash.com/photo-1592924357228-91a4daadcfea?w=400&auto=format&fit=crop&q=80',
    ingredientsText: 'Pomodoro biologico coltivato in Italia 99.5%, sale marino 0.5%.',
    ingredientsList: ['Pomodoro Biologico 100% Italiano', 'Sale Marino'],
    allergens: [],
    labels: ['Biologico UE', '100% Pomodoro Italiano', 'Nutri-Score A', 'Senza Conservanti', 'Senza Glutine'],
    safetyTier: 'clean',
    familyCompatibilityScore: 97,
    highlightTag: '100% Bio Italiano • Nutri-Score A',
    priceEur: 1.29,
    nutrition: {
      energyKcal: 25,
      sugars: 3.8,
      fat: 0.2,
      saturatedFat: 0.05,
      proteins: 1.3,
      carbohydrates: 4.1,
      fiber: 1.4,
      salt: 0.5,
      sodium: 0.2,
      novaGroup: 1,
      nutriscoreGrade: 'a',
      ecoscoreGrade: 'a'
    }
  },

  // 🇪🇸 ES - Mercadona
  {
    barcode: '8480000151234',
    name: 'Hacendado Gazpacho Tradicional Fresco Sin Gluten',
    brand: 'Hacendado',
    type: 'food',
    category: 'Hacendado Sin Gluten',
    storeId: 'mercadona_es',
    country: 'ES',
    image: 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=400&auto=format&fit=crop&q=80',
    ingredientsText: 'Hortalizas frescas (93%) (tomate, pimiento, pepino, cebolla), aceite de oliva virgen extra (2.6%), vinagre de jerez reserva, sal, ajo.',
    ingredientsList: ['Tomate Fresco', 'Pimiento', 'Pepino', 'Cebolla', 'Aceite de Oliva Virgen Extra (AOVE)', 'Vinagre de Jerez', 'Sal', 'Ajo'],
    allergens: [],
    labels: ['Sin Gluten', '100% Natural', 'Con AOVE', 'Nutri-Score A', 'Dieta Mediterránea'],
    safetyTier: 'clean',
    familyCompatibilityScore: 98,
    highlightTag: 'Nutri-Score A • 100% Natural con AOVE',
    priceEur: 1.70,
    nutrition: {
      energyKcal: 44,
      sugars: 2.1,
      fat: 2.7,
      saturatedFat: 0.4,
      proteins: 0.8,
      carbohydrates: 3.6,
      fiber: 1.1,
      salt: 0.78,
      sodium: 0.31,
      novaGroup: 1,
      nutriscoreGrade: 'a',
      ecoscoreGrade: 'a'
    }
  }
];

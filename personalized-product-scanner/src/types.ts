export type SupportedCountry = 'US' | 'UK' | 'FR' | 'DE' | 'IT' | 'ES';
export type SupportedLanguage = 'en' | 'fr' | 'de' | 'it' | 'es';

export type AllergenKey =
  | 'peanut'
  | 'tree_nut'
  | 'milk'
  | 'gluten'
  | 'egg'
  | 'soy'
  | 'fish'
  | 'shellfish'
  | 'sesame'
  | 'sulfite'
  | 'mustard'
  | 'celery'
  | 'lupin'
  | 'mollusc'
  | 'fragrance'
  | 'parabens'
  | 'sulfates'
  | 'alcohol'
  | 'essential_oils'
  | 'retinoid'
  | 'salicylic_acid';

export type DietType =
  | 'omnivore'
  | 'vegan'
  | 'vegetarian'
  | 'keto'
  | 'halal'
  | 'kosher'
  | 'diabetic'
  | 'low_sugar'
  | 'paleo'
  | 'gluten_free'
  | 'low_sodium';

export type SpecialCondition =
  | 'pregnant'
  | 'nursing'
  | 'sensitive_skin'
  | 'eczema'
  | 'hypertension'
  | 'acne_prone';

export interface UserProfile {
  id?: string;
  name?: string;
  role?: string; // 'Self' | 'Child' | 'Partner' | 'Parent'
  avatarColor?: string;
  country?: SupportedCountry;
  language?: SupportedLanguage;
  allergies: string[];
  customAllergens: string[];
  medications?: string[];
  age?: number;
  gender?: 'male' | 'female' | 'other';
  pregnancyStatus?: 'not_applicable' | 'trying_to_conceive' | 'pregnant' | 'breastfeeding';
  kidneyFunction?: 'normal' | 'mild_impairment' | 'moderate_impairment' | 'severe_impairment';
  liverFunction?: 'normal' | 'mild_impairment' | 'moderate_impairment' | 'severe_impairment';
  dietType: DietType;
  specialConditions: SpecialCondition[];
  updatedAt?: string;
}

export interface FamilyProfile {
  id: string;
  name: string;
  role: string;
  avatarColor: string;
  country?: SupportedCountry;
  allergies: string[];
  customAllergens: string[];
  medications?: string[];
  age?: number;
  gender?: 'male' | 'female' | 'other';
  pregnancyStatus?: 'not_applicable' | 'trying_to_conceive' | 'pregnant' | 'breastfeeding';
  kidneyFunction?: 'normal' | 'mild_impairment' | 'moderate_impairment' | 'severe_impairment';
  liverFunction?: 'normal' | 'mild_impairment' | 'moderate_impairment' | 'severe_impairment';
  dietType: DietType;
  specialConditions: SpecialCondition[];
}

export interface SafeSwapRecommendation {
  id: string;
  name: string;
  brand: string;
  productType: 'food' | 'cosmetic';
  category: string;
  score: number; // 0-100
  imageUrl?: string;
  whyBetter: string[];
  keyBenefits: string[];
  cleanHighlights: string[];
  priceRange?: string;
  certificationBadges?: string[];
  activeIngredients?: string[]; // used for MedMatch interaction verification
  medMatchVerification?: {
    verified: boolean; // engine reachable and analysis ran
    majorCount: number;
    moderateCount: number;
    minorCount: number;
    clean: boolean; // no major interactions with the user's medications
  };
}

export interface IngredientSafetyItem {
  name: string;
  hazardLevel: 'safe' | 'caution' | 'danger'; // Green, Yellow, Red
  roleDescription: string; // e.g. "Natural Emulsifier", "Synthetic Preservative", "Endocrine Disruptor Risk"
  regulatoryStatus?: string; // e.g. "EU Restricted", "FDA GRAS", "EWG Score 1"
  healthImpact?: string;
}

export interface PubMedCitation {
  id: string;
  title: string;
  journal?: string;
  year?: string;
  url: string;
  snippet?: string;
}

export interface ResearchData {
  ingredient: string;
  studyCount: number;
  citations: PubMedCitation[];
  summaryNote?: string;
}

export interface MatchWarning {
  id: string;
  level: 'high' | 'medium' | 'low' | 'info';
  category: 'allergy' | 'diet' | 'condition' | 'ingredient' | 'nutrition';
  title: string;
  message: string;
  matchedItem: string;
  explanation?: string;
  research?: ResearchData;
}

export interface UkTrafficLight {
  fatLevel?: 'low' | 'med' | 'high';
  satFatLevel?: 'low' | 'med' | 'high';
  sugarsLevel?: 'low' | 'med' | 'high';
  saltLevel?: 'low' | 'med' | 'high';
}

export interface RegulatoryStatusBadge {
  region: 'EU' | 'US' | 'UK' | 'FR' | 'DE' | 'IT' | 'ES' | 'GLOBAL';
  authority: string; // e.g. "EFSA", "FDA", "ANSM", "FSA", "Prop 65"
  statusType: 'banned' | 'restricted' | 'warning_label' | 'approved_gras';
  title: string;
  detail: string;
}

export interface CleanScoreBreakdown {
  totalScore: number; // 0-100 (Yuka-style overall score)
  cleanScore?: number; // alias
  nutritionalQualityScore: number; // 60% weight (Nutri-Score based)
  nutritionPoints?: number; // alias
  additivesSafetyScore: number; // 30% weight (EFSA & FDA toxicological deconstruction)
  additivesPoints?: number; // alias
  organicBioBonus: number; // 10% weight (EU Bio, USDA Organic, AB France)
  ratingLevel: 'excellent' | 'good' | 'mediocre' | 'bad';
}

export interface DetectedHerbDrugAlert {
  herbName: string;
  drugOrClass: string;
  severity: 'contraindicated' | 'major' | 'moderate' | 'minor';
  mechanism: string;
  clinicalImpact: string;
  managementAdvice: string;
  evidenceTier: string;
  source: string;
}

export interface NutritionFacts {
  energyKcal?: number;
  sugars?: number;
  salt?: number;
  sodium?: number;
  fat?: number;
  saturatedFat?: number;
  proteins?: number;
  carbohydrates?: number;
  fiber?: number;
  novaGroup?: number; // 1 to 4
  nutriscoreGrade?: 'a' | 'b' | 'c' | 'd' | 'e';
  ecoscoreGrade?: 'a' | 'b' | 'c' | 'd' | 'e';
  ukTrafficLight?: UkTrafficLight;
  servingSize?: string;
  usDVs?: {
    caloriesPercent?: number;
    fatPercent?: number;
    satFatPercent?: number;
    sodiumPercent?: number;
    carbsPercent?: number;
    fiberPercent?: number;
  };
}

export interface CosmeticProfile {
  category?: string;
  comedogenicRating?: number; // 0-5
  hasFragrance?: boolean;
  hasParabens?: boolean;
  hasSulfates?: boolean;
  hasAlcohol?: boolean;
  hasRetinoids?: boolean;
  hasSalicylicAcid?: boolean;
  safetySummary?: string;
}

export interface ProductScanResult {
  barcode: string;
  productName: string;
  brand?: string;
  countryOfOrigin?: string;
  productType: 'food' | 'cosmetic' | 'supplement';
  imageUrl?: string;
  ingredientsText: string;
  ingredientsList: string[];
  allergens: string[];
  labels: string[];
  nutrition?: NutritionFacts;
  cosmetic?: CosmeticProfile;
  ingredientSafetyList?: IngredientSafetyItem[];
  regulatoryBadges?: RegulatoryStatusBadge[];
  cleanScoreBreakdown?: CleanScoreBreakdown;
  herbDrugAlerts?: DetectedHerbDrugAlert[];
  safeSwaps?: SafeSwapRecommendation[];
  crossReactivityAlerts?: CrossReactivityAlert[];
  skincareActiveCheck?: RoutineAuditCheckResult;
  matchAssessment: {
    status: 'safe' | 'caution' | 'warning' | 'danger';
    score: number; // 0-100
    summary: string;
    warnings: MatchWarning[];
    safeHighlights: string[];
  };
  medMatch?: MedMatchAnalysis;
  source: 'openfoodfacts' | 'openbeautyfacts' | 'usda' | 'inci' | 'gemini_vision' | 'cached' | 'demo';
  scannedAt: string;
}

export interface HealthAnalyticsData {
  averageCompatibilityScore: number;
  totalProductsScanned: number;
  safeCount: number;
  warningCount: number;
  dangerCount: number;
  ultraProcessedCount: number; // NOVA 4
  ultraProcessedPercentage: number;
  topAllergensAvoided: { name: string; count: number }[];
  flaggedAdditivesEncountered: { name: string; count: number; risk: string }[];
  cleanProductRatio: number;
}

export interface ScanHistoryItem {
  id: string;
  barcode: string;
  productName: string;
  brand?: string;
  productType: 'food' | 'cosmetic' | 'supplement';
  imageUrl?: string;
  status: 'safe' | 'caution' | 'warning' | 'danger';
  score: number;
  warningCount: number;
  scannedAt: string;
  fullResult?: ProductScanResult;
  favorite?: boolean;
}

export interface ParsedReceiptItem {
  id: string;
  name: string;
  category: string;
  quantity?: number;
  estimatedPrice?: string;
  productType: 'food' | 'cosmetic' | 'household';
  ingredientsSummary: string;
  detectedAllergens: string[];
  flaggedAdditives: string[];
  novaGroup?: number;
  status: 'safe' | 'caution' | 'danger';
  score: number;
  affectedFamilyMembers: string[];
  warningReason?: string;
  suggestedSwap?: {
    name: string;
    brand: string;
    whyBetter: string;
  };
}

export interface ReceiptAuditResult {
  storeName: string;
  auditDate: string;
  totalItemsCount: number;
  overallScore: number;
  status: 'safe' | 'caution' | 'danger';
  safeItemsCount: number;
  flaggedItemsCount: number;
  highRiskCount: number;
  ultraProcessedPercentage: number;
  keyAllergensFound: string[];
  criticalAdditivesFound: string[];
  familyImpactSummary: string[];
  items: ParsedReceiptItem[];
}

export interface SupermarketStore {
  id: string;
  name: string;
  country: SupportedCountry | 'GLOBAL';
  logoBadge: string;
  accentColor: string;
  categories: string[];
  description: string;
}

export interface MarketProductItem {
  barcode: string;
  name: string;
  brand: string;
  type: 'food' | 'cosmetic';
  category: string;
  image: string;
  storeId: string;
  country?: SupportedCountry | 'GLOBAL';
  priceUsd?: number;
  priceEur?: number;
  priceGbp?: number;
  safetyTier: 'clean' | 'caution' | 'high_risk';
  familyCompatibilityScore: number;
  highlightTag: string;
  ingredientsText: string;
  ingredientsList: string[];
  allergens: string[];
  labels: string[];
  nutrition?: any;
  cosmetic?: any;
}

export interface CrossReactivityAlert {
  primaryAllergen: string;
  triggerItem: string;
  syndromeName: string;
  clinicalCrossRisk: 'very_high' | 'high' | 'medium' | 'moderate';
  riskPercentageRange: string;
  mechanismExplanation: string;
  scientificProteinFamily: string;
  clinicalAdvice: string;
  cookingEffect?: string;
}

export interface CrossReactivityRule {
  id: string;
  sourceKey: string;
  sourceName: string;
  syndromeName: string;
  crossItems: {
    name: string;
    riskPercent: string;
    riskLevel: 'very_high' | 'high' | 'medium' | 'moderate';
    notes: string;
  }[];
  proteinFamily: string;
  mechanism: string;
  symptoms: string[];
  cookingEffect: string;
}

export interface SkincareActiveItem {
  name: string;
  category: 
    | 'retinoid' 
    | 'aha' 
    | 'bha' 
    | 'pha' 
    | 'vitamin_c_pure' 
    | 'vitamin_c_derivative' 
    | 'niacinamide' 
    | 'benzoyl_peroxide' 
    | 'copper_peptide' 
    | 'hydroquinone' 
    | 'azelaic_acid' 
    | 'physical_sunscreen' 
    | 'chemical_sunscreen'
    | 'barrier_ceramide'
    | 'hyaluronic_acid';
  role: string;
  concentrationEst?: string;
}

export interface SkincareConflictWarning {
  activeA: string;
  activeB: string;
  severity: 'high' | 'medium' | 'caution' | 'synergy';
  ruleTitle: string;
  riskDescription: string;
  solutionRecommendation: string;
  timingGuide: string;
  phClash?: boolean;
  barrierDamageRisk?: boolean;
}

export interface UserRoutineProduct {
  id: string;
  name: string;
  brand: string;
  step: 'cleanser' | 'toner' | 'serum' | 'treatment' | 'moisturizer' | 'sunscreen' | 'mask';
  timeOfDay: 'am' | 'pm' | 'both';
  activeIngredients: string[];
  activeCategories?: string[];
  notes?: string;
}

export interface RoutineAuditCheckResult {
  conflictCount: number;
  synergyCount: number;
  overallRoutineSafetyScore: number;
  conflicts: SkincareConflictWarning[];
  synergies: SkincareConflictWarning[];
  activeIngredientsFound: SkincareActiveItem[];
  skinCyclingGuide: {
    dayOrTime: string;
    instructions: string;
    productsUsed: string[];
  }[];
}

export interface HerbDrugInteractionAlert {
  herbName: string;
  drugOrClass: string;
  severity: 'contraindicated' | 'major' | 'moderate' | 'minor';
  mechanism: string;
  clinicalImpact: string;
  managementAdvice: string;
  evidenceTier: string;
  source: string;
}

export interface HerbDrugInteractionPair {
  id: string;
  herbOrSupplement: string;
  supplementAliases: string[];
  affectedDrugOrClass: string;
  drugAliases: string[];
  severity: 'contraindicated' | 'major' | 'moderate' | 'minor';
  mechanismType: string;
  cypEnzymeAffected?: string;
  clinicalSummary: string;
  managementAdvice: string;
  evidenceTier: string;
  sourceCitation: string;
}


/* ============ MedMatch AI medical types ============ */

export type MedMatchSeverity = 'major' | 'moderate' | 'minor';

export type MedMatchKind = 'herb' | 'drug_class' | 'food';

export interface MedMatchSearchHit {
  kind: MedMatchKind;
  id: string;
  label: string;
  matched_alias: string;
  score: number;
  scientific?: string;
  examples?: string[];
  warns_against?: string[];
}

export interface MedMatchEvidence {
  source: string;
  trust: number;
  doi?: string | null;
}

export interface MedMatchInteraction {
  type: 'herb-drug' | 'drug-drug' | 'drug-food' | 'herb-herb-evidence' | 'herb-drug-evidence' | 'cyp-inferred';
  a: { label: string; id: string; kind: MedMatchKind };
  b: { label: string; id: string; kind: MedMatchKind };
  severity: MedMatchSeverity | null;   // null = evidence-based, no severity
  effect?: string;
  mechanism?: string;
  evidence?: any;
  source?: string;
  doi?: string;
  trust?: number;
  action?: string;
  enzyme?: string;
  timing?: string;
}

export interface MedMatchDepletion {
  ingredient: string;
  severity: MedMatchSeverity;
  effect_size?: string;
  mechanism?: string;
  source?: string;
}

export interface MedMatchBeersFlag {
  class_id: string;
  label: string;
  level: 'avoid' | 'caution';
  note: string;
}

export interface MedMatchQtRisk {
  level: 'low' | 'moderate' | 'high';
  qt_classes: string[];
  factors: string[];
}

export interface MedMatchElectrolyte {
  electrolyte: string;
  sources: string[];
  reasons: string[];
  secondary_risk?: string;
}

export interface MedMatchCascadeNode {
  label: string;
  kind: string;
  role: string;
}

export interface MedMatchCascade {
  chain: MedMatchCascadeNode[];
  enzymes: string[];
  effect: string;
  trust: number;
}

export interface MedMatchScheduleConflict {
  a: string;
  b: string;
  reason: string;
  min_hours: number;
}

export interface MedMatchAnalysis {
  matched: { input: string; kind: string; id: string; label: string }[];
  interactions: MedMatchInteraction[];
  unmatched: string[];
  depletions: MedMatchDepletion[];
  beers?: MedMatchBeersFlag[];
  qt_risk?: MedMatchQtRisk[];
  electrolytes?: MedMatchElectrolyte[];
  cascades?: MedMatchCascade[];
  schedule?: MedMatchScheduleConflict[];
}

export interface MedMatchScanExtension {
  medMatch?: MedMatchAnalysis;
}

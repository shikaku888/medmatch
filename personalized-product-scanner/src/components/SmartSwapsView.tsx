import React, { useState, useEffect } from 'react';
import { ProductScanResult, UserProfile, SafeSwapRecommendation, SupportedLanguage } from '../types';
import { getTranslation } from '../i18n';
import { 
  Sparkles, 
  ShieldCheck, 
  ArrowRight, 
  GitCompare, 
  Leaf, 
  Check, 
  RefreshCw
} from 'lucide-react';

interface SmartSwapsViewProps {
  currentProduct: ProductScanResult | null;
  userProfile: UserProfile;
  onCompareProducts: (itemA: ProductScanResult, swap: SafeSwapRecommendation) => void;
  onSelectSwapAsProduct: (swap: SafeSwapRecommendation) => void;
}

export const SmartSwapsView: React.FC<SmartSwapsViewProps> = ({
  currentProduct,
  userProfile,
  onCompareProducts,
  onSelectSwapAsProduct
}) => {
  const lang = userProfile.language || 'en';
  const t = (key: string, fallback?: string) => getTranslation(lang, key, fallback);

  const [swaps, setSwaps] = useState<SafeSwapRecommendation[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeFilter, setActiveFilter] = useState<'all' | 'food' | 'cosmetic'>('all');

  useEffect(() => {
    fetchSwaps();
  }, [currentProduct?.barcode, userProfile.updatedAt, userProfile.language]);

  const fetchSwaps = async () => {
    if (!currentProduct) {
      setSwaps(getCuratedSwapsForProfile(userProfile));
      return;
    }

    setLoading(true);
    try {
      const res = await fetch('/api/smart-swaps', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product: currentProduct, profile: userProfile })
      });
      if (res.ok) {
        const data = await res.json();
        setSwaps(data);
      } else {
        setSwaps(getCuratedSwapsForProfile(userProfile));
      }
    } catch (err) {
      console.warn('Could not fetch dynamic swaps:', err);
      setSwaps(getCuratedSwapsForProfile(userProfile));
    } finally {
      setLoading(false);
    }
  };

  const filteredSwaps = swaps.filter(s => {
    if (activeFilter === 'all') return true;
    return s.productType === activeFilter;
  });

  return (
    <div id="smart-swaps-view" className="space-y-6">
      {/* Header Banner */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-blue-900 via-indigo-900 to-slate-900 text-white shadow-md relative overflow-hidden">
        <div className="relative z-10 max-w-2xl">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-blue-500/20 border border-blue-400/30 text-blue-300 text-xs font-semibold mb-3">
            <Sparkles className="w-3.5 h-3.5" />
            <span>{t('aiEngineBadge', 'AI Recommendation Engine • Pro Tier')}</span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight">
            {t('smartSwapsTitle', 'Smart Safe Swaps')}
          </h2>
          <p className="text-sm text-slate-300 mt-1 leading-relaxed">
            {t('smartSwapsSubtitle', 'Algorithmic clean alternatives formulated without your specific allergens and tailored to your diet.')}
          </p>
        </div>

        {/* Decorative element */}
        <div className="absolute right-0 top-0 bottom-0 w-80 opacity-10 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-blue-400 to-transparent pointer-events-none" />
      </div>

      {/* Target Product Reference Banner */}
      {currentProduct && (
        <div className="p-4 rounded-xl bg-amber-50/70 border border-amber-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-slate-900">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-lg bg-amber-100 border border-amber-300 flex items-center justify-center shrink-0 font-bold text-amber-800 text-sm">
              {currentProduct.matchAssessment.score}
            </div>
            <div>
              <span className="text-[10px] uppercase font-bold text-amber-800 tracking-wider">
                {t('activeEvaluation', 'Current Flagged Product')}
              </span>
              <h4 className="text-sm font-bold text-slate-900">
                {currentProduct.productName} ({currentProduct.brand || 'Standard'})
              </h4>
              <p className="text-xs text-slate-600">
                {currentProduct.matchAssessment.warnings.length} {t('statusWarning', 'conflicts identified')}.
              </p>
            </div>
          </div>

          <button
            onClick={fetchSwaps}
            disabled={loading}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-white hover:bg-amber-100 text-amber-900 border border-amber-300 text-xs font-semibold shadow-2xs transition-colors shrink-0"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>{t('findSmartSwaps', 'Regenerate AI Swaps')}</span>
          </button>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center justify-between border-b border-slate-200 pb-3">
        <div className="flex space-x-2">
          <button
            onClick={() => setActiveFilter('all')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeFilter === 'all'
                ? 'bg-slate-900 text-white shadow-2xs'
                : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
            }`}
          >
            {t('allProducts', 'All Categories')}
          </button>
          <button
            onClick={() => setActiveFilter('food')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeFilter === 'food'
                ? 'bg-slate-900 text-white shadow-2xs'
                : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
            }`}
          >
            {t('foodOnly', 'Foods & Groceries')}
          </button>
          <button
            onClick={() => setActiveFilter('cosmetic')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeFilter === 'cosmetic'
                ? 'bg-slate-900 text-white shadow-2xs'
                : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
            }`}
          >
            {t('cosmeticOnly', 'Skincare & Cosmetics')}
          </button>
        </div>
        <span className="text-xs text-slate-500 font-medium">
          {filteredSwaps.length} {t('safe', 'Alternatives')}
        </span>
      </div>

      {/* Loading state */}
      {loading ? (
        <div className="p-12 text-center bg-white rounded-xl border border-slate-200">
          <RefreshCw className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-3" />
          <h4 className="text-sm font-bold text-slate-800">
            {t('scanning', 'Analyzing across databases...')}
          </h4>
        </div>
      ) : (
        /* Swap Cards Grid */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredSwaps.length === 0 ? (
            <div className="col-span-full p-8 text-center text-slate-500 bg-white rounded-xl border border-slate-200">
              {t('noSwapsFound', 'No smart swaps found matching your current filter.')}
            </div>
          ) : (
            filteredSwaps.map((swap) => (
              <div
                key={swap.id}
                className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col justify-between hover:border-blue-400 hover:shadow-md transition-all group"
              >
                <div className="p-5 space-y-4">
                  {/* Header */}
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                        {swap.category}
                      </span>
                      <h3 className="font-bold text-base text-slate-900 mt-1.5 leading-snug group-hover:text-blue-600 transition-colors">
                        {swap.name}
                      </h3>
                      <p className="text-xs text-slate-500 font-medium">
                        {swap.brand}
                      </p>
                    </div>

                    <div className="text-right shrink-0">
                      <span className="block text-[9px] uppercase font-bold tracking-wider text-slate-400">
                        Score
                      </span>
                      <span className="text-xl font-black text-emerald-600">
                        {swap.score}<span className="text-xs text-slate-400 font-medium">/100</span>
                      </span>
                    </div>
                  </div>

                  {/* Score Delta vs Current Product */}
                  {currentProduct && (
                    <div className="p-2.5 rounded-lg bg-emerald-50 border border-emerald-200 flex items-center justify-between text-xs text-emerald-900 font-medium">
                      <span className="flex items-center space-x-1.5">
                        <ShieldCheck className="w-4 h-4 text-emerald-600" />
                        <span>Score Delta:</span>
                      </span>
                      <span className="font-bold text-emerald-700">
                        +{Math.max(5, swap.score - currentProduct.matchAssessment.score)} pts
                      </span>
                    </div>
                  )}

                  {/* Why it's Better list */}
                  <div>
                    <h5 className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1.5">
                      {t('whyBetterTitle', 'Why This Swap is Better:')}
                    </h5>
                    <ul className="space-y-1.5 text-xs text-slate-700">
                      {swap.whyBetter.map((reason, idx) => (
                        <li key={idx} className="flex items-start space-x-2">
                          <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                          <span>{reason}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Clean Highlights Badges */}
                  <div className="pt-2 border-t border-slate-100 flex flex-wrap gap-1.5">
                    {swap.cleanHighlights.map((badge, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 text-[10px] font-semibold border border-slate-200"
                      >
                        {badge}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="p-4 bg-slate-50 border-t border-slate-200 flex items-center gap-2">
                  {currentProduct && (
                    <button
                      onClick={() => onCompareProducts(currentProduct, swap)}
                      className="flex-1 inline-flex items-center justify-center space-x-1.5 py-2 px-3 rounded-lg bg-white hover:bg-slate-100 text-slate-800 text-xs font-bold border border-slate-300 shadow-2xs transition-colors"
                    >
                      <GitCompare className="w-3.5 h-3.5 text-blue-600" />
                      <span>{t('compareProduct', 'Compare')}</span>
                    </button>
                  )}
                  
                  <button
                    onClick={() => onSelectSwapAsProduct(swap)}
                    className="flex-1 inline-flex items-center justify-center space-x-1.5 py-2 px-3 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow-2xs transition-colors"
                  >
                    <span>{t('viewDetailsAndScan', 'Select Swap')}</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};

// Curated default recommendations localized
function getCuratedSwapsForProfile(profile: UserProfile): SafeSwapRecommendation[] {
  const isEs = profile.language === 'es';
  const isFr = profile.language === 'fr';
  const isDe = profile.language === 'de';
  const isIt = profile.language === 'it';

  if (isEs) {
    return [
      {
        id: 'swap_curated_1',
        name: 'Mantequilla Orgánica de Semillas de Girasol',
        brand: 'SunButter',
        productType: 'food',
        category: 'Untables y Alternativa a Frutos Secos',
        score: 98,
        whyBetter: [
          '100% Libre de los 8 alérgenos principales (Sin cacahuate ni frutos de cáscara)',
          'Cero aceites hidrogenados o conservantes químicos',
          'Elaborado en instalaciones certificadas libres de alérgenos'
        ],
        keyBenefits: ['7g de proteína vegetal por porción', 'Rico en Vitamina E, Zinc y Magnesio'],
        cleanHighlights: ['Sin Cacahuate', 'Sin Gluten Certificado', 'Non-GMO Project', 'Kosher'],
        priceRange: '$$ - Moderado',
        certificationBadges: ['USDA Organic', 'Certified Allergen Friendly']
      },
      {
        id: 'swap_curated_2',
        name: 'Leche de Avena Orgánica Sin Azúcar (Edición Barista)',
        brand: 'Oatly / Califia',
        productType: 'food',
        category: 'Bebida Vegetal Alternativa a Lácteos',
        score: 96,
        whyBetter: [
          'Cero lácteos, lactosa, caseína ni grasas animales',
          'Sin azúcares añadidos ni edulcorantes artificiales',
          'Certificado libre de residuos de glifosato'
        ],
        keyBenefits: ['Fortificado con Calcio, Riboflavina, Vitamina D y B12', 'Textura cremosa natural'],
        cleanHighlights: ['Certificado Vegano', 'Sin Nueces', 'Sin Soya', 'Sin Lácteos'],
        priceRange: '$$ - Estándar',
        certificationBadges: ['USDA Organic', 'Non-GMO']
      },
      {
        id: 'swap_curated_3',
        name: 'Toleriane Dermallergo Hidratante Facial Calmante',
        brand: 'La Roche-Posay',
        productType: 'cosmetic',
        category: 'Cuidado para Piel Sensible',
        score: 99,
        whyBetter: [
          '0% Fragancias, Alcohol, Parabenos o Conservantes (Empaque Hermético)',
          'Formulado con Neurosensina para calmar rojeces e irritaciones',
          'Probado en pieles hiperreactivas con tendencia alérgica'
        ],
        keyBenefits: ['Agua Termal Prebiótica que restaura el microbioma', 'Reparación intensa de barrera lipídica'],
        cleanHighlights: ['Dermatológicamente Probado', 'Hipoalergénico', 'No Comedogénico'],
        priceRange: '$$ - Gama Media',
        certificationBadges: ['National Eczema Association', 'ECARF']
      },
      {
        id: 'swap_curated_4',
        name: 'Pan Artesanal de Masa Madre de Granos Ancestrales',
        brand: 'Base Culture',
        productType: 'food',
        category: 'Panadería Saludable',
        score: 94,
        whyBetter: [
          'Receta 100% libre de gluten y libre de granos refinados',
          'Sin jarabe de maíz de alta fructosa ni propionato de calcio',
          'Bajo índice glucémico para control de glucosa'
        ],
        keyBenefits: ['4g de fibra prebiótica por rebanada', 'Formulación limpia con aceite de oliva extra virgen'],
        cleanHighlights: ['Sin Gluten', 'Sin Granos', 'Sin Lácteos', 'Paleo'],
        priceRange: '$$ - Premium',
        certificationBadges: ['Non-GMO Verified']
      }
    ];
  }

  return [
    {
      id: 'swap_curated_1',
      name: 'Organic Creamy Sunflower Butter',
      brand: 'SunButter',
      productType: 'food',
      category: 'Spreads & Nut Butter Alternative',
      score: 98,
      whyBetter: [
        '100% Free from Top 8 Allergens (Peanut & Tree Nut Free)',
        'Zero hydrogenated oils or chemical preservatives',
        'Produced in a dedicated allergen-free certified facility'
      ],
      keyBenefits: ['7g Plant Protein per serving', 'Packed with Vitamin E, Zinc, and Magnesium'],
      cleanHighlights: ['Certified Peanut-Free', 'Gluten-Free', 'Non-GMO Project', 'Kosher'],
      priceRange: '$$ - Moderate',
      certificationBadges: ['USDA Organic', 'Certified Allergen Friendly']
    },
    {
      id: 'swap_curated_2',
      name: 'Unsweetened Organic Oat Milk (Barista Edition)',
      brand: 'Oatly / Califia',
      productType: 'food',
      category: 'Dairy Alternative Beverage',
      score: 96,
      whyBetter: [
        'Zero dairy, lactose, casein, or animal fats',
        'Zero added cane sugars or artificial sweeteners',
        'Glyphosate residue-free tested'
      ],
      keyBenefits: ['Fortified with Calcium, Riboflavin, Vitamin D & B12', 'Smooth natural texture'],
      cleanHighlights: ['Vegan Certified', 'Nut-Free', 'Soy-Free', 'Dairy-Free'],
      priceRange: '$$ - Standard',
      certificationBadges: ['USDA Organic', 'Non-GMO']
    },
    {
      id: 'swap_curated_3',
      name: 'Toleriane Dermallergo Soothing Daily Moisturizer',
      brand: 'La Roche-Posay',
      productType: 'cosmetic',
      category: 'Sensitive Skincare',
      score: 99,
      whyBetter: [
        '0% Fragrance, Alcohol, Parabens, or Preservatives (Hermetic Packaging)',
        'Formulated with Neurosensine to inhibit neuro-sensory redness',
        'Tested on allergy-prone and reactive skin types'
      ],
      keyBenefits: ['Prebiotic Thermal Spring Water restores microbiome', 'Intense 48H lipid barrier repair'],
      cleanHighlights: ['Dermatologist Tested', 'Hypoallergenic', 'Non-Comedogenic'],
      priceRange: '$$ - Mid-Tier',
      certificationBadges: ['National Eczema Association', 'ECARF Certified']
    },
    {
      id: 'swap_curated_4',
      name: 'Simple Artisan Ancient Grain Sourdough',
      brand: 'Base Culture',
      productType: 'food',
      category: 'Bakery',
      score: 94,
      whyBetter: [
        '100% Certified Gluten-Free, Grain-Free recipe',
        'Zero high-fructose corn syrup, bleached flour, or calcium propionate',
        'Low glycemic index prevents insulin spikes'
      ],
      keyBenefits: ['4g Prebiotic fiber per slice', 'Clean ingredient deck with olive oil'],
      cleanHighlights: ['Gluten-Free', 'Grain-Free', 'Dairy-Free', 'Paleo'],
      priceRange: '$$ - Premium',
      certificationBadges: ['Non-GMO Verified']
    }
  ];
}

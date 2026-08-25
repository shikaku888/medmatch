import React, { useState } from 'react';
import { ProductScanResult, UserProfile, SupportedLanguage } from '../types';
import { getTranslation } from '../i18n';
import { 
  GitCompare, 
  Check, 
  X, 
  Trophy
} from 'lucide-react';

interface CompareViewProps {
  productA: ProductScanResult | null;
  productB: ProductScanResult | null;
  allScans: ProductScanResult[];
  userProfile: UserProfile;
  onSelectA: (p: ProductScanResult) => void;
  onSelectB: (p: ProductScanResult) => void;
}

export const CompareView: React.FC<CompareViewProps> = ({
  productA,
  productB,
  allScans,
  userProfile,
  onSelectA,
  onSelectB
}) => {
  const lang = userProfile.language || 'en';
  const t = (key: string, fallback?: string) => getTranslation(lang, key, fallback);

  const [showSelectorA, setShowSelectorA] = useState(false);
  const [showSelectorB, setShowSelectorB] = useState(false);

  const getWinner = () => {
    if (!productA || !productB) return null;
    const scoreA = productA.matchAssessment.score;
    const scoreB = productB.matchAssessment.score;
    if (scoreA > scoreB) return 'A';
    if (scoreB > scoreA) return 'B';
    return 'tie';
  };

  const winner = getWinner();

  return (
    <div className="space-y-6">
      {/* Compare Header */}
      <div className="bg-white border border-slate-200 p-6 rounded-xl shadow-sm">
        <div className="flex items-center space-x-3.5">
          <div className="w-12 h-12 rounded-xl bg-blue-50 border border-blue-100 text-blue-600 flex items-center justify-center">
            <GitCompare className="w-7 h-7" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">
              {t('compareTitle', 'Comparative Compatibility Evaluation')}
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              {t('compareSubtitle', 'Evaluate two products side-by-side against your allergies, dietary regimen, and clinical contraindications.')}
            </p>
          </div>
        </div>
      </div>

      {/* Comparison Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* PRODUCT A */}
        <div className={`p-6 rounded-xl border bg-white shadow-sm transition-all ${
          winner === 'A' ? 'border-emerald-500 ring-1 ring-emerald-500/20' : 'border-slate-200'
        }`}>
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs uppercase font-bold text-slate-500 tracking-wider">
              {t('productOptionA', 'Product Option A')}
            </span>
            {winner === 'A' && (
              <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-md bg-emerald-50 text-emerald-800 text-xs font-bold border border-emerald-200 shadow-2xs">
                <Trophy className="w-3.5 h-3.5 text-emerald-600" />
                <span>{t('recommendedChoice', 'Recommended Choice')}</span>
              </span>
            )}
          </div>

          {productA ? (
            <div className="space-y-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-base font-bold text-slate-900 leading-snug">
                    {productA.productName}
                  </h3>
                  {productA.brand && (
                    <p className="text-xs text-slate-500 mt-0.5">{productA.brand}</p>
                  )}
                  <span className="inline-block mt-1.5 text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
                    {productA.productType}
                  </span>
                </div>
                <button
                  onClick={() => setShowSelectorA(true)}
                  className="text-xs text-blue-600 hover:text-blue-700 font-semibold hover:underline shrink-0 cursor-pointer"
                >
                  {t('changeProduct', 'Change')}
                </button>
              </div>

              {/* Fit Score */}
              <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between shadow-2xs">
                <div>
                  <span className="block text-[10px] text-slate-500 uppercase font-semibold">{t('avgScoreMetric', 'Score')}</span>
                  <span className={`text-2xl font-black ${
                    productA.matchAssessment.score >= 80 ? 'text-emerald-700' : productA.matchAssessment.score >= 50 ? 'text-amber-600' : 'text-rose-600'
                  }`}>
                    {productA.matchAssessment.score}/100
                  </span>
                </div>
                <span className={`px-2.5 py-1 rounded-md text-xs font-bold uppercase ${
                  productA.matchAssessment.status === 'safe' 
                    ? 'bg-emerald-100 text-emerald-800 border border-emerald-200' 
                    : 'bg-rose-100 text-rose-800 border border-rose-200'
                }`}>
                  {productA.matchAssessment.status}
                </span>
              </div>

              {/* Warnings breakdown */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-slate-600 uppercase tracking-wider">
                  {t('statusWarning', 'Flagged Items')} ({productA.matchAssessment.warnings.length})
                </h4>
                {productA.matchAssessment.warnings.length > 0 ? (
                  <div className="space-y-1.5">
                    {productA.matchAssessment.warnings.map(w => (
                      <div key={w.id} className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-800 shadow-2xs font-medium">
                        <span className="font-bold text-rose-600 mr-1.5">•</span>
                        {w.title}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-emerald-800 bg-emerald-50 border border-emerald-200 p-2.5 rounded-lg flex items-center space-x-1.5 font-semibold">
                    <Check className="w-4 h-4 text-emerald-600" />
                    <span>{t('noConflictsDetected', 'No personal conflicts detected!')}</span>
                  </p>
                )}
              </div>

              {/* Nutrition */}
              {productA.nutrition && (
                <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs grid grid-cols-3 gap-2 shadow-2xs">
                  <div className="bg-white p-2 rounded border border-slate-200">
                    <span className="block text-[10px] text-slate-500 uppercase">{t('sugars', 'Sugars')}</span>
                    <span className="font-bold text-slate-900">{productA.nutrition.sugars ?? 'N/A'}g</span>
                  </div>
                  <div className="bg-white p-2 rounded border border-slate-200">
                    <span className="block text-[10px] text-slate-500 uppercase">{t('sodium', 'Sodium')}</span>
                    <span className="font-bold text-slate-900">{productA.nutrition.sodium ?? 'N/A'}mg</span>
                  </div>
                  <div className="bg-white p-2 rounded border border-slate-200">
                    <span className="block text-[10px] text-slate-500 uppercase">{t('novaScore', 'NOVA')}</span>
                    <span className="font-bold text-slate-900">Group {productA.nutrition.novaGroup ?? 'N/A'}</span>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="p-10 text-center border-2 border-dashed border-slate-200 rounded-xl space-y-3 bg-slate-50">
              <p className="text-xs text-slate-500 font-medium">{t('noProductSelectedA', 'No product selected for Option A')}</p>
              <button
                onClick={() => setShowSelectorA(true)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs rounded-lg transition-colors shadow-sm cursor-pointer"
              >
                {t('selectProductA', 'Select Product A')}
              </button>
            </div>
          )}
        </div>

        {/* PRODUCT B */}
        <div className={`p-6 rounded-xl border bg-white shadow-sm transition-all ${
          winner === 'B' ? 'border-emerald-500 ring-1 ring-emerald-500/20' : 'border-slate-200'
        }`}>
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs uppercase font-bold text-slate-500 tracking-wider">
              {t('productOptionB', 'Product Option B')}
            </span>
            {winner === 'B' && (
              <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-md bg-emerald-50 text-emerald-800 text-xs font-bold border border-emerald-200 shadow-2xs">
                <Trophy className="w-3.5 h-3.5 text-emerald-600" />
                <span>{t('recommendedChoice', 'Recommended Choice')}</span>
              </span>
            )}
          </div>

          {productB ? (
            <div className="space-y-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-base font-bold text-slate-900 leading-snug">
                    {productB.productName}
                  </h3>
                  {productB.brand && (
                    <p className="text-xs text-slate-500 mt-0.5">{productB.brand}</p>
                  )}
                  <span className="inline-block mt-1.5 text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
                    {productB.productType}
                  </span>
                </div>
                <button
                  onClick={() => setShowSelectorB(true)}
                  className="text-xs text-blue-600 hover:text-blue-700 font-semibold hover:underline shrink-0 cursor-pointer"
                >
                  {t('changeProduct', 'Change')}
                </button>
              </div>

              {/* Fit Score */}
              <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between shadow-2xs">
                <div>
                  <span className="block text-[10px] text-slate-500 uppercase font-semibold">{t('avgScoreMetric', 'Score')}</span>
                  <span className={`text-2xl font-black ${
                    productB.matchAssessment.score >= 80 ? 'text-emerald-700' : productB.matchAssessment.score >= 50 ? 'text-amber-600' : 'text-rose-600'
                  }`}>
                    {productB.matchAssessment.score}/100
                  </span>
                </div>
                <span className={`px-2.5 py-1 rounded-md text-xs font-bold uppercase ${
                  productB.matchAssessment.status === 'safe' 
                    ? 'bg-emerald-100 text-emerald-800 border border-emerald-200' 
                    : 'bg-rose-100 text-rose-800 border border-rose-200'
                }`}>
                  {productB.matchAssessment.status}
                </span>
              </div>

              {/* Warnings breakdown */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-slate-600 uppercase tracking-wider">
                  {t('statusWarning', 'Flagged Items')} ({productB.matchAssessment.warnings.length})
                </h4>
                {productB.matchAssessment.warnings.length > 0 ? (
                  <div className="space-y-1.5">
                    {productB.matchAssessment.warnings.map(w => (
                      <div key={w.id} className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-800 shadow-2xs font-medium">
                        <span className="font-bold text-rose-600 mr-1.5">•</span>
                        {w.title}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-emerald-800 bg-emerald-50 border border-emerald-200 p-2.5 rounded-lg flex items-center space-x-1.5 font-semibold">
                    <Check className="w-4 h-4 text-emerald-600" />
                    <span>{t('noConflictsDetected', 'No personal conflicts detected!')}</span>
                  </p>
                )}
              </div>

              {/* Nutrition */}
              {productB.nutrition && (
                <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs grid grid-cols-3 gap-2 shadow-2xs">
                  <div className="bg-white p-2 rounded border border-slate-200">
                    <span className="block text-[10px] text-slate-500 uppercase">{t('sugars', 'Sugars')}</span>
                    <span className="font-bold text-slate-900">{productB.nutrition.sugars ?? 'N/A'}g</span>
                  </div>
                  <div className="bg-white p-2 rounded border border-slate-200">
                    <span className="block text-[10px] text-slate-500 uppercase">{t('sodium', 'Sodium')}</span>
                    <span className="font-bold text-slate-900">{productB.nutrition.sodium ?? 'N/A'}mg</span>
                  </div>
                  <div className="bg-white p-2 rounded border border-slate-200">
                    <span className="block text-[10px] text-slate-500 uppercase">{t('novaScore', 'NOVA')}</span>
                    <span className="font-bold text-slate-900">Group {productB.nutrition.novaGroup ?? 'N/A'}</span>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="p-10 text-center border-2 border-dashed border-slate-200 rounded-xl space-y-3 bg-slate-50">
              <p className="text-xs text-slate-500 font-medium">{t('noProductSelectedB', 'No product selected for Option B')}</p>
              <button
                onClick={() => setShowSelectorB(true)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs rounded-lg transition-colors shadow-sm cursor-pointer"
              >
                {t('selectProductB', 'Select Product B')}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Product Selection Modal (A or B) */}
      {(showSelectorA || showSelectorB) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs">
          <div className="bg-white border border-slate-200 rounded-xl max-w-lg w-full p-6 space-y-4 max-h-[80vh] flex flex-col shadow-xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <h3 className="text-base font-bold text-slate-900">
                {t('selectProductOption', 'Select Product')} ({showSelectorA ? 'Option A' : 'Option B'})
              </h3>
              <button
                onClick={() => { setShowSelectorA(false); setShowSelectorB(false); }}
                className="text-slate-400 hover:text-slate-700 p-1 rounded-md cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="overflow-y-auto space-y-2 flex-1 pr-1">
              {allScans.map((scan) => (
                <button
                  key={scan.barcode}
                  onClick={() => {
                    if (showSelectorA) onSelectA(scan);
                    if (showSelectorB) onSelectB(scan);
                    setShowSelectorA(false);
                    setShowSelectorB(false);
                  }}
                  className="w-full p-3 rounded-lg bg-slate-50 hover:bg-blue-50/50 border border-slate-200 text-left transition-colors flex items-center justify-between shadow-2xs cursor-pointer"
                >
                  <div>
                    <h4 className="text-xs font-bold text-slate-900">{scan.productName}</h4>
                    <p className="text-[10px] text-slate-500">{scan.brand || scan.productType}</p>
                  </div>
                  <span className={`text-xs font-black ${
                    scan.matchAssessment.score >= 80 ? 'text-emerald-700' : scan.matchAssessment.score >= 50 ? 'text-amber-600' : 'text-rose-600'
                  }`}>
                    {scan.matchAssessment.score}/100
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

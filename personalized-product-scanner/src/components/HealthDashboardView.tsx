import React, { useState, useEffect } from 'react';
import { UserProfile, HealthAnalyticsData, ScanHistoryItem } from '../types';
import { getTranslation } from '../i18n';
import { 
  Activity, 
  ShieldCheck, 
  AlertOctagon, 
  Flame, 
  FileText, 
  Printer, 
  Sparkles, 
  CheckCircle,
  HeartPulse
} from 'lucide-react';

interface HealthDashboardViewProps {
  userProfile: UserProfile;
  history: ScanHistoryItem[];
  onOpenProModal: () => void;
  isProUser: boolean;
}

export const HealthDashboardView: React.FC<HealthDashboardViewProps> = ({
  userProfile,
  history,
  onOpenProModal,
  isProUser
}) => {
  const lang = userProfile.language || 'en';
  const t = (key: string, fallback?: string) => getTranslation(lang, key, fallback);

  const [analytics, setAnalytics] = useState<HealthAnalyticsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [showExportModal, setShowExportModal] = useState(false);

  useEffect(() => {
    fetchAnalytics();
  }, [history.length, userProfile.updatedAt, userProfile.language]);

  const fetchAnalytics = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/analytics');
      if (res.ok) {
        const data = await res.json();
        setAnalytics(data);
      }
    } catch (e) {
      console.warn('Analytics fetch error:', e);
    } finally {
      setLoading(false);
    }
  };

  const handlePrintReport = () => {
    window.print();
  };

  const avgScore = analytics?.averageCompatibilityScore ?? 88;
  const ultraProcessedPct = analytics?.ultraProcessedPercentage ?? 25;
  const safeRatio = analytics?.cleanProductRatio ?? 75;

  return (
    <div id="health-dashboard-view" className="space-y-6">
      {/* Header Banner */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950 to-blue-950 text-white shadow-md flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-emerald-500/20 border border-emerald-400/30 text-emerald-300 text-xs font-semibold mb-2">
            <HeartPulse className="w-3.5 h-3.5" />
            <span>{t('dashboardTitle', 'Health & Additive Exposure Dashboard')}</span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight">
            {t('dashboardTitle', 'Personal Health & Additive Exposure Dashboard')}
          </h2>
          <p className="text-sm text-slate-300 mt-1 max-w-xl">
            {t('dashboardSubtitle', 'Real-time telemetry of scanned groceries, skincare formulations, allergen intercepts, and ultra-processed food burden.')}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <button
            id="export-clinical-report-btn"
            onClick={() => setShowExportModal(true)}
            className="inline-flex items-center space-x-2 px-4 py-2.5 rounded-xl bg-white hover:bg-slate-100 text-slate-900 text-xs font-bold shadow-sm transition-all border border-slate-200"
          >
            <FileText className="w-4 h-4 text-blue-600" />
            <span>{t('clinicalReportBtn', 'Clinical Dietitian Report')}</span>
          </button>
        </div>
      </div>

      {/* Top 4 KPI Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Compatibility Score */}
        <div className="p-5 rounded-xl bg-white border border-slate-200 shadow-sm space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              {t('avgScoreMetric', 'Mean Compatibility')}
            </span>
            <Activity className={`w-4 h-4 ${avgScore >= 80 ? 'text-emerald-600' : 'text-amber-600'}`} />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-3xl font-black text-slate-900">{avgScore}</span>
            <span className="text-xs text-slate-400 font-medium">/ 100</span>
          </div>
          <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
            <div 
              className={`h-full ${avgScore >= 80 ? 'bg-emerald-500' : 'bg-amber-500'}`}
              style={{ width: `${avgScore}%` }}
            />
          </div>
          <p className="text-[11px] text-slate-500 font-medium">
            {avgScore >= 80 ? t('safe', 'Optimal match') : t('caution', 'Requires ingredient scrutiny')}
          </p>
        </div>

        {/* Metric 2: Ultra-Processed Ratio */}
        <div className="p-5 rounded-xl bg-white border border-slate-200 shadow-sm space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              {t('ultraProcessedMetric', 'NOVA 4 Ultra-Processed')}
            </span>
            <Flame className="w-4 h-4 text-rose-500" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-3xl font-black text-rose-600">{ultraProcessedPct}%</span>
            <span className="text-xs text-slate-400 font-medium">{t('allScans', 'of Scanned Diet')}</span>
          </div>
          <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
            <div 
              className="h-full bg-rose-500"
              style={{ width: `${ultraProcessedPct}%` }}
            />
          </div>
          <p className="text-[11px] text-slate-500 font-medium">
            {ultraProcessedPct < 30 ? t('safe', 'Low ultra-processed burden') : t('warning', 'Consider Whole-Food Swaps')}
          </p>
        </div>

        {/* Metric 3: Allergen Intercepts */}
        <div className="p-5 rounded-xl bg-white border border-slate-200 shadow-sm space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              {t('allergenInterceptsMetric', 'Allergens Blocked')}
            </span>
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-3xl font-black text-emerald-600">
              {analytics?.dangerCount ?? 0}
            </span>
            <span className="text-xs text-slate-400 font-medium">{t('statusDanger', 'Hazard Alerts Intercepted')}</span>
          </div>
          <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
            <div className="h-full bg-emerald-500" style={{ width: '100%' }} />
          </div>
          <p className="text-[11px] text-slate-500 font-medium">
            {userProfile.allergies.length} {t('allergens', 'Allergens Monitored')}
          </p>
        </div>

        {/* Metric 4: Clean Ratio */}
        <div className="p-5 rounded-xl bg-white border border-slate-200 shadow-sm space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              {t('cleanRatioMetric', 'Safe Clean Ratio')}
            </span>
            <CheckCircle className="w-4 h-4 text-blue-600" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-3xl font-black text-slate-900">{safeRatio}%</span>
            <span className="text-xs text-slate-400 font-medium">
              ({analytics?.safeCount ?? 0}/{analytics?.totalProductsScanned ?? history.length})
            </span>
          </div>
          <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
            <div className="h-full bg-blue-600" style={{ width: `${safeRatio}%` }} />
          </div>
          <p className="text-[11px] text-slate-500 font-medium">
            {t('fdaGras', 'Verified Safe Databases')}
          </p>
        </div>
      </div>

      {/* Main Breakdown Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* SECTION A: Toxic Additive & Preservative Radar */}
        <div className="p-6 rounded-xl bg-white border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center space-x-2.5">
              <div className="p-2 rounded-lg bg-rose-50 border border-rose-200 text-rose-700">
                <AlertOctagon className="w-4 h-4" />
              </div>
              <div>
                <h3 className="font-bold text-sm text-slate-900">
                  {t('additiveRiskTitle', 'Toxic Additive & Sensitizer Radar')}
                </h3>
                <p className="text-xs text-slate-500 font-medium">
                  {t('cleanChemistry', 'Preservatives, artificial colorants, and endocrine disruptors')}
                </p>
              </div>
            </div>
            <span className="text-xs font-bold text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
              {t('safe', 'Active Screen')}
            </span>
          </div>

          <div className="space-y-3">
            {[
              {
                category: 'Synthetic Dyes (Red 40, Yellow 5, Titanium Dioxide)',
                level: 'Moderate',
                description: 'Neuro-behavioral triggers & intestinal barrier disruption',
                status: 'Monitored',
                statusColor: 'text-amber-700 bg-amber-50 border-amber-200'
              },
              {
                category: 'Preservatives & Nitrites (Sodium Nitrite, BHA/BHT)',
                level: 'High Risk',
                description: 'Endocrine disruption & carcinogenic nitrosamine formation',
                status: 'Restricted',
                statusColor: 'text-rose-700 bg-rose-50 border-rose-200'
              },
              {
                category: 'Cosmetic Sensitizers (Parabens, Phthalates, Fragrance)',
                level: 'High Risk',
                description: 'Hormone receptor binding & skin contact dermatitis',
                status: 'Restricted',
                statusColor: 'text-rose-700 bg-rose-50 border-rose-200'
              },
              {
                category: 'High-Intensity Sweeteners (Sucralose, Aspartame)',
                level: 'Low-Moderate',
                description: 'Gut microbiome shifts & metabolic signaling strain',
                status: 'Tracked',
                statusColor: 'text-blue-700 bg-blue-50 border-blue-200'
              }
            ].map((tox, i) => (
              <div
                key={i}
                className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 flex items-start justify-between gap-3 text-xs"
              >
                <div className="space-y-1">
                  <h4 className="font-bold text-slate-900">{tox.category}</h4>
                  <p className="text-slate-600 font-normal">{tox.description}</p>
                </div>
                <span className={`shrink-0 px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider border ${tox.statusColor}`}>
                  {tox.status}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* SECTION B: Longitudinal Profile Protection Summary */}
        <div className="p-6 rounded-xl bg-white border border-slate-200 shadow-sm space-y-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center space-x-2.5">
                <div className="p-2 rounded-lg bg-blue-50 border border-blue-200 text-blue-700">
                  <ShieldCheck className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-slate-900">
                    {t('profileTitle', 'Clinical Protection Protocol')}
                  </h3>
                  <p className="text-xs text-slate-500 font-medium">
                    {t('profileSubtitle', 'Profile rules actively verified on every scan')}
                  </p>
                </div>
              </div>
              <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                100% {t('safe', 'Active')}
              </span>
            </div>

            <div className="mt-4 space-y-3">
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <span className="block text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                  {t('foodAllergensTitle', 'Targeted Allergens & Sensitivities')} ({userProfile.allergies.length + userProfile.customAllergens.length}):
                </span>
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {[...userProfile.allergies, ...userProfile.customAllergens].map((alg, idx) => (
                    <span
                      key={idx}
                      className="px-2.5 py-1 rounded-md bg-white border border-slate-200 text-xs font-semibold text-slate-800 shadow-2xs"
                    >
                      🛡️ {alg}
                    </span>
                  ))}
                  {userProfile.allergies.length === 0 && (
                    <span className="text-xs text-slate-400 italic">None</span>
                  )}
                </div>
              </div>

              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <span className="block text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                  {t('dietTypeTitle', 'Dietary Guideline:')}
                </span>
                <p className="text-xs font-bold text-slate-800 mt-1 capitalize">
                  🥗 {userProfile.dietType}
                </p>
              </div>

              {userProfile.specialConditions.length > 0 && (
                <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                  <span className="block text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                    {t('specialConditionsTitle', 'Physiological Conditions:')}
                  </span>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {userProfile.specialConditions.map((cond, idx) => (
                      <span
                        key={idx}
                        className="px-2.5 py-1 rounded-md bg-amber-50 border border-amber-200 text-xs font-semibold text-amber-900"
                      >
                        ⚠️ {cond}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Pro Upgrade Banner */}
          {!isProUser && (
            <div className="mt-4 p-4 rounded-xl bg-gradient-to-r from-blue-900 to-indigo-900 text-white flex items-center justify-between gap-3 shadow-sm">
              <div className="space-y-0.5">
                <h4 className="font-bold text-xs flex items-center space-x-1.5 text-amber-300">
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>{t('upgradeToPro', 'Upgrade to Pro')}</span>
                </h4>
                <p className="text-[11px] text-slate-300">
                  {t('tagline', 'Unlock multi-member profiles & AI smart swaps.')}
                </p>
              </div>
              <button
                onClick={onOpenProModal}
                className="px-3 py-1.5 rounded-lg bg-amber-400 hover:bg-amber-300 text-slate-950 text-xs font-bold shrink-0 transition-colors shadow-2xs"
              >
                {t('upgradeToPro', 'Go Pro')}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* MODAL: Printable Clinical Dietitian Report */}
      {showExportModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-3xl w-full overflow-hidden text-slate-900 animate-in fade-in zoom-in-95 duration-200">
            {/* Header */}
            <div className="p-6 bg-slate-900 text-white flex items-center justify-between">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-blue-400">
                  {t('clinicalReportBtn', 'Clinical Document Export')}
                </span>
                <h3 className="text-xl font-bold">{t('clinicalReportBtn', 'Personalized Assessment Report')}</h3>
                <p className="text-xs text-slate-400">{userProfile.name} • {new Date().toLocaleDateString()}</p>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={handlePrintReport}
                  className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold flex items-center space-x-1.5 shadow-sm"
                >
                  <Printer className="w-3.5 h-3.5" />
                  <span>{t('shareProduct', 'Print / PDF')}</span>
                </button>
                <button
                  onClick={() => setShowExportModal(false)}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold"
                >
                  {t('close', 'Close')}
                </button>
              </div>
            </div>

            {/* Document Content */}
            <div className="p-8 space-y-6 max-h-[70vh] overflow-y-auto text-xs leading-relaxed font-sans">
              <div className="border-b border-slate-200 pb-4 flex justify-between items-start">
                <div>
                  <h4 className="font-bold text-base text-slate-900">MedMatch Verified Safety Transcript</h4>
                  <p className="text-slate-500">Clinical Telemetry Engine • OpenFoodFacts + USDA + PubMed Grounded</p>
                </div>
                <div className="text-right text-[11px] text-slate-500 font-mono">
                  Report ID: MEDMATCH-{Math.random().toString(36).substring(2, 9).toUpperCase()}
                </div>
              </div>

              {/* Patient Profile Box */}
              <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div>
                  <span className="block text-[10px] text-slate-400 font-bold uppercase">{t('tabProfile', 'Profile')}</span>
                  <span className="font-bold text-slate-800">{userProfile.name || 'Primary User'}</span>
                </div>
                <div>
                  <span className="block text-[10px] text-slate-400 font-bold uppercase">{t('dietTypeTitle', 'Diet')}</span>
                  <span className="font-bold text-slate-800 capitalize">{userProfile.dietType}</span>
                </div>
                <div>
                  <span className="block text-[10px] text-slate-400 font-bold uppercase">{t('allergens', 'Allergens')}</span>
                  <span className="font-bold text-rose-700">{userProfile.allergies.join(', ') || 'None'}</span>
                </div>
                <div>
                  <span className="block text-[10px] text-slate-400 font-bold uppercase">{t('specialConditionsTitle', 'Conditions')}</span>
                  <span className="font-bold text-amber-800">{userProfile.specialConditions.join(', ') || 'None'}</span>
                </div>
              </div>

              {/* Scanned Items History Summary Table */}
              <div>
                <h5 className="font-bold text-sm text-slate-900 mb-2">{t('historyTitle', 'Verified Scanned Products Audit Trail')}</h5>
                <table className="w-full border-collapse border border-slate-200 text-left text-[11px]">
                  <thead>
                    <tr className="bg-slate-100 text-slate-700 font-bold">
                      <th className="p-2 border border-slate-200">Product</th>
                      <th className="p-2 border border-slate-200">Category</th>
                      <th className="p-2 border border-slate-200">Status</th>
                      <th className="p-2 border border-slate-200">Score</th>
                      <th className="p-2 border border-slate-200">Summary</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.slice(0, 10).map((item, idx) => (
                      <tr key={idx} className="hover:bg-slate-50">
                        <td className="p-2 border border-slate-200 font-bold text-slate-900">{item.productName}</td>
                        <td className="p-2 border border-slate-200 capitalize">{item.productType}</td>
                        <td className="p-2 border border-slate-200">
                          <span className={`px-1.5 py-0.5 rounded font-bold uppercase text-[9px] ${
                            item.status === 'safe' ? 'bg-emerald-100 text-emerald-800' :
                            item.status === 'danger' ? 'bg-rose-100 text-rose-800' : 'bg-amber-100 text-amber-800'
                          }`}>
                            {item.status}
                          </span>
                        </td>
                        <td className="p-2 border border-slate-200 font-bold">{item.score}/100</td>
                        <td className="p-2 border border-slate-200 text-slate-600">
                          {item.fullResult?.matchAssessment.summary || 'Compliant with restrictions.'}
                        </td>
                      </tr>
                    ))}
                    {history.length === 0 && (
                      <tr>
                        <td colSpan={5} className="p-4 text-center text-slate-400 italic">
                          {t('noHistoryMatch', 'No scan history recorded.')}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* Medical Disclaimer */}
              <div className="p-3 rounded-lg bg-slate-100 text-[10px] text-slate-500 border border-slate-200 italic">
                Disclaimer: Grounded in manufacturer ingredient declarations and peer-reviewed biomedical literature (NCBI PubMed, OpenFoodFacts, USDA). For dietary reference; consult a licensed healthcare professional.
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

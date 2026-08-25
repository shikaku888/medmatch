	import React, { useState } from 'react';
	import { getTranslation } from '../i18n';
	import { ProductScanResult, MatchWarning, ResearchData, IngredientSafetyItem, CrossReactivityAlert, RoutineAuditCheckResult, SupportedLanguage } from '../types';
	import { MedMatchResults } from './MedMatchResults';
	import {
	  ShieldCheck,
	  AlertOctagon,
	  AlertTriangle, 
  Info, 
  BookOpen, 
  Bookmark, 
  BookmarkCheck, 
  Share2, 
  Sparkles, 
  Layers, 
  Leaf, 
  Flame, 
  Droplet, 
  Check, 
  ChevronDown, 
  ChevronUp,
  Tag,
  GitCompare,
  Activity,
  Heart,
  MessageSquare,
  FlaskConical,
  Dna,
  Zap,
  Calendar,
  Sparkle,
  Pill,
  Globe,
  Award
} from 'lucide-react';

interface ScanResultCardProps {
  result: ProductScanResult;
  language?: SupportedLanguage;
  onOpenEvidence: (research: ResearchData) => void;
  onCompareWith?: (product: ProductScanResult) => void;
  onOpenAiChat?: () => void;
  onOpenSmartSwaps?: () => void;
  onOpenCrossReactivity?: () => void;
  onOpenSkincareRadar?: () => void;
  onOpenHerbDrugModal?: () => void;
  onRescan?: () => void;
}

export const ScanResultCard: React.FC<ScanResultCardProps> = ({
  result,
  language = 'en',
  onOpenEvidence,
  onCompareWith,
  onOpenAiChat,
  onOpenSmartSwaps,
  onOpenCrossReactivity,
  onOpenSkincareRadar,
  onOpenHerbDrugModal,
  onRescan
}) => {
  const [showFullIngredients, setShowFullIngredients] = useState(false);
  const [showCleanChemistry, setShowCleanChemistry] = useState(false);
  const [copied, setCopied] = useState(false);
  const [isFavorited, setIsFavorited] = useState(false);

  const t = (key: Parameters<typeof getTranslation>[1]) => getTranslation(language as SupportedLanguage, key);

  const { matchAssessment } = result;
  const { status, score, summary, warnings, safeHighlights } = matchAssessment;

  const handleShare = () => {
    const text = `Product: ${result.productName}\nPersonal Fit Status: ${status.toUpperCase()} (${score}/100)\nClean Score: ${result.cleanScoreBreakdown?.cleanScore || score}/100\n${summary}\nScanned with SuitSafe.`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Status Styling Configurations
  const statusConfig = {
    safe: {
      border: 'border-emerald-200',
      bg: 'bg-emerald-50/30',
      glow: 'shadow-sm',
      badgeBg: 'bg-emerald-700 text-white font-bold',
      icon: ShieldCheck,
      iconColor: 'text-emerald-700',
      iconBg: 'bg-emerald-100 border-emerald-200 text-emerald-800',
      label: 'COMPATIBLE WITH PROFILE',
      headerBg: 'bg-gradient-to-b from-emerald-50/80 to-white'
    },
    caution: {
      border: 'border-yellow-200',
      bg: 'bg-yellow-50/30',
      glow: 'shadow-sm',
      badgeBg: 'bg-amber-600 text-white font-bold',
      icon: Info,
      iconColor: 'text-amber-700',
      iconBg: 'bg-amber-100 border-amber-200 text-amber-800',
      label: 'MINOR CAUTIONS IDENTIFIED',
      headerBg: 'bg-gradient-to-b from-amber-50/80 to-white'
    },
    warning: {
      border: 'border-amber-200',
      bg: 'bg-amber-50/30',
      glow: 'shadow-sm',
      badgeBg: 'bg-amber-700 text-white font-bold',
      icon: AlertTriangle,
      iconColor: 'text-amber-800',
      iconBg: 'bg-amber-100 border-amber-200 text-amber-800',
      label: 'DIETARY OR CONDITION CONFLICT',
      headerBg: 'bg-gradient-to-b from-amber-50/80 to-white'
    },
    danger: {
      border: 'border-rose-200',
      bg: 'bg-rose-50/30',
      glow: 'shadow-sm',
      badgeBg: 'bg-rose-700 text-white font-bold',
      icon: AlertOctagon,
      iconColor: 'text-rose-700',
      iconBg: 'bg-rose-100 border-rose-200 text-rose-800',
      label: 'ALLERGEN ALERT / CRITICAL CONFLICT',
      headerBg: 'bg-gradient-to-b from-rose-50/80 to-white'
    }
  }[status];

  const StatusIcon = statusConfig.icon;

  const safetyItems = result.ingredientSafetyList || [];
  const hazardCount = safetyItems.filter(i => i.hazardLevel === 'danger').length;
  const cautionCount = safetyItems.filter(i => i.hazardLevel === 'caution').length;

  const cleanScore = result.cleanScoreBreakdown?.cleanScore ?? score;

  const getCleanScoreColor = (sc: number) => {
    if (sc >= 75) return { text: 'text-emerald-700', bg: 'bg-emerald-500', pill: 'bg-emerald-100 text-emerald-800', label: 'Excellent' };
    if (sc >= 50) return { text: 'text-amber-600', bg: 'bg-amber-500', pill: 'bg-amber-100 text-amber-800', label: 'Good / Moderate' };
    if (sc >= 25) return { text: 'text-orange-600', bg: 'bg-orange-500', pill: 'bg-orange-100 text-orange-800', label: 'Mediocre' };
    return { text: 'text-rose-600', bg: 'bg-rose-500', pill: 'bg-rose-100 text-rose-800', label: 'Poor / Bad' };
  };

  const cleanScoreStyle = getCleanScoreColor(cleanScore);

  return (
    <div 
      id="scan-result-card"
      className={`rounded-2xl border ${statusConfig.border} bg-white shadow-sm overflow-hidden text-slate-900 transition-all duration-200`}
    >
      {/* Assessment Header Banner */}
      <div className={`p-6 ${statusConfig.headerBg} border-b border-slate-200`}>
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-start space-x-4">
            <div className={`p-3 rounded-xl ${statusConfig.iconBg} border shadow-2xs shrink-0`}>
              <StatusIcon className={`w-7 h-7 ${statusConfig.iconColor}`} />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className={`px-2.5 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider ${statusConfig.badgeBg}`}>
                  {statusConfig.label}
                </span>
                {result.countryOfOrigin && (
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-white flex items-center space-x-1">
                    <Globe className="w-3 h-3 text-blue-400" />
                    <span>{result.countryOfOrigin} Market</span>
                  </span>
                )}
                <span className="text-xs text-slate-500 font-mono">
                  {result.barcode}
                </span>
              </div>
              <h2 className="text-xl sm:text-2xl font-bold text-slate-900 mt-1 tracking-tight">
                {result.productName}
              </h2>
              {result.brand && (
                <p className="text-xs text-slate-500 font-medium mt-0.5">
                  Brand: <span className="text-slate-800 font-semibold">{result.brand}</span>
                </p>
              )}
            </div>
          </div>

          {/* Scores Column: Fit Score + Yuka-Style Clean Score */}
          <div className="flex flex-wrap items-center gap-3 shrink-0">
            
            {/* Yuka-Style Clean Score Gauge */}
            {result.cleanScoreBreakdown && (
              <div className="bg-white border border-slate-200 px-3.5 py-2.5 rounded-xl shadow-2xs flex items-center space-x-3">
                <div className="text-right">
                  <span className="block text-[9px] uppercase tracking-wider text-slate-500 font-bold">
                    {t('cleanScore')} (Yuka-Index)
                  </span>
                  <div className="flex items-baseline space-x-1 justify-end">
                    <span className={`text-2xl font-black ${cleanScoreStyle.text}`}>
                      {cleanScore}
                    </span>
                    <span className="text-xs text-slate-400 font-medium">/100</span>
                  </div>
                  <span className={`inline-block px-1.5 py-0.2 rounded text-[9px] font-bold ${cleanScoreStyle.pill}`}>
                    {cleanScoreStyle.label}
                  </span>
                </div>
                <div className="w-10 h-10 rounded-full border-4 border-slate-100 flex items-center justify-center relative shadow-inner overflow-hidden">
                  <div 
                    className={`absolute bottom-0 w-full ${cleanScoreStyle.bg} transition-all duration-500 opacity-90`}
                    style={{ height: `${cleanScore}%` }}
                  />
                  <Award className="w-4 h-4 text-white relative z-10 drop-shadow-xs" />
                </div>
              </div>
            )}

            {/* Profile Fit Score Badge */}
            <div className="flex items-center space-x-3 bg-white border border-slate-200 px-3.5 py-2.5 rounded-xl shadow-2xs">
              <div className="text-right">
                <span className="block text-[9px] uppercase tracking-wider text-slate-500 font-bold">
                  {t('profileCompatibility')}
                </span>
                <span className={`text-2xl font-black ${
                  score >= 80 ? 'text-emerald-700' : score >= 50 ? 'text-amber-600' : 'text-rose-600'
                }`}>
                  {score}<span className="text-xs text-slate-400 font-medium">/100</span>
                </span>
              </div>
              <div className="w-10 h-10 rounded-full bg-slate-50 border-2 border-slate-200 flex items-center justify-center relative">
                <Activity className={`w-4 h-4 ${score >= 80 ? 'text-emerald-600' : score >= 50 ? 'text-amber-600' : 'text-rose-600'}`} />
              </div>
            </div>
          </div>
        </div>

        {/* Executive Summary */}
        <div className="mt-4 p-3.5 rounded-lg bg-white border border-slate-200 text-xs sm:text-sm text-slate-700 leading-relaxed font-medium shadow-2xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <span>{summary}</span>

          {/* Pro Action Triggers */}
          <div className="flex items-center space-x-2 shrink-0">
            {onOpenAiChat && (
              <button
                onClick={onOpenAiChat}
                className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow-2xs transition-colors"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>{t('askAiConsultant')}</span>
              </button>
            )}

            {score < 90 && onOpenSmartSwaps && (
              <button
                onClick={onOpenSmartSwaps}
                className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-amber-50 hover:bg-amber-100 text-amber-900 border border-amber-300 text-xs font-bold transition-colors"
              >
                <span>{t('findBetterAlternative')} (90+)</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Main Analysis Body */}
      <div className="p-6 space-y-6">

        {/* SECTION: MEDMATCH AI INTERACTION CHECK (FastAPI backend, evidence-backed) */}
        {result.medMatch && (
          <div className="p-4 rounded-xl bg-white border-2 border-teal-300 space-y-3 shadow-xs">
            <MedMatchResults analysis={result.medMatch} language={language} />
            {onOpenHerbDrugModal && (
              <button
                onClick={onOpenHerbDrugModal}
                className="text-xs font-bold text-teal-800 hover:underline flex items-center space-x-1"
              >
                <Pill className="w-3.5 h-3.5" />
                <span>Pharmacology Compendium (71,900 evidence-backed pairs)</span>
              </button>
            )}
          </div>
        )}

        {/* SECTION: REGULATORY STATUS BADGES (EU, US, UK, CA PROP 65) */}
        {result.regulatoryBadges && result.regulatoryBadges.length > 0 && (
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
            <div className="flex items-center space-x-2">
              <ShieldCheck className="w-4 h-4 text-blue-600" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                {t('regulatoryStatus')} (EU EFSA • US FDA • UK FSA • CA Prop 65)
              </h3>
            </div>

            <div className="flex flex-wrap gap-2">
              {result.regulatoryBadges.map((badge, idx) => (
                <div 
                  key={idx}
                  className={`p-2.5 rounded-xl border text-xs space-y-1 flex-1 min-w-[240px] ${
                    badge.region === 'EU' && badge.statusType === 'banned' 
                      ? 'bg-rose-50 border-rose-300' 
                      : badge.statusType === 'warning_label'
                      ? 'bg-amber-50 border-amber-300'
                      : 'bg-white border-slate-200'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-900">{badge.title}</span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold ${
                      badge.region === 'EU' && badge.statusType === 'banned'
                        ? 'bg-rose-600 text-white'
                        : badge.statusType === 'warning_label'
                        ? 'bg-amber-600 text-white'
                        : 'bg-slate-700 text-white'
                    }`}>
                      {badge.region} • {badge.statusType.replace('_', ' ')}
                    </span>
                  </div>
                  <p className="text-slate-600 text-[11px]">{badge.detail}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* SECTION: YUKA CLEAN SCORE THREE-PILLAR DECONSTRUCTION */}
        {result.cleanScoreBreakdown && (
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center space-x-2">
                <Award className="w-4 h-4 text-blue-600" />
                <span>Yuka Clean Formulation Matrix (0-100)</span>
              </h3>
              <span className="text-[11px] font-bold text-slate-600">
                Score: {result.cleanScoreBreakdown.totalScore}/100
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {/* Nutritional Quality: 60% */}
              <div className="p-3 rounded-lg bg-white border border-slate-200 space-y-1 shadow-2xs">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-slate-700">🥗 Nutrition Quality</span>
                  <span className="font-extrabold text-blue-700">60% Weight</span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div 
                    className="bg-blue-600 h-2 rounded-full" 
                    style={{ width: `${result.cleanScoreBreakdown.nutritionalQualityScore}%` }}
                  />
                </div>
                <div className="flex justify-between text-[10px] text-slate-500">
                  <span>Nutri-Score {result.nutrition?.nutriscoreGrade?.toUpperCase() || 'N/A'}</span>
                  <span className="font-bold text-slate-800">{result.cleanScoreBreakdown.nutritionalQualityScore}/100</span>
                </div>
              </div>

              {/* Additives & Toxins: 30% */}
              <div className="p-3 rounded-lg bg-white border border-slate-200 space-y-1 shadow-2xs">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-slate-700">🧪 Clean Additives</span>
                  <span className="font-extrabold text-amber-700">30% Weight</span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div 
                    className={`h-2 rounded-full ${
                      result.cleanScoreBreakdown.additivesSafetyScore >= 80 ? 'bg-emerald-500' : 'bg-amber-500'
                    }`} 
                    style={{ width: `${result.cleanScoreBreakdown.additivesSafetyScore}%` }}
                  />
                </div>
                <div className="flex justify-between text-[10px] text-slate-500">
                  <span>EFSA/FDA Monitored</span>
                  <span className="font-bold text-slate-800">{result.cleanScoreBreakdown.additivesSafetyScore}/100</span>
                </div>
              </div>

              {/* Organic / Bio: 10% */}
              <div className="p-3 rounded-lg bg-white border border-slate-200 space-y-1 shadow-2xs">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-slate-700">🌿 Organic / Bio</span>
                  <span className="font-extrabold text-emerald-700">10% Weight</span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div 
                    className="bg-emerald-500 h-2 rounded-full" 
                    style={{ width: `${result.cleanScoreBreakdown.organicBioBonus}%` }}
                  />
                </div>
                <div className="flex justify-between text-[10px] text-slate-500">
                  <span>{result.cleanScoreBreakdown.organicBioBonus > 0 ? 'Certified Bio (+10)' : 'Conventional (0)'}</span>
                  <span className="font-bold text-slate-800">{result.cleanScoreBreakdown.organicBioBonus}/100</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SECTION 1: DETECTED WARNINGS & PubMed EVIDENCE */}
        {warnings.length > 0 ? (
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-amber-600" />
                <span>Personal Profile Conflicts ({warnings.length})</span>
              </h3>
              <span className="text-xs text-slate-400">Targeted ingredient evaluation</span>
            </div>

            <div className="space-y-2.5">
              {warnings.map((warn) => (
                <div
                  key={warn.id}
                  className={`p-4 rounded-xl border transition-all ${
                    warn.level === 'high'
                      ? 'bg-rose-50/50 border-rose-200'
                      : warn.level === 'medium'
                      ? 'bg-amber-50/50 border-amber-200'
                      : 'bg-slate-50 border-slate-200'
                  }`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center space-x-2">
                        <span className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider ${
                          warn.level === 'high'
                            ? 'bg-rose-600 text-white'
                            : warn.level === 'medium'
                            ? 'bg-amber-600 text-white'
                            : 'bg-slate-200 text-slate-800'
                        }`}>
                          {warn.level} Priority
                        </span>
                        <h4 className="font-bold text-sm text-slate-900">
                          {warn.title}
                        </h4>
                      </div>
                      <p className="text-xs text-slate-700 leading-relaxed font-normal">
                        {warn.message}
                      </p>
                      {warn.explanation && (
                        <p className="text-xs text-slate-500 italic">
                          {warn.explanation}
                        </p>
                      )}
                    </div>

                    {/* Scientific Research Citation Button */}
                    {warn.research && (
                      <button
                        id={`evidence-btn-${warn.id}`}
                        onClick={() => onOpenEvidence(warn.research!)}
                        className="shrink-0 flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 text-xs font-semibold transition-colors shadow-2xs"
                        title="Click to view peer-reviewed NCBI PubMed studies"
                      >
                        <BookOpen className="w-3.5 h-3.5 text-blue-600" />
                        <span>{warn.research.studyCount}+ PubMed Studies</span>
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center space-x-3">
            <ShieldCheck className="w-5 h-5 text-emerald-600 shrink-0" />
            <p className="text-xs text-emerald-800 font-semibold">
              Zero allergen, diet, or condition conflicts identified for your profile.
            </p>
          </div>
        )}

        {/* SECTION 1.5: CROSS-REACTIVITY CLINICAL ALERTS */}
        {result.crossReactivityAlerts && result.crossReactivityAlerts.length > 0 && (
          <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-300 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Dna className="w-4 h-4 text-amber-700" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-amber-900">
                  {t('crossReactivity')} ({result.crossReactivityAlerts.length})
                </h3>
              </div>
              {onOpenCrossReactivity && (
                <button
                  onClick={onOpenCrossReactivity}
                  className="text-xs font-bold text-amber-800 hover:underline flex items-center space-x-1"
                >
                  <span>Explore Cross-Matrix</span>
                </button>
              )}
            </div>

            <div className="space-y-2">
              {result.crossReactivityAlerts.map((cross, idx) => (
                <div key={idx} className="p-3 rounded-lg bg-white/90 border border-amber-200 text-xs space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-900">
                      {cross.syndromeName}: {cross.triggerItem}
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-extrabold bg-amber-600 text-white">
                      Cross-Risk: {cross.riskPercentageRange}
                    </span>
                  </div>
                  <p className="text-slate-700 font-medium">
                    Because you have an allergy to <strong>{cross.primaryAllergen}</strong>. The <em>{cross.scientificProteinFamily}</em> protein family shares homologous epitope structures.
                  </p>
                  <p className="text-[11px] text-amber-900 font-semibold">
                    💡 Clinical Guidance: {cross.clinicalAdvice} {cross.cookingEffect ? `(${cross.cookingEffect})` : ''}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* SECTION 1.8: COSMECEUTICAL SKINCARE ACTIVE RADAR & ROUTINE CONFLICTS */}
        {result.skincareActiveCheck && (
          <div className="p-4 rounded-xl bg-teal-50/70 border border-teal-200 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Sparkles className="w-4 h-4 text-teal-700" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-teal-900">
                  {t('skincareRadar')} & Routine Verification
                </h3>
              </div>
              {onOpenSkincareRadar && (
                <button
                  onClick={onOpenSkincareRadar}
                  className="text-xs font-bold text-teal-800 hover:underline flex items-center space-x-1"
                >
                  <Zap className="w-3.5 h-3.5" />
                  <span>Routine Shelf</span>
                </button>
              )}
            </div>

            {/* Actives Found in this Product */}
            {result.skincareActiveCheck.activeIngredientsFound && result.skincareActiveCheck.activeIngredientsFound.length > 0 && (
              <div>
                <span className="text-[11px] font-bold text-slate-600 uppercase block mb-1">
                  Active Clinical Actives in this formulation:
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {result.skincareActiveCheck.activeIngredientsFound.map((act, i) => (
                    <span key={i} className="px-2 py-0.5 rounded text-xs font-bold bg-teal-100 text-teal-900 border border-teal-200">
                      {act.name} ({act.category})
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Conflicts vs Current Routine */}
            {result.skincareActiveCheck.conflicts.length > 0 ? (
              <div className="space-y-1.5 pt-1">
                <span className="text-[11px] font-bold text-rose-700 uppercase block">
                  ⚠️ Conflicts with your registered Routine:
                </span>
                {result.skincareActiveCheck.conflicts.map((conf, i) => (
                  <div key={i} className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-xs space-y-0.5">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-rose-900">
                        {conf.ruleTitle} ({conf.activeA} vs {conf.activeB})
                      </span>
                      <span className="px-1.5 py-0.2 rounded text-[9px] font-extrabold bg-rose-600 text-white uppercase">
                        {conf.severity}
                      </span>
                    </div>
                    <p className="text-slate-700">{conf.riskDescription}</p>
                    <p className="text-[11px] text-teal-800 font-semibold">
                      💡 Guideline: {conf.solutionRecommendation} ({conf.timingGuide})
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-2.5 rounded-lg bg-white border border-teal-200 text-xs text-teal-800 flex items-center space-x-2">
                <Check className="w-4 h-4 text-teal-600 shrink-0" />
                <span>Zero ingredient conflicts with items on your Routine Shelf.</span>
              </div>
            )}
          </div>
        )}

        {/* SECTION 2: CLEAN CHEMISTRY & TOXICITY DECONSTRUCTION */}
        {safetyItems.length > 0 && (
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <FlaskConical className="w-4 h-4 text-indigo-600" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                  Clean Chemistry & Toxicological Screen ({safetyItems.length})
                </h3>
              </div>
              <button
                onClick={() => setShowCleanChemistry(!showCleanChemistry)}
                className="text-xs text-blue-600 font-bold hover:underline flex items-center space-x-1"
              >
                <span>{showCleanChemistry ? 'Collapse' : `View ${safetyItems.length} Ingredients`}</span>
                {showCleanChemistry ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>
            </div>

            <div className="flex flex-wrap gap-2 text-xs">
              <span className="px-2.5 py-1 rounded-lg bg-emerald-100 text-emerald-800 font-semibold">
                🟢 {safetyItems.filter(s => s.hazardLevel === 'safe').length} Safe / Bioactive
              </span>
              {cautionCount > 0 && (
                <span className="px-2.5 py-1 rounded-lg bg-amber-100 text-amber-800 font-semibold">
                  🟡 {cautionCount} Monitored / Additives
                </span>
              )}
              {hazardCount > 0 && (
                <span className="px-2.5 py-1 rounded-lg bg-rose-100 text-rose-800 font-bold">
                  🔴 {hazardCount} High Hazard / Restricted
                </span>
              )}
            </div>

            {showCleanChemistry && (
              <div className="mt-3 space-y-2 max-h-60 overflow-y-auto pr-1">
                {safetyItems.map((item, idx) => (
                  <div
                    key={idx}
                    className={`p-3 rounded-lg border flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs ${
                      item.hazardLevel === 'danger'
                        ? 'bg-rose-50/60 border-rose-200'
                        : item.hazardLevel === 'caution'
                        ? 'bg-amber-50/60 border-amber-200'
                        : 'bg-white border-slate-200'
                    }`}
                  >
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className={`w-2 h-2 rounded-full ${
                          item.hazardLevel === 'danger' ? 'bg-rose-600' : item.hazardLevel === 'caution' ? 'bg-amber-500' : 'bg-emerald-500'
                        }`} />
                        <h5 className="font-bold text-slate-900">{item.name}</h5>
                        <span className="text-[10px] text-slate-500">({item.roleDescription})</span>
                      </div>
                      {item.healthImpact && (
                        <p className="text-[11px] text-slate-600 mt-0.5 pl-4">
                          {item.healthImpact}
                        </p>
                      )}
                    </div>

                    {item.regulatoryStatus && (
                      <span className="shrink-0 px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-700 border border-slate-200">
                        {item.regulatoryStatus}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* SECTION 3: UK TRAFFIC LIGHT SYSTEM & NUTRI-SCORE */}
        {result.nutrition && (
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center space-x-2">
                <Flame className="w-3.5 h-3.5 text-amber-600" />
                <span>Multi-Market Nutrition Frameworks</span>
              </h3>
              <div className="flex items-center space-x-2">
                {result.nutrition.nutriscoreGrade && (
                  <span className="px-2 py-0.5 rounded text-xs font-black uppercase bg-blue-700 text-white">
                    Nutri-Score {result.nutrition.nutriscoreGrade.toUpperCase()}
                  </span>
                )}
                {result.nutrition.ecoscoreGrade && (
                  <span className="px-2 py-0.5 rounded text-xs font-black uppercase bg-emerald-700 text-white flex items-center space-x-1">
                    <Leaf className="w-3 h-3" />
                    <span>Eco-Score {result.nutrition.ecoscoreGrade.toUpperCase()}</span>
                  </span>
                )}
              </div>
            </div>

            {/* UK Traffic Light Grid */}
            {result.nutrition.ukTrafficLight && (
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1.5">
                  {t('ukTrafficLight')} (FSA UK Standards):
                </span>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {[
                    { label: 'Fat', val: result.nutrition.fat, rating: result.nutrition.ukTrafficLight.fatLevel, unit: 'g' },
                    { label: 'Saturates', val: result.nutrition.saturatedFat, rating: result.nutrition.ukTrafficLight.satFatLevel, unit: 'g' },
                    { label: 'Sugars', val: result.nutrition.sugars, rating: result.nutrition.ukTrafficLight.sugarsLevel, unit: 'g' },
                    { label: 'Salt', val: result.nutrition.salt, rating: result.nutrition.ukTrafficLight.saltLevel, unit: 'g' },
                  ].map((nutr, i) => (
                    <div 
                      key={i} 
                      className={`p-2.5 rounded-xl border text-center ${
                        nutr.rating === 'high' ? 'bg-rose-50 border-rose-300' :
                        nutr.rating === 'med' ? 'bg-amber-50 border-amber-300' :
                        'bg-emerald-50 border-emerald-300'
                      }`}
                    >
                      <span className="text-[10px] font-bold text-slate-500 uppercase block">{nutr.label}</span>
                      <span className={`inline-block px-1.5 py-0.2 rounded text-[9px] font-black uppercase ${
                        nutr.rating === 'high' ? 'bg-rose-600 text-white' :
                        nutr.rating === 'med' ? 'bg-amber-600 text-white' :
                        'bg-emerald-600 text-white'
                      }`}>
                        {nutr.rating}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* US Daily Values Grid */}
            {result.nutrition.usDVs && (
              <div className="pt-2 border-t border-slate-200">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1.5">
                  {t('usDailyValues')} (% Daily Reference Intake):
                </span>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                  <div className="p-2 rounded bg-white border border-slate-200 text-center">
                    <span className="text-[10px] text-slate-500 block">Total Fat DV</span>
                    <strong className="text-slate-900">{result.nutrition.usDVs.fatPercent}%</strong>
                  </div>
                  <div className="p-2 rounded bg-white border border-slate-200 text-center">
                    <span className="text-[10px] text-slate-500 block">Sat. Fat DV</span>
                    <strong className="text-slate-900">{result.nutrition.usDVs.satFatPercent}%</strong>
                  </div>
                  <div className="p-2 rounded bg-white border border-slate-200 text-center">
                    <span className="text-[10px] text-slate-500 block">Sodium DV</span>
                    <strong className="text-slate-900">{result.nutrition.usDVs.sodiumPercent}%</strong>
                  </div>
                  <div className="p-2 rounded bg-white border border-slate-200 text-center">
                    <span className="text-[10px] text-slate-500 block">NOVA Group</span>
                    <strong className="text-slate-900">Group {result.nutrition.novaGroup || 'N/A'}</strong>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* SECTION 4: COSMETIC INCI PROFILE */}
        {result.productType === 'cosmetic' && result.cosmetic && (
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center space-x-2">
                <Droplet className="w-3.5 h-3.5 text-blue-600" />
                <span>Cosmetic & Skincare INCI Profile</span>
              </h3>
              <span className="text-[11px] text-slate-500 font-medium">Formulation Safety</span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 text-xs">
              <div className="p-3 rounded-lg bg-white border border-slate-200 flex items-center justify-between shadow-2xs">
                <span className="text-slate-500 font-medium">Fragrance:</span>
                <span className={`font-bold ${!result.cosmetic.hasFragrance ? 'text-emerald-700' : 'text-rose-600'}`}>
                  {!result.cosmetic.hasFragrance ? 'Fragrance-Free' : 'Present'}
                </span>
              </div>
              <div className="p-3 rounded-lg bg-white border border-slate-200 flex items-center justify-between shadow-2xs">
                <span className="text-slate-500 font-medium">Parabens:</span>
                <span className={`font-bold ${!result.cosmetic.hasParabens ? 'text-emerald-700' : 'text-amber-600'}`}>
                  {!result.cosmetic.hasParabens ? 'Paraben-Free' : 'Contains Parabens'}
                </span>
              </div>
              <div className="p-3 rounded-lg bg-white border border-slate-200 flex items-center justify-between shadow-2xs">
                <span className="text-slate-500 font-medium">Comedogenic:</span>
                <span className={`font-bold ${
                  (result.cosmetic.comedogenicRating || 0) >= 3 ? 'text-amber-600' : 'text-emerald-700'
                }`}>
                  {result.cosmetic.comedogenicRating || 0}/5 Rating
                </span>
              </div>
            </div>
            {result.cosmetic.safetySummary && (
              <p className="text-xs text-slate-600 italic bg-white p-2.5 rounded-lg border border-slate-200">
                {result.cosmetic.safetySummary}
              </p>
            )}
          </div>
        )}

        {/* SECTION 5: INGREDIENTS LIST VIEWER */}
        <div>
          <button
            onClick={() => setShowFullIngredients(!showFullIngredients)}
            className="w-full flex items-center justify-between p-3 rounded-lg bg-slate-50 hover:bg-slate-100 border border-slate-200 text-xs font-semibold text-slate-700 transition-colors"
          >
            <div className="flex items-center space-x-2">
              <Layers className="w-4 h-4 text-slate-500" />
              <span>Complete Ingredients List ({result.ingredientsList?.length || 'View'})</span>
            </div>
            {showFullIngredients ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
          </button>

          {showFullIngredients && (
            <div className="mt-2 p-4 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-700 space-y-3">
              <p className="leading-relaxed font-mono text-[11px] text-slate-600">
                {result.ingredientsText || result.ingredientsList?.join(', ') || 'No ingredients text reported.'}
              </p>

              {result.ingredientsList && result.ingredientsList.length > 0 && (
                <div>
                  <span className="block text-[10px] text-slate-500 uppercase tracking-wider mb-1.5 font-bold">
                    Parsed Components ({result.ingredientsList.length}):
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {result.ingredientsList.map((ing, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 rounded bg-white text-slate-800 text-[11px] border border-slate-200 shadow-2xs font-medium"
                      >
                        {ing}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* SECTION 6: DATA SOURCE ATTRIBUTION */}
        <div className="flex flex-wrap items-center justify-between text-xs text-slate-500 pt-3 border-t border-slate-200">
          <div className="flex items-center space-x-2">
            <span>Verified Source:</span>
            <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-semibold border border-slate-200 text-[11px]">
              {result.source === 'openfoodfacts' ? 'Open Food Facts (Public Database)' : 
               result.source === 'openbeautyfacts' ? 'Open Beauty Facts' : 
               result.source === 'usda' ? 'USDA FoodData Central' : 
               result.source === 'gemini_vision' ? 'Gemini Vision AI Engine' : 'Verified Dataset'}
            </span>
          </div>
          <span>Evaluated {new Date(result.scannedAt).toLocaleTimeString()}</span>
        </div>

        {/* ACTION BUTTONS */}
        <div className="flex flex-wrap items-center gap-2 pt-2">
          {onOpenAiChat && (
            <button
              onClick={onOpenAiChat}
              className="flex-1 inline-flex items-center justify-center space-x-2 py-2.5 px-3 rounded-lg bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-bold transition-colors border border-blue-200 shadow-2xs"
            >
              <MessageSquare className="w-4 h-4 text-blue-600" />
              <span>{t('askAiConsultant')}</span>
            </button>
          )}

          {onOpenHerbDrugModal && (
            <button
              onClick={onOpenHerbDrugModal}
              className="inline-flex items-center justify-center space-x-1.5 py-2.5 px-3 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-800 text-xs font-bold transition-colors border border-rose-200 shadow-2xs"
              title={t('herbDrugRadar')}
            >
              <Pill className="w-4 h-4 text-rose-600" />
              <span className="hidden sm:inline">{t('herbDrugRadar')}</span>
            </button>
          )}

          {onOpenCrossReactivity && (
            <button
              onClick={onOpenCrossReactivity}
              className="inline-flex items-center justify-center space-x-1.5 py-2.5 px-3 rounded-lg bg-amber-50 hover:bg-amber-100 text-amber-800 text-xs font-bold transition-colors border border-amber-200 shadow-2xs"
              title={t('crossReactivity')}
            >
              <Dna className="w-4 h-4 text-amber-600" />
              <span className="hidden sm:inline">{t('crossReactivity')}</span>
            </button>
          )}

          {result.productType === 'cosmetic' && onOpenSkincareRadar && (
            <button
              onClick={onOpenSkincareRadar}
              className="inline-flex items-center justify-center space-x-1.5 py-2.5 px-3 rounded-lg bg-teal-50 hover:bg-teal-100 text-teal-800 text-xs font-bold transition-colors border border-teal-200 shadow-2xs"
              title={t('skincareRadar')}
            >
              <Zap className="w-4 h-4 text-teal-600" />
              <span className="hidden sm:inline">{t('skincareRadar')}</span>
            </button>
          )}

          {onCompareWith && (
            <button
              id="compare-this-product-btn"
              onClick={() => onCompareWith(result)}
              className="flex-1 inline-flex items-center justify-center space-x-2 py-2.5 px-3 rounded-lg bg-white hover:bg-slate-50 text-slate-800 text-xs font-semibold transition-colors border border-slate-300 shadow-2xs"
            >
              <GitCompare className="w-4 h-4 text-blue-600" />
              <span>{t('compare')}</span>
            </button>
          )}

          <button
            id="share-scan-btn"
            onClick={handleShare}
            className="inline-flex items-center justify-center space-x-1.5 py-2.5 px-3 rounded-lg bg-white hover:bg-slate-50 text-slate-800 text-xs font-semibold transition-colors border border-slate-300 shadow-2xs"
          >
            {copied ? <Check className="w-4 h-4 text-emerald-600" /> : <Share2 className="w-4 h-4 text-slate-500" />}
            <span className="hidden sm:inline">{copied ? 'Copied' : 'Share'}</span>
          </button>

          {onRescan && (
            <button
              id="rescan-another-btn"
              onClick={onRescan}
              className="inline-flex items-center justify-center space-x-2 py-2.5 px-4 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold transition-colors shadow-sm"
            >
              <span>{t('scan')}</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};


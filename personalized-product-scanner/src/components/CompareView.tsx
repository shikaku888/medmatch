import React, { useState } from 'react';
import {
  ProductScanResult,
  UserProfile,
  MedMatchAnalysis,
  MedMatchSeverity,
} from '../types';
import { getTranslation } from '../i18n';
import {
  GitCompare,
  Check,
  X,
  Trophy,
  AlertOctagon,
  AlertTriangle,
  Info,
  BookOpen,
  Heart,
  GitBranch,
  CalendarClock,
  Droplet,
  Pill,
} from 'lucide-react';

interface CompareViewProps {
  productA: ProductScanResult | null;
  productB: ProductScanResult | null;
  allScans: ProductScanResult[];
  userProfile: UserProfile;
  onSelectA: (p: ProductScanResult) => void;
  onSelectB: (p: ProductScanResult) => void;
}

const SEV_ORDER: (MedMatchSeverity | 'evidence')[] = ['major', 'moderate', 'minor', 'evidence'];

function sevRank(sev: MedMatchSeverity | null) {
  const idx = SEV_ORDER.indexOf(sev ?? 'evidence');
  return idx === -1 ? 99 : idx;
}

/**
 * Medical comparison basis (plan 4.3): products are ranked by MedMatch
 * interaction burden against the user's medication profile, not food scores.
 * Deterministic weights — worst severity always dominates the verdict.
 */
interface MedStats {
  score: number; // 0-100 medical safety score
  major: number;
  moderate: number;
  minor: number;
  evidence: number;
  cascades: number;
  scheduleConflicts: number;
  qtWorst: 'high' | 'moderate' | null;
  beersAvoid: number;
  beersCaution: number;
  depletions: number;
  electrolytes: number;
  worst: MedMatchSeverity | 'evidence' | 'clear';
}

function medStats(a: MedMatchAnalysis): MedStats {
  let score = 100;
  const major = a.interactions.filter(i => i.severity === 'major').length;
  const moderate = a.interactions.filter(i => i.severity === 'moderate').length;
  const minor = a.interactions.filter(i => i.severity === 'minor').length;
  const evidence = a.interactions.filter(i => !i.severity).length;

  score -= major * 28;
  score -= moderate * 12;
  score -= minor * 4;
  score -= evidence * 2;

  const cascades = a.cascades?.length ?? 0;
  score -= cascades * 6;

  const scheduleConflicts = a.schedule?.length ?? 0;
  score -= scheduleConflicts * 5;

  let qtWorst: 'high' | 'moderate' | null = null;
  for (const qt of a.qt_risk || []) {
    if (qt.level === 'high') qtWorst = 'high';
    else if (qt.level === 'moderate' && !qtWorst) qtWorst = 'moderate';
  }
  if (qtWorst === 'high') score -= 10;
  else if (qtWorst === 'moderate') score -= 4;

  let beersAvoid = 0;
  let beersCaution = 0;
  for (const b of a.beers || []) {
    if (b.level === 'avoid') beersAvoid++;
    else beersCaution++;
  }
  score -= beersAvoid * 8;
  score -= beersCaution * 3;

  const depletions = (a.depletions || []).length;
  for (const d of a.depletions || []) {
    if (d.severity === 'major') score -= 6;
    else if (d.severity === 'moderate') score -= 3;
    else score -= 1;
  }

  const electrolytes = a.electrolytes?.length ?? 0;
  score -= electrolytes * 3;

  const worst: MedStats['worst'] =
    major > 0 ? 'major'
    : moderate > 0 ? 'moderate'
    : minor > 0 ? 'minor'
    : evidence > 0 ? 'evidence'
    : 'clear';

  return {
    score: Math.max(0, Math.min(100, Math.round(score))),
    major, moderate, minor, evidence,
    cascades, scheduleConflicts, qtWorst,
    beersAvoid, beersCaution,
    depletions, electrolytes,
    worst,
  };
}

const WORST_META: Record<Exclude<MedStats['worst'], undefined>, { label: string; cls: string }> = {
  major: { label: 'Major Risk', cls: 'bg-rose-100 text-rose-800 border-rose-200' },
  moderate: { label: 'Caution', cls: 'bg-amber-100 text-amber-800 border-amber-200' },
  minor: { label: 'Minor Only', cls: 'bg-sky-100 text-sky-800 border-sky-200' },
  evidence: { label: 'Evidence Signals', cls: 'bg-indigo-100 text-indigo-800 border-indigo-200' },
  clear: { label: 'Clear', cls: 'bg-emerald-100 text-emerald-800 border-emerald-200' },
};

function countChip(label: string, count: number, toneCls: string) {
  if (count <= 0) return null;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold border ${toneCls}`}>
      {count} {label}
    </span>
  );
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

  const statsA = productA?.medMatch ? medStats(productA.medMatch) : null;
  const statsB = productB?.medMatch ? medStats(productB.medMatch) : null;
  const medicalVerdict = Boolean(statsA && statsB);
  const partialCoverage = Boolean((statsA && !statsB) || (statsB && !statsA));

  const getWinner = (): 'A' | 'B' | 'tie' | null => {
    if (!productA || !productB) return null;
    if (statsA && statsB) {
      if (statsA.score !== statsB.score) return statsA.score > statsB.score ? 'A' : 'B';
      if (statsA.major !== statsB.major) return statsA.major < statsB.major ? 'A' : 'B';
      return 'tie';
    }
    // Legacy fallback for scans not yet MedMatch-analyzed.
    const scoreA = productA.matchAssessment.score;
    const scoreB = productB.matchAssessment.score;
    if (scoreA > scoreB) return 'A';
    if (scoreB > scoreA) return 'B';
    return 'tie';
  };

  const winner = getWinner();

  const verdictLine = (() => {
    if (!medicalVerdict || !productA || !productB || !statsA || !statsB) return null;
    if (winner === 'tie') {
      return t('compareTieVerdict', 'Tie — both products carry the same interaction burden for your current medications.');
    }
    const wName = winner === 'A' ? productA.productName : productB.productName;
    const w = (winner === 'A' ? statsA : statsB)!;
    const l = (winner === 'A' ? statsB : statsA)!;
    return `${wName}: ${w.score}/100 ${t('compareVs', 'vs')} ${l.score}/100 — ${w.major} ${t('sevMajor', 'major')} / ${l.major} ${t('sevMajor', 'major')} · ${w.moderate} ${t('sevModerate', 'moderate')} / ${l.moderate} ${t('sevModerate', 'moderate')}`;
  })();

  const renderPanel = (
    side: 'A' | 'B',
    product: ProductScanResult | null,
    stats: MedStats | null
  ) => {
    const isWinner = winner === side;
    const openSelector = () => { if (side === 'A') setShowSelectorA(true); else setShowSelectorB(true); };
    const noProductText = side === 'A'
      ? t('noProductSelectedA', 'No product selected for Option A')
      : t('noProductSelectedB', 'No product selected for Option B');
    const selectText = side === 'A' ? t('selectProductA', 'Select Product A') : t('selectProductB', 'Select Product B');

    return (
      <div className={`p-6 rounded-xl border bg-white shadow-sm transition-all ${
        isWinner ? 'border-emerald-500 ring-1 ring-emerald-500/20' : 'border-slate-200'
      }`}>
        <div className="flex items-center justify-between mb-4">
          <span className="text-xs uppercase font-bold text-slate-500 tracking-wider">
            {side === 'A' ? t('productOptionA', 'Product Option A') : t('productOptionB', 'Product Option B')}
          </span>
          {isWinner && (
            <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-md bg-emerald-50 text-emerald-800 text-xs font-bold border border-emerald-200 shadow-2xs">
              <Trophy className="w-3.5 h-3.5 text-emerald-600" />
              <span>{t('recommendedChoice', 'Recommended Choice')}</span>
            </span>
          )}
        </div>

        {product ? (
          <div className="space-y-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-base font-bold text-slate-900 leading-snug">
                  {product.productName}
                </h3>
                {product.brand && (
                  <p className="text-xs text-slate-500 mt-0.5">{product.brand}</p>
                )}
                <span className="inline-block mt-1.5 text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
                  {product.productType}
                </span>
              </div>
              <button
                onClick={openSelector}
                className="text-xs text-blue-600 hover:text-blue-700 font-semibold hover:underline shrink-0 cursor-pointer"
              >
                {t('changeProduct', 'Change')}
              </button>
            </div>

            {stats ? (
              <>
                {/* MedMatch medical safety */}
                <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between shadow-2xs">
                  <div>
                    <span className="block text-[10px] text-slate-500 uppercase font-semibold">
                      {t('medSafetyScore', 'Interaction Safety')}
                    </span>
                    <span className={`text-2xl font-black ${
                      stats.score >= 80 ? 'text-emerald-700' : stats.score >= 50 ? 'text-amber-600' : 'text-rose-600'
                    }`}>
                      {stats.score}/100
                    </span>
                  </div>
                  <span className={`px-2.5 py-1 rounded-md text-xs font-bold uppercase border ${WORST_META[stats.worst].cls}`}>
                    {WORST_META[stats.worst].label}
                  </span>
                </div>

                {/* Severity counts */}
                <div className="flex flex-wrap gap-1.5">
                  {countChip(t('sevMajor', 'major'), stats.major, 'bg-rose-50 text-rose-700 border-rose-200')}
                  {countChip(t('sevModerate', 'moderate'), stats.moderate, 'bg-amber-50 text-amber-700 border-amber-200')}
                  {countChip(t('sevMinor', 'minor'), stats.minor, 'bg-sky-50 text-sky-700 border-sky-200')}
                  {countChip(t('sevEvidence', 'evidence'), stats.evidence, 'bg-indigo-50 text-indigo-700 border-indigo-200')}
                  {stats.major + stats.moderate + stats.minor + stats.evidence === 0 && (
                    <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                      <Check className="w-3 h-3" />
                      <span>{t('noInteractions', 'No interactions vs your medications')}</span>
                    </span>
                  )}
                </div>

                {/* Top interactions */}
                {product.medMatch!.interactions.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="text-xs font-bold text-slate-600 uppercase tracking-wider">
                      {t('topInteractions', 'Key Interactions')}
                    </h4>
                    <div className="space-y-1.5">
                      {[...product.medMatch!.interactions]
                        .sort((x, y) => sevRank(x.severity) - sevRank(y.severity))
                        .slice(0, 3)
                        .map((it, idx) => {
                          const tone = it.severity === 'major'
                            ? 'border-rose-200 bg-rose-50'
                            : it.severity === 'moderate'
                              ? 'border-amber-200 bg-amber-50'
                              : it.severity === 'minor'
                                ? 'border-sky-200 bg-sky-50'
                                : 'border-indigo-200 bg-indigo-50';
                          return (
                            <div key={idx} className={`p-2.5 rounded-lg border text-xs shadow-2xs ${tone}`}>
                              <div className="flex items-center justify-between gap-2">
                                <span className="font-bold text-slate-900 truncate">
                                  {it.a.label} <span className="text-slate-400">×</span> {it.b.label}
                                </span>
                                <span className={`shrink-0 px-2 py-0.5 rounded-full font-bold text-[10px] uppercase ${
                                  it.severity === 'major' ? 'bg-rose-600 text-white'
                                  : it.severity === 'moderate' ? 'bg-amber-500 text-white'
                                  : it.severity === 'minor' ? 'bg-sky-500 text-white'
                                  : 'bg-indigo-500 text-white'
                                }`}>
                                  {it.severity ?? t('sevEvidence', 'Evidence')}
                                </span>
                              </div>
                              {(it.effect || it.mechanism) && (
                                <p className="mt-1 text-slate-600 line-clamp-2">{it.effect || it.mechanism}</p>
                              )}
                            </div>
                          );
                        })}
                    </div>
                  </div>
                )}

                {/* Engine signals */}
                {(stats.cascades > 0 || stats.scheduleConflicts > 0 || stats.qtWorst || stats.beersAvoid + stats.beersCaution > 0 || stats.depletions > 0 || stats.electrolytes > 0) && (
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {stats.qtWorst && (
                      <div className="p-2.5 rounded-lg bg-white border border-slate-200 flex items-center gap-2 shadow-2xs">
                        <Heart className={`w-4 h-4 shrink-0 ${stats.qtWorst === 'high' ? 'text-rose-600' : 'text-amber-500'}`} />
                        <span className="font-semibold text-slate-700">
                          {t('qtRiskLabel', 'QT risk')}: {stats.qtWorst}
                        </span>
                      </div>
                    )}
                    {stats.cascades > 0 && (
                      <div className="p-2.5 rounded-lg bg-white border border-slate-200 flex items-center gap-2 shadow-2xs">
                        <GitBranch className="w-4 h-4 shrink-0 text-violet-600" />
                        <span className="font-semibold text-slate-700">
                          {stats.cascades} {t('cascadeChains', 'cascade chains')}
                        </span>
                      </div>
                    )}
                    {stats.scheduleConflicts > 0 && (
                      <div className="p-2.5 rounded-lg bg-white border border-slate-200 flex items-center gap-2 shadow-2xs">
                        <CalendarClock className="w-4 h-4 shrink-0 text-blue-600" />
                        <span className="font-semibold text-slate-700">
                          {stats.scheduleConflicts} {t('scheduleConflicts', 'schedule conflicts')}
                        </span>
                      </div>
                    )}
                    {stats.depletions > 0 && (
                      <div className="p-2.5 rounded-lg bg-white border border-slate-200 flex items-center gap-2 shadow-2xs">
                        <Pill className="w-4 h-4 shrink-0 text-teal-600" />
                        <span className="font-semibold text-slate-700">
                          {stats.depletions} {t('nutrientDepletions', 'nutrient depletions')}
                        </span>
                      </div>
                    )}
                    {stats.electrolytes > 0 && (
                      <div className="p-2.5 rounded-lg bg-white border border-slate-200 flex items-center gap-2 shadow-2xs">
                        <Droplet className="w-4 h-4 shrink-0 text-cyan-600" />
                        <span className="font-semibold text-slate-700">
                          {stats.electrolytes} {t('electrolyteFlags', 'electrolyte flags')}
                        </span>
                      </div>
                    )}
                    {userProfile.age != null && userProfile.age >= 65 && stats.beersAvoid + stats.beersCaution > 0 && (
                      <div className="col-span-2 p-2.5 rounded-lg bg-amber-50 border border-amber-200 flex items-center gap-2 shadow-2xs">
                        <AlertTriangle className="w-4 h-4 shrink-0 text-amber-600" />
                        <span className="font-semibold text-amber-800">
                          {t('beersFlag', 'Beers Criteria (65+)')}: {stats.beersAvoid} {t('beersAvoid', 'avoid')} · {stats.beersCaution} {t('beersCaution', 'caution')}
                        </span>
                      </div>
                    )}
                  </div>
                )}

                {/* Evidence sources footnote */}
                {product.medMatch!.interactions.some(i => i.source || i.doi) && (
                  <div className="flex items-center gap-1.5 text-[10px] text-slate-400 font-medium">
                    <BookOpen className="w-3 h-3" />
                    <span>{t('medEvidenceNote', 'Sources: SUPP.AI · DDInter · DailyMed · FDA — see Evidence modal per scan')}</span>
                  </div>
                )}
              </>
            ) : (
              <>
                {/* Legacy fallback: not yet MedMatch-analyzed */}
                <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between shadow-2xs">
                  <div>
                    <span className="block text-[10px] text-slate-500 uppercase font-semibold">{t('avgScoreMetric', 'Score')}</span>
                    <span className={`text-2xl font-black ${
                      product.matchAssessment.score >= 80 ? 'text-emerald-700' : product.matchAssessment.score >= 50 ? 'text-amber-600' : 'text-rose-600'
                    }`}>
                      {product.matchAssessment.score}/100
                    </span>
                  </div>
                  <span className={`px-2.5 py-1 rounded-md text-xs font-bold uppercase ${
                    product.matchAssessment.status === 'safe'
                      ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                      : 'bg-rose-100 text-rose-800 border border-rose-200'
                  }`}>
                    {product.matchAssessment.status}
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 italic px-1">
                  {t('notAnalyzedNote', 'Not yet MedMatch-analyzed — rescan this product to compare by medical interactions.')}
                </p>
                <div className="space-y-2">
                  <h4 className="text-xs font-bold text-slate-600 uppercase tracking-wider">
                    {t('statusWarning', 'Flagged Items')} ({product.matchAssessment.warnings.length})
                  </h4>
                  {product.matchAssessment.warnings.length > 0 ? (
                    <div className="space-y-1.5">
                      {product.matchAssessment.warnings.map(w => (
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
              </>
            )}
          </div>
        ) : (
          <div className="p-10 text-center border-2 border-dashed border-slate-200 rounded-xl space-y-3 bg-slate-50">
            <p className="text-xs text-slate-500 font-medium">{noProductText}</p>
            <button
              onClick={openSelector}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs rounded-lg transition-colors shadow-sm cursor-pointer"
            >
              {selectText}
            </button>
          </div>
        )}
      </div>
    );
  };

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
              {t('compareSubtitle', 'Two products ranked by drug–supplement interaction burden against your current medications (MedMatch 7-layer engine), then by allergy conflicts.')}
            </p>
          </div>
        </div>
        {partialCoverage && (
          <div className="mt-4 flex items-start gap-2 p-3 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-amber-600" />
            <span className="font-medium">
              {t('comparePartialCoverage', 'One option has no MedMatch analysis yet — verdict falls back to the legacy allergy score until both are rescanned.')}
            </span>
          </div>
        )}
        {verdictLine && (
          <div className="mt-4 flex items-start gap-2 p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-700">
            <AlertOctagon className="w-4 h-4 shrink-0 mt-0.5 text-slate-400" />
            <span className="font-medium">{verdictLine}</span>
          </div>
        )}
      </div>

      {/* Comparison Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {renderPanel('A', productA, statsA)}
        {renderPanel('B', productB, statsB)}
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
                    {scan.medMatch && (
                      <span className={`text-[10px] font-bold ${
                        scan.medMatch.interactions.some(i => i.severity === 'major')
                          ? 'text-rose-600'
                          : scan.medMatch.interactions.length > 0
                            ? 'text-amber-600'
                            : 'text-emerald-600'
                      }`}>
                        {scan.medMatch.interactions.length} {t('medInteractions', 'med interactions')}
                      </span>
                    )}
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

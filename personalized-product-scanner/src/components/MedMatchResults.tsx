import React, { useEffect, useState } from 'react';
import { MedMatchAnalysis, MedMatchClinicalSummary, MedMatchEvidenceIntersection, MedMatchInteraction, MedMatchSeverity, SupportedLanguage, UserProfile } from '../types';
import { getTranslation, localizeText } from '../i18n';
import { CascadeAnalysisModal } from './CascadeAnalysisModal';
import { ScheduleOptimizerModal } from './ScheduleOptimizerModal';
import {
  AlertOctagon,
  AlertTriangle,
  Info,
  Activity,
  BookOpen,
  Droplet,
  ShieldCheck,
  Heart,
  Zap,
  Users,
  GitBranch,
  CalendarClock,
  Database,
} from 'lucide-react';

interface MedMatchResultsProps {
  analysis?: MedMatchAnalysis;
  language?: SupportedLanguage;
  profile?: UserProfile;
  onRecoveryMode?: (mode: 'photo' | 'text') => void;
}

const SEVERITY_STYLES: Record<MedMatchSeverity, { box: string; badge: string; icon: React.ReactNode }> = {
  major: {
    box: 'border-rose-300 bg-rose-50',
    badge: 'bg-rose-600 text-white',
    icon: <AlertOctagon className="w-4 h-4 text-rose-600" />,
  },
  moderate: {
    box: 'border-amber-300 bg-amber-50',
    badge: 'bg-amber-500 text-white',
    icon: <AlertTriangle className="w-4 h-4 text-amber-600" />,
  },
  minor: {
    box: 'border-sky-300 bg-sky-50',
    badge: 'bg-sky-500 text-white',
    icon: <Info className="w-4 h-4 text-sky-600" />,
  },
};

const SEV_ORDER: (MedMatchSeverity | 'evidence' | null)[] = ['major', 'moderate', 'minor', 'evidence'];

function sevRank(sev: MedMatchSeverity | null) {
  const idx = SEV_ORDER.indexOf(sev ?? 'evidence');
  return idx === -1 ? 99 : idx;
}

/** Medical interaction results from the MedMatch FastAPI backend (7-layer logic). */
export const MedMatchResults: React.FC<MedMatchResultsProps> = ({ analysis, language = 'en', profile, onRecoveryMode }) => {
  const [isCascadeOpen, setIsCascadeOpen] = useState(false);
  const [isScheduleOpen, setIsScheduleOpen] = useState(false);
  const [intersections, setIntersections] = useState<MedMatchEvidenceIntersection[]>([]);
  const [supplemental, setSupplemental] = useState<Record<string, MedMatchClinicalSummary>>({});
  const [supplementalLoading, setSupplementalLoading] = useState(false);
  const targets = Array.from(new Map(
    (analysis?.matched || [])
      .filter((item) => item.kind === 'drug_class' && item.id)
      .map((item) => [item.id, item])
  ).values());

  useEffect(() => {
    let ignore = false;
    setIntersections([]);
    setSupplemental({});
    if (!targets.length) return () => { ignore = true; };
    const load = async () => {
      setSupplementalLoading(true);
      const [intersectionRows, summaryRows] = await Promise.all([
        Promise.all(targets.map(async (target) => {
          try {
            const response = await fetch(`/api/drug/${encodeURIComponent(target.id)}/evidence-intersection?limit=5`);
            if (!response.ok) return [];
            const payload = await response.json();
            if (payload.status !== 'evidence_intersection_found' || !Array.isArray(payload.ingredients)) return [];
            return payload.ingredients.map((item: MedMatchEvidenceIntersection) => ({ ...item, drug_id: target.id, drug_label: target.label }));
          } catch { return []; }
        })),
        Promise.all(targets.slice(0, 8).map(async (target) => {
          try {
            const response = await fetch(`/api/drug/${encodeURIComponent(target.id)}/clinical-summary?limit=5`);
            if (!response.ok) return null;
            const payload = await response.json() as MedMatchClinicalSummary;
            return [target.id, payload] as const;
          } catch { return null; }
        })),
      ]);
      if (ignore) return;
      setIntersections(intersectionRows.flat());
      setSupplemental(Object.fromEntries(summaryRows.filter((item): item is readonly [string, MedMatchClinicalSummary] => Boolean(item))));
      setSupplementalLoading(false);
    };
    void load();
    return () => { ignore = true; };
  }, [analysis]);

  if (!analysis) return null;
  const t = (key: Parameters<typeof getTranslation>[1]) => getTranslation(language as SupportedLanguage, key);
  const localize = (text: string) => localizeText(language, text);
  const interactions = [...analysis.interactions].sort(
    (a, b) => sevRank(a.severity) - sevRank(b.severity)
  );
  const clinicalInteractionCount = interactions.filter((item) => Boolean(item.severity)).length;
  const evidenceCount = interactions.length - clinicalInteractionCount;
  const depletions = analysis.depletions || [];
  const isUnknown = analysis.result === 'unknown_unmatched' || analysis.unmatched.length > 0;

  const context = analysis.patientContext;
  const personalization = analysis.personalization;
  const contextMeds = context?.medications || [];
  const contextLabs = context?.labs || [];
  const contextConditions = context?.conditions || [];
  const contextMissing = personalization?.missingContext || [];

  return (
    <div className="space-y-3">
      <div className="flex items-center space-x-2">
        <Activity className="w-4 h-4 text-teal-700" />
        <h3 className="text-xs font-bold uppercase tracking-wider text-teal-900">
          MedMatch AI — Interaction Check ({clinicalInteractionCount})
        </h3>
        {evidenceCount > 0 && (
          <span className="text-[10px] font-semibold text-indigo-700">
            · {evidenceCount} {t('sevEvidence')}
          </span>
        )}
      </div>
      {interactions.length === 0 && depletions.length === 0 && (
        <div className={`p-4 rounded-xl border text-sm flex items-start space-x-2 ${
          isUnknown
            ? 'bg-amber-50 border-amber-300 text-amber-900'
            : 'bg-slate-50 border-slate-300 text-slate-800'
        }`}>
          {isUnknown ? <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" /> : <Info className="w-4 h-4 mt-0.5 shrink-0" />}
          <div>
            <p className="font-semibold">
              {isUnknown
                ? t('unknownInteraction')
                : t('noDocumentedInteraction')}
            </p>
            <p className="mt-1 text-xs">
              {localize(analysis.message || t('notProofSafe'))}
            </p>
            {isUnknown && (
              <div className="mt-3 flex min-w-0 flex-wrap gap-2">
                <button type="button" onClick={() => onRecoveryMode?.('photo')} className="rounded-lg bg-amber-700 px-3 py-2 text-xs font-bold text-white hover:bg-amber-800">
                  {t('tryOcrPhoto')}
                </button>
                <button type="button" onClick={() => onRecoveryMode?.('text')} className="rounded-lg border border-amber-400 bg-white px-3 py-2 text-xs font-bold text-amber-900 hover:bg-amber-100">
                  {t('enterProductName')}
                </button>
                <span className="self-center text-[11px] text-amber-800">{t('suggestMissing')}</span>
              </div>
            )}
          </div>
        </div>
      )}
      {(analysis.checkedSources?.length || analysis.dataFreshness?.generatedAt) && (
        <div className="text-[10px] text-slate-500 space-y-0.5">
          {analysis.checkedSources?.length ? (
            <p>{t('sourcesChecked')}: {analysis.checkedSources.join(' · ')} ({analysis.coverage || 'partial'} coverage)</p>
          ) : null}
          {analysis.dataFreshness?.generatedAt ? (
            <p>{t('dataChecked')}: {new Date(analysis.dataFreshness.generatedAt).toLocaleString(language)}</p>
          ) : null}
        </div>
      )}
      {(context || personalization) && (
        <section data-testid="personalization-context" className="min-w-0 rounded-xl border border-teal-200 bg-teal-50/70 p-4 text-teal-950">
          <div className="flex min-w-0 flex-wrap items-start justify-between gap-2">
            <div className="flex min-w-0 items-center gap-2">
              <ShieldCheck className="h-4 w-4 shrink-0 text-teal-700" />
              <h4 className="text-xs font-bold uppercase tracking-wider">{t('appliedContext')}</h4>
            </div>
            {personalization?.personalizedUrgency && (
              <span className={`rounded-full px-2 py-1 text-[10px] font-black uppercase ${
                personalization.personalizedUrgency === 'high'
                  ? 'bg-red-100 text-red-800'
                  : personalization.personalizedUrgency === 'moderate'
                    ? 'bg-amber-100 text-amber-800'
                    : personalization.personalizedUrgency === 'unknown'
                      ? 'bg-slate-200 text-slate-700'
                      : 'bg-emerald-100 text-emerald-800'
              }`}>
                {t('personalizedUrgency')}: {personalization.personalizedUrgency}
              </span>
            )}
          </div>
          <p className="mt-1 text-xs text-teal-800">
            {t('profileContext')}: <strong>{profile?.name || t('activeProfile')}</strong>. {t('contextDisclaimer')}
          </p>
          <div className="mt-3 grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-2">
            <div className="min-w-0 rounded-lg bg-white/70 p-2 text-xs">
              <span className="font-semibold">{t('medicationsLabel')}</span>
              <div className="mt-1 space-y-1">
                {contextMeds.length > 0 ? contextMeds.map((med, index) => (
                  <p key={`${med.ingredient || med.brand || 'med'}-${index}`} className="break-words">
                    {med.ingredient || med.brand || t('unknownMedication')}
                    {med.strength || med.dose || med.route || med.frequency || med.timing || med.formulation
                      ? ` · ${[med.strength, med.dose && `${med.dose}${med.unit ? ` ${med.unit}` : ''}`, med.route, med.formulation, med.frequency, med.timing].filter(Boolean).join(' · ')}`
                      : ''}
                  </p>
                )) : <p className="text-slate-600">{t('addMedications')}</p>}
              </div>
            </div>
            <div className="min-w-0 rounded-lg bg-white/70 p-2 text-xs">
              <span className="font-semibold">{t('pregnancyLactation')}</span>
              <p className="mt-1 break-words">
                {context?.pregnancy?.status || context?.lactation?.status
                  ? `${context?.pregnancy?.status || t('unknownValue')} / ${context?.lactation?.status || t('unknownValue')}`
                  : `${t('unknownValue')} / ${t('unknownValue')}`}
              </p>
            </div>
            <div className="min-w-0 rounded-lg bg-white/70 p-2 text-xs">
              <span className="font-semibold">{t('renalHepatic')}</span>
              <p className="mt-1 break-words">
                {context?.renal?.status || context?.renal?.eGFR || context?.hepatic?.status
                  ? `${context?.renal?.status || (context?.renal?.eGFR ? `eGFR ${context.renal.eGFR}` : t('unknownValue'))} / ${context?.hepatic?.status || t('unknownValue')}`
                  : `${t('unknownValue')} / ${t('unknownValue')}`}
              </p>
            </div>
            <div className="min-w-0 rounded-lg bg-white/70 p-2 text-xs">
              <span className="font-semibold">{t('conditions')}</span>
              <p className="mt-1 break-words">{contextConditions.length ? contextConditions.join(', ') : t('noConditions')}</p>
            </div>
          </div>
          {(personalization?.reasons?.length || contextMissing.length) ? (
            <div className="mt-3 space-y-2">
              {personalization?.reasons?.map((item, index) => (
                <div key={`${item.factor}-${index}`} className="rounded-lg border border-teal-200 bg-white/70 p-2 text-xs">
                  <span className="font-bold">{item.factor}</span>
                  {item.impact ? <span className="ml-2 font-semibold uppercase text-amber-700">{item.impact}</span> : null}
                  <p className="mt-0.5 break-words">{item.reason}</p>
                </div>
              ))}
              {contextMissing.length > 0 && (
                <p className="rounded-lg border border-dashed border-amber-300 bg-amber-50 p-2 text-xs text-amber-900">
                  {t('missingContext')}: {contextMissing.join(', ')}. {t('contextDisclaimer')}
                </p>
              )}
            </div>
          ) : null}
          {contextLabs.length > 0 && (
            <div className="mt-3 rounded-lg bg-white/70 p-2 text-xs">
              <span className="font-semibold">{t('labContext')}</span>
              <div className="mt-1 space-y-1">
                {contextLabs.map((lab, index) => (
                  <p key={`${lab.name || 'lab'}-${index}`} className="break-words">
                    {lab.name || t('unknownTest')}: {lab.value == null ? t('unknownValue') : String(lab.value)} {lab.unit || ''}
                    {lab.observedAt ? ` · ${lab.observedAt}` : ''}
                    {lab.referenceRange ? ` · ${t('referenceShort')} ${lab.referenceRange}` : ''}
                  </p>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {/* ⑥ Beers Criteria (backend gates on age >= 65) */}
      {(analysis.beers?.length || 0) > 0 && (
        <div className="p-4 rounded-xl bg-orange-50 border border-orange-300 space-y-2">
          <div className="flex items-center space-x-2">
            <Users className="w-4 h-4 text-orange-700" />
            <h4 className="text-xs font-bold uppercase tracking-wider text-orange-900">
              Beers Criteria — Age 65+ Medication Review
            </h4>
          </div>
          {analysis.beers!.map((b, i) => (
            <div key={i} className="text-xs text-orange-900 space-y-0.5">
              <span className={`inline-block px-1.5 py-0.5 rounded text-[9px] font-black uppercase mr-1.5 ${
                b.level === 'avoid' ? 'bg-orange-700 text-white' : 'bg-orange-200 text-orange-900'
              }`}>
                {b.level}
              </span>
              <span className="font-bold">{b.label}</span>
              <p className="text-orange-800">{b.note}</p>
            </div>
          ))}
        </div>
      )}

      {/* ③ QT Prolongation Risk */}
      {(analysis.qt_risk?.length || 0) > 0 && analysis.qt_risk![0].qt_classes.length > 0 && (() => {
        const qt = analysis.qt_risk![0];
        const color = qt.level === 'high' ? 'bg-rose-50 border-rose-300 text-rose-900'
          : qt.level === 'moderate' ? 'bg-amber-50 border-amber-300 text-amber-900'
          : 'bg-slate-50 border-slate-300 text-slate-800';
        return (
          <div className={`p-4 rounded-xl border space-y-2 ${color}`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Heart className={`w-4 h-4 ${qt.level === 'high' ? 'text-rose-700' : 'text-amber-700'}`} />
                <h4 className="text-xs font-bold uppercase tracking-wider">QT Prolongation Risk</h4>
              </div>
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-black uppercase ${
                qt.level === 'high' ? 'bg-rose-600 text-white' : qt.level === 'moderate' ? 'bg-amber-600 text-white' : 'bg-slate-600 text-white'
              }`}>
                {qt.level}
              </span>
            </div>
            <p className="text-xs font-semibold">QT-prolonging items: {qt.qt_classes.join(', ')}</p>
            {qt.factors.length > 0 && (
              <p className="text-xs opacity-80">Additive patient factors: {qt.factors.join(' · ')}</p>
            )}
            {qt.level !== 'low' && (
              <p className="text-xs font-semibold">Discuss an ECG / electrolyte check with your prescriber before adding more QT drugs.</p>
            )}
          </div>
        );
      })()}

      {/* ④ Electrolyte Depletion */}
      {(analysis.electrolytes?.length || 0) > 0 && (
        <div className="p-4 rounded-xl bg-yellow-50 border border-yellow-300 space-y-2">
          <div className="flex items-center space-x-2">
            <Zap className="w-4 h-4 text-yellow-700" />
            <h4 className="text-xs font-bold uppercase tracking-wider text-yellow-900">
              Electrolyte Depletion Watch
            </h4>
          </div>
          {analysis.electrolytes!.map((e, i) => (
            <div key={i} className="text-xs text-yellow-900 space-y-0.5">
              <span className="font-bold">⚡ {e.electrolyte}</span>
              <span className="text-yellow-700"> — from: {e.sources.join(', ')}</span>
              {e.secondary_risk ? <p className="text-yellow-800">{e.secondary_risk}</p> : null}
            </div>
          ))}
        </div>
      )}

      {/* ① Cascade chains + ② Schedule conflicts (modal triggers) */}
      {(analysis.cascades?.length || 0) > 0 && (
        <button
          onClick={() => setIsCascadeOpen(true)}
          className="w-full p-3 rounded-xl bg-indigo-50 border border-indigo-200 text-xs font-bold text-indigo-900 hover:bg-indigo-100 transition-colors flex items-center justify-center space-x-2"
        >
          <GitBranch className="w-4 h-4" />
          <span>{analysis.cascades!.length} multi-step enzyme cascade(s) detected — view chain analysis</span>
        </button>
      )}

      {(analysis.schedule?.length || 0) > 0 && (
        <button
          onClick={() => setIsScheduleOpen(true)}
          className="w-full p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-xs font-bold text-emerald-900 hover:bg-emerald-100 transition-colors flex items-center justify-center space-x-2"
        >
          <CalendarClock className="w-4 h-4" />
          <span>{analysis.schedule!.length} timing conflict(s) resolvable by schedule — view plan</span>
        </button>
      )}

      {interactions.map((inter, idx) => (
        <InteractionCard key={idx} inter={inter} />
      ))}

      {intersections.length > 0 && (
        <div data-testid="multi-source-evidence" className="p-4 rounded-xl bg-indigo-50 border border-indigo-200 space-y-2">
          <div className="flex items-center space-x-2">
            <Database className="w-4 h-4 text-indigo-700" />
            <h4 className="text-xs font-bold uppercase tracking-wider text-indigo-900">
              Multi-source evidence
            </h4>
          </div>
          <p className="text-xs text-indigo-900">
            Ingredient-level overlap across OnSIDES, FAERS and FDA label data. This is not a safety clearance.
          </p>
          {intersections.map((item) => (
            <div key={`${item.drug_id}-${item.ingredient_id}`} className="p-3 rounded-lg bg-white border border-indigo-100 space-y-1">
              <p className="text-xs font-bold text-slate-900">
                {item.drug_label}: {item.ingredient_name}
              </p>
              <p className="text-[11px] text-indigo-800 font-semibold">
                {item.sources.join(' + ')} · {item.source_count} sources
              </p>
              <p className="text-[11px] text-slate-600">
                OnSIDES effects: {item.onsides_effect_count} · FAERS cases: {item.faers_case_count} · FDA labels: {item.label_count}
              </p>
              <p className="text-[10px] text-slate-500">
                RxNorm exact match · {item.ontology_version}
              </p>
            </div>
          ))}
          <p className="text-[10px] text-slate-500">
            Sources are summarized separately; no unvalidated MedDRA/text crosswalk is applied.
          </p>
        </div>
      )}

      {(supplementalLoading || Object.keys(supplemental).length > 0) && (
        <div data-testid="supplemental-clinical-evidence" className="p-4 rounded-xl bg-slate-50 border border-slate-300 space-y-3">
          <div className="flex items-center space-x-2">
            <BookOpen className="w-4 h-4 text-slate-700" />
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-900">Clinical reference layers</h4>
            {supplementalLoading && <span className="text-[10px] text-slate-500">Loading…</span>}
          </div>
          <p className="text-[11px] text-slate-600">ATC, mechanism, label, lactation, recall and CAERS data are shown as separate reference layers—not as one safety score.</p>
          {targets.slice(0, 8).map((target) => {
            const summary = supplemental[target.id];
            const layers = summary?.layers;
            const indications = layers?.indications?.indications || [];
            const lactation = layers?.lactation?.records || [];
            const recalls = layers?.recalls?.recalls || [];
            const caers = layers?.caers?.events || [];
            const atc = layers?.atc?.atc || [];
            const mechanisms = layers?.mechanism?.targets || [];
            const productScope = summary?.scope !== 'drug_class';
            return (
              <div key={target.id} className="p-3 rounded-lg bg-white border border-slate-200 space-y-2">
                <p className="text-xs font-bold text-slate-900">{target.label}</p>
                {summary?.scope === 'drug_class' && <p className="text-[10px] text-slate-500">Class-level examples — verify exact ingredient, strength, route and formulation.</p>}
                {atc.length > 0 && <p className="text-[11px] text-slate-700"><span className="font-semibold">ATC:</span> {atc.slice(0, 3).map((item) => item.atc_code).join(' · ')}</p>}
                {mechanisms.length > 0 && <p className="text-[11px] text-slate-700"><span className="font-semibold">Targets/MOA:</span> {mechanisms.slice(0, 3).map((item) => `${item.target_name || 'target'}${item.action_type ? ` (${item.action_type})` : ''}`).join(' · ')}</p>}
                {productScope && indications.length > 0 && <p className="text-[11px] text-slate-700"><span className="font-semibold">FDA indication:</span> {String(indications[0].indications_and_usage || '').slice(0, 360)}</p>}
                {productScope && lactation.length > 0 && <div className="rounded-md bg-blue-50 border border-blue-100 p-2 text-[11px] text-blue-950"><span className="font-semibold">LactMed:</span> {String(lactation[0].summary_of_use || '').slice(0, 360)} <a className="font-semibold underline" href={lactation[0].source_url || '#'} target="_blank" rel="noreferrer">Source</a></div>}
                {productScope && recalls.length > 0 && <div className="rounded-md bg-rose-50 border border-rose-200 p-2 text-[11px] text-rose-950"><span className="font-semibold">FDA recall signal:</span> {recalls.length} record(s). {String(recalls[0].reason_for_recall || '').slice(0, 240)} <a className="font-semibold underline" href={recalls[0].source_url || '#'} target="_blank" rel="noreferrer">Verify notice</a></div>}
                {productScope && caers.length > 0 && <div className="rounded-md bg-amber-50 border border-amber-200 p-2 text-[11px] text-amber-950"><span className="font-semibold">CAERS signal:</span> {caers[0].reaction} ({caers[0].case_count} case(s)); reports are unvalidated and do not prove causality.</div>}
                {!summary && supplementalLoading && <p className="text-[11px] text-slate-500">Loading reference data…</p>}
                {summary && !atc.length && !mechanisms.length && !indications.length && !lactation.length && !recalls.length && !caers.length && <p className="text-[11px] text-slate-500">No matching supplemental record; this is unknown, not a safety clearance.</p>}
              </div>
            );
          })}
        </div>
      )}

      {depletions.length > 0 && (
        <div className="p-4 rounded-xl bg-violet-50 border border-violet-200 space-y-2">
          <div className="flex items-center space-x-2">
            <Droplet className="w-4 h-4 text-violet-700" />
            <h4 className="text-xs font-bold uppercase tracking-wider text-violet-900">
              Nutrient depletion watch
            </h4>
          </div>
          {depletions.slice(0, 8).map((d, i) => (
            <div key={i} className="text-xs text-violet-900 space-y-0.5">
              <span className="font-bold">
                {t('mayDeplete')}: {d.ingredient}
              </span>
              {d.effect_size ? <span className="text-violet-700"> ({d.effect_size})</span> : null}
              {d.mechanism ? <p className="text-violet-600">{d.mechanism}</p> : null}
            </div>
          ))}
        </div>
      )}

      {analysis.unmatched?.length > 0 && (
        <p className="text-xs text-slate-500">
          {t('unrecognized')}: {analysis.unmatched.slice(0, 8).join(', ')}
        </p>
      )}

      <CascadeAnalysisModal
        isOpen={isCascadeOpen}
        onClose={() => setIsCascadeOpen(false)}
        cascades={analysis.cascades || []}
        language={language}
      />

      <ScheduleOptimizerModal
        isOpen={isScheduleOpen}
        onClose={() => setIsScheduleOpen(false)}
        conflicts={analysis.schedule || []}
        language={language}
      />
    </div>
  );
};

function InteractionCard({ inter }: { inter: MedMatchInteraction }) {
  const sev = inter.severity;
  const isEvidence = !sev;
  const style = sev ? SEVERITY_STYLES[sev] : null;

  return (
    <div
      className={`p-3.5 rounded-xl border text-xs space-y-1.5 ${
        style ? style.box : 'border-indigo-200 bg-indigo-50'
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-bold text-slate-900">
          {inter.a.label} <span className="text-slate-400">×</span> {inter.b.label}
        </span>
        <span
          className={`shrink-0 px-2 py-0.5 rounded-full font-bold text-[10px] uppercase tracking-wide ${
            style ? style.badge : 'bg-indigo-500 text-white'
          }`}
        >
          {sev ? sev : 'Evidence'}
        </span>
      </div>

      {inter.effect && <p className="text-slate-700">{inter.effect}</p>}
      {inter.mechanism && (
        <p className="text-slate-500">
          <span className="font-semibold">Why:</span> {inter.mechanism}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-500">
        {inter.source && (
          <span className="inline-flex items-center gap-1">
            <BookOpen className="w-3 h-3" /> {inter.source}
          </span>
        )}
        {inter.trust != null && <span>Trust: {inter.trust.toFixed(1)}</span>}
        {inter.doi && <span className="truncate max-w-[200px]">DOI: {inter.doi}</span>}
        {inter.enzyme && <span>CYP: {inter.enzyme}</span>}
        {inter.timing === 'separated' && (
          <span className="font-semibold text-emerald-700">
            ✓ taken at different times — separating doses reduces risk
          </span>
        )}
      </div>

      {inter.action && (
        <p className={`font-semibold ${sev === 'major' ? 'text-rose-700' : 'text-slate-700'}`}>
          {inter.action}
        </p>
      )}
    </div>
  );
}

import React, { useState } from 'react';
import { MedMatchAnalysis, MedMatchInteraction, MedMatchSeverity, SupportedLanguage } from '../types';
import { getTranslation } from '../i18n';
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
} from 'lucide-react';

interface MedMatchResultsProps {
  analysis?: MedMatchAnalysis;
  language?: SupportedLanguage;
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
export const MedMatchResults: React.FC<MedMatchResultsProps> = ({ analysis, language = 'en' }) => {
  if (!analysis) return null;
  const t = (key: Parameters<typeof getTranslation>[1]) => getTranslation(language as SupportedLanguage, key);
  const interactions = [...analysis.interactions].sort(
    (a, b) => sevRank(a.severity) - sevRank(b.severity)
  );
  const depletions = analysis.depletions || [];
  const [isCascadeOpen, setIsCascadeOpen] = useState(false);
  const [isScheduleOpen, setIsScheduleOpen] = useState(false);

  return (
    <div className="space-y-3">
      <div className="flex items-center space-x-2">
        <Activity className="w-4 h-4 text-teal-700" />
        <h3 className="text-xs font-bold uppercase tracking-wider text-teal-900">
          MedMatch AI — Interaction Check ({interactions.length})
        </h3>
      </div>

      {interactions.length === 0 && depletions.length === 0 && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-sm text-emerald-800 flex items-center space-x-2">
          <ShieldCheck className="w-4 h-4" />
          <span>No documented interactions found among the recognized ingredients.</span>
        </div>
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

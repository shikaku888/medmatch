import React from 'react';
import { MedMatchScheduleConflict, SupportedLanguage } from '../types';
import { getTranslation } from '../i18n';
import { X, CalendarClock, Clock, AlertTriangle } from 'lucide-react';

interface ScheduleOptimizerModalProps {
  isOpen: boolean;
  onClose: () => void;
  conflicts: MedMatchScheduleConflict[];
  language?: SupportedLanguage;
}

/** ② Schedule Optimizer — separation timing to defuse absorption-type interactions. */
export const ScheduleOptimizerModal: React.FC<ScheduleOptimizerModalProps> = ({
  isOpen,
  onClose,
  conflicts,
  language = 'en'
}) => {
  const t = (key: Parameters<typeof getTranslation>[1]) => getTranslation(language, key);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] shadow-2xl flex flex-col overflow-hidden border border-slate-200">

        {/* Header */}
        <div className="p-5 bg-gradient-to-r from-emerald-900 to-slate-900 text-white flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-emerald-500/20 border border-emerald-400/30 text-emerald-300">
              <CalendarClock className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold tracking-tight">Schedule Optimizer</h2>
              <p className="text-xs text-emerald-200 mt-0.5">
                Separation timing that defuses absorption-type interactions without changing your medication list
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg bg-slate-800/60 text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 overflow-y-auto space-y-4 flex-1 bg-slate-50">
          {conflicts.length === 0 && (
            <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-sm text-emerald-800">
              No timing conflicts — all analyzed items can be taken together.
            </div>
          )}

          {conflicts.map((c, i) => (
            <div key={i} className="p-4 rounded-xl bg-white border border-emerald-200 shadow-2xs space-y-2.5">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-bold text-slate-900">
                  {c.a} <span className="text-slate-400 mx-1">×</span> {c.b}
                </span>
                <span className="shrink-0 inline-flex items-center space-x-1 px-2 py-0.5 rounded-full bg-emerald-600 text-white text-[10px] font-black uppercase">
                  <Clock className="w-3 h-3" />
                  <span>≥ {c.min_hours}h apart</span>
                </span>
              </div>

              <p className="text-xs text-slate-700 flex items-start space-x-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0 mt-0.5" />
                <span>{c.reason}</span>
              </p>

              <div className="p-2.5 rounded-lg bg-emerald-50 border border-emerald-100 text-xs text-emerald-900 font-medium">
                💡 Suggested plan: take <strong>{c.a}</strong> first, then <strong>{c.b}</strong> at least {c.min_hours} hours later
                (e.g. 7:00 → 11:00). If one is morning-only, anchor it first and push the other to the next available slot.
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="p-4 bg-white border-t border-slate-200 flex items-center justify-between text-xs text-slate-500">
          <span>Timing advice only — never change doses without your prescriber.</span>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

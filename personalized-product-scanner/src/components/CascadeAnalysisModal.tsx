import React from 'react';
import { MedMatchCascade, SupportedLanguage } from '../types';
import { getTranslation } from '../i18n';
import { X, GitBranch, ArrowRight, FlaskConical } from 'lucide-react';

interface CascadeAnalysisModalProps {
  isOpen: boolean;
  onClose: () => void;
  cascades: MedMatchCascade[];
  language?: SupportedLanguage;
}

const KIND_ICON: Record<string, string> = {
  herb: '🌿',
  drug_class: '💊',
  food: '🍎',
};

/** ① Cascade Analysis — multi-hop CYP450 enzyme-pathway risk chains. */
export const CascadeAnalysisModal: React.FC<CascadeAnalysisModalProps> = ({
  isOpen,
  onClose,
  cascades,
  language = 'en'
}) => {
  const t = (key: Parameters<typeof getTranslation>[1]) => getTranslation(language, key);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] shadow-2xl flex flex-col overflow-hidden border border-slate-200">

        {/* Header */}
        <div className="p-5 bg-gradient-to-r from-indigo-900 to-slate-900 text-white flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-indigo-500/20 border border-indigo-400/30 text-indigo-300">
              <GitBranch className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold tracking-tight">Cascade Analysis</h2>
              <p className="text-xs text-indigo-200 mt-0.5">
                Enzyme-pathway chains: A → enzyme → B → enzyme → C (mechanism inference, no direct study required)
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
          {cascades.length === 0 && (
            <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-sm text-emerald-800">
              No multi-step enzyme cascades detected among the analyzed items.
            </div>
          )}

          {cascades.map((cascade, i) => (
            <div key={i} className="p-4 rounded-xl bg-white border border-indigo-200 shadow-2xs space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-indigo-900 flex items-center space-x-1.5">
                  <FlaskConical className="w-3.5 h-3.5" />
                  <span>Chain #{i + 1} — CYP{cascade.enzymes.join(' / CYP')}</span>
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-100 text-indigo-800">
                  Trust {cascade.trust.toFixed(1)} · inferred
                </span>
              </div>

              {/* Chain diagram */}
              <div className="flex flex-wrap items-center gap-1.5">
                {cascade.chain.map((node, j) => (
                  <React.Fragment key={j}>
                    {j > 0 && <ArrowRight className="w-3.5 h-3.5 text-slate-400 shrink-0" />}
                    <div className="px-2.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-xs">
                      <span className="font-bold text-slate-900">{KIND_ICON[node.kind] || '•'} {node.label}</span>
                      <span className="block text-[10px] text-slate-500">{node.role}</span>
                    </div>
                  </React.Fragment>
                ))}
              </div>

              <p className="text-xs text-slate-700 bg-indigo-50 border border-indigo-100 p-2.5 rounded-lg">
                {cascade.effect}
              </p>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="p-4 bg-white border-t border-slate-200 flex items-center justify-between text-xs text-slate-500">
          <span>Inferred from CYP450/P-gp pathway data — not direct clinical studies.</span>
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

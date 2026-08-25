import React, { useState, useEffect } from 'react';
import { SupportedLanguage } from '../types';
import { getTranslation } from '../i18n';
import {
  Pill,
  Search,
  ShieldAlert,
  BookOpen,
  Loader2,
  X,
  Leaf,
  AlertTriangle
} from 'lucide-react';

interface HerbDrugModalProps {
  isOpen: boolean;
  onClose: () => void;
  language: SupportedLanguage;
  activeMedications: string[];
  onUpdateMedications?: (meds: string[]) => void;
}

interface HerbSearchHit {
  kind: 'herb' | 'drug_class' | 'food';
  id: string;
  label: string;
  matched_alias: string;
  score: number;
  scientific?: string;
  examples?: string[];
  warns_against?: string[];
}

const KIND_BADGE: Record<HerbSearchHit['kind'], { label: string; cls: string }> = {
  herb: { label: 'Herb', cls: 'bg-emerald-600 text-white' },
  drug_class: { label: 'Drug Class', cls: 'bg-blue-600 text-white' },
  food: { label: 'Food', cls: 'bg-amber-600 text-white' }
};

export const HerbDrugModal: React.FC<HerbDrugModalProps> = ({
  isOpen,
  onClose,
  language,
  activeMedications,
  onUpdateMedications
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [newMedInput, setNewMedInput] = useState('');
  const [results, setResults] = useState<HerbSearchHit[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const t = (key: Parameters<typeof getTranslation>[1]) => getTranslation(language, key);

  // Live compendium search against the MedMatch AI FastAPI backend (debounced).
  useEffect(() => {
    const term = searchTerm.trim();
    if (term.length < 2) {
      setResults([]);
      setSearchError(null);
      setIsSearching(false);
      return;
    }

    let cancelled = false;
    setIsSearching(true);
    setSearchError(null);
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/herb-drug-interactions?q=${encodeURIComponent(term)}`);
        if (!res.ok) throw new Error(`Search failed (${res.status})`);
        const data = await res.json();
        if (!cancelled) {
          setResults(data.results || []);
          setIsSearching(false);
        }
      } catch (err) {
        if (!cancelled) {
          setSearchError(err instanceof Error ? err.message : 'Search failed');
          setResults([]);
          setIsSearching(false);
        }
      }
    }, 300);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [searchTerm]);

  if (!isOpen) return null;

  const handleAddMed = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newMedInput.trim() || !onUpdateMedications) return;
    const clean = newMedInput.trim();
    if (!activeMedications.includes(clean)) {
      onUpdateMedications([...activeMedications, clean]);
    }
    setNewMedInput('');
  };

  const handleRemoveMed = (medToRemove: string) => {
    if (onUpdateMedications) {
      onUpdateMedications(activeMedications.filter(m => m !== medToRemove));
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl max-w-3xl w-full max-h-[90vh] shadow-2xl flex flex-col overflow-hidden border border-slate-200">

        {/* Modal Header */}
        <div className="p-5 bg-gradient-to-r from-rose-900 to-slate-900 text-white flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-rose-500/20 border border-rose-400/30 text-rose-300">
              <Pill className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-lg font-bold tracking-tight">
                  {t('herbDrugRadar')}
                </h2>
                <span className="px-2 py-0.5 rounded text-[10px] font-extrabold bg-rose-500 text-white uppercase">
                  Pharmacovigilance
                </span>
              </div>
              <p className="text-xs text-rose-200 mt-0.5">
                Clinical Pharmacological Interaction & Prescription Shield (CYP450 / P-gp)
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

        <div className="p-6 overflow-y-auto space-y-6 flex-1 bg-slate-50">

          {/* User's Active Prescription Drugs Manager */}
          <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-2xs space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center space-x-2">
                  <ShieldAlert className="w-4 h-4 text-blue-600" />
                  <span>My Active Prescriptions & Medications</span>
                </h3>
                <p className="text-xs text-slate-500">
                  Add medications you are taking to automatically cross-check with foods & supplements.
                </p>
              </div>
              <span className="text-xs font-bold px-2 py-0.5 rounded bg-blue-100 text-blue-800">
                {activeMedications.length} Registered
              </span>
            </div>

            {onUpdateMedications && (
              <form onSubmit={handleAddMed} className="flex gap-2">
                <input
                  type="text"
                  value={newMedInput}
                  onChange={(e) => setNewMedInput(e.target.value)}
                  placeholder="e.g. Warfarin, Sertraline, Atorvastatin, Metformin..."
                  className="flex-1 px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-2 focus:ring-rose-500 bg-white"
                />
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold transition-colors shadow-2xs"
                >
                  Add Rx
                </button>
              </form>
            )}

            <div className="flex flex-wrap gap-2 pt-1">
              {activeMedications.length > 0 ? (
                activeMedications.map((med, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-lg bg-slate-100 text-slate-800 text-xs font-medium border border-slate-200"
                  >
                    <span>💊 {med}</span>
                    {onUpdateMedications && (
                      <button
                        onClick={() => handleRemoveMed(med)}
                        className="text-slate-400 hover:text-rose-600 transition-colors ml-1"
                        title="Remove medication"
                      >
                        ×
                      </button>
                    )}
                  </span>
                ))
              ) : (
                <p className="text-xs text-slate-400 italic">
                  No active prescription medications registered. Type your medication above.
                </p>
              )}
            </div>
          </div>

          {/* Live Clinical Compendium Search (MedMatch AI backend) */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center space-x-2">
              <BookOpen className="w-4 h-4 text-rose-600" />
              <span>Herb-Drug Interaction Compendium (Live)</span>
            </h3>

            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search herbal supplement (Ginkgo, St John's Wort) or medication (Warfarin, Statin)..."
                className="w-full pl-9 pr-4 py-2 text-xs rounded-xl border border-slate-300 focus:outline-hidden focus:ring-2 focus:ring-rose-500 bg-white"
              />
            </div>

            {isSearching && (
              <div className="p-4 rounded-xl bg-white border border-slate-200 text-xs text-slate-500 flex items-center space-x-2">
                <Loader2 className="w-4 h-4 animate-spin text-rose-600" />
                <span>Querying 71,900+ evidence-backed pairs (SUPP.AI, DDInter, iDISK, DailyMed)...</span>
              </div>
            )}

            {searchError && (
              <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-rose-600" />
                <span>{searchError}</span>
              </div>
            )}

            {!isSearching && !searchError && searchTerm.trim().length >= 2 && results.length === 0 && (
              <div className="p-4 rounded-xl bg-slate-100 border border-slate-200 text-xs text-slate-500">
                No matches — try another spelling.
              </div>
            )}

            <div className="space-y-3 pt-1">
              {results.map((item) => (
                <div
                  key={`${item.kind}-${item.id}`}
                  className="p-4 rounded-xl border bg-white border-slate-200 hover:border-slate-300 shadow-2xs space-y-2"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div>
                      <span className="text-sm font-bold text-slate-900 flex items-center space-x-1.5">
                        <Leaf className="w-4 h-4 text-emerald-600" />
                        <span>{item.label}</span>
                      </span>
                      {item.scientific && (
                        <span className="text-xs text-slate-500 italic block mt-0.5">{item.scientific}</span>
                      )}
                    </div>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase shrink-0 ${KIND_BADGE[item.kind].cls}`}>
                      {KIND_BADGE[item.kind].label}
                    </span>
                  </div>

                  {item.warns_against && item.warns_against.length > 0 && (
                    <div className="text-xs p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-900 space-y-1">
                      <p className="font-bold">⚠️ Avoid combining with:</p>
                      <p className="text-rose-800">{item.warns_against.join(', ')}</p>
                    </div>
                  )}

                  {item.examples && item.examples.length > 0 && (
                    <p className="text-[11px] text-slate-500 pt-1 border-t border-slate-100">
                      Common products: {item.examples.join(', ')}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>

        </div>

        {/* Footer */}
        <div className="p-4 bg-white border-t border-slate-200 flex items-center justify-between text-xs text-slate-500">
          <span>Data grounded in SUPP.AI, DDInter, iDISK (MSKCC), DailyMed & FDA FAERS.</span>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold transition-colors"
          >
            Close Radar
          </button>
        </div>

      </div>
    </div>
  );
};

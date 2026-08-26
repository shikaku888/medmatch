import React, { useState, useEffect } from 'react';
import { UserRoutineProduct, RoutineAuditCheckResult, SkincareActiveItem, SupportedLanguage } from '../types';
import { getTranslation } from '../i18n';
import { 
  X, 
  Sparkles, 
  AlertTriangle, 
  CheckCircle2, 
  ShieldCheck, 
  Plus, 
  Trash2, 
  Clock, 
  Sun, 
  Moon, 
  Layers, 
  Calendar, 
  RefreshCw, 
  Zap,
  Info,
  ChevronRight,
  Sparkle
} from 'lucide-react';

interface SkincareRoutineRadarModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectProduct?: (productName: string) => void;
  language?: SupportedLanguage;
}

export const SkincareRoutineRadarModal: React.FC<SkincareRoutineRadarModalProps> = ({
  isOpen,
  onClose,
  language = 'en'
}) => {
  const t = (key: string, fb: string) => getTranslation(language, key, fb);
  const [activeTab, setActiveTab] = useState<'routine' | 'radar' | 'cycling'>('radar');
  const [routine, setRoutine] = useState<UserRoutineProduct[]>([]);
  const [auditResult, setAuditResult] = useState<RoutineAuditCheckResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isAddingNew, setIsAddingNew] = useState(false);

  // New item form state
  const [newName, setNewName] = useState('');
  const [newBrand, setNewBrand] = useState('');
  const [newStep, setNewStep] = useState<UserRoutineProduct['step']>('serum');
  const [newTimeOfDay, setNewTimeOfDay] = useState<UserRoutineProduct['timeOfDay']>('pm');
  const [newActivesInput, setNewActivesInput] = useState('');

  useEffect(() => {
    if (isOpen) {
      loadRoutineAndAudit();
    }
  }, [isOpen]);

  const loadRoutineAndAudit = async () => {
    setIsLoading(true);
    try {
      const res = await fetch('/api/skincare-routine');
      if (res.ok) {
        const data = await res.json();
        setRoutine(data);
        runAudit(data);
      }
    } catch (e) {
      console.warn('Could not load routine:', e);
    } finally {
      setIsLoading(false);
    }
  };

  const runAudit = async (routineList: UserRoutineProduct[]) => {
    try {
      const res = await fetch('/api/skincare-routine/audit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ newActives: [] })
      });
      if (res.ok) {
        const audit = await res.json();
        setAuditResult(audit);
      }
    } catch (e) {
      console.warn('Audit error:', e);
    }
  };

  const handleAddProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;

    const activesArray = newActivesInput
      .split(',')
      .map(s => s.trim())
      .filter(s => s.length > 0);

    const newItem: UserRoutineProduct = {
      id: `routine_${Date.now()}`,
      name: newName.trim(),
      brand: newBrand.trim() || undefined,
      step: newStep,
      timeOfDay: newTimeOfDay,
      activeIngredients: activesArray
    };

    try {
      const res = await fetch('/api/skincare-routine', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newItem)
      });
      if (res.ok) {
        const updated = await res.json();
        setRoutine(updated);
        runAudit(updated);
        setIsAddingNew(false);
        setNewName('');
        setNewBrand('');
        setNewActivesInput('');
      }
    } catch (e) {
      console.warn('Error adding routine item:', e);
    }
  };

  const handleDeleteItem = async (id: string) => {
    try {
      const res = await fetch(`/api/skincare-routine/${id}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        const updated = await res.json();
        setRoutine(updated);
        runAudit(updated);
      }
    } catch (e) {
      console.warn('Error deleting routine item:', e);
    }
  };

  const stepLabels: Record<UserRoutineProduct['step'], string> = {
    cleanser: 'Cleanser',
    toner: 'Toner / Essence',
    serum: 'Treatment Serum',
    treatment: 'Active Treatment (Retinol / AHA / BHA)',
    moisturizer: 'Moisturizer / Cream',
    sunscreen: 'Sunscreen (SPF)',
    mask: 'Facial Mask'
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div 
        id="skincare-routine-radar-modal"
        className="bg-white w-full max-w-4xl rounded-2xl shadow-2xl border border-slate-200 flex flex-col max-h-[92vh] overflow-hidden"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 bg-gradient-to-r from-teal-500/10 via-indigo-500/5 to-transparent flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-teal-500/15 text-teal-800 border border-teal-500/20 shadow-2xs">
              <Sparkles className="w-5 h-5 text-teal-700" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="font-bold text-slate-900 text-base sm:text-lg">
                  {t('skinTitle', 'Skincare Actives Radar & Vanity Shelf')}
                </h3>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-teal-100 text-teal-800 border border-teal-200">
                  Cosmeceutical & Routine Audit
                </span>
              </div>
              <p className="text-xs text-slate-500">
                Check pH clashes, protect the skin moisture barrier, and follow evidence-based 4-Night Skin Cycling.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="px-6 py-2.5 bg-slate-50 border-b border-slate-200 flex items-center space-x-2">
          <button
            onClick={() => setActiveTab('radar')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center space-x-1.5 ${
              activeTab === 'radar' 
                ? 'bg-teal-700 text-white shadow-xs' 
                : 'text-slate-600 hover:bg-slate-200/70'
            }`}
          >
            <Zap className="w-3.5 h-3.5" />
            <span>Active Conflicts & Synergies</span>
            {auditResult && auditResult.conflicts.length > 0 && (
              <span className="px-1.5 py-0.2 rounded-full bg-rose-500 text-white text-[10px]">
                {auditResult.conflicts.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('routine')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center space-x-1.5 ${
              activeTab === 'routine' 
                ? 'bg-teal-700 text-white shadow-xs' 
                : 'text-slate-600 hover:bg-slate-200/70'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>My Vanity Shelf ({routine.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('cycling')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center space-x-1.5 ${
              activeTab === 'cycling' 
                ? 'bg-teal-700 text-white shadow-xs' 
                : 'text-slate-600 hover:bg-slate-200/70'
            }`}
          >
            <Calendar className="w-3.5 h-3.5" />
            <span>4-Night Skin Cycling</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 p-6 overflow-y-auto space-y-5 bg-white">
          {/* TAB 1: CONFLICT & SYNERGY RADAR */}
          {activeTab === 'radar' && (
            <div className="space-y-5">
              {/* Routine Actives Summary Pill Box */}
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-600">
                    All Active Ingredients in Your Routine:
                  </span>
                  <button
                    onClick={() => setActiveTab('routine')}
                    className="text-[11px] font-bold text-teal-700 hover:underline"
                  >
                    + Add Product
                  </button>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {routine.flatMap(r => r.activeIngredients || []).length > 0 ? (
                    Array.from(new Set(routine.flatMap(r => r.activeIngredients || []))).map((act, i) => (
                      <span key={i} className="px-2.5 py-1 rounded-md text-xs font-bold bg-teal-50 text-teal-800 border border-teal-200">
                        {act}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-slate-400 italic">No actives detected yet. Add skincare products in the Vanity Shelf tab.</span>
                  )}
                </div>
              </div>

              {/* Conflicts Section */}
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <AlertTriangle className="w-4 h-4 text-rose-600" />
                  <h4 className="text-xs sm:text-sm font-bold text-slate-900 uppercase tracking-wider">
                    Active Ingredient Warnings & Conflicts ({auditResult?.conflicts.length || 0})
                  </h4>
                </div>

                {auditResult && auditResult.conflicts.length > 0 ? (
                  <div className="grid grid-cols-1 gap-3">
                    {auditResult.conflicts.map((conf, idx) => (
                      <div 
                        key={idx}
                        className={`p-4 rounded-xl border ${
                          conf.severity === 'high' 
                            ? 'bg-rose-50/50 border-rose-200' 
                            : 'bg-amber-50/50 border-amber-200'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="space-y-1.5 flex-1">
                            <div className="flex items-center space-x-2">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold uppercase ${
                                conf.severity === 'high' ? 'bg-rose-600 text-white' : 'bg-amber-600 text-white'
                              }`}>
                                {conf.severity === 'high' ? 'Strong Conflict' : 'Use Caution'}
                              </span>
                              <h5 className="font-bold text-slate-900 text-xs sm:text-sm">
                                {conf.ruleTitle} ({conf.activeA} + {conf.activeB})
                              </h5>
                            </div>

                            <p className="text-xs text-slate-700 font-medium">
                              {conf.riskDescription}
                            </p>

                            <div className="p-2.5 rounded-lg bg-white/90 border border-slate-200/80 text-xs text-slate-800 space-y-1">
                              <p>
                                <span className="font-bold text-teal-800">Recommendation: </span>
                                {conf.solutionRecommendation}
                              </p>
                              <p className="text-[11px] text-slate-500 font-mono">
                                ⏱️ Timing Guide: {conf.timingGuide}
                              </p>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-5 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center space-x-3 text-emerald-800">
                    <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
                    <div className="text-xs">
                      <span className="font-bold block">Your routine is well-balanced and safe!</span>
                      <span>No acid clashes, pH incompatibility, or negative interactions detected in your current routine.</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Synergies Section */}
              <div className="space-y-3 pt-2">
                <div className="flex items-center space-x-2">
                  <Sparkles className="w-4 h-4 text-teal-600" />
                  <h4 className="text-xs sm:text-sm font-bold text-slate-900 uppercase tracking-wider">
                    Evidence-Based Actives Synergies ({auditResult?.synergies.length || 0})
                  </h4>
                </div>

                {auditResult && auditResult.synergies.length > 0 ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {auditResult.synergies.map((syn, idx) => (
                      <div key={idx} className="p-3.5 rounded-xl bg-teal-50/40 border border-teal-200 space-y-1.5">
                        <div className="flex items-center space-x-1.5">
                          <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-teal-200 text-teal-900">
                            Synergy Pair
                          </span>
                          <h5 className="font-bold text-slate-900 text-xs">
                            {syn.ruleTitle}
                          </h5>
                        </div>
                        <p className="text-xs text-slate-600 font-medium">
                          {syn.solutionRecommendation}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-500">
                    Consider adding barrier-repairing ingredients like <strong>Niacinamide</strong>, <strong>Hyaluronic Acid</strong>, or <strong>Ceramides</strong> to enhance hydration and skin tolerance.
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 2: KỆ MỸ PHẨM (ROUTINE SHELF) */}
          {activeTab === 'routine' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-xs sm:text-sm font-bold text-slate-900">
                    {t('skinShelf', 'Daily Skincare Products Shelf')}
                  </h4>
                  <p className="text-xs text-slate-500">
                    Save your skincare routine so AI automatically cross-audits compatibility whenever you scan a new item.
                  </p>
                </div>

                <button
                  onClick={() => setIsAddingNew(!isAddingNew)}
                  className="px-3 py-1.5 rounded-lg bg-teal-700 text-white text-xs font-bold hover:bg-teal-800 transition-colors flex items-center space-x-1.5"
                >
                  <Plus className="w-4 h-4" />
                  <span>{isAddingNew ? 'Cancel' : 'Add Product'}</span>
                </button>
              </div>

              {/* Add New Product Form */}
              {isAddingNew && (
                <form onSubmit={handleAddProduct} className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
                  <h5 className="text-xs font-bold text-slate-900 uppercase">Add New Product to Vanity Shelf</h5>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[11px] font-bold text-slate-600 mb-1">Product Name *</label>
                      <input
                        type="text"
                        required
                        placeholder="e.g. Paula's Choice 2% BHA Liquid Exfoliant"
                        value={newName}
                        onChange={e => setNewName(e.target.value)}
                        className="w-full px-3 py-1.5 text-xs bg-white border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-teal-500"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-bold text-slate-600 mb-1">Brand</label>
                      <input
                        type="text"
                        placeholder="e.g. Paula's Choice"
                        value={newBrand}
                        onChange={e => setNewBrand(e.target.value)}
                        className="w-full px-3 py-1.5 text-xs bg-white border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-teal-500"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[11px] font-bold text-slate-600 mb-1">Routine Step</label>
                      <select
                        value={newStep}
                        onChange={e => setNewStep(e.target.value as any)}
                        className="w-full px-3 py-1.5 text-xs bg-white border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-teal-500"
                      >
                        <option value="cleanser">Cleanser</option>
                        <option value="toner">Toner / Essence</option>
                        <option value="serum">Serum</option>
                        <option value="treatment">Treatment (Retinol/AHA/BHA)</option>
                        <option value="moisturizer">Moisturizer</option>
                        <option value="sunscreen">Sunscreen (SPF)</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-[11px] font-bold text-slate-600 mb-1">Time of Application</label>
                      <select
                        value={newTimeOfDay}
                        onChange={e => setNewTimeOfDay(e.target.value as any)}
                        className="w-full px-3 py-1.5 text-xs bg-white border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-teal-500"
                      >
                        <option value="am">Morning Only (AM)</option>
                        <option value="pm">Night Only (PM)</option>
                        <option value="both">Both Morning & Night (AM & PM)</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="block text-[11px] font-bold text-slate-600 mb-1">Active Ingredients (comma separated)</label>
                    <input
                      type="text"
                      placeholder="e.g. Salicylic Acid (BHA), Niacinamide, Hyaluronic Acid"
                      value={newActivesInput}
                      onChange={e => setNewActivesInput(e.target.value)}
                      className="w-full px-3 py-1.5 text-xs bg-white border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-teal-500"
                    />
                  </div>

                  <div className="flex justify-end space-x-2 pt-2">
                    <button
                      type="button"
                      onClick={() => setIsAddingNew(false)}
                      className="px-3 py-1.5 rounded-lg border border-slate-300 text-xs font-bold text-slate-600 hover:bg-slate-100"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="px-4 py-1.5 rounded-lg bg-teal-700 text-white text-xs font-bold hover:bg-teal-800"
                    >
                      Save Product
                    </button>
                  </div>
                </form>
              )}

              {/* Routine Product Cards List */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {routine.map((item) => (
                  <div 
                    key={item.id}
                    className="p-3.5 rounded-xl bg-white border border-slate-200 shadow-2xs hover:border-slate-300 transition-all flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-teal-700 bg-teal-50 px-2 py-0.5 rounded">
                          {stepLabels[item.step]}
                        </span>
                        <div className="flex items-center space-x-1 text-[11px] font-medium text-slate-500">
                          {item.timeOfDay === 'am' && <Sun className="w-3.5 h-3.5 text-amber-500" />}
                          {item.timeOfDay === 'pm' && <Moon className="w-3.5 h-3.5 text-indigo-500" />}
                          {item.timeOfDay === 'both' && (
                            <>
                              <Sun className="w-3 h-3 text-amber-500" />
                              <Moon className="w-3 h-3 text-indigo-500" />
                            </>
                          )}
                          <span className="capitalize">{item.timeOfDay}</span>
                        </div>
                      </div>

                      <h5 className="font-bold text-slate-900 text-xs sm:text-sm mt-1">
                        {item.name}
                      </h5>
                      {item.brand && (
                        <p className="text-[11px] text-slate-500 font-medium">{item.brand}</p>
                      )}

                      {item.activeIngredients && item.activeIngredients.length > 0 && (
                        <div className="mt-2.5 flex flex-wrap gap-1">
                          {item.activeIngredients.map((act, idx) => (
                            <span key={idx} className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-700">
                              {act}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="mt-3 pt-2 border-t border-slate-100 flex justify-end">
                      <button
                        onClick={() => handleDeleteItem(item.id)}
                        className="text-slate-400 hover:text-rose-600 p-1 transition-colors"
                        title="Remove from routine"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 3: 4-NIGHT SKIN CYCLING */}
          {activeTab === 'cycling' && (
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-gradient-to-r from-indigo-500/10 via-purple-500/5 to-transparent border border-indigo-200">
                <div className="flex items-center space-x-2">
                  <Sparkles className="w-4 h-4 text-indigo-600" />
                  <h4 className="font-bold text-slate-900 text-xs sm:text-sm">
                    Dermatologist-Backed 4-Night Skin Cycling Protocol
                  </h4>
                </div>
                <p className="text-xs text-slate-600 mt-1">
                  A cyclical routine designed to maximize the efficacy of potent actives (AHA, BHA, Retinoids) without compromising the skin's natural moisture barrier.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {auditResult?.skinCyclingGuide.map((night) => (
                  <div key={night.dayOrTime} className="p-4 rounded-xl bg-white border border-slate-200 shadow-2xs space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="px-2 py-0.5 rounded text-[10px] font-extrabold uppercase bg-slate-900 text-white">
                        {night.dayOrTime}
                      </span>
                      <span className="text-[11px] font-bold text-slate-500">
                        {night.productsUsed.join(' + ')}
                      </span>
                    </div>

                    <p className="text-xs text-slate-700 font-medium">
                      {night.instructions}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between text-xs text-slate-500">
          <span>Automatically updates when you add or remove products from your routine.</span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-slate-900 text-white hover:bg-slate-800 text-xs font-bold transition-colors"
          >
            Close Radar
          </button>
        </div>
      </div>
    </div>
  );
};

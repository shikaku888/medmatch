import React, { useState, useEffect } from 'react';
import { CrossReactivityRule, UserProfile, FamilyProfile, SupportedLanguage } from '../types';
import { getTranslation } from '../i18n';
import { 
  X, 
  ShieldAlert, 
  Dna, 
  Search, 
  Flame, 
  AlertTriangle, 
  CheckCircle2, 
  Layers, 
  Sparkles, 
  Info, 
  ChevronRight,
  Stethoscope,
  BookOpen,
  Filter
} from 'lucide-react';

interface CrossReactivityModalProps {
  isOpen: boolean;
  onClose: () => void;
  userProfile: UserProfile;
  familyProfiles?: FamilyProfile[];
  language?: SupportedLanguage;
}

export const CrossReactivityModal: React.FC<CrossReactivityModalProps> = ({
  isOpen,
  onClose,
  userProfile,
  familyProfiles = [],
  language = 'en'
}) => {
  const t = (key: string, fb: string) => getTranslation(language, key, fb);
  const [rules, setRules] = useState<CrossReactivityRule[]>([]);
  const [selectedRuleId, setSelectedRuleId] = useState<string>('birch_pollen_oas');
  const [searchQuery, setSearchQuery] = useState('');
  const [filterRisk, setFilterRisk] = useState<'all' | 'very_high' | 'high'>('all');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetchRules();
    }
  }, [isOpen]);

  const fetchRules = async () => {
    setIsLoading(true);
    try {
      const res = await fetch('/api/cross-reactivity-rules');
      if (res.ok) {
        const data = await res.json();
        setRules(data);
        if (data.length > 0 && !selectedRuleId) {
          setSelectedRuleId(data[0].id);
        }
      }
    } catch (e) {
      console.warn('Could not load cross-reactivity rules:', e);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  const currentRule = rules.find(r => r.id === selectedRuleId) || rules[0];

  // Check if current user or family has this allergy
  const userAllergies = [...userProfile.allergies, ...(userProfile.customAllergens || []).map(c => c.toLowerCase())];
  const matchingFamilyMembers = familyProfiles.filter(fp => 
    currentRule && fp.allergies.some(a => a === currentRule.sourceKey || a.includes(currentRule.sourceKey) || currentRule.sourceName.toLowerCase().includes(a))
  );
  const isUserAffected = currentRule && userAllergies.some(a => a === currentRule.sourceKey || a.includes(currentRule.sourceKey) || currentRule.sourceName.toLowerCase().includes(a));

  // Filtered cross items in detail view
  const filteredCrossItems = currentRule?.crossItems.filter(item => {
    const matchesSearch = searchQuery === '' || 
      item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.notes.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesRisk = filterRisk === 'all' || item.riskLevel === filterRisk;
    return matchesSearch && matchesRisk;
  }) || [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div 
        id="cross-reactivity-modal"
        className="bg-white w-full max-w-4xl rounded-2xl shadow-2xl border border-slate-200 flex flex-col max-h-[92vh] overflow-hidden"
      >
        {/* Header */}
        <div className="px-6 py-4.5 border-b border-slate-200 bg-gradient-to-r from-amber-500/10 via-rose-500/5 to-transparent flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-amber-500/15 text-amber-800 border border-amber-500/20 shadow-2xs">
              <Dna className="w-5 h-5 text-amber-700" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="font-bold text-slate-900 text-base sm:text-lg">
                  {t('crossTitle', 'Biological Cross-Reactivity Matrix')}
                </h3>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200">
                  Clinical Immunology Standards
                </span>
              </div>
              <p className="text-xs text-slate-500">
                {t('crossSubtitle', 'Analyze epitope protein homology, Pollen Food Allergy Syndrome (PFAS/OAS), Latex-Fruit syndrome, and CMPA clinical risk rates.')}
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

        {/* Content Body: Two Columns */}
        <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
          {/* Left Column: Syndromes Navigation */}
          <div className="w-full md:w-80 border-r border-slate-200 bg-slate-50/50 p-4 overflow-y-auto space-y-2">
            <span className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 px-1 mb-2">
              Primary Cross-Allergy Syndromes ({rules.length})
            </span>

            {rules.map((rule) => {
              const isSelected = rule.id === selectedRuleId;
              const hasFamilyConflict = familyProfiles.some(fp => 
                fp.allergies.some(a => a === rule.sourceKey || a.includes(rule.sourceKey) || rule.sourceName.toLowerCase().includes(a))
              );

              return (
                <button
                  key={rule.id}
                  onClick={() => setSelectedRuleId(rule.id)}
                  className={`w-full text-left p-3 rounded-xl border transition-all ${
                    isSelected 
                      ? 'bg-white border-amber-400 shadow-sm ring-1 ring-amber-400/30' 
                      : 'bg-white/80 border-slate-200 hover:bg-white hover:border-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-[10px] font-bold uppercase tracking-wider ${
                      isSelected ? 'text-amber-700' : 'text-slate-500'
                    }`}>
                      {rule.sourceKey.replace('_', ' ')}
                    </span>
                    {hasFamilyConflict && (
                      <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-rose-100 text-rose-700 border border-rose-200">
                        Family Risk
                      </span>
                    )}
                  </div>
                  <h4 className="text-xs font-bold text-slate-900 line-clamp-1">
                    {rule.syndromeName}
                  </h4>
                  <p className="text-[11px] text-slate-500 line-clamp-1 mt-0.5 font-medium">
                    {rule.sourceName}
                  </p>
                  <div className="mt-2 flex items-center justify-between text-[10px] text-slate-400">
                    <span>{rule.crossItems.length} cross-reactive foods</span>
                    <ChevronRight className={`w-3.5 h-3.5 ${isSelected ? 'text-amber-600' : 'text-slate-400'}`} />
                  </div>
                </button>
              );
            })}
          </div>

          {/* Right Column: Syndrome Details & Cross Reaction Food List */}
          <div className="flex-1 p-5 overflow-y-auto space-y-4 bg-white">
            {currentRule ? (
              <>
                {/* Active Rule Top Banner */}
                <div className="p-4 rounded-xl bg-gradient-to-br from-amber-50 to-orange-50/50 border border-amber-200 space-y-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <span className="text-[10px] uppercase font-bold tracking-wider text-amber-700 bg-amber-100 px-2 py-0.5 rounded">
                        Immunology Syndrome
                      </span>
                      <h3 className="text-base sm:text-lg font-bold text-slate-900 mt-1">
                        {currentRule.syndromeName}
                      </h3>
                    </div>

                    {(isUserAffected || matchingFamilyMembers.length > 0) && (
                      <div className="px-3 py-1 rounded-lg bg-rose-100 text-rose-800 border border-rose-200 text-xs font-bold flex items-center space-x-1.5">
                        <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
                        <span>Warning: Affects {matchingFamilyMembers.map(m => m.name).join(', ') || 'You'}</span>
                      </div>
                    )}
                  </div>

                  <p className="text-xs text-slate-700 leading-relaxed font-medium">
                    {currentRule.mechanism}
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs pt-1">
                    <div className="p-2.5 rounded-lg bg-white/90 border border-amber-200/80">
                      <span className="block text-[10px] font-bold uppercase text-slate-500">Antigen Protein Family</span>
                      <span className="font-bold text-slate-800 font-mono text-[11px]">{currentRule.proteinFamily}</span>
                    </div>
                    <div className="p-2.5 rounded-lg bg-white/90 border border-amber-200/80">
                      <span className="block text-[10px] font-bold uppercase text-slate-500">Common Symptoms</span>
                      <span className="text-slate-800 font-medium text-[11px]">{currentRule.symptoms.join(' • ')}</span>
                    </div>
                  </div>

                  {currentRule.cookingEffect && (
                    <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-400/40 text-xs text-amber-900 flex items-start space-x-2">
                      <Flame className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                      <div>
                        <span className="font-bold">Thermal & Cooking Processing Effect: </span>
                        <span>{currentRule.cookingEffect}</span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Filter & Search Bar */}
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5 pt-1">
                  <div className="relative flex-1">
                    <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      placeholder="Search cross-reactive triggers (e.g. Apple, Banana, Hazelnut...)"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-amber-500"
                    />
                  </div>

                  <div className="flex items-center space-x-1.5 text-xs">
                    <span className="text-[11px] text-slate-500 font-medium">Risk Level:</span>
                    <button
                      onClick={() => setFilterRisk('all')}
                      className={`px-2.5 py-1 rounded-md text-[11px] font-bold transition-colors ${
                        filterRisk === 'all' ? 'bg-slate-800 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      }`}
                    >
                      All
                    </button>
                    <button
                      onClick={() => setFilterRisk('very_high')}
                      className={`px-2.5 py-1 rounded-md text-[11px] font-bold transition-colors ${
                        filterRisk === 'very_high' ? 'bg-rose-600 text-white' : 'bg-rose-50 text-rose-700 border border-rose-200'
                      }`}
                    >
                      Very High (&gt;75%)
                    </button>
                  </div>
                </div>

                {/* Cross Reactivity Food Items Cards */}
                <div className="space-y-2">
                  <span className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                    Cross-Reactive Foods & Sensitivity Matrix ({filteredCrossItems.length})
                  </span>

                  <div className="grid grid-cols-1 gap-2.5">
                    {filteredCrossItems.map((item, idx) => {
                      const isVeryHigh = item.riskLevel === 'very_high';
                      const isHigh = item.riskLevel === 'high';

                      return (
                        <div
                          key={idx}
                          className={`p-3.5 rounded-xl border transition-all ${
                            isVeryHigh 
                              ? 'bg-rose-50/40 border-rose-200' 
                              : isHigh 
                              ? 'bg-amber-50/40 border-amber-200' 
                              : 'bg-slate-50/40 border-slate-200'
                          }`}
                        >
                          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                            <div>
                              <div className="flex items-center space-x-2">
                                <h4 className="font-bold text-slate-900 text-xs sm:text-sm">
                                  {item.name}
                                </h4>
                                <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold ${
                                  isVeryHigh 
                                    ? 'bg-rose-600 text-white' 
                                    : isHigh 
                                    ? 'bg-amber-600 text-white' 
                                    : 'bg-slate-200 text-slate-700'
                                }`}>
                                  Cross-Rate: {item.riskPercent}
                                </span>
                              </div>
                              <p className="text-xs text-slate-600 mt-1 font-medium">
                                {item.notes}
                              </p>
                            </div>

                            <span className="text-[11px] font-mono text-slate-500 shrink-0">
                              {isVeryHigh ? 'High Epitope Neutralization' : 'Homologous Antigen'}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </>
            ) : (
              <div className="p-8 text-center text-slate-500">
                Loading cross-reactivity matrix...
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between text-xs text-slate-500">
          <div className="flex items-center space-x-2">
            <Stethoscope className="w-4 h-4 text-slate-400" />
            <span>Clinical reference: EAACI Molecular Allergology Guidelines & World Allergy Organization (WAO).</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-slate-900 text-white hover:bg-slate-800 text-xs font-bold transition-colors"
          >
            Close Matrix
          </button>
        </div>
      </div>
    </div>
  );
};

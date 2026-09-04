import React, { useState } from 'react';
import { UserProfile, SupportedLanguage, SupportedCountry } from '../types';
import { getTranslation, LANGUAGE_OPTIONS } from '../i18n';
import { 
  Scan, 
  UserCircle, 
  History as HistoryIcon, 
  GitCompare, 
  ShieldCheck,
  Sparkles,
  Activity,
  Users,
  Layers,
  Award,
  Dna,
  Zap,
  Globe,
  Pill,
  ChevronDown
} from 'lucide-react';

export type AppTab = 'scanner' | 'swaps' | 'dashboard' | 'history' | 'compare' | 'profile';

interface HeaderProps {
  currentTab: AppTab;
  setCurrentTab: (tab: AppTab) => void;
  userProfile: UserProfile;
  historyCount: number;
  onOpenFamilyModal: () => void;
  onOpenBatchScanModal: () => void;
  onOpenReceiptAuditModal?: () => void;
  onOpenMarketCatalogModal?: () => void;
  onOpenCrossReactivityModal?: () => void;
  onOpenSkincareRadarModal?: () => void;
  onOpenHerbDrugModal?: () => void;
  onLanguageChange: (lang: SupportedLanguage) => void;
  onCountryChange?: (country: SupportedCountry) => void;
}

export const Header: React.FC<HeaderProps> = ({
  currentTab,
  setCurrentTab,
  userProfile,
  historyCount,
  onOpenFamilyModal,
  onOpenBatchScanModal,
  onOpenReceiptAuditModal,
  onOpenMarketCatalogModal,
  onOpenCrossReactivityModal,
  onOpenSkincareRadarModal,
  onOpenHerbDrugModal,
  onLanguageChange,
  onCountryChange
}) => {

  const [langMenuOpen, setLangMenuOpen] = useState(false);

  const lang = userProfile.language || 'en';
  const t = (key: Parameters<typeof getTranslation>[1]) => getTranslation(lang, key);

  const currentLangObj = LANGUAGE_OPTIONS.find(l => l.code === lang) || LANGUAGE_OPTIONS[0];

  return (
    <header className="sticky top-0 z-40 bg-[#0f172a] border-b border-slate-800 text-white shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-center justify-between min-h-14 gap-x-2 gap-y-1 py-1.5">
          
          {/* Logo & Identity */}
          <div 
            id="brand-logo-btn"
            onClick={() => setCurrentTab('scanner')}
            className="flex items-center space-x-3 cursor-pointer group shrink-0"
          >
            <div className="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center font-bold text-white shadow-sm transition-transform group-hover:scale-105">
              <ShieldCheck className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-base tracking-tight text-white group-hover:text-blue-400 transition-colors">
                  MedMatch AI
                </span>
                <span className="hidden sm:inline-flex text-[10px] font-semibold px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                  Interaction Checker
                </span>
              </div>
              <p className="text-[11px] text-slate-400 hidden sm:block">
                Drug & Supplement Interaction Checker
              </p>
            </div>
          </div>

          {/* Household Member & Language Picker */}
          <div className="flex flex-wrap items-center justify-end space-x-1.5 sm:space-x-2 max-w-full min-w-0">
            
            {/* Language Selector */}
            <div className="relative">
              <button
                id="language-selector-btn"
                onClick={() => setLangMenuOpen(!langMenuOpen)}
                className="flex items-center space-x-1.5 px-2.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs text-slate-200 transition-colors"
                title="Select Language"
              >
                <Globe className="w-3.5 h-3.5 text-slate-400" />
                <span className="font-bold text-xs">{currentLangObj.flag} {currentLangObj.code.toUpperCase()}</span>
                <ChevronDown className="w-3 h-3 text-slate-400" />
              </button>

              {langMenuOpen && (
                <div className="absolute left-0 sm:left-auto sm:right-0 mt-1 w-44 bg-slate-900 border border-slate-700 rounded-xl shadow-xl z-50 py-1 max-h-80 overflow-y-auto">
                  <div className="px-3 py-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider border-b border-slate-800">
                    Language
                  </div>
                  {LANGUAGE_OPTIONS.map(l => (
                    <button
                      key={l.code}
                      onClick={() => {
                        onLanguageChange(l.code);
                        setLangMenuOpen(false);
                      }}
                      className={`w-full flex items-center justify-between px-3 py-2 text-xs text-left hover:bg-slate-800 transition-colors ${
                        l.code === lang ? 'text-blue-400 font-bold bg-slate-800/60' : 'text-slate-200'
                      }`}
                    >
                      <span className="flex items-center space-x-2">
                        <span>{l.flag}</span>
                        <span>{l.name}</span>
                      </span>
                      <span className="text-[10px] font-bold text-slate-400">{l.code.toUpperCase()}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Family Profile Member Quick Switcher (Desktop) */}
            <button
              id="household-switcher-btn"
              onClick={onOpenFamilyModal}
              className="hidden lg:flex items-center space-x-2 px-3 py-1.5 rounded-xl bg-slate-800/90 hover:bg-slate-700 border border-slate-700 text-xs text-slate-200 transition-colors group"
              title="Click to switch active family member profile"
            >
              <div className="w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center font-bold text-[10px] text-white">
                {userProfile.name?.charAt(0) || 'U'}
              </div>
              <div className="text-left">
                <span className="block font-bold text-white leading-none">
                  {userProfile.name || 'Alex'}
                </span>
                <span className="text-[10px] text-slate-400 leading-none capitalize">
                  {userProfile.role || 'Primary'} • {userProfile.dietType}
                </span>
              </div>
              <Users className="w-3.5 h-3.5 text-slate-400 group-hover:text-blue-400 ml-1" />
            </button>

            {onOpenHerbDrugModal && (
              <button
                id="herb-drug-header-btn"
                onClick={onOpenHerbDrugModal}
                className="hidden xl:flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-rose-300 hover:text-rose-200 transition-colors"
                title={t('herbDrugRadar')}
              >
                <Pill className="w-3.5 h-3.5 text-rose-400" />
                <span>{t('herbDrugRadar')}</span>
              </button>
            )}

            {onOpenReceiptAuditModal && (
              <button
                id="receipt-cart-header-btn"
                onClick={onOpenReceiptAuditModal}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-gradient-to-r from-amber-500/20 to-orange-500/20 hover:from-amber-500/30 hover:to-orange-500/30 border border-amber-500/40 text-xs font-bold text-amber-300 transition-all shadow-2xs"
                title={t('receiptScan')}
              >
                <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                <span>{t('receiptScan')}</span>
              </button>
            )}

            {onOpenCrossReactivityModal && (
              <button
                id="cross-reactivity-header-btn"
                onClick={onOpenCrossReactivityModal}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-amber-300 hover:text-amber-200 transition-colors"
                title={t('crossReactivity')}
              >
                <Dna className="w-3.5 h-3.5 text-amber-400" />
                <span>{t('crossReactivity')}</span>
              </button>
            )}

            {onOpenSkincareRadarModal && (
              <button
                id="skincare-radar-header-btn"
                onClick={onOpenSkincareRadarModal}
                className="hidden 2xl:flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-teal-300 hover:text-teal-200 transition-colors"
                title={t('skincareRadar')}
              >
                <Zap className="w-3.5 h-3.5 text-teal-400" />
                <span>{t('skincareRadar')}</span>
              </button>
            )}

            {onOpenMarketCatalogModal && (
              <button
                id="market-catalog-header-btn"
                onClick={onOpenMarketCatalogModal}
                className="hidden 2xl:flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-slate-300 transition-colors"
                title={t('supermarkets')}
              >
                <Layers className="w-3.5 h-3.5 text-blue-400" />
                <span>{t('supermarkets')}</span>
              </button>
            )}
          </div>

          {/* Desktop Navigation Controls */}
          <nav className="hidden lg:flex items-center space-x-1 sm:space-x-1.5 overflow-x-auto scrollbar-none py-0.5 w-full justify-end">
            <button
              id="nav-scanner-tab"
              onClick={() => setCurrentTab('scanner')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold tracking-wide uppercase transition-all ${
                currentTab === 'scanner'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800'
              }`}
            >
              <Scan className="w-3.5 h-3.5" />
              <span>{t('scan')}</span>
            </button>

            <button
              id="nav-swaps-tab"
              onClick={() => setCurrentTab('swaps')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold tracking-wide uppercase transition-all relative ${
                currentTab === 'swaps'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-amber-300 hover:text-amber-200 hover:bg-slate-800'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              <span>{t('safeSwaps')}</span>
            </button>

            <button
              id="nav-dashboard-tab"
              onClick={() => setCurrentTab('dashboard')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold tracking-wide uppercase transition-all ${
                currentTab === 'dashboard'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800'
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              <span>{t('healthIndex')}</span>
            </button>

            <button
              id="nav-compare-tab"
              onClick={() => setCurrentTab('compare')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold tracking-wide uppercase transition-all ${
                currentTab === 'compare'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800'
              }`}
            >
              <GitCompare className="w-3.5 h-3.5" />
              <span>{t('compare')}</span>
            </button>

            <button
              id="nav-history-tab"
              onClick={() => setCurrentTab('history')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold tracking-wide uppercase transition-all ${
                currentTab === 'history'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800'
              }`}
            >
              <HistoryIcon className="w-3.5 h-3.5" />
              <span>{t('history')}</span>
              {historyCount > 0 && (
                <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${
                  currentTab === 'history' ? 'bg-white text-blue-700' : 'bg-slate-700 text-slate-300'
                }`}>
                  {historyCount}
                </span>
              )}
            </button>

            <button
              id="nav-profile-tab"
              onClick={() => setCurrentTab('profile')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold tracking-wide uppercase transition-all ${
                currentTab === 'profile'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800'
              }`}
            >
              <UserCircle className="w-3.5 h-3.5" />
              <span>{t('profile')}</span>
            </button>

          </nav>

          {/* Mobile Right Controls */}
          <div className="flex md:hidden items-center space-x-2">
            <button
              id="mobile-family-btn"
              onClick={onOpenFamilyModal}
              className="flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-xs text-white"
              title="Switch Member"
            >
              <div className="w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center font-bold text-[10px] text-white">
                {userProfile.name?.charAt(0) || 'U'}
              </div>
              <span className="font-bold text-xs max-w-[70px] truncate">
                {userProfile.name || 'Alex'}
              </span>
              <Users className="w-3 h-3 text-slate-400" />
            </button>

            <button
              id="mobile-pantry-btn"
              onClick={onOpenBatchScanModal}
              className="p-2 rounded-lg bg-slate-800 border border-slate-700 text-blue-400"
              title="Pantry Audit"
            >
              <Layers className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};


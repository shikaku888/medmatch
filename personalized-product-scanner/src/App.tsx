import React, { useState, useEffect } from 'react';
import { 
  UserProfile, 
  FamilyProfile, 
  ProductScanResult, 
  ScanHistoryItem, 
  ResearchData, 
  SafeSwapRecommendation,
  SupportedLanguage,
  SupportedCountry
} from './types';
import { Header, AppTab } from './components/Header';
import { ScannerView } from './components/ScannerView';
import { ScanResultCard } from './components/ScanResultCard';
import { ProfileView } from './components/ProfileView';
import { HistoryView } from './components/HistoryView';
import { CompareView } from './components/CompareView';
import { EvidenceModal } from './components/EvidenceModal';
import { SmartSwapsView } from './components/SmartSwapsView';
import { HealthDashboardView } from './components/HealthDashboardView';
import { FamilyProfilesModal } from './components/FamilyProfilesModal';
import { AiDietitianChatModal } from './components/AiDietitianChatModal';
import { ProUpgradeModal } from './components/ProUpgradeModal';
import { BatchScanModal } from './components/BatchScanModal';
import { ReceiptCartAuditModal } from './components/ReceiptCartAuditModal';
import { SupermarketCatalogModal } from './components/SupermarketCatalogModal';
import { CrossReactivityModal } from './components/CrossReactivityModal';
import { SkincareRoutineRadarModal } from './components/SkincareRoutineRadarModal';
import { HerbDrugModal } from './components/HerbDrugModal';
import { getTranslation } from './i18n';
import { 
  ShieldCheck, 
  Sparkles, 
  Layers, 
  BookOpen, 
  HeartHandshake, 
  RotateCcw,
  CheckCircle2,
  Scan,
  Users,
  Activity,
  Award,
  History as HistoryIcon,
  GitCompare,
  UserCircle
} from 'lucide-react';

export default function App() {
  const [currentTab, setCurrentTab] = useState<AppTab>('scanner');
  
  // User Profile
  const [userProfile, setUserProfile] = useState<UserProfile>({
    id: 'profile_primary',
    name: 'Alex Rivera',
    role: 'Primary Account',
    avatarColor: 'blue',
    allergies: ['peanut', 'milk'],
    customAllergens: [],
    dietType: 'omnivore',
    specialConditions: [],
    updatedAt: new Date().toISOString()
  });

  // Current Scan Result & History
  const [currentScanResult, setCurrentScanResult] = useState<ProductScanResult | null>(null);
  const [history, setHistory] = useState<ScanHistoryItem[]>([]);
  const [demoProducts, setDemoProducts] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Pro Subscription State
  const [isProUser, setIsProUser] = useState(false);

  // Family Profiles List
  const [familyProfiles, setFamilyProfiles] = useState<FamilyProfile[]>([]);

  // Modals
  const [selectedEvidence, setSelectedEvidence] = useState<ResearchData | null>(null);
  const [isFamilyModalOpen, setIsFamilyModalOpen] = useState(false);
  const [isAiChatModalOpen, setIsAiChatModalOpen] = useState(false);
  const [isProModalOpen, setIsProModalOpen] = useState(false);
  const [isBatchModalOpen, setIsBatchModalOpen] = useState(false);
  const [isReceiptAuditModalOpen, setIsReceiptAuditModalOpen] = useState(false);
  const [isMarketCatalogModalOpen, setIsMarketCatalogModalOpen] = useState(false);
  const [isCrossReactivityModalOpen, setIsCrossReactivityModalOpen] = useState(false);
  const [isSkincareRadarModalOpen, setIsSkincareRadarModalOpen] = useState(false);
  const [isHerbDrugModalOpen, setIsHerbDrugModalOpen] = useState(false);

  // Compare State
  const [compareProductA, setCompareProductA] = useState<ProductScanResult | null>(null);
  const [compareProductB, setCompareProductB] = useState<ProductScanResult | null>(null);

  // Fetch initial profile, history, and demo products on mount
  useEffect(() => {
    fetchProfile();
    fetchFamilyProfiles();
    fetchHistory();
    fetchDemoProducts();
  }, []);

  const fetchProfile = async () => {
    try {
      const res = await fetch('/api/profile');
      if (res.ok) {
        const data: UserProfile = await res.json();
        const validLanguages: SupportedLanguage[] = ['en', 'fr', 'de', 'it', 'es'];
        const validCountries: SupportedCountry[] = ['US', 'UK', 'FR', 'DE', 'IT', 'ES'];

        const rawLang = localStorage.getItem('medmatch_lang') as SupportedLanguage | null;
        const rawCountry = localStorage.getItem('medmatch_country') as SupportedCountry | null;

        const savedLang = validLanguages.includes(rawLang as any) ? rawLang : null;
        const savedCountry = validCountries.includes(rawCountry as any) ? rawCountry : null;
        
        const merged: UserProfile = {
          ...data,
          language: savedLang || (validLanguages.includes(data.language as any) ? data.language : 'en'),
          country: savedCountry || (validCountries.includes(data.country as any) ? data.country : 'US')
        };
        setUserProfile(merged);
      }
    } catch (e) {
      console.warn('Could not load profile:', e);
      const savedLang = localStorage.getItem('medmatch_lang') as SupportedLanguage | null;
      const savedCountry = localStorage.getItem('medmatch_country') as SupportedCountry | null;
      if (savedLang || savedCountry) {
        setUserProfile(prev => ({
          ...prev,
          language: savedLang || prev.language || 'en',
          country: savedCountry || prev.country || 'US'
        }));
      }
    }
  };

  const handleLanguageChange = (lang: SupportedLanguage) => {
    localStorage.setItem('medmatch_lang', lang);
    const updated: UserProfile = { ...userProfile, language: lang };
    setUserProfile(updated);
    handleSaveProfile(updated);
  };

  const handleCountryChange = (country: SupportedCountry) => {
    localStorage.setItem('medmatch_country', country);
    const updated: UserProfile = { ...userProfile, country: country };
    setUserProfile(updated);
    handleSaveProfile(updated);
  };

  const fetchFamilyProfiles = async () => {
    try {
      const res = await fetch('/api/family-profiles');
      if (res.ok) {
        const data = await res.json();
        setFamilyProfiles(data);
      }
    } catch (e) {
      console.warn('Could not load family profiles:', e);
    }
  };

  const fetchHistory = async () => {
    try {
      const res = await fetch('/api/history');
      if (res.ok) {
        const data = await res.json();
        setHistory(data);
      }
    } catch (e) {
      console.warn('Could not load history:', e);
    }
  };

  const fetchDemoProducts = async () => {
    try {
      const res = await fetch('/api/demo-products');
      if (res.ok) {
        const data = await res.json();
        setDemoProducts(data);
      }
    } catch (e) {
      console.warn('Could not load demo products:', e);
    }
  };

  const handleSaveProfile = async (updated: UserProfile) => {
    try {
      const res = await fetch('/api/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated)
      });
      if (res.ok) {
        const saved = await res.json();
        setUserProfile(saved);

        // If a product is currently open, re-scan to re-evaluate match with the new profile
        if (currentScanResult && currentScanResult.barcode) {
          reEvaluateCurrentProduct(currentScanResult.barcode);
        }
      }
    } catch (e) {
      console.error('Error saving profile:', e);
    }
  };

  const handleProfileSwitched = (newProfile: UserProfile) => {
    setUserProfile(newProfile);
    if (currentScanResult && currentScanResult.barcode) {
      reEvaluateCurrentProduct(currentScanResult.barcode);
    }
  };

  const reEvaluateCurrentProduct = async (barcode: string) => {
    try {
      const res = await fetch('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ barcode })
      });
      if (res.ok) {
        const data = await res.json();
        setCurrentScanResult(data);
      }
    } catch (e) {
      console.warn('Re-evaluation error:', e);
    }
  };

  const handleApplyPreset = async (presetKey: string) => {
    let presetProfile: Partial<UserProfile> = {};

    if (presetKey === 'pregnant_sensitive') {
      presetProfile = {
        name: 'Sarah (Expecting)',
        role: 'Partner',
        allergies: ['fragrance', 'alcohol', 'retinoid', 'salicylic_acid', 'parabens'],
        customAllergens: ['hydroquinone'],
        dietType: 'omnivore',
        specialConditions: ['pregnant', 'sensitive_skin']
      };
    } else if (presetKey === 'vegan_nut') {
      presetProfile = {
        name: 'Jordan (Vegan & Allergy)',
        role: 'Self',
        allergies: ['peanut', 'tree_nut', 'sesame'],
        customAllergens: [],
        dietType: 'vegan',
        specialConditions: []
      };
    } else if (presetKey === 'diabetic_heart') {
      presetProfile = {
        name: 'Arthur (Diabetic Care)',
        role: 'Parent',
        allergies: [],
        customAllergens: ['high fructose corn syrup', 'aspartame'],
        dietType: 'diabetic',
        specialConditions: ['hypertension']
      };
    } else if (presetKey === 'gluten_dairy') {
      presetProfile = {
        name: 'Liam (Child Safe)',
        role: 'Child',
        allergies: ['gluten', 'milk', 'peanut'],
        customAllergens: ['red 40'],
        dietType: 'gluten_free',
        specialConditions: ['eczema']
      };
    }

    const updated = { ...userProfile, ...presetProfile };
    await handleSaveProfile(updated);
  };

  const handleScanComplete = (result: ProductScanResult) => {
    setCurrentScanResult(result);
    fetchHistory();
  };

  const handleClearHistory = async () => {
    try {
      await fetch('/api/history', { method: 'DELETE' });
      setHistory([]);
    } catch (e) {
      console.warn('Error clearing history:', e);
    }
  };

  const handleToggleFavorite = async (id: string) => {
    try {
      await fetch('/api/history/favorite', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id })
      });
      fetchHistory();
    } catch (e) {
      console.warn('Error toggling favorite:', e);
    }
  };

  const handleStartCompare = (product: ProductScanResult) => {
    setCompareProductA(product);
    const otherHistory = history.find(h => h.barcode !== product.barcode && h.fullResult);
    if (otherHistory && otherHistory.fullResult) {
      setCompareProductB(otherHistory.fullResult);
    }
    setCurrentTab('compare');
  };

  const handleCompareTwo = (p1: ProductScanResult, p2: ProductScanResult) => {
    setCompareProductA(p1);
    setCompareProductB(p2);
    setCurrentTab('compare');
  };

  // Convert Safe Swap to full ProductScanResult for side-by-side comparison
  const handleCompareWithSwap = (current: ProductScanResult, swap: SafeSwapRecommendation) => {
    const swapAsProduct: ProductScanResult = {
      barcode: `SWAP_${swap.id}`,
      productName: swap.name,
      brand: swap.brand,
      productType: swap.productType,
      imageUrl: swap.imageUrl,
      ingredientsText: swap.cleanHighlights.join(', ') + ' - Verified 100% compliant recipe.',
      ingredientsList: swap.cleanHighlights,
      allergens: [],
      labels: swap.certificationBadges || ['Clean Verified', 'Allergen Safe'],
      matchAssessment: {
        status: 'safe',
        score: swap.score,
        summary: `Recommended Safe Swap: 100% compliant with your personal profile. ${swap.whyBetter.join('. ')}`,
        warnings: [],
        safeHighlights: swap.cleanHighlights
      },
      source: 'local_scan',
      scannedAt: new Date().toISOString()
    };

    setCompareProductA(current);
    setCompareProductB(swapAsProduct);
    setCurrentTab('compare');
  };

  const handleSelectSwapAsProduct = (swap: SafeSwapRecommendation) => {
    const swapAsProduct: ProductScanResult = {
      barcode: `SWAP_${swap.id}`,
      productName: swap.name,
      brand: swap.brand,
      productType: swap.productType,
      imageUrl: swap.imageUrl,
      ingredientsText: swap.cleanHighlights.join(', ') + ' - Verified 100% compliant recipe.',
      ingredientsList: swap.cleanHighlights,
      allergens: [],
      labels: swap.certificationBadges || ['Clean Verified', 'Allergen Safe'],
      matchAssessment: {
        status: 'safe',
        score: swap.score,
        summary: `Recommended Safe Swap: 100% compliant with your personal profile. ${swap.whyBetter.join('. ')}`,
        warnings: [],
        safeHighlights: swap.cleanHighlights
      },
      source: 'local_scan',
      scannedAt: new Date().toISOString()
    };

    setCurrentScanResult(swapAsProduct);
    setCurrentTab('scanner');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // Compile all available scans
  const allAvailableScans: ProductScanResult[] = [
    ...(currentScanResult ? [currentScanResult] : []),
    ...history.filter(h => h.fullResult).map(h => h.fullResult!)
  ].filter((v, i, a) => a.findIndex(t => t.barcode === v.barcode) === i);

  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-900 flex flex-col font-sans selection:bg-blue-500 selection:text-white">
      {/* Top Header & Navigation */}
      <Header
        currentTab={currentTab}
        setCurrentTab={setCurrentTab}
        userProfile={userProfile}
        historyCount={history.length}
        onLanguageChange={handleLanguageChange}
        onCountryChange={handleCountryChange}
        onOpenFamilyModal={() => setIsFamilyModalOpen(true)}
        onOpenBatchScanModal={() => setIsBatchModalOpen(true)}
        onOpenReceiptAuditModal={() => setIsReceiptAuditModalOpen(true)}
        onOpenMarketCatalogModal={() => setIsMarketCatalogModalOpen(true)}
        onOpenCrossReactivityModal={() => setIsCrossReactivityModalOpen(true)}
        onOpenSkincareRadarModal={() => setIsSkincareRadarModalOpen(true)}
        onOpenHerbDrugModal={() => setIsHerbDrugModalOpen(true)}
        onOpenProModal={() => setIsProModalOpen(true)}
        isProUser={isProUser}
      />

      {/* Main Content Stage */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-3 sm:px-6 lg:px-8 py-5 sm:py-8 pb-24 md:pb-8">
        
        {/* TAB 1: SCANNER VIEW */}
        {currentTab === 'scanner' && (
          <div className="space-y-8 animate-fade-in">
            {/* Top Scanning Controls */}
            <ScannerView
              onScanComplete={handleScanComplete}
              userProfile={userProfile}
              demoProducts={demoProducts}
              isLoading={isLoading}
              setIsLoading={setIsLoading}
              onOpenReceiptAuditModal={() => setIsReceiptAuditModalOpen(true)}
              onOpenMarketCatalogModal={() => setIsMarketCatalogModalOpen(true)}
              onOpenBatchScanModal={() => setIsBatchModalOpen(true)}
              onOpenCrossReactivityModal={() => setIsCrossReactivityModalOpen(true)}
              onOpenSkincareRadarModal={() => setIsSkincareRadarModalOpen(true)}
            />

            {/* Currently Active / Scanned Result Card */}
            {currentScanResult && (
              <div className="pt-2">
                <div className="flex items-center justify-between mb-3 px-1">
                  <div className="flex items-center space-x-2">
                    <span className="w-2 h-2 rounded-full bg-blue-600"></span>
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-700">
                      {getTranslation(userProfile.language || 'en', 'activeEvaluation', 'Active Product Evaluation')}
                    </span>
                  </div>
                  <button
                    onClick={() => setCurrentScanResult(null)}
                    className="text-xs text-slate-500 hover:text-slate-800 font-medium transition-colors"
                  >
                    {getTranslation(userProfile.language || 'en', 'clearResult', 'Clear Result')}
                  </button>
                </div>

                <ScanResultCard
                  result={currentScanResult}
                  language={userProfile.language}
                  onOpenEvidence={(res) => setSelectedEvidence(res)}
                  onCompareWith={handleStartCompare}
                  onOpenAiChat={() => setIsAiChatModalOpen(true)}
                  onOpenSmartSwaps={() => setCurrentTab('swaps')}
                  onOpenCrossReactivity={() => setIsCrossReactivityModalOpen(true)}
                  onOpenSkincareRadar={() => setIsSkincareRadarModalOpen(true)}
                  onRescan={() => {
                    setCurrentScanResult(null);
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                  }}
                />
              </div>
            )}
          </div>
        )}

        {/* TAB 2: SMART SAFE SWAPS VIEW */}
        {currentTab === 'swaps' && (
          <div className="animate-fade-in">
            <SmartSwapsView
              currentProduct={currentScanResult}
              userProfile={userProfile}
              onCompareProducts={handleCompareWithSwap}
              onSelectSwapAsProduct={handleSelectSwapAsProduct}
            />
          </div>
        )}

        {/* TAB 3: HEALTH & BIOMETRIC EXPOSURE DASHBOARD */}
        {currentTab === 'dashboard' && (
          <div className="animate-fade-in">
            <HealthDashboardView
              userProfile={userProfile}
              history={history}
              onOpenProModal={() => setIsProModalOpen(true)}
              isProUser={isProUser}
            />
          </div>
        )}

        {/* TAB 4: PROFILE VIEW */}
        {currentTab === 'profile' && (
          <div className="animate-fade-in">
            <ProfileView
              userProfile={userProfile}
              onSaveProfile={handleSaveProfile}
              onApplyPreset={handleApplyPreset}
            />
          </div>
        )}

        {/* TAB 5: HISTORY VIEW */}
        {currentTab === 'history' && (
          <div className="animate-fade-in">
            <HistoryView
              history={history}
              userProfile={userProfile}
              language={userProfile.language}
              onSelectScan={(res) => {
                setCurrentScanResult(res);
                setCurrentTab('scanner');
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
              onClearHistory={handleClearHistory}
              onToggleFavorite={handleToggleFavorite}
              onCompareProducts={handleCompareTwo}
            />
          </div>
        )}

        {/* TAB 6: COMPARE VIEW */}
        {currentTab === 'compare' && (
          <div className="animate-fade-in">
            <CompareView
              productA={compareProductA}
              productB={compareProductB}
              allScans={allAvailableScans}
              userProfile={userProfile}
              onSelectA={(p) => setCompareProductA(p)}
              onSelectB={(p) => setCompareProductB(p)}
            />
          </div>
        )}
      </main>

      {/* MODALS */}
      
      {/* 1. PubMed Evidence Modal */}
      {selectedEvidence && (
        <EvidenceModal
          research={selectedEvidence}
          onClose={() => setSelectedEvidence(null)}
        />
      )}

      {/* 2. Family Profiles Modal */}
      <FamilyProfilesModal
        isOpen={isFamilyModalOpen}
        onClose={() => setIsFamilyModalOpen(false)}
        activeProfile={userProfile}
        onProfileSwitched={handleProfileSwitched}
      />

      {/* 3. AI Dietitian Consultation Modal */}
      {currentScanResult && (
        <AiDietitianChatModal
          isOpen={isAiChatModalOpen}
          onClose={() => setIsAiChatModalOpen(false)}
          product={currentScanResult}
          userProfile={userProfile}
        />
      )}

      {/* 4. Pro Upgrade Modal */}
      <ProUpgradeModal
        isOpen={isProModalOpen}
        onClose={() => setIsProModalOpen(false)}
        onUpgradeSuccess={() => setIsProUser(true)}
        isProUser={isProUser}
      />

      {/* 5. Batch / Pantry Audit Scanner Modal */}
      <BatchScanModal
        isOpen={isBatchModalOpen}
        onClose={() => setIsBatchModalOpen(false)}
        userProfile={userProfile}
        onSelectResult={(res) => {
          setCurrentScanResult(res);
          setCurrentTab('scanner');
        }}
      />

      {/* 6. Receipt & Cart Audit Scanner Modal */}
      <ReceiptCartAuditModal
        isOpen={isReceiptAuditModalOpen}
        onClose={() => setIsReceiptAuditModalOpen(false)}
        userProfile={userProfile}
        familyProfiles={familyProfiles}
        onSelectProduct={(barcode) => {
          reEvaluateCurrentProduct(barcode);
          setCurrentTab('scanner');
        }}
      />

      {/* 7. Supermarket & Local Stores Catalog Modal */}
      <SupermarketCatalogModal
        isOpen={isMarketCatalogModalOpen}
        onClose={() => setIsMarketCatalogModalOpen(false)}
        userProfile={userProfile}
        onSelectProduct={(barcode) => {
          reEvaluateCurrentProduct(barcode);
          setCurrentTab('scanner');
        }}
      />

      {/* 8. Cross-Reactivity Clinical Matrix Modal */}
      <CrossReactivityModal
        isOpen={isCrossReactivityModalOpen}
        onClose={() => setIsCrossReactivityModalOpen(false)}
        userProfile={userProfile}
      />

      {/* 9. Cosmeceutical Skincare Routine Radar & Active Collisions Shelf Modal */}
      <SkincareRoutineRadarModal
        isOpen={isSkincareRadarModalOpen}
        onClose={() => setIsSkincareRadarModalOpen(false)}
      />

      {/* 10. Herb-Drug, Botanical & Supplement Interaction Radar Modal */}
      <HerbDrugModal
        isOpen={isHerbDrugModalOpen}
        onClose={() => setIsHerbDrugModalOpen(false)}
        language={userProfile.language || 'en'}
        activeMedications={userProfile.medications || []}
      />

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-6 text-center text-xs text-slate-500 mt-12 mb-16 md:mb-0">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center space-x-2">
            <span className="font-bold text-slate-800">MedMatch AI</span>
            <span>•</span>
            <p>© {new Date().getFullYear()} Clinical Product Suitability, Safe Swaps & Toxic Exposure Radar</p>
          </div>
          <div className="flex items-center space-x-4 text-slate-600 text-xs">
            <span className="font-medium">Open Food Facts & USDA</span>
            <span>•</span>
            <span className="font-medium">NCBI PubMed Studies</span>
            <span>•</span>
            <span className="font-medium">On-device OCR & Clinical Engine</span>
          </div>
        </div>
      </footer>

      {/* Mobile Bottom Navigation Bar (Thumb Ergonomics) */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-[#0f172a]/95 backdrop-blur-md border-t border-slate-800 px-3 py-1.5 flex items-center justify-around shadow-lg">
        <button
          id="mobile-bottom-scan"
          onClick={() => setCurrentTab('scanner')}
          className={`flex flex-col items-center justify-center py-1 px-2.5 rounded-lg transition-colors min-w-[56px] min-h-[44px] ${
            currentTab === 'scanner'
              ? 'text-blue-400 font-bold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Scan className="w-5 h-5 mb-0.5" />
          <span className="text-[10px] tracking-tight">{getTranslation(userProfile.language || 'en', 'tabScanner', 'Scan')}</span>
        </button>

        <button
          id="mobile-bottom-swaps"
          onClick={() => setCurrentTab('swaps')}
          className={`flex flex-col items-center justify-center py-1 px-2.5 rounded-lg transition-colors min-w-[56px] min-h-[44px] ${
            currentTab === 'swaps'
              ? 'text-amber-400 font-bold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Sparkles className="w-5 h-5 mb-0.5" />
          <span className="text-[10px] tracking-tight">{getTranslation(userProfile.language || 'en', 'tabSwaps', 'Swaps')}</span>
        </button>

        <button
          id="mobile-bottom-dashboard"
          onClick={() => setCurrentTab('dashboard')}
          className={`flex flex-col items-center justify-center py-1 px-2.5 rounded-lg transition-colors min-w-[56px] min-h-[44px] ${
            currentTab === 'dashboard'
              ? 'text-blue-400 font-bold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Activity className="w-5 h-5 mb-0.5" />
          <span className="text-[10px] tracking-tight">{getTranslation(userProfile.language || 'en', 'tabDashboard', 'Health')}</span>
        </button>

        <button
          id="mobile-bottom-history"
          onClick={() => setCurrentTab('history')}
          className={`flex flex-col items-center justify-center py-1 px-2.5 rounded-lg transition-colors min-w-[56px] min-h-[44px] relative ${
            currentTab === 'history'
              ? 'text-blue-400 font-bold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <HistoryIcon className="w-5 h-5 mb-0.5" />
          <span className="text-[10px] tracking-tight">{getTranslation(userProfile.language || 'en', 'tabHistory', 'History')}</span>
          {history.length > 0 && (
            <span className="absolute top-1 right-2.5 w-4 h-4 rounded-full bg-blue-600 text-white text-[9px] font-bold flex items-center justify-center">
              {history.length > 9 ? '9+' : history.length}
            </span>
          )}
        </button>

        <button
          id="mobile-bottom-profile"
          onClick={() => setCurrentTab('profile')}
          className={`flex flex-col items-center justify-center py-1 px-2.5 rounded-lg transition-colors min-w-[56px] min-h-[44px] ${
            currentTab === 'profile'
              ? 'text-blue-400 font-bold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <UserCircle className="w-5 h-5 mb-0.5" />
          <span className="text-[10px] tracking-tight">{getTranslation(userProfile.language || 'en', 'tabProfile', 'Profile')}</span>
        </button>
      </div>
    </div>
  );
}

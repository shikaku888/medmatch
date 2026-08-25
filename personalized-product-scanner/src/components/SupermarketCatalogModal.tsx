import React, { useState, useEffect } from 'react';
import { SupermarketStore, MarketProductItem, UserProfile, SupportedCountry } from '../types';
import { getTranslation, COUNTRY_OPTIONS } from '../i18n';
import { 
  Store, 
  Search, 
  Filter, 
  X, 
  Sparkles, 
  Check, 
  AlertTriangle, 
  ShieldCheck, 
  ExternalLink, 
  Scan, 
  Layers,
  Flame,
  ArrowRight,
  Globe
} from 'lucide-react';

interface SupermarketCatalogModalProps {
  isOpen: boolean;
  onClose: () => void;
  userProfile: UserProfile;
  onSelectProduct: (barcode: string) => void;
}

export const SupermarketCatalogModal: React.FC<SupermarketCatalogModalProps> = ({
  isOpen,
  onClose,
  userProfile,
  onSelectProduct
}) => {
  const [stores, setStores] = useState<SupermarketStore[]>([]);
  const [products, setProducts] = useState<MarketProductItem[]>([]);
  const [selectedCountry, setSelectedCountry] = useState<SupportedCountry | 'ALL'>(userProfile.country || 'US');
  const [selectedStore, setSelectedStore] = useState<string>('traderjoes');
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [safetyFilter, setSafetyFilter] = useState<'all' | 'clean' | 'caution' | 'high_risk'>('all');
  const [loading, setLoading] = useState(true);

  const lang = userProfile.language || 'en';
  const t = (key: Parameters<typeof getTranslation>[1]) => getTranslation(lang, key);

  useEffect(() => {
    if (isOpen) {
      fetchStores();
    }
  }, [isOpen]);

  useEffect(() => {
    if (userProfile.country) {
      setSelectedCountry(userProfile.country);
    }
  }, [userProfile.country]);

  const fetchStores = async () => {
    try {
      setLoading(true);
      const res = await fetch('/api/markets');
      if (res.ok) {
        const data = await res.json();
        setStores(data.stores || []);
        setProducts(data.featuredProducts || []);
        
        // Auto select first store matching country
        const match = data.stores?.find((s: SupermarketStore) => s.country === (userProfile.country || 'US'));
        if (match) {
          setSelectedStore(match.id);
        } else if (data.stores?.length > 0) {
          setSelectedStore(data.stores[0].id);
        }
      }
    } catch (e) {
      console.warn('Failed to load market presets:', e);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const countryFilteredStores = selectedCountry === 'ALL'
    ? stores
    : stores.filter(s => s.country === selectedCountry);

  const currentStore = stores.find(s => s.id === selectedStore);

  const filteredProducts = products.filter(p => {
    if (selectedStore && p.storeId !== selectedStore) return false;
    if (selectedCategory !== 'All' && !p.category.toLowerCase().includes(selectedCategory.toLowerCase())) return false;
    if (safetyFilter !== 'all' && p.safetyTier !== safetyFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return p.name.toLowerCase().includes(q) || p.brand.toLowerCase().includes(q) || p.category.toLowerCase().includes(q);
    }
    return true;
  });

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/70 backdrop-blur-xs flex items-center justify-center p-3 sm:p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-4xl w-full max-h-[92vh] flex flex-col overflow-hidden text-slate-900 animate-in fade-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="p-4 sm:p-5 bg-[#0f172a] text-white flex items-center justify-between border-b border-slate-800">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-blue-500/20 text-blue-400 border border-blue-500/30">
              <Store className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-lg font-bold">{t('supermarkets')} & Retail Chains</h3>
                <span className="px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-400/30 text-[10px] font-bold uppercase tracking-wider">
                  US • UK • FR • DE • IT • ES
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Explore preset catalogs from Trader Joe's, Costco, Tesco, Carrefour, Edeka, Mercadona, and Conad.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Country Filter Tab Row */}
        <div className="bg-slate-950 border-b border-slate-800 px-4 py-2 flex items-center space-x-1.5 overflow-x-auto scrollbar-none">
          <button
            onClick={() => {
              setSelectedCountry('ALL');
              if (stores.length > 0) setSelectedStore(stores[0].id);
            }}
            className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-all shrink-0 flex items-center space-x-1 ${
              selectedCountry === 'ALL'
                ? 'bg-blue-600 text-white'
                : 'bg-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            <Globe className="w-3 h-3" />
            <span>All Markets</span>
          </button>

          {COUNTRY_OPTIONS.map(c => (
            <button
              key={c.code}
              onClick={() => {
                setSelectedCountry(c.code);
                const firstInCountry = stores.find(s => s.country === c.code);
                if (firstInCountry) setSelectedStore(firstInCountry.id);
              }}
              className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-all shrink-0 flex items-center space-x-1.5 ${
                selectedCountry === c.code
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-800 text-slate-300 hover:text-white'
              }`}
            >
              <span>{c.flag}</span>
              <span>{c.name}</span>
            </button>
          ))}
        </div>

        {/* Store Switcher Badges */}
        <div className="bg-slate-900/90 border-b border-slate-800 px-4 py-2.5 flex items-center space-x-2 overflow-x-auto scrollbar-none">
          {countryFilteredStores.map(store => (
            <button
              key={store.id}
              onClick={() => {
                setSelectedStore(store.id);
                setSelectedCategory('All');
              }}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all shrink-0 flex items-center space-x-1.5 ${
                selectedStore === store.id
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'bg-slate-800/80 text-slate-300 hover:bg-slate-800 hover:text-white border border-slate-700'
              }`}
            >
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/20 font-mono">
                {store.logoBadge}
              </span>
              <span>{store.name}</span>
            </button>
          ))}
        </div>

        {/* Content Body */}
        <div className="p-4 sm:p-6 overflow-y-auto flex-1 space-y-5">
          
          {/* Store Info Banner */}
          {currentStore && (
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <div className="text-xs font-bold text-slate-800 flex items-center space-x-1.5">
                  <span>{currentStore.name}</span>
                  <span className="text-[10px] text-slate-500 font-normal">• Market: {currentStore.country}</span>
                </div>
                <p className="text-xs text-slate-600 mt-0.5">{currentStore.description}</p>
              </div>

              {/* Categories */}
              <div className="flex items-center gap-1.5 flex-wrap">
                <button
                  onClick={() => setSelectedCategory('All')}
                  className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-colors ${
                    selectedCategory === 'All'
                      ? 'bg-slate-900 text-white'
                      : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-100'
                  }`}
                >
                  All
                </button>
                {currentStore.categories.map(cat => (
                  <button
                    key={cat}
                    onClick={() => setSelectedCategory(cat)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
                      selectedCategory === cat
                        ? 'bg-slate-900 text-white font-bold'
                        : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-100'
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Search & Safety Filter Bar */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="relative w-full sm:w-72">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search catalog items..."
                className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-slate-300 focus:ring-2 focus:ring-blue-500 bg-white"
              />
            </div>

            <div className="flex items-center space-x-1.5 bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs font-medium w-full sm:w-auto overflow-x-auto">
              <button
                onClick={() => setSafetyFilter('all')}
                className={`px-3 py-1 rounded-lg transition-all whitespace-nowrap ${safetyFilter === 'all' ? 'bg-white text-slate-900 font-bold shadow-2xs' : 'text-slate-600'}`}
              >
                All ({products.filter(p => p.storeId === selectedStore).length})
              </button>
              <button
                onClick={() => setSafetyFilter('clean')}
                className={`px-3 py-1 rounded-lg transition-all whitespace-nowrap ${safetyFilter === 'clean' ? 'bg-white text-emerald-700 font-bold shadow-2xs' : 'text-slate-600'}`}
              >
                Clean Standard
              </button>
              <button
                onClick={() => setSafetyFilter('caution')}
                className={`px-3 py-1 rounded-lg transition-all whitespace-nowrap ${safetyFilter === 'caution' ? 'bg-white text-amber-700 font-bold shadow-2xs' : 'text-slate-600'}`}
              >
                Caution
              </button>
              <button
                onClick={() => setSafetyFilter('high_risk')}
                className={`px-3 py-1 rounded-lg transition-all whitespace-nowrap ${safetyFilter === 'high_risk' ? 'bg-white text-rose-700 font-bold shadow-2xs' : 'text-slate-600'}`}
              >
                High Risk / Additives
              </button>
            </div>
          </div>

          {/* Product Grid */}
          <div className="grid sm:grid-cols-2 gap-3.5">
            {filteredProducts.map((p) => (
              <div
                key={p.barcode}
                className={`p-4 rounded-xl border transition-all flex flex-col justify-between ${
                  p.safetyTier === 'clean'
                    ? 'border-emerald-200 bg-emerald-50/20 hover:border-emerald-300'
                    : p.safetyTier === 'caution'
                    ? 'border-amber-200 bg-amber-50/20 hover:border-amber-300'
                    : 'border-rose-200 bg-rose-50/20 hover:border-rose-300'
                }`}
              >
                <div>
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div className="flex items-start space-x-2.5">
                      <img
                        src={p.image}
                        alt={p.name}
                        className="w-12 h-12 rounded-lg object-cover border border-slate-200 shrink-0 bg-white"
                      />
                      <div>
                        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-tight">
                          {p.brand} • {p.category}
                        </span>
                        <h5 className="text-xs font-bold text-slate-900 line-clamp-1">{p.name}</h5>
                        <div className="flex items-center space-x-1.5 mt-1">
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${
                            p.safetyTier === 'clean'
                              ? 'bg-emerald-100 text-emerald-800'
                              : p.safetyTier === 'caution'
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-rose-100 text-rose-800'
                          }`}>
                            {p.highlightTag}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="text-right shrink-0">
                      <span className={`text-xs font-black px-2 py-1 rounded-lg ${
                        p.familyCompatibilityScore >= 80 
                          ? 'bg-emerald-100 text-emerald-800' 
                          : p.familyCompatibilityScore >= 50 
                          ? 'bg-amber-100 text-amber-800' 
                          : 'bg-rose-100 text-rose-800'
                      }`}>
                        {p.familyCompatibilityScore}/100
                      </span>
                    </div>
                  </div>

                  <p className="text-[11px] text-slate-600 line-clamp-2 mt-2">
                    {p.ingredientsText}
                  </p>
                </div>

                <div className="mt-3 pt-3 border-t border-slate-200/60 flex items-center justify-between">
                  <div className="text-xs font-bold text-slate-700">
                    {p.priceEur ? `€${p.priceEur.toFixed(2)}` : p.priceGbp ? `£${p.priceGbp.toFixed(2)}` : p.priceUsd ? `$${p.priceUsd.toFixed(2)}` : 'Market Price'}
                  </div>

                  <button
                    onClick={() => {
                      onSelectProduct(p.barcode);
                      onClose();
                    }}
                    className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs flex items-center space-x-1.5 transition-colors shadow-2xs"
                  >
                    <Scan className="w-3.5 h-3.5" />
                    <span>Scan & Evaluate</span>
                  </button>
                </div>
              </div>
            ))}
          </div>

          {filteredProducts.length === 0 && (
            <div className="p-8 text-center text-slate-500 bg-slate-50 rounded-2xl border border-slate-200">
              <Store className="w-8 h-8 mx-auto text-slate-400 mb-2" />
              <p className="text-xs font-bold">No products match the selected filters.</p>
              <p className="text-[11px] text-slate-400 mt-0.5">Try selecting another category or market tab.</p>
            </div>
          )}

        </div>

        {/* Footer */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex items-center justify-between text-xs text-slate-500">
          <span>Benchmarked against EFSA (EU), FDA (US), and FSA (UK) standards</span>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-900 text-white font-bold text-xs transition-colors"
          >
            Close
          </button>
        </div>

      </div>
    </div>
  );
};


import React, { useState } from 'react';
import { ScanHistoryItem, ProductScanResult, UserProfile, SupportedLanguage } from '../types';
import { getTranslation } from '../i18n';
import { 
  History as HistoryIcon, 
  Search, 
  Trash2, 
  ShieldCheck, 
  AlertTriangle, 
  AlertOctagon, 
  Info, 
  Bookmark, 
  ArrowRight,
  GitCompare
} from 'lucide-react';

interface HistoryViewProps {
  history: ScanHistoryItem[];
  userProfile?: UserProfile;
  language?: SupportedLanguage;
  onSelectScan: (result: ProductScanResult) => void;
  onClearHistory: () => void;
  onToggleFavorite: (id: string) => void;
  onCompareProducts?: (p1: ProductScanResult, p2: ProductScanResult) => void;
}

export const HistoryView: React.FC<HistoryViewProps> = ({
  history,
  userProfile,
  language = userProfile?.language || 'en',
  onSelectScan,
  onClearHistory,
  onToggleFavorite,
  onCompareProducts
}) => {
  const t = (key: string, fallback?: string) => getTranslation(language, key, fallback);

  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [compareList, setCompareList] = useState<ScanHistoryItem[]>([]);

  const filtered = history.filter((item) => {
    const matchesSearch = 
      item.productName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (item.brand && item.brand.toLowerCase().includes(searchQuery.toLowerCase())) ||
      item.barcode.includes(searchQuery);

    const matchesStatus = filterStatus === 'all' || 
      (filterStatus === 'favorites' && item.favorite) ||
      item.status === filterStatus;

    return matchesSearch && matchesStatus;
  });

  const toggleCompare = (item: ScanHistoryItem) => {
    if (compareList.some(c => c.id === item.id)) {
      setCompareList(compareList.filter(c => c.id !== item.id));
    } else {
      if (compareList.length >= 2) {
        setCompareList([compareList[1], item]);
      } else {
        setCompareList([...compareList, item]);
      }
    }
  };

  const handleTriggerCompare = () => {
    if (compareList.length === 2 && compareList[0].fullResult && compareList[1].fullResult && onCompareProducts) {
      onCompareProducts(compareList[0].fullResult, compareList[1].fullResult);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'safe':
        return {
          bg: 'bg-emerald-50 text-emerald-800 border-emerald-200',
          icon: ShieldCheck,
          label: t('statusSafe', 'Compatible')
        };
      case 'caution':
        return {
          bg: 'bg-yellow-50 text-yellow-800 border-yellow-200',
          icon: Info,
          label: t('statusCaution', 'Caution')
        };
      case 'warning':
        return {
          bg: 'bg-amber-50 text-amber-800 border-amber-200',
          icon: AlertTriangle,
          label: t('statusWarning', 'Conflict')
        };
      case 'danger':
      default:
        return {
          bg: 'bg-rose-50 text-rose-800 border-rose-200',
          icon: AlertOctagon,
          label: t('statusDanger', 'Allergy Alert')
        };
    }
  };

  return (
    <div className="space-y-6">
      {/* Header with Search and Clear */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white border border-slate-200 p-6 rounded-xl shadow-sm">
        <div className="flex items-center space-x-3.5">
          <div className="w-12 h-12 rounded-xl bg-blue-50 border border-blue-100 text-blue-600 flex items-center justify-center">
            <HistoryIcon className="w-7 h-7" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">
              {t('historyTitle', 'Scan History & Verified Products')}
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              {t('historySubtitle', 'Review past scanned grocery, cosmetic, and supplement assessments.')}
            </p>
          </div>
        </div>

        {history.length > 0 && (
          <button
            onClick={onClearHistory}
            className="px-3.5 py-2 rounded-lg bg-white hover:bg-rose-50 text-slate-600 hover:text-rose-700 border border-slate-300 hover:border-rose-200 text-xs font-semibold transition-colors flex items-center space-x-2 shadow-2xs cursor-pointer"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>{t('clearHistory', 'Clear All')}</span>
          </button>
        )}
      </div>

      {/* Compare Floating Banner if 2 items selected */}
      {compareList.length > 0 && (
        <div className="p-4 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-between gap-4 shadow-sm">
          <div className="flex items-center space-x-3 text-xs">
            <GitCompare className="w-5 h-5 text-blue-600" />
            <div>
              <span className="font-bold text-blue-900">
                {compareList.length}/2 {t('compareProducts', 'Selected for Comparison')}:
              </span>
              <span className="text-slate-700 ml-2 font-medium">
                {compareList.map(c => c.productName).join(' vs ')}
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => setCompareList([])}
              className="text-xs text-slate-600 hover:text-slate-900 px-2.5 py-1.5 font-medium cursor-pointer"
            >
              {t('close', 'Clear')}
            </button>
            <button
              onClick={handleTriggerCompare}
              disabled={compareList.length < 2}
              className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-bold text-xs rounded-lg transition-colors shadow-2xs cursor-pointer"
            >
              {t('compareProduct', 'Compare Now')}
            </button>
          </div>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="flex flex-col md:flex-row gap-3">
        <div className="relative flex-1">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('searchPlaceholder', 'Search past scans by name, brand, or barcode...')}
            className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-300 rounded-lg text-slate-900 placeholder-slate-400 text-xs focus:outline-none focus:border-blue-600 focus:bg-white"
          />
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-2.5" />
        </div>

        {/* Filter Pills */}
        <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 text-xs">
          {[
            { key: 'all', label: t('allScans', 'All') },
            { key: 'safe', label: t('statusSafe', 'Compatible') },
            { key: 'warning', label: t('statusWarning', 'Warnings') },
            { key: 'danger', label: t('statusDanger', 'Allergy Alerts') },
            { key: 'favorites', label: t('savedFavorites', 'Favorites') }
          ].map(f => (
            <button
              key={f.key}
              onClick={() => setFilterStatus(f.key)}
              className={`px-3 py-1.5 rounded-lg font-semibold transition-colors shrink-0 cursor-pointer shadow-2xs ${
                filterStatus === f.key
                  ? 'bg-blue-600 text-white border border-blue-600'
                  : 'bg-white text-slate-600 hover:text-slate-900 border border-slate-200 hover:bg-slate-50'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* History Items List */}
      {filtered.length > 0 ? (
        <div className="grid grid-cols-1 gap-3">
          {filtered.map((item) => {
            const badge = getStatusBadge(item.status);
            const BadgeIcon = badge.icon;
            const isComparing = compareList.some(c => c.id === item.id);

            return (
              <div
                key={item.id}
                className="p-4 rounded-xl bg-white border border-slate-200 hover:border-slate-300 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm"
              >
                <div 
                  onClick={() => item.fullResult && onSelectScan(item.fullResult)}
                  className="flex items-center space-x-3.5 flex-1 cursor-pointer group"
                >
                  {item.imageUrl ? (
                    <img
                      src={item.imageUrl}
                      alt={item.productName}
                      className="w-14 h-14 rounded-lg object-cover bg-slate-50 border border-slate-200 shrink-0"
                    />
                  ) : (
                    <div className="w-14 h-14 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-center shrink-0 text-slate-400">
                      <HistoryIcon className="w-6 h-6" />
                    </div>
                  )}

                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center space-x-2">
                      <span className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-bold border ${badge.bg}`}>
                        <BadgeIcon className="w-3 h-3" />
                        <span>{badge.label}</span>
                      </span>
                      <span className="text-[10px] uppercase font-bold text-slate-500">
                        {item.productType}
                      </span>
                      <span className="text-[10px] text-slate-400 font-mono">
                        {new Date(item.scannedAt).toLocaleDateString()}
                      </span>
                    </div>

                    <h4 className="text-sm font-bold text-slate-900 group-hover:text-blue-600 transition-colors truncate">
                      {item.productName}
                    </h4>

                    {item.brand && (
                      <p className="text-xs text-slate-500 truncate">
                        {item.brand} • <span className="font-mono text-slate-400">{item.barcode}</span>
                      </p>
                    )}
                  </div>
                </div>

                {/* Score & Actions */}
                <div className="flex items-center space-x-2 shrink-0 self-end sm:self-center">
                  <div className="text-right pr-2">
                    <span className="block text-[10px] text-slate-400 uppercase font-semibold">Score</span>
                    <span className={`text-sm font-black ${
                      item.score >= 80 ? 'text-emerald-700' : item.score >= 50 ? 'text-amber-600' : 'text-rose-600'
                    }`}>
                      {item.score}/100
                    </span>
                  </div>

                  <button
                    onClick={() => toggleCompare(item)}
                    className={`p-2 rounded-lg border text-xs transition-colors cursor-pointer ${
                      isComparing 
                        ? 'bg-blue-50 border-blue-500 text-blue-700' 
                        : 'bg-white border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                    }`}
                    title="Select to compare"
                  >
                    <GitCompare className="w-4 h-4" />
                  </button>

                  <button
                    onClick={() => onToggleFavorite(item.id)}
                    className={`p-2 rounded-lg border text-xs transition-colors cursor-pointer ${
                      item.favorite 
                        ? 'bg-amber-50 border-amber-400 text-amber-600' 
                        : 'bg-white border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                    }`}
                    title="Bookmark"
                  >
                    <Bookmark className="w-4 h-4" />
                  </button>

                  <button
                    onClick={() => item.fullResult && onSelectScan(item.fullResult)}
                    className="p-2 rounded-lg bg-slate-50 hover:bg-slate-100 text-slate-700 hover:text-slate-900 border border-slate-200 transition-colors cursor-pointer"
                    title="Open Full Result"
                  >
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="p-12 text-center bg-white border border-slate-200 rounded-xl space-y-3 shadow-sm">
          <HistoryIcon className="w-12 h-12 text-slate-300 mx-auto" />
          <h3 className="text-base font-bold text-slate-800">{t('noHistoryMatch', 'No scan history recorded')}</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            {t('noHistoryMatchDesc', 'Scan a barcode, analyze ingredients, or load preset sample products to build your history.')}
          </p>
        </div>
      )}
    </div>
  );
};

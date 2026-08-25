import React, { useState, useRef } from 'react';
import { 
  ReceiptAuditResult, 
  ParsedReceiptItem, 
  UserProfile, 
  FamilyProfile, 
  ProductScanResult 
} from '../types';
import { 
  Receipt, 
  Camera, 
  Upload, 
  Sparkles, 
  X, 
  AlertTriangle, 
  ShieldCheck, 
  ShieldAlert, 
  Users, 
  ArrowRight, 
  RefreshCw, 
  ShoppingBag, 
  CheckCircle2, 
  Layers, 
  Store, 
  HelpCircle,
  FileText,
  Percent,
  Flame,
  ArrowUpRight
} from 'lucide-react';

interface ReceiptCartAuditModalProps {
  isOpen: boolean;
  onClose: () => void;
  userProfile: UserProfile;
  familyProfiles: FamilyProfile[];
  onSelectProduct?: (barcode: string) => void;
}

const SAMPLE_RECEIPTS = [
  {
    title: "Trader Joe's & Costco (US)",
    store: "Trader Joe's",
    text: `1. Organic Creamy Sunflower Seed Butter 16oz
2. Cauliflower Gnocchi 12oz
3. Nutella Hazelnut Spread 13oz
4. Lay's Classic Potato Chips Party Size
5. Oatly Barista Edition Oat Milk 32oz`
  },
  {
    title: 'Tesco Express Haul (UK)',
    store: 'Tesco',
    text: `1. Innocent Super Smoothie Recharge 750ml
2. Marmite Yeast Extract 250g
3. McVitie's Milk Chocolate Digestives 266g
4. Alpro Soya No Sugars 1L
5. Walkers Ready Salted Crisps 6 Pack`
  },
  {
    title: 'Carrefour Bio (France)',
    store: 'Carrefour',
    text: `1. Carrefour Bio Lait Demi-Écrémé 1L
2. Lu Petit Beurre Biscuits 200g
3. Bonne Maman Confiture Fraises 370g
4. Danone Activia Nature 4x125g
5. Haribo Tagada Bonbons 300g`
  },
  {
    title: 'Edeka & Rewe (Germany)',
    store: 'Edeka',
    text: `1. Alnatura Haferdrink Ungesüßt 1L
2. Ritter Sport Voll-Nuss 100g
3. Dr. Oetker Ristorante Pizza Salame 320g
4. Leibniz Butterkeks 200g`
  },
  {
    title: 'Mercadona Haul (Spain)',
    store: 'Mercadona',
    text: `1. Hacendado Gazpacho Tradicional Fresco 1L
2. Tortilla de Patatas con Cebolla Hacendado 600g
3. Jamón Serrano Gran Reserva 100g
4. Bebida de Avena Sin Azúcar 1L
5. Galletas María Dorada Hacendado 800g`
  },
  {
    title: 'Pharmacy & Skincare Receipt',
    store: 'Pharmacy Dermacenter',
    text: `1. La Roche-Posay Toleriane Dermo-Cleanser 200ml
2. CeraVe Hydrating Facial Cleanser 236ml
3. The Ordinary Niacinamide 10% + Zinc 1% 30ml
4. Bioderma Sensibio H2O Micellar Water 500ml`
  }
];

export const ReceiptCartAuditModal: React.FC<ReceiptCartAuditModalProps> = ({
  isOpen,
  onClose,
  userProfile,
  familyProfiles,
  onSelectProduct
}) => {
  const [mode, setMode] = useState<'upload' | 'text' | 'sample'>('sample');
  const [receiptText, setReceiptText] = useState(SAMPLE_RECEIPTS[0].text);
  const [storeHint, setStoreHint] = useState(SAMPLE_RECEIPTS[0].store);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [auditResult, setAuditResult] = useState<ReceiptAuditResult | null>(null);
  const [filterCategory, setFilterCategory] = useState<'all' | 'safe' | 'caution' | 'danger'>('all');
  const [expandedItem, setExpandedItem] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      setSelectedImage(event.target?.result as string);
      setMode('upload');
    };
    reader.readAsDataURL(file);
  };

  const handleRunAudit = async () => {
    setLoading(true);
    setAuditResult(null);

    try {
      let payload: any = {
        storeNameHint: storeHint,
        country: userProfile.country || 'US',
        language: userProfile.language || 'en',
        medications: userProfile.medications || []
      };

      if (mode === 'upload' && selectedImage) {
        payload.imageBase64 = selectedImage;
      } else {
        payload.receiptText = receiptText;
      }

      const res = await fetch('/api/scan/receipt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        throw new Error('Failed to parse receipt');
      }

      const data: ReceiptAuditResult = await res.json();
      setAuditResult(data);
    } catch (err: any) {
      console.error('Audit failed:', err);
      alert('Unable to analyze the receipt at this time. Please try again with a clearer photo or pasted text items.');
    } finally {
      setLoading(false);
    }
  };

  const filteredItems = auditResult?.items.filter(item => {
    if (filterCategory === 'all') return true;
    return item.status === filterCategory;
  }) || [];

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/70 backdrop-blur-xs flex items-center justify-center p-3 sm:p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-4xl w-full max-h-[92vh] flex flex-col overflow-hidden text-slate-900 animate-in fade-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="p-4 sm:p-5 bg-[#0b1120] text-white flex items-center justify-between border-b border-slate-800">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-br from-amber-500/20 to-orange-500/20 text-amber-400 border border-amber-500/30">
              <Receipt className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-lg font-bold">Batch Receipt & Shopping Cart Audit</h3>
                <span className="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-400/30 text-[10px] font-bold uppercase tracking-wider">
                  AI Vision 3.7
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Scan grocery receipts or paste carts for multi-profile biological allergen safety scoring.
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

        {/* Modal Body */}
        <div className="p-4 sm:p-6 overflow-y-auto flex-1 space-y-6">
          
          {!auditResult ? (
            /* Input Selection View */
            <div className="space-y-6">
              
              {/* Method Switcher Tabs */}
              <div className="grid grid-cols-3 gap-2 p-1.5 bg-slate-100 rounded-xl border border-slate-200 text-xs font-semibold">
                <button
                  onClick={() => setMode('sample')}
                  className={`py-2 px-3 rounded-lg flex items-center justify-center space-x-1.5 transition-all ${
                    mode === 'sample' 
                      ? 'bg-white text-slate-900 shadow-xs font-bold' 
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                  <span>Sample Receipts</span>
                </button>
                <button
                  onClick={() => setMode('upload')}
                  className={`py-2 px-3 rounded-lg flex items-center justify-center space-x-1.5 transition-all ${
                    mode === 'upload' 
                      ? 'bg-white text-slate-900 shadow-xs font-bold' 
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <Camera className="w-3.5 h-3.5 text-blue-500" />
                  <span>Take Photo / Upload</span>
                </button>
                <button
                  onClick={() => setMode('text')}
                  className={`py-2 px-3 rounded-lg flex items-center justify-center space-x-1.5 transition-all ${
                    mode === 'text' 
                      ? 'bg-white text-slate-900 shadow-xs font-bold' 
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <FileText className="w-3.5 h-3.5 text-emerald-500" />
                  <span>Paste Item List</span>
                </button>
              </div>

              {/* Mode Content */}
              {mode === 'sample' && (
                <div className="space-y-4">
                  <p className="text-xs text-slate-600 font-medium">
                    Select a realistic supermarket receipt sample to test AI audit speed:
                  </p>
                  <div className="grid sm:grid-cols-3 gap-3">
                    {SAMPLE_RECEIPTS.map((s, idx) => (
                      <button
                        key={idx}
                        onClick={() => {
                          setReceiptText(s.text);
                          setStoreHint(s.store);
                        }}
                        className={`p-3.5 rounded-xl border text-left transition-all ${
                          receiptText === s.text
                            ? 'border-amber-500 bg-amber-50/50 shadow-xs'
                            : 'border-slate-200 bg-white hover:border-slate-300'
                        }`}
                      >
                        <div className="flex items-center space-x-1.5 text-amber-700 font-bold text-xs mb-1">
                          <Store className="w-3.5 h-3.5" />
                          <span>{s.store}</span>
                        </div>
                        <h4 className="text-xs font-bold text-slate-900 mb-2">{s.title}</h4>
                        <pre className="text-[10px] text-slate-500 font-mono whitespace-pre-line line-clamp-3 bg-white p-1.5 rounded border border-slate-100">
                          {s.text}
                        </pre>
                      </button>
                    ))}
                  </div>

                  <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200">
                    <label className="block text-xs font-bold text-slate-700 mb-1">
                      View & Edit items on receipt:
                    </label>
                    <textarea
                      rows={5}
                      value={receiptText}
                      onChange={(e) => setReceiptText(e.target.value)}
                      className="w-full text-xs font-mono p-2.5 rounded-lg border border-slate-300 bg-white focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
                    />
                  </div>
                </div>
              )}

              {mode === 'upload' && (
                <div className="space-y-4">
                  <input
                    type="file"
                    ref={fileInputRef}
                    accept="image/*"
                    onChange={handleImageUpload}
                    className="hidden"
                  />

                  {selectedImage ? (
                    <div className="relative rounded-xl overflow-hidden border border-slate-200 max-h-64 flex items-center justify-center bg-slate-900">
                      <img
                        src={selectedImage}
                        alt="Receipt preview"
                        className="max-h-64 w-auto object-contain"
                      />
                      <button
                        onClick={() => setSelectedImage(null)}
                        className="absolute top-2 right-2 p-1.5 rounded-full bg-slate-900/80 text-white hover:bg-slate-900"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  ) : (
                    <div
                      onClick={() => fileInputRef.current?.click()}
                      className="border-2 border-dashed border-slate-300 hover:border-amber-500 rounded-2xl p-8 text-center cursor-pointer transition-all bg-slate-50 hover:bg-amber-50/30"
                    >
                      <div className="w-12 h-12 mx-auto rounded-full bg-amber-100 text-amber-600 flex items-center justify-center mb-3">
                        <Upload className="w-6 h-6" />
                      </div>
                      <h4 className="text-sm font-bold text-slate-800">Upload or Photograph Supermarket Receipt</h4>
                      <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                        Supports receipts from Trader Joe's, Costco, Tesco, Carrefour, Edeka, Whole Foods, or online order bills.
                      </p>
                    </div>
                  )}

                  <div className="flex items-center space-x-2">
                    <label className="text-xs font-bold text-slate-700 whitespace-nowrap">Store name (optional):</label>
                    <input
                      type="text"
                      value={storeHint}
                      onChange={(e) => setStoreHint(e.target.value)}
                      placeholder="e.g. Trader Joe's, Costco, Tesco..."
                      className="flex-1 px-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:ring-2 focus:ring-amber-500"
                    />
                  </div>
                </div>
              )}

              {mode === 'text' && (
                <div className="space-y-3">
                  <label className="block text-xs font-bold text-slate-700">
                    Paste receipt lines, grocery list, or cart items:
                  </label>
                  <textarea
                    rows={7}
                    value={receiptText}
                    onChange={(e) => setReceiptText(e.target.value)}
                    placeholder="e.g.:
1. Organic Whole Milk 1L
2. Peanut Butter Crunchy 500g
3. Gluten Free Oat Bread
4. Natural Almond Drink"
                    className="w-full text-xs font-mono p-3 rounded-xl border border-slate-300 focus:ring-2 focus:ring-amber-500 bg-white"
                  />
                  <div className="flex items-center space-x-2">
                    <label className="text-xs font-bold text-slate-700 whitespace-nowrap">Store / Market Name:</label>
                    <input
                      type="text"
                      value={storeHint}
                      onChange={(e) => setStoreHint(e.target.value)}
                      placeholder="e.g. Whole Foods, Trader Joe's, Costco..."
                      className="flex-1 px-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:ring-2 focus:ring-amber-500"
                    />
                  </div>
                </div>
              )}

              {/* Family Context Bar */}
              <div className="p-3.5 rounded-xl bg-blue-50/70 border border-blue-200/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                <div className="flex items-center space-x-2 text-blue-900 font-semibold">
                  <Users className="w-4 h-4 text-blue-600 shrink-0" />
                  <span>
                    Cross-auditing mode for {familyProfiles.length > 0 ? `${familyProfiles.length} family members` : 'User Profile'}
                  </span>
                </div>
                <div className="flex items-center space-x-1.5 flex-wrap">
                  {familyProfiles.map(m => (
                    <span
                      key={m.id}
                      className="px-2 py-0.5 rounded-md bg-white border border-blue-200 text-[11px] text-blue-800 font-medium shadow-2xs"
                    >
                      {m.name} ({m.role})
                    </span>
                  ))}
                </div>
              </div>

              {/* Action Button */}
              <button
                onClick={handleRunAudit}
                disabled={loading || (mode === 'upload' && !selectedImage) || (mode !== 'upload' && !receiptText.trim())}
                className="w-full py-3.5 rounded-xl bg-gradient-to-r from-amber-500 via-orange-500 to-amber-600 hover:from-amber-600 hover:to-orange-700 text-white font-bold text-sm shadow-md transition-all flex items-center justify-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>AI is auditing all items & family allergy profiles...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>Run Receipt Safety Audit Now</span>
                  </>
                )}
              </button>
            </div>
          ) : (
            /* Results View */
            <div className="space-y-6 animate-in fade-in duration-300">
              
              {/* Overall Score Banner */}
              <div className={`p-5 rounded-2xl border text-slate-900 ${
                auditResult.status === 'safe'
                  ? 'bg-emerald-50/80 border-emerald-300'
                  : auditResult.status === 'caution'
                  ? 'bg-amber-50/80 border-amber-300'
                  : 'bg-rose-50/80 border-rose-300'
              }`}>
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="flex items-start space-x-3.5">
                    <div className={`p-3 rounded-xl shrink-0 ${
                      auditResult.status === 'safe'
                        ? 'bg-emerald-500 text-white'
                        : auditResult.status === 'caution'
                        ? 'bg-amber-500 text-white'
                        : 'bg-rose-500 text-white'
                    }`}>
                      {auditResult.status === 'safe' ? (
                        <ShieldCheck className="w-7 h-7" />
                      ) : auditResult.status === 'caution' ? (
                        <AlertTriangle className="w-7 h-7" />
                      ) : (
                        <ShieldAlert className="w-7 h-7" />
                      )}
                    </div>
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="text-xs font-bold uppercase tracking-wider text-slate-600">
                          {auditResult.storeName} • {new Date(auditResult.auditDate).toLocaleDateString('en-US')}
                        </span>
                      </div>
                      <h4 className="text-xl font-extrabold text-slate-900 mt-0.5">
                        {auditResult.status === 'safe' && 'Cart Meets Family Biological Safety Standards'}
                        {auditResult.status === 'caution' && 'Cart Has Flagged Items Requiring Caution'}
                        {auditResult.status === 'danger' && 'Warning: High Risk Items Detected in Cart'}
                      </h4>
                      <p className="text-xs text-slate-700 mt-1 max-w-xl">
                        {auditResult.familyImpactSummary[0] || 'Full audit completed across all scanned receipt items.'}
                      </p>
                    </div>
                  </div>

                  {/* Score Pill */}
                  <div className="flex items-center space-x-3 bg-white px-4 py-3 rounded-xl border border-slate-200 shadow-xs shrink-0 self-start md:self-auto">
                    <div className="text-right">
                      <div className="text-[11px] font-bold text-slate-500 uppercase tracking-tight">Cart Safety Score</div>
                      <div className="text-2xl font-black text-slate-900">{auditResult.overallScore}/100</div>
                    </div>
                    <div className={`w-3 h-10 rounded-full ${
                      auditResult.overallScore >= 80 ? 'bg-emerald-500' : auditResult.overallScore >= 50 ? 'bg-amber-500' : 'bg-rose-500'
                    }`} />
                  </div>
                </div>

                {/* Key Summary Stats Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mt-4 pt-4 border-t border-slate-200/60">
                  <div className="bg-white/80 p-2.5 rounded-xl border border-slate-200/60">
                    <div className="text-[11px] text-slate-500 font-medium">Total Items</div>
                    <div className="text-base font-bold text-slate-900">{auditResult.totalItemsCount} items</div>
                  </div>
                  <div className="bg-white/80 p-2.5 rounded-xl border border-slate-200/60">
                    <div className="text-[11px] text-emerald-600 font-medium">Safe for Family</div>
                    <div className="text-base font-bold text-emerald-700">{auditResult.safeItemsCount} items</div>
                  </div>
                  <div className="bg-white/80 p-2.5 rounded-xl border border-slate-200/60">
                    <div className="text-[11px] text-amber-600 font-medium">Use Caution</div>
                    <div className="text-base font-bold text-amber-700">{auditResult.flaggedItemsCount} items</div>
                  </div>
                  <div className="bg-white/80 p-2.5 rounded-xl border border-slate-200/60">
                    <div className="text-[11px] text-rose-600 font-medium">High Allergy/Toxin Risk</div>
                    <div className="text-base font-bold text-rose-700">{auditResult.highRiskCount} items</div>
                  </div>
                </div>
              </div>

              {/* Family Alerts Banner (if any) */}
              {auditResult.criticalAdditivesFound.length > 0 || auditResult.keyAllergensFound.length > 0 ? (
                <div className="p-4 rounded-xl bg-slate-900 text-white text-xs space-y-2">
                  <div className="flex items-center space-x-2 text-amber-400 font-bold">
                    <AlertTriangle className="w-4 h-4" />
                    <span>Allergens & Additives Flagged in Cart:</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {auditResult.keyAllergensFound.map(a => (
                      <span key={a} className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30 font-medium">
                        Allergen: {a}
                      </span>
                    ))}
                    {auditResult.criticalAdditivesFound.map(ad => (
                      <span key={ad} className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 font-medium">
                        Additive: {ad}
                      </span>
                    ))}
                    {auditResult.ultraProcessedPercentage > 0 && (
                      <span className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 font-medium">
                        Ultra-Processed Food (NOVA 4): {auditResult.ultraProcessedPercentage}%
                      </span>
                    )}
                  </div>
                </div>
              ) : null}

              {/* Filter Tabs */}
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="flex items-center space-x-1.5 bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs font-semibold">
                  <button
                    onClick={() => setFilterCategory('all')}
                    className={`px-3 py-1 rounded-lg transition-all ${filterCategory === 'all' ? 'bg-white text-slate-900 shadow-2xs' : 'text-slate-600'}`}
                  >
                    All ({auditResult.items.length})
                  </button>
                  <button
                    onClick={() => setFilterCategory('safe')}
                    className={`px-3 py-1 rounded-lg transition-all ${filterCategory === 'safe' ? 'bg-white text-emerald-700 shadow-2xs font-bold' : 'text-slate-600'}`}
                  >
                    Safe ({auditResult.safeItemsCount})
                  </button>
                  <button
                    onClick={() => setFilterCategory('caution')}
                    className={`px-3 py-1 rounded-lg transition-all ${filterCategory === 'caution' ? 'bg-white text-amber-700 shadow-2xs font-bold' : 'text-slate-600'}`}
                  >
                    Caution ({auditResult.flaggedItemsCount})
                  </button>
                  <button
                    onClick={() => setFilterCategory('danger')}
                    className={`px-3 py-1 rounded-lg transition-all ${filterCategory === 'danger' ? 'bg-white text-rose-700 shadow-2xs font-bold' : 'text-slate-600'}`}
                  >
                    Danger ({auditResult.highRiskCount})
                  </button>
                </div>

                <button
                  onClick={() => setAuditResult(null)}
                  className="text-xs font-bold text-slate-600 hover:text-slate-900 flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Scan Another Receipt</span>
                </button>
              </div>

              {/* Items List */}
              <div className="space-y-3">
                {filteredItems.map((item) => (
                  <div
                    key={item.id}
                    className={`p-4 rounded-xl border transition-all ${
                      item.status === 'safe'
                        ? 'border-emerald-200 bg-emerald-50/20'
                        : item.status === 'caution'
                        ? 'border-amber-200 bg-amber-50/20'
                        : 'border-rose-200 bg-rose-50/30'
                    }`}
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-start space-x-3">
                        <div className={`p-2 rounded-lg shrink-0 mt-0.5 ${
                          item.status === 'safe'
                            ? 'bg-emerald-100 text-emerald-700'
                            : item.status === 'caution'
                            ? 'bg-amber-100 text-amber-700'
                            : 'bg-rose-100 text-rose-700'
                        }`}>
                          {item.status === 'safe' ? (
                            <CheckCircle2 className="w-4 h-4" />
                          ) : (
                            <AlertTriangle className="w-4 h-4" />
                          )}
                        </div>
                        <div>
                          <div className="flex items-center space-x-2 flex-wrap">
                            <h5 className="text-sm font-bold text-slate-900">{item.name}</h5>
                            <span className="text-[10px] px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 border border-slate-200">
                              {item.category}
                            </span>
                            {item.novaGroup && item.novaGroup >= 4 && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 border border-purple-200 font-bold">
                                NOVA 4
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-slate-600 mt-0.5">
                            {item.ingredientsSummary}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center space-x-2 self-end sm:self-auto shrink-0">
                        <span className={`text-xs font-black px-2.5 py-1 rounded-lg ${
                          item.score >= 80 
                            ? 'bg-emerald-100 text-emerald-800' 
                            : item.score >= 50 
                            ? 'bg-amber-100 text-amber-800' 
                            : 'bg-rose-100 text-rose-800'
                        }`}>
                          {item.score}/100
                        </span>
                      </div>
                    </div>

                    {/* Affected Family Members */}
                    {item.affectedFamilyMembers && item.affectedFamilyMembers.length > 0 && (
                      <div className="mt-2.5 pt-2.5 border-t border-slate-200/60 flex items-center space-x-1.5 text-xs text-rose-700 font-medium">
                        <Users className="w-3.5 h-3.5 text-rose-600" />
                        <span>Warning: Family member must avoid:</span>
                        <div className="flex gap-1 flex-wrap">
                          {item.affectedFamilyMembers.map(fam => (
                            <span key={fam} className="px-2 py-0.5 rounded-md bg-rose-100 text-rose-800 font-bold text-[10px]">
                              {fam}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Safe Swap Suggestion (If item flagged) */}
                    {item.suggestedSwap && (
                      <div className="mt-3 p-3 rounded-lg bg-white border border-amber-200 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2 shadow-2xs">
                        <div className="flex items-center space-x-2">
                          <Sparkles className="w-4 h-4 text-amber-500 shrink-0" />
                          <div>
                            <div className="text-[11px] font-bold text-amber-800">
                              Safer alternative recommendation: <span className="font-extrabold text-slate-900">{item.suggestedSwap.name}</span> ({item.suggestedSwap.brand})
                            </div>
                            <div className="text-[10px] text-slate-500">
                              {item.suggestedSwap.whyBetter}
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>

            </div>
          )}

        </div>

        {/* Footer */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex items-center justify-between text-xs text-slate-500">
          <div className="flex items-center space-x-1.5">
            <ShieldCheck className="w-4 h-4 text-blue-600" />
            <span>Cross-referenced against international EFSA, FDA & INCI scientific registries</span>
          </div>
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

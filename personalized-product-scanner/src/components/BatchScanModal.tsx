import React, { useState } from 'react';
import { ProductScanResult, UserProfile } from '../types';
import { 
  Layers, 
  Sparkles, 
  X, 
  Check, 
  AlertTriangle, 
  ShieldCheck, 
  RefreshCw, 
  Plus, 
  Barcode,
  ArrowRight,
  Pill
} from 'lucide-react';

/** Row tone: MedMatch interaction severity first, legacy allergy status as fallback. */
function medTone(res: ProductScanResult): { rowCls: string; badgeCls: string; label: string; medLine: string | null } {
  const mm = res.medMatch;
  if (!mm) {
    const legacy = res.matchAssessment.status;
    return {
      rowCls: legacy === 'safe' ? 'bg-emerald-50/50 border-emerald-200 hover:border-emerald-300'
        : legacy === 'danger' ? 'bg-rose-50/50 border-rose-200 hover:border-rose-300'
        : 'bg-amber-50/50 border-amber-200 hover:border-amber-300',
      badgeCls: legacy === 'safe' ? 'bg-emerald-600 text-white'
        : legacy === 'danger' ? 'bg-rose-600 text-white'
        : 'bg-amber-600 text-white',
      label: legacy,
      medLine: null
    };
  }
  const major = mm.interactions.filter(i => i.severity === 'major').length;
  const moderate = mm.interactions.filter(i => i.severity === 'moderate').length;
  const minor = mm.interactions.filter(i => i.severity === 'minor').length;
  const evidence = mm.interactions.filter(i => !i.severity).length;
  const tone = major > 0
    ? { rowCls: 'bg-rose-50/50 border-rose-200 hover:border-rose-300', badgeCls: 'bg-rose-600 text-white', label: 'major risk' }
    : moderate > 0
      ? { rowCls: 'bg-amber-50/50 border-amber-200 hover:border-amber-300', badgeCls: 'bg-amber-600 text-white', label: 'caution' }
      : { rowCls: 'bg-emerald-50/50 border-emerald-200 hover:border-emerald-300', badgeCls: 'bg-emerald-600 text-white', label: 'clear' };
  const bits = [
    major > 0 ? `${major} major` : '',
    moderate > 0 ? `${moderate} moderate` : '',
    minor > 0 ? `${minor} minor` : '',
    evidence > 0 ? `${evidence} evidence` : ''
  ].filter(Boolean).join(' · ');
  return { ...tone, medLine: bits || 'No interactions vs active member meds' };
}

interface BatchScanModalProps {
  isOpen: boolean;
  onClose: () => void;
  userProfile: UserProfile;
  onSelectResult: (result: ProductScanResult) => void;
}

export const BatchScanModal: React.FC<BatchScanModalProps> = ({
  isOpen,
  onClose,
  userProfile,
  onSelectResult
}) => {
  const [barcodeInput, setBarcodeInput] = useState('');
  const [barcodesList, setBarcodesList] = useState<string[]>([
    '3017620422003', // Nutella
    '0737628064502', // SunButter
    '3337875588621'  // Toleriane
  ]);
  const [results, setResults] = useState<ProductScanResult[]>([]);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleAddBarcode = () => {
    if (barcodeInput.trim() && !barcodesList.includes(barcodeInput.trim())) {
      setBarcodesList([...barcodesList, barcodeInput.trim()]);
      setBarcodeInput('');
    }
  };

  const handleRunBatchAudit = async () => {
    if (barcodesList.length === 0) return;
    setLoading(true);
    try {
      const res = await fetch('/api/batch-scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          barcodes: barcodesList,
          country: userProfile.country || 'US',
          language: userProfile.language || 'en',
          medications: userProfile.medications || []
        })
      });
      if (res.ok) {
        const data = await res.json();
        setResults(data.results || []);
      }
    } catch (e) {
      console.warn('Batch audit failed:', e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-2xl w-full max-h-[85vh] flex flex-col overflow-hidden text-slate-900 animate-in fade-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="p-6 bg-slate-900 text-white flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-blue-500/20 text-blue-300 border border-blue-400/30">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold">Batch Product Audit — Meds & Supplements</h3>
              <p className="text-xs text-slate-400">
                Paste multiple barcodes or type medication/supplement names (one per add); each item is checked against the active member's medications by the MedMatch engine.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {/* Barcode Queue Adder */}
          <div className="space-y-3">
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
              Add Barcodes to Queue ({barcodesList.length} Items):
            </label>
            <div className="flex space-x-2">
              <div className="relative flex-1">
                <Barcode className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  value={barcodeInput}
                  onChange={(e) => setBarcodeInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddBarcode()}
                  placeholder="Barcode (3017620422003) or medication/supplement name (e.g. warfarin, St John's Wort)"
                  className="w-full pl-9 pr-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono"
                />
              </div>
              <button
                onClick={handleAddBarcode}
                className="px-3 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold transition-colors border border-slate-300"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>

            {/* Chips */}
            <div className="flex flex-wrap gap-1.5">
              {barcodesList.map((code) => (
                <span
                  key={code}
                  className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-md bg-slate-100 text-slate-800 text-xs font-mono border border-slate-200"
                >
                  <span>{code}</span>
                  <button
                    onClick={() => setBarcodesList(barcodesList.filter((c) => c !== code))}
                    className="text-slate-400 hover:text-rose-600"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>

            <button
              onClick={handleRunBatchAudit}
              disabled={loading || barcodesList.length === 0}
              className="w-full py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow-sm transition-all flex items-center justify-center space-x-2"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Running MedMatch interaction checks...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Run Batch Safety Audit ({barcodesList.length} Items)</span>
                </>
              )}
            </button>
          </div>

          {/* Audit Results Table */}
          {results.length > 0 && (
            <div className="space-y-3 pt-4 border-t border-slate-200">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                Audit Summary ({results.length} Products Verified)
              </h4>

              <div className="space-y-2">
                {results.map((res, i) => (
                  <div
                    key={i}
                    onClick={() => {
                      onSelectResult(res);
                      onClose();
                    }}
                    className={`p-3.5 rounded-xl border flex items-center justify-between gap-3 cursor-pointer hover:shadow-xs transition-all ${medTone(res).rowCls}`}
                  >
                    <div className="space-y-0.5">
                      <div className="flex items-center space-x-2">
                        <span className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase ${medTone(res).badgeCls}`}>
                          {medTone(res).label}
                        </span>
                        <h5 className="font-bold text-xs text-slate-900">{res.productName}</h5>
                      </div>
                      {medTone(res).medLine ? (
                        <p className="text-[11px] text-slate-700 font-semibold flex items-center gap-1">
                          <Pill className="w-3 h-3 text-teal-600" />
                          {medTone(res).medLine}
                        </p>
                      ) : (
                        <p className="text-[11px] text-slate-600">
                          {res.matchAssessment.summary}
                        </p>
                      )}
                    </div>

                    <div className="flex items-center space-x-3 shrink-0">
                      <span className="font-bold text-sm text-slate-800">
                        {res.matchAssessment.score}/100
                      </span>
                      <ArrowRight className="w-4 h-4 text-slate-400" />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

import React, { useState, useRef, useEffect } from 'react';
import { ProductScanResult, UserProfile, MedMatchAnalysis, MedMatchSeverity } from '../types';
import { getTranslation } from '../i18n';
import { BrowserMultiFormatReader } from '@zxing/browser';
import { 
  Scan, 
  Camera, 
  Upload, 
  FileText, 
  Search, 
  Sparkles, 
  Check, 
  AlertCircle, 
  RotateCcw, 
  ArrowRight,
  Shield,
  Loader2,
  Maximize,
  X,
  Dna,
  Zap,
  Pill
} from 'lucide-react';

interface ScannerViewProps {
  onScanComplete: (result: ProductScanResult) => void;
  userProfile: UserProfile;
  demoProducts: any[];
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  onOpenReceiptAuditModal?: () => void;
  onOpenMarketCatalogModal?: () => void;
  onOpenBatchScanModal?: () => void;
  onOpenCrossReactivityModal?: () => void;
  onOpenSkincareRadarModal?: () => void;
}

export const ScannerView: React.FC<ScannerViewProps> = ({
  onScanComplete,
  userProfile,
  demoProducts,
  isLoading,
  setIsLoading,
  onOpenReceiptAuditModal,
  onOpenMarketCatalogModal,
  onOpenBatchScanModal,
  onOpenCrossReactivityModal,
  onOpenSkincareRadarModal
}) => {
  const t = (k: string) => getTranslation(userProfile.language || 'en', k);
  const [scanMode, setScanMode] = useState<'barcode' | 'camera' | 'photo' | 'text' | 'meds'>('barcode');
  const [barcodeInput, setBarcodeInput] = useState('');
  const [rawTextInput, setRawTextInput] = useState('');
  const [rawTextName, setRawTextName] = useState('');
  const [medNamesInput, setMedNamesInput] = useState(userProfile.medications?.join(', ') || '');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  
  // Camera state
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [cameraFacing, setCameraFacing] = useState<'environment' | 'user'>('environment');
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const readerRef = useRef<BrowserMultiFormatReader | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Photo upload state
  const [uploadedImage, setUploadedImage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Initialize ZXing Reader
  useEffect(() => {
    readerRef.current = new BrowserMultiFormatReader();
    return () => {
      stopCamera();
    };
  }, []);

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    setIsCameraActive(false);
  };

  const startCamera = async () => {
    setErrorMessage(null);
    setIsCameraActive(true);
    setScanMode('camera');

    try {
      if (videoRef.current && readerRef.current) {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: cameraFacing }
        });
        streamRef.current = stream;
        videoRef.current.srcObject = stream;
        await videoRef.current.play();

        // Start continuous barcode scanning
        readerRef.current.decodeFromVideoElement(
          videoRef.current,
          (result, error) => {
            if (result) {
              const text = result.getText();
              if (text && text.trim().length > 3) {
                stopCamera();
                handleBarcodeSubmit(text.trim());
              }
            }
          }
        );
      }
    } catch (err: any) {
      console.warn('Camera initialization error:', err);
      setErrorMessage('Could not open camera. Please check camera permissions or use manual barcode/photo upload.');
      setIsCameraActive(false);
    }
  };

  const handleBarcodeSubmit = async (codeToScan?: string) => {
    const code = (codeToScan || barcodeInput).trim();
    if (!code) {
      setErrorMessage('Please enter a barcode number or product name.');
      return;
    }

    setErrorMessage(null);
    setIsLoading(true);

    try {
      const res = await fetch('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          barcode: code,
          country: userProfile.country || 'US',
          language: userProfile.language || 'en',
          medications: userProfile.medications || []
        })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || `Scan failed (Status ${res.status})`);
      }

      const data: ProductScanResult = await res.json();
      onScanComplete(data);
    } catch (err: any) {
      setErrorMessage(err.message || 'Could not find product details for this barcode.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async () => {
      const base64 = reader.result as string;
      setUploadedImage(base64);
      processImageScan(base64, file.type);
    };
    reader.readAsDataURL(file);
  };

  const processImageScan = async (base64: string, mimeType: string) => {
    setErrorMessage(null);
    setIsLoading(true);

    try {
      const res = await fetch('/api/scan/image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          imageBase64: base64, 
          mimeType,
          country: userProfile.country || 'US',
          language: userProfile.language || 'en',
          medications: userProfile.medications || []
        })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || 'Failed to analyze product image');
      }

      const data: ProductScanResult = await res.json();
      onScanComplete(data);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to extract ingredients from image with AI Vision.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleTextSubmit = async () => {
    if (!rawTextInput.trim() || rawTextInput.trim().length < 5) {
      setErrorMessage('Please paste complete ingredient text.');
      return;
    }

    setErrorMessage(null);
    setIsLoading(true);

    try {
      const res = await fetch('/api/scan/text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          text: rawTextInput, 
          name: rawTextName,
          country: userProfile.country || 'US',
          language: userProfile.language || 'en',
          medications: userProfile.medications || []
        })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || 'Failed to analyze ingredient text');
      }

      const data: ProductScanResult = await res.json();
      onScanComplete(data);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to analyze ingredient list.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleMedsSubmit = async () => {
    const names = Array.from(new Set(
      medNamesInput
        .split(/[\n,]+/)
        .map(n => n.trim())
        .filter(Boolean)
    ));
    if (names.length === 0) {
      setErrorMessage('Enter at least one medication or supplement name.');
      return;
    }

    setErrorMessage(null);
    setIsLoading(true);

    try {
      const res = await fetch('/api/medmatch/check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          items: names.map(n => ({ name: n })),
          profile: {
            age: userProfile.age,
            gender: userProfile.gender,
            pregnancyStatus: userProfile.pregnancyStatus,
            kidneyFunction: userProfile.kidneyFunction,
            liverFunction: userProfile.liverFunction,
          }
        })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || 'MedMatch AI backend unreachable');
      }

      const analysis: MedMatchAnalysis = await res.json();
      const interactions = analysis.interactions || [];
      const countBy = (sev: MedMatchSeverity) => interactions.filter(i => i.severity === sev).length;
      const majorCount = countBy('major');
      const moderateCount = countBy('moderate');
      const minorCount = countBy('minor');

      onScanComplete({
        barcode: 'MED-CHECK',
        productName: 'Medication Interaction Check',
        productType: 'supplement',
        ingredientsText: names.join(', '),
        ingredientsList: names,
        allergens: [],
        labels: [],
        medMatch: analysis,
        matchAssessment: {
          status: majorCount > 0 ? 'danger' : moderateCount > 0 ? 'warning' : interactions.length > 0 ? 'caution' : 'safe',
          score: Math.max(5, 100 - majorCount * 25 - moderateCount * 10 - minorCount * 3),
          summary: `${interactions.length} interaction(s) found across ${analysis.matched.length} recognized items`,
          warnings: [],
          safeHighlights: []
        },
        source: 'cached',
        scannedAt: new Date().toISOString()
      });
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to check medication interactions.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Active Bio-Profile Bar */}
      <div className="p-3.5 bg-slate-900 text-white rounded-xl border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-xs text-white shrink-0">
            {userProfile.name?.charAt(0) || 'U'}
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-bold text-white">
                Active Member: {userProfile.name || 'Alex'}
              </span>
              <span className="px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 text-[10px] uppercase font-medium border border-slate-700">
                {userProfile.role || 'Primary'}
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Evaluating for: <span className="text-slate-200 font-medium">
                {userProfile.allergies.length > 0 ? userProfile.allergies.join(', ') : 'No allergens'}
              </span> • Diet: <span className="text-slate-200 capitalize font-medium">{userProfile.dietType}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-xs">
          <span className="text-[11px] text-slate-400 hidden md:inline">
            Each scan is cross-referenced with this bio-profile
          </span>
        </div>
      </div>

      {/* Smart Scanner Extensions (Stage 1 & Safety Intelligence Tools) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {onOpenReceiptAuditModal && (
          <button
            id="quick-receipt-audit-btn"
            onClick={onOpenReceiptAuditModal}
            className="p-3.5 rounded-xl bg-gradient-to-br from-amber-50 to-orange-50/60 hover:from-amber-100/80 hover:to-orange-100/80 border border-amber-200/80 text-left transition-all group flex items-start space-x-3 shadow-2xs cursor-pointer"
          >
            <div className="p-2.5 rounded-xl bg-amber-500 text-white shrink-0 shadow-xs group-hover:scale-105 transition-transform">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <h5 className="text-xs font-bold text-slate-900 group-hover:text-amber-700 transition-colors">
                  {t('receiptAudit')}
                </h5>
                <span className="text-[9px] px-1 py-0.2 rounded bg-amber-200 text-amber-900 font-extrabold uppercase">
                  AI Vision
                </span>
              </div>
              <p className="text-[11px] text-slate-600 mt-0.5 leading-snug">
                Scan whole receipts or cart photos to cross-audit medication interactions and allergen safety for all family members.
              </p>
            </div>
          </button>
        )}

        {onOpenCrossReactivityModal && (
          <button
            id="quick-cross-reactivity-btn"
            onClick={onOpenCrossReactivityModal}
            className="p-3.5 rounded-xl bg-gradient-to-br from-amber-50/80 to-yellow-50/80 hover:from-amber-100 hover:to-yellow-100 border border-amber-300 text-left transition-all group flex items-start space-x-3 shadow-2xs cursor-pointer"
          >
            <div className="p-2.5 rounded-xl bg-amber-600 text-white shrink-0 shadow-xs group-hover:scale-105 transition-transform">
              <Dna className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <h5 className="text-xs font-bold text-slate-900 group-hover:text-amber-800 transition-colors">
                  {t('crossReactivity')}
                </h5>
                <span className="text-[9px] px-1 py-0.2 rounded bg-amber-200 text-amber-900 font-extrabold uppercase">
                  Clinical
                </span>
              </div>
              <p className="text-[11px] text-slate-600 mt-0.5 leading-snug">
                Latex-Fruit Syndrome, Birch-Pollen (PFS/OAS), Crustacean Tropomyosin.
              </p>
            </div>
          </button>
        )}

        {onOpenSkincareRadarModal && (
          <button
            id="quick-skincare-radar-btn"
            onClick={onOpenSkincareRadarModal}
            className="p-3.5 rounded-xl bg-gradient-to-br from-teal-50 to-emerald-50/70 hover:from-teal-100/90 hover:to-emerald-100/90 border border-teal-200 text-left transition-all group flex items-start space-x-3 shadow-2xs cursor-pointer"
          >
            <div className="p-2.5 rounded-xl bg-teal-600 text-white shrink-0 shadow-xs group-hover:scale-105 transition-transform">
              <Zap className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <h5 className="text-xs font-bold text-slate-900 group-hover:text-teal-800 transition-colors">
                  {t('skincareRadar')}
                </h5>
                <span className="text-[9px] px-1 py-0.2 rounded bg-teal-200 text-teal-900 font-extrabold uppercase">
                  Skin Routine
                </span>
              </div>
              <p className="text-[11px] text-slate-600 mt-0.5 leading-snug">
                Audit conflicts between Retinol, AHA/BHA, Vitamin C, Niacinamide & Skin Cycling.
              </p>
            </div>
          </button>
        )}

        {onOpenMarketCatalogModal && (
          <button
            id="quick-market-catalog-btn"
            onClick={onOpenMarketCatalogModal}
            className="p-3.5 rounded-xl bg-gradient-to-br from-blue-50 to-indigo-50/60 hover:from-blue-100/80 hover:to-indigo-100/80 border border-blue-200/80 text-left transition-all group flex items-start space-x-3 shadow-2xs cursor-pointer"
          >
            <div className="p-2.5 rounded-xl bg-blue-600 text-white shrink-0 shadow-xs group-hover:scale-105 transition-transform">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <h5 className="text-xs font-bold text-slate-900 group-hover:text-blue-700 transition-colors">
                  {t('marketCatalog')}
                </h5>
                <span className="text-[9px] px-1 py-0.2 rounded bg-blue-200 text-blue-900 font-extrabold uppercase">
                  Global Stores
                </span>
              </div>
              <p className="text-[11px] text-slate-600 mt-0.5 leading-snug">
                Trader Joe's, Costco, Tesco, Carrefour, Edeka, Mercadona, Conad.
              </p>
            </div>
          </button>
        )}

        {onOpenBatchScanModal && (
          <button
            id="quick-pantry-audit-btn"
            onClick={onOpenBatchScanModal}
            className="p-3.5 rounded-xl bg-gradient-to-br from-slate-50 to-slate-100/80 hover:from-slate-100 hover:to-slate-200/80 border border-slate-200 text-left transition-all group flex items-start space-x-3 shadow-2xs cursor-pointer"
          >
            <div className="p-2.5 rounded-xl bg-slate-800 text-white shrink-0 shadow-xs group-hover:scale-105 transition-transform">
              <RotateCcw className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <h5 className="text-xs font-bold text-slate-900 group-hover:text-slate-700 transition-colors">
                  {t('batchScan')}
                </h5>
                <span className="text-[9px] px-1 py-0.2 rounded bg-slate-200 text-slate-800 font-extrabold uppercase">
                  Pantry Audit
                </span>
              </div>
              <p className="text-[11px] text-slate-600 mt-0.5 leading-snug">
                Rapidly scan multiple barcodes or paste pantry lists to audit your kitchen.
              </p>
            </div>
          </button>
        )}
      </div>

      {/* Main Scanner Workspace */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 sm:p-6 shadow-xs relative overflow-hidden">
        {/* Scanner Mode Toggle Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 mb-4 border-b border-slate-100 gap-2">
          <div className="grid grid-cols-2 sm:flex sm:items-center gap-1.5 sm:space-x-1 bg-slate-100 p-1 rounded-xl">
            <button
              id="mode-barcode-btn"
              onClick={() => { stopCamera(); setScanMode('barcode'); }}
              className={`flex items-center justify-center space-x-1.5 py-2 px-3 rounded-lg text-xs font-semibold transition-all ${
                scanMode === 'barcode'
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Scan className="w-3.5 h-3.5 text-blue-600" />
              <span>Barcode / Name</span>
            </button>

            <button
              id="mode-camera-btn"
              onClick={() => { setScanMode('camera'); startCamera(); }}
              className={`flex items-center justify-center space-x-1.5 py-2 px-3 rounded-lg text-xs font-semibold transition-all ${
                scanMode === 'camera'
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Camera className="w-3.5 h-3.5 text-blue-600" />
              <span>Camera HUD</span>
            </button>

            <button
              id="mode-photo-btn"
              onClick={() => { stopCamera(); setScanMode('photo'); }}
              className={`flex items-center justify-center space-x-1.5 py-2 px-3 rounded-lg text-xs font-semibold transition-all ${
                scanMode === 'photo'
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Upload className="w-3.5 h-3.5 text-blue-600" />
              <span>Photo OCR</span>
            </button>

            <button
              id="mode-text-btn"
              onClick={() => { stopCamera(); setScanMode('text'); }}
              className={`flex items-center justify-center space-x-1.5 py-2 px-3 rounded-lg text-xs font-semibold transition-all ${
                scanMode === 'text'
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <FileText className="w-3.5 h-3.5 text-blue-600" />
              <span>Raw Text</span>
            </button>

            <button
              id="mode-meds-btn"
              onClick={() => {
                stopCamera();
                setMedNamesInput(prev => prev || userProfile.medications?.join(', ') || '');
                setScanMode('meds');
              }}
              className={`flex items-center justify-center space-x-1.5 py-2 px-3 rounded-lg text-xs font-semibold transition-all ${
                scanMode === 'meds'
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Pill className="w-3.5 h-3.5 text-rose-600" />
              <span>Medication Names</span>
            </button>
          </div>

          <span className="text-[11px] text-slate-500 font-mono hidden md:inline">
            Open Food Facts • USDA • PubMed
          </span>
        </div>

        {/* TAB 1: BARCODE SEARCH */}
        {scanMode === 'barcode' && (
          <div className="space-y-4">
            <form 
              onSubmit={(e) => { e.preventDefault(); handleBarcodeSubmit(); }}
              className="flex flex-col sm:flex-row gap-2.5"
            >
              <div className="relative flex-1">
                <input
                  id="barcode-input-field"
                  type="text"
                  value={barcodeInput}
                  onChange={(e) => setBarcodeInput(e.target.value)}
                  placeholder="Enter barcode number (e.g. 3017620422003) or product name..."
                  className="w-full pl-10 pr-4 py-3 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 placeholder-slate-400 text-sm focus:outline-none focus:border-blue-600 focus:bg-white focus:ring-2 focus:ring-blue-600/10 font-mono transition-colors"
                />
                <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
              </div>

              <button
                id="submit-barcode-scan-btn"
                type="submit"
                disabled={isLoading || !barcodeInput.trim()}
                className="py-3 px-6 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold text-xs uppercase tracking-wider rounded-xl transition-colors shadow-xs flex items-center justify-center space-x-2 shrink-0"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Evaluating...</span>
                  </>
                ) : (
                  <>
                    <Scan className="w-4 h-4" />
                    <span>Scan Product</span>
                  </>
                )}
              </button>
            </form>
          </div>
        )}

        {/* TAB 2: LIVE CAMERA SCANNER */}
        {scanMode === 'camera' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                  Live Viewfinder
                </h4>
                <p className="text-[11px] text-slate-500">
                  Center the product barcode inside the blue scanner box.
                </p>
              </div>

              <button
                onClick={stopCamera}
                className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition-colors"
              >
                Close Camera
              </button>
            </div>

            <div className="relative rounded-xl overflow-hidden bg-slate-950 aspect-video max-h-[360px] border border-slate-800 flex items-center justify-center">
              <video
                ref={videoRef}
                className="w-full h-full object-cover"
                playsInline
                muted
              />

              {/* Targeting Reticle & Scanline */}
              <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
                <div className="w-64 h-36 border-2 border-blue-400 rounded-lg relative shadow-2xl">
                  <div className="absolute -top-1 -left-1 w-4 h-4 border-t-4 border-l-4 border-blue-400"></div>
                  <div className="absolute -top-1 -right-1 w-4 h-4 border-t-4 border-r-4 border-blue-400"></div>
                  <div className="absolute -bottom-1 -left-1 w-4 h-4 border-b-4 border-l-4 border-blue-400"></div>
                  <div className="absolute -bottom-1 -right-1 w-4 h-4 border-b-4 border-r-4 border-blue-400"></div>
                  <div className="w-full h-0.5 bg-blue-400 shadow-md shadow-blue-400/50 animate-pulse mt-16"></div>
                </div>
              </div>

              {!isCameraActive && (
                <div className="absolute inset-0 bg-slate-900/90 flex flex-col items-center justify-center p-4 text-center">
                  <Camera className="w-10 h-10 text-slate-400 mb-2" />
                  <p className="text-xs text-slate-300 mb-4">Camera is paused or waiting for permission</p>
                  <button
                    onClick={startCamera}
                    className="px-4 py-2 bg-blue-600 text-white font-semibold text-xs rounded-lg shadow-sm"
                  >
                    Start Camera
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 3: PHOTO OCR UPLOAD */}
        {scanMode === 'photo' && (
          <div className="space-y-4">
            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-slate-300 hover:border-blue-500 rounded-xl p-8 flex flex-col items-center justify-center text-center cursor-pointer bg-slate-50 hover:bg-blue-50/20 transition-colors"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                capture="environment"
                onChange={handleImageUpload}
                className="hidden"
              />

              {uploadedImage ? (
                <div className="space-y-3">
                  <img
                    src={uploadedImage}
                    alt="Uploaded Label"
                    className="max-h-40 rounded-lg object-contain mx-auto border border-slate-200 shadow-sm"
                  />
                  <p className="text-xs text-slate-500 font-medium">Click to upload another photo</p>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto border border-blue-100">
                    <Upload className="w-5 h-5" />
                  </div>
                  <p className="text-xs font-bold text-slate-800">
                    Upload or snap a photo of the ingredients panel
                  </p>
                  <p className="text-[11px] text-slate-500">
                    On-device OCR (Tesseract) extracts ingredients and assesses compatibility
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 4: RAW INGREDIENT TEXT PASTE */}
        {scanMode === 'text' && (
          <div className="space-y-3">
            <input
              type="text"
              value={rawTextName}
              onChange={(e) => setRawTextName(e.target.value)}
              placeholder="Product Name (optional, e.g. Protein Bar, Face Cream)..."
              className="w-full px-3.5 py-2 bg-slate-50 border border-slate-300 rounded-lg text-slate-900 placeholder-slate-400 text-xs focus:outline-none focus:border-blue-600 focus:bg-white"
            />

            <textarea
              value={rawTextInput}
              onChange={(e) => setRawTextInput(e.target.value)}
              rows={4}
              placeholder="Paste ingredient list here (e.g. Water, Skimmed Milk, Hazelnuts, Sugar, Soy Lecithin, Fragrance, Parabens)..."
              className="w-full p-3 bg-slate-50 border border-slate-300 rounded-lg text-slate-900 placeholder-slate-400 text-xs font-mono focus:outline-none focus:border-blue-600 focus:bg-white"
            />

            <button
              onClick={handleTextSubmit}
              disabled={isLoading || !rawTextInput.trim()}
              className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-bold text-xs uppercase tracking-wider rounded-lg transition-colors shadow-xs flex items-center justify-center space-x-2"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Analyzing Ingredients...</span>
                </>
              ) : (
                <>
                  <span>Analyze Ingredients</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        )}

        {/* TAB 5: MEDICATION NAMES — MedMatch AI direct check */}
        {scanMode === 'meds' && (
          <div className="space-y-3">
            <textarea
              value={medNamesInput}
              onChange={(e) => setMedNamesInput(e.target.value)}
              rows={4}
              placeholder="e.g. Warfarin, Simvastatin, St John Wort — one per line or comma-separated..."
              className="w-full p-3 bg-slate-50 border border-slate-300 rounded-lg text-slate-900 placeholder-slate-400 text-xs font-mono focus:outline-none focus:border-rose-600 focus:bg-white"
            />

            <button
              onClick={handleMedsSubmit}
              disabled={isLoading || !medNamesInput.trim()}
              className="w-full py-2.5 bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-white font-bold text-xs uppercase tracking-wider rounded-lg transition-colors shadow-xs flex items-center justify-center space-x-2"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Checking Interactions...</span>
                </>
              ) : (
                <>
                  <Pill className="w-4 h-4" />
                  <span>Check Interactions</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        )}

        {/* Error Alert Display */}
        {errorMessage && (
          <div className="mt-4 p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start space-x-2.5">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-rose-600" />
            <div>
              <p className="font-bold">Scan Notice</p>
              <p className="text-[11px] text-rose-700">{errorMessage}</p>
            </div>
          </div>
        )}
      </div>

      {/* QUICK DATABASE SAMPLES */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">
            Quick Test Items
          </h4>
          <span className="text-[11px] text-slate-400">Click any product to simulate a live barcode scan</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {demoProducts.map((p) => (
            <button
              key={p.barcode}
              onClick={() => {
                setBarcodeInput(p.barcode);
                handleBarcodeSubmit(p.barcode);
              }}
              disabled={isLoading}
              className="p-3 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 hover:border-slate-300 text-left transition-all group flex items-center space-x-3 cursor-pointer shadow-2xs"
            >
              <img
                src={p.image}
                alt={p.name}
                className="w-12 h-12 rounded-lg object-cover bg-slate-100 border border-slate-200 shrink-0"
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center space-x-1.5 mb-0.5">
                  <span className={`text-[9px] uppercase font-bold px-1.5 py-0.2 rounded ${
                    p.type === 'food' ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' : 'bg-sky-50 text-sky-800 border border-sky-200'
                  }`}>
                    {p.type}
                  </span>
                  <span className="text-[10px] text-slate-500 truncate">{p.category}</span>
                </div>
                <h5 className="text-xs font-bold text-slate-900 truncate group-hover:text-blue-600 transition-colors">
                  {p.name}
                </h5>
                <p className="text-[10px] text-slate-500 truncate">
                  {p.brand} • <span className="font-mono text-slate-400">{p.barcode}</span>
                </p>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

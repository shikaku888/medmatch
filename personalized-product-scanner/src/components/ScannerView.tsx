import React, { useState, useRef, useEffect } from 'react';
import { ProductScanResult, UserProfile, MedMatchAnalysis, MedMatchSeverity } from '../types';
import { getTranslation, localizeText } from '../i18n';
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
  recoveryMode?: 'photo' | 'text';
}

type ScanDraft = {
  draftId: string;
  status: 'waiting_confirmation';
  dataCompleteness?: 'complete' | 'partial' | 'missing';
  product: {
    productName?: string;
    brand?: string;
    productType?: ProductScanResult['productType'];
    imageUrl?: string;
    barcode?: string;
    amazonProductId?: string;
    evidenceImage?: boolean;
  };
  ingredientsList: string[];
  ingredientsText?: string;
  source: string;
  imageFingerprint?: string;
};


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
  onOpenSkincareRadarModal,
  recoveryMode
}) => {
  const t = (k: string) => getTranslation(userProfile.language || 'en', k);
  const lang = userProfile.language || 'en';
  const draftCopy = {
    confirmLabel: t('confirmProduct'),
    reviewTitle: t('reviewBeforeAnalysis'),
    unknownProduct: t('unknownProduct'),
    unknownBrand: t('unknownBrand'),
    missingIngredients: t('missingIngredients'),
    partialIngredients: t('partialIngredients'),
    productImage: t('productImage'),
    noProductImage: t('noProductImage'),
    ingredientsTitle: t('recognizedIngredients'),
    removeIngredient: t('removeIngredient'),
    addIngredient: t('addIngredient'),
    confirmAnalysis: t('confirmAnalysis'),
    wrongProduct: t('wrongProduct')
  };
  const contributionCopy = ({
    en: { title: 'Help verify this product', body: 'Share only product facts. Your image, profile, and device data are not shared.', button: 'Share product facts', sent: 'Submitted for review' },
    vi: { title: 'Giúp xác minh sản phẩm', body: 'Chỉ chia sẻ thông tin sản phẩm. Ảnh, hồ sơ và thiết bị của bạn không được chia sẻ.', button: 'Chia sẻ thông tin sản phẩm', sent: 'Đã gửi để kiểm duyệt' },
    fr: { title: 'Aidez à vérifier ce produit', body: 'Partagez uniquement les informations du produit. Vos données personnelles ne sont pas partagées.', button: 'Partager les informations', sent: 'Envoyé pour vérification' },
    de: { title: 'Produkt verifizieren helfen', body: 'Teilen Sie nur Produktdaten. Bild, Profil und Gerätedaten werden nicht geteilt.', button: 'Produktdaten teilen', sent: 'Zur Prüfung eingereicht' },
    it: { title: 'Aiuta a verificare questo prodotto', body: 'Condividi solo i dati del prodotto. Immagine, profilo e dispositivo non vengono condivisi.', button: 'Condividi dati prodotto', sent: 'Inviato per la verifica' },
    es: { title: 'Ayuda a verificar este producto', body: 'Comparte solo datos del producto. No se comparten tu imagen, perfil ni dispositivo.', button: 'Compartir datos del producto', sent: 'Enviado para revisión' },
    ja: { title: 'この製品の確認に協力', body: '製品情報のみ共有します。画像、プロフィール、端末情報は共有されません。', button: '製品情報を共有', sent: '確認のため送信済み' }
  } as const)[lang] || ({
    title: 'Help verify this product',
    body: 'Share only product facts. Your image, profile, and device data are not shared.',
    button: 'Share product facts',
    sent: 'Submitted for review'
  });
  const backLabelCopy = ({
    en: ['Need stronger identification?', 'Take a clear photo of the back label. We will merge its ingredients with this product draft.', 'Scan back label', 'Reading back label…'],
    vi: ['Cần xác minh chính xác hơn?', 'Chụp rõ mặt sau sản phẩm. Hệ thống sẽ gộp thành phần vào bản nháp này.', 'Chụp mặt sau thành phần', 'Đang đọc mặt sau…'],
    fr: ['Besoin d’une identification plus fiable ?', 'Photographiez clairement l’étiquette arrière. Ses ingrédients seront fusionnés avec ce brouillon.', 'Scanner l’étiquette arrière', 'Lecture de l’étiquette…'],
    de: ['Genauere Identifizierung nötig?', 'Fotografieren Sie das hintere Etikett. Die Zutaten werden mit diesem Entwurf zusammengeführt.', 'Rücketikett scannen', 'Etikett wird gelesen…'],
    it: ['Serve un’identificazione più precisa?', 'Fotografa chiaramente l’etichetta posteriore. Gli ingredienti saranno uniti a questa bozza.', 'Scansiona etichetta posteriore', 'Lettura etichetta…'],
    es: ['¿Necesitas una identificación más precisa?', 'Fotografía claramente la etiqueta trasera. Sus ingredientes se combinarán con este borrador.', 'Escanear etiqueta trasera', 'Leyendo etiqueta…'],
    ja: ['より正確な識別が必要ですか？', '裏面のラベルを撮影してください。成分をこの下書きに統合します。', '裏面ラベルをスキャン', 'ラベルを読み取り中…']
  } as const)[lang] || ['Need stronger identification?', 'Take a clear photo of the back label.', 'Scan back label', 'Reading back label…'];
  const modeCopy = ({
    en: { barcode: 'Search product', camera: 'Scan with camera', photo: 'Product photo', text: 'Paste ingredients', meds: 'My medicines' },
    vi: { barcode: 'Tìm sản phẩm', camera: 'Quét bằng camera', photo: 'Ảnh sản phẩm', text: 'Dán thành phần', meds: 'Thuốc đang dùng' },
    fr: { barcode: 'Rechercher un produit', camera: 'Scanner avec l’appareil photo', photo: 'Photo du produit', text: 'Coller les ingrédients', meds: 'Mes médicaments' },
    de: { barcode: 'Produkt suchen', camera: 'Mit Kamera scannen', photo: 'Produktfoto', text: 'Zutaten einfügen', meds: 'Meine Medikamente' },
    it: { barcode: 'Cerca prodotto', camera: 'Scansiona con la fotocamera', photo: 'Foto del prodotto', text: 'Incolla ingredienti', meds: 'I miei farmaci' },
    es: { barcode: 'Buscar producto', camera: 'Escanear con cámara', photo: 'Foto del producto', text: 'Pegar ingredientes', meds: 'Mis medicamentos' },
    ja: { barcode: '商品を検索', camera: 'カメラでスキャン', photo: '商品写真', text: '成分を貼り付け', meds: '服用中の薬' }
  } as const)[lang] || {
    barcode: 'Search product',
    camera: 'Scan with camera',
    photo: 'Product photo',
    text: 'Paste ingredients',
    meds: 'My medicines'
  };
  const publicSafetyCopy = ({
    en: 'A helpful screening tool, not a diagnosis. Check the package and ask a healthcare professional when unsure.',
    vi: 'Công cụ hỗ trợ sàng lọc, không thay thế chẩn đoán. Hãy kiểm tra bao bì và hỏi nhân viên y tế khi chưa chắc chắn.',
    fr: 'Un outil d’aide au repérage, pas un diagnostic. Vérifiez l’emballage et demandez conseil en cas de doute.',
    de: 'Eine Orientierungshilfe, keine Diagnose. Prüfen Sie die Verpackung und fragen Sie bei Unsicherheit medizinisches Fachpersonal.',
    it: 'Uno strumento di supporto, non una diagnosi. Controlla la confezione e chiedi a un professionista sanitario in caso di dubbio.',
    es: 'Una ayuda para orientarte, no un diagnóstico. Comprueba el envase y consulta a un profesional sanitario si tienes dudas.',
    ja: '確認を助けるためのツールであり、診断ではありません。迷ったときは容器を確認し、医療専門家に相談してください。'
  } as const)[lang] || 'A helpful screening tool, not a diagnosis. Check the package and ask a healthcare professional when unsure.';
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
  const [pendingDraft, setPendingDraft] = useState<ScanDraft | null>(null);
  const [draftIngredients, setDraftIngredients] = useState<string[]>([]);
  const [contributionStatus, setContributionStatus] = useState<'idle' | 'submitting' | 'submitted' | 'duplicate'>('idle');
  // Photo upload state
  const [uploadedImage, setUploadedImage] = useState<string | null>(null);
  const [frontImage, setFrontImage] = useState<string | null>(null);
  const [backLabelLoading, setBackLabelLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const backLabelInputRef = useRef<HTMLInputElement | null>(null);

  // Initialize ZXing Reader
  useEffect(() => {
    readerRef.current = new BrowserMultiFormatReader();
    return () => {
      stopCamera();
    };
  }, []);

  useEffect(() => {
    if (recoveryMode) setScanMode(recoveryMode);
  }, [recoveryMode]);

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
      setErrorMessage(t('cameraError'));
      setIsCameraActive(false);
    }
  };

  const handleBarcodeSubmit = async (codeToScan?: string) => {
    const code = (codeToScan || barcodeInput).trim();
    if (!code) {
      setErrorMessage(t('errorEmptyBarcode'));
      return;
    }

    setErrorMessage(null);
    setIsLoading(true);
    try {
      const res = await fetch('/api/scan/draft', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value: code })
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(localizeText(lang, errData.error || t('errorLookup')));
      }
      const draft: ScanDraft = await res.json();
      setDraftIngredients(draft.ingredientsList || []);
      setPendingDraft(draft);
    } catch (err: unknown) {
      setErrorMessage(localizeText(lang, err instanceof Error ? err.message : t('errorLookup')));
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

  const createImageFingerprint = async (base64: string): Promise<string> => {
    const image = new Image();
    image.src = base64;
    await new Promise<void>((resolve, reject) => { image.onload = () => resolve(); image.onerror = () => reject(new Error('Image could not be decoded')); });
    const canvas = document.createElement('canvas');
    canvas.width = 8; canvas.height = 8;
    const context = canvas.getContext('2d');
    if (!context) throw new Error('Image fingerprint unavailable');
    context.drawImage(image, 0, 0, 8, 8);
    const pixels = context.getImageData(0, 0, 8, 8).data;
    const values = Array.from({ length: 64 }, (_, index) => pixels[index * 4] * 0.299 + pixels[index * 4 + 1] * 0.587 + pixels[index * 4 + 2] * 0.114);
    const average = values.reduce((sum, value) => sum + value, 0) / values.length;
    const bits = values.reduce((hash, value, index) => hash + (value >= average ? (1n << BigInt(63 - index)) : 0n), 0n);
    return `ahash:${bits.toString(16).padStart(16, '0')}`;
  };

  const processImageScan = async (base64: string, mimeType: string) => {
    setErrorMessage(null);
    setIsLoading(true);
    try {
      const imageFingerprint = await createImageFingerprint(base64);
      const knownResponse = await fetch('/api/product/resolve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ imageFingerprint })
      });
      if (knownResponse.ok) {
        const known = await knownResponse.json();
        if (known.status === 'found' && known.product) {
          const analysisResponse = await fetch('/api/scan/text', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              text: known.product.ingredientsText || known.product.ingredientsList?.join(', ') || '',
              name: known.product.productName || '',
              country: userProfile.country || 'US',
              language: userProfile.language || 'en',
              medications: userProfile.medications || []
            })
          });
          if (analysisResponse.ok) {
            const reusedResult: ProductScanResult = await analysisResponse.json();
            reusedResult.source = 'community_verified';
            reusedResult.identityCode = known.product.identityCode;
            reusedResult.matchConfidence = known.product.matchConfidence;
            reusedResult.matchReasons = known.product.matchReasons;
            reusedResult.imageUrl = base64;
            onScanComplete(reusedResult);
            return;
          }
        }
      }
      const res = await fetch('/api/scan/draft/image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ imageBase64: base64, mimeType, imageFingerprint })
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(localizeText(lang, errData.error || t('errorImage')));
      }
      const draft: ScanDraft = await res.json();
      setDraftIngredients(draft.ingredientsList || []);
      setPendingDraft(draft);
    } catch (err: unknown) {
      setErrorMessage(localizeText(lang, err instanceof Error ? err.message : t('errorImage')));
    } finally {
      setIsLoading(false);
    }
  };
  const handleBackLabelUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !pendingDraft) return;
    const reader = new FileReader();
    reader.onload = async () => {
      setBackLabelLoading(true);
      try {
        const imageFingerprint = await createImageFingerprint(reader.result as string);
        const response = await fetch('/api/scan/draft/image', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ imageBase64: reader.result, mimeType: file.type, imageFingerprint })
        });
        if (!response.ok) throw new Error(t('errorImage'));
        const backDraft: ScanDraft = await response.json();
        const merged = Array.from(new Set([...draftIngredients, ...(backDraft.ingredientsList || [])])).filter(Boolean);
        setDraftIngredients(merged);
        setPendingDraft(current => current ? { ...current, imageFingerprint: current.imageFingerprint || backDraft.imageFingerprint } : current);
      } catch (err) {
        setErrorMessage(localizeText(lang, err instanceof Error ? err.message : t('errorImage')));
      } finally {
        setBackLabelLoading(false);
        event.target.value = '';
      }
    };
    reader.readAsDataURL(file);
  };


  const submitContribution = async () => {
    if (!pendingDraft || contributionStatus !== 'idle') return;
    setContributionStatus('submitting');
    try {
      const response = await fetch('/api/product/contributions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          market: userProfile.country || 'US',
          language: userProfile.language || 'en',
          barcode: pendingDraft.product.barcode,
          productName: pendingDraft.product.productName,
          brand: pendingDraft.product.brand,
          productType: pendingDraft.product.productType || 'other',
          ingredientsText: draftIngredients.join(', '),
          imageFingerprint: pendingDraft.imageFingerprint,
          shareProductFacts: true,
          consentVersion: 'product-facts-v1'
        })
      });
      if (!response.ok) throw new Error('Contribution rejected');
      const result = await response.json();
      setContributionStatus(result.status === 'duplicate_candidate' ? 'duplicate' : 'submitted');
    } catch {
      setContributionStatus('idle');
      setErrorMessage(t('errorLookup'));
    }
  };

  const confirmDraft = async () => {
    if (!pendingDraft || !draftIngredients.length) {
      setErrorMessage(t('errorConfirmIngredients'));
    }
    setErrorMessage(null);
    setIsLoading(true);
    try {
      const confirmRes = await fetch(`/api/scan/draft/${pendingDraft.draftId}/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ingredientsList: draftIngredients })
      });
      if (!confirmRes.ok) {
        const errData = await confirmRes.json().catch(() => ({}));
        throw new Error(localizeText(lang, errData.error || t('errorConfirm')));
      }
      const confirmed = await confirmRes.json();
      const isPhoto = confirmed.inputType === 'ingredient_photo';
      const analyzeRes = await fetch(isPhoto ? '/api/scan/text' : '/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(isPhoto
          ? {
              text: confirmed.ingredientsText,
              name: confirmed.product?.productName || '',
              country: userProfile.country || 'US',
              language: userProfile.language || 'en',
              medications: userProfile.medications || []
            }
          : {
              barcode: confirmed.product?.barcode || confirmed.inputValue,
              country: userProfile.country || 'US',
              language: userProfile.language || 'en',
              medications: userProfile.medications || []
            })
      });
      if (!analyzeRes.ok) {
        const errData = await analyzeRes.json().catch(() => ({}));
        throw new Error(localizeText(lang, errData.error || t('errorAnalyze')));
      }
      const analyzed: ProductScanResult = await analyzeRes.json();
      if (isPhoto && uploadedImage) analyzed.imageUrl = uploadedImage;
      onScanComplete(analyzed);
      setPendingDraft(null);
      setDraftIngredients([]);
    } catch (err: unknown) {
      setErrorMessage(localizeText(lang, err instanceof Error ? err.message : t('errorAnalyze')));
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
          medications: userProfile.medications || [],
          medicationDetails: userProfile.medicationDetails || [],
          labs: userProfile.labs || []
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
      setErrorMessage(t('errorMedicationEmpty'));
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
            pregnancyTrimester: userProfile.pregnancyTrimester,
            kidneyFunction: userProfile.kidneyFunction,
            eGFR: userProfile.eGFR,
            liverFunction: userProfile.liverFunction,
            medicationDetails: userProfile.medicationDetails || [],
            labs: userProfile.labs || []
          }
        })
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(localizeText(lang, errData.error || t('errorMedicationBackend')));
      }

      const analysis: MedMatchAnalysis = await res.json();
      const interactions = analysis.interactions || [];
      const countBy = (sev: MedMatchSeverity) => interactions.filter(i => i.severity === sev).length;
      const majorCount = countBy('major');
      const moderateCount = countBy('moderate');
      const minorCount = countBy('minor');

      onScanComplete({
        barcode: 'MED-CHECK',
        productName: t('medicationInteractionCheck'),
        productType: 'supplement',
        ingredientsText: names.join(', '),
        ingredientsList: names,
        allergens: [],
        labels: [],
        medMatch: analysis,
        matchAssessment: {
          status: majorCount > 0 ? 'danger' : moderateCount > 0 ? 'warning' : interactions.length > 0 ? 'caution' : 'safe',
          score: Math.max(5, 100 - majorCount * 25 - moderateCount * 10 - minorCount * 3),
          summary: t('interactionSummaryTemplate')
            .replace('{count}', String(interactions.length))
            .replace('{matched}', String(analysis.matched.length)),
          warnings: [],
          safeHighlights: []
        },
        source: 'cached',
        scannedAt: new Date().toISOString()
      });
    } catch (err) {
      setErrorMessage(localizeText(lang, err instanceof Error ? err.message : t('errorMedicationCheck')));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="p-3.5 bg-slate-900 text-white rounded-xl border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-xs text-white shrink-0">
            {userProfile.name?.charAt(0) || 'U'}
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-sm font-bold">{userProfile.name || t('guestUser')}</span>
              <span className="px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 text-[10px] uppercase font-medium border border-slate-700">
                {userProfile.role || t('primary')}
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              {t('allergensLabel')}: <span className="text-slate-200 font-medium">
                {userProfile.allergies.length > 0 ? userProfile.allergies.join(', ') : t('none')}
              </span> • {t('dietLabel')}: <span className="text-slate-200 capitalize font-medium">{userProfile.dietType}</span>
              {userProfile.specialConditions?.length ? (
                <> • {t('conditionsLabel')}: <span className="text-slate-200 font-medium">{userProfile.specialConditions.join(', ')}</span></>
              ) : null}
              {userProfile.medications?.length ? (
                <> • {t('medicationsLabel')}: <span className="text-slate-200 font-medium">{userProfile.medications.join(', ')}</span></>
              ) : null}
            </p>
          </div>
        </div>
        <div className="flex items-center space-x-2 text-xs">
          <span className="text-[11px] text-slate-400 hidden md:inline">{t('profileCrossReference')}</span>
        </div>
      </div>
      {pendingDraft && (
        <section className="bg-amber-50 border border-amber-200 rounded-xl p-5 space-y-4" aria-label={draftCopy.confirmLabel}>
          <div className="rounded-lg border border-slate-200 bg-white p-3">
            <p className="text-sm font-semibold text-slate-900">{backLabelCopy[0]}</p>
            <p className="mt-1 text-xs text-slate-600">{backLabelCopy[1]}</p>
            <input ref={backLabelInputRef} type="file" accept="image/*" capture="environment" onChange={handleBackLabelUpload} className="hidden" />
            <button type="button" onClick={() => backLabelInputRef.current?.click()} disabled={backLabelLoading} className="mt-2 rounded-lg border border-slate-300 px-3 py-2 text-xs font-bold text-slate-700 disabled:opacity-50">
              {backLabelLoading ? backLabelCopy[3] : backLabelCopy[2]}
            </button>
          </div>
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-amber-800">{draftCopy.reviewTitle}</p>
              <h2 className="text-lg font-bold text-slate-900 mt-1">{pendingDraft.product.productName || draftCopy.unknownProduct}</h2>
              <p className="text-xs text-slate-600">
                {pendingDraft.product.brand || draftCopy.unknownBrand} · Source: {pendingDraft.source}
              </p>
              {pendingDraft.dataCompleteness === 'missing' && (
                <p className="text-xs font-semibold text-rose-700">{draftCopy.missingIngredients}</p>
              )}
              {pendingDraft.dataCompleteness === 'partial' && (
                <p className="text-xs font-semibold text-amber-700">{draftCopy.partialIngredients}</p>
              )}
            </div>
            {pendingDraft.product.imageUrl ? (
              <img src={pendingDraft.product.imageUrl} alt={draftCopy.productImage} className="w-20 h-20 rounded-lg object-cover border border-amber-200" />
            ) : (
              <div className="w-20 h-20 rounded-lg bg-amber-100 border border-amber-200 flex items-center justify-center text-[10px] text-amber-800 text-center">
                {draftCopy.noProductImage}
              </div>
            )}
          </div>
          <div className="space-y-2">
            <p className="text-xs font-semibold text-slate-700">{draftCopy.ingredientsTitle}</p>
            {draftIngredients.map((ingredient, index) => (
              <div className="flex gap-2" key={`${index}-${ingredient}`}>
                <input
                  value={ingredient}
                  onChange={(event) => setDraftIngredients(current => current.map((value, i) => i === index ? event.target.value : value))}
                  className="flex-1 px-3 py-2 rounded-lg border border-amber-200 bg-white text-sm text-slate-900"
                />
                <button
                  type="button"
                  aria-label={draftCopy.removeIngredient}
                  onClick={() => setDraftIngredients(current => current.filter((_, i) => i !== index))}
                  className="px-3 rounded-lg border border-amber-200 bg-white text-slate-600 hover:text-rose-600"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() => setDraftIngredients(current => [...current, ''])}
              className="text-xs font-semibold text-blue-700 hover:text-blue-900"
            >
              {draftCopy.addIngredient}
            </button>
          </div>
          <div className="rounded-lg border border-blue-200 bg-blue-50 p-3">
            <p className="text-sm font-semibold text-blue-900">{contributionCopy.title}</p>
            <p className="mt-1 text-xs text-blue-800">{contributionCopy.body}</p>
            <button
              type="button"
              onClick={submitContribution}
              disabled={isLoading || contributionStatus !== 'idle' || !draftIngredients.some(value => value.trim())}
              className="mt-2 rounded-lg border border-blue-300 bg-white px-3 py-2 text-xs font-bold text-blue-800 disabled:opacity-50"
            >
              {contributionStatus === 'duplicate' ? 'Already verified' : contributionStatus === 'submitted' ? contributionCopy.sent : contributionStatus === 'submitting' ? '…' : contributionCopy.button}
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={confirmDraft}
              disabled={isLoading || !draftIngredients.some(value => value.trim())}
              className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-bold disabled:opacity-50"
            >
              {draftCopy.confirmAnalysis}
            </button>
            <button
              type="button"
              onClick={() => { setPendingDraft(null); setDraftIngredients([]); }}
              className="px-4 py-2 rounded-lg border border-slate-300 bg-white text-slate-700 text-sm font-semibold"
            >
              {draftCopy.wrongProduct}
            </button>
          </div>
        </section>
      )}

      {/* Main Scanner Workspace */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 sm:p-6 shadow-xs relative overflow-hidden">
        <p className="mb-4 rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 text-[11px] leading-relaxed text-blue-900">
          {publicSafetyCopy}
        </p>
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
              <span>{modeCopy.barcode}</span>
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
              <span>{modeCopy.camera}</span>
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
              <span>{modeCopy.photo}</span>
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
              <span>{modeCopy.text}</span>
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
              <span>{modeCopy.meds}</span>
            </button>
          </div>

          <span className="text-[11px] text-slate-500 font-mono hidden md:inline">
            {t('sourceAttribution')}
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
                  placeholder={t('barcodePlaceholder')}
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
                    <span>{t('evaluating')}</span>
                  </>
                ) : (
                  <>
                    <Scan className="w-4 h-4" />
                    <span>{t('scanProduct')}</span>
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
                  {t('liveViewfinder')}
                </h4>
                <p className="text-[11px] text-slate-500">
                  {t('centerBarcode')}
                </p>
              </div>

              <button
                onClick={stopCamera}
                className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition-colors"
              >
                {t('closeCamera')}
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
                  <p className="text-xs text-slate-300 mb-4">{t('cameraPaused')}</p>
                  <button
                    onClick={startCamera}
                    className="px-4 py-2 bg-blue-600 text-white font-semibold text-xs rounded-lg shadow-sm"
                  >
                    {t('startCamera')}
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
                    alt={t('uploadedLabel')}
                    className="max-h-40 rounded-lg object-contain mx-auto border border-slate-200 shadow-sm"
                  />
                  <p className="text-xs text-slate-500 font-medium">{t('clickUploadPhoto')}</p>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto border border-blue-100">
                    <Upload className="w-5 h-5" />
                  </div>
                  <p className="text-xs font-bold text-slate-800">
                    {t('uploadIngredientsPanel')}
                  </p>
                  <p className="text-[11px] text-slate-500">
                    {t('ocrDescription')}
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
              placeholder={t('productNameOptional')}
              className="w-full px-3.5 py-2 bg-slate-50 border border-slate-300 rounded-lg text-slate-900 placeholder-slate-400 text-xs focus:outline-none focus:border-blue-600 focus:bg-white"
            />

            <textarea
              value={rawTextInput}
              onChange={(e) => setRawTextInput(e.target.value)}
              rows={4}
              placeholder={t('ingredientsPlaceholder')}
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
                  <span>{t('analyzingIngredients')}</span>
                </>
              ) : (
                <>
                  <span>{t('analyzeIngredients')}</span>
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
              placeholder={t('medicationsPlaceholder')}
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
                  <span>{t('checkingInteractions')}</span>
                </>
              ) : (
                <>
                  <Pill className="w-4 h-4" />
                  <span>{t('checkInteractions')}</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        )}

        {/* Error Alert Display */}
        {errorMessage && (
          <div className="mt-4 min-w-0 rounded-lg border border-rose-200 bg-rose-50 p-3 text-rose-800 text-xs">
            <div className="flex items-start space-x-2.5">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-600" />
              <div className="min-w-0">
                <p className="font-bold">{t('scanNotice')}</p>
                <p className="break-words text-[11px] text-rose-700">{errorMessage}</p>
              </div>
            </div>
            <div className="mt-3 flex min-w-0 flex-wrap gap-2">
              <button type="button" onClick={() => { setErrorMessage(null); setScanMode('photo'); }} className="rounded-lg bg-rose-700 px-3 py-2 text-[11px] font-bold text-white hover:bg-rose-800">
                {t('tryOcrPhoto')}
              </button>
              <button type="button" onClick={() => { setErrorMessage(null); setScanMode('text'); }} className="rounded-lg border border-rose-300 bg-white px-3 py-2 text-[11px] font-bold text-rose-900 hover:bg-rose-100">
                {t('enterProductName')}
              </button>
              {onOpenMarketCatalogModal && (
                <button type="button" onClick={onOpenMarketCatalogModal} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-[11px] font-bold text-slate-800 hover:bg-slate-100">
                  {t('suggestProduct')}
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {import.meta.env.DEV && (
      <>
      {/* QUICK DATABASE SAMPLES */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">
            {t('quickTestItems')}
          </h4>
          <span className="text-[11px] text-slate-400">{t('simulateBarcode')}</span>
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
      </>
      )}

      {/* More tools rail */}
{/* More tools — compact rail */}
      <div className="flex gap-2.5 overflow-x-auto pb-2 scrollbar-none">
        {onOpenReceiptAuditModal && (
          <button
            id="quick-receipt-audit-btn"
            onClick={onOpenReceiptAuditModal}
            className="p-2.5 rounded-xl bg-gradient-to-br shrink-0 from-amber-50 to-orange-50/60 hover:from-amber-100/80 hover:to-orange-100/80 border border-amber-200/80 text-left transition-all group flex items-start space-x-2.5 shadow-2xs cursor-pointer w-[172px]"
          >
            <div className="p-2.5 rounded-xl bg-amber-500 text-white shrink-0 shadow-xs group-hover:scale-105 transition-transform">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <h5 className="text-[11px] font-bold text-slate-900 group-hover:text-amber-700 transition-colors">
                  {t('receiptAudit')}
                </h5>
              </div>
              
            </div>
          </button>
        )}

        {onOpenCrossReactivityModal && (
          <button
            id="quick-cross-reactivity-btn"
            onClick={onOpenCrossReactivityModal}
            className="p-2.5 rounded-xl bg-gradient-to-br shrink-0 from-amber-50/80 to-yellow-50/80 hover:from-amber-100 hover:to-yellow-100 border border-amber-300 text-left transition-all group flex items-start space-x-2.5 shadow-2xs cursor-pointer w-[172px]"
          >
            <div className="p-2.5 rounded-xl bg-amber-600 text-white shrink-0 shadow-xs group-hover:scale-105 transition-transform">
              <Dna className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <h5 className="text-[11px] font-bold text-slate-900 group-hover:text-amber-800 transition-colors">
                  {t('crossReactivity')}
                </h5>
              </div>
              
            </div>
          </button>
        )}

        {onOpenSkincareRadarModal && (
          <button
            id="quick-skincare-radar-btn"
            onClick={onOpenSkincareRadarModal}
            className="p-2.5 rounded-xl bg-gradient-to-br shrink-0 from-teal-50 to-emerald-50/70 hover:from-teal-100/90 hover:to-emerald-100/90 border border-teal-200 text-left transition-all group flex items-start space-x-2.5 shadow-2xs cursor-pointer w-[172px]"
          >
            <div className="p-2.5 rounded-xl bg-teal-600 text-white shrink-0 shadow-xs group-hover:scale-105 transition-transform">
              <Zap className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <h5 className="text-[11px] font-bold text-slate-900 group-hover:text-teal-800 transition-colors">
                  {t('skincareRadar')}
                </h5>
                <span className="text-[9px] px-1 py-0.2 rounded bg-teal-200 text-teal-900 font-extrabold uppercase">
                  Skin Routine
                </span>
              </div>
              
            </div>
          </button>
        )}

        {onOpenMarketCatalogModal && (
          <button
            id="quick-market-catalog-btn"
            onClick={onOpenMarketCatalogModal}
            className="p-2.5 rounded-xl bg-gradient-to-br shrink-0 from-blue-50 to-indigo-50/60 hover:from-blue-100/80 hover:to-indigo-100/80 border border-blue-200/80 text-left transition-all group flex items-start space-x-2.5 shadow-2xs cursor-pointer w-[172px]"
          >
            <div className="p-2.5 rounded-xl bg-blue-600 text-white shrink-0 shadow-xs group-hover:scale-105 transition-transform">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <h5 className="text-[11px] font-bold text-slate-900 group-hover:text-blue-700 transition-colors">
                  {t('marketCatalog')}
                </h5>
                <span className="text-[9px] px-1 py-0.2 rounded bg-blue-200 text-blue-900 font-extrabold uppercase">
                  Global Stores
                </span>
              </div>
              
            </div>
          </button>
        )}

        {onOpenBatchScanModal && (
          <button
            id="quick-pantry-audit-btn"
            onClick={onOpenBatchScanModal}
            className="p-2.5 rounded-xl bg-gradient-to-br shrink-0 from-slate-50 to-slate-100/80 hover:from-slate-100 hover:to-slate-200/80 border border-slate-200 text-left transition-all group flex items-start space-x-2.5 shadow-2xs cursor-pointer w-[172px]"
          >
            <div className="p-2.5 rounded-xl bg-slate-800 text-white shrink-0 shadow-xs group-hover:scale-105 transition-transform">
              <RotateCcw className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <h5 className="text-[11px] font-bold text-slate-900 group-hover:text-slate-700 transition-colors">
                  {t('batchScan')}
                </h5>
                <span className="text-[9px] px-1 py-0.2 rounded bg-slate-200 text-slate-800 font-extrabold uppercase">
                  Pantry Audit
                </span>
              </div>
              
            </div>
          </button>
        )}
      </div>
    </div>
  );
};

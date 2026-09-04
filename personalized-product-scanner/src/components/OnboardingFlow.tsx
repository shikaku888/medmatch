import React, { useEffect, useRef, useState } from 'react';
import { UserProfile } from '../types';
import { ShieldCheck, Pill, Search, X, Check, ArrowRight, ArrowLeft, Leaf, Sparkles } from 'lucide-react';

interface Props {
  initialProfile: UserProfile;
  onSave: (profile: UserProfile) => void | Promise<void>;
  onSkip: () => void;
}

const LANGS = [
  { code: 'en', label: 'English' },
  { code: 'vi', label: 'Tiếng Việt' },
  { code: 'fr', label: 'Français' },
  { code: 'de', label: 'Deutsch' },
  { code: 'it', label: 'Italiano' },
  { code: 'es', label: 'Español' },
  { code: 'ja', label: '日本語' },
] as const;

type Lang = typeof LANGS[number]['code'];

const T: Record<Lang, Record<string, string>> = {
  en: {
    wTitle: 'Every scan becomes personal',
    wSub: 'Tell us what medications you take — we check every product against them before you buy or swallow.',
    wCta: 'Add my medications',
    skip: 'Skip for now',
    mTitle: 'What medications do you take?',
    mSub: 'Search by name — prescriptions, OTC painkillers, blood pressure pills, supplements, herbs…',
    mPlaceholder: 'e.g. warfarin, metformin, ibuprofen…',
    mEmpty: 'Start typing — results appear here.',
    mChosen: 'Your list',
    mNext: 'Continue',
    aTitle: 'Any allergies or things to avoid?',
    aSub: 'Tap all that apply — we flag them on every scan.',
    aCommon: 'Common allergens',
    aFinish: 'Finish setup',
    privacy: 'No account. No email. Data stays tied to this device only.',
    example: 'The kind of warning you\'ll get — with scientific evidence attached.',
    back: 'Back',
    herb: 'Herb', drug_class: 'Drug', food: 'Food',
  },
  vi: {
    wTitle: 'Mỗi lần quét đều là riêng bạn',
    wSub: 'Cho app biết bạn đang uống thuốc gì — mọi sản phẩm sẽ được đối chiếu trước khi mua hoặc uống.',
    wCta: 'Thêm thuốc của tôi',
    skip: 'Bỏ qua lúc này',
    mTitle: 'Bạn đang uống thuốc nào?',
    mSub: 'Gõ tên — thuốc kê đơn, giảm đau, huyết áp, TPCN, thảo dược…',
    mPlaceholder: 'vd: warfarin, metformin, paracetamol…',
    mEmpty: 'Bắt đầu gõ — kết quả sẽ hiện ở đây.',
    mChosen: 'Danh sách của bạn',
    mNext: 'Tiếp tục',
    aTitle: 'Dị ứng hoặc cần tránh gì?',
    aSub: 'Chọn tất cả mục phù hợp — app sẽ cảnh báo trong mọi lần quét.',
    aCommon: 'Dị ứng phổ biến',
    aFinish: 'Hoàn tất',
    privacy: 'Không tài khoản. Không email. Dữ liệu gắn với thiết bị này.',
    example: 'Đây là kiểu cảnh báo bạn sẽ nhận — kèm bằng chứng khoa học.',
    back: 'Quay lại',
    herb: 'Thảo dược', drug_class: 'Thuốc', food: 'Thực phẩm',
  },
  fr: {
    wTitle: 'Chaque scan devient personnel',
    wSub: 'Indiquez vos médicaments — nous vérifions chaque produit avant achat ou prise.',
    wCta: 'Ajouter mes médicaments',
    skip: 'Plus tard',
    mTitle: 'Quels médicaments prenez-vous ?',
    mSub: 'Cherchez par nom — ordonnance, antalgique, tension, compléments, plantes…',
    mPlaceholder: 'ex : warfarine, metformine, paracétamol…',
    mEmpty: 'Commencez à taper — les résultats apparaissent ici.',
    mChosen: 'Votre liste',
    mNext: 'Continuer',
    aTitle: 'Des allergies ou substances à éviter ?',
    aSub: 'Touchez tout ce qui s\'applique — signalé à chaque scan.',
    aCommon: 'Allergènes courants',
    aFinish: 'Terminer',
    privacy: 'Sans compte. Sans e-mail. Données liées à cet appareil.',
    example: 'Voici le type d’alerte que vous recevrez — avec les preuves scientifiques.',
    back: 'Retour',
    herb: 'Plante', drug_class: 'Médicament', food: 'Aliment',
  },
  de: {
    wTitle: 'Jeder Scan wird persönlich',
    wSub: 'Geben Sie Ihre Medikamente an — wir prüfen jedes Produkt, bevor Sie kaufen oder einnehmen.',
    wCta: 'Meine Medikamente hinzufügen',
    skip: 'Später',
    mTitle: 'Welche Medikamente nehmen Sie?',
    mSub: 'Nach Name suchen — verschrieben, Schmerzmittel, Blutdruck, Nahrungsergänzung, Kräuter…',
    mPlaceholder: 'z.B. Warfarin, Metformin, Ibuprofen…',
    mEmpty: 'Tippen Sie los — Ergebnisse erscheinen hier.',
    mChosen: 'Ihre Liste',
    mNext: 'Weiter',
    aTitle: 'Allergien oder Zu-Meidendes?',
    aSub: 'Alles Antippen, was zutrifft — bei jedem Scan markiert.',
    aCommon: 'Häufige Allergene',
    aFinish: 'Fertig',
    privacy: 'Kein Konto. Keine E-Mail. Daten nur auf diesem Gerät.',
    example: 'So sieht eine Warnung aus — mit wissenschaftlichen Belegen.',
    back: 'Zurück',
    herb: 'Kraut', drug_class: 'Medikament', food: 'Lebensmittel',
  },
  it: {
    wTitle: 'Ogni scan diventa personale',
    wSub: 'Dicci quali medicine prendi — controlliamo ogni prodotto prima che tu lo compri o lo prenda.',
    wCta: 'Aggiungi le mie medicine',
    skip: 'Più tardi',
    mTitle: 'Quali medicine prendi?',
    mSub: 'Cerca per nome — prescription, antidolorifici, pressione, integratori, erbe…',
    mPlaceholder: 'es. warfarin, metformina, paracetamolo…',
    mEmpty: 'Inizia a digitare — i risultati appaiono qui.',
    mChosen: 'La tua lista',
    mNext: 'Continua',
    aTitle: 'Allergie o cose da evitare?',
    aSub: 'Tocca tutto ciò che riguarda te — segnalato a ogni scan.',
    aCommon: 'Allergeni comuni',
    aFinish: 'Finisci',
    privacy: 'Nessun account. Nessuna email. Dati legati a questo dispositivo.',
    example: 'Questo è il tipo di avviso che riceverai — con prove scientifiche.',
    back: 'Indietro',
    herb: 'Erba', drug_class: 'Farmaco', food: 'Alimento',
  },
  es: {
    wTitle: 'Cada escaneo se vuelve personal',
    wSub: 'Dinos qué medicamentos tomas — verificamos cada producto antes de comprarlo o tomarlo.',
    wCta: 'Añadir mis medicamentos',
    skip: 'Más tarde',
    mTitle: '¿Qué medicamentos tomas?',
    mSub: 'Busca por nombre — recetados, analgésicos, tensión, suplementos, hierbas…',
    mPlaceholder: 'ej. warfarina, metformina, ibuprofeno…',
    mEmpty: 'Empieza a escribir — los resultados aparecen aquí.',
    mChosen: 'Tu lista',
    mNext: 'Continuar',
    aTitle: '¿Alergias o cosas que evitar?',
    aSub: 'Toca todo lo que aplique — se marca en cada escaneo.',
    aCommon: 'Alérgenos comunes',
    aFinish: 'Terminar',
    privacy: 'Sin cuenta. Sin email. Datos ligados a este dispositivo.',
    example: 'Este es el tipo de alerta que recibirás — con evidencia científica.',
    back: 'Atrás',
    herb: 'Hierba', drug_class: 'Medicamento', food: 'Alimento',
  },
  ja: {
    wTitle: 'スキャンをあなた向けに',
    wSub: '服用中の薬を教えてください。購入または服用する前に、すべての製品との相互作用を確認します。',
    wCta: '服用中の薬を追加',
    skip: '今はスキップ',
    mTitle: '服用中の薬は？',
    mSub: '名前で検索 — 処方薬、市販の鎮痛薬、血圧の薬、サプリメント、ハーブ…',
    mPlaceholder: '例: ワルファリン、メトホルミン、イブプロフェン…',
    mEmpty: '入力を始めると結果が表示されます。',
    mChosen: 'あなたのリスト',
    mNext: '続ける',
    aTitle: 'アレルギーや避けたいものは？',
    aSub: '該当するものをすべて選択 — 毎回のスキャンで確認します。',
    aCommon: '主なアレルゲン',
    aFinish: '設定を完了',
    privacy: 'アカウント不要。データはこの端末にのみ紐づきます。',
    example: 'このような警告が表示されます — 科学的根拠付きです。',
    back: '戻る',
    herb: 'ハーブ', drug_class: '医薬品', food: '食品',
  },
};

const ALLERGY_CHIPS: { key: string; label: string }[] = [
  { key: 'peanut', label: '🥜 Peanuts' },
  { key: 'tree_nut', label: '🌰 Tree nuts' },
  { key: 'milk', label: '🥛 Milk / dairy' },
  { key: 'gluten', label: '🌾 Gluten / wheat' },
  { key: 'egg', label: '🥚 Eggs' },
  { key: 'soy', label: '🫘 Soy' },
  { key: 'fish', label: '🐟 Fish' },
  { key: 'shellfish', label: '🦐 Shellfish' },
  { key: 'sesame', label: '🌱 Sesame' },
  { key: 'sulfite', label: '🍷 Sulfites' },
  { key: 'fragrance', label: '🧴 Fragrance' },
  { key: 'parabens', label: '🧪 Parabens' },
];

const detectLang = (): Lang => {
  const stored = (typeof localStorage !== 'undefined' && localStorage.getItem('medmatch_lang')) as Lang | null;
  if (stored && stored in T) return stored;
  const nav = (navigator.language || 'en').slice(0, 2) as Lang;
  return nav in T ? nav : 'en';
};

interface SearchHit { kind: string; id: string; label: string; score?: number }

export const OnboardingFlow: React.FC<Props> = ({ initialProfile, onSave, onSkip }) => {
  const [lang, setLang] = useState<Lang>(detectLang());
  const [step, setStep] = useState(0);
  const [meds, setMeds] = useState<string[]>([...(initialProfile.medications || [])]);
  const [allergies, setAllergies] = useState<string[]>([...(initialProfile.allergies || [])]);
  const [q, setQ] = useState('');
  const [results, setResults] = useState<SearchHit[]>([]);
  const [searching, setSearching] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [medDetails, setMedDetails] = useState<Record<string, SearchHit>>({});
  const [saving, setSaving] = useState(false);
  const debounceRef = useRef<number | null>(null);

  const t = T[lang];

  useEffect(() => {
    if (step !== 1 || q.trim().length < 2) { setResults([]); return; }
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(async () => {
      setSearching(true);
      try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(q.trim())}&limit=8`);
        if (res.ok) {
          const data = await res.json();
          setResults((data.results || []).filter((r: SearchHit) => r.label));
        }
      } catch { /* ignore */ }
      setSearching(false);
    }, 250);
    return () => { if (debounceRef.current) window.clearTimeout(debounceRef.current); };
  }, [q, step]);

  const addMed = (hit: SearchHit) => {
    if (!hit.label) return;
    setMeds((prev) => (prev.some((m) => m.toLowerCase() === hit.label.toLowerCase()) ? prev : [...prev, hit.label]));
    setMedDetails((prev) => ({ ...prev, [hit.label]: hit }));
  };

  const toggleAllergy = (key: string) =>
    setAllergies((prev) => (prev.includes(key) ? prev.filter((a) => a !== key) : [...prev, key]));

  const finish = async () => {
    setSaveError(null);
    setSaving(true);
    const updated: UserProfile = {
      ...initialProfile,
      medications: Array.from(new Set([...(initialProfile.medications || []), ...meds])),
      allergies: Array.from(new Set([...(initialProfile.allergies || []), ...allergies])),
      language: lang as UserProfile['language'],
    };
    try {
      const res = await fetch('/api/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated),
      });
      if (!res.ok) throw new Error(`profile save failed (${res.status})`);
      const saved = await res.json();
      localStorage.setItem('mm_onboarded', '1');
      await onSave(saved);
    } catch {
      setSaveError('Could not save your profile. Check the connection and try again.');
    } finally {
      setSaving(false);
    }
  };

  const kindBadge = (kind: string) => {
    const map: Record<string, string> = {
      drug_class: 'bg-rose-500/20 text-rose-300 border-rose-500/40',
      herb: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
      food: 'bg-sky-500/20 text-sky-300 border-sky-500/40',
    };
    return map[kind] || 'bg-slate-700 text-slate-300 border-slate-600';
  };

  return (
    <div className="fixed inset-0 z-[60] bg-[#0f172a] text-white overflow-y-auto">
      <div className="max-w-md mx-auto min-h-full flex flex-col px-6 py-8">

        {/* Language row */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <span className="font-bold tracking-tight">MedMatch AI</span>
          </div>
          <select
            value={lang}
            onChange={(e) => setLang(e.target.value as Lang)}
            className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200"
            aria-label="Language"
          >
            {LANGS.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
          </select>
        </div>

        {/* Progress dots */}
        <div className="flex items-center gap-1.5 mb-6">
          {[0, 1, 2].map((i) => (
            <div key={i} className={`h-1.5 rounded-full transition-all ${i === step ? 'w-6 bg-blue-500' : i < step ? 'w-3 bg-blue-500/60' : 'w-3 bg-slate-700'}`} />
          ))}
        </div>

        {/* STEP 0 — Welcome */}
        {step === 0 && (
          <div className="flex-1 flex flex-col">
            <div className="w-16 h-16 bg-blue-600/20 border border-blue-500/40 rounded-2xl flex items-center justify-center mb-6">
              <Pill className="w-8 h-8 text-blue-400" />
            </div>
            <h1 className="text-2xl font-bold leading-snug mb-3">{t.wTitle}</h1>
            <p className="text-slate-400 leading-relaxed mb-8">{t.wSub}</p>

            <div className="bg-slate-800/50 border border-slate-700/60 rounded-xl p-4 mb-8 flex items-start gap-3">
              <Sparkles className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              <div className="text-xs text-slate-300 leading-relaxed">
                <b className="text-white">Warfarin + Turmeric · Anticoagulants + Ginkgo</b><br />
                {t.example}
              </div>
            </div>

            <div className="mt-auto space-y-2.5">
              <button
                onClick={() => setStep(1)}
                className="w-full py-3.5 rounded-xl bg-blue-600 hover:bg-blue-500 font-semibold transition-colors flex items-center justify-center gap-2"
              >
                {t.wCta} <ArrowRight className="w-4 h-4" />
              </button>
              <button
                onClick={onSkip}
                className="w-full py-2.5 text-slate-400 hover:text-slate-200 text-sm"
              >
                {t.skip}
              </button>
              <p className="text-[11px] text-slate-500 text-center pt-2">{t.privacy}</p>
            </div>
          </div>
        )}

        {/* STEP 1 — Medications type-ahead */}
        {step === 1 && (
          <div className="flex-1 flex flex-col">
            <button onClick={() => setStep(0)} className="flex items-center gap-1 text-slate-400 hover:text-white text-xs mb-4 self-start">
              <ArrowLeft className="w-3.5 h-3.5" /> {t.back}
            </button>
            <h1 className="text-xl font-bold mb-2">{t.mTitle}</h1>
            <p className="text-slate-400 text-sm mb-4">{t.mSub}</p>

            <div className="relative mb-3">
              <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                autoFocus
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder={t.mPlaceholder}
                className="w-full bg-slate-800 border border-slate-700 rounded-xl pl-9 pr-3 py-3 text-sm placeholder-slate-500 focus:outline-none focus:border-blue-500"
              />
            </div>

            {/* Search results */}
            {q.trim().length >= 2 && (
              <div className="mb-4 space-y-1.5 max-h-52 overflow-y-auto">
                {searching && <div className="text-xs text-slate-500 px-2 py-2">…</div>}
                {!searching && results.length === 0 && <div className="text-xs text-slate-500 px-2 py-2">{t.mEmpty}</div>}
                {results.map((r) => (
                  <button
                    key={`${r.kind}:${r.id}`}
                    onClick={() => addMed(r)}
                    className="w-full flex items-center justify-between bg-slate-800/60 hover:bg-slate-700/70 border border-slate-700/60 rounded-lg px-3 py-2.5 text-left transition-colors"
                  >
                    <span className="text-sm">{r.label}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border ${kindBadge(r.kind)}`}>
                      {t[(r.kind as 'herb' | 'drug_class' | 'food')] || r.kind}
                    </span>
                  </button>
                ))}
              </div>
            )}

            {/* Chosen list */}
            {meds.length > 0 && (
              <div className="mb-4">
                <div className="text-[11px] uppercase tracking-wide text-slate-500 mb-2">{t.mChosen}</div>
                <div className="flex flex-wrap gap-2">
                  {meds.map((m) => (
                    <span key={m} className="flex min-w-0 items-center gap-1 bg-blue-600/20 border border-blue-500/40 text-blue-200 rounded-full pl-3 pr-1.5 py-1 text-xs">
                      <span className="min-w-0 break-words">{m}</span>
                      {medDetails[m] && <span className="shrink-0 text-[9px] uppercase text-blue-300">confirmed</span>}
                      <button onClick={() => setMeds(meds.filter((x) => x !== m))} className="p-0.5 hover:text-white" aria-label={`remove ${m}`}>
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="mt-auto pt-4">
              <button
                onClick={() => setStep(2)}
                className="w-full py-3.5 rounded-xl bg-blue-600 hover:bg-blue-500 font-semibold transition-colors flex items-center justify-center gap-2"
              >
                {t.mNext} <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* STEP 2 — Allergies quick-pick */}
        {step === 2 && (
          <div className="flex-1 flex flex-col">
            <button onClick={() => setStep(1)} className="flex items-center gap-1 text-slate-400 hover:text-white text-xs mb-4 self-start">
              <ArrowLeft className="w-3.5 h-3.5" /> {t.back}
            </button>
            <h1 className="text-xl font-bold mb-2">{t.aTitle}</h1>
            <p className="text-slate-400 text-sm mb-5">{t.aSub}</p>

            <div className="text-[11px] uppercase tracking-wide text-slate-500 mb-2">{t.aCommon}</div>
            <div className="grid grid-cols-2 gap-2 mb-8">
              {ALLERGY_CHIPS.map((chip) => {
                const on = allergies.includes(chip.key);
                return (
                  <button
                    key={chip.key}
                    onClick={() => toggleAllergy(chip.key)}
                    className={`flex items-center gap-2 rounded-xl px-3 py-2.5 text-xs border transition-colors text-left ${
                      on ? 'bg-blue-600/25 border-blue-500/60 text-blue-100' : 'bg-slate-800/60 border-slate-700/60 text-slate-300 hover:bg-slate-700/60'
                    }`}
                  >
                    <span>{on && <Check className="w-3.5 h-3.5 inline mr-1 text-blue-400" />}{chip.label}</span>
                  </button>
                );
              })}
            </div>

            <div className="mt-auto space-y-2.5">
              {saveError && <p role="alert" className="mb-2 rounded-lg border border-rose-400/50 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">{saveError}</p>}
              <button
                onClick={finish}
                disabled={saving}
                className="w-full py-3.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 font-semibold transition-colors flex items-center justify-center gap-2"
              >
                {saving ? '…' : (<><Leaf className="w-4 h-4" /> {t.aFinish}</>)}
              </button>
              <p className="text-[11px] text-slate-500 text-center">{t.privacy}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

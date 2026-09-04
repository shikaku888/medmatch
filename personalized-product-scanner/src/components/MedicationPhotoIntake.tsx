import React, { useRef, useState } from 'react';
import { SupportedLanguage } from '../types';

type Props = { language: SupportedLanguage; onAdd: (medications: string[]) => void };

const COPY: Record<SupportedLanguage, { title: string; body: string; button: string; loading: string; add: string; empty: string; error: string }> = {
  en: { title: 'Add medicines from a photo', body: 'Photograph a prescription or medication package. Review every OCR result before saving.', button: 'Scan prescription / package', loading: 'Reading medication label…', add: 'Add selected medicines', empty: 'No medication candidates found.', error: 'Could not read this medication image.' },
  vi: { title: 'Thêm thuốc từ ảnh', body: 'Chụp đơn thuốc hoặc vỏ hộp thuốc. Hãy kiểm tra từng kết quả OCR trước khi lưu.', button: 'Chụp đơn thuốc / vỏ hộp', loading: 'Đang đọc nhãn thuốc…', add: 'Thêm thuốc đã chọn', empty: 'Không tìm thấy tên thuốc.', error: 'Không đọc được ảnh thuốc.' },
  fr: { title: 'Ajouter des médicaments par photo', body: 'Photographiez une ordonnance ou une boîte. Vérifiez chaque résultat OCR avant l’enregistrement.', button: 'Scanner ordonnance / boîte', loading: 'Lecture de l’étiquette…', add: 'Ajouter les médicaments', empty: 'Aucun médicament trouvé.', error: 'Impossible de lire cette image.' },
  de: { title: 'Medikamente per Foto hinzufügen', body: 'Fotografieren Sie ein Rezept oder eine Packung. Prüfen Sie jedes OCR-Ergebnis vor dem Speichern.', button: 'Rezept / Packung scannen', loading: 'Medikamentenetikett wird gelesen…', add: 'Ausgewählte Medikamente hinzufügen', empty: 'Keine Medikamente gefunden.', error: 'Medikamentenbild konnte nicht gelesen werden.' },
  it: { title: 'Aggiungi farmaci da una foto', body: 'Fotografa una ricetta o una confezione. Controlla ogni risultato OCR prima di salvarlo.', button: 'Scansiona ricetta / confezione', loading: 'Lettura etichetta…', add: 'Aggiungi farmaci selezionati', empty: 'Nessun farmaco trovato.', error: 'Impossibile leggere questa immagine.' },
  es: { title: 'Añadir medicamentos desde una foto', body: 'Fotografía una receta o un envase. Revisa cada resultado OCR antes de guardarlo.', button: 'Escanear receta / envase', loading: 'Leyendo etiqueta…', add: 'Añadir medicamentos seleccionados', empty: 'No se encontraron medicamentos.', error: 'No se pudo leer esta imagen.' },
  ja: { title: '写真から薬を追加', body: '処方箋または薬の箱を撮影します。保存前にOCR結果をすべて確認してください。', button: '処方箋 / パッケージをスキャン', loading: '薬のラベルを読み取り中…', add: '選択した薬を追加', empty: '薬が見つかりませんでした。', error: '薬の画像を読み取れませんでした。' }
};

export const MedicationPhotoIntake: React.FC<Props> = ({ language, onAdd }) => {
  const copy = COPY[language] || COPY.en;
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [medications, setMedications] = useState<string[]>([]);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const handleFile = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async () => {
      setLoading(true); setError('');
      try {
        const response = await fetch('/api/medications/parse-image', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ imageBase64: reader.result, mimeType: file.type }) });
        if (!response.ok) throw new Error(copy.error);
        const result = await response.json();
        const extracted = Array.isArray(result.medications)
          ? result.medications.filter((value: unknown): value is string => typeof value === 'string')
          : [];
        const unique: string[] = Array.from(new Set(extracted.map((value) => value.trim()).filter(Boolean)));
        setMedications(unique);
        setSelected(Object.fromEntries(unique.map((value) => [value, true])));
      } catch { setError(copy.error); }
      finally { setLoading(false); event.target.value = ''; }
    };
    reader.readAsDataURL(file);
  };
  return <section className="rounded-xl border border-rose-200 bg-rose-50/40 p-4 space-y-3">
    <div><h4 className="text-sm font-bold text-slate-900">{copy.title}</h4><p className="mt-1 text-xs text-slate-600">{copy.body}</p></div>
    <input ref={inputRef} type="file" accept="image/*" capture="environment" onChange={handleFile} className="hidden" />
    <button type="button" onClick={() => inputRef.current?.click()} disabled={loading} className="rounded-lg bg-rose-600 px-3 py-2 text-xs font-bold text-white disabled:opacity-50">{loading ? copy.loading : copy.button}</button>
    {error && <p role="alert" className="text-xs text-rose-700">{error}</p>}
    {medications.length > 0 ? <div className="space-y-2"><p className="text-xs font-semibold text-slate-700">{medications.length} found — review before saving</p>{medications.map((medication) => <label key={medication} className="flex items-center gap-2 text-sm text-slate-800"><input type="checkbox" checked={Boolean(selected[medication])} onChange={() => setSelected((current) => ({ ...current, [medication]: !current[medication] }))} />{medication}</label>)}<button type="button" onClick={() => onAdd(medications.filter((medication) => selected[medication]))} className="rounded-lg border border-rose-300 bg-white px-3 py-2 text-xs font-bold text-rose-800">{copy.add}</button></div> : <p className="text-xs text-slate-500">{copy.empty}</p>}
  </section>;
};

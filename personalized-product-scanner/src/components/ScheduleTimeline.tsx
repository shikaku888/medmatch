import React from 'react';
import { Clock, ArrowRight } from 'lucide-react';
import { DetectedHerbDrugAlert } from '../types';

interface SchedPair { a: string; b: string; min_hours: number; reason: string }
interface HerbAlert { herbName: string; drugOrClass: string; managementAdvice?: string; mechanism?: string; clinicalImpact?: string }

interface Props {
  schedule: SchedPair[];
  herbAlerts: HerbAlert[];
  language?: string;
  overrides?: Record<string, string>;
  onOverride?: (entity: string, time: string) => void;
}

const L10N: Record<string, { title: string; apart: string; note: string; scope: string }> = {
  en: { title: 'Suggested daily timing', apart: 'keep ≥{h}h apart', note: 'Times are a starting point — follow your prescriber.', scope: 'Only absorption/timing-fixable interactions are shown. Never change a dose yourself.' },
  vi: { title: 'Giờ uống gợi ý', apart: 'cách nhau ≥{h}h', note: 'Giờ là gợi ý khởi điểm — luôn theo hướng dẫn của bác sĩ.', scope: 'Chỉ hiển thị tương tác có thể xử lý bằng thời điểm uống. Không tự đổi liều.' },
  fr: { title: 'Horaires suggérés', apart: '≥{h}h d\'écart', note: 'Points de départ — suivez votre prescripteur.', scope: 'Seules les interactions corrigeables par le moment de prise sont affichées. Ne changez jamais la dose seul.' },
  de: { title: 'Vorgeschlagene Tageszeiten', apart: '≥{h}h Abstand', note: 'Startpunkte — folgen Sie Ihrem Arzt.', scope: 'Nur durch Einnahmezeit lösbare Interaktionen werden gezeigt. Dosis nie selbst ändern.' },
  it: { title: 'Orari suggeriti', apart: '≥{h}h di distanza', note: 'Punti di partenza — segua il medico.', scope: 'Sono mostrate solo interazioni risolvibili con il momento di assunzione. Non modificare la dose da soli.' },
  es: { title: 'Horarios sugeridos', apart: '≥{h}h de diferencia', note: 'Puntos de partida — siga a su médico.', scope: 'Solo se muestran interacciones corregibles con el horario. Nunca cambie la dosis por su cuenta.' },
  ja: { title: '推奨される服用時間', apart: '{h}時間以上あける', note: '時間は目安です。処方医の指示に従ってください。', scope: '服用時間で調整できる相互作用のみ表示しています。自己判断で用量を変更しないでください。' },
};

const parseHours = (advice: string): number | null => {
  const m = advice.match(/(\d+)\s*(?:–|-|to)?\s*(?:\d+\s*)?hours?/i)
    || advice.match(/at least (\d+)/i);
  return m ? parseInt(m[1], 10) : null;
};

const fmt = (h: number) => {
  const hh = Math.floor(h) % 24;
  const mm = Math.round((h - Math.floor(h)) * 60);
  return `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`;
};

export const ScheduleTimeline: React.FC<Props> = ({ schedule, herbAlerts, language = 'en', overrides = {}, onOverride }) => {
  const lang = L10N[language] ? language : 'en';
  const t = L10N[lang];

  // Build pair entries from both sources
  const entries: { a: string; b: string; hours: number; reason: string }[] = [];
  for (const s of schedule || []) {
    entries.push({ a: s.a, b: s.b, hours: s.min_hours || 4, reason: s.reason || '' });
  }
  for (const h of herbAlerts || []) {
    const advice = h.managementAdvice || '';
    if (!/hour|separate|apart/i.test(advice)) continue;
    const hours = parseHours(advice) || 4;
    const b = (h.drugOrClass || '').split('(')[0].trim() || h.drugOrClass;
    entries.push({ a: h.herbName, b, hours, reason: h.mechanism || h.clinicalImpact || '' });
  }
  if (entries.length === 0) return null;

  // Dedup by unordered pair
  const seenPairs = new Set<string>();
  const uniq = entries.filter((e) => {
    const k = [e.a.toLowerCase(), e.b.toLowerCase()].sort().join('|');
    if (seenPairs.has(k)) return false;
    seenPairs.add(k);
    return true;
  }).slice(0, 4);

  // Sequential placement starting 08:00; user overrides are FIXED anchors
  const toH = (hhmm: string): number | null => {
    const m = hhmm.match(/^(\d{1,2}):(\d{2})$/);
    return m ? parseInt(m[1], 10) + parseInt(m[2], 10) / 60 : null;
  };
  const ovNum: Record<string, number> = {};
  for (const [k, v] of Object.entries(overrides)) {
    const h = toH(v);
    if (h !== null) ovNum[k.toLowerCase()] = h;
  }
  const timeOf: Record<string, number> = {};
  let cursor = 8;
  for (const e of uniq) {
    const aK = e.a.toLowerCase(), bK = e.b.toLowerCase();
    const ta = ovNum[aK] ?? (timeOf[aK] ?? (ovNum[bK] !== undefined ? ovNum[bK] - e.hours : cursor));
    timeOf[aK] = ta;
    const tbNeed = ta + e.hours;
    const tb = ovNum[bK] ?? (timeOf[bK] !== undefined ? Math.max(timeOf[bK], tbNeed) : tbNeed);
    timeOf[bK] = tb;
    cursor = Math.max(cursor, tb);
  }

  const pills = Object.entries(timeOf).slice(0, 5);
  const barPct = (h: number) => `${Math.min(96, Math.max(2, (h / 24) * 100))}%`;

  return (
    <div className="mt-3 p-3.5 rounded-xl bg-slate-900/90 border border-teal-500/30">
      <div className="flex items-center gap-2 mb-3">
        <Clock className="w-4 h-4 text-teal-400" />
        <span className="text-xs font-bold text-teal-200 uppercase tracking-wide">{t.title}</span>
      </div>

      {/* 24h bar */}
      <div className="relative h-8 mb-4 mx-1">
        <div className="absolute top-1/2 left-0 right-0 h-1 -translate-y-1/2 rounded-full bg-slate-700" />
        {pills.map(([name, h], idx) => (
          <div key={name} className="absolute top-0 -translate-x-1/2" style={{ left: barPct(h) }}>
            <div className={`w-3.5 h-3.5 rounded-full border-2 ${idx % 2 === 0 ? 'bg-teal-400 border-teal-200' : 'bg-amber-400 border-amber-200'}`} />
            {onOverride ? (
              <input
                type="time"
                value={overrides[name] || fmt(h)}
                onChange={(e) => onOverride(name, e.target.value)}
                className="block mt-1 w-[74px] text-[10px] font-mono text-center bg-slate-800 border border-slate-600 rounded text-slate-200"
                aria-label={`time ${name}`}
              />
            ) : (
              <div className="text-[9px] text-slate-300 text-center mt-1 whitespace-nowrap font-mono">{fmt(h)}</div>
            )}
            <div className="text-[9px] text-slate-400 text-center whitespace-nowrap max-w-[74px] truncate">{name}</div>
          </div>
        ))}
      </div>

      {/* Pair cards */}
      <div className="space-y-2">
        {uniq.map((e, idx) => (
          <div key={idx} className="flex items-center gap-2 bg-slate-800/60 rounded-lg px-3 py-2">
            <span className="text-xs font-semibold text-white bg-slate-700 rounded-md px-2 py-1">{e.a}</span>
            <span className="flex items-center gap-1 text-[10px] text-teal-300 font-mono whitespace-nowrap">
              {fmt(timeOf[e.a.toLowerCase()] ?? 8)}
              <ArrowRight className="w-3 h-3" />
              {t.apart.replace('{h}', String(e.hours))}
              <ArrowRight className="w-3 h-3" />
              {fmt((timeOf[e.a.toLowerCase()] ?? 8) + e.hours)}
            </span>
            <span className="text-xs font-semibold text-white bg-slate-700 rounded-md px-2 py-1">{e.b}</span>
          </div>
        ))}
      </div>

      <p className="text-[10px] text-slate-500 mt-3">{t.note}</p>
      <p className="text-[10px] text-amber-300/80 mt-1">{t.scope}</p>
    </div>
  );
};

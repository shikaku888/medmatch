import React, { useEffect, useMemo, useState } from 'react';
import { Bell, BellOff, Check, Plus, Trash2 } from 'lucide-react';
import { SupportedLanguage, UserProfile } from '../types';

interface Reminder {
  id: string;
  label: string;
  medication?: string;
  time: string;
  days: number[];
  enabled: boolean;
  notes?: string;
}

interface Props {
  profile: UserProfile;
  language?: SupportedLanguage;
}

interface PeriodicSyncRegistration extends ServiceWorkerRegistration {
  periodicSync?: {
    register(tag: string, options: { minInterval: number }): Promise<void>;
  };
}

const COPY: Record<string, {
  title: string;
  subtitle: string;
  enable: string;
  enabled: string;
  unsupported: string;
  medication: string;
  label: string;
  labelPlaceholder: string;
  time: string;
  days: string;
  add: string;
  remove: string;
  noReminders: string;
  everyDay: string;
  permissionDenied: string;
}> = {
  en: {
    title: 'Medication reminders',
    subtitle: 'Get a browser notification at the times you choose. This never changes a dose.',
    enable: 'Enable notifications',
    enabled: 'Notifications enabled',
    unsupported: 'This browser does not support notifications.',
    medication: 'Medication or supplement',
    label: 'Reminder label',
    labelPlaceholder: 'e.g. Morning medication',
    time: 'Time',
    days: 'Days',
    add: 'Add reminder',
    remove: 'Remove',
    noReminders: 'No reminders yet.',
    everyDay: 'Every day',
    permissionDenied: 'Notifications are blocked. Allow them in browser settings to use reminders.',
  },
  vi: {
    title: 'Nhắc giờ uống thuốc',
    subtitle: 'Nhận thông báo vào giờ bạn chọn. Tính năng này không thay đổi liều thuốc.',
    enable: 'Bật thông báo',
    enabled: 'Đã bật thông báo',
    unsupported: 'Trình duyệt này không hỗ trợ thông báo.',
    medication: 'Thuốc hoặc thực phẩm bổ sung',
    label: 'Tên lời nhắc',
    labelPlaceholder: 'vd: Thuốc buổi sáng',
    time: 'Giờ',
    days: 'Ngày',
    add: 'Thêm lời nhắc',
    remove: 'Xóa',
    noReminders: 'Chưa có lời nhắc.',
    everyDay: 'Mỗi ngày',
    permissionDenied: 'Thông báo đang bị chặn. Hãy cho phép trong cài đặt trình duyệt.',
  },
  ja: {
    title: '服用リマインダー',
    subtitle: '指定した時間にブラウザ通知を受け取ります。用量は変更しません。',
    enable: '通知を有効にする',
    enabled: '通知は有効です',
    unsupported: 'このブラウザは通知に対応していません。',
    medication: '薬またはサプリメント',
    label: 'リマインダー名',
    labelPlaceholder: '例: 朝の薬',
    time: '時間',
    days: '曜日',
    add: 'リマインダーを追加',
    remove: '削除',
    noReminders: 'リマインダーはまだありません。',
    everyDay: '毎日',
    permissionDenied: '通知がブロックされています。ブラウザ設定で許可してください。',
  },
};

const DAY_LABELS: Record<string, string[]> = {
  en: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
  vi: ['CN', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7'],
  ja: ['日', '月', '火', '水', '木', '金', '土'],
};

const ALL_DAYS = [0, 1, 2, 3, 4, 5, 6];


async function syncServiceWorker(reminders: Reminder[]) {
  if (!('serviceWorker' in navigator)) return;
  try {
    const registration = await navigator.serviceWorker.ready as PeriodicSyncRegistration;
    registration.active?.postMessage({ type: 'MEDMATCH_REMINDERS_SYNC', reminders });
    await registration.periodicSync?.register('medmatch-reminders', { minInterval: 15 * 60 * 1000 });
  } catch {
    // Page-level checks remain available when background sync is unsupported.
  }
}

export const ReminderSettings: React.FC<Props> = ({ profile, language = 'en' }) => {
  const t = COPY[language] || COPY.en;
  const dayLabels = DAY_LABELS[language] || DAY_LABELS.en;
  const medicationOptions = useMemo(() => profile.medications || [], [profile.medications]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [permission, setPermission] = useState<NotificationPermission | 'unsupported'>(
    typeof Notification === 'undefined' ? 'unsupported' : Notification.permission,
  );
  const [label, setLabel] = useState('');
  const [medication, setMedication] = useState(medicationOptions[0] || '');
  const [time, setTime] = useState('08:00');
  const [days, setDays] = useState<number[]>(ALL_DAYS);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setMedication((current) => current || medicationOptions[0] || '');
  }, [medicationOptions]);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/reminders')
      .then((res) => (res.ok ? res.json() : []))
      .then((data: Reminder[]) => {
        if (!cancelled) setReminders(Array.isArray(data) ? data : []);
      })
      .catch(() => {
        if (!cancelled) setReminders([]);
      });
    return () => { cancelled = true; };
  }, [profile.id]);

  useEffect(() => {
    void syncServiceWorker(reminders);
  }, [reminders]);

  useEffect(() => {
    if (reminders.length === 0) return;
    const check = () => {
      if (navigator.serviceWorker?.controller) {
        navigator.serviceWorker.controller.postMessage({ type: 'MEDMATCH_REMINDERS_CHECK' });
        return;
      }
      if (permission !== 'granted' || typeof Notification === 'undefined') return;
      const now = new Date();
      const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
      const nowMinutes = now.getHours() * 60 + now.getMinutes();
      reminders.forEach((reminder) => {
        const [hour, minute] = (reminder.time || '').split(':').map(Number);
        const minutesLate = nowMinutes - (hour * 60 + minute);
        if (!reminder.enabled || !reminder.days.includes(now.getDay()) || !Number.isFinite(minutesLate) || minutesLate < 0 || minutesLate > 2) return;
        const key = `medmatch-reminder:${reminder.id}:${today}`;
        if (localStorage.getItem(key)) return;
        localStorage.setItem(key, '1');
        new Notification('MedMatch', { body: reminder.label });
      });
    };
    check();
    const timer = window.setInterval(check, 60_000);
    return () => window.clearInterval(timer);
  }, [permission, reminders]);

  const requestPermission = async () => {
    if (typeof Notification === 'undefined') {
      setPermission('unsupported');
      return;
    }
    const next = await Notification.requestPermission();
    setPermission(next);
  };

  const addReminder = async (event: React.FormEvent) => {
    event.preventDefault();
    const nextLabel = label.trim() || (medication ? `${medication} reminder` : 'Medication reminder');
    if (!days.length) return;
    setSaving(true);
    try {
      const res = await fetch('/api/reminders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          label: nextLabel,
          medication,
          time,
          days,
          enabled: true,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        }),
      });
      if (res.ok) {
        const created: Reminder = await res.json();
        setReminders((current) => [...current, created]);
        setLabel('');
      }
    } finally {
      setSaving(false);
    }
  };

  const toggleReminder = async (reminder: Reminder) => {
    const res = await fetch(`/api/reminders/${encodeURIComponent(reminder.id)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: !reminder.enabled }),
    });
    if (res.ok) {
      const updated: Reminder = await res.json();
      setReminders((current) => current.map((item) => item.id === updated.id ? updated : item));
    }
  };

  const removeReminder = async (reminder: Reminder) => {
    const res = await fetch(`/api/reminders/${encodeURIComponent(reminder.id)}`, { method: 'DELETE' });
    if (res.ok) setReminders((current) => current.filter((item) => item.id !== reminder.id));
  };

  return (
    <section className="rounded-xl border border-amber-200 bg-amber-50/50 p-6 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            {permission === 'granted' ? <Bell className="h-5 w-5 text-amber-600" /> : <BellOff className="h-5 w-5 text-amber-600" />}
            <h3 className="text-base font-bold text-slate-900">{t.title}</h3>
          </div>
          <p className="mt-1 text-xs text-slate-600">{t.subtitle}</p>
        </div>
        {permission === 'granted' ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-1 text-[10px] font-bold text-emerald-800">
            <Check className="h-3 w-3" /> {t.enabled}
          </span>
        ) : permission === 'unsupported' ? null : (
          <button type="button" onClick={requestPermission} className="rounded-lg bg-amber-600 px-3 py-2 text-xs font-bold text-white hover:bg-amber-700">
            {t.enable}
          </button>
        )}
      </div>

      {permission === 'unsupported' && <p className="text-xs text-slate-600">{t.unsupported}</p>}
      {permission === 'denied' && <p className="text-xs text-rose-700">{t.permissionDenied}</p>}

      <form onSubmit={addReminder} className="grid grid-cols-1 gap-3 rounded-lg border border-amber-200 bg-white p-3 sm:grid-cols-[1fr_1fr_auto]">
        <label className="space-y-1">
          <span className="text-[10px] font-bold uppercase tracking-wide text-slate-600">{t.medication}</span>
          <select value={medication} onChange={(event) => setMedication(event.target.value)} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs">
            <option value="">—</option>
            {medicationOptions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label className="space-y-1">
          <span className="text-[10px] font-bold uppercase tracking-wide text-slate-600">{t.label}</span>
          <input value={label} onChange={(event) => setLabel(event.target.value)} placeholder={t.labelPlaceholder} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-xs" />
        </label>
        <label className="space-y-1">
          <span className="text-[10px] font-bold uppercase tracking-wide text-slate-600">{t.time}</span>
          <input type="time" required value={time} onChange={(event) => setTime(event.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-xs" />
        </label>
        <div className="sm:col-span-3 space-y-1">
          <span className="text-[10px] font-bold uppercase tracking-wide text-slate-600">{t.days}</span>
          <div className="flex flex-wrap gap-1.5">
            {ALL_DAYS.map((day) => {
              const selected = days.includes(day);
              return (
                <button key={day} type="button" onClick={() => setDays((current) => selected ? current.filter((item) => item !== day) : [...current, day].sort())} className={`rounded-md px-2.5 py-1.5 text-[10px] font-bold ${selected ? 'bg-amber-600 text-white' : 'bg-slate-100 text-slate-500'}`}>
                  {dayLabels[day]}
                </button>
              );
            })}
            <button type="button" onClick={() => setDays(days.length === 7 ? [] : ALL_DAYS)} className="ml-1 text-[10px] font-bold text-amber-700 hover:underline">{t.everyDay}</button>
          </div>
        </div>
        <button type="submit" disabled={saving || !days.length} className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-slate-900 px-3 py-2 text-xs font-bold text-white hover:bg-slate-800 disabled:opacity-50 sm:col-span-3 sm:justify-self-start">
          <Plus className="h-3.5 w-3.5" /> {t.add}
        </button>
      </form>

      <div className="space-y-2">
        {reminders.length === 0 && <p className="text-xs text-slate-500">{t.noReminders}</p>}
        {reminders.map((reminder) => (
          <div key={reminder.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-white bg-white px-3 py-2.5">
            <div className="min-w-0">
              <p className={`text-xs font-bold ${reminder.enabled ? 'text-slate-900' : 'text-slate-400 line-through'}`}>{reminder.label}</p>
              <p className="text-[10px] text-slate-500">{reminder.medication || 'Medication'} · {reminder.time} · {reminder.days.length === 7 ? t.everyDay : reminder.days.map((day) => dayLabels[day]).join(', ')}</p>
            </div>
            <div className="flex items-center gap-1.5">
              <button type="button" onClick={() => toggleReminder(reminder)} className="rounded-md border border-slate-200 px-2 py-1 text-[10px] font-bold text-slate-600 hover:bg-slate-50">{reminder.enabled ? 'Pause' : 'Resume'}</button>
              <button type="button" onClick={() => removeReminder(reminder)} aria-label={`${t.remove} ${reminder.label}`} className="rounded-md p-1.5 text-rose-600 hover:bg-rose-50"><Trash2 className="h-3.5 w-3.5" /></button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};

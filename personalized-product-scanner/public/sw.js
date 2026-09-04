/* MedMatch Scanner service worker.
   Assets: cache-first. /api/: network-only (medical data must be fresh).
   Reminders: best-effort background notifications with a page-level fallback. */
const CACHE = 'scanner-shell-v3';
const SCOPE = new URL(self.registration.scope).pathname.replace(/\/?$/, '/');
const SHELL = [SCOPE, `${SCOPE}index.html`, `${SCOPE}manifest.webmanifest`];
const REMINDER_DB = 'medmatch-reminders-v1';
const REMINDER_STORE = 'reminders';

const openReminderDb = () => new Promise((resolve, reject) => {
  const request = indexedDB.open(REMINDER_DB, 1);
  request.onupgradeneeded = () => request.result.createObjectStore(REMINDER_STORE, {keyPath: 'id'});
  request.onsuccess = () => resolve(request.result);
  request.onerror = () => reject(request.error);
});

const replaceReminders = async (reminders) => {
  const db = await openReminderDb();
  await new Promise((resolve, reject) => {
    const tx = db.transaction(REMINDER_STORE, 'readwrite');
    const store = tx.objectStore(REMINDER_STORE);
    store.clear();
    reminders.forEach((reminder) => store.put(reminder));
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
  });
  db.close();
};

const readReminders = async () => {
  const db = await openReminderDb();
  const reminders = await new Promise((resolve, reject) => {
    const request = db.transaction(REMINDER_STORE, 'readonly').objectStore(REMINDER_STORE).getAll();
    request.onsuccess = () => resolve(request.result || []);
    request.onerror = () => reject(request.error);
  });
  db.close();
  return reminders;
};

const updateReminder = async (reminder) => {
  const db = await openReminderDb();
  await new Promise((resolve, reject) => {
    const tx = db.transaction(REMINDER_STORE, 'readwrite');
    tx.objectStore(REMINDER_STORE).put(reminder);
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
  });
  db.close();
};

const checkDueReminders = async () => {
  if (!self.registration.showNotification) return;
  const now = new Date();
  const date = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  const nowMinutes = now.getHours() * 60 + now.getMinutes();
  const reminders = await readReminders();
  for (const reminder of reminders) {
    const match = /^(\d{2}):(\d{2})$/.exec(reminder.time || '');
    if (!reminder.enabled || !Array.isArray(reminder.days) || !reminder.days.includes(now.getDay()) || !match) continue;
    const scheduledMinutes = Number(match[1]) * 60 + Number(match[2]);
    const minutesLate = nowMinutes - scheduledMinutes;
    if (minutesLate < 0 || minutesLate > 60 || reminder.lastNotifiedDate === date) continue;
    await self.registration.showNotification('MedMatch', {
      body: reminder.label || reminder.medication || 'Medication reminder',
      tag: `medmatch-reminder-${reminder.id}`,
      icon: '/static/icon.svg',
      data: {url: `${SCOPE}#/profile`},
    });
    await updateReminder({...reminder, lastNotifiedDate: date});
  }
};

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('message', (e) => {
  if (e.data?.type === 'MEDMATCH_REMINDERS_SYNC') {
    e.waitUntil(replaceReminders(Array.isArray(e.data.reminders) ? e.data.reminders : []));
  } else if (e.data?.type === 'MEDMATCH_REMINDERS_CHECK') {
    e.waitUntil(checkDueReminders());
  }
});

self.addEventListener('periodicsync', (e) => {
  if (e.tag === 'medmatch-reminders') e.waitUntil(checkDueReminders());
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  e.waitUntil(clients.matchAll({type: 'window', includeUncontrolled: true}).then((windows) => {
    const existing = windows.find((client) => 'focus' in client);
    if (existing) return existing.focus();
    return clients.openWindow(e.notification.data?.url || SCOPE);
  }));
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (url.origin !== location.origin) return;
  if (url.pathname.startsWith('/api/')) return;
  const inScope = SCOPE === '/' ? true : url.pathname.startsWith(SCOPE);
  if (!inScope) return;

  const shellIndex = `${SCOPE}index.html`;
  if (e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(shellIndex, copy));
          return res;
        })
        .catch(() => caches.match(shellIndex))
    );
    return;
  }

  e.respondWith(
    caches.match(e.request).then(
      (hit) =>
        hit ||
        fetch(e.request).then((res) => {
          const isAsset = url.pathname.startsWith(`${SCOPE}assets/`);
          const isSharedIcon = url.pathname === '/static/icon.svg' || url.pathname === '/static/favicon.svg';
          if (res.ok && (isAsset || isSharedIcon)) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(e.request, copy));
          }
          return res;
        })
    )
  );
});

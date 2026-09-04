import React, { useEffect, useState } from 'react';

type Observation = {
  observationId: string;
  market: string;
  language: string;
  barcode?: string;
  productName: string;
  brand?: string;
  productType?: string;
  ingredientsText?: string;
  status: string;
};

type Candidate = {
  linkId: string;
  leftMarket: string;
  rightMarket: string;
  confidence: number;
  relation: string;
  status: string;
  evidence?: { brand?: string; formulationFingerprint?: string };
};

export const AdminContributionView: React.FC = () => {
  const [token, setToken] = useState(() => localStorage.getItem('medmatch_admin_token') || '');
  const [observations, setObservations] = useState<Observation[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const headers = () => ({ Authorization: `Bearer ${token}` });
  const load = async () => {
    if (!token) return;
    setLoading(true); setError('');
    try {
      const [obsRes, candidateRes] = await Promise.all([
        fetch('/api/product/contributions?status=pending', { headers: headers() }),
        fetch('/api/product/cross-market/candidates', { headers: headers() })
      ]);
      if (!obsRes.ok || !candidateRes.ok) throw new Error('Admin authentication or API request failed');
      setObservations(await obsRes.json());
      setCandidates(await candidateRes.json());
      localStorage.setItem('medmatch_admin_token', token);
    } catch (err) { setError(err instanceof Error ? err.message : 'Request failed'); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const review = async (path: string, body: object) => {
    setError('');
    const response = await fetch(path, { method: 'POST', headers: { ...headers(), 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (!response.ok) { setError('Review action failed'); return; }
    await load();
  };

  return <main className="min-h-screen bg-slate-50 p-6 text-slate-900">
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div><p className="text-xs font-bold uppercase tracking-widest text-blue-700">MedMatch Admin</p><h1 className="text-2xl font-bold">Product contribution review</h1><p className="text-sm text-slate-600">Approve facts before they become reusable community data.</p></div>
        <form className="flex gap-2" onSubmit={(event) => { event.preventDefault(); load(); }}><input aria-label="Admin token" type="password" value={token} onChange={(event) => setToken(event.target.value)} placeholder="Admin token" className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm" /><button className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-bold text-white">{loading ? 'Loading…' : 'Load queue'}</button></form>
      </header>
      {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
      <section className="space-y-3"><h2 className="text-lg font-bold">Pending observations ({observations.length})</h2>{observations.map((item) => <article key={item.observationId} className="rounded-xl border border-amber-200 bg-white p-4 shadow-sm"><div className="flex flex-wrap justify-between gap-3"><div><h3 className="font-bold">{item.productName}</h3><p className="text-xs text-slate-600">{item.brand || 'Unknown brand'} · {item.market} · {item.language} · {item.barcode || 'No barcode'}</p></div><div className="flex gap-2"><button onClick={() => review(`/api/product/contributions/${item.observationId}/approve`, {})} className="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-bold text-white">Approve</button><button onClick={() => review(`/api/product/contributions/${item.observationId}/reject`, {})} className="rounded-lg border border-rose-300 px-3 py-2 text-xs font-bold text-rose-700">Reject</button></div></div><p className="mt-3 text-sm text-slate-700">{item.ingredientsText || 'No ingredients submitted'}</p></article>)}</section>
      <section className="space-y-3"><h2 className="text-lg font-bold">Cross-market candidates ({candidates.length})</h2>{candidates.map((item) => <article key={item.linkId} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-blue-200 bg-white p-4 shadow-sm"><div><p className="font-bold">{item.leftMarket} ↔ {item.rightMarket}</p><p className="text-xs text-slate-600">{item.relation} · confidence {Math.round(item.confidence * 100)}%</p></div><div className="flex gap-2"><button onClick={() => review(`/api/product/cross-market/${item.linkId}/review`, { decision: 'confirmed' })} className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-bold text-white">Confirm link</button><button onClick={() => review(`/api/product/cross-market/${item.linkId}/review`, { decision: 'rejected' })} className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-bold text-slate-700">Reject</button></div></article>)}</section>
    </div>
  </main>;
};

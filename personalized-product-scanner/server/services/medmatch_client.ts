/**
 * MedMatch AI client — calls the FastAPI medical backend (7-layer logic).
 * The Express BFF never contains medical data itself: every warning the UI
 * shows comes from this client, so the medical core stays independent.
 *
 * Backend base URL: MEDMATCH_URL env or http://127.0.0.1:8765
 */
import { MedMatchAnalysis, MedMatchSearchHit } from '../../src/types';

const MEDMATCH_URL = process.env.MEDMATCH_URL || 'http://127.0.0.1:8765';

export async function medMatchFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${MEDMATCH_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`MedMatch ${res.status} ${path}: ${body.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

/** Lớp 1 — Input Normalizer: map a raw ingredient string to a standard entity. */
export async function normalizeIngredient(raw: string): Promise<MedMatchSearchHit | null> {
  if (!raw || raw.trim().length < 2) return null;
  const { results } = await medMatchFetch<{ results: MedMatchSearchHit[] }>(
    `/api/search?q=${encodeURIComponent(raw.trim())}&limit=3`
  );
  if (!results?.length) return null;
  // prefer herb/drug_class/food hits with high confidence
  const hit = results.find((r) => (r.kind === 'herb' || r.kind === 'drug_class' || r.kind === 'food') && r.score >= 0.85)
    || results[0];
  return hit.score >= 0.7 ? hit : null;
}

/** Lớp 2-7 — full interaction analysis for a list of normalized items + user medications. */
export async function analyzeMedications(
  items: { name: string; kind?: string; matched?: { kind: string; id: string }; time?: string | null }[],
  profile?: {
    age?: number;
    gender?: string;
    pregnancyStatus?: string;
    kidneyFunction?: string;
    liverFunction?: string;
  } | null
): Promise<MedMatchAnalysis> {
  return medMatchFetch<MedMatchAnalysis>('/api/analyze', {
    method: 'POST',
    body: JSON.stringify({ items, profile: profile ?? null }),
  });
}

export async function lookupBarcode(barcode: string) {
  return medMatchFetch<any>(`/api/lookup/${encodeURIComponent(barcode)}`);
}

export async function medMatchStats() {
  return medMatchFetch<Record<string, number>>('/api/stats');
}

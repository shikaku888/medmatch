/**
 * MedMatch AI client — calls the FastAPI medical backend (7-layer logic).
 * The Express BFF never contains medical data itself: every warning the UI
 * shows comes from this client, so the medical core stays independent.
 *
 * Backend base URL: MEDMATCH_URL env or http://127.0.0.1:8765
 *
 * GET lookups go through the SQLite FTS5 lookup cache: repeat scans skip the
 * HTTP round-trip, and a stale entry answers when the backend is unreachable.
 */
import { cacheGet, cacheGetStale, cacheSet } from './lookup_cache';
import type { MedMatchAnalysis, MedMatchSearchHit } from '../../src/types';

const MEDMATCH_URL = process.env.MEDMATCH_URL || 'http://127.0.0.1:8765';

/** TTLs per GET prefix — product/barcode data is stable, search drifts daily. */
const GET_TTL_MS: Array<[string, number]> = [
  ['/api/lookup', 7 * 24 * 3600_000],
  ['/api/products', 24 * 3600_000],
  ['/api/search', 24 * 3600_000],
];

function ttlFor(path: string): number | undefined {
  return GET_TTL_MS.find(([prefix]) => path.startsWith(prefix))?.[1];
}

function stringAt(v: unknown, field: string): string | undefined {
  if (typeof v !== 'object' || v === null || !(field in v)) return undefined;
  const value = v[field];
  return typeof value === 'string' && value.length > 0 ? value : undefined;
}

function arrayAt(v: unknown, field: string): unknown[] {
  if (typeof v !== 'object' || v === null || !(field in v)) return [];
  const value = v[field];
  return Array.isArray(value) ? value : [];
}

/** Raw query term from the path (e.g. /api/search?q=ketoconazole) — indexed so
 * offline name search matches what the user actually typed. */
function queryTermOf(path: string): string | undefined {
  const m = /[?&]q=([^&]+)/.exec(path);
  try {
    return m ? decodeURIComponent(m[1]) : undefined;
  } catch {
    return undefined;
  }
}

/** Human-readable names from a response, for the FTS5 offline index. */
function namesFrom(path: string, data: unknown): string[] {
  if (path.startsWith('/api/lookup')) {
    const name = stringAt(data, 'name');
    return name ? [name] : [];
  }
  const results = arrayAt(data, 'results');
  const nameField = path.startsWith('/api/search') ? 'label' : 'name';
  return results
    .map((r) => stringAt(r, nameField))
    .filter((s): s is string => Boolean(s))
    .slice(0, 8);
}

export async function medMatchFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const isGet = !init?.method || init.method === 'GET';
  const ttl = isGet ? ttlFor(path) : undefined;
  if (isGet && ttl != null) {
    const cached = cacheGet<T>('medmatch', path, ttl);
    if (cached !== null) return cached;
  }
  try {
    const res = await fetch(`${MEDMATCH_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    });
    if (!res.ok) {
      const body = await res.text().catch(() => '');
      throw new Error(`MedMatch ${res.status} ${path}: ${body.slice(0, 200)}`);
    }
    const data = (await res.json()) as T;
    if (isGet && ttl != null) {
      cacheSet('medmatch', path, data, [queryTermOf(path), ...namesFrom(path, data)].filter((s): s is string => Boolean(s)), ttl);
    }
    return data;
  } catch (err) {
    if (isGet) {
      // Backend unreachable — a previously seen response is better than nothing.
      const stale = cacheGetStale<T>(path);
      if (stale !== null) return stale;
    }
    throw err;
  }
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

export async function lookupBarcode(barcode: string): Promise<unknown> {
  return medMatchFetch<unknown>(`/api/lookup/${encodeURIComponent(barcode)}`);
}

export async function medMatchStats() {
  return medMatchFetch<Record<string, number>>('/api/stats');
}

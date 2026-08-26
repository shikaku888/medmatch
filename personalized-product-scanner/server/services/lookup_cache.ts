/**
 * SQLite lookup cache (node:sqlite, zero-dep) with FTS5 name index.
 * Caches MedMatch GET lookups (search / barcode / product catalog) so repeat
 * scans skip the HTTP round-trip, and stale entries still answer when the
 * backend is unreachable (offline fallback). Product names land in an FTS5
 * index for offline name search over everything ever seen.
 */
import { DatabaseSync } from 'node:sqlite';
import path from 'path';

const DB_PATH = path.join(process.cwd(), 'lookup_cache.db');

let db: DatabaseSync | null = null;

function getDb(): DatabaseSync {
  if (!db) {
    db = new DatabaseSync(DB_PATH);
    db.exec('PRAGMA journal_mode = WAL;');
    db.exec(`
      CREATE TABLE IF NOT EXISTS lookup_cache (
        cache_key TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        expires_at INTEGER,
        hits INTEGER NOT NULL DEFAULT 0
      );
      CREATE INDEX IF NOT EXISTS idx_cache_kind ON lookup_cache(kind);
      CREATE VIRTUAL TABLE IF NOT EXISTS cache_fts USING fts5(name, kind, cache_key UNINDEXED);
    `);
  }
  return db;
}

export function cacheGet<T = unknown>(kind: string, key: string, ttlMs?: number): T | null {
  const row = getDb().prepare('SELECT payload, created_at, expires_at FROM lookup_cache WHERE cache_key = ?').get(key) as
    | { payload: string; created_at: number; expires_at: number | null }
    | undefined;
  if (!row) return null;
  const expires = ttlMs != null ? row.created_at + ttlMs : row.expires_at;
  if (expires != null && expires < Date.now()) return null;
  getDb().prepare('UPDATE lookup_cache SET hits = hits + 1 WHERE cache_key = ?').run(key);
  return JSON.parse(row.payload) as T;
}

/** Stale read — ignores expiry, used as offline fallback when the network fails. */
export function cacheGetStale<T = unknown>(key: string): T | null {
  const row = getDb().prepare('SELECT payload FROM lookup_cache WHERE cache_key = ?').get(key) as
    | { payload: string }
    | undefined;
  return row ? (JSON.parse(row.payload) as T) : null;
}

export function cacheSet(
  kind: string,
  key: string,
  payload: unknown,
  names: string[] = [],
  ttlMs?: number
): void {
  const now = Date.now();
  const con = getDb();
  con.prepare('DELETE FROM lookup_cache WHERE cache_key = ?').run(key);
  con.prepare('DELETE FROM cache_fts WHERE cache_key = ?').run(key);
  con.prepare(
    'INSERT INTO lookup_cache (cache_key, kind, payload, created_at, expires_at, hits) VALUES (?, ?, ?, ?, ?, 0)'
  ).run(key, kind, JSON.stringify(payload), now, ttlMs != null ? now + ttlMs : null);
  const insertFts = con.prepare('INSERT INTO cache_fts (name, kind, cache_key) VALUES (?, ?, ?)');
  for (const name of [...new Set(names)].filter(Boolean).slice(0, 8)) {
    insertFts.run(name, kind, key);
  }
}

/** Offline name search over every cached entity (FTS5 prefix-aware). */
export function cacheSearch<T = unknown>(query: string, limit = 10): T[] {
  const q = query.trim();
  if (!q) return [];
  const match = q.replace(/"/g, '""').split(/\s+/).filter(Boolean).map((w) => `${w.replace(/\*/g, '')}*`).join(' ');
  const rows = getDb().prepare(
    `SELECT lc.payload FROM cache_fts f
     JOIN lookup_cache lc ON lc.cache_key = f.cache_key
     WHERE cache_fts MATCH ?
     ORDER BY rank LIMIT ?`
  ).all(match, limit) as Array<{ payload: string }>;
  return rows.map((r) => JSON.parse(r.payload) as T);
}

export function cacheStats(): Record<string, number | Record<string, number>> {
  const con = getDb();
  const total = (con.prepare('SELECT COUNT(*) n, COALESCE(SUM(hits),0) h FROM lookup_cache').get() as { n: number; h: number });
  const byKind: Record<string, number> = {};
  for (const r of con.prepare('SELECT kind, COUNT(*) n FROM lookup_cache GROUP BY kind').all() as Array<{ kind: string; n: number }>) {
    byKind[r.kind] = r.n;
  }
  const fts = (con.prepare('SELECT COUNT(*) n FROM cache_fts').get() as { n: number });
  return { entries: total.n, hits: total.h, fts_names: fts.n, by_kind: byKind };
}

export function cacheClear(): number {
  const con = getDb();
  const n = (con.prepare('SELECT COUNT(*) n FROM lookup_cache').get() as { n: number }).n;
  con.exec('DELETE FROM lookup_cache; DELETE FROM cache_fts;');
  return n;
}

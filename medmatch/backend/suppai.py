"""SUPP.AI importer: evidence-backed supplement-drug interactions (free API, no key).

Two modes:
- targeted crawl (run): resolve each of our 250 herbs to a SUPP.AI agent and
  fetch all interaction pages.
- full crawl (crawl_supplements): enumerate ALL supplement agents (letter
  queries) and fetch interactions for every one; herb_id = "suppai:{cui}".
  Use together with data/suppai_herbs.json (merged into herbs by db.py).

Each interaction's drug is mapped to one of our drug_classes by normalized
name matching. Rows land in `suppai_interactions` with paper evidence
(DOI/PMID/year/sentences). trust=0.9 (plan3 tier: SUPP.AI).

Idempotent via UNIQUE(pair_key); resume via herb_id presence.

Usage:
    python -m backend.suppai [--limit N] [--delay 0.6]
    python -m backend.suppai --enumerate            # save suppai_agents.json
    python -m backend.suppai --crawl-all            # fetch all supplements
    python -m backend.suppai --remap                # RxNorm name lookup remap
    python -m backend.suppai --remap-local          # offline re-match vs classes
"""
import argparse
import json
import sqlite3
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .engine import normalize

BASE = "https://supp.ai/api"
RXNORM_BASE = "https://rxnav.nlm.nih.gov/REST"
DATA_DIR = Path(__file__).parent / "data"
AGENTS_PATH = DATA_DIR / "suppai_agents.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS suppai_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    herb_id TEXT NOT NULL,
    class_id TEXT,
    supp_cui TEXT NOT NULL,
    drug_cui TEXT NOT NULL,
    drug_name TEXT NOT NULL,
    evidence TEXT,
    doi TEXT,
    pair_key TEXT NOT NULL,
    trust REAL NOT NULL DEFAULT 0.9,
    added_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_suppai_pair ON suppai_interactions(pair_key);
"""


def _get(path: str, params: dict | None = None) -> dict:
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.load(r)


def _rx_get(path: str, params: dict | None = None) -> dict:
    url = RXNORM_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.load(r)


def _load_herbs() -> list[dict]:
    return json.loads((DATA_DIR / "herbs.json").read_text(encoding="utf-8"))


def _load_class_index() -> dict[str, str]:
    """normalized drug name/alias -> our drug_class id."""
    classes = json.loads((DATA_DIR / "drug_classes.json").read_text(encoding="utf-8"))
    drug_names = json.loads((DATA_DIR / "drug_names_en.json").read_text(encoding="utf-8"))
    idx: dict[str, str] = {}
    for c in classes:
        names = [drug_names.get(d.lower(), d) for d in c["drugs"]]
        names += c.get("aliases") or []
        for n in names:
            idx.setdefault(normalize(n), c["id"])
    return idx


def find_supplement_agent(name_en: str, scientific: str | None) -> dict | None:
    """Top supplement hit for an herb name, or None."""
    for q in dict.fromkeys([name_en, scientific]):
        if not q:
            continue
        d = _get("/agent/search", {"q": q})
        for r in d.get("results", []):
            if r.get("ent_type") == "supplement":
                return r
    return None


def map_drug_to_class(agent: dict, cls_index: dict[str, str]) -> str | None:
    names = [agent.get("preferred_name", "")]
    names += agent.get("synonyms") or []
    names += agent.get("tradenames") or []
    for n in names:
        if n and normalize(n) in cls_index:
            return cls_index[normalize(n)]
    return None


def fetch_interactions(cui: str, delay: float) -> list[dict]:
    """All interaction pages for an agent. Pagination param is `p` (1-based);
    the `page` param is ignored by the API."""
    rows: list[dict] = []
    page = 1
    while True:
        d = _get(f"/agent/{cui}/interactions", {"p": page})
        rows.extend(d.get("interactions", []))
        per_page = d.get("interactions_per_page", 50)
        if page * per_page >= d.get("total", 0):
            break
        page += 1
        time.sleep(delay)
    return rows


def _evidence_json(interaction: dict) -> tuple[str, str | None]:
    papers = []
    doi = None
    for ev in interaction.get("evidence", []):
        paper = ev.get("paper", {})
        if doi is None and paper.get("doi"):
            doi = paper["doi"]
        papers.append({
            "doi": paper.get("doi"),
            "pmid": paper.get("pmid"),
            "year": paper.get("year"),
            "title": paper.get("title"),
            "human_study": paper.get("human_study"),
            "sentences": (ev.get("sentences") or [])[:2],
        })
    return json.dumps(papers), doi


def run(conn: sqlite3.Connection, limit: int | None, delay: float) -> dict:
    """Targeted crawl: our 250 herbs only."""
    conn.executescript(SCHEMA)
    herbs = _load_herbs()
    cls_index = _load_class_index()
    done = {r[0] for r in conn.execute("SELECT DISTINCT supp_cui FROM suppai_interactions")}

    stats = {"herbs": 0, "matched_agents": 0, "interactions": 0, "mapped": 0, "errors": 0}
    for h in herbs:
        if h["id"] in done:
            continue
        if limit is not None and stats["herbs"] >= limit:
            break
        stats["herbs"] += 1
        try:
            agent = find_supplement_agent(h["name"], h.get("scientific"))
            if not agent:
                continue
            stats["matched_agents"] += 1
            for inter in fetch_interactions(agent["cui"], delay):
                drug = inter.get("agent", {})
                evidence, doi = _evidence_json(inter)
                class_id = map_drug_to_class(drug, cls_index)
                stats["interactions"] += 1
                if class_id:
                    stats["mapped"] += 1
                conn.execute(
                    "INSERT OR IGNORE INTO suppai_interactions"
                    " (herb_id, class_id, supp_cui, drug_cui, drug_name, evidence, doi, pair_key, trust)"
                    " VALUES (?,?,?,?,?,?,?,?,0.9)",
                    (h["id"], class_id, agent["cui"], drug.get("cui"),
                     drug.get("preferred_name"), evidence, doi,
                     f"suppai:{h['id']}|{drug.get('cui')}"),
                )
        except Exception as e:
            stats["errors"] += 1
            print(f"ERR {h['id']}: {e}")
        time.sleep(delay)
        if stats["herbs"] % 25 == 0:
            print(f"herbs={stats['herbs']} agents={stats['matched_agents']}"
                  f" rows={stats['interactions']} mapped={stats['mapped']}")
    conn.commit()
    return stats


def enumerate_supplements(delay: float = 0.4) -> dict[str, dict]:
    """Enumerate ALL supplement agents via letter queries (a-z, 0).

    The search endpoint caps at 100 pages of 10 per query, so we paginate
    per letter. Saves {cui: {name, synonyms, count}} to suppai_agents.json.
    """
    found: dict[str, dict] = {}
    for letter in list("abcdefghijklmnopqrstuvwxyz") + ["0"]:
        page = 0
        while True:
            d = _get("/agent/search", {"q": letter, "p": page})
            results = d.get("results", [])
            for r in results:
                if r.get("ent_type") == "supplement":
                    found[r["cui"]] = {
                        "name": r.get("preferred_name"),
                        "synonyms": r.get("synonyms") or [],
                        "count": r.get("interacts_with_count", 0),
                    }
            if len(results) < 10 or page + 1 >= d.get("total_pages", 0):
                break
            page += 1
            time.sleep(delay)
        time.sleep(delay)
    AGENTS_PATH.write_text(json.dumps(found, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Enumerated {len(found)} supplements -> {AGENTS_PATH}")
    return found


def crawl_supplements(conn: sqlite3.Connection, agents: dict[str, dict], delay: float = 0.4,
                      mod: int | None = None, idx: int | None = None) -> dict:
    """Fetch interactions for every supplement agent; herb_id = suppai:{cui}."""
    conn.executescript(SCHEMA)
    cls_index = _load_class_index()
    done = {r[0] for r in conn.execute("SELECT DISTINCT supp_cui FROM suppai_interactions")}
    stats = {"agents": 0, "interactions": 0, "mapped": 0, "errors": 0}
    for cui in agents:
        if mod and int(cui[1:], 16) % mod != idx:
            continue
        if cui in done:
            continue
        stats["agents"] += 1
        hid = f"suppai:{cui}"
        try:
            for inter in fetch_interactions(cui, delay):
                drug = inter.get("agent", {})
                evidence, doi = _evidence_json(inter)
                class_id = map_drug_to_class(drug, cls_index)
                stats["interactions"] += 1
                if class_id:
                    stats["mapped"] += 1
                conn.execute(
                    "INSERT OR IGNORE INTO suppai_interactions"
                    " (herb_id, class_id, supp_cui, drug_cui, drug_name, evidence, doi, pair_key, trust)"
                    " VALUES (?,?,?,?,?,?,?,?,0.9)",
                    (hid, class_id, cui, drug.get("cui"),
                     drug.get("preferred_name"), evidence, doi,
                     f"suppai:{hid}|{drug.get('cui')}"),
                )
        except Exception as e:
            stats["errors"] += 1
            print(f"ERR {cui}: {e}")
        time.sleep(delay)
        if stats["agents"] % 100 == 0:
            print(f"agents={stats['agents']} rows={stats['interactions']}"
                  f" mapped={stats['mapped']} errors={stats['errors']}")
    conn.commit()
    return stats



def remap_herb_herb(conn: sqlite3.Connection) -> int:
    """Convert SUPP.AI rows whose 'drug' is actually another supplement
    into herb_herb_evidence (supplement x supplement interactions)."""
    import sqlite3 as _sq
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS herb_herb_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            herb_a TEXT NOT NULL,
            herb_b TEXT NOT NULL,
            evidence TEXT,
            doi TEXT,
            pair_key TEXT NOT NULL,
            trust REAL NOT NULL DEFAULT 0.9,
            source TEXT NOT NULL DEFAULT 'SUPP.AI'
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_hh_pair ON herb_herb_evidence(pair_key);
    """)
    herbs = json.loads((DATA_DIR / "herbs.json").read_text(encoding="utf-8"))
    suppai_herbs_path = DATA_DIR / "suppai_herbs.json"
    if suppai_herbs_path.exists():
        herbs = herbs + json.loads(suppai_herbs_path.read_text(encoding="utf-8"))
    idx: dict[str, str] = {}
    for h in herbs:
        for a in [h["name"], *(h.get("aliases") or [])]:
            if a:
                idx.setdefault(normalize(a), h["id"])

    rows = conn.execute(
        "SELECT id, herb_id, drug_name, evidence, doi FROM suppai_interactions"
        " WHERE class_id IS NULL"
    ).fetchall()
    inserted = 0
    for row_id, herb_id, drug_name, evidence, doi in rows:
        herb_b = idx.get(normalize(drug_name))
        if not herb_b or herb_b == herb_id:
            continue
        a, b = sorted((herb_id, herb_b))
        conn.execute(
            "INSERT OR IGNORE INTO herb_herb_evidence"
            " (herb_a, herb_b, evidence, doi, pair_key, trust)"
            " VALUES (?,?,?,?,?,0.9)",
            (a, b, evidence, doi, f"hh:{a}|{b}"),
        )
        inserted += 1
    conn.commit()
    return inserted

def remap_local(conn: sqlite3.Connection) -> int:
    """Fast offline remap: re-run name matching with the current class index."""
    cls_index = _load_class_index()
    rows = conn.execute(
        "SELECT DISTINCT drug_cui, drug_name FROM suppai_interactions"
        " WHERE class_id IS NULL"
    ).fetchall()
    updated = 0
    for cui, drug_name in rows:
        cid = None
        for n in [drug_name, drug_name.split(" (")[0], drug_name.split(",")[0]]:
            if n and normalize(n) in cls_index:
                cid = cls_index[normalize(n)]
                break
        if cid:
            cur = conn.execute(
                "UPDATE suppai_interactions SET class_id = ?"
                " WHERE drug_cui = ? AND class_id IS NULL",
                (cid, cui),
            )
            updated += cur.rowcount
    conn.commit()
    return updated


def remap_unmapped(conn: sqlite3.Connection, delay: float = 0.3) -> int:
    """Map NULL class_id rows via RxNorm name lookup (unambiguous matches only)."""
    rxnorm = json.loads((DATA_DIR / "rxnorm_map.json").read_text(encoding="utf-8"))
    classes = json.loads((DATA_DIR / "drug_classes.json").read_text(encoding="utf-8"))
    drug_names = json.loads((DATA_DIR / "drug_names_en.json").read_text(encoding="utf-8"))
    name_to_class = {}
    for c in classes:
        for d in c["drugs"]:
            name_to_class[drug_names.get(d.lower(), d).lower()] = c["id"]
    rxcui_to_class = {
        info["rxcui"]: name_to_class[name]
        for name, info in rxnorm.items()
        if name in name_to_class
    }

    rows = conn.execute(
        "SELECT DISTINCT drug_cui, drug_name FROM suppai_interactions"
        " WHERE class_id IS NULL"
    ).fetchall()
    updated = 0
    cache: dict[str, str | None] = {}
    for cui, drug_name in rows:
        if cui in cache:
            class_id = cache[cui]
        else:
            class_id = None
            try:
                d = _rx_get("/rxcui.json", {"name": drug_name})
                hits = {
                    rxcui_to_class[r]
                    for r in d.get("idGroup", {}).get("rxnormId", [])
                    if r in rxcui_to_class
                }
                if len(hits) == 1:
                    class_id = hits.pop()
            except Exception as e:
                print(f"ERR remap {drug_name}: {e}")
            cache[cui] = class_id
            time.sleep(delay)
        if class_id:
            cur = conn.execute(
                "UPDATE suppai_interactions SET class_id = ?"
                " WHERE drug_cui = ? AND class_id IS NULL",
                (class_id, cui),
            )
            updated += cur.rowcount
    conn.commit()
    return updated


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--delay", type=float, default=0.6)
    ap.add_argument("--enumerate", action="store_true")
    ap.add_argument("--crawl-all", action="store_true")
    ap.add_argument("--shard-mod", type=int, default=None)
    ap.add_argument("--shard-idx", type=int, default=None)
    ap.add_argument("--remap", action="store_true")
    ap.add_argument("--remap-local", action="store_true")
    ap.add_argument("--remap-herb-herb", action="store_true")
    args = ap.parse_args()
    from .db import DB_PATH

    if args.enumerate:
        enumerate_supplements(delay=args.delay)
        raise SystemExit(0)

    conn = sqlite3.connect(DB_PATH, isolation_level=None)  # autocommit: long crawls must not hold one txn
    try:
        if args.crawl_all:
            agents = json.loads(AGENTS_PATH.read_text(encoding="utf-8"))
            print(f"Crawl-all: {len(agents)} supplement agents")
            print(crawl_supplements(conn, agents, delay=args.delay, mod=args.shard_mod, idx=args.shard_idx))
        elif args.remap_local:
            print(f"REMAP-LOCAL updated {remap_local(conn)} rows")
        elif args.remap_herb_herb:
            print(f"HERB-HERB inserted {remap_herb_herb(conn)} rows")
        elif args.remap:
            print(f"REMAP updated {remap_unmapped(conn, delay=args.delay)} rows")
        else:
            stats = run(conn, args.limit, args.delay)
            total = conn.execute("SELECT COUNT(*) FROM suppai_interactions").fetchone()[0]
            print(f"DONE {stats} total_rows={total}")
    finally:
        conn.close()

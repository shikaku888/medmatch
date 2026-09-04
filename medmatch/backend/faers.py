"""Precompute FAERS adverse-event report counts for our drugs (openFDA, free).

For each drug name (class members + top SUPP.AI drug names), store the count
of adverse event reports mentioning it. Anonymous access works with a low
rate limit; an API key can be supplied via the OPENFDA_KEY env var.

Usage:
    python -m backend.faers [--limit N] [--delay 0.3]
    python -m backend.faers --build-aggregate
"""
import argparse
import json
import os
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from pathlib import Path
DATA_DIR = Path(__file__).parent / "data"
BASE = "https://api.fda.gov/drug/event.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS faers_counts (
    drug_name TEXT PRIMARY KEY,
    count INTEGER NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS faers_adverse_events (
    drug_key TEXT NOT NULL,
    drug_name TEXT NOT NULL,
    pt TEXT NOT NULL,
    quarter TEXT NOT NULL,
    case_count INTEGER NOT NULL,
    serious_case_count INTEGER NOT NULL,
    primary_suspect_case_count INTEGER NOT NULL DEFAULT 0,
    secondary_case_count INTEGER NOT NULL DEFAULT 0,
    concomitant_case_count INTEGER NOT NULL DEFAULT 0,
    first_seen TEXT,
    last_seen TEXT,
    source TEXT NOT NULL DEFAULT 'FDA FAERS',
    PRIMARY KEY (drug_key, pt, quarter)
);
CREATE INDEX IF NOT EXISTS idx_faers_events_pt ON faers_adverse_events(pt);
CREATE INDEX IF NOT EXISTS idx_faers_events_quarter ON faers_adverse_events(quarter);
"""


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^0-9a-z]+", " ", (name or "").casefold())).strip()


def build_adverse_event_aggregate(conn: sqlite3.Connection) -> dict[str, int]:
    """Materialize unique-case FAERS reactions for fast drug-level reads."""
    required = ("fda_report", "fda_drug", "fda_reaction", "fda_outcome")
    if any(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is None
        for table in required
    ):
        return {"rows": 0, "status": "missing_source_tables"}

    conn.executescript(SCHEMA)
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(faers_adverse_events)")
    }
    for column in (
        "primary_suspect_case_count",
        "secondary_case_count",
        "concomitant_case_count",
    ):
        if column not in columns:
            conn.execute(
                f"ALTER TABLE faers_adverse_events ADD COLUMN {column} INTEGER NOT NULL DEFAULT 0"
            )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fda_drug_prod_ai ON fda_drug(prod_ai)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fda_drug_name ON fda_drug(drugname)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fda_drug_primaryid ON fda_drug(primaryid)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fda_reaction_primaryid ON fda_reaction(primaryid)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fda_outcome_primaryid ON fda_outcome(primaryid)")
    conn.execute("DELETE FROM faers_adverse_events")
    conn.execute(
        """
        INSERT INTO faers_adverse_events
            (drug_key, drug_name, pt, quarter, case_count, serious_case_count,
             primary_suspect_case_count, secondary_case_count, concomitant_case_count,
             first_seen, last_seen, source)
        WITH latest AS (
            SELECT caseid, MAX(CAST(COALESCE(caseversion, '0') AS INTEGER)) AS caseversion
            FROM fda_report
            GROUP BY caseid
        ),
        reports AS (
            SELECT r.primaryid, r.caseid, r.quarter,
                   COALESCE(NULLIF(r.event_dt, ''), NULLIF(r.fda_dt, '')) AS seen_at
            FROM fda_report r
            JOIN latest l
              ON l.caseid = r.caseid
             AND l.caseversion = CAST(COALESCE(r.caseversion, '0') AS INTEGER)
        ),
        names AS (
            SELECT d.primaryid, d.caseid, d.role_cod, d.prod_ai AS drug_name,
                   d.quarter, p.seen_at
            FROM fda_drug d
            JOIN reports p ON p.primaryid = d.primaryid
            WHERE TRIM(COALESCE(d.prod_ai, '')) != ''
            UNION
            SELECT d.primaryid, d.caseid, d.role_cod, d.drugname AS drug_name,
                   d.quarter, p.seen_at
            FROM fda_drug d
            JOIN reports p ON p.primaryid = d.primaryid
            WHERE TRIM(COALESCE(d.drugname, '')) != ''
        ),
        reactions AS (
            SELECT DISTINCT n.primaryid, n.caseid, n.drug_name, n.role_cod, r.pt,
                            COALESCE(r.quarter, n.quarter) AS quarter, n.seen_at
            FROM names n
            JOIN fda_reaction r ON r.primaryid = n.primaryid
            WHERE TRIM(COALESCE(r.pt, '')) != ''
        )
        SELECT LOWER(TRIM(drug_name)), MIN(drug_name), pt, quarter,
               COUNT(DISTINCT caseid),
               COUNT(DISTINCT CASE WHEN EXISTS (
                   SELECT 1 FROM fda_outcome o
                   WHERE o.primaryid = reactions.primaryid
                     AND o.outc_cod IN ('DE', 'LT', 'HO', 'DS', 'CA')
               ) THEN caseid END),
               COUNT(DISTINCT CASE WHEN role_cod = 'PS' THEN caseid END),
               COUNT(DISTINCT CASE WHEN role_cod = 'SS' THEN caseid END),
               COUNT(DISTINCT CASE WHEN role_cod = 'C' THEN caseid END),
               MIN(seen_at), MAX(seen_at), 'FDA FAERS'
        FROM reactions
        GROUP BY LOWER(TRIM(drug_name)), pt, quarter
        """
    )
    count = conn.execute("SELECT COUNT(*) FROM faers_adverse_events").fetchone()[0]
    conn.commit()
    return {"rows": count, "status": "ok"}


def _get_count(drug_name: str, key: str | None) -> int | None:
    q = urllib.parse.quote(f'patient.drug.medicinalproduct:"{drug_name}"')
    url = f"{BASE}?search={q}&limit=1"
    headers = {}
    if key:
        url += f"&api_key={key}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return 0  # openFDA 404 = no reports for this drug
        raise
    return d.get("meta", {}).get("results", {}).get("total")


def collect_names(conn: sqlite3.Connection, limit: int | None) -> list[str]:
    names: set[str] = set()
    classes = json.loads((DATA_DIR / "drug_classes.json").read_text(encoding="utf-8"))
    drug_names = json.loads((DATA_DIR / "drug_names_en.json").read_text(encoding="utf-8"))
    for c in classes:
        for d in c["drugs"]:
            names.add(drug_names.get(d.lower(), d).lower())
    # top SUPP.AI drug names by row count
    rows = conn.execute(
        "SELECT drug_name, COUNT(*) n FROM suppai_interactions"
        " WHERE drug_name != '' GROUP BY drug_name ORDER BY n DESC LIMIT 200"
    ).fetchall()
    for drug_name, _ in rows:
        names.add(drug_name.lower())
    out = sorted(names)
    if limit:
        out = out[:limit]
    return out


def run(conn: sqlite3.Connection, limit: int | None, delay: float) -> dict:
    conn.executescript(SCHEMA)
    key = os.environ.get("OPENFDA_KEY") or None
    names = collect_names(conn, limit)
    stats = {"total": len(names), "ok": 0, "errors": 0}
    for name in names:
        try:
            count = _get_count(name, key)
            if count is not None:
                conn.execute(
                    "INSERT OR REPLACE INTO faers_counts (drug_name, count) VALUES (?,?)",
                    (name, count),
                )
                stats["ok"] += 1
        except Exception as e:
            stats["errors"] += 1
            print(f"ERR {name}: {e}")
        time.sleep(delay)
        if stats["ok"] % 50 == 0 and stats["ok"]:
            print(f"ok={stats['ok']}/{stats['total']} errors={stats['errors']}")
    conn.commit()
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--delay", type=float, default=0.3)
    ap.add_argument(
        "--build-aggregate",
        action="store_true",
        help="build the local unique-case FAERS adverse-event aggregate",
    )
    args = ap.parse_args()
    from .db import DB_PATH

    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    try:
        if args.build_aggregate:
            print(build_adverse_event_aggregate(conn))
        else:
            print(run(conn, args.limit, args.delay))
    finally:
        conn.close()

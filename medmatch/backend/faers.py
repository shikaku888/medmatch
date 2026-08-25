"""Precompute FAERS adverse-event report counts for our drugs (openFDA, free).

For each drug name (class members + top SUPP.AI drug names), store the count
of adverse event reports mentioning it. Anonymous access works with a low
rate limit; an API key can be supplied via the OPENFDA_KEY env var.

Usage:
    python -m backend.faers [--limit N] [--delay 0.3]
"""
import argparse
import json
import os
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
"""


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
    args = ap.parse_args()
    from .db import DB_PATH

    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    try:
        print(run(conn, args.limit, args.delay))
    finally:
        conn.close()

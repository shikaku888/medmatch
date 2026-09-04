"""FDA enforcement (recalls) — drug + food, via openFDA (CC0, no key).

Bulk-copies the full openFDA enforcement archive (drug ~17.9k + food ~29.3k
records) into a local table so the scanner can badge an unsafe product at
scan/lookup time without a network round-trip. Records are upserted by
``event_id``; a failed refresh never deletes prior successful data.

Usage:
    python -m backend.recalls [--max N] [--delay 0.35]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import time
import urllib.request
import zipfile
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from .db import DB_PATH
from .license_registry import register_release, seed_licenses

API_BASE = "https://api.fda.gov"
SOURCE_CODE = "fda_recalls"
PARSER_VERSION = "fda-recalls-v1"
DEFAULT_MAX = 60000
PAGE_SIZE = 1000

SCHEMA = """
CREATE TABLE IF NOT EXISTS fda_recalls (
    event_key TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    product_type TEXT,
    classification TEXT,
    status TEXT,
    recalling_firm TEXT,
    city TEXT,
    state TEXT,
    country TEXT,
    product_description TEXT,
    product_quantity TEXT,
    reason_for_recall TEXT,
    recall_number TEXT,
    voluntary_mandated TEXT,
    initial_firm_notification TEXT,
    distribution_pattern TEXT,
    recall_initiation_date TEXT,
    center_classification_date TEXT,
    termination_date TEXT,
    report_date TEXT,
    code_info TEXT,
    more_code_info TEXT,
    source_url TEXT NOT NULL,
    downloaded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fda_recalls_desc ON fda_recalls(product_description);
CREATE INDEX IF NOT EXISTS idx_fda_recalls_firm ON fda_recalls(recalling_firm);
CREATE INDEX IF NOT EXISTS idx_fda_recalls_class ON fda_recalls(classification);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _digits(value) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _fetch_all(
    endpoint: str,
    *,
    max_records: int,
    delay: float,
    api_key: str | None,
) -> list[dict]:
    """Fetch all enforcement pages for `endpoint` (drug or food)."""
    records: list[dict] = []
    skip = 0
    while len(records) < max_records:
        params = {"skip": skip, "limit": min(PAGE_SIZE, max_records - len(records))}
        if api_key:
            params["api_key"] = api_key
        url = f"{API_BASE}/{endpoint}.json?" + urllib.parse.urlencode(params)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MedMatch-Recalls/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.load(resp)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                break
            raise
        page = payload.get("results") or []
        if not page:
            break
        records.extend(page)
        skip += len(page)
        if len(page) < PAGE_SIZE:
            break
        time.sleep(delay)
    return records[:max_records]

def _read_archive(path: Path) -> list[dict]:
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.casefold().endswith(".json")]
        if not members:
            raise ValueError(f"recall archive has no JSON member: {path}")
        with archive.open(members[0]) as stream:
            payload = json.load(stream)
    records = payload.get("results") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError("recall archive missing results array")
    return records

def _event_key(record: dict) -> str:
    """FDA event_id repeats for product-level rows; include recall/product identity."""
    values = "|".join(str(record.get(field) or "") for field in (
        "product_type", "event_id", "recall_number", "product_description", "code_info"
    ))
    return hashlib.sha256(values.encode("utf-8")).hexdigest()


def _row(record: dict, source_url: str, downloaded_at: str) -> tuple:
    event_id = str(record.get("event_id") or "")
    product_type = str(record.get("product_type") or "")
    return (
        _event_key(record), event_id, product_type,
        str(record.get("classification") or ""), str(record.get("status") or ""),
        str(record.get("recalling_firm") or ""), str(record.get("city") or ""),
        str(record.get("state") or ""), str(record.get("country") or ""),
        str(record.get("product_description") or ""), str(record.get("product_quantity") or ""),
        str(record.get("reason_for_recall") or ""), str(record.get("recall_number") or ""),
        str(record.get("voluntary_mandated") or ""), str(record.get("initial_firm_notification") or ""),
        str(record.get("distribution_pattern") or ""), str(record.get("recall_initiation_date") or ""),
        str(record.get("center_classification_date") or ""), str(record.get("termination_date") or ""),
        str(record.get("report_date") or ""), str(record.get("code_info") or ""),
        str(record.get("more_code_info") or ""), source_url, downloaded_at,
    )


def run(conn: sqlite3.Connection, max_records: int = DEFAULT_MAX, delay: float = 0.35) -> dict:
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(fda_recalls)")}
    if "event_key" not in columns and "event_id" in columns:
        conn.execute("DROP INDEX IF EXISTS idx_fda_recalls_desc")
        conn.execute("DROP INDEX IF EXISTS idx_fda_recalls_firm")
        conn.execute("DROP INDEX IF EXISTS idx_fda_recalls_class")
        conn.execute("ALTER TABLE fda_recalls RENAME TO fda_recalls_legacy")
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT OR IGNORE INTO fda_recalls "
            "SELECT product_type || ':' || event_id, event_id, product_type, classification, status, "
            "recalling_firm, city, state, country, product_description, product_quantity, reason_for_recall, "
            "recall_number, voluntary_mandated, initial_firm_notification, distribution_pattern, "
            "recall_initiation_date, center_classification_date, termination_date, report_date, code_info, "
            "more_code_info, source_url, downloaded_at FROM fda_recalls_legacy"
        )
        conn.execute("DROP TABLE fda_recalls_legacy")
    api_key = os.environ.get("OPENFDA_KEY") or None
    downloaded_at = _now()
    stats = {"ok": 0, "errors": 0, "records": 0}
    seen: set[str] = set()
    seed_licenses(conn, {"fda_recalls"})
    archive_dir = Path(__file__).parent / "data" / "recalls"
    sources = (
        ("drug/enforcement", archive_dir / "drug-enforcement.zip", "https://download.open.fda.gov/drug/enforcement/drug-enforcement-0001-of-0001.json.zip"),
        ("food/enforcement", archive_dir / "food-enforcement.zip", "https://download.open.fda.gov/food/enforcement/food-enforcement-0001-of-0001.json.zip"),
    )
    if all(archive.exists() for _, archive, _ in sources):
        conn.execute("DELETE FROM fda_recalls")
    for endpoint, archive, bulk_url in sources:
        try:
            page = (_read_archive(archive) if archive.exists() else _fetch_all(
                endpoint, max_records=max_records, delay=delay, api_key=api_key
            ))
            for record in page:
                event_id = str(record.get("event_id") or "")
                event_key = _event_key(record)
                if not event_id or event_key in seen:
                    continue
                seen.add(event_key)
                source_url = f"{API_BASE}/{endpoint}.json?search=event_id:{event_id}"
                conn.execute(
                    "INSERT OR REPLACE INTO fda_recalls VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    _row(record, source_url, downloaded_at),
                )
            stats["ok"] += 1
            stats["records"] += len(page)
        except Exception as error:
            stats["errors"] += 1
            print(f"ERR {endpoint}: {error}")
    conn.commit()

    blob = json.dumps(
        [dict(r) for r in conn.execute(
            "SELECT event_id, product_type, classification, product_description, "
            "reason_for_recall, recall_number, recall_initiation_date FROM fda_recalls"
        )], ensure_ascii=False, sort_keys=True,
    ).encode("utf-8")
    import hashlib
    register_release(
        conn, SOURCE_CODE, "FDA enforcement records (drug + food recalls)",
        version=downloaded_at, source_url="https://api.fda.gov/download.json",
        terms_url="https://open.fda.gov/license/",
        licence_name="Public Domain / CC0 (openFDA, US federal)", commercial_status="core_open",
        sha256=hashlib.sha256(blob).hexdigest(), parser_version=PARSER_VERSION,
        downloaded_at=downloaded_at, notes=f"drug+food records={stats['records']}",
    )
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=DEFAULT_MAX)
    ap.add_argument("--delay", type=float, default=0.35)
    args = ap.parse_args()
    conn = sqlite3.connect(DB_PATH, timeout=90)
    try:
        print(run(conn, max_records=max(1, min(args.max, 60000)), delay=args.delay))
    finally:
        conn.close()
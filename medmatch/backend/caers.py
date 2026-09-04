"""Import CAERS supplement/food adverse-event data from openFDA.

The official bulk manifest (``https://api.fda.gov/download.json``) publishes a
single ~9 MB ZIP for the current 151k-report release. CAERS is CC0/openFDA and
is observational: a report can list multiple products and reactions, so rows
are signals and never causality/incidence claims.

Usage:
    python -m backend.caers [food-event.json.zip]
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from .db import DB_PATH
from .license_registry import register_release, seed_licenses

DEFAULT_ARCHIVE = Path(__file__).parent / "data" / "caers" / "food-event.zip"
SOURCE_URL = "https://download.open.fda.gov/food/event/food-event-0001-of-0001.json.zip"
MANIFEST_URL = "https://api.fda.gov/download.json"
PARSER_VERSION = "caers-bulk-v1"

SCHEMA = """
CREATE TABLE IF NOT EXISTS caers_product_events (
    product_key TEXT NOT NULL,
    product_name TEXT NOT NULL,
    reaction TEXT NOT NULL,
    case_count INTEGER NOT NULL,
    serious_count INTEGER NOT NULL,
    first_seen TEXT,
    last_seen TEXT,
    source TEXT NOT NULL DEFAULT 'FDA CAERS',
    PRIMARY KEY (product_key, reaction)
);
CREATE INDEX IF NOT EXISTS idx_caers_key ON caers_product_events(product_key);
CREATE INDEX IF NOT EXISTS idx_caers_reaction ON caers_product_events(reaction);
"""

_SERIOUS = {"death", "life threatening", "hospitalization", "disability", "birth defect", "required intervention"}


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^0-9a-z]+", " ", (name or "").casefold())).strip()


def _date(value) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    if len(digits) >= 6:
        return f"{digits[:4]}-{digits[4:6]}"
    return None


def _read_archive(path: Path) -> list[dict]:
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.casefold().endswith(".json")]
        if not members:
            raise ValueError("CAERS archive has no JSON member")
        with archive.open(members[0]) as stream:
            payload = json.load(stream)
    reports = payload.get("results") if isinstance(payload, dict) else payload
    if not isinstance(reports, list):
        raise ValueError("CAERS archive missing results array")
    return reports


def _aggregate(reports: list[dict]) -> list[tuple]:
    # One case/reaction/product is counted once even if a malformed report
    # repeats an item. FDA cautions that product↔reaction causality is unknown.
    buckets: dict[tuple[str, str], list] = {}
    for report in reports:
        report_id = str(report.get("report_number") or report.get("report_id") or "")
        when = _date(report.get("date_created") or report.get("date_started"))
        serious = any(str(outcome).casefold() in _SERIOUS for outcome in (report.get("outcomes") or []))
        products = report.get("products") or []
        reactions = {str(value).strip().upper() for value in (report.get("reactions") or []) if str(value).strip()}
        product_pairs: set[tuple[str, str]] = set()
        for product in products:
            if not isinstance(product, dict):
                continue
            name = str(product.get("name_brand") or product.get("name") or "").strip()
            key = _normalize_name(name)
            if not key or not reactions:
                continue
            for reaction in reactions:
                product_pairs.add((key, reaction))
                bucket = buckets.setdefault((key, reaction), [name, set(), 0, [], []])
                # report IDs are unique in the source; retain a bounded fallback
                # key for malformed records so repeated rows do not double count.
                identity = report_id or f"{when}:{name}:{reaction}"
                if identity in bucket[1]:
                    continue
                bucket[1].add(identity)
                bucket[2] += int(serious)
                if when:
                    bucket[3].append(when)
                    bucket[4].append(when)
    output = []
    for (key, reaction), (name, identities, serious, firsts, lasts) in buckets.items():
        output.append((key, name, reaction, len(identities), serious, min(firsts) if firsts else None, max(lasts) if lasts else None))
    return output


def run(conn: sqlite3.Connection, archive: Path = DEFAULT_ARCHIVE) -> dict:
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    downloaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    reports = _read_archive(archive)
    rows = _aggregate(reports)
    seed_licenses(conn, {"caers"})
    conn.execute("DELETE FROM caers_product_events")
    conn.executemany(
        "INSERT OR REPLACE INTO caers_product_events "
        "(product_key, product_name, reaction, case_count, serious_count, first_seen, last_seen) VALUES (?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    register_release(
        conn, "caers", "FDA CAERS bulk food/supplement/cosmetic adverse events",
        version=downloaded_at, source_url=SOURCE_URL, terms_url="https://open.fda.gov/license/",
        licence_name="Public Domain / CC0 (openFDA CAERS)", commercial_status="core_open",
        downloaded_at=downloaded_at, sha256=digest.hexdigest(), parser_version=PARSER_VERSION,
        notes=f"reports={len(reports)}; product-reaction aggregates={len(rows)}",
    )
    return {"reports": len(reports), "aggregates": len(rows), "products": conn.execute("SELECT COUNT(DISTINCT product_key) FROM caers_product_events").fetchone()[0]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("archive", nargs="?", type=Path, default=DEFAULT_ARCHIVE)
    args = ap.parse_args()
    conn = sqlite3.connect(DB_PATH, timeout=120)
    try:
        print(run(conn, args.archive))
    finally:
        conn.close()

"""Enrich the existing DailyMed/openFDA label index with clinical sections.

The local openFDA bulk archives are already downloaded and ``label_section``
contains their set IDs plus warnings/interactions. This pass adds indications,
contraindications, population sections, dosage, active ingredients and inactive
ingredients without storing another copy of raw label JSON. It also fills
``ndc_products.inactive_ingredients`` when a label's product/package NDC joins.
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

DATA_DIR = Path(__file__).parent / "data" / "openfda"
SOURCE_CODE = "openfda"
PARSER_VERSION = "openfda-label-sections-v1"
TARGET_COLUMNS = {
    "indications_and_usage": "indications_and_usage",
    "contraindications": "contraindications",
    "adverse_reactions": "adverse_reactions",
    "pregnancy": "pregnancy",
    "lactation": "lactation",
    "pediatric_use": "pediatric_use",
    "geriatric_use": "geriatric_use",
    "renal_impairment": "renal_impairment",
    "hepatic_impairment": "hepatic_impairment",
    "overdosage": "overdosage",
    "dosage_and_administration": "dosage_and_administration",
    "inactive_ingredient": "inactive_ingredient",
    "active_ingredient": "active_ingredient",
    "purpose": "purpose",
}


def _text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        value = "\n\n".join(part for item in value if (part := _text(item)))
    elif isinstance(value, dict):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    value = str(value).strip()
    return value or None


def _ensure_columns(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(label_section)")}
    for column in TARGET_COLUMNS.values():
        if column not in columns:
            conn.execute(f"ALTER TABLE label_section ADD COLUMN {column} TEXT")
    ndc_columns = {row[1] for row in conn.execute("PRAGMA table_info(ndc_products)")}
    if ndc_columns and "inactive_ingredients" not in ndc_columns:
        conn.execute("ALTER TABLE ndc_products ADD COLUMN inactive_ingredients TEXT NOT NULL DEFAULT ''")


def _ndc_values(openfda: dict) -> list[str]:
    values = []
    for key in ("product_ndc", "package_ndc"):
        raw = openfda.get(key) or []
        if not isinstance(raw, list):
            raw = [raw]
        values.extend(str(value).strip() for value in raw if str(value).strip())
    return list(dict.fromkeys(values))


def run(conn: sqlite3.Connection, archives: list[Path] | None = None) -> dict:
    conn.row_factory = sqlite3.Row
    _ensure_columns(conn)
    seed_licenses(conn, {SOURCE_CODE})
    archives = archives or sorted(DATA_DIR.glob("drug-label-*.json.zip"))
    if not archives:
        raise FileNotFoundError(f"No openFDA label archives found under {DATA_DIR}")
    downloaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    stats = {"archives": 0, "labels": 0, "matched_label_rows": 0, "ndc_excipients": 0, "errors": 0}
    update_columns = tuple(TARGET_COLUMNS.values())
    set_clause = ", ".join(f"{column} = ?" for column in update_columns)
    for archive in archives:
        stats["archives"] += 1
        try:
            with zipfile.ZipFile(archive) as z:
                members = [name for name in z.namelist() if name.casefold().endswith(".json")]
                if not members:
                    raise ValueError("archive has no JSON member")
                payload = json.load(z.open(members[0]))
            records = payload.get("results") or []
            for record in records:
                if not isinstance(record, dict):
                    continue
                stats["labels"] += 1
                set_id = str(record.get("set_id") or "").strip()
                if not set_id:
                    continue
                values = [_text(record.get(source)) for source in TARGET_COLUMNS]
                cur = conn.execute(
                    f"UPDATE label_section SET {set_clause} WHERE set_id = ?",
                    [*values, set_id],
                )
                stats["matched_label_rows"] += cur.rowcount
                openfda = record.get("openfda") or {}
                inactive = _text(record.get("inactive_ingredient"))
                if inactive:
                    for ndc in _ndc_values(openfda):
                        cur = conn.execute(
                            "UPDATE ndc_products SET inactive_ingredients = ? "
                            "WHERE product_ndc = ? AND (inactive_ingredients IS NULL OR inactive_ingredients = '')",
                            (inactive, ndc),
                        )
                        stats["ndc_excipients"] += max(cur.rowcount, 0)
                if stats["labels"] % 5000 == 0:
                    conn.commit()
            conn.commit()
        except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as error:
            stats["errors"] += 1
            print(f"ERR {archive.name}: {error}")
    digest = hashlib.sha256()
    for archive in archives:
        with archive.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
    register_release(
        conn, SOURCE_CODE, "openFDA bulk label clinical sections",
        version=downloaded_at, source_url="https://api.fda.gov/download.json",
        terms_url="https://open.fda.gov/license/", licence_name="Public Domain / CC0 (openFDA)",
        commercial_status="core_open", downloaded_at=downloaded_at,
        sha256=digest.hexdigest(), parser_version=PARSER_VERSION,
        notes=f"archives={len(archives)}; labels={stats['labels']}; matched={stats['matched_label_rows']}",
    )
    stats["rows"] = conn.execute("SELECT COUNT(*) FROM label_section").fetchone()[0]
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("archives", nargs="*", type=Path)
    args = parser.parse_args()
    conn = sqlite3.connect(DB_PATH, timeout=120)
    try:
        print(run(conn, args.archives or None))
    finally:
        conn.close()

"""Targeted, retrying OpenFDA drug-label refresh.

The runner intentionally refreshes named drugs instead of crawling the entire
OpenFDA label archive. Each successful record is upserted into a source-owned
label table and recorded in the crawl manifest. A failed target never deletes
its previous successful data.

Usage::

    python -m backend.refresh_openfda --drug sirolimus
    python -m backend.refresh_openfda --drug warfarin --drug sirolimus
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Callable, Iterable

from .db import DB_PATH
from .license_registry import register_release, seed_licenses

API_BASE = "https://api.fda.gov/drug/label.json"
SOURCE_CODE = "openfda"
PARSER_VERSION = "openfda-label-refresh-v1"
DEFAULT_PAGE_SIZE = 100
DEFAULT_MAX_LABELS = 1000

SCHEMA = """
CREATE TABLE IF NOT EXISTS openfda_label_sections (
    label_id TEXT PRIMARY KEY,
    effective_time TEXT,
    generic_name TEXT,
    brand_name TEXT,
    openfda_generic TEXT,
    boxed_warning TEXT,
    contraindications TEXT,
    warnings_and_precautions TEXT,
    adverse_reactions TEXT,
    drug_interactions TEXT,
    pregnancy TEXT,
    lactation TEXT,
    pediatric_use TEXT,
    geriatric_use TEXT,
    renal_impairment TEXT,
    hepatic_impairment TEXT,
    overdosage TEXT,
    dosage_and_administration TEXT,
    source_url TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'openFDA',
    raw_json TEXT NOT NULL,
    downloaded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_openfda_label_generic
    ON openfda_label_sections(generic_name, openfda_generic);
CREATE INDEX IF NOT EXISTS idx_openfda_label_brand
    ON openfda_label_sections(brand_name);
"""

MANIFEST_SCHEMA = """
CREATE TABLE IF NOT EXISTS crawl_manifest (
    source TEXT NOT NULL,
    item_key TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_ok_at TEXT,
    note TEXT,
    PRIMARY KEY (source, item_key)
);
"""

_SECTION_FIELDS = {
    "boxed_warning": ("boxed_warning",),
    "contraindications": ("contraindications",),
    "warnings_and_precautions": ("warnings_and_precautions", "warnings"),
    "adverse_reactions": ("adverse_reactions",),
    "drug_interactions": ("drug_interactions",),
    "pregnancy": ("pregnancy",),
    "lactation": ("lactation", "nursing_mothers", "pregnancy_or_breast_feeding"),
    "pediatric_use": ("pediatric_use",),
    "geriatric_use": ("geriatric_use",),
    "renal_impairment": ("renal_impairment",),
    "hepatic_impairment": ("hepatic_impairment",),
    "overdosage": ("overdosage",),
    "dosage_and_administration": ("dosage_and_administration",),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^0-9a-z]+", " ", (value or "").casefold())).strip()


def _text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        parts = [_text(item) for item in value]
        value = "\n\n".join(part for part in parts if part)
    elif isinstance(value, dict):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    value = str(value).strip()
    return value or None


def _first(record: dict, *keys: str) -> str | None:
    for key in keys:
        value = _text(record.get(key))
        if value:
            return value
    return None


def parse_label(record: dict, source_url: str, downloaded_at: str | None = None) -> dict:
    """Convert one openFDA label document into the local section contract."""
    if not isinstance(record, dict):
        raise ValueError("OpenFDA label record must be an object")
    openfda = record.get("openfda")
    if not isinstance(openfda, dict):
        openfda = {}
    label_id = _first(record, "id") or _first(openfda, "spl_set_id", "spl_id")
    if not label_id:
        raise ValueError("OpenFDA label has no stable id")
    parsed = {
        "label_id": label_id,
        "effective_time": _first(record, "effective_time", "effective_date"),
        "generic_name": _first(openfda, "generic_name"),
        "brand_name": _first(openfda, "brand_name"),
        "openfda_generic": _first(openfda, "generic_name"),
        "source_url": source_url,
        "source": "openFDA",
        "raw_json": json.dumps(record, ensure_ascii=False, sort_keys=True),
        "downloaded_at": downloaded_at or _now(),
    }
    for target, fields in _SECTION_FIELDS.items():
        parsed[target] = _first(record, *fields)
    return parsed


def _query_url(drug_name: str, skip: int, limit: int, api_key: str | None) -> str:
    params = {
        "search": f'openfda.generic_name:"{drug_name}"',
        "skip": skip,
        "limit": limit,
    }
    if api_key:
        params["api_key"] = api_key
    return API_BASE + "?" + urllib.parse.urlencode(params)


def fetch_page(
    drug_name: str,
    *,
    skip: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    retries: int = 4,
    api_key: str | None = None,
    opener: Callable = urllib.request.urlopen,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Fetch one page, retrying only transient OpenFDA failures."""
    url = _query_url(drug_name, skip, limit, api_key)
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(
                url,
                headers={"Accept": "application/json", "User-Agent": "MedMatch-OpenFDA-Refresh/1.0"},
            )
            with opener(request, timeout=30) as response:
                payload = json.load(response)
            if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
                raise ValueError("OpenFDA response missing results array")
            return payload
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return {"results": [], "meta": {"results": {"total": 0}}}
            last_error = error
            transient = error.code == 429 or 500 <= error.code <= 599
            if not transient or attempt >= retries:
                raise
            retry_after = error.headers.get("Retry-After") if error.headers else None
            if retry_after is not None:
                try:
                    delay = max(0.0, float(retry_after))
                except ValueError:
                    delay = min(30.0, 0.5 * (2**attempt))
            else:
                delay = min(30.0, 0.5 * (2**attempt))
            sleep(delay)
        except (TimeoutError, urllib.error.URLError, ValueError, json.JSONDecodeError) as error:
            last_error = error
            if attempt >= retries:
                raise
            sleep(min(30.0, 0.5 * (2**attempt)))
    raise RuntimeError(f"OpenFDA request failed: {last_error}")


def fetch_records(
    drug_name: str,
    *,
    max_labels: int = DEFAULT_MAX_LABELS,
    page_size: int = DEFAULT_PAGE_SIZE,
    retries: int = 4,
    api_key: str | None = None,
    fetch_page_fn: Callable = fetch_page,
) -> tuple[list[dict], str | None]:
    records: list[dict] = []
    skip = 0
    last_updated = None
    while len(records) < max_labels:
        payload = fetch_page_fn(
            drug_name,
            skip=skip,
            limit=min(page_size, max_labels - len(records)),
            retries=retries,
            api_key=api_key,
        )
        page = payload.get("results") or []
        meta = payload.get("meta") or {}
        result_meta = meta.get("results") if isinstance(meta, dict) else None
        if isinstance(result_meta, dict):
            last_updated = meta.get("last_updated") or result_meta.get("last_updated") or last_updated
        if not page:
            break
        records.extend(page)
        skip += len(page)
        total = result_meta.get("total") if isinstance(result_meta, dict) else None
        if len(page) < page_size or (isinstance(total, int) and skip >= total):
            break
    return records[:max_labels], last_updated


def _manifest_start(conn: sqlite3.Connection, item_key: str) -> None:
    now = _now()
    conn.execute(
        "INSERT INTO crawl_manifest (source,item_key,started_at,finished_at,status,attempts,last_ok_at,note) "
        "VALUES (?,?,?,NULL,'pending',1,NULL,NULL) "
        "ON CONFLICT(source,item_key) DO UPDATE SET started_at=excluded.started_at, "
        "finished_at=NULL, status='pending', attempts=crawl_manifest.attempts+1, note=NULL",
        (SOURCE_CODE, item_key, now),
    )
    conn.commit()


def _manifest_finish(conn: sqlite3.Connection, item_key: str, status: str, note: str | None = None) -> None:
    now = _now()
    conn.execute(
        "UPDATE crawl_manifest SET finished_at=?, status=?, last_ok_at=CASE WHEN ?='ok' THEN ? ELSE last_ok_at END, note=? "
        "WHERE source=? AND item_key=?",
        (now, status, status, now, note, SOURCE_CODE, item_key),
    )
    conn.commit()


def _upsert_label(conn: sqlite3.Connection, label: dict) -> None:
    columns = (
        "label_id", "effective_time", "generic_name", "brand_name", "openfda_generic",
        "boxed_warning", "contraindications", "warnings_and_precautions", "adverse_reactions",
        "drug_interactions", "pregnancy", "lactation", "pediatric_use", "geriatric_use",
        "renal_impairment", "hepatic_impairment", "overdosage", "dosage_and_administration",
        "source_url", "source", "raw_json", "downloaded_at",
    )
    values = [label.get(column) for column in columns]
    placeholders = ",".join("?" for _ in columns)
    updates = ",".join(f"{column}=excluded.{column}" for column in columns[1:])
    conn.execute(
        f"INSERT INTO openfda_label_sections ({','.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT(label_id) DO UPDATE SET {updates}",
        values,
    )


def refresh(
    conn: sqlite3.Connection,
    drug_names: Iterable[str],
    *,
    max_labels: int = DEFAULT_MAX_LABELS,
    page_size: int = DEFAULT_PAGE_SIZE,
    retries: int = 4,
    api_key: str | None = None,
    fetcher: Callable | None = None,
) -> dict:
    """Refresh named drugs without deleting prior data on a failed target."""
    if conn.row_factory is None:
        conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.executescript(MANIFEST_SCHEMA)
    seed_licenses(conn, {SOURCE_CODE})
    names = list(dict.fromkeys(_normalize_name(str(name)) for name in drug_names if _normalize_name(str(name))))
    stats = {"requested": len(names), "ok": 0, "empty": 0, "errors": 0, "labels": 0}
    release_records: list[dict] = []
    fetcher = fetcher or (lambda name: fetch_records(
        name, max_labels=max_labels, page_size=page_size, retries=retries, api_key=api_key,
    ))
    for name in names:
        _manifest_start(conn, name)
        try:
            fetched = fetcher(name)
            if isinstance(fetched, tuple):
                records, version = fetched
            else:
                records, version = fetched, None
            if not isinstance(records, list):
                raise ValueError("refresh fetcher must return a list of records")
            parsed = [parse_label(record, f"{API_BASE}?search={urllib.parse.quote(name)}") for record in records]
            with conn:
                for label in parsed:
                    _upsert_label(conn, label)
            _manifest_finish(conn, name, "ok", "no labels found" if not parsed else None)
            stats["ok"] += 1
            stats["empty"] += int(not parsed)
            stats["labels"] += len(parsed)
            release_records.extend(parsed)
        except Exception as error:
            _manifest_finish(conn, name, "error", str(error)[:500])
            stats["errors"] += 1
    if release_records:
        blob = "\n".join(label["raw_json"] for label in release_records).encode("utf-8")
        version = _now()
        register_release(
            conn,
            SOURCE_CODE,
            "OpenFDA targeted drug label refresh",
            version=version,
            source_url=API_BASE,
            terms_url="https://open.fda.gov/license/",
            licence_name="Public Domain / CC0 (openFDA, US federal)",
            commercial_status="core_open",
            sha256=hashlib.sha256(blob).hexdigest(),
            parser_version=PARSER_VERSION,
            notes=f"Targeted labels: {', '.join(names)}; records={len(release_records)}",
        )
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh named OpenFDA drug labels")
    parser.add_argument("--drug", action="append", required=True, help="Generic drug name; repeat for multiple drugs")
    parser.add_argument("--max-labels", type=int, default=DEFAULT_MAX_LABELS)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--retries", type=int, default=4)
    args = parser.parse_args()
    conn = sqlite3.connect(DB_PATH)
    try:
        print(refresh(
            conn,
            args.drug,
            max_labels=max(1, min(args.max_labels, 1000)),
            page_size=max(1, min(args.page_size, 100)),
            retries=max(0, min(args.retries, 8)),
            api_key=os.environ.get("OPENFDA_API_KEY") or os.environ.get("OPENFDA_KEY"),
        ))
    finally:
        conn.close()


if __name__ == "__main__":
    main()

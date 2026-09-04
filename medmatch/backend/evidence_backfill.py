"""Backfill the Phase 1 canonical evidence layer from interaction_unified.

This is intentionally conservative. Existing source tables remain unchanged;
rows with no release/license are retained as candidate lineage and are not
silently promoted as accepted commercial evidence.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .evidence_schema import (
    SCHEMA_VERSION,
    canonical_json,
    evidence_id,
    finding_id,
    normalized_payload_hash,
    scope_hash,
)
from .license_registry import KNOWN_LICENSES
from .source_reconciliation import ensure_reconciliation_schema, resolve_source_code

PARSER_VERSION = "unified-backfill-v1"
POLICY_VERSION = "provenance-backfill-v1"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _source_level(source: str, inferred: bool) -> str:
    if inferred or "inference" in source.casefold():
        return "inferred"
    text = source.casefold()
    if "fda" in text or "dailymed" in text or "label" in text:
        return "regulatory"
    return "unknown"


def _finding_type(a_kind: str, b_kind: str) -> str:
    kinds = {a_kind, b_kind}
    if kinds == {"drug_class"}:
        return "drug_drug"
    if "food" in kinds and "drug_class" in kinds:
        return "drug_food"
    if "herb" in kinds and "drug_class" in kinds:
        return "herb_drug"
    if kinds == {"herb"}:
        return "herb_herb"
    return "mechanism"


def _release_for(conn: sqlite3.Connection, source_code: str) -> tuple[str, str]:
    row = conn.execute(
        "SELECT version, release_status FROM dataset_release "
        "WHERE source_code = ? ORDER BY downloaded_at DESC LIMIT 1",
        (source_code,),
    ).fetchone()
    if row and row[0]:
        return f"{source_code}:{row[0]}", row[1] or "accepted"
    version = "legacy-unknown"
    conn.execute(
        "INSERT OR IGNORE INTO dataset_release "
        "(source_code, dataset_name, version, licence_name, commercial_status, "
        "downloaded_at, parser_version, notes, release_status) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (
            source_code,
            f"Legacy unified evidence ({source_code})",
            version,
            (KNOWN_LICENSES.get(source_code) or {}).get("label"),
            "restricted_private",
            _now(),
            PARSER_VERSION,
            "Synthetic release created during conservative Phase 1 backfill; review required.",
            "candidate",
        ),
    )
    return f"{source_code}:{version}", "candidate"


def _ingestion_run(conn: sqlite3.Connection, source_code: str, release_id: str) -> str:
    run_id = f"backfill:interaction_unified:{source_code}:v1"
    conn.execute(
        "INSERT OR IGNORE INTO ingestion_run "
        "(ingestion_run_id, source_code, release_id, parser_version, contract_version, "
        "started_at, completed_at, status, notes) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            run_id, source_code, release_id, PARSER_VERSION, SCHEMA_VERSION,
            _now(), _now(), "accepted",
            "Conservative backfill from interaction_unified; not a fresh crawl.",
        ),
    )
    return run_id


def _subjects(conn: sqlite3.Connection, eid: str, row: sqlite3.Row) -> None:
    for ordinal, kind, entity_id in (
        (0, row["a_kind"], row["a_id"]),
        (1, row["b_kind"], row["b_id"]),
    ):
        conn.execute(
            "INSERT OR IGNORE INTO evidence_record_subject "
            "(evidence_id, ordinal, entity_kind, entity_id, raw_name, mapping_method, "
            "mapping_confidence, mapping_status) VALUES (?,?,?,?,?,?,?,?)",
            (eid, ordinal, kind, entity_id, entity_id, "legacy_unified_id", 1.0, "accepted"),
        )


def backfill_unified(conn: sqlite3.Connection, limit: int | None = None) -> dict[str, int]:
    ensure_reconciliation_schema(conn)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(interaction_unified)")}
    required = {"pair_key", "a_kind", "a_id", "b_kind", "b_id", "severity", "effect", "mechanism", "evidence", "confidence", "is_inferred"}
    missing = required - columns
    if missing:
        raise RuntimeError(f"interaction_unified missing columns: {sorted(missing)}")

    sql = "SELECT pair_key, a_kind, a_id, b_kind, b_id, severity, effect, mechanism, evidence, confidence, is_inferred FROM interaction_unified ORDER BY pair_key"
    params: tuple[Any, ...] = ()
    if limit is not None:
        sql += " LIMIT ?"
        params = (limit,)
    rows = conn.execute(sql, params).fetchall()
    stats = {"findings": 0, "evidence": 0, "links": 0, "candidate_findings": 0, "synthetic_evidence": 0}
    now = _now()

    for row in rows:
        try:
            evidence_items = json.loads(row["evidence"] or "[]")
        except (TypeError, json.JSONDecodeError):
            evidence_items = []
        if not isinstance(evidence_items, list):
            evidence_items = []
        if not evidence_items:
            evidence_items = [{"source": "Unified legacy", "record_type": "row_without_evidence"}]
            stats["synthetic_evidence"] += 1

        evidence_refs: list[tuple[str, float, str]] = []
        evidence_levels: list[str] = []
        for index, item in enumerate(evidence_items):
            payload = item if isinstance(item, dict) else {"value": item}
            source_label = str(payload.get("source") or "Unified legacy")
            source_code = resolve_source_code(source_label)
            release_id, release_status = _release_for(conn, source_code)
            run_id = _ingestion_run(conn, source_code, release_id)
            payload_hash = normalized_payload_hash(payload)
            record_key = f"interaction_unified:{row['pair_key']}:{index}"
            eid = evidence_id(source_code, release_id, record_key, payload_hash)
            inferred = bool(row["is_inferred"]) or _source_level(source_label, False) == "inferred"
            level = _source_level(source_label, inferred)
            evidence_status = "candidate" if release_status != "accepted" else "accepted"
            trust = payload.get("trust")
            try:
                confidence = float(trust if trust is not None else row["confidence"])
            except (TypeError, ValueError):
                confidence = None
            if confidence is not None:
                confidence = max(0.0, min(1.0, confidence))
            severity = row["severity"] if row["severity"] in {"contraindicated", "major", "moderate", "minor"} else None
            conn.execute(
                "INSERT OR IGNORE INTO evidence_record "
                "(evidence_id, source_code, release_id, ingestion_run_id, record_key, "
                "evidence_type, evidence_level, status, statement, effect, mechanism, "
                "evidence_severity, evidence_confidence, source_record_id, doi, "
                "context_json, normalized_payload_sha256, parser_version, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    eid, source_code, release_id, run_id, record_key,
                    _finding_type(row["a_kind"], row["b_kind"]), level, evidence_status,
                    row["effect"], row["effect"], row["mechanism"], severity, confidence,
                    str(payload.get("recordId") or record_key), payload.get("doi"),
                    canonical_json({}), payload_hash, PARSER_VERSION, now,
                ),
            )
            _subjects(conn, eid, row)
            evidence_refs.append((eid, confidence or 0.0, evidence_status))
            evidence_levels.append(level)
            stats["evidence"] += 1

        pair = row["pair_key"]
        scope = scope_hash({})
        inferred = bool(row["is_inferred"])
        accepted_refs = [x for x in evidence_refs if x[2] == "accepted"]
        selected = max(evidence_refs, key=lambda x: x[1])[0]
        if inferred:
            level = "inferred"
        elif "regulatory" in evidence_levels:
            level = "regulatory"
        else:
            level = "unknown"
        status = "accepted" if accepted_refs else "candidate"
        evidence_status = "screening_signal" if inferred else ("supported_signal" if accepted_refs else "unknown")
        fid = finding_id(SCHEMA_VERSION, pair, _finding_type(row["a_kind"], row["b_kind"]), scope, POLICY_VERSION)
        conn.execute(
            "INSERT INTO canonical_finding "
            "(finding_id, pair_key, a_kind, a_id, b_kind, b_id, finding_type, status, "
            "evidence_status, evidence_level, evidence_severity, evidence_confidence, "
            "effect, mechanism, inferred, context_json, scope_hash, resolution_policy_version, "
            "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(finding_id) DO UPDATE SET "
            "pair_key=excluded.pair_key, a_kind=excluded.a_kind, a_id=excluded.a_id, "
            "b_kind=excluded.b_kind, b_id=excluded.b_id, finding_type=excluded.finding_type, "
            "status=excluded.status, evidence_status=excluded.evidence_status, "
            "evidence_level=excluded.evidence_level, evidence_severity=excluded.evidence_severity, "
            "evidence_confidence=excluded.evidence_confidence, effect=excluded.effect, "
            "mechanism=excluded.mechanism, inferred=excluded.inferred, "
            "context_json=excluded.context_json, scope_hash=excluded.scope_hash, "
            "resolution_policy_version=excluded.resolution_policy_version, "
            "last_seen=excluded.last_seen",
            (
                fid, pair, row["a_kind"], row["a_id"], row["b_kind"], row["b_id"],
                _finding_type(row["a_kind"], row["b_kind"]), status, evidence_status, level,
                row["severity"] if row["severity"] in {"contraindicated", "major", "moderate", "minor"} else "unknown",
                row["confidence"], row["effect"], row["mechanism"], int(inferred),
                canonical_json({}), scope, POLICY_VERSION, now, now,
            ),
        )
        # A changed unified row must replace, not accumulate, its selected
        # lineage. Evidence records remain immutable audit history.
        conn.execute("DELETE FROM finding_evidence WHERE finding_id = ?", (fid,))
        if status != "accepted":
            stats["candidate_findings"] += 1
        for eid, confidence, _ in evidence_refs:
            conn.execute(
                "INSERT OR IGNORE INTO finding_evidence "
                "(finding_id, evidence_id, role, source_confidence, selected) VALUES (?,?,?,?,?)",
                (fid, eid, "supporting", confidence, int(eid == selected)),
            )
            stats["links"] += 1
        stats["findings"] += 1
    conn.commit()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill canonical evidence from interaction_unified")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    from .db import get_conn

    conn = get_conn()
    try:
        print(json.dumps(backfill_unified(conn, args.limit), sort_keys=True))
    finally:
        conn.close()


if __name__ == "__main__":
    main()

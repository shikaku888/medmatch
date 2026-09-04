"""Reconcile legacy evidence source labels with canonical releases.

The first provenance backfill preserved source labels as conservative
``legacy_*`` codes when a release was not registered. This module resolves
those labels deterministically, registers only known releases, and promotes
findings only when source/license/release gates pass.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .evidence_schema import (
    SCHEMA_VERSION,
    canonical_json,
    ensure_schema,
    evidence_id,
    normalized_payload_hash,
    slug_source,
)
from .license_registry import KNOWN_LICENSES, seed_licenses

ALIAS_VERSION = "source-alias-v1"
RECONCILIATION_VERSION = "source-reconciliation-v1"
PARSER_VERSION = "source-reconciliation-v1"
POLICY_VERSION = "provenance-reconciliation-v1"
DATA_DIR = Path(__file__).parent / "data"

RECON_SCHEMA = """
CREATE TABLE IF NOT EXISTS source_alias (
    alias_pattern TEXT PRIMARY KEY,
    source_code TEXT NOT NULL,
    match_kind TEXT NOT NULL CHECK (match_kind IN ('exact', 'prefix', 'contains', 'regex')),
    priority INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_source_alias_lookup
    ON source_alias(active, priority, source_code);

CREATE TABLE IF NOT EXISTS source_reconciliation_run (
    reconciliation_run_id TEXT PRIMARY KEY,
    alias_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'accepted', 'failed')),
    records_seen INTEGER NOT NULL DEFAULT 0,
    records_reconciled INTEGER NOT NULL DEFAULT 0,
    records_unresolved INTEGER NOT NULL DEFAULT 0,
    findings_promoted INTEGER NOT NULL DEFAULT 0,
    findings_remaining_candidate INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS source_reconciliation_record (
    reconciliation_run_id TEXT NOT NULL,
    old_evidence_id TEXT NOT NULL,
    new_evidence_id TEXT,
    from_source_code TEXT NOT NULL,
    to_source_code TEXT,
    from_release_id TEXT NOT NULL,
    to_release_id TEXT,
    decision TEXT NOT NULL CHECK (decision IN ('reconciled', 'unresolved', 'no_change', 'superseded')),
    source_label TEXT,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (reconciliation_run_id, old_evidence_id),
    FOREIGN KEY (reconciliation_run_id) REFERENCES source_reconciliation_run(reconciliation_run_id)
);
CREATE INDEX IF NOT EXISTS idx_source_reconciliation_decision
    ON source_reconciliation_record(decision, to_source_code);
"""

# Exact labels in the tapirro dataset are source citations, not independent
# providers. They must remain attributable to the tapirro dataset release.
def _tapirro_source_labels() -> set[str]:
    path = DATA_DIR / "interactions.json"
    if not path.exists():
        return set()
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {str(row.get("source")).strip() for row in rows if row.get("source")}


TAPIRRO_SOURCE_LABELS = _tapirro_source_labels()

# Patterns are persisted for audit, while resolve_source_code keeps the
# source-specific precedence explicit and deterministic.
DEFAULT_ALIASES = (
    ("https://doi.org/10.5281/zenodo.19685458", "zenodo_ddi_2026", "exact", 1000),
    ("supp.ai", "suppai", "contains", 900),
    ("suppai", "suppai", "contains", 890),
    ("dailymed:", "dailymed", "prefix", 880),
    ("openfda", "openfda", "contains", 870),
    ("cyp450 inference", "cyp_inference", "exact", 860),
    ("chembl", "chembl", "contains", 850),
    ("mskcc", "idisk", "contains", 840),
    ("fda curated", "fda_curated", "prefix", 830),
)

SOURCE_RELEASES = {
    "tapirro": {
        "dataset_name": "tapirro herb-drug-interaction-checker",
        "version": "seed-v1",
        "source_url": "https://github.com/tapirro/herb-drug-interaction-checker",
        "terms_url": "https://github.com/tapirro/herb-drug-interaction-checker",
        "licence_name": "MIT",
        "commercial_status": "core_open",
        "parser_version": "db.seed.v1",
        "release_status": "accepted",
        "notes": "Translated local seed; source citations remain in source_locator.",
    },
    "fda_curated": {
        "dataset_name": "MedMatch curated FDA labeling facts",
        "version": "seed-v1",
        "source_url": "https://open.fda.gov/",
        "terms_url": "https://open.fda.gov/license/",
        "licence_name": "Public-domain FDA labeling facts, MedMatch curated",
        "commercial_status": "core_open",
        "parser_version": "drug-seeds-v1",
        "release_status": "accepted",
        "notes": "Derived curated rules; not a raw FDA bulk mirror.",
    },
    "dailymed": {
        "dataset_name": "DailyMed SPL API drug interaction sections",
        "version": "api",
        "source_url": "https://dailymed.nlm.nih.gov/dailymed/services/v2",
        "terms_url": "https://dailymed.nlm.nih.gov/dailymed/disclaimer.cfm",
        "licence_name": "Public Domain / CC0",
        "commercial_status": "core_open",
        "parser_version": "dailymed.run",
        "release_status": "accepted",
        "notes": "Release registration reconciled from the existing DailyMed importer.",
    },
    "cyp_inference": {
        "dataset_name": "MedMatch CYP450 derived inference",
        "version": "algorithm-v1",
        "source_url": None,
        "terms_url": None,
        "licence_name": "MedMatch derived output; upstream sources separately attributed",
        "commercial_status": "derived_internal",
        "parser_version": "unify.py:cyp-inference-v1",
        "release_status": "accepted",
        "notes": "Derived findings remain screening_signal and link to upstream roles.",
    },
    "cyp_roles": {
        "dataset_name": "MedMatch CYP role catalog",
        "version": "runtime-v1",
        "source_url": None,
        "terms_url": None,
        "licence_name": "MedMatch derived output; upstream sources separately attributed",
        "commercial_status": "derived_internal",
        "parser_version": "cyp-roles-v1",
        "release_status": "accepted",
        "notes": "Runtime role catalog used as upstream lineage for CYP inference.",
    },
    "idisk": {
        "dataset_name": "iDISK/MSKCC legacy interaction evidence",
        "version": "legacy-unknown",
        "source_url": None,
        "terms_url": "https://www.mskcc.org/",
        "licence_name": "Commercial reuse requires terms verification",
        "commercial_status": "restricted_private",
        "parser_version": PARSER_VERSION,
        "release_status": "candidate",
        "notes": "Not promoted until commercial reuse and redistribution terms are verified.",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()




def _release_id(source_code: str, version: str) -> str:
    return f"{source_code}:{version}"


def ensure_reconciliation_schema(conn: sqlite3.Connection) -> None:
    ensure_schema(conn)
    conn.executescript(RECON_SCHEMA)
    seed_licenses(conn)
    for pattern, source_code, match_kind, priority in DEFAULT_ALIASES:
        conn.execute(
            "INSERT OR REPLACE INTO source_alias "
            "(alias_pattern, source_code, match_kind, priority, notes) VALUES (?,?,?,?,?)",
            (pattern, source_code, match_kind, priority, "Canonical alias rule " + ALIAS_VERSION),
        )
    for source_code, release in SOURCE_RELEASES.items():
        conn.execute(
            "INSERT OR IGNORE INTO dataset_release "
            "(source_code, dataset_name, version, source_url, terms_url, licence_name, "
            "commercial_status, downloaded_at, parser_version, notes, release_status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                source_code,
                release["dataset_name"],
                release["version"],
                release["source_url"],
                release["terms_url"],
                release["licence_name"],
                release["commercial_status"],
                _now(),
                release["parser_version"],
                release["notes"],
                release["release_status"],
            ),
        )
    conn.commit()


def resolve_source_code(source_label: str) -> str:
    """Resolve a source label without treating arbitrary citations as providers."""
    label = " ".join(str(source_label or "").split()).strip()
    lowered = label.casefold()
    if label in TAPIRRO_SOURCE_LABELS:
        return "tapirro"
    if lowered == "https://doi.org/10.5281/zenodo.19685458":
        return "zenodo_ddi_2026"
    if "supp.ai" in lowered or lowered.startswith("suppai"):
        return "suppai"
    if lowered.startswith("dailymed:"):
        return "dailymed"
    if lowered.startswith("openfda"):
        return "openfda"
    if lowered == "cyp450 inference":
        return "cyp_inference"
    if "chembl" in lowered:
        return "chembl"
    if "mskcc" in lowered:
        return "idisk"
    if lowered.startswith("fda ") or lowered.startswith("public knowledge; fda"):
        return "fda_curated"
    if not label or lowered == "unified legacy":
        return "legacy_unknown"
    return slug_source(label)


def _source_label_index(conn: sqlite3.Connection) -> dict[str, str]:
    """Recover original source labels from the backfill record key."""
    out: dict[str, str] = {}
    for row in conn.execute("SELECT pair_key, evidence FROM interaction_unified"):
        try:
            values = json.loads(row["evidence"] or "[]")
        except (TypeError, json.JSONDecodeError):
            values = []
        if not isinstance(values, list):
            continue
        for index, value in enumerate(values):
            label = value.get("source") if isinstance(value, dict) else None
            out[f"interaction_unified:{row['pair_key']}:{index}"] = str(label or "Unified legacy")
    return out


def _accepted_release(conn: sqlite3.Connection, source_code: str) -> tuple[str, str] | None:
    row = conn.execute(
        "SELECT version, release_status FROM dataset_release "
        "WHERE source_code = ? AND release_status = 'accepted' "
        "ORDER BY downloaded_at DESC LIMIT 1",
        (source_code,),
    ).fetchone()
    if not row or not row[0]:
        return None
    return _release_id(source_code, row[0]), row[1]


def _ensure_source_license(conn: sqlite3.Connection, source_code: str) -> None:
    if conn.execute(
        "SELECT 1 FROM source_license WHERE source_code = ?", (source_code,)
    ).fetchone():
        return
    conn.execute(
        "INSERT OR IGNORE INTO source_license "
        "(source_code, licence_name, commercial_use_allowed, redistribution_allowed, "
        "modification_allowed, attribution_required, non_commercial_only, "
        "raw_redistribution_allowed, review_notes) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            source_code,
            "Unresolved legacy source; license not verified",
            0, 0, 0, 1, 1, 0,
            "Created by source reconciliation; legal/source manifest required.",
        ),
    )


def _license_is_eligible(conn: sqlite3.Connection, source_code: str) -> bool:
    row = conn.execute(
        "SELECT commercial_use_allowed, derived_use_allowed, legal_review_status "
        "FROM source_license WHERE source_code = ?",
        (source_code,),
    ).fetchone()
    if not row:
        return False
    return bool(row[0] or row[1]) and row[2] not in {"rejected", "restricted"}


def _reconciliation_run(conn: sqlite3.Connection, run_id: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO source_reconciliation_run "
        "(reconciliation_run_id, alias_version, policy_version, started_at, status) "
        "VALUES (?,?,?,?,?)",
        (run_id, ALIAS_VERSION, POLICY_VERSION, _now(), "running"),
    )


def _source_run(conn: sqlite3.Connection, source_code: str, release_id: str, accepted: bool) -> str:
    run_id = f"reconcile:{source_code}:{release_id.split(':', 1)[1]}:{RECONCILIATION_VERSION}"
    conn.execute(
        "INSERT OR IGNORE INTO ingestion_run "
        "(ingestion_run_id, source_code, release_id, parser_version, contract_version, "
        "started_at, completed_at, status, notes) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            run_id, source_code, release_id, PARSER_VERSION, SCHEMA_VERSION,
            _now(), _now(), "accepted" if accepted else "failed",
            "Source/release reconciliation; no new source payload fetched.",
        ),
    )
    return run_id


def _evidence_level(source_label: str, source_code: str, current: str) -> str:
    if source_code == "cyp_inference":
        return "inferred"
    if source_code in {"dailymed", "openfda", "fda_curated"}:
        return "regulatory"
    if source_code == "chembl":
        return "mechanistic"
    return current if current in {
        "regulatory", "clinical_guideline", "clinical_study", "observational",
        "case_report", "pharmacovigilance", "mechanistic", "inferred",
        "reference_only", "unknown",
    } else "unknown"


def _copy_subjects(conn: sqlite3.Connection, old_id: str, new_id: str) -> None:
    rows = conn.execute(
        "SELECT ordinal, entity_kind, entity_id, raw_name, mapping_method, "
        "mapping_confidence, mapping_status, external_ids_json "
        "FROM evidence_record_subject WHERE evidence_id = ? ORDER BY ordinal",
        (old_id,),
    ).fetchall()
    for row in rows:
        conn.execute(
            "INSERT OR IGNORE INTO evidence_record_subject "
            "(evidence_id, ordinal, entity_kind, entity_id, raw_name, mapping_method, "
            "mapping_confidence, mapping_status, external_ids_json) VALUES (?,?,?,?,?,?,?,?,?)",
            (new_id, *tuple(row)),
        )


def _copy_links(conn: sqlite3.Connection, old_id: str, new_id: str) -> None:
    rows = conn.execute(
        "SELECT finding_id, role, source_severity, source_confidence FROM finding_evidence "
        "WHERE evidence_id = ?",
        (old_id,),
    ).fetchall()
    for row in rows:
        conn.execute(
            "INSERT OR IGNORE INTO finding_evidence "
            "(finding_id, evidence_id, role, source_severity, source_confidence, selected) "
            "VALUES (?,?,?,?,?,0)",
            (row["finding_id"], new_id, row["role"], row["source_severity"], row["source_confidence"]),
        )


def _record_source(conn: sqlite3.Connection, row: sqlite3.Row, labels: dict[str, str]) -> str:
    label = labels.get(row["record_key"])
    if label:
        return label
    return row["source_code"]

def _ensure_cyp_role_lineage(conn: sqlite3.Connection, now: str) -> dict[str, int]:
    table_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cyp_roles'"
    ).fetchone()
    if not table_exists:
        return {"role_records": 0, "derivations": 0, "unresolved_derivations": 0}

    release_id = "cyp_roles:runtime-v1"
    run_id = _source_run(conn, "cyp_roles", release_id, True)
    roles = conn.execute(
        "SELECT entity_type, entity_id, role, enzyme FROM cyp_roles "
        "ORDER BY entity_type, entity_id, role, enzyme"
    ).fetchall()
    by_entity: dict[tuple[str, str], list[str]] = {}
    for role in roles:
        payload = {
            "entity_type": role["entity_type"],
            "entity_id": role["entity_id"],
            "role": role["role"],
            "enzyme": role["enzyme"],
        }
        record_key = (
            f"cyp_role:{role['entity_type']}:{role['entity_id']}:"
            f"{role['role']}:{role['enzyme']}"
        )
        payload_hash = normalized_payload_hash(payload)
        upstream_id = evidence_id("cyp_roles", release_id, record_key, payload_hash)
        conn.execute(
            "INSERT OR IGNORE INTO evidence_record "
            "(evidence_id, source_code, release_id, ingestion_run_id, record_key, "
            "evidence_type, evidence_level, status, statement, evidence_confidence, "
            "source_record_id, source_locator, context_json, normalized_payload_sha256, "
            "parser_version, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                upstream_id, "cyp_roles", release_id, run_id, record_key, "mechanism",
                "mechanistic", "accepted",
                f"{role['entity_type']} {role['entity_id']} has {role['role']} role for CYP {role['enzyme']}.",
                0.8, record_key, record_key, canonical_json(payload), payload_hash,
                "cyp-roles-v1", now,
            ),
        )
        conn.execute(
            "INSERT OR IGNORE INTO evidence_record_subject "
            "(evidence_id, ordinal, entity_kind, entity_id, raw_name, mapping_method, "
            "mapping_confidence, mapping_status) VALUES (?,?,?,?,?,?,?,?)",
            (
                upstream_id, 0, role["entity_type"], role["entity_id"], role["entity_id"],
                "cyp-role-catalog", 1.0, "accepted",
            ),
        )
        conn.execute(
            "INSERT OR IGNORE INTO evidence_record_subject "
            "(evidence_id, ordinal, entity_kind, entity_id, raw_name, mapping_method, "
            "mapping_confidence, mapping_status) VALUES (?,?,?,?,?,?,?,?)",
            (
                upstream_id, 1, "chemical", role["enzyme"], role["enzyme"],
                "cyp-role-catalog", 1.0, "accepted",
            ),
        )
        by_entity.setdefault((role["entity_type"], role["entity_id"]), []).append(upstream_id)

    derivations = 0
    unresolved = 0
    cyp_rows = conn.execute(
        "SELECT evidence_id, record_key FROM evidence_record "
        "WHERE source_code='cyp_inference' AND status='accepted'"
    ).fetchall()
    for row in cyp_rows:
        pair = row["record_key"].removeprefix("interaction_unified:").rsplit(":", 1)[0]
        upstream_ids: list[str] = []
        for endpoint in pair.split("|"):
            if ":" not in endpoint:
                continue
            kind, entity_id = endpoint.split(":", 1)
            upstream_ids.extend(by_entity.get((kind, entity_id), ()))
        upstream_ids = sorted(set(upstream_ids))
        if not upstream_ids:
            conn.execute(
                "UPDATE evidence_record SET status='candidate' WHERE evidence_id=?",
                (row["evidence_id"],),
            )
            unresolved += 1
            continue
        for upstream_id in upstream_ids:
            before = conn.total_changes
            conn.execute(
                "INSERT OR IGNORE INTO evidence_derivation "
                "(derived_evidence_id, upstream_evidence_id, operation, operation_version) "
                "VALUES (?,?,?,?)",
                (row["evidence_id"], upstream_id, "cyp-pathway-overlap", "cyp-derivation-v1"),
            )
            derivations += int(conn.total_changes > before)
    return {
        "role_records": len(roles),
        "derivations": derivations,
        "unresolved_derivations": unresolved,
    }



def reconcile_evidence(conn: sqlite3.Connection, limit: int | None = None) -> dict[str, int]:
    ensure_reconciliation_schema(conn)
    run_id = f"reconcile-run:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    _reconciliation_run(conn, run_id)
    labels = _source_label_index(conn)
    sql = (
        "SELECT * FROM evidence_record WHERE record_key LIKE 'interaction_unified:%' "
        "AND status <> 'superseded' ORDER BY evidence_id"
    )
    params: tuple[Any, ...] = ()
    if limit is not None:
        sql += " LIMIT ?"
        params = (limit,)
    rows = conn.execute(sql, params).fetchall()
    now = _now()
    source_license_cache = {
        item[0] for item in conn.execute("SELECT source_code FROM source_license")
    }
    release_cache: dict[str, tuple[str, str] | None] = {}
    run_cache: dict[tuple[str, str, bool], str] = {}
    candidate_sources: set[str] = set()
    map_rows: list[tuple[Any, ...]] = []
    stats = {"seen": len(rows), "reconciled": 0, "unresolved": 0, "no_change": 0}

    for row in rows:
        source_label = _record_source(conn, row, labels)
        target_source = resolve_source_code(source_label)
        if target_source not in source_license_cache:
            _ensure_source_license(conn, target_source)
            source_license_cache.add(target_source)
        if target_source not in release_cache:
            release_cache[target_source] = _accepted_release(conn, target_source)
        release = release_cache[target_source]
        eligible = bool(release and _license_is_eligible(conn, target_source))
        if not release:
            version = "legacy-unknown"
            release_id = _release_id(target_source, version)
            if target_source not in candidate_sources:
                conn.execute(
                    "INSERT OR IGNORE INTO dataset_release "
                    "(source_code, dataset_name, version, licence_name, commercial_status, "
                    "downloaded_at, parser_version, notes, release_status) VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        target_source, f"Unresolved legacy source ({target_source})", version,
                        (KNOWN_LICENSES.get(target_source) or {}).get("label"),
                        "restricted_private", now, PARSER_VERSION,
                        "Candidate release; source/license reconciliation required.", "candidate",
                    ),
                )
                candidate_sources.add(target_source)
            release = (release_id, "candidate")
            release_cache[target_source] = release
        release_id, release_status = release
        accepted = eligible and release_status == "accepted"
        run_key = (target_source, release_id, accepted)
        run_for_source = run_cache.get(run_key)
        if run_for_source is None:
            run_for_source = _source_run(conn, target_source, release_id, accepted)
            run_cache[run_key] = run_for_source
        new_level = _evidence_level(source_label, target_source, row["evidence_level"])
        new_status = "accepted" if accepted else "candidate"
        new_id = evidence_id(
            target_source, release_id, row["record_key"], row["normalized_payload_sha256"]
        )
        changed = (
            new_id != row["evidence_id"]
            or row["status"] != new_status
            or row["evidence_level"] != new_level
        )
        if changed:
            stats["reconciled"] += 1
            decision = "reconciled" if accepted else "superseded"
        else:
            stats["no_change"] += 1
            decision = "no_change" if accepted else "unresolved"
        if not accepted:
            stats["unresolved"] += 1
        map_rows.append(
            (
                row["evidence_id"], new_id, row["source_code"], target_source,
                row["release_id"], release_id, run_for_source, new_level,
                new_status, source_label, decision,
                "accepted release and eligible license" if accepted
                else "release/license gate unresolved",
            )
        )

    conn.execute("DROP TABLE IF EXISTS temp._source_reconcile_map")
    conn.execute(
        "CREATE TEMP TABLE _source_reconcile_map ("
        "old_evidence_id TEXT PRIMARY KEY, new_evidence_id TEXT NOT NULL, "
        "from_source_code TEXT NOT NULL, to_source_code TEXT NOT NULL, "
        "from_release_id TEXT NOT NULL, to_release_id TEXT NOT NULL, "
        "ingestion_run_id TEXT NOT NULL, new_level TEXT NOT NULL, "
        "new_status TEXT NOT NULL, source_label TEXT, decision TEXT NOT NULL, reason TEXT NOT NULL)"
    )
    conn.executemany(
        "INSERT INTO _source_reconcile_map VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        map_rows,
    )
    conn.execute(
        "INSERT OR IGNORE INTO evidence_record "
        "(evidence_id, source_code, release_id, ingestion_run_id, record_key, evidence_type, "
        "evidence_level, status, title, statement, effect, mechanism, evidence_severity, "
        "evidence_confidence, published_at, valid_from, valid_until, source_record_id, "
        "source_url, source_locator, doi, pmid, quote_text, context_json, raw_payload_sha256, "
        "normalized_payload_sha256, parser_version, created_at) "
        "SELECT m.new_evidence_id, m.to_source_code, m.to_release_id, m.ingestion_run_id, "
        "e.record_key, e.evidence_type, m.new_level, m.new_status, e.title, e.statement, "
        "e.effect, e.mechanism, e.evidence_severity, e.evidence_confidence, e.published_at, "
        "e.valid_from, e.valid_until, e.source_record_id, e.source_url, "
        "COALESCE(e.source_locator, m.source_label), e.doi, e.pmid, e.quote_text, "
        "e.context_json, e.raw_payload_sha256, e.normalized_payload_sha256, "
        "e.parser_version, e.created_at "
        "FROM _source_reconcile_map m JOIN evidence_record e "
        "ON e.evidence_id=m.old_evidence_id"
    )
    conn.execute(
        "UPDATE evidence_record SET status = (SELECT m.new_status FROM _source_reconcile_map m "
        "WHERE m.old_evidence_id=evidence_record.evidence_id), evidence_level = "
        "(SELECT m.new_level FROM _source_reconcile_map m "
        "WHERE m.old_evidence_id=evidence_record.evidence_id) "
        "WHERE evidence_id IN (SELECT old_evidence_id FROM _source_reconcile_map "
        "WHERE old_evidence_id=new_evidence_id)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO evidence_record_subject "
        "(evidence_id, ordinal, entity_kind, entity_id, raw_name, mapping_method, "
        "mapping_confidence, mapping_status, external_ids_json) "
        "SELECT m.new_evidence_id, s.ordinal, s.entity_kind, s.entity_id, s.raw_name, "
        "s.mapping_method, s.mapping_confidence, s.mapping_status, s.external_ids_json "
        "FROM _source_reconcile_map m JOIN evidence_record_subject s "
        "ON s.evidence_id=m.old_evidence_id"
    )
    conn.execute(
        "INSERT OR IGNORE INTO finding_evidence "
        "(finding_id, evidence_id, role, source_severity, source_confidence, selected) "
        "SELECT fe.finding_id, m.new_evidence_id, fe.role, fe.source_severity, "
        "fe.source_confidence, 0 FROM _source_reconcile_map m "
        "JOIN finding_evidence fe ON fe.evidence_id=m.old_evidence_id"
    )
    affected_findings = {
        item[0] for item in conn.execute(
            "SELECT DISTINCT finding_id FROM finding_evidence fe "
            "JOIN _source_reconcile_map m ON fe.evidence_id IN "
            "(m.old_evidence_id, m.new_evidence_id)"
        )
    }
    conn.execute(
        "UPDATE evidence_record SET status='superseded' "
        "WHERE evidence_id IN (SELECT old_evidence_id FROM _source_reconcile_map "
        "WHERE old_evidence_id <> new_evidence_id)"
    )
    conn.execute(
        "INSERT OR REPLACE INTO source_reconciliation_record "
        "(reconciliation_run_id, old_evidence_id, new_evidence_id, from_source_code, "
        "to_source_code, from_release_id, to_release_id, decision, source_label, reason, created_at) "
        "SELECT ?, old_evidence_id, new_evidence_id, from_source_code, to_source_code, "
        "from_release_id, to_release_id, decision, source_label, reason, ? "
        "FROM _source_reconcile_map",
        (run_id, now),
    )
    conn.execute("DROP TABLE temp._source_reconcile_map")
    derivation_stats = _ensure_cyp_role_lineage(conn, now)

    promoted, remaining = _reselect_findings(conn, affected_findings)
    conn.execute(
        "UPDATE source_reconciliation_run SET completed_at=?, status='accepted', records_seen=?, "
        "records_reconciled=?, records_unresolved=?, findings_promoted=?, "
        "findings_remaining_candidate=? WHERE reconciliation_run_id=?",
        (now, stats["seen"], stats["reconciled"], stats["unresolved"],
         promoted, remaining, run_id),
    )
    conn.commit()
    return {
        **stats,
        **derivation_stats,
        "findings_promoted": promoted,
        "findings_remaining_candidate": remaining,
    }
def _reselect_findings(conn: sqlite3.Connection, only: set[str] | None) -> tuple[int, int]:
    if only is not None and not only:
        return 0, 0
    if only is None or len(only) > 900:
        finding_rows = conn.execute(
            "SELECT finding_id, inferred FROM canonical_finding"
        ).fetchall()
        finding_ids = None
    else:
        values = sorted(only)
        placeholders = ",".join("?" for _ in values)
        finding_rows = conn.execute(
            f"SELECT finding_id, inferred FROM canonical_finding "
            f"WHERE finding_id IN ({placeholders})",
            values,
        ).fetchall()
        finding_ids = values

    level_rank = {
        "regulatory": 7, "clinical_guideline": 6, "clinical_study": 5,
        "observational": 4, "case_report": 3, "pharmacovigilance": 3,
        "mechanistic": 2, "inferred": 1, "unknown": 0,
    }
    eligible_sql = (
        "SELECT fe.finding_id, fe.evidence_id, er.evidence_level, er.evidence_confidence "
        "FROM finding_evidence fe JOIN evidence_record er ON er.evidence_id=fe.evidence_id "
        "LEFT JOIN source_license sl ON sl.source_code=er.source_code "
        "LEFT JOIN dataset_release dr ON dr.source_code=er.source_code "
        "AND dr.version=substr(er.release_id, length(er.source_code)+2) "
        "WHERE fe.role='supporting' AND er.status='accepted' "
        "AND dr.release_status='accepted' "
        "AND (sl.commercial_use_allowed=1 OR sl.derived_use_allowed=1) "
        "AND EXISTS (SELECT 1 FROM evidence_record_subject ers "
        "WHERE ers.evidence_id=er.evidence_id) "
        "AND NOT EXISTS (SELECT 1 FROM evidence_record_subject ers "
        "WHERE ers.evidence_id=er.evidence_id AND ers.mapping_status <> 'accepted') "
        "AND (er.evidence_level <> 'inferred' OR EXISTS ("
        "SELECT 1 FROM evidence_derivation ed "
        "WHERE ed.derived_evidence_id=er.evidence_id))"
    )
    eligible_params: list[str] = []
    if finding_ids is not None:
        placeholders = ",".join("?" for _ in finding_ids)
        eligible_sql += f" AND fe.finding_id IN ({placeholders})"
        eligible_params = finding_ids
    candidates_by_finding: dict[str, list[sqlite3.Row]] = {}
    for row in conn.execute(eligible_sql, eligible_params).fetchall():
        candidates_by_finding.setdefault(row["finding_id"], []).append(row)

    reselection_rows: list[tuple[Any, ...]] = []
    promoted = 0
    remaining = 0
    for item in finding_rows:
        fid = item["finding_id"]
        candidates = candidates_by_finding.get(fid, [])
        if not candidates:
            reselection_rows.append((fid, None, "candidate", "unknown", "unknown", None))
            remaining += 1
            continue
        best = max(
            candidates,
            key=lambda row: (
                level_rank.get(row["evidence_level"], 0),
                row["evidence_confidence"] or 0.0,
            ),
        )
        if bool(item["inferred"]) or best["evidence_level"] == "inferred":
            evidence_status, evidence_level = "screening_signal", "inferred"
        elif best["evidence_level"] == "regulatory":
            evidence_status, evidence_level = "documented", "regulatory"
        else:
            evidence_status, evidence_level = "supported_signal", best["evidence_level"]
        reselection_rows.append(
            (fid, best["evidence_id"], "accepted", evidence_status,
             evidence_level, best["evidence_confidence"])
        )
        promoted += 1

    conn.execute("DROP TABLE IF EXISTS temp._finding_reselection")
    conn.execute(
        "CREATE TEMP TABLE _finding_reselection ("
        "finding_id TEXT PRIMARY KEY, best_evidence_id TEXT, status TEXT NOT NULL, "
        "evidence_status TEXT NOT NULL, evidence_level TEXT NOT NULL, evidence_confidence REAL)"
    )
    conn.executemany(
        "INSERT INTO _finding_reselection VALUES (?,?,?,?,?,?)",
        reselection_rows,
    )
    if finding_ids is None:
        conn.execute(
            "UPDATE finding_evidence SET selected = CASE WHEN EXISTS "
            "(SELECT 1 FROM _finding_reselection r WHERE "
            "r.finding_id=finding_evidence.finding_id AND "
            "r.best_evidence_id=finding_evidence.evidence_id) THEN 1 ELSE 0 END "
            "WHERE role='supporting'"
        )
    else:
        placeholders = ",".join("?" for _ in finding_ids)
        conn.execute(
            f"UPDATE finding_evidence SET selected = CASE WHEN EXISTS "
            f"(SELECT 1 FROM _finding_reselection r WHERE "
            f"r.finding_id=finding_evidence.finding_id AND "
            f"r.best_evidence_id=finding_evidence.evidence_id) THEN 1 ELSE 0 END "
            f"WHERE role='supporting' AND finding_id IN ({placeholders})",
            finding_ids,
        )
    conn.execute(
        "UPDATE canonical_finding SET status=(SELECT status FROM _finding_reselection r "
        "WHERE r.finding_id=canonical_finding.finding_id), "
        "evidence_status=(SELECT evidence_status FROM _finding_reselection r "
        "WHERE r.finding_id=canonical_finding.finding_id), "
        "evidence_level=(SELECT evidence_level FROM _finding_reselection r "
        "WHERE r.finding_id=canonical_finding.finding_id), "
        "evidence_confidence=(SELECT evidence_confidence FROM _finding_reselection r "
        "WHERE r.finding_id=canonical_finding.finding_id) "
        "WHERE finding_id IN (SELECT finding_id FROM _finding_reselection)"
    )
    conn.execute("DROP TABLE temp._finding_reselection")
    return promoted, remaining


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile canonical evidence sources and releases")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    from .db import get_conn

    conn = get_conn()
    try:
        print(json.dumps(reconcile_evidence(conn, args.limit), sort_keys=True))
    finally:
        conn.close()


if __name__ == "__main__":
    main()

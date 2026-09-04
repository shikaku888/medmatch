"""Canonical evidence/provenance schema and deterministic identity helpers.

Phase 1 is additive: source-specific tables remain staging/read models while
these tables provide the shared contract for evidence, findings, and lineage.
No source payload is silently promoted to an accepted commercial finding.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = "medmatch.evidence.v1"

EVIDENCE_LEVELS = {
    "regulatory", "clinical_guideline", "clinical_study", "observational",
    "case_report", "pharmacovigilance", "mechanistic", "inferred",
    "reference_only", "unknown",
}
EVIDENCE_STATUSES = {"documented", "supported_signal", "screening_signal", "unknown"}
SEVERITIES = {"contraindicated", "major", "moderate", "minor", "unknown", "not_applicable"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS ingestion_run (
    ingestion_run_id TEXT PRIMARY KEY,
    source_code TEXT NOT NULL,
    release_id TEXT,
    parser_version TEXT NOT NULL,
    contract_version TEXT NOT NULL DEFAULT 'medmatch.evidence.v1',
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'accepted', 'failed', 'rolled_back')),
    input_sha256 TEXT,
    schema_hash TEXT,
    rows_seen INTEGER NOT NULL DEFAULT 0,
    rows_accepted INTEGER NOT NULL DEFAULT 0,
    rows_rejected INTEGER NOT NULL DEFAULT 0,
    rows_changed INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    error_summary TEXT,
    artifact_ref TEXT,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_ingestion_source_status
    ON ingestion_run(source_code, status, started_at);

CREATE TABLE IF NOT EXISTS evidence_artifact (
    artifact_id TEXT PRIMARY KEY,
    ingestion_run_id TEXT NOT NULL,
    uri TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER,
    content_type TEXT,
    encrypted INTEGER NOT NULL DEFAULT 1,
    retention_class TEXT NOT NULL DEFAULT 'release',
    raw_access_allowed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (ingestion_run_id) REFERENCES ingestion_run(ingestion_run_id),
    UNIQUE(ingestion_run_id, sha256)
);

CREATE TABLE IF NOT EXISTS evidence_record (
    evidence_id TEXT PRIMARY KEY,
    source_code TEXT NOT NULL,
    release_id TEXT NOT NULL,
    ingestion_run_id TEXT NOT NULL,
    record_key TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    evidence_level TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'accepted',
    title TEXT,
    statement TEXT,
    effect TEXT,
    mechanism TEXT,
    evidence_severity TEXT,
    evidence_confidence REAL,
    published_at TEXT,
    valid_from TEXT,
    valid_until TEXT,
    source_record_id TEXT,
    source_url TEXT,
    source_locator TEXT,
    doi TEXT,
    pmid TEXT,
    quote_text TEXT,
    context_json TEXT NOT NULL DEFAULT '{}',
    raw_payload_sha256 TEXT,
    normalized_payload_sha256 TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (ingestion_run_id) REFERENCES ingestion_run(ingestion_run_id),
    UNIQUE(source_code, release_id, record_key, normalized_payload_sha256),
    CHECK (evidence_confidence IS NULL OR
           (evidence_confidence >= 0 AND evidence_confidence <= 1)),
    CHECK (evidence_severity IS NULL OR evidence_severity IN
           ('contraindicated', 'major', 'moderate', 'minor', 'unknown', 'not_applicable'))
);
CREATE INDEX IF NOT EXISTS idx_evidence_record_source_record
    ON evidence_record(source_code, source_record_id);
CREATE INDEX IF NOT EXISTS idx_evidence_record_type_level
    ON evidence_record(evidence_type, evidence_level, status);

CREATE TABLE IF NOT EXISTS evidence_record_subject (
    evidence_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    entity_kind TEXT NOT NULL,
    entity_id TEXT,
    raw_name TEXT NOT NULL,
    mapping_method TEXT NOT NULL,
    mapping_confidence REAL,
    mapping_status TEXT NOT NULL DEFAULT 'accepted',
    external_ids_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (evidence_id, ordinal),
    FOREIGN KEY (evidence_id) REFERENCES evidence_record(evidence_id),
    CHECK (mapping_confidence IS NULL OR
           (mapping_confidence >= 0 AND mapping_confidence <= 1)),
    CHECK (mapping_status IN ('candidate', 'accepted', 'rejected', 'unknown'))
);
CREATE INDEX IF NOT EXISTS idx_evidence_subject_entity
    ON evidence_record_subject(entity_kind, entity_id, mapping_status);

CREATE TABLE IF NOT EXISTS canonical_finding (
    finding_id TEXT PRIMARY KEY,
    pair_key TEXT NOT NULL,
    a_kind TEXT NOT NULL,
    a_id TEXT NOT NULL,
    b_kind TEXT NOT NULL,
    b_id TEXT NOT NULL,
    finding_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'accepted',
    evidence_status TEXT NOT NULL,
    evidence_level TEXT NOT NULL,
    evidence_severity TEXT NOT NULL DEFAULT 'unknown',
    evidence_confidence REAL,
    effect TEXT,
    mechanism TEXT,
    action TEXT,
    inferred INTEGER NOT NULL DEFAULT 0,
    context_json TEXT NOT NULL DEFAULT '{}',
    scope_hash TEXT NOT NULL,
    resolution_policy_version TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    CHECK (evidence_status IN ('documented', 'supported_signal', 'screening_signal', 'unknown')),
    CHECK (evidence_level IN
           ('regulatory', 'clinical_guideline', 'clinical_study', 'observational',
            'case_report', 'pharmacovigilance', 'mechanistic', 'inferred',
            'reference_only', 'unknown')),
    CHECK (evidence_severity IN
           ('contraindicated', 'major', 'moderate', 'minor', 'unknown', 'not_applicable')),
    CHECK (evidence_confidence IS NULL OR
           (evidence_confidence >= 0 AND evidence_confidence <= 1)),
    UNIQUE(pair_key, finding_type, scope_hash, resolution_policy_version)
);
CREATE INDEX IF NOT EXISTS idx_canonical_finding_pair
    ON canonical_finding(a_kind, a_id, b_kind, b_id, status);
CREATE INDEX IF NOT EXISTS idx_canonical_finding_level
    ON canonical_finding(evidence_level, evidence_severity, status);

CREATE TABLE IF NOT EXISTS finding_evidence (
    finding_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    role TEXT NOT NULL,
    source_severity TEXT,
    source_confidence REAL,
    selected INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    PRIMARY KEY (finding_id, evidence_id),
    FOREIGN KEY (finding_id) REFERENCES canonical_finding(finding_id),
    FOREIGN KEY (evidence_id) REFERENCES evidence_record(evidence_id),
    CHECK (role IN ('supporting', 'contradicting', 'context', 'derivation')),
    CHECK (source_confidence IS NULL OR
           (source_confidence >= 0 AND source_confidence <= 1))
);
CREATE INDEX IF NOT EXISTS idx_finding_evidence_selected
    ON finding_evidence(finding_id, selected, role);

CREATE TABLE IF NOT EXISTS evidence_derivation (
    derived_evidence_id TEXT NOT NULL,
    upstream_evidence_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    operation_version TEXT NOT NULL,
    PRIMARY KEY (derived_evidence_id, upstream_evidence_id, operation),
    FOREIGN KEY (derived_evidence_id) REFERENCES evidence_record(evidence_id),
    FOREIGN KEY (upstream_evidence_id) REFERENCES evidence_record(evidence_id)
);

CREATE TABLE IF NOT EXISTS finding_conflict (
    conflict_id TEXT PRIMARY KEY,
    finding_id TEXT NOT NULL,
    dimension TEXT NOT NULL,
    source_values_json TEXT NOT NULL,
    selected_value TEXT,
    resolution TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    reviewer_status TEXT NOT NULL DEFAULT 'system_resolved',
    created_at TEXT NOT NULL,
    FOREIGN KEY (finding_id) REFERENCES canonical_finding(finding_id),
    CHECK (dimension IN ('severity', 'effect', 'mechanism', 'action', 'mapping', 'scope')),
    CHECK (reviewer_status IN ('system_resolved', 'needs_review', 'reviewed'))
);
CREATE INDEX IF NOT EXISTS idx_finding_conflict_review
    ON finding_conflict(reviewer_status, created_at);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(*parts: Any) -> str:
    payload = "\x1f".join(canonical_json(p) if not isinstance(p, str) else p for p in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def pair_key(a_kind: str, a_id: str, b_kind: str, b_id: str) -> str:
    return "|".join(sorted((f"{a_kind}:{a_id}", f"{b_kind}:{b_id}")))


def evidence_id(source_code: str, release_id: str, record_key: str,
                normalized_payload_sha256: str) -> str:
    return f"evidence:sha256:{sha256_text(source_code, release_id, record_key, normalized_payload_sha256)}"


def finding_id(contract_version: str, pair: str, finding_type: str,
               scope_hash: str, policy_version: str) -> str:
    return f"finding:sha256:{sha256_text(contract_version, pair, finding_type, scope_hash, policy_version)}"


def scope_hash(context: dict[str, Any] | None) -> str:
    context = context or {}
    normalized = {k: v for k, v in context.items() if v is not None}
    return f"sha256:{sha256_text(canonical_json(normalized))}"


def _add_column_if_missing(conn, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def ensure_schema(conn) -> None:
    """Idempotently provision the Phase 1 schema on a writable connection."""
    from .license_registry import ensure as ensure_license_schema

    ensure_license_schema(conn)
    for table, column, definition in (
        ("source_license", "provider", "TEXT"),
        ("source_license", "dataset_kind", "TEXT"),
        ("source_license", "authority_tier", "TEXT"),
        ("source_license", "display_policy", "TEXT NOT NULL DEFAULT 'show_attribution'"),
        ("source_license", "derived_use_allowed", "INTEGER NOT NULL DEFAULT 0"),
        ("source_license", "legal_review_status", "TEXT NOT NULL DEFAULT 'pending'"),
        ("source_license", "reviewed_by", "TEXT"),
        ("dataset_release", "release_status", "TEXT NOT NULL DEFAULT 'accepted'"),
        ("dataset_release", "published_at", "TEXT"),
        ("dataset_release", "fetched_at", "TEXT"),
        ("dataset_release", "content_type", "TEXT"),
        ("dataset_release", "size_bytes", "INTEGER"),
        ("dataset_release", "row_count", "INTEGER"),
        ("dataset_release", "schema_hash", "TEXT"),
        ("dataset_release", "artifact_ref", "TEXT"),
        ("dataset_release", "ingestion_run_id", "TEXT"),
    ):
        _add_column_if_missing(conn, table, column, definition)
    conn.executescript(SCHEMA)
    conn.commit()


def normalized_payload_hash(payload: dict[str, Any]) -> str:
    return f"sha256:{sha256_text(canonical_json(payload))}"


def slug_source(value: str) -> str:
    text = (value or "unknown").casefold()
    aliases = (
        ("supp.ai", "suppai"), ("suppai", "suppai"),
        ("dailymed", "dailymed"), ("openfda", "openfda"),
        ("fda", "openfda"), ("tapirro", "tapirro"),
        ("onsides", "onsides"), ("faers", "faers"),
        ("mendeley", "mendeley_drug_food"), ("pharmgkb", "pharmgkb"),
        ("cyp", "cyp_inference"), ("idisk", "idisk"),
    )
    for marker, code in aliases:
        if marker in text:
            return code
    slug = re.sub(r"[^a-z0-9]+", "_", text).strip("_")[:48]
    return f"legacy_{slug or 'unknown'}"

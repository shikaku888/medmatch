from __future__ import annotations

import sqlite3

from backend.engine import Engine
from backend.evidence_schema import (
    canonical_json,
    ensure_schema,
    evidence_id,
    finding_id,
    normalized_payload_hash,
    pair_key,
    scope_hash,
)


def _fixture_engine() -> tuple[Engine, sqlite3.Connection]:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    ensure_schema(conn)
    engine = Engine.__new__(Engine)
    engine.conn = conn
    engine.has_canonical = True
    engine.use_canonical_read = True
    return engine, conn


def _add_release(conn: sqlite3.Connection, source_code: str, version: str = "v1") -> str:
    release_id = f"{source_code}:{version}"
    conn.execute(
        "INSERT INTO source_license "
        "(source_code, licence_name, commercial_use_allowed, derived_use_allowed, legal_review_status) "
        "VALUES (?,?,?,?,?)",
        (source_code, "Fixture licence", 1, 0, "pending"),
    )
    conn.execute(
        "INSERT INTO dataset_release "
        "(source_code, dataset_name, version, downloaded_at, release_status) VALUES (?,?,?,?,?)",
        (source_code, "Fixture release", version, "2026-01-01T00:00:00+00:00", "accepted"),
    )
    conn.execute(
        "INSERT INTO ingestion_run "
        "(ingestion_run_id, source_code, release_id, parser_version, started_at, completed_at, status) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            f"run:{source_code}",
            source_code,
            release_id,
            "fixture-v1",
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "accepted",
        ),
    )
    return release_id


def _add_record(
    conn: sqlite3.Connection,
    *,
    source_code: str,
    release_id: str,
    record_key: str,
    evidence_level: str = "clinical_study",
    status: str = "accepted",
    subject_status: str | None = "accepted",
    with_derivation: bool = False,
) -> str:
    payload_hash = normalized_payload_hash({"record": record_key})
    evidence = evidence_id(source_code, release_id, record_key, payload_hash)
    conn.execute(
        "INSERT INTO evidence_record "
        "(evidence_id, source_code, release_id, ingestion_run_id, record_key, evidence_type, "
        "evidence_level, status, effect, mechanism, evidence_severity, evidence_confidence, "
        "context_json, normalized_payload_sha256, parser_version, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            evidence,
            source_code,
            release_id,
            f"run:{source_code}",
            record_key,
            "fixture",
            evidence_level,
            status,
            "Fixture effect",
            "Fixture mechanism",
            "moderate",
            0.9,
            canonical_json({}),
            payload_hash,
            "fixture-v1",
            "2026-01-01T00:00:00+00:00",
        ),
    )
    if subject_status is not None:
        conn.execute(
            "INSERT INTO evidence_record_subject "
            "(evidence_id, ordinal, entity_kind, entity_id, raw_name, mapping_method, "
            "mapping_confidence, mapping_status) VALUES (?,?,?,?,?,?,?,?)",
            (evidence, 0, "drug_class", record_key, record_key, "fixture", 1.0, subject_status),
        )
    if with_derivation:
        conn.execute(
            "INSERT INTO evidence_derivation "
            "(derived_evidence_id, upstream_evidence_id, operation, operation_version) "
            "VALUES (?,?,?,?)",
            (evidence, evidence, "fixture-derivation", "fixture-v1"),
        )
    return evidence


def _add_finding(
    conn: sqlite3.Connection,
    *,
    key: str,
    source_code: str,
    finding_status: str = "accepted",
    evidence_level: str = "clinical_study",
    evidence_status: str = "documented",
    record_status: str = "accepted",
    subject_status: str | None = "accepted",
    inferred: bool = False,
    with_derivation: bool = False,
) -> str:
    release_id = _add_release(conn, source_code, key)
    record = _add_record(
        conn,
        source_code=source_code,
        release_id=release_id,
        record_key=key,
        evidence_level="inferred" if inferred else evidence_level,
        status=record_status,
        subject_status=subject_status,
        with_derivation=with_derivation,
    )
    pair = pair_key("drug_class", key, "herb", "fixture-herb")
    fid = finding_id("fixture-contract", pair, "herb_drug", scope_hash({}), "fixture-policy")
    conn.execute(
        "INSERT INTO canonical_finding "
        "(finding_id, pair_key, a_kind, a_id, b_kind, b_id, finding_type, status, "
        "evidence_status, evidence_level, evidence_severity, evidence_confidence, effect, "
        "mechanism, action, inferred, context_json, scope_hash, resolution_policy_version, "
        "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            fid,
            pair,
            "drug_class",
            key,
            "herb",
            "fixture-herb",
            "herb_drug",
            finding_status,
            evidence_status,
            "inferred" if inferred else evidence_level,
            "moderate",
            0.9,
            "Fixture effect",
            "Fixture mechanism",
            "Monitor",
            int(inferred),
            canonical_json({}),
            scope_hash({}),
            "fixture-policy",
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
        ),
    )
    conn.execute(
        "INSERT INTO finding_evidence "
        "(finding_id, evidence_id, role, source_confidence, selected) VALUES (?,?,?,?,?)",
        (fid, record, "supporting", 0.9, 1),
    )
    return fid


def test_canonical_pairs_requires_accepted_valid_lineage() -> None:
    engine, conn = _fixture_engine()
    _add_finding(conn, key="valid", source_code="fixture-valid")
    _add_finding(conn, key="candidate-finding", source_code="fixture-candidate", finding_status="candidate")
    _add_finding(
        conn,
        key="candidate-evidence",
        source_code="fixture-evidence-candidate",
        record_status="candidate",
    )
    _add_finding(
        conn,
        key="unmapped-subject",
        source_code="fixture-unmapped",
        subject_status="candidate",
    )
    _add_finding(
        conn,
        key="missing-subject",
        source_code="fixture-missing-subject",
        subject_status=None,
    )
    _add_finding(
        conn,
        key="missing-derivation",
        source_code="fixture-inferred",
        inferred=True,
    )
    _add_finding(
        conn,
        key="derived-inference",
        source_code="fixture-derived",
        inferred=True,
        with_derivation=True,
    )
    _add_finding(conn, key="unlicensed", source_code="fixture-unlicensed")
    conn.execute(
        "UPDATE source_license SET commercial_use_allowed=0, derived_use_allowed=0 "
        "WHERE source_code='fixture-unlicensed'"
    )
    _add_finding(conn, key="unaccepted-release", source_code="fixture-unaccepted-release")
    conn.execute(
        "UPDATE dataset_release SET release_status='candidate' "
        "WHERE source_code='fixture-unaccepted-release'"
    )
    _add_finding(conn, key="failed-ingestion", source_code="fixture-failed-ingestion")
    conn.execute(
        "UPDATE ingestion_run SET status='failed' "
        "WHERE source_code='fixture-failed-ingestion'"
    )
    conn.commit()

    rows = engine.canonical_pairs("drug_class", "valid")
    assert [row["finding_id"] for row in rows] == [
        finding_id(
            "fixture-contract",
            pair_key("drug_class", "valid", "herb", "fixture-herb"),
            "herb_drug",
            scope_hash({}),
            "fixture-policy",
        )
    ]
    assert rows[0]["status"] == "accepted"
    assert rows[0]["evidence"][0]["sourceCode"] == "fixture-valid"
    assert rows[0]["evidence_ids"] == [rows[0]["evidence"][0]["evidenceId"]]
    assert len(engine.canonical_pairs("drug_class", "derived-inference")) == 1
    for invalid in (
        "candidate-finding",
        "candidate-evidence",
        "failed-ingestion",
        "unmapped-subject",
        "missing-subject",
        "missing-derivation",
        "unlicensed",
        "unaccepted-release",
    ):
        assert engine.canonical_pairs("drug_class", invalid) == [], invalid
    conn.close()


PARITY_FIXTURES = (
    (
        "herb-class",
        [
            {"name": "turmeric", "matched": {"kind": "herb", "id": "curcuma"}},
            {"name": "warfarin", "matched": {"kind": "drug_class", "id": "anticoagulantes"}},
        ],
    ),
    (
        "class-class",
        [
            {"name": "anticoagulantes", "matched": {"kind": "drug_class", "id": "anticoagulantes"}},
            {"name": "thyroid", "matched": {"kind": "drug_class", "id": "tiroideos"}},
        ],
    ),
    (
        "class-food",
        [
            {"name": "estatinas", "matched": {"kind": "drug_class", "id": "estatinas"}},
            {"name": "grapefruit", "matched": {"kind": "food", "id": "grapefruit"}},
        ],
    ),
    ("unmatched", [{"name": "fixture item not in vocabulary"}]),
)


def _run_fixture(monkeypatch, items: list[dict], flag: str) -> dict:
    monkeypatch.setenv("CANONICAL_EVIDENCE_READ", flag)
    engine = Engine()
    try:
        return engine.analyze(items)
    finally:
        engine.conn.close()


def _semantics(result: dict) -> tuple:
    interactions = []
    for item in result["interactions"]:
        endpoints = tuple(
            sorted(
                (
                    (item.get("a", {}).get("kind"), item.get("a", {}).get("id")),
                    (item.get("b", {}).get("kind"), item.get("b", {}).get("id")),
                )
            )
        )
        interactions.append(
            (endpoints, item.get("severity"), item.get("effect"), item.get("mechanism"))
        )
    return result["result"], tuple(sorted(interactions, key=repr)), tuple(sorted(result["unmatched"]))


def test_dual_read_preserves_required_result_semantics(monkeypatch) -> None:
    for name, items in PARITY_FIXTURES:
        legacy = _run_fixture(monkeypatch, items, "0")
        canonical = _run_fixture(monkeypatch, items, "1")
        assert _semantics(canonical) == _semantics(legacy), name

def test_canonical_read_defaults_on_after_parity(monkeypatch) -> None:
    monkeypatch.delenv("CANONICAL_EVIDENCE_READ", raising=False)
    engine = Engine()
    try:
        assert engine.use_canonical_read is True
    finally:
        engine.conn.close()

import json
import sqlite3

from backend.evidence_backfill import backfill_unified
from backend.evidence_schema import (
    SCHEMA_VERSION,
    canonical_json,
    ensure_schema,
    evidence_id,
    finding_id,
    normalized_payload_hash,
    pair_key,
    scope_hash,
)


def test_schema_is_idempotent_and_exposes_phase_one_tables():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    ensure_schema(conn)

    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {
        "source_license",
        "dataset_release",
        "ingestion_run",
        "evidence_artifact",
        "evidence_record",
        "evidence_record_subject",
        "canonical_finding",
        "finding_evidence",
        "evidence_derivation",
        "finding_conflict",
    } <= tables
    assert conn.execute(
        "SELECT COUNT(*) FROM pragma_table_info('evidence_record') WHERE name='normalized_payload_sha256'"
    ).fetchone()[0] == 1
    conn.close()


def test_canonical_ids_are_stable_and_order_independent():
    assert canonical_json({"b": 2, "a": 1}) == '{"a":1,"b":2}'
    assert pair_key("herb", "curcuma", "drug_class", "anticoagulantes") == pair_key(
        "drug_class", "anticoagulantes", "herb", "curcuma"
    )
    payload_hash = normalized_payload_hash({"doi": "10.example/1", "trust": 0.9})
    assert evidence_id("suppai", "suppai:2026", "record-1", payload_hash) == evidence_id(
        "suppai", "suppai:2026", "record-1", payload_hash
    )
    assert finding_id(
        SCHEMA_VERSION,
        pair_key("herb", "curcuma", "drug_class", "anticoagulantes"),
        "herb_drug",
        scope_hash({}),
        "risk-resolution-v1",
    ) == finding_id(
        SCHEMA_VERSION,
        pair_key("drug_class", "anticoagulantes", "herb", "curcuma"),
        "herb_drug",
        scope_hash({}),
        "risk-resolution-v1",
    )


def test_unified_backfill_creates_finding_evidence_lineage_idempotently():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    conn.execute(
        """CREATE TABLE interaction_unified (
            pair_key TEXT PRIMARY KEY,
            a_kind TEXT NOT NULL, a_id TEXT NOT NULL,
            b_kind TEXT NOT NULL, b_id TEXT NOT NULL,
            severity TEXT, effect TEXT, mechanism TEXT,
            evidence TEXT, confidence REAL, is_inferred INTEGER NOT NULL
        )"""
    )
    conn.execute(
        "INSERT INTO interaction_unified VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            "drug_class:anticoagulantes|herb:hypericum",
            "drug_class", "anticoagulantes",
            "herb", "hypericum",
            "major", "Reduced warfarin exposure", "CYP2C9 induction",
            json.dumps([{"source": "SUPP.AI", "trust": 0.9, "doi": "10.example/1"}]),
            0.9, 0,
        ),
    )
    first = backfill_unified(conn)
    second = backfill_unified(conn)
    assert first == {"findings": 1, "evidence": 1, "links": 1, "candidate_findings": 1, "synthetic_evidence": 0}
    assert second == {"findings": 1, "evidence": 1, "links": 1, "candidate_findings": 1, "synthetic_evidence": 0}
    assert conn.execute("SELECT COUNT(*) FROM canonical_finding").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM evidence_record").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM finding_evidence WHERE selected=1").fetchone()[0] == 1
    finding = conn.execute("SELECT status, evidence_status, evidence_level FROM canonical_finding").fetchone()
    assert tuple(finding) == ("candidate", "unknown", "unknown")
    conn.close()


def test_unified_backfill_refreshes_changed_finding_and_selected_lineage():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    conn.execute(
        """CREATE TABLE interaction_unified (
            pair_key TEXT PRIMARY KEY,
            a_kind TEXT NOT NULL, a_id TEXT NOT NULL,
            b_kind TEXT NOT NULL, b_id TEXT NOT NULL,
            severity TEXT, effect TEXT, mechanism TEXT,
            evidence TEXT, confidence REAL, is_inferred INTEGER NOT NULL
        )"""
    )
    pair = "drug_class:aines|drug_class:isrs"
    conn.execute(
        "INSERT INTO interaction_unified VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            pair, "drug_class", "aines", "drug_class", "isrs",
            "moderate", "CYP pathway overlap: 2D6", "Enzyme pathway inference",
            json.dumps([{"source": "CYP450 inference", "trust": 0.5}]), 0.5, 1,
        ),
    )
    backfill_unified(conn)

    conn.execute(
        "UPDATE interaction_unified SET severity=?, effect=?, mechanism=?, evidence=?, confidence=?, is_inferred=? "
        "WHERE pair_key=?",
        (
            "major",
            "Increased risk of gastrointestinal bleeding when SSRIs are combined with NSAIDs.",
            "SSRIs impair platelet serotonin-mediated aggregation; NSAIDs inhibit platelet function and injure the gastrointestinal mucosa.",
            json.dumps([{"source": "FDA SSRI and NSAID labeling", "trust": 1.0}]),
            1.0,
            0,
            pair,
        ),
    )
    backfill_unified(conn)

    finding = conn.execute(
        "SELECT evidence_severity, evidence_level, inferred, effect FROM canonical_finding "
        "WHERE pair_key=?",
        (pair,),
    ).fetchone()
    assert tuple(finding) == (
        "major",
        "regulatory",
        0,
        "Increased risk of gastrointestinal bleeding when SSRIs are combined with NSAIDs.",
    )
    assert conn.execute(
        "SELECT COUNT(*) FROM evidence_record WHERE record_key LIKE ?",
        (f"interaction_unified:{pair}:%",),
    ).fetchone()[0] == 2
    assert conn.execute(
        "SELECT COUNT(*) FROM finding_evidence WHERE finding_id=? AND selected=1",
        (conn.execute("SELECT finding_id FROM canonical_finding WHERE pair_key=?", (pair,)).fetchone()[0],),
    ).fetchone()[0] == 1
    conn.close()

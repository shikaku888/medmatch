import json
import sqlite3

from backend.evidence_schema import (
    SCHEMA_VERSION,
    canonical_json,
    evidence_id,
    finding_id,
    normalized_payload_hash,
    scope_hash,
)
from backend.source_reconciliation import (
    POLICY_VERSION,
    _ensure_cyp_role_lineage,
    _source_run,
    ensure_reconciliation_schema,
    reconcile_evidence,
    resolve_source_code,
)


def _insert_legacy_evidence(conn, *, source_label, source_code, pair, finding):
    record_key = f"interaction_unified:{pair}:0"
    payload_hash = normalized_payload_hash({"source": source_label, "trust": 0.4})
    release_id = f"{source_code}:legacy-unknown"
    conn.execute(
        "INSERT OR IGNORE INTO dataset_release "
        "(source_code, dataset_name, version, commercial_status, downloaded_at, "
        "parser_version, notes, release_status) VALUES (?,?,?,?,?,?,?,?)",
        (source_code, "legacy", "legacy-unknown", "restricted_private", "2026-01-01T00:00:00+00:00", "test", "test", "candidate"),
    )
    run_id = f"test:{source_code}"
    conn.execute(
        "INSERT OR IGNORE INTO ingestion_run "
        "(ingestion_run_id, source_code, release_id, parser_version, contract_version, "
        "started_at, completed_at, status) VALUES (?,?,?,?,?,?,?,?)",
        (run_id, source_code, release_id, "test", SCHEMA_VERSION, "2026-01-01", "2026-01-01", "failed"),
    )
    old_id = evidence_id(source_code, release_id, record_key, payload_hash)
    conn.execute(
        "INSERT INTO evidence_record "
        "(evidence_id, source_code, release_id, ingestion_run_id, record_key, evidence_type, "
        "evidence_level, status, statement, evidence_severity, evidence_confidence, "
        "source_record_id, context_json, normalized_payload_sha256, parser_version, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (old_id, source_code, release_id, run_id, record_key, "herb_drug", "unknown", "candidate",
         "legacy statement", "major", 0.4, record_key, canonical_json({}), payload_hash, "test", "2026-01-01"),
    )
    conn.execute(
        "INSERT INTO evidence_record_subject "
        "(evidence_id, ordinal, entity_kind, entity_id, raw_name, mapping_method, mapping_confidence, mapping_status) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (old_id, 0, "herb", "hypericum", "hypericum", "test", 1.0, "accepted"),
    )
    conn.execute(
        "INSERT INTO finding_evidence "
        "(finding_id, evidence_id, role, source_confidence, selected) VALUES (?,?,?,?,1)",
        (finding, old_id, "supporting", 0.4),
    )
    return old_id


def _insert_finding(conn, pair, fid):
    conn.execute(
        "INSERT INTO canonical_finding "
        "(finding_id, pair_key, a_kind, a_id, b_kind, b_id, finding_type, status, "
        "evidence_status, evidence_level, evidence_severity, evidence_confidence, effect, "
        "mechanism, inferred, context_json, scope_hash, resolution_policy_version, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (fid, pair, "drug_class", "anticoagulantes", "herb", "hypericum", "herb_drug", "candidate",
         "unknown", "unknown", "major", 0.4, "legacy", "legacy", 0, canonical_json({}),
         scope_hash({}), POLICY_VERSION, "2026-01-01", "2026-01-01"),
    )


def test_source_labels_resolve_to_provider_not_citation_slug():
    assert resolve_source_code("EMA/HMPC monograph") == "tapirro"
    assert resolve_source_code("FDA statin labeling") == "fda_curated"
    assert resolve_source_code("DailyMed: label ABC") == "dailymed"
    assert resolve_source_code("SUPP.AI (herb-herb)") == "suppai"
    assert resolve_source_code("MSKCC") == "idisk"
    assert resolve_source_code("unrecognized citation") == "legacy_unrecognized_citation"


def test_reconciliation_rekeys_eligible_source_and_keeps_restricted_candidate():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_reconciliation_schema(conn)
    conn.execute(
        """CREATE TABLE interaction_unified (
            pair_key TEXT PRIMARY KEY,
            a_kind TEXT NOT NULL, a_id TEXT NOT NULL,
            b_kind TEXT NOT NULL, b_id TEXT NOT NULL,
            severity TEXT, effect TEXT, mechanism TEXT,
            evidence TEXT, confidence REAL, is_inferred INTEGER NOT NULL
        )"""
    )
    tapirro_pair = "drug_class:anticoagulantes|herb:hypericum"
    idisk_pair = "drug_class:antipsicoticos|herb:curcuma"
    conn.executemany(
        "INSERT INTO interaction_unified VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [
            (tapirro_pair, "drug_class", "anticoagulantes", "herb", "hypericum", "major", "effect", "mechanism",
             json.dumps([{"source": "EMA/HMPC monograph", "trust": 0.4}]), 0.4, 0),
            (idisk_pair, "drug_class", "antipsicoticos", "herb", "curcuma", "moderate", "effect", "mechanism",
             json.dumps([{"source": "MSKCC", "trust": 0.4}]), 0.4, 0),
        ],
    )
    tapirro_finding = "finding:tapirro-test"
    idisk_finding = "finding:idisk-test"
    _insert_finding(conn, tapirro_pair, tapirro_finding)
    _insert_finding(conn, idisk_pair, idisk_finding)
    old_tapirro = _insert_legacy_evidence(
        conn, source_label="EMA/HMPC monograph", source_code="legacy_ema_hmpc_monograph",
        pair=tapirro_pair, finding=tapirro_finding,
    )
    old_idisk = _insert_legacy_evidence(
        conn, source_label="MSKCC", source_code="legacy_mskcc", pair=idisk_pair, finding=idisk_finding,
    )
    conn.commit()

    stats = reconcile_evidence(conn)
    tapirro_new = conn.execute(
        "SELECT evidence_id, source_code, release_id, status FROM evidence_record "
        "WHERE source_code='tapirro'"
    ).fetchone()
    idisk_new = conn.execute(
        "SELECT evidence_id, source_code, release_id, status FROM evidence_record "
        "WHERE source_code='idisk'"
    ).fetchone()
    assert tapirro_new is not None
    assert tuple(tapirro_new[1:]) == ("tapirro", "tapirro:seed-v1", "accepted")
    assert idisk_new is not None
    assert tuple(idisk_new[1:]) == ("idisk", "idisk:legacy-unknown", "candidate")
    assert conn.execute("SELECT status FROM evidence_record WHERE evidence_id=?", (old_tapirro,)).fetchone()[0] == "superseded"
    assert conn.execute("SELECT status FROM evidence_record WHERE evidence_id=?", (old_idisk,)).fetchone()[0] == "superseded"
    assert conn.execute(
        "SELECT selected FROM finding_evidence WHERE finding_id=? AND evidence_id=?",
        (tapirro_finding, tapirro_new[0]),
    ).fetchone()[0] == 1
    assert conn.execute("SELECT status FROM canonical_finding WHERE finding_id=?", (tapirro_finding,)).fetchone()[0] == "accepted"
    assert conn.execute("SELECT status FROM canonical_finding WHERE finding_id=?", (idisk_finding,)).fetchone()[0] == "candidate"
    assert stats["reconciled"] == 2
    assert stats["unresolved"] == 1
    conn.close()

def test_inferred_evidence_requires_explicit_cyp_derivation_lineage():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_reconciliation_schema(conn)
    conn.execute(
        "CREATE TABLE cyp_roles (entity_type TEXT, entity_id TEXT, role TEXT, enzyme TEXT, "
        "PRIMARY KEY(entity_type, entity_id, role, enzyme))"
    )
    conn.executemany(
        "INSERT INTO cyp_roles VALUES (?,?,?,?)",
        [
            ("drug_class", "anticoagulantes", "substrate", "2C9"),
            ("herb", "hypericum", "inducer", "2C9"),
        ],
    )
    release_id = "cyp_inference:algorithm-v1"
    run_id = _source_run(conn, "cyp_inference", release_id, True)
    record_key = "interaction_unified:drug_class:anticoagulantes|herb:hypericum:0"
    payload_hash = normalized_payload_hash({"source": "CYP450 inference", "trust": 0.5})
    inferred_id = evidence_id("cyp_inference", release_id, record_key, payload_hash)
    conn.execute(
        "INSERT INTO evidence_record "
        "(evidence_id, source_code, release_id, ingestion_run_id, record_key, evidence_type, "
        "evidence_level, status, statement, evidence_confidence, source_record_id, source_locator, "
        "context_json, normalized_payload_sha256, parser_version, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (inferred_id, "cyp_inference", release_id, run_id, record_key, "herb_drug", "inferred",
         "accepted", "pathway overlap", 0.5, record_key, record_key, canonical_json({}),
         payload_hash, "test", "2026-01-01"),
    )
    conn.executemany(
        "INSERT INTO evidence_record_subject "
        "(evidence_id, ordinal, entity_kind, entity_id, raw_name, mapping_method, mapping_confidence, mapping_status) "
        "VALUES (?,?,?,?,?,?,?,?)",
        [
            (inferred_id, 0, "drug_class", "anticoagulantes", "anticoagulantes", "test", 1.0, "accepted"),
            (inferred_id, 1, "herb", "hypericum", "hypericum", "test", 1.0, "accepted"),
        ],
    )
    stats = _ensure_cyp_role_lineage(conn, "2026-01-01")
    assert stats == {"role_records": 2, "derivations": 2, "unresolved_derivations": 0}
    assert conn.execute(
        "SELECT COUNT(*) FROM evidence_derivation WHERE derived_evidence_id=?",
        (inferred_id,),
    ).fetchone()[0] == 2
    conn.close()

from __future__ import annotations

import asyncio
import json
import sqlite3

from backend import app as app_module
from backend.evidence_ontology import build_intersection


def _connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE rxnorm_names (rxcui TEXT, name TEXT, tty TEXT);
        CREATE TABLE onsides_ingredient_effects (
            rxnorm_ingredient_id TEXT NOT NULL,
            rxnorm_ingredient_name TEXT NOT NULL,
            effect_meddra_id TEXT NOT NULL,
            effect TEXT NOT NULL,
            source_region TEXT NOT NULL,
            row_count INTEGER NOT NULL,
            label_count INTEGER NOT NULL,
            high_confidence INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE faers_adverse_events (
            drug_key TEXT NOT NULL,
            drug_name TEXT NOT NULL,
            pt TEXT NOT NULL,
            quarter TEXT NOT NULL,
            case_count INTEGER NOT NULL
        );
        CREATE TABLE label_section (
            set_id TEXT PRIMARY KEY,
            generic_name TEXT,
            openfda_generic TEXT
        );
        INSERT INTO rxnorm_names VALUES ('1191', 'Aspirin', 'IN');
        INSERT INTO onsides_ingredient_effects VALUES
            ('1191', 'Aspirin', '10000001', 'Nausea', 'US', 12, 2, 1);
        INSERT INTO faers_adverse_events VALUES
            ('aspirin', 'ASPIRIN', 'Nausea', '2025Q1', 7),
            ('aspirin', 'ASPIRIN', 'Headache', '2025Q1', 3);
        INSERT INTO label_section VALUES ('label-1', 'ASPIRIN', NULL);
        """
    )
    return conn


def test_build_intersection_uses_exact_rxnorm_identity_and_keeps_sources_separate() -> None:
    conn = _connection()
    result = build_intersection(conn)

    assert result["intersections"] == 1
    row = conn.execute(
        "SELECT * FROM evidence_ontology_intersection WHERE rxnorm_ingredient_id='1191'"
    ).fetchone()
    assert row is not None
    assert json.loads(row["sources"]) == ["OnSIDES", "FAERS", "FDA labels"]
    assert row["source_count"] == 3
    assert row["onsides_effect_count"] == 1
    assert row["onsides_row_count"] == 12
    assert row["faers_case_count"] == 10
    assert row["faers_term_count"] == 2
    assert row["label_count"] == 1
    assert row["match_method"] == "rxnorm_exact_name"
    assert row["built_at"]
    conn.close()


def test_ambiguous_rxnorm_name_is_not_intersected() -> None:
    conn = _connection()
    conn.execute("INSERT INTO rxnorm_names VALUES ('1192', 'Aspirin', 'IN')")
    result = build_intersection(conn)

    assert result["intersections"] == 0
    assert conn.execute("SELECT COUNT(*) FROM evidence_ontology_intersection").fetchone()[0] == 0
    conn.close()


def test_intersection_endpoint_exposes_ingredient_level_contract(monkeypatch) -> None:
    conn = _connection()
    build_intersection(conn)
    monkeypatch.setattr(app_module, "get_conn", lambda: conn)
    monkeypatch.setattr(app_module, "_onsides_ingredient_keys", lambda drug_id, db: ["1191"])

    payload = asyncio.run(app_module.drug_evidence_intersection("aspirin", 10))

    assert payload["status"] == "evidence_intersection_found"
    assert payload["ingredients"][0]["sources"] == ["OnSIDES", "FAERS", "FDA labels"]
    assert "not merged" in payload["limitations"][1]
    conn.close()

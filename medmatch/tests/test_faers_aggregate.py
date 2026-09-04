from __future__ import annotations

import asyncio
import sqlite3

from backend import app as app_module
from backend.faers import build_adverse_event_aggregate


def test_faers_aggregate_deduplicates_case_versions_and_reactions() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE fda_report (
            primaryid TEXT, caseid TEXT, caseversion TEXT, quarter TEXT,
            event_dt TEXT, fda_dt TEXT
        );
        CREATE TABLE fda_drug (
            primaryid TEXT, caseid TEXT, role_cod TEXT, drugname TEXT,
            prod_ai TEXT, quarter TEXT
        );
        CREATE TABLE fda_reaction (
            primaryid TEXT, caseid TEXT, pt TEXT, quarter TEXT
        );
        CREATE TABLE fda_outcome (
            primaryid TEXT, caseid TEXT, outc_cod TEXT, quarter TEXT
        );
        INSERT INTO fda_report VALUES ('old', 'case-1', '1', '2026Q2', '20260101', '20260102');
        INSERT INTO fda_report VALUES ('new', 'case-1', '2', '2026Q2', '20260201', '20260202');
        INSERT INTO fda_drug VALUES ('old', 'case-1', 'PS', 'WARFARIN', 'WARFARIN', '2026Q2');
        INSERT INTO fda_drug VALUES ('new', 'case-1', 'PS', 'WARFARIN', 'WARFARIN', '2026Q2');
        INSERT INTO fda_reaction VALUES ('new', 'case-1', 'Haemorrhage', '2026Q2');
        INSERT INTO fda_reaction VALUES ('new', 'case-1', 'Haemorrhage', '2026Q2');
        INSERT INTO fda_outcome VALUES ('new', 'case-1', 'DE', '2026Q2');
        """
    )

    assert build_adverse_event_aggregate(conn) == {"rows": 1, "status": "ok"}
    row = conn.execute(
        "SELECT * FROM faers_adverse_events WHERE drug_key = 'warfarin'"
    ).fetchone()

    assert row["case_count"] == 1
    assert row["serious_case_count"] == 1
    assert row["primary_suspect_case_count"] == 1
    assert row["first_seen"] == "20260201"
    assert row["last_seen"] == "20260201"
    conn.close()


def test_faers_endpoint_exposes_quarter_roles_and_limitations(monkeypatch) -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE drug_classes (id TEXT PRIMARY KEY, drugs TEXT);
        CREATE TABLE faers_adverse_events (
            drug_key TEXT, drug_name TEXT, pt TEXT, quarter TEXT,
            case_count INTEGER, serious_case_count INTEGER,
            primary_suspect_case_count INTEGER, secondary_case_count INTEGER,
            concomitant_case_count INTEGER, first_seen TEXT, last_seen TEXT,
            source TEXT
        );
        CREATE TABLE dataset_release (source_code TEXT, downloaded_at TEXT);
        INSERT INTO faers_adverse_events VALUES
            ('warfarin', 'WARFARIN', 'Haemorrhage', '2026Q2', 4, 2, 3, 1, 0,
             '20260101', '20260601', 'FDA FAERS');
        INSERT INTO dataset_release VALUES ('faers', '2026-07-01T00:00:00Z');
        """
    )
    monkeypatch.setattr(app_module, "get_conn", lambda: conn)

    payload = asyncio.run(app_module.drug_adverse_events("warfarin", 10, None))

    assert payload["events"][0]["quarter"] == "2026Q2"
    assert payload["events"][0]["role_case_counts"] == {"PS": 3, "SS": 1, "C": 0}
    assert payload["updated_at"] == "2026-07-01T00:00:00Z"
    assert any("causality" in limitation for limitation in payload["limitations"])
    conn.close()

from __future__ import annotations

import asyncio
import json
import sqlite3

from backend import app as app_module


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE drug_classes (id TEXT PRIMARY KEY, drugs TEXT);
        INSERT INTO drug_classes VALUES ('analgesics', '["ibuprofen"]');
        CREATE TABLE drugcentral_structures (struct_id TEXT PRIMARY KEY, name TEXT);
        INSERT INTO drugcentral_structures VALUES ('1407', 'ibuprofen');
        CREATE TABLE drugcentral_synonyms (struct_id TEXT, synonym TEXT, lname TEXT);
        CREATE TABLE drugcentral_struct_atc (struct_id TEXT, atc_code TEXT);
        INSERT INTO drugcentral_struct_atc VALUES ('1407', 'M01AE01');
        CREATE TABLE drugcentral_atc (chemical_substance TEXT, code TEXT, l1_name TEXT, l2_name TEXT, l3_name TEXT, l4_name TEXT);
        INSERT INTO drugcentral_atc VALUES ('ibuprofen', 'M01AE01', 'MUSCULO-SKELETAL', 'ANTIINFLAMMATORY', 'NSAIDS', 'Propionic acid derivatives');
        CREATE TABLE drugcentral_target_facts (struct_id TEXT, target_id TEXT, target_name TEXT, target_class TEXT, relation TEXT, moa TEXT, action_type TEXT, act_source_url TEXT, moa_source_url TEXT);
        INSERT INTO drugcentral_target_facts VALUES ('1407', '1', 'Cyclooxygenase-2', 'Enzyme', '=', 'inhibition', 'INHIBITOR', NULL, NULL);
        CREATE TABLE lactmed_records (substance_id TEXT, substance_name TEXT, revised_date TEXT, summary_of_use TEXT, drug_levels TEXT, infant_effects TEXT, lactation_effects TEXT, alternate_drugs TEXT, drug_class TEXT, source_url TEXT, downloaded_at TEXT);
        INSERT INTO lactmed_records VALUES ('LM1', 'Ibuprofen', '2024-01-01', 'Low levels.', 'Low.', 'None reported.', 'None.', 'Acetaminophen', 'NSAID', 'https://www.ncbi.nlm.nih.gov/books/LM1/', '2026-01-01');
        CREATE TABLE fda_recalls (event_key TEXT PRIMARY KEY, event_id TEXT, product_type TEXT, classification TEXT, status TEXT, recalling_firm TEXT, city TEXT, state TEXT, country TEXT, product_description TEXT, product_quantity TEXT, reason_for_recall TEXT, recall_number TEXT, voluntary_mandated TEXT, initial_firm_notification TEXT, distribution_pattern TEXT, recall_initiation_date TEXT, center_classification_date TEXT, termination_date TEXT, report_date TEXT, code_info TEXT, more_code_info TEXT, source_url TEXT, downloaded_at TEXT);
        INSERT INTO fda_recalls VALUES ('drug:x', 'x', 'Drugs', 'Class II', 'Ongoing', 'Firm', '', '', 'US', 'Ibuprofen tablets', '', 'Contamination', 'D-x', '', '', '', '20260101', '', '', '', '', '', 'https://example.test', '2026');
        CREATE TABLE caers_product_events (product_key TEXT, product_name TEXT, reaction TEXT, case_count INTEGER, serious_count INTEGER, first_seen TEXT, last_seen TEXT, source TEXT);
        INSERT INTO caers_product_events VALUES ('ibuprofen', 'Ibuprofen', 'NAUSEA', 3, 1, '2020-01-01', '2025-01-01', 'FDA CAERS');
        """
    )
    return conn


def test_drugcentral_atc_and_mechanism(monkeypatch) -> None:
    conn = _db()
    monkeypatch.setattr(app_module, "get_conn", lambda: conn)
    atc = asyncio.run(app_module.drug_atc("analgesics"))
    mechanism = asyncio.run(app_module.drug_mechanism("analgesics", 10))
    assert atc["status"] == "evidence_found"
    assert atc["atc"][0]["atc_code"] == "M01AE01"
    assert mechanism["targets"][0]["action_type"] == "INHIBITOR"
    conn.close()


def test_lactmed_recall_caers_are_separate_observational_payloads(monkeypatch) -> None:
    conn = _db()
    monkeypatch.setattr(app_module, "get_conn", lambda: conn)
    lact = asyncio.run(app_module.drug_lactation("analgesics"))
    recall = asyncio.run(app_module.drug_recalls("analgesics", 10))
    caers = asyncio.run(app_module.drug_caers_events("analgesics", 10))
    assert lact["status"] == "evidence_found"
    assert lact["records"][0]["substance_name"] == "Ibuprofen"
    assert recall["status"] == "recall_found"
    assert caers["status"] == "signal_found"
    assert "causality" in " ".join(caers["limitations"]).lower()
    conn.close()

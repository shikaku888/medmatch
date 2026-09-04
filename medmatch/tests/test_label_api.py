from __future__ import annotations

import asyncio
import sqlite3

from backend import app as app_module


def test_label_endpoint_returns_reference_sections_and_provenance(monkeypatch) -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE drug_classes (id TEXT PRIMARY KEY, drugs TEXT);
        CREATE TABLE label_section (
            set_id TEXT PRIMARY KEY, effective_time TEXT, generic_name TEXT,
            brand_name TEXT, openfda_generic TEXT, drug_interactions TEXT, warnings TEXT
        );
        INSERT INTO drug_classes VALUES ('anticoagulantes', '["warfarin"]');
        INSERT INTO label_section VALUES (
            'set-1', '20260810', NULL, NULL, 'WARFARIN',
            'Avoid concomitant NSAIDs.', 'Monitor for bleeding.'
        );
        """
    )
    monkeypatch.setattr(app_module, "get_conn", lambda: conn)

    payload = asyncio.run(app_module.drug_label("anticoagulantes"))

    assert payload["reference_only"] is True
    assert {section["section"] for section in payload["sections"]} == {
        "warnings_and_precautions", "drug_interactions"
    }
    assert all(section["source"] == "DailyMed/OpenFDA" for section in payload["sections"])
    assert all(section["source_url"].endswith("setid=set-1") for section in payload["sections"])
    assert "contraindications" in payload["unavailable_sections"]
    conn.close()


def test_mendeley_endpoint_keeps_research_evidence_separate(monkeypatch) -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE drug_classes (id TEXT PRIMARY KEY, drugs TEXT);
        CREATE TABLE mendeley_drug_food_2021 (
            label INTEGER, food_constituent TEXT, food_smiles TEXT,
            drug_constituent TEXT, drug_smiles TEXT, interaction TEXT, source TEXT
        );
        INSERT INTO drug_classes VALUES ('statins', '["simvastatin"]');
        INSERT INTO mendeley_drug_food_2021 VALUES
            (1, 'naringin', 'C', 'simvastatin', 'N', 'inhibits transport', 'Mendeley');
        """
    )
    monkeypatch.setattr(app_module, "get_conn", lambda: conn)

    payload = asyncio.run(app_module.drug_food_evidence("statins", 10))

    assert payload["evidence"][0]["evidence_type"] == "research_evidence"
    assert payload["evidence"][0]["confidence"] is None
    assert "FDA contraindication" in payload["limitations"][1]
    conn.close()


def test_lactation_without_local_copy_is_explicitly_unknown(monkeypatch) -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE drug_classes (id TEXT PRIMARY KEY, drugs TEXT)")
    conn.execute("INSERT INTO drug_classes VALUES ('antibiotics', '[\"amoxicillin\"]')")
    monkeypatch.setattr(app_module, "get_conn", lambda: conn)

    payload = asyncio.run(app_module.drug_lactation("antibiotics"))

    assert payload["status"] == "unknown"
    assert payload["infant_exposure"] is None
    assert payload["references"][0]["source"] == "NCBI Bookshelf"
    conn.close()


def test_pharmacogenomics_requires_genotype_for_recommendation(monkeypatch) -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE drug_classes (id TEXT PRIMARY KEY, drugs TEXT);
        CREATE TABLE pharmgkb_relations (
            ent1_id TEXT, ent1_name TEXT, ent1_type TEXT,
            ent2_id TEXT, ent2_name TEXT, ent2_type TEXT,
            evidence TEXT, association TEXT, pk TEXT, pd TEXT, pmids TEXT, row_ord INTEGER
        );
        INSERT INTO drug_classes VALUES ('anticoagulants', '[\"warfarin\"]');
        INSERT INTO pharmgkb_relations VALUES
            ('PA1', 'CYP2C9', 'Gene', 'PA2', 'warfarin', 'Chemical',
             'high evidence', 'associated', '', '', '12345', 1);
        """
    )
    monkeypatch.setattr(app_module, "get_conn", lambda: conn)

    payload = asyncio.run(app_module.drug_pharmacogenomics("anticoagulants", 10))

    assert payload["relationships"][0]["gene"]["name"] == "CYP2C9"
    assert "No personal recommendation" in payload["recommendation"]
    assert payload["license"] == "CC BY-SA 4.0; attribution and share-alike apply."
    conn.close()


def test_pharmacogenomics_check_requires_context_before_interpretation(monkeypatch) -> None:
    monkeypatch.setattr(
        app_module,
        "_pharmacogenomics_payload",
        lambda drug_id, limit: {"drug_id": drug_id, "relationships": []},
    )

    unknown = asyncio.run(
        app_module.pharmacogenomics_check(
            app_module.PharmacogenomicsCheckRequest(drug_id="warfarin")
        )
    )
    assert unknown["status"] == "unknown"
    assert unknown["recommendation"] is None

    review = asyncio.run(
        app_module.pharmacogenomics_check(
            app_module.PharmacogenomicsCheckRequest(
                drug_id="warfarin",
                genotype={"gene": "CYP2C9", "allele": "*2"},
                indication="atrial fibrillation",
            )
        )
    )
    assert review["status"] == "review_required"
    assert "no automatic dose recommendation" in review["recommendation"]


def test_context_missing_status_is_unknown_not_normal(monkeypatch) -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE drug_classes (id TEXT PRIMARY KEY, drugs TEXT);
        CREATE TABLE label_section (
            set_id TEXT PRIMARY KEY, effective_time TEXT, generic_name TEXT,
            brand_name TEXT, openfda_generic TEXT, drug_interactions TEXT, warnings TEXT
        );
        INSERT INTO drug_classes VALUES ('statins', '[\"simvastatin\"]');
        INSERT INTO label_section VALUES
            ('set-2', '20260101', NULL, NULL, 'SIMVASTATIN', NULL, 'Use caution in pregnancy.');
        """
    )
    monkeypatch.setattr(app_module, "get_conn", lambda: conn)

    payload = asyncio.run(app_module.drug_context("statins", {"pregnancyStatus": "pregnant"}))

    assert payload["contexts"]["pregnancy"]["status"] == "known"
    assert payload["contexts"]["renal"]["status"] == "unknown"
    assert "renal" in payload["missing_context"]
    assert payload["alerts"][0]["status"] == "unknown"

    nested = asyncio.run(
        app_module.drug_context("statins", {"pregnancy": {"status": "pregnant", "weeks": 18}})
    )
    assert nested["contexts"]["pregnancy"]["value"]["weeks"] == 18
    assert nested["alerts"][0]["context"] == "pregnancy"
    conn.close()


def test_context_endpoint_validates_all_population_boundaries(monkeypatch) -> None:
    monkeypatch.setattr(
        app_module,
        "_label_payload",
        lambda *_args, **_kwargs: {
            "sections": [
                {"section": "pregnancy", "text": "Review with clinician."},
                {"section": "lactation", "text": "Review with clinician."},
                {"section": "renal_impairment", "text": "Review with clinician."},
                {"section": "hepatic_impairment", "text": "Review with clinician."},
                {"section": "pediatric_use", "text": "Safety below age 18 is not established."},
            ]
        },
    )

    payload = asyncio.run(
        app_module.drug_context(
            "statins",
            {
                "age": 17,
                "pregnancyStatus": "pregnant",
                "lactationStatus": "breastfeeding",
                "kidneyFunction": "moderate_impairment",
                "liverFunction": "mild_impairment",
            },
        )
    )

    assert {alert["context"] for alert in payload["alerts"]} == {
        "pregnancy", "lactation", "renal", "hepatic", "pediatric",
    }
    assert all(alert["status"] == "known" for alert in payload["alerts"])


def test_enrichment_references_are_outbound_only(monkeypatch) -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE drug_classes (id TEXT PRIMARY KEY, drugs TEXT);
        INSERT INTO drug_classes VALUES ('statins', '["simvastatin"]');
        """
    )
    monkeypatch.setattr(app_module, "get_conn", lambda: conn)

    for endpoint in (
        app_module.drug_targets,
        app_module.drug_medlineplus,
        app_module.drug_livertox,
    ):
        payload = asyncio.run(endpoint("statins"))
        assert payload["status"] == "outbound_reference_only"
        assert payload["limitations"]
    conn.close()

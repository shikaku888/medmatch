from __future__ import annotations

import json
import sqlite3

from backend import unify


def test_drug_name_mapping_prefers_exact_rxnorm_and_keeps_unmatched_reviewable() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(unify.SCHEMA)
    conn.executescript(
        """
        CREATE TABLE drug_classes (id TEXT PRIMARY KEY, name_en TEXT, drugs TEXT, aliases TEXT);
        CREATE TABLE zenodo_ddi_2026 (drug_a TEXT, drug_b TEXT, interaction TEXT, source TEXT);
        CREATE TABLE rxnorm_concepts (rxcui TEXT PRIMARY KEY, name TEXT, tty TEXT);
        CREATE TABLE rxnorm_relations (rxcui1 TEXT, rel TEXT, rxcui2 TEXT, rela TEXT);
        INSERT INTO drug_classes VALUES ('anticoagulantes', 'Anticoagulants', '["warfarin"]', '[]');
        INSERT INTO zenodo_ddi_2026 VALUES ('ibuprofen', 'warfarin', 'bleeding', 'zenodo');
        INSERT INTO zenodo_ddi_2026 VALUES ('ibuprofen', 'not-a-drug', 'unknown', 'zenodo');
        INSERT INTO rxnorm_concepts VALUES ('5640', 'ibuprofen', 'IN');
        INSERT INTO rxnorm_concepts VALUES ('11289', 'warfarin', 'IN');
        """
    )

    counts = unify.build_drug_name_mapping(conn)
    rows = {
        row["raw_name"]: dict(row)
        for row in conn.execute(
            "SELECT raw_name, normalized_name, entity_type, entity_id, rxcui, confidence, match_method "
            "FROM drug_name_mapping WHERE source = 'zenodo_ddi_2026'"
        )
    }

    assert counts == {"mapped": 2, "unmapped": 1}
    assert rows["ibuprofen"]["entity_type"] == "drug_ingredient"
    assert rows["ibuprofen"]["rxcui"] == "5640"
    assert rows["ibuprofen"]["confidence"] == 1.0
    assert rows["warfarin"]["match_method"] == "rxnorm_exact"
    assert rows["not-a-drug"]["entity_id"] is None
    assert rows["not-a-drug"]["match_method"] == "unmapped"


def test_zenodo_resolver_maps_brands_combinations_and_excludes_devices() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(unify.SCHEMA)
    conn.executescript(
        """
        CREATE TABLE drug_classes (id TEXT PRIMARY KEY, name_en TEXT, drugs TEXT, aliases TEXT);
        CREATE TABLE zenodo_ddi_2026 (drug_a TEXT, drug_b TEXT, interaction TEXT, source TEXT);
        CREATE TABLE rxnorm_concepts (rxcui TEXT PRIMARY KEY, name TEXT, tty TEXT);
        CREATE TABLE rxnorm_relations (rxcui1 TEXT, rel TEXT, rxcui2 TEXT, rela TEXT);
        INSERT INTO zenodo_ddi_2026 VALUES
            ('Augmentin', 'Acetaminophen and Codeine', 'interaction', 'zenodo');
        INSERT INTO zenodo_ddi_2026 VALUES
            ('(R)-warfarin', '14-Panel Toxicology Medicated Collection System', 'interaction', 'zenodo');
        INSERT INTO rxnorm_concepts VALUES
            ('100', 'Augmentin', 'BN'),
            ('101', 'amoxicillin', 'IN'),
            ('102', 'clavulanate', 'IN'),
            ('103', 'acetaminophen', 'IN'),
            ('104', 'codeine', 'IN'),
            ('105', 'warfarin', 'IN');
        INSERT INTO rxnorm_relations VALUES
            ('100', 'RO', '101', 'has_tradename'),
            ('100', 'RO', '102', 'has_tradename');
        """
    )

    counts = unify.build_drug_name_mapping(conn)
    rows = {
        row["raw_name"]: dict(row)
        for row in conn.execute(
            "SELECT raw_name, entity_type, entity_id, match_method "
            "FROM drug_name_mapping WHERE source = 'zenodo_ddi_2026'"
        )
    }
    components = {
        raw_name: [
            component["entity_id"]
            for component in conn.execute(
                "SELECT entity_id FROM drug_name_mapping_component "
                "WHERE source = 'zenodo_ddi_2026' AND raw_name = ? "
                "ORDER BY component_index",
                (raw_name,),
            )
        ]
        for raw_name, row in rows.items()
        if row["entity_type"] == "drug_ingredient"
    }

    assert counts == {"mapped": 3, "unmapped": 1}
    assert rows["Augmentin"]["match_method"] == "rxnorm_exact"
    assert components["Augmentin"] == ["101", "102"]
    assert rows["Acetaminophen and Codeine"]["match_method"] == "rxnorm_components"
    assert components["Acetaminophen and Codeine"] == ["103", "104"]
    assert rows["(R)-warfarin"]["entity_id"] == "105"
    assert rows["(R)-warfarin"]["match_method"] == "rxnorm_stereo_stripped"
    assert rows["14-Panel Toxicology Medicated Collection System"]["entity_type"] == "non_drug"
    assert rows["14-Panel Toxicology Medicated Collection System"]["match_method"] == "excluded_non_drug"
    conn.close()
def test_pharmgkb_brand_bridge_is_exact_and_ambiguous_brands_stay_reviewable() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(unify.SCHEMA)
    conn.executescript(
        """
        CREATE TABLE drug_classes (id TEXT PRIMARY KEY, name_en TEXT, drugs TEXT, aliases TEXT);
        CREATE TABLE zenodo_ddi_2026 (drug_a TEXT, drug_b TEXT, interaction TEXT, source TEXT);
        CREATE TABLE rxnorm_concepts (rxcui TEXT PRIMARY KEY, name TEXT, tty TEXT);
        CREATE TABLE rxnorm_relations (rxcui1 TEXT, rel TEXT, rxcui2 TEXT, rela TEXT);
        CREATE TABLE pharmgkb_drugs (
            name TEXT, generic_names TEXT, trade_names TEXT,
            brand_mixtures TEXT, type TEXT, rxnorm TEXT
        );
        INSERT INTO zenodo_ddi_2026 VALUES
            ('Biaxin XL', 'Cedax', 'interaction', 'zenodo');
        INSERT INTO rxnorm_concepts VALUES
            ('21212', 'clarithromycin', 'IN'),
            ('20492', 'ceftibuten', 'IN'),
            ('2194', 'cefuroxime', 'IN');
        INSERT INTO pharmgkb_drugs VALUES
            ('clarithromycin', '', 'Biaxin', '', 'Drug', '21212'),
            ('ceftibuten', '', 'Cedax', '', 'Drug', '20492'),
            ('cefuroxime', '', 'Cedax', '', 'Drug', '2194');
        """
    )

    counts = unify.build_drug_name_mapping(conn)
    rows = {
        row["raw_name"]: dict(row)
        for row in conn.execute(
            "SELECT raw_name, entity_id, match_method "
            "FROM drug_name_mapping WHERE source = 'zenodo_ddi_2026'"
        )
    }

    assert counts == {"mapped": 1, "unmapped": 1}
    assert rows["Biaxin XL"] == {
        "raw_name": "Biaxin XL",
        "entity_id": "21212",
        "match_method": "rxnorm_formulation_suffix",
    }
    assert rows["Cedax"]["entity_id"] is None
    assert rows["Cedax"]["match_method"] == "unmapped"
    review = conn.execute(
        "SELECT reason, status FROM drug_name_mapping_review "
        "WHERE source = 'zenodo_ddi_2026' AND raw_name = 'Cedax'"
    ).fetchone()
    assert dict(review) == {"reason": "unmapped", "status": "pending"}
    conn.close()





def test_ingredient_pairs_skips_self_pair_and_preserves_provenance() -> None:
    from backend.engine import Engine

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE interaction_unified (
            a_kind TEXT, a_id TEXT, b_kind TEXT, b_id TEXT,
            severity TEXT, effect TEXT, mechanism TEXT, evidence TEXT,
            confidence REAL, is_inferred INTEGER, pair_key TEXT PRIMARY KEY
        );
        CREATE TABLE drug_name_mapping (
            source TEXT, raw_name TEXT, normalized_name TEXT,
            entity_type TEXT, entity_id TEXT, rxcui TEXT,
            confidence REAL, match_method TEXT, reviewed INTEGER
        );
        INSERT INTO drug_name_mapping VALUES
            ('zenodo_ddi_2026', 'Ibuprofen', 'famotidine ibuprofen oral tablet',
             'drug_ingredient', '100', '100', 1.0, 'rxnorm_exact', 0);
        INSERT INTO drug_name_mapping VALUES
            ('zenodo_ddi_2026', 'Warfarin', 'warfarin oral tablet',
             'drug_ingredient', '200', '200', 1.0, 'rxnorm_exact', 0);
        INSERT INTO drug_name_mapping VALUES
            ('zenodo_ddi_2026', 'Uncertain', 'uncertain',
             'drug_ingredient', '300', '300', 0.9, 'rxnorm_token_exact', 0);
        INSERT INTO drug_name_mapping VALUES
            ('zenodo_ddi_2026', 'Reviewed', 'reviewed',
             'drug_ingredient', '400', '400', 1.0, 'manual_review', 1);
        INSERT INTO interaction_unified VALUES
            ('drug_ingredient', '100', 'drug_ingredient', '200',
             'major', 'Bleeding risk', 'Additive anticoagulation',
             '[{"source":"FDA labels","trust":1.0}]', 1.0, 0,
             'drug_ingredient:100|drug_ingredient:200');
        """
    )
    engine = Engine.__new__(Engine)
    engine.conn = conn
    engine.has_mapping_components = False
    engine.has_unified = True
    assert engine._ingredient_ids_for_input("ibuprofen") == ["100"]
    assert engine._ingredient_ids_for_input("warfarin") == ["200"]
    assert engine._ingredient_ids_for_input("uncertain") == []
    assert engine._ingredient_ids_for_input("reviewed") == ["400"]

    assert engine.ingredient_pairs(["100"], ["100"]) == []
    rows = engine.ingredient_pairs(["100"], ["200"])

    assert rows[0]["evidence"] == [{"source": "FDA labels", "trust": 1.0}]
    assert rows[0]["effect"] == "Bleeding risk"
    assert rows[0]["action"].startswith("Do not combine")
    conn.close()

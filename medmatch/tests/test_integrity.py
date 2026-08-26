"""Data integrity tests for the seeded SQLite DB.

Guard rails before large data-union imports (SUPP.AI 59K, DSLD, iDISK):
- seed counts and dedup invariants must hold
- referential integrity herb_id / class_id
- severity and trust ranges
- engine smoke: known matches + canonical interaction
"""
import sqlite3

import pytest

from backend.db import build_db, DB_PATH
from backend.engine import Engine

HERB_DRUG_PAIRS = 565   # unique herb-drug pairs (tapirro, translated EN)
DRUG_DRUG_RULES = 57    # 49 class-level + 8 drug-level FDA-labeling rules


@pytest.fixture(scope="session")
def conn():
    build_db()
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    yield c
    c.close()


def test_seed_counts(conn):
    assert conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0] == HERB_DRUG_PAIRS
    assert conn.execute("SELECT COUNT(*) FROM drug_drug").fetchone()[0] == DRUG_DRUG_RULES


def test_pair_keys_unique(conn):
    for table in ("interactions", "drug_drug"):
        total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        distinct = conn.execute(f"SELECT COUNT(DISTINCT pair_key) FROM {table}").fetchone()[0]
        assert distinct == total, f"{table}: duplicate pair_key"


def test_interaction_refs_resolve(conn):
    bad = conn.execute(
        "SELECT COUNT(*) FROM interactions i"
        " LEFT JOIN herbs h ON h.id = i.herb_id"
        " LEFT JOIN drug_classes c ON c.id = i.class_id"
        " WHERE h.id IS NULL OR c.id IS NULL"
    ).fetchone()[0]
    assert bad == 0


def test_drug_drug_class_refs_resolve(conn):
    bad = conn.execute(
        "SELECT COUNT(*) FROM drug_drug d"
        " LEFT JOIN drug_classes c1 ON c1.id = d.cls_a"
        " LEFT JOIN drug_classes c2 ON c2.id = d.cls_b"
        " WHERE (d.cls_a IS NOT NULL AND c1.id IS NULL)"
        "    OR (d.cls_b IS NOT NULL AND c2.id IS NULL)"
    ).fetchone()[0]
    assert bad == 0


def test_severity_values(conn):
    for table in ("interactions", "drug_drug"):
        rows = conn.execute(f"SELECT severity FROM {table}").fetchall()
        assert rows
        assert all(r["severity"] in {"major", "moderate", "minor"} for r in rows)


def test_trust_range(conn):
    for table in ("interactions", "drug_drug"):
        rows = conn.execute(f"SELECT trust FROM {table}").fetchall()
        assert rows
        assert all(0.0 <= r["trust"] <= 1.0 for r in rows)


def test_seed_trust_levels(conn):
    # tapirro seeds: 0.9; FDA-labeling rules: 1.0 (plan3 tiers)
    assert conn.execute("SELECT COUNT(*) FROM interactions WHERE trust = 0.9").fetchone()[0] == HERB_DRUG_PAIRS
    assert conn.execute("SELECT COUNT(*) FROM drug_drug WHERE trust = 1.0").fetchone()[0] == DRUG_DRUG_RULES


def test_engine_match_known_items():
    eng = Engine()
    assert any(r["kind"] == "herb" and r["id"] == "curcuma" for r in eng.match("turmeric"))
    assert any(r["kind"] == "drug_class" and r["id"] == "anticoagulantes" for r in eng.match("warfarin"))


def test_analyze_smoke():
    eng = Engine()
    out = eng.analyze([{"name": "St. John's Wort"}, {"name": "warfarin"}])
    # analyze returns the full 7-layer output: legacy keys + inference engines
    # (cascades/schedule/qt_risk/electrolytes/beers per brain.md layer 4)
    assert {"matched", "interactions", "unmatched", "depletions",
            "cascades", "schedule", "qt_risk", "electrolytes", "beers"} == set(out)
    # hypericum + anticoagulants is the canonical major interaction in the dataset
    assert any(i["severity"] == "major" for i in out["interactions"])


def test_suppai_integrity(conn):
    has = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='suppai_interactions'"
    ).fetchone()
    if not has:
        pytest.skip("suppai table not present")
    total = conn.execute("SELECT COUNT(*) FROM suppai_interactions").fetchone()[0]
    if total == 0:
        pytest.skip("no suppai rows")
    distinct = conn.execute("SELECT COUNT(DISTINCT pair_key) FROM suppai_interactions").fetchone()[0]
    assert distinct == total
    assert conn.execute("SELECT COUNT(*) FROM suppai_interactions WHERE trust != 0.9").fetchone()[0] == 0
    bad = conn.execute(
        "SELECT COUNT(*) FROM suppai_interactions s"
        " LEFT JOIN herbs h ON h.id = s.herb_id"
        " LEFT JOIN drug_classes c ON c.id = s.class_id"
        " WHERE h.id IS NULL OR (s.class_id IS NOT NULL AND c.id IS NULL)"
    ).fetchone()[0]
    assert bad == 0


def test_idisk_integrity(conn):
    has = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='idisk_interactions'"
    ).fetchone()
    if not has:
        pytest.skip("idisk table not present")
    total = conn.execute("SELECT COUNT(*) FROM idisk_interactions").fetchone()[0]
    if total == 0:
        pytest.skip("no idisk rows")
    distinct = conn.execute("SELECT COUNT(DISTINCT pair_key) FROM idisk_interactions").fetchone()[0]
    assert distinct == total
    assert conn.execute("SELECT COUNT(*) FROM idisk_interactions WHERE trust != 0.7").fetchone()[0] == 0
    bad = conn.execute(
        "SELECT COUNT(*) FROM idisk_interactions i"
        " LEFT JOIN herbs h ON h.id = i.herb_id"
        " LEFT JOIN drug_classes c ON c.id = i.class_id"
        " WHERE h.id IS NULL OR c.id IS NULL"
    ).fetchone()[0]
    assert bad == 0


def test_drug_food_integrity(conn):
    assert conn.execute("SELECT COUNT(*) FROM foods").fetchone()[0] == 10
    total = conn.execute("SELECT COUNT(*) FROM drug_food").fetchone()[0]
    assert total >= 30
    distinct = conn.execute("SELECT COUNT(DISTINCT pair_key) FROM drug_food").fetchone()[0]
    assert distinct == total
    assert conn.execute("SELECT COUNT(*) FROM drug_food WHERE trust != 1.0").fetchone()[0] == 0
    bad = conn.execute(
        "SELECT COUNT(*) FROM drug_food f"
        " LEFT JOIN drug_classes c ON c.id = f.cls_a"
        " LEFT JOIN foods fd ON fd.id = f.food_id"
        " WHERE c.id IS NULL OR fd.id IS NULL"
    ).fetchone()[0]
    assert bad == 0


def test_cyp_roles_integrity(conn):
    total = conn.execute("SELECT COUNT(*) FROM cyp_roles").fetchone()[0]
    assert total >= 70
    assert conn.execute(
        "SELECT COUNT(*) FROM cyp_roles WHERE role NOT IN ('substrate','inhibitor','inducer')"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM cyp_roles WHERE enzyme NOT IN ('1A2','2C9','2C19','2D6','3A4','p_gp')"
    ).fetchone()[0] == 0
    bad = conn.execute(
        "SELECT COUNT(*) FROM cyp_roles c"
        " LEFT JOIN drug_classes dc ON dc.id = c.entity_id AND c.entity_type = 'drug_class'"
        " LEFT JOIN herbs h ON h.id = c.entity_id AND c.entity_type = 'herb'"
        " WHERE (c.entity_type = 'drug_class' AND dc.id IS NULL)"
        "    OR (c.entity_type = 'herb' AND h.id IS NULL)"
    ).fetchone()[0]
    assert bad == 0

def test_herb_herb_integrity(conn):
    has = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='herb_herb_evidence'"
    ).fetchone()
    if not has:
        pytest.skip("herb_herb table not present")
    total = conn.execute("SELECT COUNT(*) FROM herb_herb_evidence").fetchone()[0]
    if total == 0:
        pytest.skip("no herb_herb rows")
    distinct = conn.execute("SELECT COUNT(DISTINCT pair_key) FROM herb_herb_evidence").fetchone()[0]
    assert distinct == total
    assert conn.execute("SELECT COUNT(*) FROM herb_herb_evidence WHERE trust != 0.9").fetchone()[0] == 0
    bad = conn.execute(
        "SELECT COUNT(*) FROM herb_herb_evidence hh"
        " LEFT JOIN herbs h1 ON h1.id = hh.herb_a"
        " LEFT JOIN herbs h2 ON h2.id = hh.herb_b"
        " WHERE h1.id IS NULL OR h2.id IS NULL"
    ).fetchone()[0]
    assert bad == 0

def test_dailymed_integrity(conn):
    has = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='dailymed_interactions'"
    ).fetchone()
    if not has:
        pytest.skip("dailymed table not present")
    total = conn.execute("SELECT COUNT(*) FROM dailymed_interactions").fetchone()[0]
    if total == 0:
        pytest.skip("no dailymed rows")
    distinct = conn.execute("SELECT COUNT(DISTINCT pair_key) FROM dailymed_interactions").fetchone()[0]
    assert distinct == total
    assert conn.execute("SELECT COUNT(*) FROM dailymed_interactions WHERE trust != 1.0").fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM dailymed_interactions WHERE severity NOT IN ('major','moderate','minor')"
    ).fetchone()[0] == 0
    bad = conn.execute(
        "SELECT COUNT(*) FROM dailymed_interactions d"
        " LEFT JOIN drug_classes c1 ON c1.id = d.cls_src"
        " LEFT JOIN drug_classes c2 ON c2.id = d.cls_mentioned"
        " WHERE c1.id IS NULL OR c2.id IS NULL"
    ).fetchone()[0]
    assert bad == 0

def test_ddinter_integrity(conn):
    has = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ddinter_interactions'"
    ).fetchone()
    if not has:
        pytest.skip("ddinter table not present")
    total = conn.execute("SELECT COUNT(*) FROM ddinter_interactions").fetchone()[0]
    if total == 0:
        pytest.skip("no ddinter rows")
    distinct = conn.execute("SELECT COUNT(DISTINCT pair_key) FROM ddinter_interactions").fetchone()[0]
    assert distinct == total
    assert conn.execute("SELECT COUNT(*) FROM ddinter_interactions WHERE trust != 0.9").fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM ddinter_interactions WHERE severity NOT IN ('major','moderate','minor')"
    ).fetchone()[0] == 0
    bad = conn.execute(
        "SELECT COUNT(*) FROM ddinter_interactions d"
        " LEFT JOIN drug_classes c1 ON c1.id = d.cls_a"
        " LEFT JOIN drug_classes c2 ON c2.id = d.cls_b"
        " WHERE c1.id IS NULL OR c2.id IS NULL"
    ).fetchone()[0]
    assert bad == 0

def test_depletions_integrity(conn):
    has = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='depletions'"
    ).fetchone()
    if not has:
        pytest.skip("depletions table not present")
    total = conn.execute("SELECT COUNT(*) FROM depletions").fetchone()[0]
    if total == 0:
        pytest.skip("no depletion rows")
    assert total == 21
    assert conn.execute(
        "SELECT COUNT(*) FROM depletions WHERE severity NOT IN ('major','moderate','minor')"
    ).fetchone()[0] == 0
    bad = conn.execute(
        "SELECT COUNT(*) FROM depletions d"
        " LEFT JOIN drug_classes c1 ON c1.id = d.cls_a"
        " WHERE c1.id IS NULL"
        "    OR (d.cls_b IS NOT NULL AND d.cls_b NOT IN (SELECT id FROM drug_classes))"
    ).fetchone()[0]
    assert bad == 0

def test_drugfood_evidence_integrity(conn):
    has = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='drugfood_evidence'"
    ).fetchone()
    if not has:
        pytest.skip("drugfood_evidence table not present")
    total = conn.execute("SELECT COUNT(*) FROM drugfood_evidence").fetchone()[0]
    if total == 0:
        pytest.skip("no drugfood_evidence rows")
    distinct = conn.execute("SELECT COUNT(DISTINCT pair_key) FROM drugfood_evidence").fetchone()[0]
    assert distinct == total
    assert conn.execute("SELECT COUNT(*) FROM drugfood_evidence WHERE trust != 0.8").fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM drugfood_evidence WHERE severity NOT IN ('major','moderate','minor')"
    ).fetchone()[0] == 0
    bad = conn.execute(
        "SELECT COUNT(*) FROM drugfood_evidence d"
        " LEFT JOIN drug_classes c ON c.id = d.cls_a"
        " LEFT JOIN foods f ON f.id = d.food_id"
        " WHERE c.id IS NULL OR f.id IS NULL"
    ).fetchone()[0]
    assert bad == 0

def test_herb_constituents_integrity(conn):
    has = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='herb_constituents'"
    ).fetchone()
    if not has:
        pytest.skip("herb_constituents table not present")
    total = conn.execute("SELECT COUNT(*) FROM herb_constituents").fetchone()[0]
    if total == 0:
        pytest.skip("no herb_constituents rows")
    assert total >= 30
    assert conn.execute("SELECT COUNT(*) FROM herb_constituents WHERE cid IS NULL").fetchone()[0] == 0
    bad = conn.execute(
        "SELECT COUNT(*) FROM herb_constituents h"
        " LEFT JOIN herbs hr ON hr.id = h.herb_id"
        " WHERE hr.id IS NULL"
    ).fetchone()[0]
    assert bad == 0

def test_unified_integrity(conn):
    has = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='interaction_unified'"
    ).fetchone()
    if not has:
        pytest.skip("interaction_unified table not present")
    total = conn.execute("SELECT COUNT(*) FROM interaction_unified").fetchone()[0]
    if total == 0:
        pytest.skip("no unified rows")
    assert total >= 20000
    # pair_key is PK -> unique
    assert conn.execute(
        "SELECT COUNT(*) FROM interaction_unified WHERE severity NOT IN ('major','moderate','minor')"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM interaction_unified WHERE confidence < 0.0 OR confidence > 1.0"
    ).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM standard_ingredient").fetchone()[0] >= 1200
    assert conn.execute("SELECT COUNT(*) FROM ingredient_synonyms").fetchone()[0] >= 6000
    # canonical pair must have >= 2 evidence sources
    r = conn.execute(
        "SELECT evidence FROM interaction_unified"
        " WHERE pair_key = 'drug_class:anticoagulantes|herb:hypericum'"
    ).fetchone()
    assert r is not None and len(__import__("json").loads(r[0])) >= 2

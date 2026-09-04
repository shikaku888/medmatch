"""Golden behavior checks for the first MedMatch release slice."""
from __future__ import annotations

import asyncio
import json
import sqlite3

from backend.product_index import build as build_product_index
from backend.scanner import personalization
from backend.engine import Engine
from backend.scanner.herbal_skincare import analyze_skincare_routine_conflicts
from backend.scanner.parsing import parse_ingredients_text
from backend.scanner.medmatch_bridge import normalize_ingredient
from backend.scanner import router as scanner_router
from backend.scanner.router import (
    _create_scan_draft,
    _get_scan_draft,
    batch_scan,
    compute_med_match,
    medmatch_check,
    merge_med_match_assessment,
    normalize_product_scan_result,
    scan_draft_confirm,
)
from backend.scanner.storage import ScannerDB


def _disable_research_fetch(monkeypatch) -> None:
    async def no_research(*_args, **_kwargs):
        return None

    monkeypatch.setattr(personalization, "get_pubmed_research", no_research)


def test_hypertension_profile_flags_high_sodium_product(monkeypatch) -> None:
    _disable_research_fetch(monkeypatch)
    assessment = asyncio.run(
        personalization.assess_product_match(
            {
                "productType": "food",
                "ingredientsText": "Potato, salt",
                "ingredientsList": ["Potato", "Salt"],
                "nutrition": {"sodium": 800},
            },
            {"dietType": "low_sodium", "specialConditions": ["hypertension"]},
        )
    )

    assert assessment["status"] == "warning"
    assert assessment["score"] == 80
    assert [warning["id"] for warning in assessment["warnings"]] == ["warn_hypertension_sodium"]
    assert assessment["warnings"][0]["matchedItem"] == "800mg Sodium"


def test_elderly_profile_combines_beers_qt_and_electrolyte_findings() -> None:
    engine = Engine()
    try:
        result = engine.analyze(
            [{"name": "Citalopram"}, {"name": "Amiodarone"}, {"name": "Furosemide"}],
            {"age": 72, "gender": "female", "kidneyFunction": "moderate_impairment"},
        )
    finally:
        engine.conn.close()

    assert {finding["label"] for finding in result["beers"]} == {
        "Amiodarone",
        "SSRI antidepressants",
    }
    assert result["qt_risk"][0]["level"] == "high"
    assert "age >= 65" in result["qt_risk"][0]["factors"]
    assert "female sex" in result["qt_risk"][0]["factors"]
    assert "renal impairment (electrolyte loss raises torsades risk)" in result["qt_risk"][0]["factors"]
    assert result["electrolytes"][0]["electrolyte"] == "Potassium"
    assert result["electrolytes"][0]["sources"] == ["Furosemide"]


def test_pregnancy_profile_flags_retinoid_as_high_risk(monkeypatch) -> None:
    _disable_research_fetch(monkeypatch)
    assessment = asyncio.run(
        personalization.assess_product_match(
            {
                "productType": "supplement",
                "ingredientsText": "Water, Retinol, Glycerin",
                "ingredientsList": ["Water", "Retinol", "Glycerin"],
            },
            {"dietType": "omnivore", "specialConditions": ["pregnant"]},
        )
    )

    assert assessment["status"] == "danger"
    assert assessment["score"] == 55
    assert [warning["id"] for warning in assessment["warnings"]] == ["warn_pregnancy_retinol"]


def test_penicillin_allergy_flags_amoxicillin_product() -> None:
    assessment = asyncio.run(
        personalization.assess_product_match(
            {
                "ingredientsText": "amoxicillin",
                "ingredientsList": ["amoxicillin"],
                "allergens": [],
                "labels": [],
            },
            {"allergies": ["penicillin"]},
        )
    )

    assert assessment["status"] == "danger"
    assert assessment["warnings"][0]["category"] == "allergy"
    assert assessment["warnings"][0]["matchedItem"] == "amoxicillin"
    assert assessment["warnings"][0]["level"] == "high"


def test_eczema_profile_separates_fragrance_and_alcohol_warnings(monkeypatch) -> None:
    _disable_research_fetch(monkeypatch)
    assessment = asyncio.run(
        personalization.assess_product_match(
            {
                "productType": "cosmetic",
                "ingredientsText": "Water, Fragrance, Alcohol Denat",
                "ingredientsList": ["Water", "Fragrance", "Alcohol Denat"],
                "cosmetic": {"hasFragrance": True, "hasAlcohol": True},
            },
            {"dietType": "omnivore", "specialConditions": ["eczema"]},
        )
    )

    assert assessment["status"] == "warning"
    assert assessment["score"] == 60
    assert {warning["id"] for warning in assessment["warnings"]} == {
        "warn_sensitive_fragrance",
        "warn_sensitive_alcohol",
    }


def test_product_scan_result_has_stable_envelope() -> None:
    result = normalize_product_scan_result(
        {
            "productName": "Milk Thistle",
            "ingredientsList": ["Milk Thistle"],
            "matchAssessment": {"status": "safe", "score": 100},
        },
        source="local_scan",
    )

    assert result["barcode"].startswith("SCAN_")
    assert result["productName"] == "Milk Thistle"
    assert result["productType"] == "supplement"
    assert result["ingredientsText"] == "Milk Thistle"
    assert result["ingredientsList"] == ["Milk Thistle"]
    assert result["matchAssessment"]["status"] == "safe"
    assert result["source"] == "local_scan"
    assert result["scannedAt"]


def test_medication_findings_promote_status_without_profile_warning_leak() -> None:
    assessment = merge_med_match_assessment(
        {"status": "safe", "score": 100, "warnings": []},
        {"interactions": [{"severity": "moderate"}]},
    )

    assert assessment["status"] == "warning"
    assert assessment["score"] == 90
    assert assessment["warnings"] == []
    assert "medication interaction" in assessment["medicationSummary"]


def test_medmatch_check_preserves_unmatched_inputs() -> None:
    result = asyncio.run(
        medmatch_check(
            {
                "items": [
                    {"name": "zzzxqv-unmatched"},
                    {"name": "warfarin"},
                ]
            }
        )
    )

    assert result["result"] == "unknown_unmatched"
    assert result["unmatched"] == ["zzzxqv-unmatched"]
    assert "safe" not in result["message"].lower()

def test_product_entity_filter_keeps_excipients_and_medication_only_pairs_out() -> None:
    result = asyncio.run(
        compute_med_match(
            ["Milk Thistle", "Water", "Magnesium Stearate"],
            {"medications": ["Amlodipine", "Metformin"]},
            "supplement",
        )
    )

    assert any(item["kind"] == "herb" for item in result["matched"])
    assert not any(item["input"] in {"Water", "Magnesium Stearate"} for item in result["matched"])
    assert all(
        any(side.get("kind") == "herb" for side in (interaction.get("a") or {}, interaction.get("b") or {}))
        for interaction in result["interactions"]
    )


def test_skincare_audit_accepts_string_actives() -> None:
    result = analyze_skincare_routine_conflicts(
        [{"name": "AHA serum", "activeIngredients": ["Glycolic Acid"], "timeOfDay": "pm"}],
        ["Retinol"],
    )

    assert result["conflictCount"] == 1
    assert result["overallRoutineSafetyScore"] < 100


def test_draft_confirmation_does_not_write_history(tmp_path, monkeypatch) -> None:
    storage_path = tmp_path / "scanner.json"
    monkeypatch.setenv("SCANNER_STORAGE_PATH", str(storage_path))
    db = ScannerDB(token="golden")
    before = len(db.get_history())
    draft = _create_scan_draft(
        {
            "inputType": "code",
            "inputValue": "0033964039711",
            "product": {"productName": "Milk Thistle", "productType": "supplement"},
            "ingredientsList": ["Milk Thistle"],
            "ingredientsText": "Milk Thistle",
            "source": "product-index:ean",
        }
    )

    assert _get_scan_draft(draft["id"])["id"] == draft["id"]
    confirmed = asyncio.run(scan_draft_confirm(draft["id"], {"ingredientsList": ["Milk Thistle"]}))

    assert confirmed["confirmed"] is True
    assert len(db.get_history()) == before
    assert _get_scan_draft(draft["id"]) is None
def test_dsld_barcode_index_populates_matched_entities() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE ndc_products (
            product_ndc TEXT, brand_name TEXT, generic_name TEXT,
            labeler TEXT, ingredients TEXT
        );
        CREATE TABLE dsld_products (
            barcode TEXT, dsld_id TEXT, name TEXT, brand TEXT, ingredients TEXT
        );
        CREATE TABLE herbs (
            id TEXT PRIMARY KEY, name_en TEXT, name_es TEXT,
            scientific TEXT, aliases TEXT
        );
        CREATE TABLE drug_classes (
            id TEXT PRIMARY KEY, name_en TEXT, drugs TEXT, aliases TEXT
        );
        CREATE TABLE foods (
            id TEXT PRIMARY KEY, name_en TEXT, aliases TEXT
        );
        CREATE TABLE ingredient_synonyms (
            kind TEXT, entity_id TEXT, synonym TEXT, source TEXT,
            PRIMARY KEY (kind, entity_id, synonym)
        );
        """
    )
    conn.execute(
        "INSERT INTO herbs VALUES (?,?,?,?,?)",
        ("cardo_mariano", "Milk Thistle", "Cardo mariano", "", '["milk thistle"]'),
    )
    conn.execute(
        "INSERT INTO ingredient_synonyms VALUES (?,?,?,?)",
        ("herb", "cardo_mariano", "milk thistle", "fixture"),
    )
    conn.execute(
        "INSERT INTO dsld_products VALUES (?,?,?,?,?)",
        ("123456789012", "fixture-1", "Milk Thistle", "Fixture Brand", "Milk Thistle; Water"),
    )

    build_product_index(conn)

    row = conn.execute(
        "SELECT code_type, matched FROM product_index WHERE code = ?",
        ("123456789012",),
    ).fetchone()
    ean = conn.execute(
        "SELECT code_type, matched FROM product_index WHERE code = ?",
        ("0123456789012",),
    ).fetchone()
    assert row[0] == "upc"
    assert json.loads(row[1])[0]["id"] == "cardo_mariano"
    assert ean[0] == "ean"
    assert json.loads(ean[1])[0]["id"] == "cardo_mariano"
    conn.close()

def test_barcode_found_batch_scan_normalizes_product_and_persists(monkeypatch) -> None:
    class FakeDB:
        def __init__(self):
            self.saved = []

        def get_user_profile(self):
            return {"medications": []}

        def add_history(self, result):
            self.saved.append(result)

    fake_db = FakeDB()
    monkeypatch.setattr(scanner_router, "get_user_db", lambda: fake_db)
    monkeypatch.setattr(
        scanner_router,
        "_lookup_product_index",
        lambda code: {
            "barcode": code,
            "productName": "Milk Thistle",
            "productType": "supplement",
            "ingredientsText": "Milk Thistle",
            "ingredientsList": ["Milk Thistle"],
            "source": "product-index:test",
        },
    )

    result = asyncio.run(batch_scan({"barcodes": ["123456789012"]}))

    assert result["count"] == 1
    assert result["results"][0]["productName"] == "Milk Thistle"
    assert result["results"][0]["source"] == "product-index:test"
    assert len(fake_db.saved) == 1


def test_barcode_missing_batch_scan_returns_empty_without_history(monkeypatch) -> None:
    class FakeDB:
        def __init__(self):
            self.saved = []

        def get_user_profile(self):
            return {"medications": []}

        def add_history(self, result):
            self.saved.append(result)

    fake_db = FakeDB()
    monkeypatch.setattr(scanner_router, "get_user_db", lambda: fake_db)
    monkeypatch.setattr(scanner_router, "_lookup_product_index", lambda _code: None)
    monkeypatch.setattr(scanner_router, "_resolve_barcode_product", lambda *_args: None)

    result = asyncio.run(batch_scan({"barcodes": ["000000000000"]}))

    assert result == {"results": [], "count": 0}
    assert fake_db.saved == []


def test_ocr_text_parser_marks_valid_ingredients_complete() -> None:
    result = parse_ingredients_text(
        "Hydrating Serum\nIngredients: Water, Niacinamide, Glycerin"
    )

    assert result["productName"] == "Hydrating Serum"
    assert result["hasIngredientSection"] is True
    assert result["ingredientsList"] == ["Water", "Niacinamide", "Glycerin"]


def test_ocr_text_parser_marks_front_label_without_ingredients_incomplete() -> None:
    result = parse_ingredients_text("Brightening Serum\nVitamin C")

    assert result["hasIngredientSection"] is False
    assert result["ingredientsList"] == ["Brightening Serum", "Vitamin C"]

def test_ocr_text_parser_handles_japanese_ingredient_header_and_delimiters() -> None:
    result = parse_ingredients_text(
        "Dear-Natura Style\n原材料名：グルコン酸亜鉛、セルロース、ビタミンC、ゼラチン"
    )

    assert result["hasIngredientSection"] is True
    assert result["ingredientsList"] == ["グルコン酸亜鉛", "セルロース", "ビタミンC", "ゼラチン"]
    assert result["allergens"] == ["Gelatin"]


def test_ocr_text_parser_normalizes_full_width_japanese_punctuation() -> None:
    result = parse_ingredients_text("商品名\n原材料名：DHA･EPA、ビタミンＤ")

    assert result["ingredientsList"] == ["DHA・EPA", "ビタミンD"]

def test_medical_vocabulary_resolves_japanese_and_chinese_drug_names() -> None:
    japanese = normalize_ingredient("イブプロフェン", live=False, preferred_kinds=("drug_class",))
    chinese = normalize_ingredient("阿莫西林", live=False, preferred_kinds=("drug_class",))

    assert japanese and japanese["id"] == "aines"
    assert chinese and chinese["id"] == "antibioticos"
    assert japanese["matched_alias"] == "イブプロフェン"
    assert chinese["matched_alias"] == "阿莫西林"


def test_canonical_supplement_alias_precedes_duplicate_suppai_mapping() -> None:
    hit = normalize_ingredient("St Johns Wort", live=False)

    assert hit and hit["kind"] == "herb"
    assert hit["id"] == "hypericum"


def test_priority_interaction_cases_are_detected() -> None:
    cases = (
        ("sertraline", "ibuprofen", "major"),
        ("levothyroxine", "calcium", "moderate"),
        ("lisinopril", "potassium", "moderate"),
        ("metformin", "alcohol", "major"),
    )
    engine = Engine()
    try:
        for left, right, expected_severity in cases:
            result = engine.analyze([{"name": left}, {"name": right}])
            assert result["result"] == "interaction_found", (left, right, result)
            assert any(
                interaction["severity"] == expected_severity
                for interaction in result["interactions"]
            ), (left, right, result["interactions"])
    finally:
        engine.conn.close()

def test_food_and_supplement_interactions_use_real_rules() -> None:
    food_result = asyncio.run(
        medmatch_check({"items": [{"name": "grapefruit"}, {"name": "simvastatin"}]})
    )
    supplement_result = asyncio.run(
        medmatch_check({"items": [{"name": "St Johns Wort"}, {"name": "warfarin"}]})
    )

    assert food_result["result"] == "interaction_found"
    assert food_result["interactions"][0]["type"] == "drug-food"
    assert food_result["interactions"][0]["severity"] == "major"
    assert supplement_result["result"] == "interaction_found"
    assert supplement_result["interactions"][0]["type"] == "herb-drug"
    assert supplement_result["interactions"][0]["severity"] == "major"


def test_batch_scan_limits_to_ten_items_and_persists_post_scan_results(monkeypatch) -> None:
    class FakeDB:
        def __init__(self):
            self.saved = []

        def get_user_profile(self):
            return {"medications": []}

        def add_history(self, result):
            self.saved.append(result)

    fake_db = FakeDB()
    monkeypatch.setattr(scanner_router, "get_user_db", lambda: fake_db)
    monkeypatch.setattr(
        scanner_router,
        "_lookup_product_index",
        lambda code: {
            "barcode": code,
            "productName": f"Product {code}",
            "productType": "supplement",
            "ingredientsText": "Milk Thistle",
            "ingredientsList": ["Milk Thistle"],
            "source": "product-index:test",
        },
    )

    result = asyncio.run(batch_scan({"barcodes": [f"00{index:010d}" for index in range(12)]}))

    assert result["count"] == 10
    assert len(result["results"]) == 10
    assert len(fake_db.saved) == 10
    assert all(item["source"] == "product-index:test" for item in fake_db.saved)

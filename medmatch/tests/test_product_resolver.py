from __future__ import annotations

import asyncio
import json
import sqlite3

from backend.scanner import resolver
from backend.scanner.parsing import detect_allergens, parse_ingredients_text
from backend.scanner.personalization import analyze_ingredient_safety, assess_product_match


def test_resolver_returns_unknown_without_identity() -> None:
    result = asyncio.run(resolver.resolve_product())
    assert result["status"] == "unknown"
    assert result["product"] is None
    assert "safety clearance" in result["limitations"][0].lower()


def test_resolver_prefers_local_index_before_cache_and_providers(monkeypatch) -> None:
    local = {
        "barcode": "012345678901",
        "productName": "Local product",
        "productType": "food",
        "ingredientsList": ["rice"],
        "source": "product-index:upc",
    }
    monkeypatch.setattr(resolver, "_local_barcode", lambda _barcode: local)
    monkeypatch.setattr(resolver, "_read_cache", lambda _key: (_ for _ in ()).throw(AssertionError("cache called")))
    monkeypatch.setattr(resolver, "get_product_from_off", lambda *_args: (_ for _ in ()).throw(AssertionError("provider called")))

    result = asyncio.run(resolver.resolve_product(barcode="012345678901"))
    assert result["status"] == "found"
    assert result["sources"] == ["product-index:upc"]
    assert result["product"]["ingredientsList"] == ["rice"]


def test_resolver_caches_normalized_provider_result_separately(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PRODUCT_CACHE_DB", str(tmp_path / "product-cache.db"))
    monkeypatch.setattr(resolver, "_local_barcode", lambda _barcode: None)
    calls = {"off": 0}

    async def fake_off(*_args):
        calls["off"] += 1
        return {
            "productName": "Provider product",
            "brand": "Example",
            "productType": "food",
            "ingredientsText": "Rice; salt",
            "ingredientsList": ["Rice", "salt"],
            "rawProviderPayload": {"must_not_be_cached": True},
            "source": "openfoodfacts",
        }

    async def no_provider(*_args, **_kwargs):
        return None

    monkeypatch.setattr(resolver, "get_product_from_off", fake_off)
    monkeypatch.setattr(resolver, "search_openfda_ndc", no_provider)
    monkeypatch.setattr(resolver, "search_openfoodfacts_name", no_provider)
    monkeypatch.setattr(resolver, "search_usda_food", no_provider)
    monkeypatch.setattr(resolver, "_lnhpd", no_provider)
    monkeypatch.setattr(resolver, "_dsld_barcode", lambda _barcode: None)

    first = asyncio.run(resolver.resolve_product(barcode="999999999999"))
    second = asyncio.run(resolver.resolve_product(barcode="999999999999"))
    assert first["status"] == second["status"] == "found"
    assert calls["off"] == 1

    conn = sqlite3.connect(tmp_path / "product-cache.db")
    row = conn.execute("SELECT product_json, source, ttl_seconds, sha256 FROM product_cache").fetchone()
    conn.close()
    assert row[1] == "openfoodfacts"
    assert row[2] > 0
    assert "rawProviderPayload" not in row[0]
    assert len(row[3]) == 64

def test_unknown_product_is_added_to_privacy_safe_queue(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PRODUCT_CACHE_DB", str(tmp_path / "product-cache.db"))
    monkeypatch.setattr(resolver, "_local_barcode", lambda _barcode: None)

    async def no_provider(*_args, **_kwargs):
        return None

    monkeypatch.setattr(resolver, "get_product_from_off", no_provider)
    monkeypatch.setattr(resolver, "search_usda_food", no_provider)
    monkeypatch.setattr(resolver, "search_openfda_ndc", no_provider)
    monkeypatch.setattr(resolver, "_lnhpd", no_provider)
    monkeypatch.setattr(resolver, "_dsld_barcode", lambda _barcode: None)

    asyncio.run(resolver.resolve_product(barcode="000111222333"))
    asyncio.run(resolver.resolve_product(barcode="000111222333"))
    queued = resolver.list_unresolved()
    assert queued[0]["inputType"] == "barcode"
    assert queued[0]["attempts"] == 2
    assert "000111222333" not in queued[0]["lookupKey"]


def test_japanese_allergen_and_additive_terms_are_detected(monkeypatch) -> None:
    parsed = parse_ingredients_text("日本食品\n原材料名：米、落花生、着色料、保存料")
    assert parsed["allergens"] == ["Peanuts"]
    assert "着色料" in parsed["ingredientsList"]

    safety = analyze_ingredient_safety(["着色料", "保存料"])
    assert [item["hazardLevel"] for item in safety] == ["caution", "caution"]

    async def no_research(*_args, **_kwargs):
        return None

    from backend.scanner import personalization
    monkeypatch.setattr(personalization, "get_pubmed_research", no_research)
    assessment = asyncio.run(
        assess_product_match(
            {
                "productType": "food",
                "ingredientsText": "米、落花生",
                "ingredientsList": ["米", "落花生"],
                "allergens": [],
                "labels": [],
                "nutrition": {},
            },
            {"allergies": ["peanut"], "customAllergens": [], "dietType": "omnivore"},
        )
    )
    assert any(w["category"] == "allergy" and w["level"] == "high" for w in assessment["warnings"])


def test_japanese_negative_claim_does_not_create_allergen() -> None:
    assert detect_allergens("小麦不使用・乳成分不使用") == []

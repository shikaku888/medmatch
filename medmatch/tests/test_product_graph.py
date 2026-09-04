from __future__ import annotations

import asyncio

import pytest

from backend.scanner import product_graph
from backend.scanner.resolver import resolve_product


def test_observation_requires_explicit_product_consent(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PRODUCT_GRAPH_DB", str(tmp_path / "graph.db"))

    with pytest.raises(ValueError, match="explicit product-facts consent"):
        product_graph.submit_observation(
            {"market": "us", "language": "en-us", "barcode": "012345678901", "productName": "Example"}
        )


def test_approved_multilingual_observations_create_cross_market_candidate(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PRODUCT_GRAPH_DB", str(tmp_path / "graph.db"))
    base = {
        "brand": "Example Brand",
        "ingredientsText": "Water, Glycerin",
        "shareProductFacts": True,
        "consentVersion": "product-facts-v1",
        "imageFingerprint": "ahash:0123456789abcdef",
        "image": "must-not-be-stored",
    }
    us = product_graph.submit_observation(
        {**base, "market": "us", "language": "en-us", "barcode": "012345678901", "productName": "Hydrating Cream"}
    )
    jp = product_graph.submit_observation(
        {**base, "market": "jp", "language": "ja-jp", "barcode": "4901234567890", "productName": "保湿クリーム"}
    )

    assert us["status"] == "pending_review"
    assert jp["rawImageStored"] is False
    assert product_graph.list_observations()[0]["status"] == "pending"

    us_sku = product_graph.approve_observation(us["observationId"])
    jp_sku = product_graph.approve_observation(jp["observationId"])
    assert us_sku["status"] == "approved"
    assert jp_sku["status"] == "approved"

    candidates = product_graph.suggest_cross_market_links()
    assert len(candidates) == 1
    assert {
        candidates[0]["left"]["market_code"],
        candidates[0]["right"]["market_code"],
    } == {"jp", "us"}
    assert candidates[0]["status"] == "candidate"

    link_id = candidates[0]["linkId"]
    resolved = asyncio.run(resolve_product(barcode="012345678901", country="us"))
    assert resolved["sources"] == ["community_verified"]
    reused = product_graph.lookup_approved(barcode="012345678901", market="us")
    assert reused["productName"] == "Hydrating Cream"
    image_reused = product_graph.lookup_approved(
        image_fingerprint="ahash:0123456789abcdef", market="us"
    )
    assert image_reused["identityCode"] == "mm_img_0123456789ab"
    assert reused["source"] == "community_verified"
    assert image_reused["matchConfidence"] == 0.98
    assert image_reused["matchReasons"] == ["perceptual_image_fingerprint"]
    assert product_graph.review_cross_market_link(link_id, "confirmed")["status"] == "confirmed"
    assert product_graph.list_cross_market_links("confirmed")[0]["link_id"] == link_id


def test_product_graph_keeps_markets_separate_when_formula_differs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PRODUCT_GRAPH_DB", str(tmp_path / "graph.db"))
    common = {"brand": "Example Brand", "shareProductFacts": True}
    first = product_graph.submit_observation(
        {**common, "market": "us", "language": "en-us", "productName": "Cream", "ingredientsText": "Water, Glycerin"}
    )
    second = product_graph.submit_observation(
        {**common, "market": "jp", "language": "ja-jp", "productName": "クリーム", "ingredientsText": "Water, Glycerin, Fragrance"}
    )
    product_graph.approve_observation(first["observationId"])
    product_graph.approve_observation(second["observationId"])

    assert product_graph.suggest_cross_market_links() == []

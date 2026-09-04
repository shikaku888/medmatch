from __future__ import annotations

import asyncio

from backend.engine import Engine
from backend.scanner.advisor import ask_medmatch_advisor


def test_engine_distinguishes_no_documented_from_unmatched() -> None:
    engine = Engine()
    try:
        no_documented = engine.analyze([{"name": "turmeric"}])
        unmatched = engine.analyze([{"name": "zzzxqv-unmatched"}])
    finally:
        engine.conn.close()

    assert no_documented["result"] == "no_documented_interaction_found"
    assert "does not prove" in no_documented["message"]
    assert no_documented["checkedSources"]
    assert no_documented["dataFreshness"]["generatedAt"]
    assert unmatched["result"] == "unknown_unmatched"
    assert unmatched["unmatched"] == ["zzzxqv-unmatched"]
    assert "safe" not in unmatched["message"].lower()


def test_advisor_never_calls_unmatched_combination_good_news() -> None:
    answer = asyncio.run(
        ask_medmatch_advisor(
            "Is this safe?",
            {
                "ingredientsList": ["item-that-cannot-be-mapped"],
                "medMatch": {
                    "result": "unknown_unmatched",
                    "matched": [],
                    "interactions": [],
                    "unmatched": ["item-that-cannot-be-mapped"],
                    "checkedSources": ["RxNorm"],
                    "dataFreshness": {"generatedAt": "2026-09-02T00:00:00+00:00"},
                },
            },
            {"language": "en"},
        )
    )

    assert "good news" not in answer.lower()
    assert "as safe" in answer.lower()

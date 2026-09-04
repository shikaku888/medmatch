from __future__ import annotations

import json
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "r3_evaluation_cases.json"


def test_r3_fixture_matrix_covers_required_safety_categories() -> None:
    cases = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    categories = {case["category"] for case in cases}
    assert categories == {
        "drug-drug", "drug-food", "herb-drug", "herb-herb",
        "disease-contraindication", "pregnancy", "renal", "qt",
        "allergy", "dose-timing",
    }
    for case in cases:
        assert case["id"]
        assert case["items"]
        assert isinstance(case["profile"], dict)
        assert isinstance(case["assert"], dict)

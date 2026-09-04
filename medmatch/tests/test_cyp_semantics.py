from __future__ import annotations

from backend.engine import Engine


def test_cyp_inference_detects_inhibitor_in_either_operand() -> None:
    engine = Engine.__new__(Engine)
    substrate = {"substrate": {"3A4"}, "inhibitor": set(), "inducer": set()}
    inhibitor = {"substrate": set(), "inhibitor": {"3A4"}, "inducer": set()}

    rows = engine.cyp_inference(substrate, inhibitor, "a", "Substrate drug", "b", "Inhibitor drug")

    assert len(rows) == 1
    assert rows[0]["enzyme"] == "3A4"
    assert rows[0]["effect"].startswith("Inhibitor drug inhibits CYP3A4")
    assert rows[0]["trust"] == 0.5


def test_cyp_inference_keeps_2e1_substrate_without_inhibition() -> None:
    engine = Engine.__new__(Engine)
    substrate = {"substrate": {"2E1"}, "inhibitor": set(), "inducer": set()}
    neutral = {"substrate": set(), "inhibitor": set(), "inducer": set()}

    rows = engine.cyp_inference(substrate, neutral, "a", "2E1 substrate", "b", "Neutral drug")

    assert rows == []

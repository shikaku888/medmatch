"""Run the versioned safety fixture matrix against the current engine snapshot."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .engine import Engine

FIXTURE_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "r3_evaluation_cases.json"


def evaluate_case(engine: Engine, case: dict) -> dict:
    result = engine.analyze(
        [{"name": item} for item in case["items"]],
        profile=case.get("profile") or {},
    )
    expected = case.get("assert") or {}
    checks: dict[str, bool] = {}
    if "result_in" in expected:
        checks["result_in"] = result.get("result") in expected["result_in"]
    if "personalizedUrgency" in expected:
        checks["personalizedUrgency"] = result.get("personalization", {}).get("personalizedUrgency") == expected["personalizedUrgency"]
    if expected.get("has_unknown_or_interaction"):
        checks["has_unknown_or_interaction"] = bool(result.get("interactions") or result.get("unmatched"))
    if expected.get("has_context"):
        checks["has_context"] = bool(result.get("patientContext"))
    if "contextHas" in expected:
        checks["contextHas"] = bool(result.get("patientContext", {}).get(expected["contextHas"]))
    if expected.get("medicationMetadataPreserved"):
        medication = (result.get("patientContext", {}).get("medications") or [{}])[0]
        source = (case.get("profile", {}).get("medicationDetails") or [{}])[0]
        checks["medicationMetadataPreserved"] = all(medication.get(key) == value for key, value in source.items() if key != "ingredient")
    return {
        "id": case["id"],
        "category": case["category"],
        "result": result.get("result"),
        "urgency": result.get("personalization", {}).get("personalizedUrgency"),
        "checks": checks,
        "passed": all(checks.values()) if checks else False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, default=FIXTURE_PATH)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cases = json.loads(args.fixtures.read_text(encoding="utf-8"))
    engine = Engine()
    try:
        results = [evaluate_case(engine, case) for case in cases]
    finally:
        engine.conn.close()
    report = {
        "fixtureVersion": "r5-safety-matrix.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "passed": sum(item["passed"] for item in results),
        "failed": sum(not item["passed"] for item in results),
        "cases": results,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

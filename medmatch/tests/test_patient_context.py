from backend.engine import Engine
from backend.patient_context import PATIENT_CONTEXT_VERSION, normalize_patient_context, personalization_summary


def test_patient_context_is_versioned_and_normalizes_medication_and_labs_without_mutation():
    source = {
        "pregnancyStatus": "pregnant",
        "pregnancyTrimester": 2,
        "specialConditions": "anticoagulation",
        "pharmacogenomics": {
            "genotype": "CYP2C19 *2/*2",
            "phenotype": "poor metabolizer",
            "indication": "anticoagulation",
        },
        "medications": [{"brandName": "Coumadin", "ingredient": "warfarin", "dose": 5, "doseUnit": "mg", "route": "oral", "time": "08:00"}],
        "labs": {"test": "INR", "result": 3.2, "unit": "ratio", "date": "2026-01-01"},
    }
    context = normalize_patient_context(source)
    assert context["contextVersion"] == PATIENT_CONTEXT_VERSION
    assert context["pregnancy"] == {"status": "pregnant", "trimester": 2}
    assert context["conditions"] == ["anticoagulation"]
    assert context["pharmacogenomics"]["phenotype"] == "poor metabolizer"
    assert context["medications"][0]["brand"] == "Coumadin"
    assert context["medications"][0]["dose"] == 5
    assert context["labs"] == [{"name": "INR", "value": 3.2, "unit": "ratio", "observedAt": "2026-01-01", "referenceRange": None}]
    assert source["medications"][0]["brandName"] == "Coumadin"


def test_engine_applies_context_to_urgency_without_changing_evidence_severity():
    engine = Engine()
    try:
        items = [
            {"name": "turmeric", "matched": {"kind": "herb", "id": "curcuma"}},
            {"name": "warfarin", "matched": {"kind": "drug_class", "id": "anticoagulantes"}},
        ]
        baseline = engine.analyze(items, profile={})
        pregnant = engine.analyze(items, profile={"pregnancyStatus": "pregnant", "pregnancyTrimester": 2})
        assert baseline["interactions"][0]["severity"] == pregnant["interactions"][0]["severity"]
        assert baseline["personalization"]["personalizedUrgency"] == "moderate"
        assert pregnant["personalization"]["personalizedUrgency"] == "high"
        assert pregnant["patientContext"]["pregnancy"]["trimester"] == 2
    finally:
        engine.conn.close()


def test_personalization_reasons_and_unknown_status_are_explicit():
    context = normalize_patient_context({"pregnancyStatus": "pregnant", "kidneyFunction": "moderate_impairment"})
    summary = personalization_summary(context, [{"severity": "major"}], qt_risk=[], beers=[])
    assert summary["personalizedUrgency"] == "high"
    assert {reason["factor"] for reason in summary["reasons"]} == {"pregnancy", "renal"}
    assert "lactation" in summary["missingContext"]
    assert summary["severityIsEvidenceOnly"] is True


def test_medication_details_take_precedence_and_preserve_timing_metadata():
    context = normalize_patient_context({
        "medications": ["warfarin"],
        "medicationDetails": [{
            "ingredient": "warfarin",
            "strength": "5 mg",
            "dose": 1,
            "unit": "tablet",
            "route": "oral",
            "formulation": "tablet",
            "frequency": "once daily",
            "timing": "08:00",
        }],
    })
    medication = context["medications"][0]
    assert medication["strength"] == "5 mg"
    assert medication["dose"] == 1
    assert medication["route"] == "oral"
    assert medication["frequency"] == "once daily"
    assert medication["timing"] == "08:00"
    assert medication["formulation"] == "tablet"

"""Versioned, non-persistent patient context normalization for personalized checks."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

PATIENT_CONTEXT_VERSION = "medmatch.patient-context.v1"
UNKNOWN = {None, "", "unknown", "not_provided", "unspecified"}


def _clean_text(value: Any) -> str | None:
    if value in UNKNOWN:
        return None
    text = str(value).strip()
    return text or None


def _first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in UNKNOWN:
            return mapping[key]
    return None


def _normalize_medication(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return {"ingredient": value.strip(), "brand": None, "strength": None,
                "dose": None, "unit": None, "route": None, "frequency": None,
                "timing": None, "formulation": None}
    item = value if isinstance(value, dict) else {}
    return {
        "ingredient": _clean_text(_first(item, "ingredient", "activeIngredient", "name", "medication")),
        "brand": _clean_text(_first(item, "brand", "brandName")),
        "strength": _clean_text(_first(item, "strength", "concentration")),
        "dose": _first(item, "dose", "doseValue"),
        "unit": _clean_text(_first(item, "unit", "doseUnit")),
        "route": _clean_text(_first(item, "route", "administrationRoute")),
        "frequency": _clean_text(_first(item, "frequency", "schedule")),
        "timing": _clean_text(_first(item, "timing", "time", "timeOfDay")),
        "formulation": _clean_text(_first(item, "formulation", "dosageForm")),
    }

def _egfr_stage(value: Any) -> str | None:
    try:
        egfr = float(value)
    except (TypeError, ValueError):
        return None
    if egfr < 15:
        return "G5"
    if egfr < 30:
        return "G4"
    if egfr < 60:
        return "G3"
    if egfr < 90:
        return "G2"
    return "G1"


def _normalize_lab(value: Any) -> dict[str, Any]:
    item = value if isinstance(value, dict) else {"name": value}
    return {
        "name": _clean_text(_first(item, "name", "test", "analyte")),
        "value": _first(item, "value", "result"),
        "unit": _clean_text(item.get("unit")),
        "observedAt": _clean_text(_first(item, "observedAt", "measuredAt", "date")),
        "referenceRange": deepcopy(item.get("referenceRange")) if item.get("referenceRange") is not None else None,
    }


def normalize_patient_context(profile: dict[str, Any] | None) -> dict[str, Any]:
    """Return a detached, versioned context; never persists or mutates input."""
    source = profile if isinstance(profile, dict) else {}
    pregnancy = _first(source, "pregnancyStatus", "pregnancy_status", "pregnancy")
    lactation = _first(source, "lactationStatus", "lactation_status", "breastfeeding")
    renal = _first(source, "kidneyFunction", "renalFunction", "renal_impairment")
    hepatic = _first(source, "liverFunction", "hepaticFunction", "hepatic_impairment")
    conditions = source.get("specialConditions", source.get("conditions", []))
    if isinstance(conditions, str):
        conditions = [conditions]
    conditions = [_clean_text(item) for item in (conditions or [])]
    conditions = [item for item in conditions if item]
    medications = source.get("medicationDetails", source.get("medications", []))
    if isinstance(medications, (str, dict)):
        medications = [medications]
    labs = source.get("labs", source.get("laboratoryValues", []))
    if isinstance(labs, dict):
        labs = [labs]
    pharmacogenomics = source.get("pharmacogenomics")
    if not isinstance(pharmacogenomics, dict):
        pharmacogenomics = {}
    return {
        "contextVersion": PATIENT_CONTEXT_VERSION,
        "language": _clean_text(source.get("language")),
        "age": source.get("age"),
        "gender": _clean_text(source.get("gender")),
        "pregnancy": {
            "status": _clean_text(pregnancy),
            "trimester": source.get("pregnancyTrimester", source.get("trimester")),
        },
        "lactation": {"status": _clean_text(lactation)},
        "conditions": conditions,
        "renal": {"status": _clean_text(renal), "eGFR": source.get("eGFR"), "stage": _egfr_stage(source.get("eGFR"))},
        "hepatic": {"status": _clean_text(hepatic)},
        "labs": [_normalize_lab(item) for item in labs or []],
        "pharmacogenomics": deepcopy(pharmacogenomics),
        "medications": [_normalize_medication(item) for item in medications or []],
        "allergies": deepcopy(source.get("allergies") or []),
        "foods": deepcopy(source.get("foods") or []),
        "supplements": deepcopy(source.get("supplements") or []),
    }


def personalization_summary(
    context: dict[str, Any],
    interactions: list[dict[str, Any]],
    *,
    qt_risk: list[dict[str, Any]] | None = None,
    beers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Explain supplied factors without changing evidence severity."""
    reasons: list[dict[str, str]] = []
    missing: list[str] = []

    def add(factor: str, reason: str, impact: str = "increases_risk") -> None:
        reasons.append({"factor": factor, "impact": impact, "reason": reason})

    pregnancy = context.get("pregnancy") or {}
    pregnancy_status = str(pregnancy.get("status") or "").casefold()
    if pregnancy_status in {"pregnant", "yes", "true"}:
        add("pregnancy", "Pregnancy can change the acceptable risk of medicines and supplements.")
    elif not pregnancy.get("status"):
        missing.append("pregnancy")
    lactation = context.get("lactation") or {}
    lactation_status = str(lactation.get("status") or "").casefold()
    if lactation_status in {"breastfeeding", "lactating", "yes", "true"}:
        add("lactation", "Lactation can change infant-exposure and treatment considerations.")
    elif not lactation.get("status"):
        missing.append("lactation")

    renal = context.get("renal") or {}
    renal_status = str(renal.get("status") or "").casefold()
    if "impairment" in renal_status or "failure" in renal_status:
        add("renal", "Renal impairment may reduce clearance and increase exposure or electrolyte risk.")
    elif not renal_status and renal.get("eGFR") is None:
        missing.append("renal")
    hepatic = context.get("hepatic") or {}
    hepatic_status = str(hepatic.get("status") or "").casefold()
    if "impairment" in hepatic_status or "failure" in hepatic_status:
        add("hepatic", "Hepatic impairment may reduce metabolism and increase exposure.")
    elif not hepatic_status:
        missing.append("hepatic")

    conditions = {str(item).casefold().replace("_", " ") for item in context.get("conditions") or []}
    condition_messages = {
        "anticoagulation": "Anticoagulation makes bleeding-related interaction consequences more urgent.",
        "diabetes": "Diabetes can make glucose-lowering and appetite-related effects more consequential.",
        "hypertension": "Hypertension can make blood-pressure effects more consequential.",
        "seizure": "Seizure history can make threshold-lowering interactions more consequential.",
        "transplant": "Transplant therapy often has narrow therapeutic margins and requires clinician review.",
    }
    for condition, reason in condition_messages.items():
        if condition in conditions or any(condition in item for item in conditions):
            add(condition, reason)

    for lab in context.get("labs") or []:
        if lab.get("name") and lab.get("value") is not None:
            add("lab:" + str(lab["name"]), "A measured laboratory value was supplied and should be reviewed with this finding.")

    if any(item.get("level") == "high" for item in qt_risk or []):
        add("qt_risk", "QT screening identified additive rhythm-risk factors.")
    if any(item.get("level") == "avoid" for item in beers or []):
        add("age_65_plus", "A Beers avoid flag adds age-specific urgency.")

    major = any(item.get("severity") in {"contraindicated", "major"} for item in interactions)
    high_context = any(item["factor"] in {"pregnancy", "renal", "hepatic", "anticoagulation", "transplant"} for item in reasons)
    if interactions and (major or high_context):
        urgency = "high"
    elif interactions:
        urgency = "moderate"
    elif missing:
        urgency = "unknown"
    else:
        urgency = "low"
    return {
        "contextVersion": context.get("contextVersion", PATIENT_CONTEXT_VERSION),
        "personalizedUrgency": urgency,
        "reasons": reasons,
        "missingContext": sorted(set(missing)),
        "severityIsEvidenceOnly": True,
    }

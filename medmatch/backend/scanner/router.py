"""Scanner API router — ported from personalized-product-scanner/server.ts (startServer route handlers) — do not diverge.

Same paths/methods/status codes as the Express original; bodies are loose dicts.
Dropped by design: /api/health (main app owns it) and /api/cache/* (FTS5 lookup
cache had no UI callers).
"""
from __future__ import annotations

import hmac
import os
import re
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse
from fastapi import APIRouter, Body, Header
from fastapi.responses import JSONResponse

from backend.scanner.storage import get_user_db
from backend.scanner.ext_clients import (
    log_coverage,
    coverage_stats,
    analyze_cosmetic_ingredients,
    get_pubmed_research,
)
from backend.scanner.personalization import (
    assess_product_match,
    analyze_ingredient_safety,
    extract_regulatory_badges,
    get_all_cross_reactivity_rules,
)
from backend.scanner.herbal_skincare import (
    check_herb_drug_interactions,
    analyze_skincare_routine_conflicts,
)
from backend.scanner.advisor import generate_safe_swaps, ask_medmatch_advisor
from backend.scanner.parsing import audit_receipt, parse_product_image, parse_ingredients_text, ocr_image_to_text
from backend.scanner.market_presets import SUPERMARKET_STORES, MARKET_PRODUCTS
from backend.scanner.demo_data import DEMO_PRODUCTS
from backend.scanner.medmatch_bridge import (
    enriched_search,
    normalize_ingredient,
    analyze_medications,
    med_match_stats,
)
from backend.engine import get_engine
from backend.scanner.resolver import get_offline_product_pack, resolve_product, list_unresolved
from backend.scanner.product_graph import (
    approve_observation,
    list_cross_market_links,
    list_observations,
    reject_observation,
    review_cross_market_link,
    submit_observation,
    suggest_cross_market_links,
)

router = APIRouter()


def _err(status: int, payload: dict):
    """Express-style flat JSON error body."""
    return JSONResponse(status_code=status, content=payload)


def _iso_now() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"

def _unknown_med_match(unmatched: list[str], profile: dict | None = None) -> dict:
    """Keep unrecognized product items explicitly unknown, never safe."""
    engine = get_engine()
    sources = engine.source_coverage()
    language = (profile or {}).get("language")
    return {
        "result": "unknown_unmatched",
        "coverage": "partial",
        "checkedSources": sources,
        "dataFreshness": engine.data_freshness(sources),
        "message": (
            "Some items could not be standardized; the result is unknown for those items."
            if language != "vi"
            else "Một số mục chưa chuẩn hóa được; kết quả của các mục đó là chưa biết."
        ),
        "matched": [],
        "interactions": [],
        "unmatched": unmatched[:20],
        "depletions": [],
        "signals": [],
        "beers": [],
        "qt_risk": [],
        "electrolytes": [],
        "cascades": [],
        "schedule": [],
    }

_SCAN_DRAFT_TTL_SECONDS = 15 * 60
_SCAN_DRAFTS: dict[str, dict] = {}


def _prune_scan_drafts() -> None:
    cutoff = time.time() - _SCAN_DRAFT_TTL_SECONDS
    expired = [draft_id for draft_id, draft in _SCAN_DRAFTS.items() if draft["createdAt"] < cutoff]
    for draft_id in expired:
        _SCAN_DRAFTS.pop(draft_id, None)


def _lookup_product_index(barcode: str) -> dict | None:
    """Resolve a barcode from MedMatch's local product index without network."""
    try:
        from backend import product_index
        from backend.db import get_conn

        hit = product_index.lookup(get_conn(), barcode)
        if not hit:
            return None
        return {
            "barcode": barcode,
            "productName": hit.get("name") or f"Product {barcode}",
            "brand": hit.get("brand") or "",
            "productType": hit.get("product_type") or "supplement",
            "ingredientsText": "; ".join(s for s in (hit.get("ingredients") or "").split(";") if s.strip()),
            "ingredientsList": [s.strip() for s in (hit.get("ingredients") or "").split(";") if s.strip()],
            "excipients": [s.strip() for s in (hit.get("excipients") or "").split(";") if s.strip()],
            "allergens": [],
            "labels": [],
            "source": f"product-index:{hit.get('code_type') or 'barcode'}",
        }
    except Exception as err:
        print("Local product index lookup error:", err)
        return None

def _product_safety_evidence(product_data: dict, barcode: str = "") -> dict:
    """Attach product-level safety signals without turning them into verdicts."""
    empty = {"status": "no_signal_found", "recalls": [], "caers": [], "limitations": [
        "No matching recall or CAERS signal was found; this is not a safety clearance."
    ]}
    try:
        from backend.db import get_conn
        conn = get_conn()
        name = str(product_data.get("productName") or "").strip()
        brand = str(product_data.get("brand") or "").strip()
        barcode_digits = re.sub(r"\D", "", barcode or str(product_data.get("barcode") or ""))
        recall_clauses = []
        recall_params: list[str | int] = []
        if len(barcode_digits) >= 6:
            recall_clauses.append("(product_description LIKE ? OR code_info LIKE ?)")
            recall_params.extend([f"%{barcode_digits}%", f"%{barcode_digits}%"])
        for value in (name, brand):
            if len(value) >= 4 and value.casefold() not in {"unknown product", "product"}:
                recall_clauses.append("LOWER(product_description) LIKE ?")
                recall_params.append(f"%{value.casefold()}%")
        recalls = []
        if recall_clauses and conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='fda_recalls'").fetchone():
            recalls = [dict(row) for row in conn.execute(
                "SELECT event_id, product_type, classification, status, product_description, reason_for_recall, "
                "recall_initiation_date, source_url FROM fda_recalls WHERE " + " OR ".join(recall_clauses) +
                " ORDER BY recall_initiation_date DESC LIMIT 5", recall_params,
            ).fetchall()]
        caers = []
        caers_names = [value for value in (name, brand) if len(value) >= 4]
        if caers_names and conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='caers_product_events'").fetchone():
            clauses = []
            params = []
            for value in caers_names:
                normalized = re.sub(r"\s+", " ", re.sub(r"[^0-9a-z]+", " ", value.casefold())).strip()
                clauses.append("(product_key = ? OR product_key LIKE ?)")
                params.extend([normalized, f"%{normalized}%"])
            caers = [dict(row) for row in conn.execute(
                "SELECT product_name, reaction, case_count, serious_count, first_seen, last_seen, source "
                "FROM caers_product_events WHERE " + " OR ".join(clauses) +
                " ORDER BY case_count DESC LIMIT 8", params,
            ).fetchall()]
        result = {"status": "signal_found" if recalls or caers else "no_signal_found", "recalls": recalls, "caers": caers,
                  "limitations": ["Recall matches require product/lot verification.", "CAERS reports are voluntary and unvalidated; they do not prove causality, incidence, or absolute risk.", "No matching signal is not a safety clearance."]}
        return result
    except Exception as error:
        print("Product safety evidence lookup error:", error)
        return {**empty, "status": "unavailable"}


async def _resolve_barcode_product(barcode: str, country: str | None) -> dict | None:
    """Compatibility wrapper returning the product portion of the unified resolver."""
    resolution = await resolve_product(barcode=barcode, country=country)
    return resolution.get("product") if resolution.get("status") in ("found", "partial") else None


def _create_scan_draft(payload: dict) -> dict:
    _prune_scan_drafts()
    draft_id = f"draft_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
    now = time.time()
    draft = {
        "id": draft_id,
        "createdAt": now,
        "expiresAt": int((now + _SCAN_DRAFT_TTL_SECONDS) * 1000),
        **payload,
    }
    _SCAN_DRAFTS[draft_id] = draft
    return draft


def _get_scan_draft(draft_id: str) -> dict | None:
    _prune_scan_drafts()
    return _SCAN_DRAFTS.get(draft_id)


async def compute_med_match(
    ingredients_list: list[str],
    current_profile: dict | None,
    product_type: str | None = "supplement",
) -> dict:
    """MedMatch analysis for active product ingredients plus user medications.

    Product ingredients are not medications by default. Only herb entities are
    accepted for supplements/cosmetics; food entities are accepted for food
    products so genuine drug-food rules remain available. Drug-class matches
    from an ingredient label are rejected instead of being treated as a user's
    medication.
    """
    items: list[dict] = []
    seen: set[str] = set()
    product_keys: set[tuple[str, str]] = set()
    product_labels: set[str] = set()
    unmatched: list[str] = []

    # Common formulation materials must not become clinical entities through
    # fuzzy matching (e.g. "magnesium stearate" → drug class).
    excipient_re = re.compile(
        r"^(?:water|aqua|citric acid|magnesium stearate|stearic acid|"
        r"vegetable cellulose|cellulose|silicon dioxide|talc|rice flour|"
        r"microcrystalline cellulose|gelatin|glycerin|glycerol|"
        r"vegetable capsule|hypromellose|sodium starch glycolate)$",
        re.IGNORECASE,
    )

    def push_hit(raw: str, hit: dict, *, product: bool = False) -> None:
        key = hit["kind"] + ":" + hit["id"]
        if product:
            product_keys.add((hit["kind"], hit["id"]))
            product_labels.add(str(hit.get("label") or raw).strip().lower())
        if key in seen:
            return
        seen.add(key)
        items.append({
            "name": raw,
            "kind": hit["kind"],
            "matched": {"kind": hit["kind"], "id": hit["id"]},
        })

    product_kinds = ("food", "herb") if product_type == "food" else ("herb",)
    for ing in (ingredients_list or [])[:20]:
        raw = str(ing).strip()
        if not raw or excipient_re.fullmatch(raw):
            continue
        try:
            hit = normalize_ingredient(raw, live=False, preferred_kinds=product_kinds)
            if not hit or hit.get("kind") not in product_kinds:
                unmatched.append(raw)
                continue
            push_hit(raw, hit, product=True)
        except Exception:
            unmatched.append(raw)
    meds = (current_profile or {}).get("medications") or []
    for med in list(meds)[:20]:
        raw = str(med).strip()
        if not raw:
            continue
        try:
            hit = normalize_ingredient(raw)
            if hit:
                push_hit(raw, hit)
            else:
                unmatched.append(raw)
        except Exception:
            unmatched.append(raw)

    if not items:
        return _unknown_med_match(list(dict.fromkeys(unmatched)), current_profile)

    patient_profile = dict(current_profile) if current_profile else None

    analysis = analyze_medications(items, patient_profile)
    analysis["unmatched"] = list(dict.fromkeys((analysis.get("unmatched") or []) + unmatched))
    if analysis["unmatched"] and analysis.get("result") != "interaction_found":
        analysis["result"] = "unknown_unmatched"
        analysis["message"] = (
            "Some items could not be standardized; the result is unknown for those items."
            if (current_profile or {}).get("language") != "vi"
            else "Một số mục chưa chuẩn hóa được; kết quả của các mục đó là chưa biết."
        )

    def is_product_side(side: dict) -> bool:
        if (side.get("kind"), side.get("id")) in product_keys:
            return True
        return str(side.get("label") or "").strip().lower() in product_labels

    analysis["interactions"] = [
        interaction
        for interaction in (analysis.get("interactions") or [])
        if is_product_side(interaction.get("a") or {})
        or is_product_side(interaction.get("b") or {})
    ]
    if not analysis["interactions"] and not analysis["unmatched"]:
        analysis["result"] = "no_documented_interaction_found"
        analysis["message"] = (
            "No interaction was found in the sources checked; this does not prove the combination is safe."
            if (current_profile or {}).get("language") != "vi"
            else "Không tìm thấy tương tác trong các nguồn đang kiểm tra; điều này không chứng minh kết hợp là an toàn."
        )


    return analysis


def merge_med_match_assessment(match_assessment: dict, med_match: dict) -> dict:
    """Promote medication severity into the shared ProductScanResult status.

    `matchAssessment.warnings` remains reserved for profile restrictions
    (allergy, diet, condition, ingredient, nutrition). Medication findings stay
    in `medMatch`, while their severity affects the aggregate status and score.
    """
    assessment = dict(match_assessment or {})
    interactions = med_match.get("interactions") or []
    if not isinstance(interactions, list):
        interactions = []
    major_count = sum(1 for item in interactions if item.get("severity") in ("major", "contraindicated"))
    moderate_count = sum(1 for item in interactions if item.get("severity") == "moderate")
    minor_count = sum(1 for item in interactions if item.get("severity") == "minor")
    medication_status = (
        "danger" if major_count else
        "warning" if moderate_count else
        "caution" if minor_count else
        "safe"
    )
    status_rank = {"safe": 0, "caution": 1, "warning": 2, "danger": 3}
    profile_status = assessment.get("status") if assessment.get("status") in status_rank else "safe"
    if status_rank[medication_status] > status_rank[profile_status]:
        assessment["status"] = medication_status
    medication_score = max(5, 100 - major_count * 25 - moderate_count * 10 - minor_count * 3)
    try:
        assessment["score"] = min(float(assessment.get("score", 100)), medication_score)
    except (TypeError, ValueError):
        assessment["score"] = medication_score
    if interactions:
        medication_summary = (
            f"{len(interactions)} medication interaction(s) found"
            + (f"; {major_count} major" if major_count else "")
            + (f"; {moderate_count} moderate" if moderate_count else "")
            + (f"; {minor_count} minor" if minor_count else "")
            + ". Review the interaction details before use."
        )
        assessment["medicationSummary"] = medication_summary
        profile_summary = str(assessment.get("summary") or "").strip()
        assessment["summary"] = (
            f"{profile_summary} {medication_summary}"
            if profile_status != "safe" and profile_summary
            else medication_summary
        )
    return assessment

_PRODUCT_TYPES = {"food", "cosmetic", "supplement"}


def normalize_product_scan_result(result: dict, source: str | None = None) -> dict:
    """Return the stable ProductScanResult envelope for every scan mode."""
    out = dict(result or {})
    out["barcode"] = str(out.get("barcode") or f"SCAN_{int(time.time() * 1000)}")
    out["productName"] = str(out.get("productName") or "Unknown product")
    out["brand"] = out.get("brand") or None
    out["productType"] = out.get("productType") if out.get("productType") in _PRODUCT_TYPES else "supplement"
    out["ingredientsList"] = [
        str(item).strip() for item in (out.get("ingredientsList") or []) if str(item).strip()
    ]
    out["ingredientsText"] = str(out.get("ingredientsText") or ", ".join(out["ingredientsList"]))
    out["allergens"] = [str(item) for item in (out.get("allergens") or []) if str(item).strip()]
    out["labels"] = [str(item) for item in (out.get("labels") or []) if str(item).strip()]
    assessment = dict(out.get("matchAssessment") or {})
    assessment["status"] = assessment.get("status") if assessment.get("status") in {
        "safe", "caution", "warning", "danger"
    } else "safe"
    try:
        assessment["score"] = max(0, min(100, float(assessment.get("score", 100))))
    except (TypeError, ValueError):
        assessment["score"] = 100
    assessment["summary"] = str(assessment.get("summary") or "")
    assessment["warnings"] = assessment.get("warnings") if isinstance(assessment.get("warnings"), list) else []
    assessment["safeHighlights"] = (
        assessment.get("safeHighlights")
        if isinstance(assessment.get("safeHighlights"), list) else []
    )
    out["matchAssessment"] = assessment
    out["source"] = str(out.get("source") or source or "local_scan")
    out["scannedAt"] = str(out.get("scannedAt") or _iso_now())
    return out



_EMPTY_VERIFICATION = {"verified": False, "majorCount": 0, "moderateCount": 0, "minorCount": 0, "clean": True}


async def verify_swap_safety(active_ingredients: list[str], current_profile: dict | None) -> dict:
    """Verify a swap candidate against the user's medication list with the 7-layer engine.
    Only interactions involving at least one SWAP ingredient count — pre-existing
    medication-vs-medication findings must not penalize the candidate."""
    empty = dict(_EMPTY_VERIFICATION)
    ings = [str(i).strip() for i in (active_ingredients or []) if str(i).strip()][:15]
    if not ings:
        return empty

    try:
        swap_raw: set[str] = set()
        items: list[dict] = []
        for ing in ings:
            hit = normalize_ingredient(ing)
            if hit:
                swap_raw.add(ing.lower())
                items.append({"name": ing, "kind": hit["kind"], "matched": {"kind": hit["kind"], "id": hit["id"]}})
        meds = list((current_profile or {}).get("medications") or [])
        for med in meds[:20]:
            hit = normalize_ingredient(med)
            if hit:
                items.append({"name": med, "kind": hit["kind"], "matched": {"kind": hit["kind"], "id": hit["id"]}})
        if not items:
            return empty

        patient_profile = dict(current_profile) if current_profile else None
        analysis = analyze_medications(items, patient_profile)

        # Canonical labels/ids contributed by the SWAP (not by the user's meds)
        swap_labels: set[str] = set()
        swap_ids: set[str] = set()
        for m in analysis.get("matched") or []:
            if str(m.get("input", "")).lower() in swap_raw:
                swap_labels.add(m.get("label"))
                swap_ids.add(m.get("id"))

        def _rel(i: dict) -> bool:
            a, b = i.get("a") or {}, i.get("b") or {}
            return a.get("label") in swap_labels or b.get("label") in swap_labels or a.get("id") in swap_ids or b.get("id") in swap_ids

        relevant = [i for i in analysis.get("interactions") or [] if _rel(i)]
        major_count = sum(1 for i in relevant if i.get("severity") == "major")
        moderate_count = sum(1 for i in relevant if i.get("severity") == "moderate")
        minor_count = sum(1 for i in relevant if i.get("severity") == "minor")
        return {
            "verified": True,
            "majorCount": major_count,
            "moderateCount": moderate_count,
            "minorCount": minor_count,
            "clean": major_count == 0,
        }
    except Exception as err:
        print("Swap verification failed (non-fatal):", err)
        return empty


# ---------------------------------------------------------------------------
# MedMatch proxy endpoints (kept for frontend compatibility)
# ---------------------------------------------------------------------------
@router.post("/api/medmatch/check")
async def medmatch_check(payload: dict = Body(default={})):
    items = payload.get("items")
    profile = payload.get("profile") or None
    if not isinstance(items, list) or not items:
        return _err(400, {"error": "items array is required"})
    normalized: list[dict] = []
    unmatched: list[str] = []
    seen: set[str] = set()
    for it in items[:30]:
        raw_name = str(it.get("name") or "").strip()
        if not raw_name:
            continue
        hit = normalize_ingredient(raw_name)
        if hit and (hit["kind"] + ":" + hit["id"]) not in seen:
            seen.add(hit["kind"] + ":" + hit["id"])
            normalized.append({
                "name": raw_name,
                "kind": hit["kind"],
                "matched": {"kind": hit["kind"], "id": hit["id"]},
            })
        elif not hit:
            unmatched.append(raw_name)
    result = analyze_medications(normalized, profile)
    result["unmatched"] = list(dict.fromkeys(
        (result.get("unmatched") or []) + unmatched
    ))
    if result["unmatched"] and result.get("result") != "interaction_found":
        result["result"] = "unknown_unmatched"
        result["message"] = (
            "Some items could not be standardized; the result is unknown for those items."
            if (profile or {}).get("language") != "vi"
            else "Một số mục chưa chuẩn hóa được; kết quả của các mục đó là chưa biết."
        )
    return result


@router.get("/api/medmatch/stats")
async def medmatch_stats():
    return med_match_stats()


_REMINDER_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def _validated_reminder(payload: dict, *, existing: dict | None = None) -> dict:
    merged = {**(existing or {}), **payload}
    label = str(merged.get("label") or merged.get("medication") or "").strip()
    time_value = str(merged.get("time") or "").strip()
    if not label:
        raise ValueError("label is required")
    if not _REMINDER_TIME_RE.fullmatch(time_value):
        raise ValueError("time must use HH:MM")

    days = merged.get("days", list(range(7)))
    if not isinstance(days, list) or any(isinstance(day, bool) or not isinstance(day, int) or day not in range(7) for day in days):
        raise ValueError("days must contain weekday numbers from 0 to 6")
    normalized_days = sorted(set(days))
    enabled = merged.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be boolean")

    medication = str(merged.get("medication") or "").strip()
    notes = str(merged.get("notes") or "").strip()
    timezone = str(merged.get("timezone") or "").strip()
    return {
        "label": label[:120],
        "medication": medication[:120],
        "time": time_value,
        "days": normalized_days,
        "enabled": enabled,
        "notes": notes[:240],
        "timezone": timezone[:64],
    }


# --- Medication reminders ----------------------------------------------------
@router.get("/api/reminders")
async def reminders_get():
    return get_user_db().get_reminders()


@router.post("/api/reminders")
async def reminders_post(payload: dict = Body(default={})):
    try:
        reminder = _validated_reminder(payload)
    except ValueError as err:
        return _err(400, {"error": str(err)})
    if len(get_user_db().get_reminders()) >= 32:
        return _err(400, {"error": "Maximum of 32 reminders reached"})
    return get_user_db().upsert_reminder(reminder)


@router.put("/api/reminders/{reminder_id}")
async def reminders_put(reminder_id: str, payload: dict = Body(default={})):
    existing = next((item for item in get_user_db().get_reminders() if item.get("id") == reminder_id), None)
    if existing is None:
        return _err(404, {"error": "Reminder not found"})
    try:
        reminder = _validated_reminder(payload, existing=existing)
    except ValueError as err:
        return _err(400, {"error": str(err)})
    reminder["id"] = reminder_id
    return get_user_db().upsert_reminder(reminder)


@router.delete("/api/reminders/{reminder_id}")
async def reminders_delete(reminder_id: str):
    if not get_user_db().delete_reminder(reminder_id):
        return _err(404, {"error": "Reminder not found"})
    return {"success": True, "id": reminder_id}


# --- User Profile Endpoints -------------------------------------------------
@router.get("/api/profile")
async def profile_get():
    return get_user_db().get_user_profile()


@router.post("/api/profile")
async def profile_post(payload: dict = Body(default={})):
    return get_user_db().update_user_profile(payload)


# --- Family Profiles Multi-User Switcher (Pro feature) ------------------------
@router.get("/api/family-profiles")
async def family_profiles_get():
    return get_user_db().get_family_profiles()


@router.post("/api/family-profiles")
async def family_profiles_post(payload: dict = Body(default={})):
    return get_user_db().add_or_update_family_profile(payload)


@router.put("/api/family-profiles/switch")
async def family_profiles_switch(payload: dict = Body(default={})):
    profile_id = payload.get("profileId")
    if not profile_id:
        return _err(400, {"error": "profileId is required"})
    return get_user_db().switch_family_profile(profile_id)


@router.delete("/api/family-profiles/{id}")
async def family_profiles_delete(id: str):
    return get_user_db().delete_family_profile(id)


# --- Health Analytics & Biometric Exposure Dashboard ---------------------------
@router.get("/api/analytics")
async def analytics():
    return get_user_db().get_health_analytics()


# --- AI Dietitian & Toxicologist Chat Assistant --------------------------------
@router.post("/api/ai-chat")
async def ai_chat(payload: dict = Body(default={})):
    question = payload.get("question")
    product = payload.get("product")
    profile = payload.get("profile")
    if not question:
        return _err(400, {"error": "Question is required"})
    current_profile = profile or get_user_db().get_user_profile()
    answer = await ask_medmatch_advisor(question, product, current_profile)
    return {"answer": answer}


# --- Smart Safe Swaps Generator ---------------------------------------------
@router.post("/api/smart-swaps")
async def smart_swaps(payload: dict = Body(default={})):
    product = payload.get("product")
    profile = payload.get("profile")
    if not product:
        return _err(400, {"error": "Product data required"})

    current_profile = profile or get_user_db().get_user_profile()
    swaps = await generate_safe_swaps(product, current_profile)
    # Layer-7 style gate: verify every candidate against the user's meds before recommending it.
    verified = []
    for swap in swaps:
        verification = await verify_swap_safety(swap.get("activeIngredients") or [], current_profile)
        verified.append({**swap, "medMatchVerification": verification})
    verified.sort(
        key=lambda s: (
            (s["medMatchVerification"]["verified"] and (0 if s["medMatchVerification"]["clean"] else 1)) or 2
        )
    )
    return verified


# --- Supermarket & Local Store Presets ---------------------------------------
def _country_of(profile: dict | None = None) -> str:
    return (profile or {}).get("country") or "US"


@router.get("/api/markets")
async def markets(country: str | None = None):
    c = country or get_user_db().get_user_profile().get("country") or "US"
    stores = [s for s in SUPERMARKET_STORES if s.get("country") in ("GLOBAL", c)]
    featured_products = [p for p in MARKET_PRODUCTS if p.get("country") in ("GLOBAL", c)]

    return {
        "stores": stores or SUPERMARKET_STORES,
        "featuredProducts": featured_products or MARKET_PRODUCTS,
    }


@router.get("/api/markets/products")
async def markets_products(storeId: str | None = None, category: str | None = None, country: str | None = None):
    filtered = MARKET_PRODUCTS
    if storeId:
        filtered = [p for p in filtered if p.get("storeId") == storeId]
    if country:
        filtered = [p for p in filtered if p.get("country") in ("GLOBAL", country)]
    if category and category != "All":
        filtered = [p for p in filtered if category.lower() in (p.get("category") or "").lower()]
    return filtered


# --- Herb-Drug Interactions Reference (proxied to the MedMatch search) --------
@router.get("/api/herb-drug-interactions")
async def herb_drug_interactions(q: str | None = None):
    data = enriched_search(q or "", limit=12)
    return {"query": q or "", "results": data}


# --- Receipt & Supermarket Cart AI Audit --------------------------------------
@router.post("/api/scan/receipt")
async def scan_receipt(payload: dict = Body(default={})):
    image_base64 = payload.get("imageBase64")
    receipt_text = payload.get("receiptText")
    if image_base64 and len(str(image_base64)) > 8_000_000:
        return _err(413, {"error": "Receipt image payload is too large"})
    if receipt_text and len(str(receipt_text)) > 100_000:
        return _err(413, {"error": "Receipt text payload is too large"})
    if not image_base64 and (not receipt_text or len(receipt_text.strip()) < 5):
        return _err(400, {"error": "Receipt image or text content is required"})

    current_profile = get_user_db().get_user_profile()
    family_profiles = get_user_db().get_family_profiles()

    try:
        return await audit_receipt(payload, current_profile, family_profiles)
    except Exception as err:
        print("Receipt audit error:", err)
        return _err(500, {"error": str(err) or "Failed to analyze grocery receipt"})


# --- Batch / Pantry Audit Scanner ----------------------------------------------
_NAME_PREFIX_RE = re.compile(r"^\d{6,}$")


def _name_overlap_ok(query: str, product_name: str | None) -> bool:
    """Guard against random name collisions in fuzzy name-search sources."""
    import re as _re

    def _tok(text):
        return {w for w in _re.split(r"[^a-z0-9]+", (text or "").lower())
                if (len(w) > 2 or any(c.isdigit() for c in w)) and w not in stop}

    stop = {"and", "with", "the", "for", "of", "in", "from", "le", "la", "et", "de"}
    q = _tok(query)
    d = _tok(product_name)
    if not q:
        return True
    return len(q & d) >= max(1, (len(q) + 1) // 2)


def _dsld_db():
    from backend.db import get_conn
    return get_conn()


def _dsld_row_to_product(row) -> dict:
    ings = []
    for chunk in (row["ingredients"] or "").split("|"):
        for part in chunk.split(";"):
            part = part.strip()
            if len(part) > 2:
                ings.append(part)
    return {
        "productName": row["name"],
        "brand": row["brand"] or None,
        "productType": "food",
        "ingredientsText": (row["ingredients"] or "").replace("|", "; "),
        "ingredientsList": ings[:30],
        "allergens": [],
        "labels": ["DSLD/NIH"],
        "source": "dsld",
    }


def search_dsld_name(term: str, limit: int = 400) -> dict | None:
    """DSLD name/brand search — AND-mỗi-từ, chấm điểm overlap trên name+brand."""
    import re as _re

    q_clean = _re.sub(r"\b\d+(?:\.\d+)?\s*(mg|mcg|g|iu|ml)\b.*$", "", (term or ""), flags=_re.I).strip()
    words = [w for w in _re.split(r"[^a-z0-9]+", q_clean.lower()) if len(w) > 2][:2]
    if not words:
        return None
    stop = {"and", "with", "the", "for", "of", "in", "from", "le", "la", "et", "de"}
    q_tokens = {w for w in words if w not in stop and (len(w) > 2 or any(c.isdigit() for c in w))} or set(words)
    try:
        conn = _dsld_db()
        name_cond = " AND ".join("name LIKE ?" for _ in words)
        brand_cond = " AND ".join("brand LIKE ?" for _ in words)
        params = [f"%{w}%" for w in words] * 2
        rows = conn.execute(
            f"SELECT barcode, dsld_id, name, brand, ingredients FROM dsld_products "
            f"WHERE ({name_cond}) OR ({brand_cond}) LIMIT ?",
            [*params, limit],
        ).fetchall()
        best, best_score = None, 0
        for row in rows:
            prod = _dsld_row_to_product(row)
            if not prod["ingredientsList"]:
                continue
            hay = {w for w in _re.split(r"[^a-z0-9]+", f"{row['name']} {row['brand'] or ''}".lower()) if len(w) > 2 and w not in stop}
            score = len(q_tokens & hay)
            if score > best_score:
                best, best_score = prod, score
        return best if best and best_score >= 1 else None
    except Exception as err:
        print("DSLD name search error:", err)
        return None




def search_ndc_local(brand_or_generic: str, limit: int = 3) -> dict | None:
    """Offline drug lookup by brand/generic from the local openFDA NDC index."""
    q = (brand_or_generic or "").strip()
    if len(q) < 3:
        return None
    try:
        conn = _dsld_db()
        rows = conn.execute(
            "SELECT product_ndc, brand_name, generic_name, labeler, dosage_form, ingredients FROM ndc_products WHERE brand_name LIKE ? OR generic_name LIKE ? ORDER BY brand_name LIMIT ?",
            (f"%{q}%", f"%{q}%", limit),
        ).fetchall()
        for row in rows:
            ings = [i for i in (row["ingredients"] or "").split(";") if i.strip()]
            if not ings:
                continue
            brand = (row["brand_name"] or "").strip()
            generic = (row["generic_name"] or "").strip()
            return {
                "productName": f"{brand} ({generic})".strip(),
                "brand": row["labeler"] or brand,
                "productType": "food",
                "ingredientsText": row["ingredients"] or generic,
                "ingredientsList": ings,
                "allergens": [],
                "labels": ["openFDA NDC"],
                "source": "openfda",
            }
    except Exception as err:
        print("NDC local error:", err)
    return None


def lookup_dsld_barcode(barcode: str) -> dict | None:
    try:
        conn = _dsld_db()
        row = conn.execute(
            "SELECT barcode, dsld_id, name, brand, ingredients FROM dsld_products WHERE barcode = ? LIMIT 1",
            (barcode,),
        ).fetchone()
        if row:
            prod = _dsld_row_to_product(row)
            if prod["ingredientsList"]:
                return prod
    except Exception as err:
        print("DSLD barcode error:", err)
    return None


def _name_scan_result(code: str, hit: dict, current_profile: dict, med_match: dict) -> dict:
    major = sum(1 for i in med_match.get("interactions", []) if i.get("severity") in ("major", "contraindicated"))
    moderate = sum(1 for i in med_match.get("interactions", []) if i.get("severity") == "moderate")
    kind_label = (
        "Supplement — MedMatch DB"
        if hit["kind"] == "herb"
        else "Drug class — MedMatch DB"
        if hit["kind"] == "drug_class"
        else "Food — MedMatch DB"
    )
    status = "danger" if major > 0 else ("warning" if moderate > 0 else "safe")
    summary = (
        f"{major} major interaction(s) with the active member's medications"
        if major > 0
        else (
            f"{moderate} moderate interaction(s) — review timing"
            if moderate > 0
            else "No documented interactions with the active member's medications"
        )
    )
    return normalize_product_scan_result(
        merge_med_match_assessment(
            {
                "barcode": "NAME_" + re.sub(r"\s+", "_", str(code).strip().upper())[:40],
                "productName": hit["label"],
                "brand": kind_label,
                "productType": "supplement",
                "ingredientsText": hit["label"],
                "ingredientsList": [hit["label"]],
                "allergens": [],
                "labels": [],
                "ingredientSafetyList": [],
                "herbDrugAlerts": [],
                "matchAssessment": {
                    "status": status,
                    "score": 25 if major > 0 else (55 if moderate > 0 else 90),
                    "summary": summary,
                    "warnings": [],
                    "safeHighlights": [],
                },
                "medMatch": med_match,
                "source": "local_scan",
                "scannedAt": _iso_now(),
            },
            med_match,
        ),
        "local_scan",
    )
@router.post("/api/batch-scan")
async def batch_scan(payload: dict = Body(default={})):
    barcodes = payload.get("barcodes")
    if not isinstance(barcodes, list):
        return _err(400, {"error": "barcodes must be a list"})
    if any(len(str(code)) > 128 for code in barcodes):
        return _err(413, {"error": "Each barcode or name must be at most 128 characters"})
    current_profile = get_user_db().get_user_profile()
    results: list[dict] = []

    codes = barcodes[:10]
    for raw_code in codes:
        code = str(raw_code).strip()
        if not code:
            continue
        try:
            # Medication/supplement NAME mode — resolve through the normalizer.
            if not _NAME_PREFIX_RE.match(code):
                hit = normalize_ingredient(code)
                if not hit:
                    continue
                med_match = analyze_medications(
                    [{
                        "name": hit["label"],
                        "kind": hit["kind"],
                        "matched": {"kind": hit["kind"], "id": hit["id"]},
                    }],
                    {
                        "age": current_profile.get("age"),
                        "gender": current_profile.get("gender"),
                        "kidneyFunction": current_profile.get("kidneyFunction"),
                        "liverFunction": current_profile.get("liverFunction"),
                    },
                )
                results.append(normalize_product_scan_result(
                    _name_scan_result(code, hit, current_profile, med_match),
                    "local_scan",
                ))
                continue

            demo_item = next((p for p in DEMO_PRODUCTS if p["barcode"] == code), None)
            market_item = next((p for p in MARKET_PRODUCTS if p["barcode"] == code), None)
            product_data = _lookup_product_index(code)
            source = product_data.get("source", "product-index") if product_data else "openfoodfacts"

            if not product_data and demo_item:
                product_data = {**demo_item, "productName": demo_item["name"]}
                source = "demo"
            elif not product_data and market_item:
                product_data = {**market_item, "productName": market_item["name"]}
                source = "demo"
            elif not product_data:
                product_data = await _resolve_barcode_product(code, current_profile.get("country"))
                source = (product_data or {}).get("source", source)

            if not product_data:
                continue

            ingredients = product_data.get("ingredientsList") or []
            med_match = await compute_med_match(
                ingredients,
                current_profile,
                product_data.get("productType"),
            )
            match_assessment = merge_med_match_assessment(
                await assess_product_match(product_data, current_profile),
                med_match,
            )
            full_res = normalize_product_scan_result({
                "barcode": code,
                "productName": product_data.get("productName"),
                "brand": product_data.get("brand"),
                "productType": product_data.get("productType"),
                "imageUrl": product_data.get("imageUrl"),
                "ingredientsText": product_data.get("ingredientsText"),
                "ingredientsList": ingredients,
                "allergens": product_data.get("allergens") or [],
                "labels": product_data.get("labels") or [],
                "nutrition": product_data.get("nutrition"),
                "cosmetic": product_data.get("cosmetic"),
                "cleanScoreBreakdown": product_data.get("cleanScoreBreakdown"),
                "regulatoryBadges": extract_regulatory_badges(ingredients),
                "herbDrugAlerts": check_herb_drug_interactions(
                    ingredients,
                    current_profile.get("medications") or [],
                ),
                "medMatch": med_match,
                "countryOfOrigin": product_data.get("countryOfOrigin"),
                "ingredientSafetyList": analyze_ingredient_safety(ingredients),
                "crossReactivityAlerts": match_assessment.get("crossReactivityAlerts"),
                "skincareActiveCheck": match_assessment.get("skincareActiveCheck"),
                "matchAssessment": match_assessment,
                "source": source,
                "scannedAt": _iso_now(),
            }, source)
            results.append(full_res)
        except Exception as err:
            print("Batch scan item error:", err)

    # Cross-item check: interactions BETWEEN batch items.
    name_hits = [r for r in results if r["barcode"].startswith("NAME_") and r["medMatch"].get("matched")]
    if len(name_hits) >= 2:
        try:
            cross = analyze_medications(
                [
                    {
                        "name": r["medMatch"]["matched"][0]["label"],
                        "kind": r["medMatch"]["matched"][0]["kind"],
                        "matched": {
                            "kind": r["medMatch"]["matched"][0]["kind"],
                            "id": r["medMatch"]["matched"][0]["id"],
                        },
                    }
                    for r in name_hits
                ],
                {
                    "age": current_profile.get("age"),
                    "gender": current_profile.get("gender"),
                    "kidneyFunction": current_profile.get("kidneyFunction"),
                    "liverFunction": current_profile.get("liverFunction"),
                },
            )
            for inter in cross.get("interactions", []):
                if inter.get("severity") not in ("major", "moderate", "minor"):
                    continue
                la = ((inter.get("a") or {}).get("label") or "").lower()
                lb = ((inter.get("b") or {}).get("label") or "").lower()
                for result in name_hits:
                    label = (result["medMatch"]["matched"][0].get("label") or "").lower()
                    if label not in (la, lb):
                        continue
                    duplicate = any(
                        item.get("a", {}).get("label") == (inter.get("a") or {}).get("label")
                        and item.get("b", {}).get("label") == (inter.get("b") or {}).get("label")
                        and item.get("severity") == inter.get("severity")
                        for item in result["medMatch"]["interactions"]
                    )
                    if duplicate:
                        continue
                    result["medMatch"]["interactions"].append(inter)
                    result["matchAssessment"] = merge_med_match_assessment(
                        result["matchAssessment"],
                        result["medMatch"],
                    )
                    other = (inter.get("b") or {}).get("label") if label == la else (inter.get("a") or {}).get("label")
                    result["matchAssessment"]["summary"] = (
                        f"{inter['severity']} interaction with another batch item: "
                        f"{other} — {inter.get('mechanism') or 'engine finding'}"
                    )
        except Exception as err:
            print("Batch cross-item check failed:", err)

    # Persist the post-cross-item result, not the pre-cross-item intermediate.
    for result in results:
        get_user_db().add_history(result)
    return {"results": results, "count": len(results)}


# --- History Endpoints ---------------------------------------------------------
@router.get("/api/history")
async def history_get():
    return get_user_db().get_history()


@router.post("/api/history/favorite")
async def history_favorite(payload: dict = Body(default={})):
    id = payload.get("id")
    if not id:
        return _err(400, {"error": "Missing ID"})
    is_fav = get_user_db().toggle_favorite(id)
    return {"id": id, "favorite": is_fav}


@router.delete("/api/history")
async def history_delete():
    get_user_db().clear_history()
    return {"success": True}


@router.get("/api/data/export")
async def data_export():
    return {"data": get_user_db().export_data(), "retention": "device-scoped"}


@router.delete("/api/data")
async def data_delete():
    get_user_db().clear_all_data()
    return {"success": True, "deleted": ["profile", "family_profiles", "routine", "reminders", "history", "cache"]}


# --- Demo products endpoint -----------------------------------------------------
@router.get("/api/demo-products")
async def demo_products():
    return DEMO_PRODUCTS


# --- Cross-Reactivity Reference Rules -------------------------------------------
@router.get("/api/cross-reactivity-rules")
async def cross_reactivity_rules():
    return get_all_cross_reactivity_rules()


# --- Skincare Routine Shelf ------------------------------------------------------
@router.get("/api/skincare-routine")
async def skincare_routine_get():
    return get_user_db().get_routine()


@router.post("/api/skincare-routine")
async def skincare_routine_post(payload: dict = Body(default={})):
    if not payload.get("name"):
        return _err(400, {"error": "Product name is required"})
    return get_user_db().add_or_update_routine_item(payload)


@router.delete("/api/skincare-routine/{id}")
async def skincare_routine_delete(id: str):
    return get_user_db().delete_routine_item(id)


@router.post("/api/skincare-routine/audit")
async def skincare_routine_audit(payload: dict = Body(default={})):
    routine = get_user_db().get_routine()
    return analyze_skincare_routine_conflicts(routine, payload.get("newActives") or [])


# --- PubMed Research Endpoint -----------------------------------------------------
@router.get("/api/pubmed")
async def pubmed(ingredient: str = "", context: str | None = None):
    if not ingredient:
        return _err(400, {"error": "Ingredient query parameter is required"})
    try:
        return await get_pubmed_research(ingredient, context)
    except Exception as err:
        return _err(500, {"error": str(err)})



# --- Reviewable scan drafts -------------------------------------------------
@router.post("/api/medications/parse-image")
async def parse_medication_image(payload: dict = Body(default={})):
    image_base64 = payload.get("imageBase64")
    mime_type = payload.get("mimeType") or "image/jpeg"
    if not image_base64:
        return _err(400, {"error": "Medication image is required"})
    try:
        text = await ocr_image_to_text(image_base64, mime_type)
    except Exception as err:
        return _err(422, {"error": str(err) or "Could not read medication image"})
    candidates = []
    for line in re.split(r"[\r\n]+", text):
        value = re.sub(r"^[\s•\-*\d.)]+", "", line).strip()
        if not value or len(value) < 3 or len(value) > 120:
            continue
        if re.search(r"\b\d+\s*(mg|mcg|g|ml|tablet|tablets|capsule|capsules)\b", value, re.I) or re.search(
            r"\b(warfarin|aspirin|metformin|levothyroxine|atorvastatin|lisinopril|sertraline|ciprofloxacin|ibuprofen|paracetamol)\b",
            value,
            re.I,
        ):
            candidates.append(value)
    unique = list(dict.fromkeys(candidates))[:20]
    return {"status": "review_required", "medications": unique, "rawImageStored": False}

@router.post("/api/scan/draft")
async def scan_draft(payload: dict = Body(default={})):
    raw_value = str(payload.get("value") or payload.get("barcode") or "").strip()
    if not raw_value:
        return _err(400, {"error": "QR code or barcode is required"})

    barcode = raw_value
    amazon_id = None
    parsed_url = urlparse(raw_value)
    if parsed_url.scheme or parsed_url.netloc:
        host = (parsed_url.hostname or "").lower()
        if not (host == "amazon.com" or host.endswith(".amazon.com")):
            return _err(400, {"error": "Only Amazon product links are supported for QR URLs"})
        match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/\s?]|$)", parsed_url.path, re.I)
        amazon_id = match.group(1).upper() if match else None
        barcode = ""

    if not barcode and not amazon_id:
        return _err(400, {"error": "Could not identify a product code in this QR value"})

    if amazon_id:
        return _err(424, {
            "error": "Amazon product details are not configured",
            "amazonProductId": amazon_id,
            "hint": "Please photograph the ingredient label to continue",
        })
    if not re.fullmatch(r"\d{6,}", barcode):
        return _err(400, {"error": "Barcode must contain at least 6 digits"})

    current_profile = get_user_db().get_user_profile()
    product = await _resolve_barcode_product(barcode, current_profile.get("country"))
    if not product:
        return _err(404, {"error": "Product not found", "barcode": barcode})

    ingredients = [
        str(value).strip()
        for value in (product.get("ingredientsList") or product.get("ingredients") or [])
        if str(value).strip()
    ][:40]
    draft = _create_scan_draft({
        "inputType": "code",
        "inputValue": raw_value,
        "product": {
            "productName": product.get("productName") or product.get("name") or "Unknown product",
            "brand": product.get("brand") or product.get("brands") or "",
            "productType": product.get("productType") or "supplement",
            "imageUrl": product.get("imageUrl") or product.get("image_url"),
            "barcode": product.get("barcode") or barcode,
            "amazonProductId": amazon_id,
        },
        "ingredientsList": ingredients,
        "ingredientsText": product.get("ingredientsText") or "; ".join(ingredients),
        "source": product.get("source") or "unknown",
    })
    return {
        "draftId": draft["id"],
        "status": "waiting_confirmation",
        "dataCompleteness": "partial" if ingredients else "missing",
        "product": draft["product"],
        "ingredientsList": draft["ingredientsList"],
        "ingredientsText": draft["ingredientsText"],
        "source": draft["source"],
        "expiresAt": draft["expiresAt"],
    }


@router.post("/api/scan/draft/image")
async def scan_image_draft(payload: dict = Body(default={})):
    image_base64 = payload.get("imageBase64")
    mime_type = payload.get("mimeType") or "image/jpeg"
    if not image_base64:
        return _err(400, {"error": "Image base64 data is required"})

    try:
        parsed = await parse_product_image(image_base64, mime_type)
    except Exception as err:
        return _err(422, {"error": str(err) or "Could not read ingredient photo"})

    ingredients = [str(value).strip() for value in (parsed.get("ingredientsList") or []) if str(value).strip()][:40]
    image_fingerprint = str(payload.get("imageFingerprint") or "").strip()
    draft = _create_scan_draft({
        "inputType": "ingredient_photo",
        "inputValue": None,
        "product": {
            "productName": parsed.get("productName") or "Unknown product",
            "brand": parsed.get("brand") or "",
            "productType": parsed.get("productType") or "supplement",
            "evidenceImage": True,
        },
        "ingredientsList": ingredients,
        "ingredientsText": parsed.get("ingredientsText") or "",
        "mimeType": mime_type,
        "imageFingerprint": image_fingerprint,
        "source": "local_scan",
    })
    has_section = bool(parsed.get("hasIngredientSection"))
    return {
        "draftId": draft["id"],
        "status": "waiting_confirmation",
        "dataCompleteness": "partial" if has_section and ingredients else "missing",
        "product": draft["product"],
        "ingredientsList": ingredients,
        "ingredientsText": draft["ingredientsText"],
        "source": draft["source"],
        "imageFingerprint": draft.get("imageFingerprint"),
    }


@router.post("/api/scan/draft/{draft_id}/confirm")
async def scan_draft_confirm(draft_id: str, payload: dict = Body(default={})):
    draft = _get_scan_draft(draft_id)
    if not draft:
        return _err(404, {"error": "Scan draft expired or not found"})
    submitted = payload.get("ingredientsList")
    ingredients = submitted if isinstance(submitted, list) else draft.get("ingredientsList") or []
    ingredients = [str(value).strip() for value in ingredients if str(value).strip()][:40]
    if not ingredients:
        return _err(422, {"error": "At least one ingredient must be confirmed"})
    _SCAN_DRAFTS.pop(draft_id, None)
    return {
        "confirmed": True,
        "inputType": draft["inputType"],
        "inputValue": draft.get("inputValue"),
        "product": draft["product"],
        "ingredientsList": ingredients,
        "ingredientsText": ", ".join(ingredients),
        "source": draft["source"],
    }

@router.get("/api/offline/products")
async def offline_products(limit: int = 50000):
    try:
        return {
            "version": "product-index-v1",
            "products": get_offline_product_pack(limit),
            "maxAgeHours": 168,
        }
    except (OSError, ValueError, Exception) as err:
        return _err(503, {"error": f"Offline product pack unavailable: {err}"})

@router.post("/api/product/resolve")
async def product_resolve(payload: dict = Body(default={})):
    """Resolve barcode/name/ingredients/image fingerprint without unsafe fallback."""
    barcode = str(payload.get("barcode") or "").strip()
    name = str(payload.get("name") or payload.get("query") or "").strip()
    image_fingerprint = str(payload.get("imageFingerprint") or "").strip()
    raw_ingredients = payload.get("ingredients")
    ingredients = raw_ingredients if isinstance(raw_ingredients, list) else []
    if not barcode and not name and not ingredients and not image_fingerprint:
        return _err(400, {"error": "Barcode, product name, ingredients, or image fingerprint are required"})
    if len(barcode) > 128 or len(name) > 128 or len(ingredients) > 60 or len(image_fingerprint) > 160:
        return _err(413, {"error": "Product input exceeds the supported size"})
    profile = get_user_db().get_user_profile()
    return await resolve_product(
        barcode=barcode,
        name=name,
        ingredients=ingredients,
        country=profile.get("country"),
        image_fingerprint=image_fingerprint,
    )

def _resolver_admin_guard(x_admin_token: str | None):
    expected = os.environ.get("PRODUCT_RESOLVER_ADMIN_TOKEN") or os.environ.get("ADMIN_API_TOKEN")
    if not expected:
        return _err(503, {"error": "Resolver admin endpoint is disabled"})
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        return _err(401, {"error": "Admin authentication required"})
    return None


@router.post("/api/product/contributions")
async def product_contribution(payload: dict = Body(default={})):
    """Accept product facts only after explicit user opt-in."""
    try:
        return submit_observation(payload)
    except ValueError as err:
        return _err(422, {"error": str(err)})


@router.get("/api/product/contributions")
async def product_contributions(
    status: str = "pending",
    limit: int = 50,
    x_admin_token: str | None = Header(default=None),
):
    guard = _resolver_admin_guard(x_admin_token)
    if guard:
        return guard
    try:
        return {"items": list_observations(status, limit), "status": status}
    except ValueError as err:
        return _err(422, {"error": str(err)})


@router.post("/api/product/contributions/{observation_id}/approve")
async def approve_product_contribution(
    observation_id: str,
    x_admin_token: str | None = Header(default=None),
):
    guard = _resolver_admin_guard(x_admin_token)
    if guard:
        return guard
    try:
        return approve_observation(observation_id)
    except KeyError as err:
        return _err(404, {"error": str(err)})


@router.post("/api/product/contributions/{observation_id}/reject")
async def reject_product_contribution(
    observation_id: str,
    x_admin_token: str | None = Header(default=None),
):
    guard = _resolver_admin_guard(x_admin_token)
    if guard:
        return guard
    try:
        return reject_observation(observation_id)
    except KeyError as err:
        return _err(404, {"error": str(err)})


@router.get("/api/product/cross-market/candidates")
async def cross_market_candidates(
    limit: int = 50,
    x_admin_token: str | None = Header(default=None),
):
    guard = _resolver_admin_guard(x_admin_token)
    if guard:
        return guard
    try:
        suggested = suggest_cross_market_links(limit)
        return {"suggested": suggested, "items": list_cross_market_links("candidate", limit)}
    except ValueError as err:
        return _err(422, {"error": str(err)})


@router.post("/api/product/cross-market/{link_id}/review")
async def review_cross_market_candidate(
    link_id: str,
    payload: dict = Body(default={}),
    x_admin_token: str | None = Header(default=None),
):
    guard = _resolver_admin_guard(x_admin_token)
    if guard:
        return guard
    try:
        return review_cross_market_link(link_id, str(payload.get("decision") or ""))
    except (KeyError, ValueError) as err:
        return _err(404 if isinstance(err, KeyError) else 422, {"error": str(err)})


@router.get("/api/product/unresolved")
async def unresolved_products(limit: int = 50, x_admin_token: str | None = Header(default=None)):
    """Return hashed unresolved lookup keys for authorized coverage review."""
    guard = _resolver_admin_guard(x_admin_token)
    if guard:
        return guard
    return {"items": list_unresolved(limit), "limit": max(1, min(int(limit), 200))}

@router.post("/api/scan")
async def scan(payload: dict = Body(default={})):
    started_at = time.perf_counter()
    barcode = payload.get("barcode")
    query = payload.get("query")

    if not barcode and not query:
        return _err(400, {"error": "Barcode or search query is required"})

    current_profile = get_user_db().get_user_profile()
    product_data = None
    source = "openfoodfacts"

    clean_barcode = barcode.strip() if barcode else ""

    # Prefer MedMatch's local product index for barcode scans before external sources.
    if clean_barcode:
        local_product = _lookup_product_index(clean_barcode)
        if local_product:
            product_data = local_product
            source = local_product.get("source", "product-index")


    # 1. Use demo/market fixtures only when the local index had no result.
    demo_item = next((p for p in DEMO_PRODUCTS if p["barcode"] == clean_barcode), None)
    market_item = next(
        (p for p in MARKET_PRODUCTS if p["barcode"] == clean_barcode or (query and query.lower() in p["name"].lower())),
        None,
    )

    if not product_data and demo_item:
        product_data = {
            "productName": demo_item["name"],
            "brand": demo_item["brand"],
            "productType": demo_item["type"],
            "imageUrl": demo_item.get("image"),
            "ingredientsText": demo_item.get("ingredientsText"),
            "ingredientsList": demo_item.get("ingredientsList"),
            "allergens": demo_item.get("allergens"),
            "labels": demo_item.get("labels"),
            "nutrition": demo_item.get("nutrition"),
            "cosmetic": demo_item.get("cosmetic"),
        }
        source = "demo"
    elif not product_data and market_item:
        product_data = {
            "productName": market_item["name"],
            "brand": market_item["brand"],
            "productType": market_item["type"],
            "imageUrl": market_item.get("image"),
            "ingredientsText": market_item.get("ingredientsText"),
            "ingredientsList": market_item.get("ingredientsList"),
            "allergens": market_item.get("allergens"),
            "labels": market_item.get("labels"),
            "nutrition": market_item.get("nutrition"),
            "cosmetic": market_item.get("cosmetic"),
        }
        source = "demo"

    # All non-fixture product input now follows the same resolver contract and
    # provider order as batch scans and the explicit resolver endpoint.
    if not product_data and (query or clean_barcode):
        resolution = await resolve_product(
            barcode=clean_barcode or None,
            name=query or None,
            country=current_profile.get("country"),
        )
        product_data = resolution.get("product")
        source = (product_data or {}).get("source", source)

    if not product_data and (query or clean_barcode):
        # Layer-1 salvage: nhận dạng entity trong free-text → phân tích phần đó
        import re as _re2
        term_clean = _re2.sub(
            r"\b\d+(?:\.\d+)?\s*(mg|mcg|g|iu|ml)\b.*$",
            "",
            query or clean_barcode,
            flags=_re2.I,
        ).strip() or (query or clean_barcode)

        tokens = [w for w in _re2.split(r"[^a-zA-Z]+", (query or clean_barcode)) if len(w) > 2]
        seen_entities: set[str] = set()
        recognized: list[dict] = []
        candidates = [term_clean, " ".join(tokens[:2]), " ".join(tokens[1:3]), *tokens]
        for cand in candidates:
            if not cand or len(cand) < 3:
                continue
            h = normalize_ingredient(cand, live=False)
            if h and h.get("kind") in ("herb", "drug_class", "food") and (h["kind"] + ":" + h["id"]) not in seen_entities:
                seen_entities.add(h["kind"] + ":" + h["id"])
                recognized.append(h)
            if len(recognized) >= 4:
                break
        if recognized:
            product_data = {
                "productName": f"{(query or clean_barcode)[:60]} (partial match)",
                "brand": None,
                "productType": "food",
                "ingredientsText": ", ".join(h["label"] for h in recognized),
                "ingredientsList": [h["label"] for h in recognized],
                "allergens": [],
                "labels": ["Partial recognition"],
                "source": "name-recognition",
            }
            source = "name-recognition"

    if not product_data:
        log_coverage(
            clean_barcode or query or "",
            hit=False,
            latency_ms=(time.perf_counter() - started_at) * 1000,
        )
        return _err(404, {
            "error": "Product not found in Open Food Facts, Open Beauty Facts, USDA, or openFDA databases.",
            "hint": "Try: Photo OCR (scan the label) or type the product name — pharmacy/supplement barcodes are rarely in open food databases.",
            "barcode": clean_barcode,
        })

    # Enhance cosmetic data if cosmetic type
    if product_data.get("productType") == "cosmetic" and not product_data.get("cosmetic"):
        product_data["cosmetic"] = analyze_cosmetic_ingredients(
            product_data.get("ingredientsList") or [],
            product_data.get("ingredientsText") or "",
        )

    # MedMatch AI analysis (ingredients + user medications → 7-layer backend)
    try:
        med_match = await compute_med_match(
            product_data.get("ingredientsList") or [],
            current_profile,
            product_data.get("productType"),
        )
    except Exception as err:
        print("MedMatch analysis failed (non-fatal):", err)
        med_match = {"matched": [], "interactions": [], "unmatched": [], "depletions": []}

    match_assessment = merge_med_match_assessment(
        await assess_product_match(product_data, current_profile),
        med_match,
    )
    # Analyze Clean Chemistry Ingredient Toxicity & Regulatory Badges
    ingredient_safety_list = analyze_ingredient_safety(product_data.get("ingredientsList") or [])
    regulatory_badges = extract_regulatory_badges(product_data.get("ingredientsList") or [])

    # Check Herb-Drug Interaction against user's active medications
    user_meds = current_profile.get("medications") or []
    herb_drug_alerts = check_herb_drug_interactions(product_data.get("ingredientsList") or [], user_meds)

    full_result = normalize_product_scan_result({
        "barcode": clean_barcode or ("SEARCH_" + str(int(time.time() * 1000))),
        "productName": product_data.get("productName"),
        "brand": product_data.get("brand"),
        "productType": product_data.get("productType"),
        "imageUrl": product_data.get("imageUrl"),
        "ingredientsText": product_data.get("ingredientsText"),
        "ingredientsList": product_data.get("ingredientsList") or [],
        "excipients": product_data.get("excipients") or [],
        "allergens": product_data.get("allergens") or [],
        "labels": product_data.get("labels") or [],
        "nutrition": product_data.get("nutrition"),
        "safetyEvidence": _product_safety_evidence(product_data, clean_barcode),
        "regulatoryBadges": regulatory_badges,
        "herbDrugAlerts": herb_drug_alerts,
        "countryOfOrigin": product_data.get("countryOfOrigin"),
        "ingredientSafetyList": ingredient_safety_list,
        "crossReactivityAlerts": match_assessment.get("crossReactivityAlerts"),
        "skincareActiveCheck": match_assessment.get("skincareActiveCheck"),
        "matchAssessment": match_assessment,
        "medMatch": med_match,
        "source": source,
        "scannedAt": _iso_now(),
    }, source)

    severity = next(
        (level for level in ("major", "moderate", "minor")
         if any(item.get("severity") == level for item in med_match.get("interactions") or [])),
        None,
    )
    freshness = med_match.get("dataFreshness") or {}
    log_coverage(
        clean_barcode or query or "",
        hit=True,
        source=source,
        latency_ms=(time.perf_counter() - started_at) * 1000,
        unmatched_count=len(med_match.get("unmatched") or []),
        severity=severity,
        stale=bool(freshness.get("stale")),
    )
    get_user_db().add_history(full_result)
    return full_result


@router.post("/api/scan/image")
async def scan_image(payload: dict = Body(default={})):
    image_base64 = payload.get("imageBase64")
    mime_type = payload.get("mimeType")
    if not image_base64:
        return _err(400, {"error": "Image base64 data is required"})

    try:
        current_profile = get_user_db().get_user_profile()
        parsed = await parse_product_image(image_base64, mime_type or "image/jpeg")

        cosmetic_profile = None
        if parsed.get("productType") == "cosmetic":
            cosmetic_profile = analyze_cosmetic_ingredients(parsed.get("ingredientsList") or [], parsed.get("ingredientsText") or "")

        try:
            med_match = await compute_med_match(
                parsed.get("ingredientsList") or [],
                current_profile,
                parsed.get("productType"),
            )
        except Exception as err:
            print("MedMatch analysis failed (non-fatal):", err)
            med_match = {"matched": [], "interactions": [], "unmatched": [], "depletions": []}

        match_assessment = merge_med_match_assessment(
            await assess_product_match(
                {
                    "productName": parsed.get("productName"),
                    "productType": parsed.get("productType"),
                    "ingredientsText": parsed.get("ingredientsText"),
                    "ingredientsList": parsed.get("ingredientsList"),
                    "allergens": parsed.get("allergens") or [],
                    "labels": parsed.get("labels") or [],
                    "nutrition": parsed.get("nutrition"),
                    "cosmetic": cosmetic_profile,
                },
                current_profile,
            ),
            med_match,
        )

        ingredient_safety_list = analyze_ingredient_safety(parsed.get("ingredientsList") or [])
        regulatory_badges = extract_regulatory_badges(parsed.get("ingredientsList") or [])
        user_meds = current_profile.get("medications") or []
        herb_drug_alerts = check_herb_drug_interactions(parsed.get("ingredientsList") or [], user_meds)

        score = match_assessment.get("score") or 0
        full_result = normalize_product_scan_result({
            "barcode": f"PHOTO_{int(time.time() * 1000)}",
            "productName": parsed.get("productName"),
            "brand": parsed.get("brand"),
            "productType": parsed.get("productType"),
            "ingredientsText": parsed.get("ingredientsText"),
            "ingredientsList": parsed.get("ingredientsList"),
            "excipients": parsed.get("excipients") or [],
            "allergens": parsed.get("allergens") or [],
            "labels": parsed.get("labels") or [],
            "nutrition": parsed.get("nutrition"),
            "safetyEvidence": _product_safety_evidence(parsed),
            "cleanScoreBreakdown": {
                "totalScore": score,
                "cleanScore": score,
                "ratingLevel": "excellent" if score >= 75 else ("good" if score >= 50 else ("mediocre" if score >= 30 else "bad")),
                "nutritionalQualityScore": 40,
                "nutritionPoints": 40,
                "additivesSafetyScore": 30,
                "additivesPoints": 30,
                "organicBioBonus": 0,
            },
            "regulatoryBadges": regulatory_badges,
            "ingredientSafetyList": ingredient_safety_list,
            "crossReactivityAlerts": match_assessment.get("crossReactivityAlerts"),
            "skincareActiveCheck": match_assessment.get("skincareActiveCheck"),
            "matchAssessment": match_assessment,
            "medMatch": med_match,
            "source": "local_scan",
            "scannedAt": _iso_now(),
        }, "local_scan")

        get_user_db().add_history(full_result)
        return full_result
    except Exception as err:
        print("Image scan OCR error:", err)
        return _err(500, {"error": str(err) or "Failed to analyze product image"})


@router.post("/api/scan/text")
async def scan_text(payload: dict = Body(default={})):
    started_at = time.perf_counter()
    text = payload.get("text")
    name = payload.get("name")
    if not text or len(text.strip()) < 3:
        return _err(400, {"error": "Ingredient text is required"})

    try:
        current_profile = get_user_db().get_user_profile()
        parsed = parse_ingredients_text(text, name)

        cosmetic_profile = None
        if parsed.get("productType") == "cosmetic":
            cosmetic_profile = analyze_cosmetic_ingredients(parsed.get("ingredientsList") or [], parsed.get("ingredientsText") or "")

        try:
            med_match = await compute_med_match(
                parsed.get("ingredientsList") or [],
                current_profile,
                parsed.get("productType"),
            )
        except Exception as err:
            print("MedMatch analysis failed (non-fatal):", err)
            med_match = {"matched": [], "interactions": [], "unmatched": [], "depletions": []}

        match_assessment = merge_med_match_assessment(
            await assess_product_match(
                {
                    "productName": parsed.get("productName"),
                    "productType": parsed.get("productType"),
                    "ingredientsText": parsed.get("ingredientsText"),
                    "ingredientsList": parsed.get("ingredientsList"),
                    "allergens": parsed.get("allergens") or [],
                    "labels": parsed.get("labels") or [],
                    "cosmetic": cosmetic_profile,
                },
                current_profile,
            ),
            med_match,
        )

        ingredient_safety_list = analyze_ingredient_safety(parsed.get("ingredientsList") or [])
        regulatory_badges = extract_regulatory_badges(parsed.get("ingredientsList") or [])
        user_meds = current_profile.get("medications") or []
        herb_drug_alerts = check_herb_drug_interactions(parsed.get("ingredientsList") or [], user_meds)

        score = match_assessment.get("score") or 0
        full_result = normalize_product_scan_result({
            "barcode": f"TEXT_{int(time.time() * 1000)}",
            "productName": parsed.get("productName"),
            "brand": parsed.get("brand"),
            "productType": parsed.get("productType"),
            "ingredientsText": parsed.get("ingredientsText"),
            "ingredientsList": parsed.get("ingredientsList"),
            "excipients": parsed.get("excipients") or [],
            "allergens": parsed.get("allergens") or [],
            "labels": parsed.get("labels") or [],
            "safetyEvidence": _product_safety_evidence(parsed),
            "cleanScoreBreakdown": {
                "totalScore": score,
                "cleanScore": score,
                "ratingLevel": "excellent" if score >= 75 else ("good" if score >= 50 else ("mediocre" if score >= 30 else "bad")),
                "nutritionalQualityScore": 40,
                "nutritionPoints": 40,
                "additivesSafetyScore": 30,
                "additivesPoints": 30,
                "organicBioBonus": 0,
            },
            "regulatoryBadges": regulatory_badges,
            "herbDrugAlerts": herb_drug_alerts,
            "ingredientSafetyList": ingredient_safety_list,
            "crossReactivityAlerts": match_assessment.get("crossReactivityAlerts"),
            "skincareActiveCheck": match_assessment.get("skincareActiveCheck"),
            "matchAssessment": match_assessment,
            "medMatch": med_match,
            "source": "local_scan",
            "scannedAt": _iso_now(),
        }, "local_scan")

        severity = next(
            (level for level in ("major", "moderate", "minor")
             if any(item.get("severity") == level for item in med_match.get("interactions") or [])),
            None,
        )
        freshness = med_match.get("dataFreshness") or {}
        log_coverage(
            parsed.get("productName") or "text-scan",
            hit=True,
            source="local_scan",
            latency_ms=(time.perf_counter() - started_at) * 1000,
            unmatched_count=len(med_match.get("unmatched") or []),
            severity=severity,
            stale=bool(freshness.get("stale")),
        )
        get_user_db().add_history(full_result)
        return full_result
    except Exception as err:
        print("Text analysis error:", err)
        return _err(500, {"error": str(err) or "Failed to analyze text"})


# --- Coverage telemetry (admin) ----------------------------------------------
# Phải đặt COVERAGE_ADMIN_TOKEN ở môi trường; nếu thiếu → chỉ trả số liệu tổng
# (KHÔNG lộ text user gõ). Đây là dữ liệu người dùng — không công khai.
import os as _os

@router.get("/api/coverage/stats")
async def coverage_stats_ep(limit: int = 25, x_admin_token: str | None = Header(default=None)):
    stats = coverage_stats(max(1, min(limit, 100)))
    admin = _os.environ.get("COVERAGE_ADMIN_TOKEN") or ""
    if admin and x_admin_token and hmac.compare_digest(x_admin_token, admin):
        return stats
    # Public response contains only aggregate operational metrics.
    return {k: v for k, v in stats.items() if k != "topMisses"}


# --- GDPR / App Store: user xóa toàn bộ dữ liệu của thiết bị -------------------
@router.post("/api/user-data/purge")
async def user_data_purge():
    """Xóa sạch profile/history/routine của thiết bị gọi request (theo cookie)."""
    db_user = get_user_db()
    db_user.clear_history()
    db_user.set_routine([])
    db_user.update_user_profile({
        "allergies": [], "customAllergens": [], "medications": [],
        "specialConditions": [], "dietType": "omnivore",
    })
    removed = False
    try:
        f = db_user.storage_file
        if f.exists() and db_user.token:  # chỉ xóa file per-device, không đụng seed chung
            f.unlink()
            removed = True
    except Exception as err:
        print("purge file error:", err)
    # nạp lại mặc định trong bộ nhớ
    from backend.scanner.storage import ScannerDB
    fresh = ScannerDB(token=db_user.token)
    import backend.scanner.storage as _st
    _st._USER_DB_CACHE[db_user.token] = fresh
    return {"status": "ok", "file_removed": removed}


# Route inventory (parity with server.ts Express routes):
# GET  /api/medmatch/stats
# POST /api/medmatch/check
# GET  /api/profile                       POST /api/profile
# GET  /api/family-profiles               POST /api/family-profiles
# PUT  /api/family-profiles/switch        DELETE /api/family-profiles/{id}
# GET  /api/analytics
# POST /api/ai-chat
# POST /api/smart-swaps
# GET  /api/markets                       GET  /api/markets/products
# GET  /api/herb-drug-interactions
# POST /api/scan/receipt                  POST /api/batch-scan
# GET  /api/history                       POST /api/history/favorite   DELETE /api/history
# GET  /api/demo-products
# GET  /api/cross-reactivity-rules
# GET  /api/skincare-routine              POST /api/skincare-routine
# DELETE /api/skincare-routine/{id}       POST /api/skincare-routine/audit
# GET  /api/pubmed
# POST /api/scan                          POST /api/scan/image         POST /api/scan/text

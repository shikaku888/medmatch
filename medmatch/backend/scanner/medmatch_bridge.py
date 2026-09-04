"""In-process bridge to the MedMatch 7-layer engine.

Ported from personalized-product-scanner/server/services/medmatch_client.ts.
The HTTP proxy + FTS5 lookup cache were intentionally dropped: this module calls
backend.engine directly (same process); responses keep the /api/search + /api/analyze shapes.
"""
from __future__ import annotations

from pathlib import Path

from backend.db import DB_PATH
from backend.engine import get_engine, normalize


def enriched_search(q: str, limit: int = 3) -> list[dict]:
    """Same enrichment as FastAPI GET /api/search (app.py)."""
    results = []
    for r in get_engine().match(q, max_results=limit):
        r = dict(r)
        if r.get("kind") == "herb":
            detail = get_engine().herb_detail(r["id"])
            r["scientific"] = detail.get("scientific") if detail else None
            r["warns_against"] = [i["class_name"] for i in (detail.get("interactions") or [])][:5]
        elif r.get("kind") == "food":
            pass  # plain food item, no enrichment
        else:
            detail = get_engine().class_detail(r["id"])
            r["examples"] = (detail.get("drugs") or [])[:5] if detail else []
        results.append(r)
    return results


def _synonym_fastpath(raw: str, preferred_kinds: tuple[str, ...] | None = None) -> dict | None:
    """Self-learned phrase → entity (instant, no HTTP).

    A synonym can legitimately exist for more than one entity type (for
    example, ``magnesium`` is both a supplement herb and a drug class).  The
    caller's context must win instead of SQLite insertion order.
    """
    try:
        import sqlite3

        db_path = Path(DB_PATH)
        conn = sqlite3.connect(str(db_path), timeout=5)
        rows = conn.execute(
            "SELECT kind, entity_id FROM ingredient_synonyms "
            "WHERE synonym = ? COLLATE NOCASE",
            (raw.lower().strip(),),
        ).fetchall()
        conn.close()
        if not rows:
            return None
        row = next(
            (
                candidate
                for preferred in (preferred_kinds or ())
                for candidate in rows
                if candidate[0] == preferred
            ),
            rows[0],
        )
        kind, eid = row
        label_row = None
        table = {"herb": "herbs", "drug_class": "drug_classes", "food": "foods"}.get(kind)
        if table:
            try:
                conn = sqlite3.connect(str(db_path), timeout=5)
                label_row = conn.execute(f"SELECT name_en FROM {table} WHERE id = ?", (eid,)).fetchone()
                conn.close()
            except Exception:
                pass
        return {
            "kind": kind,
            "id": eid,
            "label": (label_row[0] if label_row else eid),
            "matched_alias": raw.lower().strip(),
            "score": 1.0,
            "resolved_via": "learned-synonym",
        }
    except Exception as err:
        print("synonym fastpath error:", err)
        return None


def _canonical_typed_match(raw: str, preferred_kinds: tuple[str, ...]) -> dict | None:
    """Return a canonical local entity before duplicate source rows."""
    query = normalize(raw)
    sources = {
        "herb": get_engine().herbs,
        "drug_class": get_engine().classes,
        "food": get_engine().foods,
    }
    for kind in preferred_kinds:
        seen_ids: set[str] = set()
        for entry in sources.get(kind, {}).values():
            entity_id = str(entry.get("id") or "")
            if not entity_id or entity_id in seen_ids:
                continue
            seen_ids.add(entity_id)
            candidates = [entry.get("name_en"), *(entry.get("aliases") or [])]
            if kind == "drug_class":
                candidates.extend(entry.get("drugs") or [])
            matched_alias = next(
                (candidate for candidate in candidates if candidate and normalize(str(candidate)) == query),
                None,
            )
            if not matched_alias:
                continue
            label = str(entry.get("name_en") or "").strip()
            hit = {
                "kind": kind,
                "id": entity_id,
                "label": label,
                "matched_alias": str(matched_alias).lower().strip(),
                "score": 1.0,
                "resolved_via": "canonical-local",
            }
            if kind == "herb":
                detail = get_engine().herb_detail(entity_id)
                hit["scientific"] = detail.get("scientific") if detail else None
                hit["warns_against"] = [i["class_name"] for i in (detail.get("interactions") or [])][:5]
            return hit
    return None


def normalize_ingredient(
    raw: str,
    live: bool = True,
    preferred_kinds: tuple[str, ...] | None = None,
) -> dict | None:
    """Lớp 1 — Input Normalizer. live=False: chỉ local (dùng trong salvage loop)."""
    if not raw or len(raw.strip()) < 2:
        return None

    # Canonical local aliases win over learned synonyms, regardless of caller
    # context. This prevents a known herb from being redirected to a weaker
    # duplicate SUPP.AI micro-class.
    canonical_kinds = preferred_kinds or ("drug_class", "food", "herb")
    canonical_hit = _canonical_typed_match(raw, canonical_kinds)
    if canonical_hit:
        return canonical_hit
    if preferred_kinds:
        direct = enriched_search(raw.strip(), limit=3)
        direct_hit = next(
            (
                result
                for result in direct
                if result.get("kind") in preferred_kinds and result.get("score", 0) >= 0.85
            ),
            None,
        )
        if direct_hit:
            return direct_hit

    fast = _synonym_fastpath(raw, preferred_kinds)
    if fast:
        return fast

    # US OTC brand names absent from the engine's name map → map to generic first
    _BRAND_ALIASES = {
        "advil": "ibuprofen", "motrin": "ibuprofen", "aleve": "naproxen",
        "claritin": "loratadine", "prilosec": "omeprazole", "nexium": "esomeprazole",
        "flonase": "fluticasone", "pepcid": "famotidine",
    }
    q = raw.strip()
    lowered = q.lower()
    for brand, generic in _BRAND_ALIASES.items():
        if brand in lowered:
            q = generic
            break

    results = enriched_search(q, limit=3)
    if not results:
        return _rxnorm_retry(raw) if live else None
    allowed_kinds = preferred_kinds or ("herb", "drug_class", "food")
    eligible = [
        result
        for result in results
        if result.get("kind") in allowed_kinds and result.get("score", 0) >= 0.85
    ]
    if not eligible:
        return None if preferred_kinds else (results[0] if results[0].get("score", 0) >= 0.7 else None)
    hit = eligible[0]
    return hit if hit.get("score", 0) >= 0.7 else None


# --- RxNorm live retry (free NIH API, no key) + self-learning synonyms -------
_RXNORM_CACHE: dict[str, str | None] = {}


def _rxnorm_resolve(clean: str) -> str | None:
    """Typos/brand variants → canonical generic name via RxNorm. Cached in-process."""
    key = clean.lower().strip()
    if key in _RXNORM_CACHE:
        return _RXNORM_CACHE[key]
    name = None
    try:
        import httpx

        r = httpx.get(
            "https://rxnav.nlm.nih.gov/REST/rxcui.json",
            params={"name": clean},
            timeout=2.5,
        )
        ids = ((r.json() or {}).get("idGroup") or {}).get("rxnormId") or []
        if ids:
            props = httpx.get(
                f"https://rxnav.nlm.nih.gov/REST/rxcui/{ids[0]}/properties.json",
                timeout=2.5,
            ).json()
            name = ((props.get("properties") or {}).get("name") or "").strip() or None
    except Exception as err:
        print("RxNorm live error:", err)
    _RXNORM_CACHE[key] = name
    return name


def _persist_synonym(raw: str, hit: dict) -> None:
    """Self-learning: raw input that resolved once never costs a lookup again."""
    try:
        import sqlite3

        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        conn.execute(
            "INSERT OR IGNORE INTO ingredient_synonyms (kind, entity_id, synonym, source) VALUES (?,?,?,?)",
            (hit.get("kind"), hit.get("id"), raw.lower().strip(), "rxnorm-live"),
        )
        conn.commit()
        conn.close()
    except Exception as err:
        print("synonym persist failed:", err)


def _rxnorm_retry(raw: str) -> dict | None:
    import re as _re

    clean = _re.sub(r"\b\d+(?:\.\d+)?\s*(mg|mcg|g|iu|ml|tablet|tablets|capsule|capsules)\b.*$", "",
                    raw.strip(), flags=_re.I).strip()
    if len(clean) < 4:
        return None
    canonical = _rxnorm_resolve(clean)
    if not canonical:
        return None
    results = enriched_search(canonical, limit=3)
    if not results:
        return None
    hit = next(
        (r for r in results if r.get("kind") in ("herb", "drug_class", "food") and r.get("score", 0) >= 0.7),
        None,
    )
    if hit:
        hit = dict(hit)
        hit["resolved_via"] = "rxnorm"
        _persist_synonym(raw, hit)
    return hit


def analyze_medications(items: list[dict], profile: dict | None = None) -> dict:
    """Lớp 2-7 — full interaction analysis for normalized items + user medications."""
    payload = []
    for it in items:
        item = dict(it)
        item["name"] = item.get("name") or item.get("label") or ""
        payload.append(item)
    return get_engine().analyze(payload, profile=profile)


def med_match_stats() -> dict:
    return get_engine().stats()

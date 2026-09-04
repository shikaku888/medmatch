"""MedMatch AI — backend API.

Product safety companion for the US/EU market: scans supplement/drug
names and checks documented interactions, then explains risks in plain
language. Informational only; never prescribes.
"""
import hmac
import json
import urllib.parse
import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .db import get_conn
from .engine import get_engine
from .rate_limit import RateLimitUnavailable, rate_limiter


STATIC_DIR = Path(__file__).parent.parent / "static"
SCANNER_DIST = STATIC_DIR / "scanner"
PRIVACY_POLICY = Path(__file__).parent.parent / "docs" / "privacy-policy.md"

app = FastAPI(title="MedMatch AI", version="0.2.0")
_configured_origins = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "").split(",")
    if origin.strip()
]
if "*" in _configured_origins:
    _configured_origins = []
if _configured_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_configured_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Admin-Token"],
    )

_RATE_LIMITS = {
    "/api/search": (60, 60.0),
    "/api/scan": (30, 60.0),
    "/api/batch-scan": (15, 60.0),
}


def _request_client_key(request: Request) -> str:
    fallback = request.client.host if request.client else "unknown"
    if os.environ.get("TRUST_PROXY_HEADERS") != "1":
        return fallback
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip() or fallback
    return request.headers.get("x-real-ip", "").strip() or fallback


_MAX_BODY_BYTES = {
    "/api/scan/receipt": 6 * 1024 * 1024,
    "/api/batch-scan": 128 * 1024,
    "/api/analyze": 256 * 1024,
}
 
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Health Scanner (React SPA ported from personalized-product-scanner)
import uuid  # noqa: E402

from .scanner.router import router as scanner_router  # noqa: E402
from .scanner.storage import (
    is_valid_device_token,
    new_device_token,
    reset_device_token,
    set_device_token,
)  # noqa: E402

app.include_router(scanner_router)


@app.middleware("http")
async def _device_identity(request: Request, call_next):
    """Bind every request to an isolated, signed-by-entropy device namespace.

    The token is an opaque random bearer identifier; profile/history data never
    falls back to the legacy shared JSON file for HTTP requests.
    """
    path = request.url.path
    for endpoint, max_bytes in _MAX_BODY_BYTES.items():
        if path == endpoint:
            try:
                if int(request.headers.get("content-length", "0")) > max_bytes:
                    return JSONResponse(
                        {"error": "request payload exceeds the endpoint limit"},
                        status_code=413,
                    )
            except ValueError:
                pass
            break
    for endpoint, (limit, window) in _RATE_LIMITS.items():
        if path == endpoint or path.startswith(endpoint + "/"):
            bucket = f"{_request_client_key(request)}:{endpoint}"
            try:
                allowed = rate_limiter.allow(bucket, limit, window)
            except RateLimitUnavailable:
                return JSONResponse(
                    {"error": "rate limit backend unavailable"},
                    status_code=503,
                    headers={"Retry-After": "30"},
                )
            if not allowed:
                return JSONResponse(
                    {"error": "rate limit exceeded", "retry_after_seconds": int(window)},
                    status_code=429,
                    headers={"Retry-After": str(int(window))},
                )
            break
    cookie_token = request.cookies.get("mt_device")
    token = cookie_token if is_valid_device_token(cookie_token) else new_device_token()
    context_token = set_device_token(token)
    try:
        response = await call_next(request)
    finally:
        reset_device_token(context_token)
    if token != cookie_token:
        response.set_cookie(
            "mt_device",
            token,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https",
            path="/",
        )
    return response


def _require_admin(x_admin_token: str | None) -> None:
    expected = os.environ.get("ADMIN_API_TOKEN")
    if not expected:
        raise HTTPException(503, "Admin API is disabled until ADMIN_API_TOKEN is configured")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(401, "Admin authentication required")


class AnalyzeItem(BaseModel):
    name: str | None = None
    label: str | None = None
    kind: str | None = None
    matched: dict | None = None
    time: str | None = None


class AnalyzeRequest(BaseModel):
    items: list[AnalyzeItem]
    profile: dict | None = None


class PharmacogenomicsCheckRequest(BaseModel):
    drug_id: str
    genotype: dict | str | None = None
    phenotype: dict | str | None = None
    indication: str | None = None
class DrugMappingReviewRequest(BaseModel):
    source: str
    raw_name: str
    status: str
    entity_type: str | None = None
    entity_id: str | None = None
    rxcui: str | None = None
    component_ids: list[str] = []
    note: str = ""


@app.get("/")
async def index():
    # React scanner is the production UI; keep the vanilla PWA as legacy fallback.
    react_index = SCANNER_DIST / "index.html"
    return FileResponse(react_index if react_index.exists() else STATIC_DIR / "index.html")


@app.get("/index.html")
async def scanner_index_alias():
    return FileResponse(SCANNER_DIST / "index.html")


@app.get("/manifest.webmanifest")
async def scanner_manifest_root():
    return FileResponse(SCANNER_DIST / "manifest.webmanifest")


@app.get("/sw.js")
async def scanner_service_worker_root():
    return FileResponse(
        SCANNER_DIST / "sw.js",
        headers={"Service-Worker-Allowed": "/"},
    )

@app.get("/privacy", include_in_schema=False)
async def privacy_page():
    return FileResponse(PRIVACY_POLICY, media_type="text/markdown")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/privacy")
async def privacy():
    return {
        "policy": (
            "The scanner stores profiles, medications, allergies, routines, reminders, "
            "optional pharmacogenomic context, and scan history server-side in a "
            "device-scoped namespace keyed by an opaque random cookie."
        ),
        "ai_data_policy": (
            "The public build uses a deterministic local advisor; profile, medication, and "
            "allergy fields are not sent to an AI provider."
        ),
        "retention": (
            "Profile, family-profile, routine, reminder, pharmacogenomic context, and history "
            "data remain until explicit deletion. History is capped at 100 entries, cache at "
            "200 entries, and coverage telemetry at 10 MiB; the device cookie lasts 365 days. "
            "There is no automatic orphan-file expiry yet."
        ),
        "export_endpoint": "/api/data/export",
        "delete_endpoint": "/api/data",
        "purge_endpoint": "/api/user-data/purge",
        "medical_disclaimer": "MedMatch is an informational reference, not diagnosis or prescribing advice.",
    }


@app.get("/api/provenance")
async def provenance():
    from .license_registry import KNOWN_LICENSES

    conn = get_conn()
    releases = [
        {key: row[key] for key in row.keys()}
        for row in conn.execute(
            "SELECT source_code, dataset_name, version, period_start, period_end, "
            "source_url, terms_url, licence_name, downloaded_at, sha256, notes "
            "FROM dataset_release ORDER BY source_code, downloaded_at DESC"
        )
    ]
    counts = {}
    for table, source in (
        ("zenodo_ddi_2026", "zenodo_ddi_2026"),
        ("onsides_effects_raw", "onsides"),
        ("onsides_ingredient_effects", "onsides"),
        ("openfda_label_sections", "openfda"),
        ("evidence_ontology_intersection", "evidence_ontology"),
        ("faers_adverse_events", "faers"),
        ("mendeley_drug_food_2021", "mendeley_drug_food"),
        ("pharmgkb_relations", "pharmgkb"),
        ("drugcentral_structures", "drugcentral"),
        ("drugcentral_targets", "drugcentral"),
        ("drugcentral_struct_atc", "drugcentral"),
        ("drugcentral_target_facts", "drugcentral"),
        ("lactmed_records", "lactmed"),
        ("fda_recalls", "fda_recalls"),
        ("caers_product_events", "caers"),
    ): 
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if exists:
            counts[source] = counts.get(source, 0) + conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
    return {
        "licenses": {
            code: {
                "label": item["label"],
                "terms_url": item["terms_url"],
                "commercial": bool(item["commercial"]),
                "attribution_required": bool(item["attr"]),
                "share_alike": bool(item["share_alike"]),
                "raw_redistribution": bool(item["raw_redist"]),
            }
            for code, item in KNOWN_LICENSES.items()
        },
        "releases": releases,
        "row_counts": counts,
    }


@app.get("/api/stats")
async def stats():
    payload = get_engine().stats()
    conn = get_conn()
    source_tables = {
        "drugcentral_structures": "DrugCentral structures",
        "drugcentral_target_facts": "DrugCentral target facts",
        "drugcentral_targets": "DrugCentral target facts (legacy)",
        "drugcentral_struct_atc": "DrugCentral ATC mappings",
        "lactmed_records": "LactMed records",
        "fda_recalls": "FDA recall records",
        "caers_product_events": "CAERS product-reaction aggregates",
    }
    payload["source_records"] = {}
    for table, label in source_tables.items():
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
            payload["source_records"][label] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return payload


@app.get("/api/search")
async def search(q: str = "", limit: int = 12):
    q = q[:200]
    limit = max(1, min(limit, 50))
    results = get_engine().match(q, max_results=limit)
    enriched = []
    for r in results:
        if r["kind"] == "herb":
            detail = get_engine().herb_detail(r["id"])
            r["scientific"] = detail.get("scientific") if detail else None
            r["warns_against"] = [i["class_name"] for i in (detail.get("interactions") or [])][:5]
        elif r["kind"] == "food":
            pass  # plain food item, no enrichment
        else:
            detail = get_engine().class_detail(r["id"])
            r["examples"] = (detail.get("drugs") or [])[:5] if detail else []
        enriched.append(r)
    return {"query": q, "results": enriched}


@app.get("/api/herb/{herb_id}")
async def herb_detail(herb_id: str):
    detail = get_engine().herb_detail(herb_id)
    if not detail:
        raise HTTPException(404, "Herb not found")
    return detail


@app.get("/api/class/{class_id}")
async def class_detail(class_id: str):
    detail = get_engine().class_detail(class_id)
    if not detail:
        raise HTTPException(404, "Drug class not found")
    return detail

_LABEL_SECTION_NAMES = (
    "boxed_warning", "contraindications", "warnings_and_precautions",
    "adverse_reactions", "drug_interactions", "indications_and_usage",
    "active_ingredient", "inactive_ingredient", "purpose", "pregnancy",
    "lactation", "pediatric_use", "geriatric_use", "renal_impairment",
    "hepatic_impairment", "overdosage", "dosage_and_administration",
)

_LABEL_COLUMN_ALIASES = {
    "boxed_warning": ("boxed_warning", "boxedwarning"),
    "contraindications": ("contraindications",),
    "warnings_and_precautions": ("warnings_and_precautions", "warnings"),
    "adverse_reactions": ("adverse_reactions", "adverse_reactions_section"),
    "drug_interactions": ("drug_interactions",),
    "indications_and_usage": ("indications_and_usage", "indications"),
    "active_ingredient": ("active_ingredient",),
    "inactive_ingredient": ("inactive_ingredient",),
    "purpose": ("purpose",),
    "pregnancy": ("pregnancy", "pregnancy_section"),
    "lactation": ("lactation",),
    "pediatric_use": ("pediatric_use", "pediatric"),
    "geriatric_use": ("geriatric_use", "geriatric"),
    "renal_impairment": ("renal_impairment", "renal"),
    "hepatic_impairment": ("hepatic_impairment", "hepatic"),
    "overdosage": ("overdosage", "overdose"),
    "dosage_and_administration": ("dosage_and_administration", "dosage"),
}


def _label_payload(drug_id: str, requested: set[str] | None = None) -> dict:
    conn = get_conn()
    table_names = []
    for table in ("label_section", "openfda_label_sections"):
        if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone():
            table_names.append(table)
    if not table_names:
        raise HTTPException(503, "Label section data is not available")
    class_row = conn.execute(
        "SELECT drugs FROM drug_classes WHERE id = ?", (drug_id,)
    ).fetchone()
    names = json.loads(class_row["drugs"] or "[]") if class_row else [drug_id]
    names = list(dict.fromkeys(str(name).strip() for name in names if str(name).strip()))
    if not names:
        raise HTTPException(404, "Drug not found")

    sections: list[dict] = []
    for table_name in table_names:
        table_columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}
        id_column = "set_id" if "set_id" in table_columns else "label_id"
        predicates = []
        params: list[str] = []
        for name in names[:20]:
            pattern = f"%{name.upper()}%"
            predicates.append(
                "(UPPER(COALESCE(generic_name, '')) LIKE ? "
                "OR UPPER(COALESCE(brand_name, '')) LIKE ? "
                "OR UPPER(COALESCE(openfda_generic, '')) LIKE ?)"
            )
            params.extend([pattern, pattern, pattern])
        base_columns = [
            column for column in (
                id_column, "effective_time", "generic_name", "brand_name", "openfda_generic"
            )
            if column in table_columns
        ]
        section_columns = {
            section: next((column for column in aliases if column in table_columns), None)
            for section, aliases in _LABEL_COLUMN_ALIASES.items()
        }
        selected_columns = base_columns + [
            column for column in section_columns.values()
            if column and column not in base_columns
        ] + [
            column for column in ("source_url", "source")
            if column in table_columns and column not in base_columns
        ]
        if not selected_columns:
            continue
        rows = conn.execute(
            "SELECT " + ", ".join(selected_columns) + f" FROM {table_name} WHERE "
            + " OR ".join(predicates)
            + " ORDER BY effective_time DESC LIMIT 100",
            params,
        ).fetchall()
        for row in rows:
            label_id = row[id_column] or drug_id
            label = next(
                (row[column] for column in ("generic_name", "brand_name", "openfda_generic")
                 if column in table_columns and row[column]),
                drug_id,
            )
            if table_name == "openfda_label_sections":
                source_url = row["source_url"] if "source_url" in table_columns else None
                source = row["source"] if "source" in table_columns else None
                source_url = source_url or (
                    "https://api.fda.gov/drug/label.json?search="
                    + urllib.parse.quote(f"id:{label_id}")
                )
                source = source or "openFDA"
            else:
                source_url = f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={label_id}"
                source = "DailyMed/OpenFDA"
            for section_name, column in section_columns.items():
                text = row[column] if column else None
                if not text or (requested and section_name not in requested):
                    continue
                sections.append(
                    {
                        "section": section_name,
                        "text": text,
                        "set_id": label_id,
                        "effective_time": row["effective_time"] if "effective_time" in table_columns else None,
                        "source_url": source_url,
                        "source": source,
                        "label_name": label,
                    }
                )
    available = {item["section"] for item in sections}
    return {
        "drug_id": drug_id,
        "sections": sections,
        "unavailable_sections": [
            section for section in _LABEL_SECTION_NAMES
            if (not requested or section in requested) and section not in available
        ],
        "reference_only": True,
        "limitations": [
            "Label excerpts are reference information, not prescribing instructions.",
            "Absence of a section in this snapshot does not prove safety.",
        ],
    }


@app.get("/api/drug/{drug_id}/label")
async def drug_label(drug_id: str):
    return _label_payload(drug_id)


@app.get("/api/drug/{drug_id}/warnings")
async def drug_warnings(drug_id: str):
    return _label_payload(drug_id, {"warnings_and_precautions", "boxed_warning"})


@app.get("/api/drug/{drug_id}/contraindications")
async def drug_contraindications(drug_id: str):
    return _label_payload(drug_id, {"contraindications"})


@app.get("/api/drug/{drug_id}/populations")
async def drug_populations(drug_id: str):
    return _label_payload(
        drug_id,
        {"pregnancy", "lactation", "pediatric_use", "geriatric_use",
         "renal_impairment", "hepatic_impairment"},
    )


def _drug_names(conn, drug_id: str) -> list[str]:
    class_row = conn.execute("SELECT drugs FROM drug_classes WHERE id = ?", (drug_id,)).fetchone()
    names = json.loads(class_row["drugs"] or "[]") if class_row else [drug_id]
    return list(dict.fromkeys(str(name).strip() for name in names if str(name).strip()))


def _drugcentral_ids(conn, drug_id: str) -> list[str]:
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='drugcentral_structures'").fetchone():
        return []
    ids: list[str] = []
    for name in _drug_names(conn, drug_id)[:20]:
        rows = conn.execute(
            "SELECT struct_id FROM drugcentral_structures WHERE LOWER(name) = LOWER(?) "
            "UNION SELECT struct_id FROM drugcentral_synonyms WHERE LOWER(synonym) = LOWER(?) "
            "OR LOWER(lname) = LOWER(?) LIMIT 20", (name, name, name),
        ).fetchall()
        ids.extend(str(row["struct_id"]) for row in rows)
    return list(dict.fromkeys(ids))


def _drugcentral_atc_payload(drug_id: str) -> dict:
    conn = get_conn()
    ids = _drugcentral_ids(conn, drug_id)
    if not ids:
        return {"drug_id": drug_id, "status": "unknown_unmatched", "atc": [], "limitations": ["No exact DrugCentral structure mapping was found."]}
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        "SELECT sa.struct_id, sa.atc_code, a.chemical_substance, a.l1_name, a.l2_name, a.l3_name, a.l4_name "
        "FROM drugcentral_struct_atc sa LEFT JOIN drugcentral_atc a ON a.code = sa.atc_code "
        f"WHERE sa.struct_id IN ({placeholders}) ORDER BY sa.atc_code", ids,
    ).fetchall()
    return {
        "drug_id": drug_id, "status": "evidence_found" if rows else "no_atc_found",
        "atc": [dict(row) for row in rows], "source": "DrugCentral (CC BY-SA 4.0)",
        "source_url": "https://drugcentral.org/", "updated_at": _release_time(conn, "drugcentral"),
        "limitations": ["ATC classification is classification context, not an indication or prescribing instruction."],
    }


def _release_time(conn, source: str) -> str | None:
    try:
        row = conn.execute("SELECT MAX(downloaded_at) AS value FROM dataset_release WHERE source_code = ?", (source,)).fetchone()
    except Exception:
        return None
    return row["value"] if row else None


@app.get("/api/drug/{drug_id}/atc")
async def drug_atc(drug_id: str):
    return _drugcentral_atc_payload(drug_id)


def _drugcentral_targets_payload(drug_id: str, limit: int) -> dict:
    conn = get_conn()
    ids = _drugcentral_ids(conn, drug_id)
    if not ids:
        return {"drug_id": drug_id, "status": "unknown_unmatched", "targets": [], "limitations": ["No exact DrugCentral structure mapping was found."]}
    placeholders = ",".join("?" for _ in ids)
    rows: list[dict] = []
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='drugcentral_target_facts'").fetchone():
        rows.extend(dict(row) for row in conn.execute(
            "SELECT DISTINCT struct_id, target_id, target_name, target_class, relation, moa, action_type, "
            "act_source_url, moa_source_url FROM drugcentral_target_facts "
            f"WHERE struct_id IN ({placeholders}) AND (target_name != '' OR moa != '') "
            "ORDER BY target_name LIMIT ?", [*ids, max(1, min(limit, 100))],
        ).fetchall())
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='drugcentral_targets'").fetchone():
        columns = {row[1] for row in conn.execute("PRAGMA table_info(drugcentral_targets)")}
        if "drugcentral_id" in columns:
            rows.extend(dict(row) for row in conn.execute(
                "SELECT drugcentral_id AS struct_id, NULL AS target_id, target_name, target_class, "
                "NULL AS relation, moa, action_type, action_source_url AS act_source_url, "
                "moa_source AS moa_source_url FROM drugcentral_targets "
                f"WHERE drugcentral_id IN ({placeholders}) AND (target_name != '' OR moa != '') "
                "ORDER BY target_name LIMIT ?", [*ids, max(1, min(limit, 100))],
            ).fetchall())
    rows = rows[:max(1, min(limit, 100))]
    return {
        "drug_id": drug_id, "status": "evidence_found" if rows else "no_target_found",
        "targets": [dict(row) for row in rows], "source": "DrugCentral (CC BY-SA 4.0)",
        "source_url": "https://drugcentral.org/", "updated_at": _release_time(conn, "drugcentral"),
        "limitations": ["Target and MOA facts are mechanistic enrichment; they do not establish a clinical interaction or diagnosis."],
    }


@app.get("/api/drug/{drug_id}/mechanism")
async def drug_mechanism(drug_id: str, limit: int = 30):
    return _drugcentral_targets_payload(drug_id, limit)


def _indications_payload(drug_id: str, limit: int = 20) -> dict:
    conn = get_conn()
    names = _drug_names(conn, drug_id)
    query = urllib.parse.quote_plus(names[0] if names else drug_id)
    records = []
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='label_section'").fetchone():
        columns = {row[1] for row in conn.execute("PRAGMA table_info(label_section)")}
        if "indications_and_usage" in columns:
            clauses, params = [], []
            for name in names[:20]:
                pattern = f"%{name.upper()}%"
                clauses.append("(UPPER(COALESCE(generic_name, '')) LIKE ? OR UPPER(COALESCE(brand_name, '')) LIKE ? OR UPPER(COALESCE(openfda_generic, '')) LIKE ?)")
                params.extend([pattern, pattern, pattern])
            params.append(max(1, min(limit, 20)))
            records = [dict(row) for row in conn.execute(
                "SELECT set_id, effective_time, generic_name, brand_name, indications_and_usage "
                "FROM label_section WHERE indications_and_usage IS NOT NULL AND indications_and_usage != '' AND "
                + " OR ".join(clauses) + " ORDER BY effective_time DESC LIMIT ?", params,
            ).fetchall()]
    return {
        "drug_id": drug_id, "status": "evidence_found" if records else "outbound_reference_only",
        "indications": records, "source": "FDA labeling / DailyMed" if records else None,
        "references": [{"title": "Open Targets Platform", "source_url": f"https://platform.opentargets.org/search?q={query}"}],
        "limitations": [
            "Indication text is reference labeling, not a diagnosis or treatment recommendation.",
            "A missing local indication is unknown; this endpoint does not infer indications from ATC or mechanism data.",
        ],
    }


@app.get("/api/drug/{drug_id}/indications")
async def drug_indications(drug_id: str):
    return _indications_payload(drug_id)


def _lactmed_payload(drug_id: str) -> dict:
    conn = get_conn()
    has_local = bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='lactmed_records'").fetchone())
    names = _drug_names(conn, drug_id)
    if not names:
        raise HTTPException(404, "Drug not found")
    query = urllib.parse.quote_plus(f"{names[0]} LactMed")
    if not has_local:
        return {
            "drug_id": drug_id, "status": "unknown", "records": [],
            "drug_level_in_milk": None, "infant_exposure": None,
            "infant_adverse_effects": None, "therapeutic_alternatives": None,
            "references": [{"title": "LactMed database", "source": "NCBI Bookshelf", "source_url": f"https://www.ncbi.nlm.nih.gov/books/?term={query}"}],
            "limitations": ["No LactMed record is bulk-copied into this snapshot.", "Open the authoritative reference and consult a clinician for breastfeeding decisions."],
        }
    predicates = " OR ".join("LOWER(substance_name) = LOWER(?)" for _ in names[:20])
    rows = conn.execute(
        "SELECT substance_id, substance_name, revised_date, summary_of_use, drug_levels, infant_effects, "
        "lactation_effects, alternate_drugs, drug_class, source_url, downloaded_at "
        "FROM lactmed_records WHERE " + predicates + " ORDER BY revised_date DESC LIMIT 20", names[:20],
    ).fetchall()
    return {
        "drug_id": drug_id, "status": "evidence_found" if rows else "unknown",
        "records": [dict(row) for row in rows],
        "references": [{"title": "LactMed database", "source": "NCBI Bookshelf", "source_url": f"https://www.ncbi.nlm.nih.gov/books/?term={query}"}],
        "source": "NLM LactMed bulk NXML", "updated_at": _release_time(conn, "lactmed"),
        "limitations": ["LactMed is breastfeeding reference evidence, not a prescription or automatic compatibility verdict.", "Consult a clinician for infant age, prematurity, dose, timing, and maternal/infant conditions."],
    }


@app.get("/api/drug/{drug_id}/lactation")
async def drug_lactation(drug_id: str):
    return _lactmed_payload(drug_id)


def _recall_payload(drug_id: str, limit: int) -> dict:
    conn = get_conn()
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='fda_recalls'").fetchone():
        raise HTTPException(503, "FDA recall data is not available")
    names = _drug_names(conn, drug_id)
    clauses = ["LOWER(product_description) LIKE ?" for _ in names[:20]]
    rows = conn.execute(
        "SELECT event_id, product_type, classification, status, recalling_firm, product_description, "
        "reason_for_recall, recall_number, recall_initiation_date, center_classification_date, "
        "termination_date, source_url FROM fda_recalls WHERE " + " OR ".join(clauses) +
        " ORDER BY recall_initiation_date DESC LIMIT ?", [*(f"%{name.casefold()}%" for name in names[:20]), max(1, min(limit, 100))],
    ).fetchall()
    return {
        "drug_id": drug_id, "status": "recall_found" if rows else "no_matching_recall_found",
        "recalls": [dict(row) for row in rows], "source": "FDA openFDA enforcement (CC0)",
        "updated_at": _release_time(conn, "fda_recalls"),
        "limitations": ["Absence of a matching recall is not a safety clearance.", "Match is product-description text search; verify lot, date, market, and current FDA notice."],
    }


@app.get("/api/drug/{drug_id}/recalls")
async def drug_recalls(drug_id: str, limit: int = 30):
    return _recall_payload(drug_id, limit)


def _caers_payload(drug_id: str, limit: int) -> dict:
    conn = get_conn()
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='caers_product_events'").fetchone():
        raise HTTPException(503, "CAERS data is not available")
    names = _drug_names(conn, drug_id)
    clauses = ["(product_key = ? OR product_key LIKE ?)" for _ in names[:20]]
    params = [value for name in names[:20] for value in (_normalize_product_key(name), f"%{_normalize_product_key(name)}%")]
    params.append(max(1, min(limit, 100)))
    rows = conn.execute(
        "SELECT product_name, reaction, case_count, serious_count, first_seen, last_seen, source "
        "FROM caers_product_events WHERE " + " OR ".join(clauses) + " ORDER BY case_count DESC LIMIT ?", params,
    ).fetchall()
    return {
        "drug_id": drug_id, "status": "signal_found" if rows else "no_matching_signal_found",
        "events": [dict(row) for row in rows], "source": "FDA CAERS/openFDA (CC0)",
        "updated_at": _release_time(conn, "caers"),
        "limitations": ["CAERS reports are voluntary and unvalidated; they do not prove causality, incidence, or absolute risk.", "A report may list multiple products and reactions without a product-reaction attribution."],
    }


def _normalize_product_key(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^0-9a-z]+", " ", str(value or "").casefold())).strip()


@app.get("/api/drug/{drug_id}/caers-events")
async def drug_caers_events(drug_id: str, limit: int = 30):
    return _caers_payload(drug_id, limit)

def _clinical_summary_payload(drug_id: str, limit: int) -> dict:
    """Bundle reference layers without collapsing class and product evidence."""
    conn = get_conn()
    class_scope = bool(conn.execute("SELECT 1 FROM drug_classes WHERE id = ?", (drug_id,)).fetchone())
    calls = {
        "atc": lambda: _drugcentral_atc_payload(drug_id),
        "mechanism": lambda: _drugcentral_targets_payload(drug_id, limit),
        "indications": lambda: _indications_payload(drug_id, limit),
        "lactation": lambda: _lactmed_payload(drug_id),
        "recalls": lambda: _recall_payload(drug_id, limit),
        "caers": lambda: _caers_payload(drug_id, limit),
    }
    layers = {}
    for name, call in calls.items():
        try:
            layers[name] = call()
        except HTTPException as error:
            layers[name] = {"status": "unavailable", "detail": error.detail}
    if class_scope:
        for name in ("indications", "lactation", "recalls", "caers"):
            layer = layers.get(name) or {}
            layer["status"] = "class_scope"
            for key in ("indications", "records", "recalls", "events"):
                if key in layer:
                    layer[key] = []
            layers[name] = layer
    return {
        "drug_id": drug_id,
        "scope": "drug_class" if class_scope else "drug",
        "layers": layers,
        "limitations": [
            "These layers are separate reference evidence; they are not a diagnosis, prescription, or single safety score.",
            "Absence of a record is unknown, not proof of safety.",
            "Class-level results are examples; verify the exact ingredient, strength, formulation, route, and product label.",
        ],
    }


@app.get("/api/drug/{drug_id}/clinical-summary")
async def drug_clinical_summary(drug_id: str, limit: int = 10):
    return _clinical_summary_payload(drug_id, limit)


def _reference_payload(drug_id: str, reference: str) -> dict:
    conn = get_conn()
    class_row = conn.execute(
        "SELECT drugs FROM drug_classes WHERE id = ?", (drug_id,)
    ).fetchone()
    names = json.loads(class_row["drugs"] or "[]") if class_row else [drug_id]
    names = [str(name).strip() for name in names if str(name).strip()]
    if not names:
        raise HTTPException(404, "Drug not found")
    query = urllib.parse.quote_plus(names[0])
    references = {
        "medlineplus": {
            "title": "MedlinePlus drug information",
            "source_url": "https://medlineplus.gov/druginformation.html",
            "terms_url": "https://medlineplus.gov/about/using/usingcontent",
        },
        "livertox": {
            "title": "LiverTox",
            "source_url": f"https://www.ncbi.nlm.nih.gov/books/?term={query}+LiverTox",
            "terms_url": "https://www.ncbi.nlm.nih.gov/books/NBK548196/",
        },
        "open_targets": {
            "title": "Open Targets Platform",
            "source_url": f"https://platform.opentargets.org/search?q={query}",
            "terms_url": "https://platform-docs.opentargets.org/licence",
        },
    }
    item = references[reference]
    return {
        "drug_id": drug_id,
        "status": "outbound_reference_only",
        "reference": item,
        "use": (
            "Target/disease context is enrichment and must not replace direct DDI evidence."
            if reference == "open_targets"
            else "Open the authoritative source; this application does not bulk-copy its content."
        ),
        "limitations": [
            "Upstream source terms and attribution must be reviewed before embedding content.",
            "This link is not a diagnosis, prescription, or safety clearance.",
        ],
    }


@app.get("/api/drug/{drug_id}/medlineplus")
async def drug_medlineplus(drug_id: str):
    return _reference_payload(drug_id, "medlineplus")


@app.get("/api/drug/{drug_id}/livertox")
async def drug_livertox(drug_id: str):
    return _reference_payload(drug_id, "livertox")


@app.get("/api/drug/{drug_id}/targets")
async def drug_targets(drug_id: str):
    return _reference_payload(drug_id, "open_targets")


def _pharmacogenomics_payload(drug_id: str, limit: int) -> dict:
    conn = get_conn()
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='pharmgkb_relations'"
    ).fetchone()
    if not exists:
        raise HTTPException(503, "Pharmacogenomics data is not available")
    class_row = conn.execute(
        "SELECT drugs FROM drug_classes WHERE id = ?", (drug_id,)
    ).fetchone()
    names = json.loads(class_row["drugs"] or "[]") if class_row else [drug_id]
    names = list(dict.fromkeys(str(name).strip() for name in names if str(name).strip()))
    if not names:
        raise HTTPException(404, "Drug not found")
    predicates = []
    params: list[str] = []
    for name in names[:20]:
        pattern = f"%{name.casefold()}%"
        predicates.append(
            "((LOWER(ent1_type) = 'chemical' AND LOWER(ent1_name) LIKE ?) "
            "OR (LOWER(ent2_type) = 'chemical' AND LOWER(ent2_name) LIKE ?))"
        )
        params.extend([pattern, pattern])
    params.append(max(1, min(limit, 100)))
    rows = conn.execute(
        "SELECT ent1_id, ent1_name, ent1_type, ent2_id, ent2_name, ent2_type, "
        "evidence, association, pk, pd, pmids FROM pharmgkb_relations WHERE "
        + " OR ".join(predicates)
        + " ORDER BY row_ord LIMIT ?",
        params,
    ).fetchall()
    relationships = []
    for row in rows:
        if str(row["ent1_type"]).casefold() == "gene":
            gene_name, gene_id = row["ent1_name"], row["ent1_id"]
            chemical_name, chemical_id = row["ent2_name"], row["ent2_id"]
        else:
            gene_name, gene_id = row["ent2_name"], row["ent2_id"]
            chemical_name, chemical_id = row["ent1_name"], row["ent1_id"]
        relationships.append(
            {
                "chemical": {"id": chemical_id, "name": chemical_name},
                "gene": {"id": gene_id, "name": gene_name},
                "association": row["association"],
                "evidence": row["evidence"],
                "pk": row["pk"],
                "pd": row["pd"],
                "pmids": row["pmids"],
            }
        )
    return {
        "drug_id": drug_id,
        "relationships": relationships,
        "recommendation": (
            "No personal recommendation is made without a validated genotype or "
            "phenotype and clinical context."
        ),
        "source": "ClinPGx/PharmGKB",
        "source_url": "https://www.clinpgx.org/page/dataUsagePolicy",
        "license": "CC BY-SA 4.0; attribution and share-alike apply.",
        "limitations": [
            "Associations are not a dose instruction.",
            "Genotype, phenotype, indication, and co-medications must be reviewed clinically.",
        ],
    }


@app.get("/api/drug/{drug_id}/pharmacogenomics")
async def drug_pharmacogenomics(drug_id: str, limit: int = 30):
    return _pharmacogenomics_payload(drug_id, limit)

@app.post("/api/pharmacogenomics/check")
async def pharmacogenomics_check(payload: PharmacogenomicsCheckRequest):
    genotype_provided = payload.genotype not in (None, "", {})
    phenotype_provided = payload.phenotype not in (None, "", {})
    base = _pharmacogenomics_payload(payload.drug_id, 100)
    if not genotype_provided and not phenotype_provided:
        return {
            **base,
            "status": "unknown",
            "recommendation": None,
            "message": (
                "Provide a validated genotype or phenotype before interpreting "
                "pharmacogenomic evidence."
            ),
            "input_context": {
                "genotype_provided": False,
                "phenotype_provided": False,
                "indication": payload.indication,
            },
        }
    return {
        **base,
        "status": "review_required",
        "recommendation": (
            "Use the supplied genotype/phenotype only with a validated CPIC/DPWG "
            "or equivalent clinical guideline; no automatic dose recommendation is made."
        ),
        "input_context": {
            "genotype_provided": genotype_provided,
            "phenotype_provided": phenotype_provided,

            "indication": payload.indication,
        },
    }


def _context_payload(drug_id: str, profile: dict | None) -> dict:
    profile = profile or {}
    def _context_text(value) -> str:
        if isinstance(value, dict):
            return str(value.get("status") or value.get("state") or "")
        return str(value)
    aliases = {
        "pregnancy": ("pregnancyStatus", "pregnancy_status", "pregnancy"),
        "lactation": ("lactationStatus", "lactation_status", "breastfeeding"),
        "renal": ("kidneyFunction", "renalFunction", "renal_impairment"),
        "hepatic": ("liverFunction", "hepaticFunction", "hepatic_impairment"),
        "age": ("age",),
    }
    contexts: dict[str, dict] = {}
    missing: list[str] = []
    for name, keys in aliases.items():
        value = next((profile[key] for key in keys if key in profile), None)
        known = value not in (None, "", "unknown", "not_provided")
        contexts[name] = {"status": "known" if known else "unknown", "value": value if known else None}
        if not known:
            missing.append(name)
    try:
        age = float(contexts["age"]["value"]) if contexts["age"]["status"] == "known" else None
    except (TypeError, ValueError):
        age = None
        contexts["age"] = {"status": "unknown", "value": None}
        if "age" not in missing:
            missing.append("age")
    try:
        labels = _label_payload(
            drug_id,
            {"pregnancy", "lactation", "renal_impairment", "hepatic_impairment",
             "pediatric_use", "geriatric_use"},
        )["sections"]
    except HTTPException:
        labels = []
    labels_by_section: dict[str, list[dict]] = {}
    for label in labels:
        labels_by_section.setdefault(label["section"], []).append(label)
    checks = (
        ("pregnancy", "pregnancy", lambda value: _context_text(value).casefold() in {"pregnant", "yes", "true"}),
        ("lactation", "lactation", lambda value: _context_text(value).casefold() in {"breastfeeding", "lactating", "yes", "true"}),
        ("renal", "renal_impairment", lambda value: "impairment" in _context_text(value).casefold()),
        ("hepatic", "hepatic_impairment", lambda value: "impairment" in _context_text(value).casefold()),
    )
    alerts = []
    for context_name, section_name, active in checks:
        context = contexts[context_name]
        if context["status"] != "known" or not active(context["value"]):
            continue
        alerts.append(
            {
                "context": context_name,
                "status": "known" if labels_by_section.get(section_name) else "unknown",
                "label_sections": labels_by_section.get(section_name, []),
                "message": (
                    "Matching authoritative label text is unavailable in this snapshot."
                    if not labels_by_section.get(section_name)
                    else "Review the matching label section with a clinician."
                ),
            }
        )
    if age is not None and age >= 65:
        section = "geriatric_use"
        alerts.append({
            "context": "geriatric",
            "status": "known" if labels_by_section.get(section) else "unknown",
            "label_sections": labels_by_section.get(section, []),
            "message": "Age boundary is explicit; do not infer dosing from age alone.",
        })
    elif age is not None and age < 18:
        section = "pediatric_use"
        alerts.append({
            "context": "pediatric",
            "status": "known" if labels_by_section.get(section) else "unknown",
            "label_sections": labels_by_section.get(section, []),
            "message": "Age boundary is explicit; do not infer pediatric dosing from this endpoint.",
        })
    return {
        "drug_id": drug_id,
        "contexts": contexts,
        "missing_context": missing,
        "alerts": alerts,
        "limitations": [
            "Missing context is unknown, not normal or safe.",
            "This endpoint does not calculate or recommend a dose.",
        ],
    }


@app.post("/api/drug/{drug_id}/context")
async def drug_context(drug_id: str, profile: dict | None = None):
    return _context_payload(drug_id, profile)


def _mendeley_food_evidence(drug_id: str, limit: int) -> dict:
    conn = get_conn()
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='mendeley_drug_food_2021'"
    ).fetchone()
    if not exists:
        raise HTTPException(503, "Mendeley drug-food evidence is not available")
    class_row = conn.execute(
        "SELECT drugs FROM drug_classes WHERE id = ?", (drug_id,)
    ).fetchone()
    names = json.loads(class_row["drugs"] or "[]") if class_row else [drug_id]
    names = list(dict.fromkeys(str(name).strip() for name in names if str(name).strip()))
    if not names:
        raise HTTPException(404, "Drug not found")
    predicates = ["LOWER(drug_constituent) LIKE ?" for _ in names[:20]]
    params = [f"%{name.casefold()}%" for name in names[:20]]
    params.append(max(1, min(limit, 100)))
    rows = conn.execute(
        "SELECT label, food_constituent, food_smiles, drug_constituent, drug_smiles, "
        "interaction, source FROM mendeley_drug_food_2021 WHERE "
        + " OR ".join(predicates)
        + " ORDER BY label DESC LIMIT ?",
        params,
    ).fetchall()
    return {
        "drug_id": drug_id,
        "evidence": [
            {
                "label": row["label"],
                "food_constituent": row["food_constituent"],
                "food_smiles": row["food_smiles"],
                "drug_constituent": row["drug_constituent"],
                "drug_smiles": row["drug_smiles"],
                "interaction": row["interaction"],
                "source": row["source"],
                "confidence": None,
                "confidence_basis": "Not provided by the source dataset.",
                "evidence_type": "research_evidence",
            }
            for row in rows
        ],
        "limitations": [
            "Food/drug constituents are not automatically mapped to common food categories.",
            "Research evidence is not an FDA contraindication or a severity classification.",
            "The dataset label is reported evidence, not incidence or causality.",
        ],
    }


@app.get("/api/drug/{drug_id}/food-evidence")
async def drug_food_evidence(drug_id: str, limit: int = 30):
    return _mendeley_food_evidence(drug_id, limit)

def _faers_drug_keys(drug_id: str, conn) -> list[str]:
    from .faers import _normalize_name

    class_row = conn.execute(
        "SELECT drugs FROM drug_classes WHERE id = ?", (drug_id,)
    ).fetchone()
    if class_row:
        names = json.loads(class_row["drugs"] or "[]")
    else:
        names = [drug_id]
        if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='drug_name_mapping'"
        ).fetchone():
            names.extend(
                row["raw_name"]
                for row in conn.execute(
                    "SELECT raw_name FROM drug_name_mapping "
                    "WHERE entity_type = 'drug_ingredient' AND entity_id = ?",
                    (drug_id,),
                )
            )
    return list(dict.fromkeys(_normalize_name(name) for name in names if _normalize_name(name)))


def _faers_adverse_events(drug_id: str, limit: int, quarter: str | None):
    if quarter and not re.fullmatch(r"\d{4}Q[1-4]", quarter):
        raise HTTPException(400, "quarter must use YYYYQn format")
    conn = get_conn()
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='faers_adverse_events'"
    ).fetchone()
    if not exists:
        raise HTTPException(503, "FAERS adverse-event aggregate is not built")
    keys = _faers_drug_keys(drug_id, conn)
    if not keys:
        raise HTTPException(404, "Drug not found")
    placeholders = ",".join("?" for _ in keys)
    params: list[str | int] = list(keys)
    quarter_filter = ""
    if quarter:
        quarter_filter = " AND quarter = ?"
        params.append(quarter)
    params.append(max(1, min(limit, 100)))
    rows = conn.execute(
        "SELECT pt, SUM(case_count) AS case_count, "
        "SUM(serious_case_count) AS serious_case_count, "
        "SUM(primary_suspect_case_count) AS primary_suspect_case_count, "
        "SUM(secondary_case_count) AS secondary_case_count, "
        "SUM(concomitant_case_count) AS concomitant_case_count, "
        "MIN(first_seen) AS first_seen, MAX(last_seen) AS last_seen, "
        "GROUP_CONCAT(DISTINCT quarter) AS quarters, MIN(source) AS source "
        "FROM faers_adverse_events "
        f"WHERE drug_key IN ({placeholders}){quarter_filter} "
        "GROUP BY pt ORDER BY case_count DESC LIMIT ?",
        params,
    ).fetchall()
    if not rows:
        raise HTTPException(404, "No FAERS adverse-event data for drug")
    updated = conn.execute(
        "SELECT MAX(downloaded_at) FROM dataset_release WHERE source_code = 'faers'"
    ).fetchone()[0]
    return {
        "drug_id": drug_id,
        "events": [
            {
                "term": row["pt"],
                "case_count": row["case_count"],
                "serious_case_count": row["serious_case_count"],
                "first_seen": row["first_seen"],
                "last_seen": row["last_seen"],
                "quarter": quarter or row["quarters"],
                "role_case_counts": {
                    "PS": row["primary_suspect_case_count"],
                    "SS": row["secondary_case_count"],
                    "C": row["concomitant_case_count"],
                },
                "source": row["source"] or "FDA FAERS",
            }
            for row in rows
        ],
        "limitations": [
            "Spontaneous reports do not prove causality.",
            "Counts are not incidence or absolute risk.",
            "A case may mention multiple drugs and reactions.",
        ],
        "updated_at": updated,
    }


@app.get("/api/drug/{drug_id}/adverse-events")
async def drug_adverse_events(drug_id: str, limit: int = 30, quarter: str | None = None):
    return _faers_adverse_events(drug_id, limit, quarter)


@app.get("/api/class/{class_id}/adverse-events")
async def class_adverse_events(class_id: str, limit: int = 30, quarter: str | None = None):
    if not get_engine().class_detail(class_id):
        raise HTTPException(404, "Drug class not found")
    return _faers_adverse_events(class_id, limit, quarter)


def _onsides_ingredient_keys(drug_id: str, conn) -> list[str]:
    from .unify import _normalized_name, _rxnorm_lookup

    class_row = conn.execute(
        "SELECT drugs FROM drug_classes WHERE id = ?", (drug_id,)
    ).fetchone()
    names = json.loads(class_row["drugs"] or "[]") if class_row else [drug_id]
    lookup = _rxnorm_lookup(conn)
    keys = []
    for name in names:
        normalized = _normalized_name(str(name))
        item = lookup.get(normalized)
        if item:
            keys.append(item["rxcui"])
    if drug_id.isdigit():
        keys.append(drug_id)
    return list(dict.fromkeys(keys))


def _onsides_adverse_effects(drug_id: str, limit: int) -> dict:
    conn = get_conn()
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='onsides_ingredient_effects'"
    ).fetchone()
    if not exists:
        raise HTTPException(503, "OnSIDES adverse-effect aggregate is not built")
    keys = _onsides_ingredient_keys(drug_id, conn)
    if not keys:
        return {
            "drug_id": drug_id,
            "status": "unknown_unmatched",
            "effects": [],
            "limitations": ["The drug could not be mapped to a RxNorm ingredient."],
        }
    placeholders = ",".join("?" for _ in keys)
    rows = conn.execute(
        "SELECT rxnorm_ingredient_id, rxnorm_ingredient_name, effect_meddra_id, effect, "
        "GROUP_CONCAT(DISTINCT source_region) AS regions, SUM(row_count) AS row_count, "
        "SUM(label_count) AS label_count, MIN(min_pred1) AS min_pred1, "
        "MAX(max_pred1) AS max_pred1, MAX(high_confidence) AS high_confidence "
        "FROM onsides_ingredient_effects WHERE rxnorm_ingredient_id IN ("
        + placeholders
        + ") GROUP BY rxnorm_ingredient_id, effect_meddra_id, effect "
        "ORDER BY row_count DESC LIMIT ?",
        [*keys, max(1, min(limit, 100))],
    ).fetchall()
    updated = conn.execute(
        "SELECT MAX(downloaded_at) FROM dataset_release WHERE source_code = 'onsides'"
    ).fetchone()[0]
    return {
        "drug_id": drug_id,
        "status": "evidence_found" if rows else "no_documented_effect_found",
        "effects": [
            {
                "ingredient_id": row["rxnorm_ingredient_id"],
                "ingredient_name": row["rxnorm_ingredient_name"],
                "meddra_id": row["effect_meddra_id"],
                "effect": row["effect"],
                "regions": (row["regions"] or "").split(",") if row["regions"] else [],
                "row_count": row["row_count"],
                "label_count": row["label_count"],
                "pred1_range": [row["min_pred1"], row["max_pred1"]],
                "high_confidence": bool(row["high_confidence"]),
                "source": "OnSIDES v3.1.1 (CC BY 4.0)",
            }
            for row in rows
        ],
        "updated_at": updated,
        "limitations": [
            "OnSIDES reports adverse-event associations; it does not prove causality or incidence.",
            "Effect counts are evidence volume, not patient risk.",
        ],
    }

def _evidence_intersection(drug_id: str, limit: int) -> dict:
    conn = get_conn()
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='evidence_ontology_intersection'"
    ).fetchone()
    if not exists:
        raise HTTPException(503, "Evidence ontology intersection is not built")
    keys = _onsides_ingredient_keys(drug_id, conn)
    if not keys:
        return {
            "drug_id": drug_id,
            "status": "unknown_unmatched",
            "ingredients": [],
            "limitations": ["The drug could not be mapped to a RxNorm ingredient."],
        }
    placeholders = ",".join("?" for _ in keys)
    rows = conn.execute(
        "SELECT rxnorm_ingredient_id, rxnorm_ingredient_name, sources, source_count, "
        "onsides_effect_count, onsides_row_count, onsides_label_count, onsides_regions, "
        "onsides_high_confidence_count, faers_case_count, faers_term_count, label_count, "
        "match_method, ontology_version, built_at "
        "FROM evidence_ontology_intersection WHERE rxnorm_ingredient_id IN ("
        + placeholders
        + ") ORDER BY source_count DESC, faers_case_count DESC LIMIT ?",
        [*keys, max(1, min(limit, 100))],
    ).fetchall()
    return {
        "drug_id": drug_id,
        "status": "evidence_intersection_found" if rows else "no_intersection_found",
        "ingredients": [
            {
                "ingredient_id": row["rxnorm_ingredient_id"],
                "ingredient_name": row["rxnorm_ingredient_name"],
                "sources": json.loads(row["sources"]),
                "source_count": row["source_count"],
                "onsides_effect_count": row["onsides_effect_count"],
                "onsides_row_count": row["onsides_row_count"],
                "onsides_label_count": row["onsides_label_count"],
                "onsides_regions": json.loads(row["onsides_regions"]),
                "onsides_high_confidence_count": row["onsides_high_confidence_count"],
                "faers_case_count": row["faers_case_count"],
                "faers_term_count": row["faers_term_count"],
                "label_count": row["label_count"],
                "match_method": row["match_method"],
                "ontology_version": row["ontology_version"],
                "built_at": row["built_at"],
            }
            for row in rows
        ],
        "limitations": [
            "The intersection is ingredient-level evidence joined by exact RxNorm identity.",
            "OnSIDES MedDRA effects are not merged with FAERS or label text without a validated crosswalk.",
            "Multiple-source evidence does not prove causality, incidence, or clinical safety.",
        ],
    }


@app.get("/api/drug/{drug_id}/evidence-intersection")
async def drug_evidence_intersection(drug_id: str, limit: int = 30):
    return _evidence_intersection(drug_id, limit)


@app.get("/api/drug/{drug_id}/adverse-effects")
async def drug_adverse_effects(drug_id: str, limit: int = 30):
    return _onsides_adverse_effects(drug_id, limit)

@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    if len(req.items) > 50:
        raise HTTPException(413, "A maximum of 50 analysis items is allowed")
    payload = []
    for i in req.items:
        item = i.model_dump()
        item["name"] = item.get("name") or item.get("label") or ""
        payload.append(item)
    return get_engine().analyze(payload, profile=req.profile)


# --- barcode lookup via Open Food Facts (free, no key) ---
def _fetch_off(barcode: str) -> dict | None:
    url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
    req = urllib.request.Request(url, headers={"User-Agent": "MedMatchAI/0.1 (health reference tool)"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _fetch_upcitemdb(barcode: str) -> dict | None:
    """Fallback barcode lookup via UPCitemdb (100/day free, needs key)."""
    key = os.environ.get("UPCITEMDB_KEY")
    if not key:
        return None
    url = "https://api.upcitemdb.com/prod/trial/lookup"
    req = urllib.request.Request(url, data=json.dumps({"upc": barcode}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        items = data.get("items") or []
        if not items:
            return None
        it = items[0]
        return {"name": it.get("title") or it.get("description"),
                "brand": it.get("brand"), "ingredients": []}
    except Exception:
        return None


@app.get("/api/lookup/{barcode}")
async def lookup(barcode: str):
    if not barcode.isdigit() or len(barcode) < 6:
        raise HTTPException(400, "Invalid barcode")
    # local product index cache-hit (NDC drug / DSLD supplement), no network
    from . import product_index
    conn = get_conn()
    hit = product_index.lookup(conn, barcode)
    if hit:
        matched = []
        try:
            for m in json.loads(hit.get("matched") or "[]"):
                matched.append({
                    "kind": m.get("kind"),
                    "entity_id": m.get("id"),
                    "label": m.get("label"),
                    "ingredient": m.get("ingredient"),
                })
        except Exception:
            matched = []
        return {"barcode": barcode, "name": hit.get("name") or f"Product {barcode}",
                "brands": hit.get("brand"), "product_type": hit.get("product_type"),
                "ingredients": [s.strip() for s in (hit.get("ingredients") or "").split(";") if s.strip()][:40],
                "excipients": [s.strip() for s in (hit.get("excipients") or "").split(";") if s.strip()][:40],
                "matched_ingredients": matched[:10],
                "source": f"product-index:{hit.get('code_type')}"}
    data = _fetch_off(barcode)
    if not data or data.get("status") != 1:
        # NIH DSLD — US dietary supplement labels (public domain), bulk-imported
        from .dsld import lookup as dsld_lookup
        dsld = dsld_lookup(barcode)
        if dsld:
            ingredients = [s.strip() for s in (dsld.get("ingredients") or "").split(",") if s.strip()]
            return {"barcode": barcode, "name": dsld.get("name") or f"DSLD {barcode}",
                    "brands": dsld.get("brand") or "", "ingredients": ingredients,
                    "matched_ingredients": [], "source": "NIH DSLD"}
        fallback = _fetch_upcitemdb(barcode)
        if not fallback:
            raise HTTPException(404, "Product not found (Open Food Facts + NIH DSLD + UPCitemdb)")
        return {"barcode": barcode, "name": fallback["name"], "brands": fallback["brand"],
                "ingredients": [], "matched_ingredients": [], "source": "UPCitemdb"}
    p = data["product"]
    ingredients = []
    for key in ("ingredients_text", "ingredients_text_en"):
        text = p.get(key)
        if text:
            ingredients = [s.strip() for s in text.split(",") if s.strip()]
            break
    if not ingredients and isinstance(p.get("ingredients"), list):
        ingredients = [i.get("text", "") for i in p["ingredients"] if i.get("text")]

    # pre-match ingredients against our herb index
    engine = get_engine()
    matched_ingredients = []
    seen_ids = set()
    for ing in ingredients[:40]:
        m = engine.match(ing, max_results=1)
        if m and m[0]["kind"] == "herb" and m[0]["score"] >= 0.85 and m[0]["id"] not in seen_ids:
            seen_ids.add(m[0]["id"])
            d = engine.herb_detail(m[0]["id"])
            matched_ingredients.append({
                "input": ing,
                "herb_id": m[0]["id"],
                "label": m[0]["label"],
                "warns_against": [i["class_name"] for i in (d.get("interactions") or [])][:6],
            })
    return {
        "barcode": barcode,
        "name": p.get("product_name") or p.get("product_name_en") or p.get("generic_name") or "Unknown product",
        "brands": p.get("brands"),
        "quantity": p.get("quantity"),
        "categories": p.get("categories"),
        "ingredients": ingredients[:40],
        "matched_ingredients": matched_ingredients,
        "source": "Open Food Facts",
    }


@app.get("/api/review/next")
async def review_next(x_admin_token: str | None = Header(default=None)):
    _require_admin(x_admin_token)
    from .db import get_conn
    from . import quality_gate
    return quality_gate.next_pending(get_conn()) or {}


@app.post("/api/review/{queue_id}")
async def review_do(
    queue_id: int,
    status: str = "verified",
    note: str = "",
    x_admin_token: str | None = Header(default=None),
):
    _require_admin(x_admin_token)
    from .db import get_conn
    from . import quality_gate
    if not quality_gate.review(get_conn(), queue_id, status, note):
        raise HTTPException(404, "Not found or already reviewed")
    return {"status": "ok"}

# iDISK product search: name -> product -> ingredients (herb-resolved)
@app.get("/api/products")
async def products(q: str = "", limit: int = 10):
    if not q.strip():
        return {"query": q, "results": []}
    from .db import get_conn
    from . import idisk_products
    conn = get_conn()
    results = []
    for p in idisk_products.search_products(conn, q.strip(), limit=min(limit, 20)):
        ingredients = idisk_products.product_ingredients(conn, p["dsp_id"])
        results.append({**p, "ingredients": ingredients[:12]})
    return {"query": q, "results": results}



@app.get("/api/unified/stats")
async def unified_stats():
    from .db import get_conn
    conn = get_conn()
    return {
        "pairs": conn.execute("SELECT COUNT(*) FROM interaction_unified").fetchone()[0],
        "inferred": conn.execute("SELECT COUNT(*) FROM interaction_unified WHERE is_inferred=1").fetchone()[0],
        "standards": conn.execute("SELECT COUNT(*) FROM standard_ingredient").fetchone()[0],
        "synonyms": conn.execute("SELECT COUNT(*) FROM ingredient_synonyms").fetchone()[0],
        "multi_source_pairs": conn.execute(
            "SELECT COUNT(*) FROM interaction_unified WHERE json_array_length(evidence) >= 2"
        ).fetchone()[0],
    }

@app.get("/api/ddi/mapping-report")
async def ddi_mapping_report(source: str | None = None):
    """Report exact raw-name mappings without exposing fuzzy review guesses."""
    conn = get_conn()
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='drug_name_mapping'"
    ).fetchone()
    if not exists:
        return {"sources": {}, "ingredient_level_pairs": 0, "class_level_pairs": 0}
    params: tuple[str, ...] = (source,) if source else ()
    where = "WHERE source = ?" if source else ""
    rows = conn.execute(
        "SELECT source, match_method, COUNT(*) AS count "
        f"FROM drug_name_mapping {where} GROUP BY source, match_method",
        params,
    ).fetchall()
    grouped: dict[str, dict] = {}
    for row in rows:
        item = grouped.setdefault(
            row["source"],
            {"mapped": 0, "unmapped": 0, "excluded": 0, "review_pending": 0, "methods": {}},
        )
        item["methods"][row["match_method"]] = row["count"]
        if row["match_method"] == "unmapped":
            item["unmapped"] += row["count"]
        elif row["match_method"].startswith("excluded_"):
            item["excluded"] += row["count"]
        else:
            item["mapped"] += row["count"]
    ingredient_pairs = conn.execute(
        "SELECT COUNT(*) FROM interaction_unified "
        "WHERE a_kind = 'drug_ingredient' OR b_kind = 'drug_ingredient'"
    ).fetchone()[0]
    class_pairs = conn.execute(
        "SELECT COUNT(*) FROM interaction_unified "
        "WHERE a_kind = 'drug_class' AND b_kind = 'drug_class'"
    ).fetchone()[0]
    component_table = conn.execute(
        "SELECT 1 FROM sqlite_master "
        "WHERE type = 'table' AND name = 'drug_name_mapping_component'"
    ).fetchone()
    ingredient_components = (
        conn.execute(
            "SELECT COUNT(*) FROM drug_name_mapping_component "
            "WHERE entity_type = 'drug_ingredient'"
        ).fetchone()[0]
        if component_table
        else 0
    )
    review_table = conn.execute(
        "SELECT 1 FROM sqlite_master "
        "WHERE type = 'table' AND name = 'drug_name_mapping_review'"
    ).fetchone()
    if review_table:
        for row in conn.execute(
            "SELECT source, COUNT(*) AS count "
            "FROM drug_name_mapping_review WHERE status = 'pending' "
            "GROUP BY source"
        ):
            grouped.setdefault(
                row["source"],
                {"mapped": 0, "unmapped": 0, "excluded": 0, "review_pending": 0, "methods": {}},
            )["review_pending"] = row["count"]
    return {
        "sources": grouped,
        "ingredient_level_pairs": ingredient_pairs,
        "class_level_pairs": class_pairs,
        "ingredient_components": ingredient_components,
    }


@app.get("/api/ddi/mapping-review/next")
async def ddi_mapping_review_next(
    source: str | None = None,
    limit: int = 20,
    x_admin_token: str | None = Header(default=None),
):
    _require_admin(x_admin_token)
    conn = get_conn()
    clauses = ["status = 'pending'"]
    params: list[str | int] = []
    if source:
        clauses.append("source = ?")
        params.append(source)
    params.append(min(max(limit, 1), 100))
    rows = conn.execute(
        "SELECT * FROM drug_name_mapping_review "
        f"WHERE {' AND '.join(clauses)} ORDER BY source, raw_name LIMIT ?",
        params,
    ).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.post("/api/ddi/mapping-review/resolve")
async def ddi_mapping_review_resolve(
    payload: DrugMappingReviewRequest,
    x_admin_token: str | None = Header(default=None),
):
    _require_admin(x_admin_token)
    if payload.status not in {"verified", "rejected"}:
        raise HTTPException(400, "status must be verified or rejected")
    conn = get_conn()
    queue = conn.execute(
        "SELECT * FROM drug_name_mapping_review "
        "WHERE source = ? AND raw_name = ? AND status = 'pending'",
        (payload.source, payload.raw_name),
    ).fetchone()
    if not queue:
        raise HTTPException(404, "Mapping review item not found or already resolved")
    if payload.status == "verified":
        if payload.entity_type not in {"drug_ingredient", "drug_class", "non_drug"}:
            raise HTTPException(400, "verified mapping requires a supported entity_type")
        if payload.entity_type != "non_drug" and not payload.entity_id:
            raise HTTPException(400, "verified mapping requires entity_id")
        component_ids = list(dict.fromkeys(payload.component_ids or (
            [payload.entity_id] if payload.entity_type == "drug_ingredient" else []
        )))
        if payload.entity_type == "drug_ingredient" and not component_ids:
            raise HTTPException(400, "drug_ingredient mapping requires component_ids")
        normalized = re.sub(
            r"\s+", " ",
            re.sub(r"[^0-9A-Za-z]+", " ", payload.raw_name.casefold()),
        ).strip()
        conn.execute(
            "UPDATE drug_name_mapping SET normalized_name = ?, entity_type = ?, "
            "entity_id = ?, rxcui = ?, confidence = 1.0, "
            "match_method = 'manual_review', reviewed = 1 "
            "WHERE source = ? AND raw_name = ?",
            (
                normalized,
                payload.entity_type,
                None if payload.entity_type == "non_drug" else payload.entity_id,
                None if payload.entity_type != "drug_ingredient" else (payload.rxcui or payload.entity_id),
                payload.source,
                payload.raw_name,
            ),
        )
        conn.execute(
            "DELETE FROM drug_name_mapping_component WHERE source = ? AND raw_name = ?",
            (payload.source, payload.raw_name),
        )
        if payload.entity_type == "drug_ingredient":
            conn.executemany(
                "INSERT INTO drug_name_mapping_component "
                "(source, raw_name, component_index, entity_type, entity_id, "
                "rxcui, confidence, match_method) VALUES (?,?,?,?,?,?,?,?)",
                [
                    (
                        payload.source, payload.raw_name, index,
                        "drug_ingredient", component_id, component_id,
                        1.0, "manual_review",
                    )
                    for index, component_id in enumerate(component_ids)
                ],
            )
    else:
        conn.execute(
            "UPDATE drug_name_mapping SET entity_type = NULL, entity_id = NULL, "
            "rxcui = NULL, confidence = 0.0, match_method = 'unmapped', reviewed = 1 "
            "WHERE source = ? AND raw_name = ?",
            (payload.source, payload.raw_name),
        )
    conn.execute(
        "UPDATE drug_name_mapping_review SET status = ?, note = ?, reviewed_at = datetime('now') "
        "WHERE source = ? AND raw_name = ?",
        (payload.status, payload.note, payload.source, payload.raw_name),
    )
    conn.commit()
    from . import unify
    stats = unify.build_unified(conn)
    return {"status": payload.status, "source": payload.source,
            "raw_name": payload.raw_name, "unified": stats}


@app.get("/api/unified/pair")
async def unified_pair(a_kind: str, a_id: str, b_kind: str, b_id: str):
    import json as _json
    from .db import get_conn
    conn = get_conn()
    key = "|".join(sorted([f"{a_kind}:{a_id}", f"{b_kind}:{b_id}"]))
    row = conn.execute(
        "SELECT * FROM interaction_unified WHERE pair_key = ?", (key,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Pair not found in unified layer")
    d = dict(row)
    d["evidence"] = _json.loads(d["evidence"] or "[]")
    d["matchLevel"] = (
        "ingredient"
        if "drug_ingredient" in (d["a_kind"], d["b_kind"])
        else "class"
    )
    d["sourceText"] = d.get("effect")
    return d


@app.get("/api/ai_reviews/stats")
async def ai_reviews_stats(x_admin_token: str | None = Header(default=None)):
    _require_admin(x_admin_token)
    from .db import get_conn
    conn = get_conn()
    rows = conn.execute("SELECT verdict, COUNT(*) n FROM ai_reviews GROUP BY verdict").fetchall()
    total = conn.execute("SELECT COUNT(*) FROM ai_reviews").fetchone()[0]
    return {
        "total": total,
        "by_verdict": {r["verdict"]: r["n"] for r in rows},
        "accuracy": round(100 * sum(r["n"] for r in rows if r["verdict"] == "correct") / total, 1) if total else 0,
    }


@app.get("/api/ai_reviews/flagged")
async def ai_reviews_flagged(
    limit: int = 20,
    x_admin_token: str | None = Header(default=None),
):
    _require_admin(x_admin_token)
    from .db import get_conn
    conn = get_conn()
    names = {}
    for kind, table in (("herb", "herbs"), ("drug_class", "drug_classes"), ("food", "foods")):
        names.update({(kind, r["id"]): r["name_en"] for r in conn.execute(f"SELECT id, name_en FROM {table}")})
    out = []
    for r in conn.execute(
        "SELECT ur.*, ar.verdict, ar.reasoning FROM ai_reviews ar"
        " JOIN interaction_unified ur ON ur.pair_key = ar.pair_key"
        " WHERE ar.verdict = 'incorrect' LIMIT ?", (min(limit, 100),)
    ):
        d = dict(r)
        d["a_label"] = names.get((d["a_kind"], d["a_id"]), d["a_id"])
        d["b_label"] = names.get((d["b_kind"], d["b_id"]), d["b_id"])
        d["evidence"] = None  # keep payload light
        out.append(d)
    return {"flagged": out}


@app.get("/api/class/{class_id}/effects")
async def class_effects(class_id: str, limit: int = 15):
    """Top OnSIDES side effects for a drug class."""
    from .db import get_conn
    conn = get_conn()
    rows = conn.execute(
        "SELECT effect, SUM(n) n FROM onsides_effects WHERE cls_a = ?"
        " GROUP BY effect ORDER BY n DESC LIMIT ?", (class_id, min(limit, 30))
    ).fetchall()
    if not rows:
        raise HTTPException(404, "No side effect data for this class")
    return {"class_id": class_id,
            "effects": [{"effect": r["effect"], "reports": r["n"]} for r in rows],
            "source": "OnSIDES (CC BY 4.0, PubMedBERT from FDA/EMA/EMC/KEGG labels)"}


@app.get("/favicon.ico")
async def favicon():
    return FileResponse(STATIC_DIR / "favicon.svg")


@app.get("/scanner")
@app.get("/scanner/{full_path:path}")
async def scanner_app(full_path: str = ""):
    """Serve the built React scanner SPA (assets under /scanner/assets/...)."""
    if full_path:
        target = (SCANNER_DIST / full_path).resolve()
        try:
            target.relative_to(SCANNER_DIST.resolve())
        except ValueError:
            raise HTTPException(404, "Not found")
        if target.is_file():
            return FileResponse(target)
    return FileResponse(SCANNER_DIST / "index.html")

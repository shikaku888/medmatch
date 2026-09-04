"""Product identity graph for consented, multilingual product observations.

The graph is separate from the clinical database and device profiles. It stores
product-level facts only; raw images, receipts, profile data, and device tokens
are intentionally outside this module.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS product_family (
    family_id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    brand TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS market_sku (
    sku_id TEXT PRIMARY KEY,
    family_id TEXT NOT NULL REFERENCES product_family(family_id),
    identity_key TEXT NOT NULL UNIQUE,
    market_code TEXT NOT NULL,
    language_code TEXT,
    barcode TEXT,
    product_name TEXT NOT NULL,
    brand TEXT,
    product_type TEXT NOT NULL DEFAULT 'food',
    image_fingerprint TEXT,
    ingredients_text TEXT NOT NULL DEFAULT '',
    ingredients_json TEXT NOT NULL DEFAULT '[]',
    formulation_fingerprint TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_market_sku_barcode ON market_sku(market_code, barcode);
CREATE INDEX IF NOT EXISTS idx_market_sku_fingerprint ON market_sku(formulation_fingerprint);
CREATE TABLE IF NOT EXISTS product_observation (
    observation_id TEXT PRIMARY KEY,
    sku_id TEXT REFERENCES market_sku(sku_id),
    source_type TEXT NOT NULL,
    market_code TEXT NOT NULL,
    language_code TEXT,
    product_name TEXT NOT NULL,
    brand TEXT,
    product_type TEXT NOT NULL DEFAULT 'food',
    image_fingerprint TEXT,
    ingredients_text TEXT NOT NULL DEFAULT '',
    ingredients_json TEXT NOT NULL DEFAULT '[]',
    formulation_fingerprint TEXT,
    consent_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    reviewed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_product_observation_status
    ON product_observation(status, created_at);
CREATE TABLE IF NOT EXISTS cross_market_link (
    link_id TEXT PRIMARY KEY,
    left_sku_id TEXT NOT NULL REFERENCES market_sku(sku_id),
    right_sku_id TEXT NOT NULL REFERENCES market_sku(sku_id),
    relation TEXT NOT NULL,
    confidence REAL NOT NULL,
    evidence_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'candidate',
    created_at TEXT NOT NULL,
    reviewed_at TEXT,
    UNIQUE(left_sku_id, right_sku_id, relation)
);
CREATE INDEX IF NOT EXISTS idx_cross_market_link_status
    ON cross_market_link(status, created_at);
"""

_MAX_TEXT = 512
_MARKET_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,15}$")
_LANGUAGE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,15}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_text(value: object, *, max_length: int = _MAX_TEXT) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = " ".join(text.split()).strip()
    return text[:max_length]


def normalize_market(value: object) -> str:
    market = normalize_text(value, max_length=16).casefold()
    if not _MARKET_RE.fullmatch(market):
        raise ValueError("market must be a lowercase market code")
    return market


def normalize_language(value: object) -> str | None:
    language = normalize_text(value, max_length=16).casefold()
    if not language:
        return None
    if not _LANGUAGE_RE.fullmatch(language):
        raise ValueError("language must be a lowercase language code")
    return language


def normalize_product_type(value: object) -> str:
    product_type = normalize_text(value, max_length=16).casefold() or "food"
    if product_type not in {"food", "supplement", "cosmetic", "drug", "other"}:
        raise ValueError("productType must be food, supplement, cosmetic, drug, or other")
    return product_type


def normalize_barcode(value: object) -> str | None:
    barcode = re.sub(r"\D", "", str(value or ""))
    if not barcode:
        return None
    if not 8 <= len(barcode) <= 14:
        raise ValueError("barcode must contain 8 to 14 digits")
    return barcode


def normalize_image_fingerprint(value: object) -> str | None:
    fingerprint = normalize_text(value, max_length=160).casefold()
    if not fingerprint:
        return None
    if not re.fullmatch(r"(?:ahash|dhash):[0-9a-f]{16,128}", fingerprint):
        raise ValueError("imageFingerprint must be an ahash or dhash hex value")
    return fingerprint


def normalize_ingredients(value: object) -> tuple[str, list[str], str | None]:
    text = normalize_text(value, max_length=4000)
    parts = []
    seen: set[str] = set()
    for item in re.split(r"[,;\n|]", text):
        item = normalize_text(item, max_length=160)
        key = item.casefold()
        if item and key not in seen:
            seen.add(key)
            parts.append(item)
    if not parts:
        return text, [], None
    fingerprint_payload = json.dumps(
        sorted(item.casefold() for item in parts), ensure_ascii=False, separators=(",", ":")
    )
    return text, parts, hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest()

def _db_path() -> Path:
    configured = os.environ.get("PRODUCT_GRAPH_DB")
    if configured:
        return Path(configured)
    base = Path(__file__).resolve().parent.parent / "data"
    return base / "product-graph.db"

def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    migrations = {
        "market_sku": {"product_type": "TEXT NOT NULL DEFAULT 'food'", "image_fingerprint": "TEXT"},
        "product_observation": {
            "barcode": "TEXT",
            "brand": "TEXT",
            "product_type": "TEXT NOT NULL DEFAULT 'food'",
            "image_fingerprint": "TEXT",
        },
    }
    for table, required in migrations.items():
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for column, definition in required.items():
            if column not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    conn.commit()
    return conn


def submit_observation(payload: dict) -> dict:
    if payload.get("shareProductFacts") is not True:
        raise ValueError("explicit product-facts consent is required")
    market = normalize_market(payload.get("market"))
    language = normalize_language(payload.get("language"))
    product_type = normalize_product_type(payload.get("productType"))
    barcode = normalize_barcode(payload.get("barcode"))
    product_name = normalize_text(payload.get("productName") or payload.get("name"))
    image_fingerprint = normalize_image_fingerprint(payload.get("imageFingerprint"))
    brand = normalize_text(payload.get("brand"))
    ingredients_text, ingredients, fingerprint = normalize_ingredients(
        payload.get("ingredientsText") or payload.get("ingredients")
    )
    if not product_name and not ingredients:
        raise ValueError("productName or ingredientsText is required")
    consent_version = normalize_text(payload.get("consentVersion") or "product-facts-v1", max_length=64)
    observation_id = f"obs_{uuid.uuid4().hex}"
    now = _now()
    with _connect() as conn:
        duplicate = None
        if barcode or image_fingerprint:
            duplicate_field = "barcode" if barcode else "image_fingerprint"
            duplicate_value = barcode or image_fingerprint
            duplicate = conn.execute(
                f"SELECT sku_id,product_name,brand,market_code,barcode,image_fingerprint FROM market_sku WHERE {duplicate_field}=? LIMIT 1",
                (duplicate_value,),
            ).fetchone()
        if duplicate:
            return {
                "observationId": None,
                "status": "duplicate_candidate",
                "duplicateCandidate": dict(duplicate),
                "reusedByOtherUsers": True,
                "rawImageStored": False,
            }
        conn.execute(
            "INSERT INTO product_observation "
            "(observation_id,source_type,market_code,language_code,barcode,product_name,brand,product_type,"
            "image_fingerprint,ingredients_text,ingredients_json,formulation_fingerprint,consent_version,status,created_at) "
            "VALUES (?, 'user_contributed', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
            (
                observation_id,
                market,
                language,
                barcode,
                product_name or "Unlabeled product",
                brand or None,
                product_type,
                image_fingerprint,
                ingredients_text,
                json.dumps(ingredients, ensure_ascii=False),
                fingerprint,
                consent_version,
                now,
            ),
        )
    return {
        "observationId": observation_id,
        "status": "pending_review",
        "reusedByOtherUsers": False,
        "storedFields": ["market", "language", "barcode", "productName", "brand", "ingredientsText"],
        "rawImageStored": False,
    }


def list_observations(status: str = "pending", limit: int = 50) -> list[dict]:
    status = normalize_text(status, max_length=24).casefold() or "pending"
    if status not in {"pending", "approved", "rejected"}:
        raise ValueError("invalid observation status")
    with _connect() as conn:
        rows = conn.execute(
            "SELECT observation_id,sku_id,source_type,market_code,language_code,barcode,"
            "product_name,brand,product_type,ingredients_text,ingredients_json,formulation_fingerprint,"
            "consent_version,status,created_at,reviewed_at FROM product_observation "
            "WHERE status=? ORDER BY created_at ASC LIMIT ?",
            (status, max(1, min(int(limit), 200))),
        ).fetchall()
    return [dict(row) for row in rows]


def _sku_identity(market: str, barcode: str | None, product_name: str, brand: str, fingerprint: str | None) -> str:
    value = barcode or "|".join((market, brand.casefold(), product_name.casefold(), fingerprint or ""))
    return f"sku-key:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def approve_observation(observation_id: str) -> dict:
    observation_id = normalize_text(observation_id, max_length=80)
    now = _now()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM product_observation WHERE observation_id=? AND status='pending'",
            (observation_id,),
        ).fetchone()
        if not row:
            raise KeyError("pending observation not found")
        identity_key = _sku_identity(
            row["market_code"], row["barcode"], row["product_name"], row["brand"] or "", row["formulation_fingerprint"]
        )
        sku = conn.execute("SELECT * FROM market_sku WHERE identity_key=?", (identity_key,)).fetchone()
        if sku:
            sku_id = sku["sku_id"]
        else:
            sku_id = f"sku_{uuid.uuid4().hex}"
            family_id = f"family_{uuid.uuid4().hex}"
            conn.execute(
                "INSERT INTO product_family(family_id,canonical_name,brand,created_at,updated_at) VALUES (?,?,?,?,?)",
                (family_id, row["product_name"], row["brand"], now, now),
            )
            conn.execute(
                "INSERT INTO market_sku "
                "(sku_id,family_id,identity_key,market_code,language_code,barcode,product_name,brand,product_type,"
                "image_fingerprint,ingredients_text,ingredients_json,formulation_fingerprint,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    sku_id,
                    family_id,
                    identity_key,
                    row["market_code"],
                    row["language_code"],
                    row["barcode"],
                    row["product_name"],
                    row["brand"],
                    row["product_type"],
                    row["image_fingerprint"],
                    row["ingredients_text"],
                    row["ingredients_json"],
                    row["formulation_fingerprint"],
                    now,
                    now,
                ),
            )
        conn.execute(
            "UPDATE product_observation SET sku_id=?,status='approved',reviewed_at=? WHERE observation_id=?",
            (sku_id, now, observation_id),
        )
    return {"observationId": observation_id, "skuId": sku_id, "status": "approved"}


def reject_observation(observation_id: str) -> dict:
    observation_id = normalize_text(observation_id, max_length=80)
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE product_observation SET status='rejected',reviewed_at=? WHERE observation_id=? AND status='pending'",
            (_now(), observation_id),
        )
def lookup_approved(*, barcode: str = "", market: str | None = None, name: str = "", image_fingerprint: str = "") -> dict | None:
    """Resolve only observations that an admin explicitly approved."""
    barcode = normalize_barcode(barcode) if barcode else None
    image_fingerprint = normalize_image_fingerprint(image_fingerprint) if image_fingerprint else None
    market_code = None
    if market:
        try:
            market_code = normalize_market(market)
        except ValueError:
            market_code = None
    with _connect() as conn:
        select = "SELECT market_code,language_code,barcode,product_name,brand,product_type,image_fingerprint,ingredients_text,ingredients_json FROM market_sku "
        if barcode or image_fingerprint:
            field = "barcode" if barcode else "image_fingerprint"
            value = barcode or image_fingerprint
            row = conn.execute(
                select + f"WHERE {field}=? AND (? IS NULL OR market_code=?) ORDER BY market_code LIMIT 1",
                (value, market_code, market_code),
            ).fetchone()
        else:
            words = [word for word in normalize_text(name).casefold().split() if len(word) >= 2][:5]
            if not words:
                return None
            clauses = " AND ".join("LOWER(product_name || ' ' || COALESCE(brand, '')) LIKE ?" for _ in words)
            params: list[str] = [f"%{word}%" for word in words]
            if market_code:
                clauses += " AND market_code=?"
                params.append(market_code)
            row = conn.execute(select + "WHERE " + clauses + " LIMIT 1", params).fetchone()
    if not row:
        return None
    try:
        ingredients = json.loads(row["ingredients_json"] or "[]")
    except json.JSONDecodeError:
        ingredients = []
    match_confidence = 1.0 if barcode else 0.98 if image_fingerprint else 0.9
    match_reasons = ["exact_barcode"] if barcode else ["perceptual_image_fingerprint"] if image_fingerprint else ["name_brand_match"]
    return {
        "barcode": row["barcode"],
        "productName": row["product_name"],
        "brand": row["brand"],
        "productType": row["product_type"],
        "ingredientsText": row["ingredients_text"],
        "ingredientsList": ingredients if isinstance(ingredients, list) else [],
        "market": row["market_code"],
        "language": row["language_code"],
        "source": "community_verified",
        "identityCode": f"mm_img_{row['image_fingerprint'][6:18]}" if row["image_fingerprint"] else None,
        "matchConfidence": match_confidence,
        "matchReasons": match_reasons,
    }


def suggest_cross_market_links(limit: int = 50) -> list[dict]:
    with _connect() as conn:
        rows = [dict(row) for row in conn.execute(
            "SELECT sku_id,market_code,language_code,product_name,brand,formulation_fingerprint "
            "FROM market_sku WHERE formulation_fingerprint IS NOT NULL ORDER BY sku_id"
        )]
        existing = {
            (row[0], row[1], row[2])
            for row in conn.execute("SELECT left_sku_id,right_sku_id,relation FROM cross_market_link")
        }
        output = []
        for index, left in enumerate(rows):
            for right in rows[index + 1:]:
                if left["market_code"] == right["market_code"]:
                    continue
                if left["formulation_fingerprint"] != right["formulation_fingerprint"]:
                    continue
                if not left["brand"] or not right["brand"]:
                    continue
                if normalize_text(left["brand"]).casefold() != normalize_text(right["brand"]).casefold():
                    continue
                pair = (left["sku_id"], right["sku_id"], "same_formula_candidate")
                if pair in existing:
                    continue
                link_id = "link_" + hashlib.sha256("|".join(pair).encode("utf-8")).hexdigest()[:32]
                conn.execute(
                    "INSERT OR IGNORE INTO cross_market_link "
                    "(link_id,left_sku_id,right_sku_id,relation,confidence,evidence_json,status,created_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        link_id,
                        left["sku_id"],
                        right["sku_id"],
                        "same_formula_candidate",
                        0.92,
                        json.dumps({"evidence": ["exact_ingredient_fingerprint", "exact_brand"]}),
                        "candidate",
                        _now(),
                    ),
                )
                output.append({"linkId": link_id, "left": left, "right": right, "status": "candidate"})
                if len(output) >= max(1, min(int(limit), 200)):
                    break
            if len(output) >= max(1, min(int(limit), 200)):
                break
        conn.commit()
    return output


def list_cross_market_links(status: str = "candidate", limit: int = 50) -> list[dict]:
    status = normalize_text(status, max_length=24).casefold() or "candidate"
    if status not in {"candidate", "confirmed", "rejected"}:
        raise ValueError("invalid link status")
    with _connect() as conn:
        rows = conn.execute(
            "SELECT link_id,left_sku_id,right_sku_id,relation,confidence,evidence_json,status,created_at,reviewed_at "
            "FROM cross_market_link WHERE status=? ORDER BY created_at ASC LIMIT ?",
            (status, max(1, min(int(limit), 200))),
        ).fetchall()
    return [dict(row) for row in rows]


def review_cross_market_link(link_id: str, decision: str) -> dict:
    link_id = normalize_text(link_id, max_length=80)
    decision = normalize_text(decision, max_length=16).casefold()
    if decision not in {"confirmed", "rejected"}:
        raise ValueError("decision must be confirmed or rejected")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE cross_market_link SET status=?,reviewed_at=? WHERE link_id=? AND status='candidate'",
            (decision, _now(), link_id),
        )
        if not cur.rowcount:
            raise KeyError("candidate link not found")
    return {"linkId": link_id, "status": decision}

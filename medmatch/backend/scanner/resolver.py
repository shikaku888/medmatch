"""Deterministic product resolution across local data and open providers.

The resolver returns one contract for barcode, name, and ingredient input. Provider
responses are normalized before caching; raw provider payloads never enter the
clinical database or the client response.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from backend.db import DB_PATH, get_conn
from backend.scanner.ext_clients import (
    get_product_from_off,
    search_openfda_ndc,
    search_openfoodfacts_name,
    search_usda_food,
)
from backend.scanner.product_graph import lookup_approved

_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
_PRODUCT_CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS product_cache (
    cache_key TEXT PRIMARY KEY,
    product_json TEXT NOT NULL,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    ttl_seconds INTEGER NOT NULL,
    sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_product_cache_fetched ON product_cache(fetched_at);
CREATE TABLE IF NOT EXISTS unresolved_products (
    lookup_key TEXT PRIMARY KEY,
    input_type TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 1,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
);
CREATE INDEX IF NOT EXISTS idx_unresolved_products_status ON unresolved_products(status, last_seen);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_lookup(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = "".join(ch if ch.isalnum() or ch in " -" else " " for ch in text)
    return re.sub(r"\s+", " ", text).strip()


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", str(value or ""))
def _cache_key(*, barcode: str = "", name: str = "", ingredients: list[str] | None = None, country: str = "") -> str:
    if barcode:
        return f"barcode:{_digits(barcode) or normalize_lookup(barcode)}:{normalize_lookup(country) or 'us'}"
    if name:
        return f"name:{normalize_lookup(name)}:{normalize_lookup(country) or 'us'}"
    normalized = ";".join(normalize_lookup(item) for item in (ingredients or []) if normalize_lookup(item))
    return f"ingredients:{normalized}"


def _cache_db():
    """Return the separate writable normalized-provider cache database."""
    try:
        configured = os.environ.get("PRODUCT_CACHE_DB")
        if configured:
            cache_path = Path(configured)
        else:
            base = Path(os.environ.get("SCANNER_DATA_DIR") or Path(__file__).resolve().parent.parent / "data")
            cache_path = base / "product-cache.db"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(cache_path, timeout=5)
        conn.executescript(_PRODUCT_CACHE_SCHEMA)
        return conn
    except (OSError, sqlite3.Error):
        return None


def _read_cache(key: str) -> dict | None:
    conn = _cache_db()
    if conn is None:
        return None
    try:
        row = conn.execute(
            "SELECT product_json, source, fetched_at, ttl_seconds, sha256 "
            "FROM product_cache WHERE cache_key = ?", (key,)
        ).fetchone()
        if not row:
            return None
        fetched = datetime.fromisoformat(str(row[2]).replace("Z", "+00:00"))
        if (datetime.now(timezone.utc) - fetched).total_seconds() > int(row[3]):
            return None
        payload = json.loads(row[0])
        if hashlib.sha256(row[0].encode("utf-8")).hexdigest() != row[4]:
            return None
        if not isinstance(payload, dict):
            return None
        return {"product": payload, "source": row[1], "cached": True}
    except (ValueError, TypeError, json.JSONDecodeError, sqlite3.Error):
        return None
    finally:
        conn.close()


def _write_cache(key: str, product: dict, source: str) -> None:
    if os.environ.get("MEDMATCH_DB_READ_ONLY") == "1":
        return
    conn = _cache_db()
    if conn is None:
        return
    try:
        product_json = json.dumps(product, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(product_json.encode("utf-8")).hexdigest()
        conn.execute(
            "INSERT OR REPLACE INTO product_cache "
            "(cache_key, product_json, source, fetched_at, ttl_seconds, sha256) VALUES (?,?,?,?,?,?)",
            (key, product_json, source, _now_iso(), _CACHE_TTL_SECONDS, digest),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
    finally:
        conn.close()


def _record_unresolved(key: str, input_type: str) -> None:
    key = hashlib.sha256(key.encode("utf-8")).hexdigest()
    conn = _cache_db()
    if conn is None:
        return
    now = _now_iso()
    try:
        conn.execute(
            "INSERT INTO unresolved_products (lookup_key,input_type,attempts,first_seen,last_seen,status) "
            "VALUES (?,?,?,?,?,'pending') "
            "ON CONFLICT(lookup_key) DO UPDATE SET attempts=attempts+1,last_seen=excluded.last_seen,status='pending'",
            (key, input_type, 1, now, now),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
    finally:
        conn.close()


def list_unresolved(limit: int = 50) -> list[dict]:
    conn = _cache_db()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            "SELECT lookup_key,input_type,attempts,first_seen,last_seen,status "
            "FROM unresolved_products WHERE status='pending' ORDER BY attempts DESC,last_seen DESC LIMIT ?",
            (max(1, min(int(limit), 200)),),
        ).fetchall()
        return [
            {
                "lookupKey": row[0], "inputType": row[1], "attempts": row[2],
                "firstSeen": row[3], "lastSeen": row[4], "status": row[5],
            }
            for row in rows
        ]
    finally:
        conn.close()


def _normalize_product(product: dict | None, source: str, barcode: str = "") -> dict | None:
    if not isinstance(product, dict):
        return None
    ingredients = product.get("ingredientsList") or product.get("ingredients") or []
    if isinstance(ingredients, str):
        ingredients = re.split(r"[,;\n]", ingredients)
    ingredients = [str(item).strip() for item in ingredients if str(item).strip()][:60]
    product_type = str(product.get("productType") or product.get("type") or "supplement").strip()
    if source == "openfda":
        product_type = "drug"
    normalized = {
        "barcode": str(product.get("barcode") or barcode or "").strip() or None,
        "productName": str(product.get("productName") or product.get("name") or "").strip() or None,
        "brand": str(product.get("brand") or product.get("brands") or "").strip() or None,
        "productType": product_type,
        "imageUrl": product.get("imageUrl") or product.get("image_url"),
        "ingredientsText": str(product.get("ingredientsText") or "").strip(),
        "ingredientsList": ingredients,
        "excipients": [str(item).strip() for item in (product.get("excipients") or []) if str(item).strip()][:60],
        "allergens": [str(item).strip() for item in (product.get("allergens") or []) if str(item).strip()][:40],
        "labels": [str(item).strip() for item in (product.get("labels") or []) if str(item).strip()][:40],
        "nutrition": product.get("nutrition"),
        "cosmetic": product.get("cosmetic"),
        "countryOfOrigin": product.get("countryOfOrigin"),
    }
    if not normalized["ingredientsText"]:
        normalized["ingredientsText"] = "; ".join(ingredients)
    normalized["source"] = source
    return normalized


def _local_barcode(barcode: str) -> dict | None:
    try:
        from backend import product_index
        conn = get_conn()
        hit = product_index.lookup(conn, barcode)
        conn.close()
        if not hit:
            return None
        return _normalize_product({
            "barcode": barcode,
            "productName": hit.get("name"),
            "brand": hit.get("brand"),
            "productType": hit.get("product_type"),
            "ingredientsText": hit.get("ingredients"),
            "ingredientsList": (hit.get("ingredients") or "").split(";"),
            "excipients": (hit.get("excipients") or "").split(";"),
        }, f"product-index:{hit.get('code_type') or 'barcode'}", barcode)
    except (OSError, sqlite3.Error):
        return None


def _local_name(name: str) -> dict | None:
    normalized = normalize_lookup(name)
    if len(normalized) < 3:
        return None
    try:
        conn = get_conn()
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='product_index'").fetchone():
            conn.close()
            return None
        words = [word for word in normalized.split() if len(word) >= 2][:5]
        clauses = " AND ".join("LOWER(name) LIKE ?" for _ in words)
        rows = conn.execute(
            "SELECT code, code_type, name, brand, product_type, ingredients, excipients "
            f"FROM product_index WHERE {clauses} LIMIT 12", tuple(f"%{word}%" for word in words),
        ).fetchall()
        conn.close()
        if not rows:
            return None
        row = rows[0]
        return _normalize_product({
            "barcode": row[0], "productName": row[2], "brand": row[3],
            "productType": row[4], "ingredientsText": row[5],
            "ingredientsList": (row[5] or "").split(";"),
            "excipients": (row[6] or "").split(";"),
        }, f"product-index:{row[1]}", str(row[0]))
    except (OSError, sqlite3.Error):
        return None


def _community_product(
    barcode: str,
    country: str | None = None,
    name: str = "",
    image_fingerprint: str = "",
) -> dict | None:
    try:
        product = lookup_approved(
            barcode=barcode,
            market=country,
            name=name,
            image_fingerprint=image_fingerprint,
        )
        if not product:
            return None
        return product
    except (ValueError, sqlite3.Error):
        return None


def _dsld_barcode(barcode: str) -> dict | None:
    try:
        conn = get_conn()
        row = conn.execute(
            "SELECT barcode, dsld_id, name, brand, ingredients FROM dsld_products WHERE barcode = ? LIMIT 1",
            (barcode,),
        ).fetchone()
        conn.close()
        if not row:
            return None
        return _normalize_product({
            "barcode": row[0], "productName": row[2], "brand": row[3],
            "productType": "supplement", "ingredientsText": row[4],
            "ingredientsList": (row[4] or "").split(";"),
        }, "dsld", barcode)
    except (OSError, sqlite3.Error):
        return None


def _dsld_name(name: str) -> dict | None:
    normalized = normalize_lookup(name)
    words = [word for word in normalized.split() if len(word) >= 2][:5]
    if not words:
        return None
    try:
        conn = get_conn()
        clauses = " AND ".join("LOWER(name || ' ' || COALESCE(brand, '')) LIKE ?" for _ in words)
        row = conn.execute(
            "SELECT barcode, name, brand, ingredients FROM dsld_products "
            f"WHERE {clauses} LIMIT 1", tuple(f"%{word}%" for word in words),
        ).fetchone()
        conn.close()
        if not row:
            return None
        return _normalize_product({
            "barcode": row[0], "productName": row[1], "brand": row[2],
            "productType": "supplement", "ingredientsText": row[3],
            "ingredientsList": (row[3] or "").split(";"),
        }, "dsld", str(row[0] or ""))
    except (OSError, sqlite3.Error):
        return None


def _parse_lnhpd(payload: Any, npn: str) -> dict | None:
    row = payload
    if isinstance(payload, list):
        row = payload[0] if payload else None
    if isinstance(payload, dict):
        row = payload.get("ProductLicence") or payload.get("productLicence") or payload.get("data") or payload
    if not isinstance(row, dict):
        return None
    ingredients = row.get("ingredients") or row.get("medicinalIngredients") or row.get("nonMedicinalIngredients") or []
    if isinstance(ingredients, list):
        ingredients = "; ".join(
            str(item.get("ingredientName") or item.get("name") or item.get("properName") or item)
            for item in ingredients
        )
    return _normalize_product({
        "barcode": npn,
        "productName": row.get("productName") or row.get("brandName") or row.get("product_name"),
        "brand": row.get("companyName") or row.get("brandName"),
        "productType": "supplement",
        "ingredientsText": ingredients,
        "ingredientsList": re.split(r"[,;\n]", str(ingredients or "")),
        "labels": ["Health Canada LNHPD"],
    }, "canada_open", npn)


async def _lnhpd(npn: str) -> dict | None:
    if not npn:
        return None
    url = "https://health-products.canada.ca/api/natural-licences/ProductLicence/?id=" + quote(npn)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, headers={"User-Agent": "MedMatch-SafeScanner/2.0"})
        if response.status_code != 200:
            return None
        return _parse_lnhpd(response.json(), npn)
    except (httpx.HTTPError, ValueError):
        return None


def _unmatched(ingredients: list[str]) -> list[str]:
    # Resolver does not claim clinical identity; this list only reports empty/invalid fields.
    return [item for item in ingredients if not normalize_lookup(item)]


def _result(status: str, product: dict | None, ingredients: list[str], unmatched: list[str], sources: list[str], limitations: list[str]) -> dict:
    return {
        "status": status,
        "product": product,
        "ingredients": ingredients[:60],
        "unmatched": unmatched[:40],
        "sources": sources,
        "limitations": limitations,
    }


async def resolve_product(*, barcode: str | None = None, name: str | None = None,
                          ingredients: list[str] | None = None, country: str | None = None,
                          image_fingerprint: str | None = None) -> dict:
    """Resolve a product using local index, cache, and open providers in order."""
    barcode = str(barcode or "").strip()
    name = str(name or "").strip()
    input_ingredients = [str(item).strip() for item in (ingredients or []) if str(item).strip()]
    key = _cache_key(barcode=barcode, name=name, ingredients=input_ingredients, country=country or "")

    # Local product index is authoritative for records already shipped in the
    # runtime snapshot; only then consult the normalized provider cache.
    local = _local_barcode(barcode) if barcode else _local_name(name) if name else None
    if local:
        return _result("found" if local["ingredientsList"] else "partial", local,
                       local["ingredientsList"], [], [str(local.get("source") or "local-index")],
                       ["Local index record; verify the physical label and lot details."])
    community = _community_product(barcode, country, name, image_fingerprint or "")
    if community:
        return _result(
            "found" if community["ingredientsList"] else "partial",
            community,
            community["ingredientsList"],
            [],
            ["community_verified"],
            ["Admin-approved community facts; verify the physical label and lot details."],
        )

    cached = _read_cache(key)
    if cached:
        product = _normalize_product(cached["product"], cached["source"], barcode)
        if product:
            return _result("found" if product["ingredientsList"] else "partial", product,
                           product["ingredientsList"], [], [cached["source"]],
                           ["Cached normalized provider result; verify label and lot details."])

    candidates: list[tuple[dict | None, str]] = []
    if barcode:
        candidates.extend([
            (await get_product_from_off(barcode, country), "openfoodfacts"),
            (await search_usda_food(barcode), "usda"),
            (await search_openfda_ndc(barcode), "openfda"),
            (_dsld_barcode(barcode), "dsld"),
            (await _lnhpd(barcode), "lnhpd"),
        ])
    elif name:
        candidates.extend([
            (await search_openfoodfacts_name(name), "openfoodfacts"),
            (await search_usda_food(name), "usda"),
            (await search_openfda_ndc(name), "openfda"),
            (_dsld_name(name), "dsld"),
            (await _lnhpd(name), "lnhpd"),
        ])
    else:
        product = _normalize_product(
            {"productName": "Unidentified product", "productType": "supplement", "ingredientsList": input_ingredients},
            "user-input",
        )
        if product and input_ingredients:
            return _result(
                "partial", product, input_ingredients, _unmatched(input_ingredients),
                ["user-input"], ["Product identity is unknown; ingredient-only screening is not a safety clearance."],
            )
        return _result(
            "unknown", None, [], [], [],
            ["No barcode, product name, or ingredients were provided; this is not a safety clearance."],
        )

    for candidate, source_hint in candidates:
        if not candidate:
            continue
        source = str(candidate.get("source") or source_hint)
        product = _normalize_product(candidate, source, barcode)
        if not product:
            continue
        _write_cache(key, product, source)
        found_ingredients = product["ingredientsList"]
        status = "found" if product.get("productName") and found_ingredients else "partial"
        limitations = [
            "Provider data is not a label or lot verification.",
            "No provider match is not a safety clearance.",
        ]
        return _result(status, product, found_ingredients, [], [source], limitations)

    if input_ingredients:
        product = _normalize_product({"productName": name or "Unidentified product", "productType": "supplement", "ingredientsList": input_ingredients}, "user-input", barcode)
        return _result("partial", product, input_ingredients, _unmatched(input_ingredients), ["user-input"], ["Product identity is unresolved; screening is incomplete and not a safety clearance."])
    if barcode or name:
        _record_unresolved(key, "barcode" if barcode else "name")
    return _result("unknown", None, [], [], [], ["No matching product was found in local data or open providers; this is not a safety clearance."])

def get_offline_product_pack(limit: int = 50000) -> list[dict]:
    """Return a bounded barcode pack for device-side offline lookup."""
    limit = max(1, min(int(limit), 50000))
    conn = get_conn()
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='product_index'").fetchone():
            return []
        rows = conn.execute(
            "SELECT code,name,brand,product_type,ingredients FROM product_index "
            "WHERE code IS NOT NULL AND name IS NOT NULL ORDER BY matched DESC, code LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "barcode": row["code"],
                "productName": row["name"],
                "brand": row["brand"],
                "productType": row["product_type"],
                "ingredientsText": row["ingredients"] or "",
            }
            for row in rows
        ]
    finally:
        conn.close()

"""Product code index (GTIN / NDC / UPC / DSLD-id) → product + matched entities.

Online lookup (Open Food Facts/UPCitemdb) chậm và không phủ drug/supplement.
Index này (builder chạy 1 lần trên mỗi nguồn bulk local) cho phép cache-hit
ngay khi quét QR/barcode, không cần gọi mạng.

Table:
    product_index (
        code      TEXT PRIMARY KEY,   -- digits-only variant (NDC/GTIN/UPC/EAN)
        code_type TEXT,               -- 'ndc' | 'upc' | 'ean' | 'gtin' | 'dsld'
        name      TEXT, brand TEXT,
        product_type TEXT,            -- 'drug' | 'supplement' | 'food'
        ingredients TEXT,             -- raw ingredient text (join '; ')
        matched    TEXT               -- JSON list of {kind, id, label, ingredient}
    )

Builder:
    python -m backend.product_index
"""
import json
import re
import unicodedata
import sqlite3
import sys
from pathlib import Path

from .db import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS product_index (
    code TEXT PRIMARY KEY,
    code_type TEXT,
    name TEXT, brand TEXT,
    product_type TEXT,
    ingredients TEXT,
    excipients TEXT,
    matched TEXT
);
CREATE INDEX IF NOT EXISTS idx_pi_type ON product_index(code_type);
"""

# NDC ingredient names thường kèm muối/acid ("hydrocodone bitartrate",
# "phenylephrine hydrochloride") trong khi synonyms của ta là base name.
_SALT_SUFFIXES = (
    " hydrochloride", " hydrobromide", " bitartrate", " tartrate", " sulfate",
    " sodium", " potassium", " phosphate", " maleate", " citrate", " acetate",
    " oxide", " besylate", " mesylate", " fumarate", " succinate", " lactate",
    " calcium", " magnesium", " orotate", " chloride", " benzoate", " salicylate",
)


def _digits(code: str) -> str:
    return re.sub(r"\D", "", code or "")


def _norm_ing(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name or "")
    preserved: list[str] = []
    for ch in decomposed:
        if unicodedata.combining(ch) and not (
            preserved and "\u3040" <= preserved[-1] <= "\u30ff"
        ):
            continue
        preserved.append(ch)
    text = unicodedata.normalize("NFKC", "".join(preserved))
    text = "".join(ch if ch.isalnum() or ch in " -" else " " for ch in text.casefold())
    return re.sub(r"\s+", " ", text).strip()


def _build_syn_map(conn: sqlite3.Connection) -> tuple[dict, dict]:
    """synonym→[(kind, id)] + label lookups (in-memory, 1 lần)."""
    syn: dict[str, list[tuple[str, str]]] = {}
    for kind, eid, s in conn.execute(
        "SELECT kind, entity_id, synonym FROM ingredient_synonyms WHERE synonym != ''"):
        syn.setdefault(_norm_ing(s), []).append((kind, eid))
    label: dict[tuple[str, str], str] = {}
    for kind, table in (("herb", "herbs"), ("drug_class", "drug_classes"), ("food", "foods")):
        for eid, name in conn.execute(f"SELECT id, name_en FROM {table}"):
            label[(kind, eid)] = name
    return syn, label


def _resolve_ingredient(raw: str, syn: dict, label: dict) -> list[dict]:
    """Tìm entity cho 1 ingredient; trả matches {kind, id, label, ingredient}."""
    norm = _norm_ing(raw)
    if not norm:
        return []
    hits: list[tuple[str, str]] = []
    if norm in syn:
        hits = syn[norm]
    else:
        # 1) strip muối/acid phổ biến: "hydrocodone bitartrate" → "hydrocodone"
        for sfx in _SALT_SUFFIXES:
            if norm.endswith(sfx):
                base = _norm_ing(norm[: -len(sfx)])
                if base in syn:
                    hits = syn[base]
                    break
    if not hits:
        # 2) drop từng từ cuối: "phenylephrine hydrochloride extra" → "phenylephrine"
        cand = norm
        while not hits and cand:
            pos = max(cand.rfind(" "), cand.rfind("-"))
            cand = cand[:pos] if pos > 0 else ""
            if cand and cand in syn:
                hits = syn[cand]
    if not hits:
        # 3) token fallback: token dài nhất ≥4cc khớp synonym chính xác
        for w in sorted((w for w in norm.split() if len(w) >= 4), key=len, reverse=True):
            if w in syn:
                hits = syn[w]
                break
    out = []
    seen = set()
    for kind, eid in hits[:6]:
        key = f"{kind}:{eid}"
        if key in seen:
            continue
        seen.add(key)
        out.append({"kind": kind, "id": eid,
                    "label": label.get((kind, eid), eid),
                    "ingredient": raw.strip()})
    return out


def build(conn: sqlite3.Connection, max_ndc: int = 0, max_dsld: int = 0) -> dict:
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(product_index)")}
    if "excipients" not in columns:
        conn.execute("ALTER TABLE product_index ADD COLUMN excipients TEXT NOT NULL DEFAULT ''")
    conn.execute("DELETE FROM product_index")
    syn, label = _build_syn_map(conn)
    cur = conn.cursor()
    stats = {"ndc": 0, "dsld": 0, "matched": 0}

    # --- 1. openFDA NDC: drug products by NDC / GTIN digits ---
    ndc_columns = {row[1] for row in conn.execute("PRAGMA table_info(ndc_products)")}
    inactive = "inactive_ingredients" if "inactive_ingredients" in ndc_columns else "'' AS inactive_ingredients"
    q = ("SELECT product_ndc, brand_name, generic_name, labeler, ingredients, " + inactive + " FROM ndc_products")
    if max_ndc:
        q += f" LIMIT {int(max_ndc)}"
    rows = conn.execute(q).fetchall()
    buf = []
    for r in rows:
        code = _digits(r["product_ndc"])
        if not code:
            continue
        ing_list = [s for s in (r["ingredients"] or "").split(";") if s.strip()]
        matched = []
        for ing in ing_list:
            matched.extend(_resolve_ingredient(ing, syn, label))
        if matched:
            stats["matched"] += 1
        name = (r["generic_name"] or r["brand_name"] or "").strip()
        excipients = (r["inactive_ingredients"] or "").strip()
        buf.append((code, "ndc", name or (r["brand_name"] or "Unknown"),
                    (r["brand_name"] or "").strip(), "drug",
                    (r["ingredients"] or "").strip(), excipients, json.dumps(matched)))
        # GTIN-13/EAN (UPC-A = 0 + NDC-10 chuẩn)and GTIN-14 dạng phổ biến
        # không ép đoán đúng chuẩn; chỉ thêm prefix-0 variant phổ biến cho NDC
        if len(code) <= 10:
            g = "0" * (11 - len(code)) + code
            if len(g) == 11 and g != code:
                buf.append((g, "ndc", name, (r["brand_name"] or "").strip(),
                            "drug", (r["ingredients"] or "").strip(), excipients,
                            json.dumps(matched)))
        if len(buf) >= 5000:
            cur.executemany(
                "INSERT OR REPLACE INTO product_index (code,code_type,name,brand,product_type,ingredients,excipients,matched) VALUES (?,?,?,?,?,?,?,?)", buf)
            buf = []
    if buf:
        cur.executemany(
            "INSERT OR REPLACE INTO product_index (code,code_type,name,brand,product_type,ingredients,excipients,matched) VALUES (?,?,?,?,?,?,?,?)", buf)
        buf = []
    conn.commit()
    stats["ndc"] = len(rows)
    # --- 2. NIH DSLD: supplement/food products by barcode digits ---
    has_dsld = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='dsld_products'"
    ).fetchone()
    rows2 = []
    if has_dsld:
        q2 = "SELECT barcode, dsld_id, name, brand, ingredients FROM dsld_products"
        if max_dsld:
            q2 += f" LIMIT {int(max_dsld)}"
        rows2 = conn.execute(q2).fetchall()
    buf = []
    skipped = 0
    for r in rows2:
        code = _digits(r["barcode"])
        if code:
            if len(code) < 8 or len(code) > 14 or code.startswith("00000"):
                skipped += 1
                code = ""
        if not code:
            code = "DSLD-" + str(r["dsld_id"])
            ctype = "dsld"
        else:
            ctype = "upc"
        name = (r["name"] or "").strip()
        brand = (r["brand"] or "").strip()
        matched = []
        for ingredient in re.split(r"\s*;\s*", r["ingredients"] or ""):
            if ingredient.strip():
                matched.extend(_resolve_ingredient(ingredient, syn, label))
        matched_json = json.dumps(matched, ensure_ascii=False)
        buf.append((code, ctype, name, brand, "supplement", (r["ingredients"] or "").strip(), "", matched_json))
        if ctype == "upc" and len(code) == 12:
            buf.append(("0" + code, "ean", name, brand, "supplement", (r["ingredients"] or "").strip(), "", matched_json))
        if len(buf) >= 5000:
            cur.executemany("INSERT OR REPLACE INTO product_index (code,code_type,name,brand,product_type,ingredients,excipients,matched) VALUES (?,?,?,?,?,?,?,?)", buf)
            buf = []
    if buf:
        cur.executemany("INSERT OR REPLACE INTO product_index (code,code_type,name,brand,product_type,ingredients,excipients,matched) VALUES (?,?,?,?,?,?,?,?)", buf)
    conn.commit()
    stats["dsld"] = len(rows2)
    stats["skipped_placeholder_barcodes"] = skipped
    stats["total"] = conn.execute("SELECT COUNT(*) FROM product_index").fetchone()[0]
    return stats



def lookup(conn: sqlite3.Connection, code: str) -> dict | None:
    """Tra nhanh theo bất kỳ dạng mã nào (digits-only chuẩn hoá)."""
    conn.row_factory = sqlite3.Row
    digits = _digits(code)
    for candidate in (code, digits):
        if not candidate:
            continue
        row = conn.execute(
            "SELECT code_type, name, brand, product_type, ingredients, excipients, matched "
            "FROM product_index WHERE code = ? LIMIT 1", (candidate,)
        ).fetchone()
        if row:
            return {key: row[key] for key in row.keys()}
    return None


def run() -> dict:
    conn = sqlite3.connect(DB_PATH, timeout=90)
    try:
        return build(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    max_ndc = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    max_dsld = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    print(run() if not (max_ndc or max_dsld) else "building partial...")
    sys.exit(0)
"""NIH DSLD (Dietary Supplement Label Database) importer — public domain (US gov).

dsld.od.nih.gov sits behind Cloudflare for programmatic clients, so the bulk
CSV is downloaded MANUALLY once (Download section → zip) and extracted to:
    backend/data/dsld/          (any *.csv inside is picked up)

The importer auto-detects column names (API-style camelCase or snake_case),
matches every UPC in `upc_s` / `upcs` / `upc` columns, and fills:
    dsld_products(barcode TEXT PRIMARY KEY, dsld_id TEXT, name TEXT, brand TEXT, ingredients TEXT)

/api/lookup/{barcode} then resolves supplement barcodes OFF misses.

Usage:
    python -m backend.dsld            # import from data/dsld/*.csv
"""
import csv
import sqlite3
import sys
from pathlib import Path

from .db import DB_PATH

DATA_DIR = Path(__file__).parent / "data" / "dsld"

SCHEMA = """
CREATE TABLE IF NOT EXISTS dsld_products (
    barcode TEXT PRIMARY KEY,
    dsld_id TEXT,
    name TEXT,
    brand TEXT,
    ingredients TEXT
);
"""

# spaces/underscores stripped ("Bar Code" -> "barcode", "Product Name" -> "productname")
COLUMN_ALIASES = {
    "dsld_id": ("id", "dsldid", "productid", "productid"),
    "name": ("productname", "name", "labeldescription"),
    "brand": ("brandname", "brand", "distributorname", "companyname"),
    "ingredients": ("ingredients", "ingredientstatement", "ingredientlist"),
}
UPC_ALIASES = ("upcs", "upc", "upccode", "barcode", "barcodes")


def _canon(header: list[str]) -> dict[str, str | None]:
    """Map canonical field -> actual CSV column name (or None)."""
    stripped = {h.strip().lower().replace(" ", "").replace("_", ""): h for h in header}
    out: dict[str, str | None] = {}
    for canon, aliases in COLUMN_ALIASES.items():
        out[canon] = next((stripped[a] for a in aliases if a in stripped), None)
    out["_upc"] = next((stripped[a] for a in UPC_ALIASES if a in stripped), None)
    return out


def import_csv(path: Path, conn: sqlite3.Connection) -> dict:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            return {"file": path.name, "rows": 0, "barcodes": 0, "skipped": "empty"}
        col = _canon(reader.fieldnames)
        if not col["_upc"] or not col["name"]:
            return {"file": path.name, "rows": 0, "barcodes": 0,
                    "skipped": f"no UPC/name column found in {reader.fieldnames}"}
        rows = barcodes = 0
        for r in reader:
            raw_upcs = (r.get(col["_upc"]) or "").strip()
            if not raw_upcs:
                continue
            name = (r.get(col["name"]) or "").strip() or None
            brand = (r.get(col["brand"]) or "").strip() if col["brand"] else None
            ingredients = (r.get(col["ingredients"]) or "").strip() if col["ingredients"] else None
            dsld_id = (r.get(col["dsld_id"]) or "").strip() if col["dsld_id"] else None
            # upc_s is space-separated; tolerate , ; | separators too
            for code in raw_upcs.replace(",", " ").replace(";", " ").replace("|", " ").split():
                code = code.strip()
                if len(code) >= 6 and code.isdigit():
                    conn.execute(
                        "INSERT OR REPLACE INTO dsld_products (barcode, dsld_id, name, brand, ingredients)"
                        " VALUES (?,?,?,?,?)", (code, dsld_id, name, brand, ingredients))
                    barcodes += 1
            rows += 1
        return {"file": path.name, "rows": rows, "barcodes": barcodes}

def import_ingredients(path: Path, conn: sqlite3.Connection, kind: str) -> int:
    """Second pass: attach ingredient statements by DSLD ID.
    kind='other'  → OtherIngredients_*.csv (inactive, semicolon-separated)
    kind='facts'  → DietarySupplementFacts_*.csv (one row per nutrient)"""
    stripped = None
    updated = 0
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fields = {f.strip().lower().replace(" ", "").replace("_", ""): f for f in (reader.fieldnames or [])}
        dsld_col = fields.get("dsldid")
        if not dsld_col:
            return 0
        per_product: dict[str, list[str]] = {}
        if kind == "other":
            other_col = fields.get("otheringredients")
            for r in reader:
                did = (r.get(dsld_col) or "").strip()
                text = (r.get(other_col) or "").strip() if other_col else ""
                if did and text:
                    per_product[did] = [s.strip() for s in text.split(";") if s.strip()]
        else:
            name_col = fields.get("ingredient")
            amount_col = fields.get("amountperserving")
            unit_col = fields.get("amountperservingunit")
            for r in reader:
                did = (r.get(dsld_col) or "").strip()
                ing = (r.get(name_col) or "").strip() if name_col else ""
                if not did or not ing:
                    continue
                amount = (r.get(amount_col) or "").strip() if amount_col else ""
                unit = (r.get(unit_col) or "").strip() if unit_col else ""
                per_product.setdefault(did, []).append(f"{ing} {amount} {unit}".strip())
        for did, parts in per_product.items():
            cur = conn.execute(
                "UPDATE dsld_products SET ingredients = COALESCE(NULLIF(ingredients, '') || ' | ', '') || ?"
                " WHERE dsld_id = ?", ("; ".join(parts), did))
            updated += cur.rowcount
    return updated


def run() -> dict:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        conn.executescript(SCHEMA)
        files = sorted(DATA_DIR.glob("*.csv")) if DATA_DIR.exists() else []
        if not files:
            print(f"NO FILES: put DSLD bulk CSV(s) into {DATA_DIR}")
            print("Download: https://dsld.od.nih.gov → Download (public domain, free)")
            return {"files": 0}
        total_bc = 0
        for f in files:
            stats = import_csv(f, conn)
            print(stats)
            total_bc += stats.get("barcodes", 0)
        for f in sorted(DATA_DIR.glob("OtherIngredients_*.csv")):
            n = import_ingredients(f, conn, "other")
            print(f"other ingredients: {f.name} → {n} products updated")
        for f in sorted(DATA_DIR.glob("DietarySupplementFacts_*.csv")):
            n = import_ingredients(f, conn, "facts")
            print(f"active ingredients: {f.name} → {n} products updated")
        conn.commit()
        print(f"total dsld_products barcodes: {n}")
        return {"files": len(files), "barcodes": total_bc}
    finally:
        conn.close()


def lookup(barcode: str) -> dict | None:
    """Live lookup used by app.py /api/lookup cascade."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM dsld_products WHERE barcode = ?", (barcode,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


if __name__ == "__main__":
    run()
    sys.exit(0)

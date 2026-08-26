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
CREATE INDEX IF NOT EXISTS idx_dsld_name ON dsld_products(name);
"""

# header candidate -> canonical field (checked case-insensitively, first hit wins)
COLUMN_ALIASES = {
    "dsld_id": ("id", "dsld_id", "productid", "product_id"),
    "name": ("productname", "product_name", "name", "labeldescription"),
    "brand": ("brandname", "brand_name", "brand", "distributorname"),
    "ingredients": ("ingredients", "ingredientstatement", "ingredient_statement", "ingredientlist"),
}
UPC_ALIASES = ("upc_s", "upcs", "upc", "upc_code", "barcodes", "barcode")


def _canon(header: list[str]) -> dict[str, str | None]:
    """Map canonical field -> actual CSV column name (or None)."""
    lowered = {h.strip().lower(): h for h in header}
    out: dict[str, str | None] = {}
    for canon, aliases in COLUMN_ALIASES.items():
        out[canon] = next((lowered[a] for a in aliases if a in lowered), None)
    out["_upc"] = next((lowered[a] for a in UPC_ALIASES if a in lowered), None)
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
        conn.commit()
        n = conn.execute("SELECT COUNT(*) FROM dsld_products").fetchone()[0]
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

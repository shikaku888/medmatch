"""openFDA NDC directory → ndc_products(upc, ...) index — public domain.

Tải drug-ndc-0001-of-0001.json.zip (28MB) → mỗi packaging.barcode (UPC) map về
1 sản phẩm (brand, generic, labeler, dạng bào chế, active ingredients, excipients).

Usage:
    python -m backend.ndc_import           # mặc định backend/data/ndc.zip
    python -m backend.ndc_import path.zip
"""
import json
import sqlite3
import sys
import zipfile
from pathlib import Path

from .db import DB_PATH

DEFAULT_ZIP = Path(__file__).parent / "data" / "ndc.zip"

SCHEMA = """
CREATE TABLE IF NOT EXISTS ndc_products (
    product_ndc TEXT PRIMARY KEY,
    brand_name TEXT,
    generic_name TEXT,
    labeler TEXT,
    dosage_form TEXT,
    ingredients TEXT,
    inactive_ingredients TEXT
);
CREATE INDEX IF NOT EXISTS idx_ndc_brand ON ndc_products(brand_name);
"""


def _ndc_ingredients(record: dict) -> tuple[str, str]:
    """Return (active, inactive) ingredient text from an openFDA NDC record.

    Modern records use ``active_ingredients`` (name + strength) with an optional
    ``inactive_ingredients`` list; older releases exposed ``ingredients``. Both
    are handled here so re-imports never silently drop actives on format change.
"""
    active = record.get("active_ingredients") or record.get("ingredients") or []
    if active and isinstance(active[0], str):
        active_names = [str(i).strip() for i in active if str(i).strip()]
    else:
        active_names = []
        for item in active:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            strength = str(item.get("strength") or "").strip()
            if strength:
                name = f"{name} ({strength})"
            active_names.append(name)
    inactive = record.get("inactive_ingredients") or []
    inactive_names = []
    for item in inactive:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
        else:
            name = str(item).strip()
        if name:
            inactive_names.append(name)
    return "; ".join(active_names)[:1000], "; ".join(inactive_names)[:1000]


def run(zip_path: Path = DEFAULT_ZIP) -> dict:
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(ndc_products)")}
    if "inactive_ingredients" not in columns:
        conn.execute("ALTER TABLE ndc_products ADD COLUMN inactive_ingredients TEXT NOT NULL DEFAULT ''")
    cur = conn.cursor()
    buf = []
    products = 0

    with zipfile.ZipFile(zip_path) as z:
        name = z.namelist()[0]
        with z.open(name) as fh:
            data = json.loads(fh.read().decode("utf-8"))

    results = data.get("results") or []
    for p in results:
        brand = (p.get("brand_name") or "").strip()
        generic = (p.get("generic_name") or "").strip()
        product_ndc = (p.get("product_ndc") or "").strip()
        labeler = (p.get("labeler_name") or "").strip()
        form = (p.get("dosage_form") or "").strip()
        ingredients, inactive = _ndc_ingredients(p)
        products += 1
        if product_ndc:
            buf.append((product_ndc, brand, generic, labeler, form, ingredients, inactive))
        if len(buf) >= 5000:
            cur.executemany(
                "INSERT OR REPLACE INTO ndc_products VALUES (?,?,?,?,?,?,?)", buf)
            buf = []
    if buf:
        cur.executemany("INSERT OR REPLACE INTO ndc_products VALUES (?,?,?,?,?,?,?)", buf)
    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM ndc_products").fetchone()[0]
    probe = conn.execute("SELECT brand_name FROM ndc_products WHERE brand_name LIKE '%Tylenol%' LIMIT 1").fetchone()
    filled = conn.execute("SELECT COUNT(*) FROM ndc_products WHERE inactive_ingredients != ''").fetchone()[0]
    conn.close()
    summary = {
        "products": products,
        "indexed": total,
        "with_excipients": filled,
        "tylenol_probe": probe[0] if probe else None,
    }
    print(summary)
    return summary


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ZIP
    run(path)
    sys.exit(0)
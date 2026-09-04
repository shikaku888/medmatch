"""NIH DSLD FULL bulk importer — public domain (US gov).

Đọc toàn bộ ProductOverview_N.csv + OtherIngredients_N.csv + DietarySupplementFacts_N.csv
trong backend/data/dsld/ (bulk zip tải tay từ dsld.od.nih.gov → Download).

Khác bản cũ (dsld.py): importer này lấy TẤT CẢ sản phẩm — kể cả không có barcode
(barcode giả 'DSLD-<id>' để name-search vẫn hoạt động), ghép ingredients từ
DietarySupplementFacts (hoạt chất + liều) và OtherIngredients.

Usage:
    python -m backend.dsld_full
"""
import csv
import re
import sqlite3
import sys
from pathlib import Path

from .db import DB_PATH

DATA_DIR = Path(__file__).parent / "data" / "dsld"


def _norm_barcode(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) < 6:
        return None
    return digits[-14:] if len(digits) > 14 else digits


def _clean_name(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\x9a", "")).strip()


def run(batch: int = 2000) -> dict:
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("""CREATE TABLE IF NOT EXISTS dsld_products (
        barcode TEXT PRIMARY KEY, dsld_id TEXT, name TEXT, brand TEXT, ingredients TEXT)""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dsld_name ON dsld_products(name)")

    # 1. Other ingredients per dsld_id
    other: dict[str, list[str]] = {}
    for path in sorted(DATA_DIR.glob("OtherIngredients_*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                dsld_id = (row.get("DSLD ID") or "").strip()
                val = _clean_name(row.get("Other Ingredients"))
                if dsld_id and val:
                    other.setdefault(dsld_id, []).extend(p.strip() for p in val.split(";") if p.strip())

    # 2. Active ingredient facts per dsld_id: "Riboflavin 100 mg"
    facts: dict[str, list[str]] = {}
    for path in sorted(DATA_DIR.glob("DietarySupplementFacts_*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                dsld_id = (row.get("DSLD ID") or "").strip()
                ing = _clean_name(row.get("Ingredient"))
                if not dsld_id or not ing:
                    continue
                amount = (row.get("Amount Per Serving") or "").strip()
                unit = (row.get("Amount Per Serving Unit") or "").strip()
                piece = f"{ing} {amount} {unit}".strip()
                facts.setdefault(dsld_id, []).append(piece)

    # 3. Products
    inserted = skipped = no_name = 0
    cur = conn.cursor()
    for path in sorted(DATA_DIR.glob("ProductOverview_*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            buf = []
            for row in reader:
                dsld_id = (row.get("DSLD ID") or "").strip()
                name = _clean_name(row.get("Product Name"))
                if not dsld_id or not name:
                    no_name += 1
                    continue
                barcode = _norm_barcode(row.get("Bar Code")) or f"DSLD-{dsld_id}"
                brand = _clean_name(row.get("Brand Name")) or None
                parts = []
                if facts.get(dsld_id):
                    parts.append("; ".join(facts[dsld_id][:25]))
                if other.get(dsld_id):
                    parts.append("; ".join(other[dsld_id][:25]))
                ingredients = " | ".join(parts) or None
                if not ingredients:
                    skipped += 1
                    continue
                buf.append((barcode, dsld_id, name, brand, ingredients))
                if len(buf) >= batch:
                    cur.executemany(
                        "INSERT OR REPLACE INTO dsld_products VALUES (?,?,?,?,?)", buf)
                    inserted += len(buf)
                    buf = []
            if buf:
                cur.executemany(
                    "INSERT OR REPLACE INTO dsld_products VALUES (?,?,?,?,?)", buf)
                inserted += len(buf)
                buf = []
        conn.commit()
        print(f"  {path.name}: total inserted={inserted:,}")

    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM dsld_products").fetchone()[0]
    named = conn.execute("SELECT COUNT(*) FROM dsld_products WHERE name LIKE '%Centrum%'").fetchone()[0]
    nm = conn.execute("SELECT COUNT(*) FROM dsld_products WHERE name LIKE '%Nature Made%'").fetchone()[0]
    conn.close()
    summary = {"inserted": inserted, "skipped_no_ingredients": skipped,
               "total_rows": total, "centrum": named, "nature_made": nm}
    print(summary)
    return summary


if __name__ == "__main__":
    run()
    sys.exit(0)

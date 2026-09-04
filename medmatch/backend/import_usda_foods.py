"""Import USDA FoodData Central branded foods into product_index.

The ZIP archive is kept outside the runtime image. This importer retains only
barcode, product identity, ingredient text, and the USDA category.
"""
from __future__ import annotations

import argparse
import csv
import io
import sqlite3
import zipfile
from pathlib import Path

from .db import DB_PATH
from .product_index import _digits

SCHEMA = """
CREATE TABLE IF NOT EXISTS product_index (
    code TEXT PRIMARY KEY,
    code_type TEXT,
    name TEXT,
    brand TEXT,
    product_type TEXT,
    ingredients TEXT,
    excipients TEXT,
    matched TEXT
)
"""


def _member(zf: zipfile.ZipFile, suffix: str) -> str:
    for name in zf.namelist():
        if name.endswith(suffix):
            return name
    raise FileNotFoundError(f"USDA archive member not found: {suffix}")


def import_archive(
    archive: Path,
    conn: sqlite3.Connection,
    *,
    limit: int = 0,
) -> dict[str, int]:
    conn.executescript(SCHEMA)
    imported = skipped = duplicate = 0
    with zipfile.ZipFile(archive) as zf:
        foods: dict[str, str] = {}
        with zf.open(_member(zf, "/food.csv")) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
            for row in reader:
                foods[row.get("fdc_id", "")] = (row.get("description") or "").strip()

        with zf.open(_member(zf, "/branded_food.csv")) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
            for row in reader:
                if limit and imported >= limit:
                    break
                code = _digits(row.get("gtin_upc", ""))
                if len(code) < 8 or len(code) > 14:
                    skipped += 1
                    continue
                ingredients = (row.get("ingredients") or "").strip()
                name = (row.get("short_description") or foods.get(row.get("fdc_id", "")) or "").strip()
                if not name:
                    name = "USDA branded food"
                brand = (row.get("brand_name") or row.get("brand_owner") or "").strip()
                category = (row.get("branded_food_category") or "").strip()
                if category:
                    name = f"{name} [{category}]"
                cur = conn.execute(
                    "INSERT OR IGNORE INTO product_index "
                    "(code, code_type, name, brand, product_type, ingredients, excipients, matched) "
                    "VALUES (?, ?, ?, ?, 'food', ?, '', ?)",
                    (code, "upc" if len(code) in (12, 13) else "gtin", name, brand, ingredients, "[]"),
                )
                if cur.rowcount:
                    imported += 1
                else:
                    duplicate += 1
                if imported and imported % 5000 == 0:
                    conn.commit()
    conn.commit()
    return {"imported": imported, "skipped": skipped, "duplicates": duplicate}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    with sqlite3.connect(args.db, timeout=120) as conn:
        print(import_archive(args.archive, conn, limit=max(0, args.limit)))


if __name__ == "__main__":
    main()

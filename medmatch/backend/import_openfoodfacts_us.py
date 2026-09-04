"""Import United States products from the Open Food Facts TSV dump."""
from __future__ import annotations

import argparse
import csv
import gzip
import sqlite3
import sys
from pathlib import Path

from .db import DB_PATH
from .product_index import _digits


def _is_us(value: str) -> bool:
    countries = {part.strip().casefold() for part in (value or "").split(",")}
    return bool(countries & {"united states", "en:united-states", "us", "usa"})


def import_dump(dump: Path, conn: sqlite3.Connection, *, limit: int = 0) -> dict[str, int]:
    csv.field_size_limit(2**31 - 1)
    imported = skipped = duplicate = non_us = 0
    with gzip.open(dump, "rt", encoding="utf-8-sig", newline="") as raw:
        reader = csv.DictReader(raw, delimiter="\t")
        for row in reader:
            countries = f"{row.get('countries_en', '')},{row.get('countries_tags', '')}"
            if not _is_us(countries):
                non_us += 1
                continue
            if limit and imported >= limit:
                break
            code = _digits(row.get("code", ""))
            if len(code) < 8 or len(code) > 14:
                skipped += 1
                continue
            name = (row.get("product_name_en") or row.get("product_name") or row.get("generic_name_en") or row.get("generic_name") or "").strip()
            if not name:
                skipped += 1
                continue
            brand = (row.get("brands") or "").strip()
            ingredients = (row.get("ingredients_text_en") or row.get("ingredients_text") or "").strip()
            categories = (row.get("categories_en") or "").strip()
            if categories:
                name = f"{name} [{categories}]"
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
    return {"imported": imported, "skipped": skipped, "duplicates": duplicate, "non_us": non_us}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dump", type=Path)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    with sqlite3.connect(args.db, timeout=120) as conn:
        print(import_dump(args.dump, conn, limit=max(0, args.limit)))


if __name__ == "__main__":
    main()

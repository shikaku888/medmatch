"""Import Japan Open Food Facts barcode rows into product_index.

The input is the official Open Food Facts TSV gzip dump. Only records that
claim Japan and use the Japanese GS1 prefixes 45/49 are retained.
"""
from __future__ import annotations

import argparse
import csv
import gzip
from pathlib import Path

from .db import DB_PATH, get_conn
from .product_index import _digits

DEFAULT_DUMP = Path(__file__).resolve().parent / "data" / "openfoodfacts" / "en.openfoodfacts.org.products.csv.gz"


def _is_japan(row: dict[str, str]) -> bool:
    countries = " ".join((row.get("countries_en") or "", row.get("countries_tags") or "")).casefold()
    return "japan" in countries or "japon" in countries


def _is_japanese_code(code: str) -> bool:
    return code.startswith("45") or code.startswith("49")


def import_japan(dump_path: Path = DEFAULT_DUMP) -> dict[str, int]:
    conn = get_conn()
    inserted = skipped = non_japan = 0
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS product_index (code TEXT PRIMARY KEY, code_type TEXT, name TEXT, brand TEXT, product_type TEXT, ingredients TEXT, excipients TEXT, matched TEXT)"
        )
        with gzip.open(dump_path, "rt", encoding="utf-8", errors="replace", newline="") as stream:
            reader = csv.DictReader(stream, delimiter="\t")
            for row in reader:
                code = _digits(row.get("code") or "")
                if not _is_japanese_code(code):
                    continue
                if not _is_japan(row):
                    non_japan += 1
                    continue
                name = (row.get("product_name_en") or row.get("product_name_ja") or row.get("product_name") or "").strip()
                if not name:
                    skipped += 1
                    continue
                ingredients = (row.get("ingredients_text_en") or row.get("ingredients_text") or "").strip()
                cur = conn.execute(
                    "INSERT OR IGNORE INTO product_index (code,code_type,name,brand,product_type,ingredients,excipients,matched) VALUES (?,?,?,?,?,?,?,?)",
                    (code, "upc" if len(code) == 12 else "gtin", name[:512], (row.get("brands") or "")[:512], "food", ingredients[:4000], "", "[]"),
                )
                if cur.rowcount:
                    inserted += 1
        conn.commit()
    finally:
        conn.close()
    return {"inserted": inserted, "skipped": skipped, "non_japan": non_japan}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", type=Path, default=DEFAULT_DUMP)
    args = parser.parse_args()
    print(import_japan(args.dump))


if __name__ == "__main__":
    main()

"""Stream selected tables from the official DrugCentral PostgreSQL dump.

The 2023 dump has structures, synonyms, ATC, products and target/MOA facts,
but no indication COPY relation. This importer preserves that boundary rather
than inventing indications from unrelated fields. DrugCentral is CC BY-SA 4.0.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from .db import DB_PATH
from .license_registry import register_release, seed_licenses

DEFAULT_DUMP = Path(__file__).parent / "data" / "drugcentral" / "drugcentral.dump.11012023.sql.gz"
SOURCE_URL = "https://unmtid-dbs.net/download/drugcentral.dump.11012023.sql.gz"
PARSER_VERSION = "drugcentral-pgcopy-v1"
# dump table: (sqlite table, source columns, sqlite columns, sqlite definition)
TABLES = {
    "structures": ("drugcentral_structures", ("id", "name", "smiles", "inchikey", "cas_reg_no"), ("struct_id", "name", "smiles", "inchikey", "cas_reg_no"), "struct_id TEXT PRIMARY KEY, name TEXT, smiles TEXT, inchikey TEXT, cas_reg_no TEXT"),
    "synonyms": ("drugcentral_synonyms", ("id", "name", "preferred_name", "lname"), ("struct_id", "synonym", "preferred_name", "lname"), "struct_id TEXT NOT NULL, synonym TEXT NOT NULL, preferred_name INTEGER, lname TEXT, PRIMARY KEY (struct_id, synonym)"),
    "atc": ("drugcentral_atc", ("chemical_substance", "code", "l1_name", "l2_name", "l3_name", "l4_name"), ("chemical_substance", "code", "l1_name", "l2_name", "l3_name", "l4_name"), "chemical_substance TEXT NOT NULL, code TEXT NOT NULL, l1_name TEXT, l2_name TEXT, l3_name TEXT, l4_name TEXT, PRIMARY KEY (chemical_substance, code)"),
    "struct2atc": ("drugcentral_struct_atc", ("struct_id", "atc_code"), ("struct_id", "atc_code"), "struct_id TEXT NOT NULL, atc_code TEXT NOT NULL, PRIMARY KEY (struct_id, atc_code)"),
    "product": ("drugcentral_products", ("id", "ndc_product_code", "form", "generic_name", "product_name", "route", "marketing_status"), ("product_id", "ndc_product_code", "form", "generic_name", "product_name", "route", "marketing_status"), "product_id TEXT PRIMARY KEY, ndc_product_code TEXT, form TEXT, generic_name TEXT, product_name TEXT, route TEXT, marketing_status TEXT"),
    "act_table_full": ("drugcentral_target_facts", ("act_id", "struct_id", "target_id", "target_name", "target_class", "relation", "moa", "action_type", "act_source_url", "moa_source_url"), ("act_id", "struct_id", "target_id", "target_name", "target_class", "relation", "moa", "action_type", "act_source_url", "moa_source_url"), "act_id TEXT PRIMARY KEY, struct_id TEXT NOT NULL, target_id TEXT, target_name TEXT, target_class TEXT, relation TEXT, moa TEXT, action_type TEXT, act_source_url TEXT, moa_source_url TEXT"),
}


def _schema() -> str:
    sql = [f"CREATE TABLE IF NOT EXISTS {target} ({definition})" for target, _, _, definition in TABLES.values()]
    sql += [
        "CREATE INDEX IF NOT EXISTS idx_dc_struct_name ON drugcentral_structures(name)",
        "CREATE INDEX IF NOT EXISTS idx_dc_synonym_name ON drugcentral_synonyms(lname)",
        "CREATE INDEX IF NOT EXISTS idx_dc_atc_struct ON drugcentral_struct_atc(struct_id)",
        "CREATE INDEX IF NOT EXISTS idx_dc_target_facts_struct ON drugcentral_target_facts(struct_id)",
        "CREATE INDEX IF NOT EXISTS idx_dc_product_generic ON drugcentral_products(generic_name)",
    ]
    return ";".join(sql) + ";"


def _copy_fields(line: str) -> list[str | None]:
    fields = next(csv.reader([line.rstrip("\n")], delimiter="\t", quoting=csv.QUOTE_NONE, escapechar="\\"))
    return [None if value == "N" else value for value in fields]


def _header(line: str) -> tuple[str, list[str]] | None:
    match = re.match(r"COPY public\.([A-Za-z0-9_]+) \((.*?)\) FROM stdin;", line)
    if not match:
        return None
    return match.group(1), [part.strip() for part in match.group(2).split(",")]


def run(conn: sqlite3.Connection, dump: Path = DEFAULT_DUMP, batch_size: int = 5000) -> dict:
    conn.row_factory = sqlite3.Row
    conn.executescript(_schema())
    seed_licenses(conn, {"drugcentral"})
    for target, _, _, _ in TABLES.values():
        conn.execute(f"DELETE FROM {target}")
    imported = {name: 0 for name in TABLES}
    errors = 0
    active: str | None = None
    source_columns: list[str] = []
    buffer: list[tuple] = []
    downloaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def flush() -> None:
        nonlocal buffer
        if not active or not buffer:
            return
        target, _, target_columns, _ = TABLES[active]
        placeholders = ",".join("?" for _ in target_columns)
        conn.executemany(
            f"INSERT OR REPLACE INTO {target} ({','.join(target_columns)}) VALUES ({placeholders})",
            buffer,
        )
        buffer = []

    with gzip.open(dump, "rt", encoding="utf-8", errors="replace", newline="") as stream:
        for line in stream:
            parsed = _header(line)
            if parsed:
                flush()
                active, source_columns = parsed
                if active not in TABLES:
                    active = None
                continue
            if active is None:
                continue
            if line.rstrip("\n") == "\\.":
                flush()
                active, source_columns = None, []
                continue
            try:
                values = _copy_fields(line)
                positions = {column: i for i, column in enumerate(source_columns)}
                wanted = TABLES[active][1]
                selected = tuple(values[positions[column]] if positions.get(column, -1) < len(values) else None for column in wanted)
                if selected[0] is None or (active != "structures" and len(selected) > 1 and selected[1] is None):
                    continue
                buffer.append(selected)
                imported[active] += 1
                if len(buffer) >= batch_size:
                    flush()
            except (csv.Error, IndexError, UnicodeError):
                errors += 1
        flush()
    conn.commit()
    digest = hashlib.sha256()
    with dump.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    register_release(conn, "drugcentral", "DrugCentral PostgreSQL dump selected tables", version="2023-11-01", source_url=SOURCE_URL, terms_url="https://drugcentral.org/terms", licence_name="CC BY-SA 4.0 (DrugCentral)", commercial_status="core_open", downloaded_at=downloaded_at, sha256=digest.hexdigest(), parser_version=PARSER_VERSION, notes="Selected structures, synonyms, ATC, products and target/MOA COPY tables")
    stats = {"imported": imported, "errors": errors}
    stats["rows"] = {name: conn.execute(f"SELECT COUNT(*) FROM {target}").fetchone()[0] for name, (target, _, _, _) in TABLES.items()}
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dump", nargs="?", type=Path, default=DEFAULT_DUMP)
    args = parser.parse_args()
    conn = sqlite3.connect(DB_PATH, timeout=120)
    try:
        print(run(conn, args.dump))
    finally:
        conn.close()

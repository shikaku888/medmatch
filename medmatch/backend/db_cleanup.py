"""Offline SQLite cleanup for the canonical MedMatch database.

The runtime snapshot already excludes build-only raw tables. This module keeps
that boundary explicit, removes exact duplicate source rows from a copied
canonical database, rebuilds derived aggregates, and verifies the result
before the caller promotes it.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sqlite3
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_SOURCE = Path(__file__).with_name("medmatch.db")
DEFAULT_OUTPUT = Path(__file__).with_name("medmatch.cleaned.db")

ONSIDES_RAW_COLUMNS: tuple[str, ...] = (
    "product_label_id",
    "source_region",
    "source_product_id",
    "source_label_url",
    "rxnorm_product_id",
    "rxnorm_ingredient_id",
    "rxnorm_ingredient_name",
    "effect_meddra_id",
    "effect",
    "label_section",
    "match_method",
    "pred0",
    "pred1",
    "source",
)

FDA_RAW_COLUMNS: dict[str, tuple[str, ...]] = {
    "fda_drug": (
        "primaryid",
        "caseid",
        "drug_seq",
        "role_cod",
        "drugname",
        "prod_ai",
        "val_vbm",
        "route",
        "dose_vbm",
        "dechal",
        "rechal",
        "nda_num",
        "quarter",
    ),
    "fda_indication": ("primaryid", "caseid", "indi_pt", "quarter"),
    "fda_outcome": ("primaryid", "caseid", "outc_cod", "quarter"),
    "fda_reaction": ("primaryid", "caseid", "pt", "drug_rec_act", "quarter"),
    "fda_therapy": (
        "primaryid",
        "caseid",
        "start_dt",
        "end_dt",
        "dur",
        "dur_cod",
        "quarter",
    ),
}

DEDUPLICATION_PLAN: dict[str, tuple[tuple[str, ...], str | None]] = {
    "onsides_effects_raw": (ONSIDES_RAW_COLUMNS, "row_id"),
    **{table: (columns, None) for table, columns in FDA_RAW_COLUMNS.items()},
}


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def _table_columns(conn: sqlite3.Connection, table: str) -> tuple[str, ...]:
    return tuple(row[1] for row in conn.execute(f"PRAGMA table_info({quote_identifier(table)})"))


def _table_ddl(conn: sqlite3.Connection, table: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not row or not row[0]:
        raise RuntimeError(f"missing CREATE TABLE DDL for {table}")
    return str(row[0])


def _replace_ddl_table_name(ddl: str, old: str, new: str) -> str:
    pattern = re.compile(
        r"(?is)^(\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?)("
        r'"(?:""|[^"])+"|`[^`]+`|\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_$]*)'
        r"(?=\s*\()"
    )
    match = pattern.match(ddl)
    if not match:
        raise RuntimeError(f"unsupported CREATE TABLE DDL for {old}")
    parsed_name = match.group(2).strip('"`[]')
    if parsed_name != old:
        raise RuntimeError(f"DDL name mismatch for {old}: {parsed_name}")
    return ddl[: match.start(2)] + quote_identifier(new) + ddl[match.end(2) :]


def _index_sql(conn: sqlite3.Connection, table: str) -> tuple[tuple[str, str], ...]:
    return tuple(
        (str(row[0]), str(row[1]))
        for row in conn.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type='index' AND tbl_name=? AND sql IS NOT NULL "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name",
            (table,),
        )
    )


def deduplicate_table(
    conn: sqlite3.Connection,
    table: str,
    key_columns: Sequence[str],
    surrogate_column: str | None = None,
) -> dict[str, int | str]:
    """Replace a table with one exact row per key tuple.

    The caller supplies the semantic identity columns. A surrogate integer
    column, such as OnSIDES row_id, is regenerated from the first retained row.
    The source table is changed transactionally by SQLite; the caller should
    still operate on a backup/copy rather than the live database.
    """
    if not table_exists(conn, table):
        return {"table": table, "before": 0, "after": 0, "removed": 0, "status": "missing"}

    columns = _table_columns(conn, table)
    keys = tuple(key_columns)
    missing = [column for column in keys if column not in columns]
    if missing:
        raise RuntimeError(f"{table}: missing key columns {missing}")
    if surrogate_column is not None and surrogate_column not in columns:
        raise RuntimeError(f"{table}: missing surrogate column {surrogate_column}")

    quoted_table = quote_identifier(table)
    quoted_columns = ", ".join(quote_identifier(column) for column in columns)
    quoted_keys = ", ".join(quote_identifier(column) for column in keys)
    before = int(conn.execute(f"SELECT COUNT(*) FROM {quoted_table}").fetchone()[0])
    if before == 0:
        return {"table": table, "before": 0, "after": 0, "removed": 0, "status": "empty"}

    old_table = f"__cleanup_old_{table}"
    clean_table = f"__cleanup_new_{table}"
    for temporary in (old_table, clean_table):
        conn.execute(f"DROP TABLE IF EXISTS {quote_identifier(temporary)}")

    ddl = _table_ddl(conn, table)
    indexes = _index_sql(conn, table)
    for index_name, _ in indexes:
        conn.execute(f"DROP INDEX {quote_identifier(index_name)}")

    conn.execute(
        f"ALTER TABLE {quoted_table} RENAME TO {quote_identifier(old_table)}"
    )
    conn.execute(_replace_ddl_table_name(ddl, table, clean_table))

    if surrogate_column is None:
        select_columns = quoted_columns
        insert_columns = quoted_columns
    else:
        select_columns = ", ".join(
            [f"MIN({quote_identifier(surrogate_column)})", *[
                quote_identifier(column) for column in keys
            ]]
        )
        insert_columns = ", ".join(
            [quote_identifier(surrogate_column), *[
                quote_identifier(column) for column in keys
            ]]
        )

    conn.execute(
        f"INSERT INTO {quote_identifier(clean_table)} ({insert_columns}) "
        f"SELECT {select_columns} FROM {quote_identifier(old_table)} "
        f"GROUP BY {quoted_keys}"
    )
    after = int(conn.execute(f"SELECT COUNT(*) FROM {quote_identifier(clean_table)}").fetchone()[0])

    conn.execute(f"DROP TABLE {quote_identifier(old_table)}")
    conn.execute(
        f"ALTER TABLE {quote_identifier(clean_table)} RENAME TO {quote_identifier(table)}"
    )
    for _, sql in indexes:
        conn.execute(sql)

    return {
        "table": table,
        "before": before,
        "after": after,
        "removed": before - after,
        "status": "cleaned",
    }


def rebuild_onsides_aggregate(conn: sqlite3.Connection) -> dict[str, int | str]:
    if not table_exists(conn, "onsides_effects_raw") or not table_exists(
        conn, "onsides_ingredient_effects"
    ):
        return {"table": "onsides_ingredient_effects", "rows": 0, "status": "missing"}

    conn.execute("DELETE FROM onsides_ingredient_effects")
    conn.execute(
        """
        INSERT INTO onsides_ingredient_effects
            (rxnorm_ingredient_id, rxnorm_ingredient_name, effect_meddra_id, effect,
             source_region, row_count, label_count, min_pred1, max_pred1, high_confidence)
        SELECT r.rxnorm_ingredient_id, MIN(r.rxnorm_ingredient_name), r.effect_meddra_id,
               MIN(r.effect), r.source_region, COUNT(*), COUNT(DISTINCT r.product_label_id),
               MIN(r.pred1), MAX(r.pred1),
               MAX(CASE WHEN h.rxnorm_ingredient_id IS NOT NULL THEN 1 ELSE 0 END)
        FROM onsides_effects_raw r LEFT JOIN onsides_high_confidence h
          ON h.rxnorm_ingredient_id = r.rxnorm_ingredient_id
         AND h.effect_meddra_id = r.effect_meddra_id
        WHERE r.rxnorm_ingredient_id IS NOT NULL
        GROUP BY r.rxnorm_ingredient_id, r.effect_meddra_id, r.source_region
        """
    )
    rows = int(conn.execute("SELECT COUNT(*) FROM onsides_ingredient_effects").fetchone()[0])
    return {"table": "onsides_ingredient_effects", "rows": rows, "status": "rebuilt"}


def _copy_database(source: Path, output: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    if source.resolve() == output.resolve():
        raise ValueError("source and output must be different files")
    wal = source.with_name(source.name + "-wal")
    if wal.exists() and wal.stat().st_size:
        raise RuntimeError(f"source has a non-empty WAL; stop writers first: {wal}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.cleanup-{os.getpid()}")
    if temporary.exists():
        temporary.unlink()
    shutil.copyfile(source, temporary)
    os.replace(temporary, output)


def compact_database(source: Path = DEFAULT_SOURCE, output: Path = DEFAULT_OUTPUT) -> dict:
    """Create a verified, compacted copy without mutating ``source``."""
    source = source.resolve()
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output}")
    _copy_database(source, output)

    results: list[dict[str, int | str]] = []
    try:
        with sqlite3.connect(output, timeout=120) as conn:
            conn.execute("PRAGMA foreign_keys=OFF")
            for table, (keys, surrogate) in DEDUPLICATION_PLAN.items():
                results.append(deduplicate_table(conn, table, keys, surrogate))
            conn.commit()

            results.append(rebuild_onsides_aggregate(conn))
            conn.commit()

            if all(table_exists(conn, table) for table in ("fda_report", "fda_drug", "fda_reaction", "fda_outcome")):
                from .faers import build_adverse_event_aggregate

                faers_result = build_adverse_event_aggregate(conn)
                results.append({"table": "faers_adverse_events", **faers_result})

            if table_exists(conn, "evidence_ontology_intersection"):
                from .evidence_ontology import build_intersection

                intersection_result = build_intersection(conn)
                results.append({"table": "evidence_ontology_intersection", **intersection_result})

            conn.execute("ANALYZE")
            conn.commit()
            conn.execute("VACUUM")
            integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
            foreign_key_errors = list(conn.execute("PRAGMA foreign_key_check"))
            if integrity != "ok":
                raise RuntimeError(f"integrity_check failed: {integrity}")
            if foreign_key_errors:
                raise RuntimeError(f"foreign_key_check failed: {foreign_key_errors[:3]}")

        return {
            "source": str(source),
            "output": str(output),
            "source_bytes": source.stat().st_size,
            "output_bytes": output.stat().st_size,
            "integrity": integrity,
            "results": results,
        }
    except Exception:
        if output.exists():
            output.unlink()
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = compact_database(args.source, args.output)
    print(f"source={result['source']}")
    print(f"output={result['output']}")
    print(f"source_bytes={result['source_bytes']}")
    print(f"output_bytes={result['output_bytes']}")
    print(f"integrity={result['integrity']}")
    for item in result["results"]:
        print(item)


if __name__ == "__main__":
    main()

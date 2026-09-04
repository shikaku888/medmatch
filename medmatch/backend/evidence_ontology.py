"""Canonical evidence intersection across independent source families.

The only shared identity used here is an exact RxNorm IN/PIN name match.
Evidence is intersected at the ingredient level, never by substring matching
adverse-event text. OnSIDES carries MedDRA effect IDs; FAERS and label text do
not carry a validated MedDRA mapping in this database, so their terms are
summarized as source counts and are not merged into OnSIDES effects.
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone

from .db import DB_PATH

ONTOLOGY_VERSION = "rxcui-ingredient-source-intersection-v1"
SOURCE_CODE = "evidence_ontology"
PARSER_VERSION = "evidence-ontology-v1"

SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence_ontology_intersection (
    rxnorm_ingredient_id TEXT PRIMARY KEY,
    rxnorm_ingredient_name TEXT NOT NULL,
    sources TEXT NOT NULL,
    source_count INTEGER NOT NULL,
    onsides_effect_count INTEGER NOT NULL DEFAULT 0,
    onsides_row_count INTEGER NOT NULL DEFAULT 0,
    onsides_label_count INTEGER NOT NULL DEFAULT 0,
    onsides_regions TEXT NOT NULL DEFAULT '[]',
    onsides_high_confidence_count INTEGER NOT NULL DEFAULT 0,
    faers_case_count INTEGER NOT NULL DEFAULT 0,
    faers_term_count INTEGER NOT NULL DEFAULT 0,
    label_count INTEGER NOT NULL DEFAULT 0,
    match_method TEXT NOT NULL,
    ontology_version TEXT NOT NULL,
    built_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_intersection_sources
    ON evidence_ontology_intersection(source_count, sources);
"""


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^0-9a-z]+", " ", (value or "").casefold())).strip()


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _rxnorm_exact_index(conn: sqlite3.Connection) -> dict[str, set[str]]:
    if not _table_exists(conn, "rxnorm_names"):
        return {}
    index: dict[str, set[str]] = defaultdict(set)
    for rxcui, name in conn.execute(
        "SELECT rxcui, name FROM rxnorm_names WHERE tty IN ('IN','PIN')"
    ):
        key = normalize_name(name)
        if key:
            index[key].add(str(rxcui))
    return dict(index)


def _canonical_name(conn: sqlite3.Connection, rxcui: str, fallback: str) -> str:
    if _table_exists(conn, "rxnorm_concepts"):
        row = conn.execute(
            "SELECT name FROM rxnorm_concepts WHERE rxcui=?", (rxcui,)
        ).fetchone()
        if row and row[0]:
            return str(row[0])
    return fallback


def _add_faers(
    conn: sqlite3.Connection,
    index: dict[str, set[str]],
    totals: dict[str, dict[str, int]],
) -> None:
    if not _table_exists(conn, "faers_adverse_events"):
        return
    for drug_key, case_count, term_count in conn.execute(
        "SELECT drug_key, SUM(case_count), COUNT(DISTINCT pt) "
        "FROM faers_adverse_events GROUP BY drug_key"
    ):
        ids = index.get(normalize_name(drug_key), set())
        if len(ids) != 1:
            continue
        rxcui = next(iter(ids))
        totals[rxcui]["faers_case_count"] += int(case_count or 0)
        totals[rxcui]["faers_term_count"] += int(term_count or 0)


def _add_labels(
    conn: sqlite3.Connection,
    index: dict[str, set[str]],
    totals: dict[str, dict[str, int]],
) -> None:
    for table in ("label_section", "openfda_label_sections"):
        if not _table_exists(conn, table):
            continue
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        name_columns = [column for column in ("generic_name", "openfda_generic") if column in columns]
        if not name_columns:
            continue
        select = ",".join(name_columns)
        for row in conn.execute(f"SELECT {select} FROM {table}"):
            matched: set[str] = set()
            for value in row:
                ids = index.get(normalize_name(value or ""), set())
                if len(ids) == 1:
                    matched.update(ids)
            for rxcui in matched:
                totals[rxcui]["label_count"] += 1


def build_intersection(conn: sqlite3.Connection) -> dict:
    """Build only multi-source ingredient intersections with exact identity."""
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    built_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    columns = {row[1] for row in conn.execute("PRAGMA table_info(evidence_ontology_intersection)")}
    if "built_at" not in columns:
        conn.execute("ALTER TABLE evidence_ontology_intersection ADD COLUMN built_at TEXT")
    if not _table_exists(conn, "onsides_ingredient_effects"):
        conn.execute("DELETE FROM evidence_ontology_intersection")
        conn.commit()
        return {"status": "missing_onsides", "intersections": 0}

    index = _rxnorm_exact_index(conn)
    totals: dict[str, dict[str, int]] = defaultdict(lambda: {
        "faers_case_count": 0,
        "faers_term_count": 0,
        "label_count": 0,
    })
    _add_faers(conn, index, totals)
    _add_labels(conn, index, totals)

    aggregate_columns = {row[1] for row in conn.execute("PRAGMA table_info(onsides_ingredient_effects)")}
    high_confidence_expr = "SUM(high_confidence)" if "high_confidence" in aggregate_columns else "0"
    onsides: dict[str, dict] = {}
    for row in conn.execute(
        "SELECT rxnorm_ingredient_id, MIN(rxnorm_ingredient_name) AS ingredient_name, "
        "COUNT(*) AS effect_count, SUM(row_count) AS row_count, "
        "SUM(label_count) AS label_count, GROUP_CONCAT(DISTINCT source_region) AS regions, "
        f"{high_confidence_expr} AS high_confidence_count "
        "FROM onsides_ingredient_effects "
        "GROUP BY rxnorm_ingredient_id"
    ):
        rxcui = str(row["rxnorm_ingredient_id"])
        onsides[rxcui] = {
            "ingredient_name": row["ingredient_name"] or _canonical_name(conn, rxcui, rxcui),
            "effect_count": int(row["effect_count"] or 0),
            "row_count": int(row["row_count"] or 0),
            "label_count": int(row["label_count"] or 0),
            "regions": sorted({region for region in (row["regions"] or "").split(",") if region}),
            "high_confidence_count": int(row["high_confidence_count"] or 0),
        }

    conn.execute("DELETE FROM evidence_ontology_intersection")
    inserted = 0
    source_counts = defaultdict(int)
    for rxcui, info in onsides.items():
        extra = totals.get(rxcui, {})
        sources = ["OnSIDES"]
        if extra.get("faers_case_count", 0) > 0:
            sources.append("FAERS")
        if extra.get("label_count", 0) > 0:
            sources.append("FDA labels")
        if len(sources) < 2:
            continue
        source_counts["+".join(sources)] += 1
        conn.execute(
            "INSERT INTO evidence_ontology_intersection "
            "(rxnorm_ingredient_id, rxnorm_ingredient_name, sources, source_count, "
            "onsides_effect_count, onsides_row_count, onsides_label_count, onsides_regions, "
            "onsides_high_confidence_count, faers_case_count, faers_term_count, label_count, "
            "match_method, ontology_version, built_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                rxcui,
                info["ingredient_name"],
                json.dumps(sources),
                len(sources),
                info["effect_count"],
                info["row_count"],
                info["label_count"],
                json.dumps(info["regions"]),
                info["high_confidence_count"],
                extra.get("faers_case_count", 0),
                extra.get("faers_term_count", 0),
                extra.get("label_count", 0),
                "rxnorm_exact_name",
                ONTOLOGY_VERSION,
                built_at,
            ),
        )
        inserted += 1
    conn.commit()
    return {
        "status": "ok",
        "intersections": inserted,
        "source_combinations": dict(source_counts),
        "ontology_version": ONTOLOGY_VERSION,
    }


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    try:
        print(build_intersection(conn))
    finally:
        conn.close()

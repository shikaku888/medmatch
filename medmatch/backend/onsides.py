"""Import OnSIDES drug side effects (CC BY 4.0) for our class member drugs.

Streams product_adverse_effect.csv (399MB), keeps rows whose product label
matches one of our class member drug names, filters to PubMedBERT-method
rows with pred0 >= 0.6, aggregates the most frequent MedDRA effects per
drug class. License: CC BY 4.0 (attribution) — commercial OK.

Usage:
    python -m backend.onsides [zip_path] [--limit N] [--full]
"""
import argparse
import csv
import json
import sqlite3
import zipfile
from collections import Counter
from pathlib import Path

from .db_cleanup import ONSIDES_RAW_COLUMNS, deduplicate_table
from .engine import normalize

DATA_DIR = Path(__file__).parent / "data"
ZIP_PATH = Path(r"C:/tmp/onsides.zip")

SCHEMA = """
CREATE TABLE IF NOT EXISTS onsides_effects (
    cls_a TEXT NOT NULL,
    drug_name TEXT NOT NULL,
    effect TEXT NOT NULL,
    n INTEGER NOT NULL,
    source TEXT NOT NULL DEFAULT 'OnSIDES (CC BY 4.0)',
    PRIMARY KEY (cls_a, drug_name, effect)
);
"""

FULL_SCHEMA = """
CREATE TABLE IF NOT EXISTS onsides_effects_raw (
    row_id INTEGER PRIMARY KEY,
    product_label_id TEXT NOT NULL,
    source_region TEXT NOT NULL,
    source_product_id TEXT,
    source_label_url TEXT,
    rxnorm_product_id TEXT,
    rxnorm_ingredient_id TEXT,
    rxnorm_ingredient_name TEXT,
    effect_meddra_id TEXT NOT NULL,
    effect TEXT NOT NULL,
    label_section TEXT,
    match_method TEXT,
    pred0 REAL,
    pred1 REAL,
    source TEXT NOT NULL DEFAULT 'OnSIDES v3.1.1 (CC BY 4.0)'
);
CREATE INDEX IF NOT EXISTS idx_onsides_raw_ingredient
    ON onsides_effects_raw(rxnorm_ingredient_id, effect_meddra_id);
CREATE INDEX IF NOT EXISTS idx_onsides_raw_region
    ON onsides_effects_raw(source_region);
CREATE TABLE IF NOT EXISTS onsides_high_confidence (
    rxnorm_ingredient_id TEXT NOT NULL,
    effect_meddra_id TEXT NOT NULL,
    PRIMARY KEY (rxnorm_ingredient_id, effect_meddra_id)
);
CREATE TABLE IF NOT EXISTS onsides_ingredient_effects (
    rxnorm_ingredient_id TEXT NOT NULL,
    rxnorm_ingredient_name TEXT NOT NULL,
    effect_meddra_id TEXT NOT NULL,
    effect TEXT NOT NULL,
    source_region TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    label_count INTEGER NOT NULL,
    min_pred1 REAL,
    max_pred1 REAL,
    high_confidence INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'OnSIDES v3.1.1 (CC BY 4.0)',
    PRIMARY KEY (rxnorm_ingredient_id, effect_meddra_id, source_region)
);
CREATE INDEX IF NOT EXISTS idx_onsides_ingredient_effect
    ON onsides_ingredient_effects(rxnorm_ingredient_id, effect);
"""


def _load_class_index() -> dict[str, str]:
    classes = json.loads((DATA_DIR / "drug_classes.json").read_text(encoding="utf-8"))
    drug_names = json.loads((DATA_DIR / "drug_names_en.json").read_text(encoding="utf-8"))
    idx: dict[str, str] = {}
    for c in classes:
        for d in c["drugs"]:
            idx.setdefault(normalize(drug_names.get(d.lower(), d)), c["id"])
    return idx


def _drug_in_label(label_name: str, cls_index: dict[str, str]) -> tuple[str, str] | None:
    low = normalize(label_name)
    if not low:
        return None
    # word-boundary containment for each known drug name
    for name, cls_id in cls_index.items():
        if not name or len(name) < 5:
            continue
        if f" {name}" in f" {low}" or f"-{name}" in low:
            return name, cls_id
    return None


def import_all(conn: sqlite3.Connection, zip_path: Path = ZIP_PATH, limit: int | None = None) -> dict:
    conn.executescript(SCHEMA)
    conn.execute("DELETE FROM onsides_effects")
    cls_index = _load_class_index()

    with zipfile.ZipFile(zip_path) as z:
        # 1) vocab
        vocab: dict[str, str] = {}
        with z.open("csv/vocab_meddra_adverse_effect.csv") as f:
            for row in csv.DictReader(line.decode("utf-8", errors="replace") for line in f):
                if row["meddra_term_type"] == "PT":
                    vocab[row["meddra_id"]] = row["meddra_name"]
        # 2) labels -> drug/class
        label_drug: dict[str, tuple[str, str]] = {}
        with z.open("csv/product_label.csv") as f:
            for row in csv.DictReader(line.decode("utf-8", errors="replace") for line in f):
                hit = _drug_in_label(row.get("source_product_name") or "", cls_index)
                if hit:
                    label_drug[row["label_id"]] = hit
        # 3) stream effects
        counts: Counter = Counter()
        rows = 0
        kept = 0
        with z.open("csv/product_adverse_effect.csv") as f:
            reader = csv.DictReader(line.decode("utf-8", errors="replace") for line in f)
            for row in reader:
                rows += 1
                lid = row.get("product_label_id")
                if lid not in label_drug:
                    continue
                if row.get("match_method") != "PMB":
                    continue
                try:
                    if float(row.get("pred0", 0)) < 0.6:
                        continue
                except ValueError:
                    continue
                effect = vocab.get(row.get("effect_meddra_id"))
                if not effect:
                    continue
                name, cls_id = label_drug[lid]
                counts[(cls_id, name, effect)] += 1
                kept += 1
                if limit and kept >= limit:
                    break
        for (cls_id, name, effect), n in counts.items():
            conn.execute(
                "INSERT OR REPLACE INTO onsides_effects (cls_a, drug_name, effect, n)"
                " VALUES (?,?,?,?)",
                (cls_id, name, effect, n),
            )
    conn.commit()
    return {"rows": rows, "kept": kept, "pairs": len(counts),
            "drugs_matched": len(label_drug), "vocab_pt": len(vocab)}


def import_full(
    conn: sqlite3.Connection,
    zip_path: Path = DATA_DIR / "onsides" / "onsides-v3.1.1.zip",
    limit: int | None = None,
) -> dict:
    conn.executescript(FULL_SCHEMA)
    # Bulk-load without maintaining secondary indexes per row; recreate them
    # once after the single transaction so a full release import stays bounded.
    conn.execute("DROP INDEX IF EXISTS idx_onsides_raw_ingredient")
    conn.execute("DROP INDEX IF EXISTS idx_onsides_raw_region")
    conn.execute("DROP INDEX IF EXISTS idx_onsides_ingredient_effect")
    columns = {row[1] for row in conn.execute("PRAGMA table_info(onsides_ingredient_effects)")}
    if "high_confidence" not in columns:
        conn.execute(
            "ALTER TABLE onsides_ingredient_effects ADD COLUMN "
            "high_confidence INTEGER NOT NULL DEFAULT 0"
        )
    conn.execute("BEGIN")
    conn.execute("DELETE FROM onsides_effects_raw")
    conn.execute("DELETE FROM onsides_ingredient_effects")
    conn.execute("DELETE FROM onsides_high_confidence")
    with zipfile.ZipFile(zip_path) as z:
        high_confidence: set[tuple[str, str]] = set()
        effects: dict[str, str] = {}
        with z.open("csv/vocab_meddra_adverse_effect.csv") as f:
            for row in csv.DictReader(line.decode("utf-8", errors="replace") for line in f):
                if row.get("meddra_term_type") == "PT":
                    effect_id = (row.get("meddra_id") or "").strip()
                    if effect_id:
                        effects[effect_id] = (row.get("meddra_name") or effect_id).strip()
        with z.open("csv/high_confidence.csv") as f:
            for row in csv.DictReader(line.decode("utf-8", errors="replace") for line in f):
                ingredient_id = (row.get("ingredient_id") or "").strip()
                effect_id = (row.get("effect_meddra_id") or "").strip()
                if ingredient_id and effect_id:
                    high_confidence.add((ingredient_id, effect_id))
        if high_confidence:
            conn.executemany(
                "INSERT OR IGNORE INTO onsides_high_confidence "
                "(rxnorm_ingredient_id, effect_meddra_id) VALUES (?,?)",
                high_confidence,
            )

        labels: dict[str, tuple[str, str, str | None]] = {}
        with z.open("csv/product_label.csv") as f:
            for row in csv.DictReader(line.decode("utf-8", errors="replace") for line in f):
                label_id = (row.get("label_id") or "").strip()
                if label_id:
                    labels[label_id] = (
                        (row.get("source") or "UNKNOWN").strip() or "UNKNOWN",
                        (row.get("source_product_id") or "").strip() or None,
                        (row.get("source_label_url") or "").strip() or None,
                    )

        product_to_ingredients: dict[str, list[str]] = {}
        with z.open("csv/vocab_rxnorm_ingredient_to_product.csv") as f:
            for row in csv.DictReader(line.decode("utf-8", errors="replace") for line in f):
                product_id = (row.get("product_id") or "").strip()
                ingredient_id = (row.get("ingredient_id") or "").strip()
                if product_id and ingredient_id:
                    product_to_ingredients.setdefault(product_id, []).append(ingredient_id)
        ingredient_names: dict[str, str] = {}
        with z.open("csv/vocab_rxnorm_ingredient.csv") as f:
            for row in csv.DictReader(line.decode("utf-8", errors="replace") for line in f):
                ingredient_id = (row.get("rxnorm_id") or "").strip()
                if ingredient_id and row.get("rxnorm_term_type") == "Ingredient":
                    ingredient_names[ingredient_id] = (
                        row.get("rxnorm_name") or ingredient_id
                    ).strip()
        label_products: dict[str, list[str]] = {}
        with z.open("csv/product_to_rxnorm.csv") as f:
            for row in csv.DictReader(line.decode("utf-8", errors="replace") for line in f):
                label_id = (row.get("label_id") or "").strip()
                product_id = (row.get("rxnorm_product_id") or "").strip()
                if label_id and product_id:
                    label_products.setdefault(label_id, []).append(product_id)

        insert_sql = (
            "INSERT INTO onsides_effects_raw "
            "(product_label_id, source_region, source_product_id, source_label_url, "
            "rxnorm_product_id, rxnorm_ingredient_id, rxnorm_ingredient_name, "
            "effect_meddra_id, effect, label_section, match_method, pred0, pred1) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"
        )
        buffer: list[tuple] = []
        rows = 0
        mapped_rows = 0
        with z.open("csv/product_adverse_effect.csv") as f:
            reader = csv.DictReader(line.decode("utf-8", errors="replace") for line in f)
            for item in reader:
                rows += 1
                label_id = (item.get("product_label_id") or "").strip()
                effect_id = (item.get("effect_meddra_id") or "").strip()
                if not label_id or not effect_id:
                    continue
                region, source_product_id, source_url = labels.get(
                    label_id, ("UNKNOWN", None, None)
                )
                product_ids = label_products.get(label_id) or [None]
                ingredient_pairs = [
                    (product_id, ingredient_id)
                    for product_id in product_ids
                    for ingredient_id in product_to_ingredients.get(product_id, [])
                ] or [(product_ids[0], None)]
                try:
                    pred0 = float(item["pred0"]) if item.get("pred0") else None
                except ValueError:
                    pred0 = None
                try:
                    pred1 = float(item["pred1"]) if item.get("pred1") else None
                except ValueError:
                    pred1 = None
                for product_id, ingredient_id in ingredient_pairs:
                    if ingredient_id:
                        mapped_rows += 1
                    buffer.append(
                        (
                            label_id,
                            region,
                            source_product_id,
                            source_url,
                            product_id,
                            ingredient_id,
                            ingredient_names.get(ingredient_id) if ingredient_id else None,
                            effect_id,
                            effects.get(effect_id, f"MedDRA {effect_id}"),
                            (item.get("label_section") or "").strip() or None,
                            (item.get("match_method") or "").strip() or None,
                            pred0,
                            pred1,
                        )
                    )
                if limit and rows >= limit:
                    break
                if len(buffer) >= 5000:
                    conn.executemany(insert_sql, buffer)
                    buffer.clear()
        if buffer:
            conn.executemany(insert_sql, buffer)
        deduplicate_table(
            conn,
            "onsides_effects_raw",
            ONSIDES_RAW_COLUMNS,
            surrogate_column="row_id",
        )
        conn.execute(
            "INSERT INTO onsides_ingredient_effects "
            "(rxnorm_ingredient_id, rxnorm_ingredient_name, effect_meddra_id, effect, "
            "source_region, row_count, label_count, min_pred1, max_pred1, high_confidence) "
            "SELECT r.rxnorm_ingredient_id, MIN(r.rxnorm_ingredient_name), r.effect_meddra_id, "
            "MIN(r.effect), r.source_region, COUNT(*), COUNT(DISTINCT r.product_label_id), "
            "MIN(r.pred1), MAX(r.pred1), "
            "MAX(CASE WHEN h.rxnorm_ingredient_id IS NOT NULL THEN 1 ELSE 0 END) "
            "FROM onsides_effects_raw r LEFT JOIN onsides_high_confidence h "
            "ON h.rxnorm_ingredient_id = r.rxnorm_ingredient_id "
            "AND h.effect_meddra_id = r.effect_meddra_id "
            "WHERE r.rxnorm_ingredient_id IS NOT NULL "
            "GROUP BY r.rxnorm_ingredient_id, r.effect_meddra_id, r.source_region"
        )
    conn.commit()
    conn.executescript(
        "CREATE INDEX IF NOT EXISTS idx_onsides_raw_ingredient "
        "ON onsides_effects_raw(rxnorm_ingredient_id, effect_meddra_id);"
        "CREATE INDEX IF NOT EXISTS idx_onsides_raw_region "
        "ON onsides_effects_raw(source_region);"
        "CREATE INDEX IF NOT EXISTS idx_onsides_ingredient_effect "
        "ON onsides_ingredient_effects(rxnorm_ingredient_id, effect);"
    )
    aggregate_rows = conn.execute(
        "SELECT COUNT(*) FROM onsides_ingredient_effects"
    ).fetchone()[0]
    return {
        "rows": rows,
        "mapped_rows": mapped_rows,
        "raw_rows": conn.execute("SELECT COUNT(*) FROM onsides_effects_raw").fetchone()[0],
        "ingredient_effects": aggregate_rows,
        "status": "ok",
    }


def refresh_high_confidence(
    conn: sqlite3.Connection,
    zip_path: Path = DATA_DIR / "onsides" / "onsides-v3.1.1.zip",
) -> dict:
    """Refresh the release-supplied ingredient/effect high-confidence flags."""
    conn.executescript(FULL_SCHEMA)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(onsides_ingredient_effects)")}
    if "high_confidence" not in columns:
        conn.execute(
            "ALTER TABLE onsides_ingredient_effects ADD COLUMN "
            "high_confidence INTEGER NOT NULL DEFAULT 0"
        )
    pairs = set()
    with zipfile.ZipFile(zip_path) as z, z.open("csv/high_confidence.csv") as f:
        for row in csv.DictReader(line.decode("utf-8", errors="replace") for line in f):
            ingredient_id = (row.get("ingredient_id") or "").strip()
            effect_id = (row.get("effect_meddra_id") or "").strip()
            if ingredient_id and effect_id:
                pairs.add((ingredient_id, effect_id))
    conn.execute("DELETE FROM onsides_high_confidence")
    conn.executemany(
        "INSERT OR IGNORE INTO onsides_high_confidence "
        "(rxnorm_ingredient_id, effect_meddra_id) VALUES (?,?)",
        pairs,
    )
    conn.execute(
        "UPDATE onsides_ingredient_effects SET high_confidence = CASE WHEN EXISTS ("
        "SELECT 1 FROM onsides_high_confidence h "
        "WHERE h.rxnorm_ingredient_id = onsides_ingredient_effects.rxnorm_ingredient_id "
        "AND h.effect_meddra_id = onsides_ingredient_effects.effect_meddra_id"
        ") THEN 1 ELSE 0 END"
    )
    conn.commit()
    return {
        "high_confidence_pairs": len(pairs),
        "flagged_aggregates": conn.execute(
            "SELECT COUNT(*) FROM onsides_ingredient_effects WHERE high_confidence = 1"
        ).fetchone()[0],
        "status": "ok",
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("zip_path", nargs="?", default=str(ZIP_PATH))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument(
        "--full",
        action="store_true",
        help="import every raw release row and build ingredient-effect aggregates",
    )
    ap.add_argument(
        "--refresh-high-confidence",
        action="store_true",
        help="refresh release-supplied high-confidence intersection flags",
    )
    args = ap.parse_args()
    from .db import DB_PATH

    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    try:
        if args.refresh_high_confidence:
            print(refresh_high_confidence(conn, Path(args.zip_path)))
        elif args.full:
            print(import_full(conn, Path(args.zip_path), args.limit))
        else:
            print(import_all(conn, Path(args.zip_path), args.limit))
    finally:
        conn.close()

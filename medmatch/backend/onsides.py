"""Import OnSIDES drug side effects (CC BY 4.0) for our class member drugs.

Streams product_adverse_effect.csv (399MB), keeps rows whose product label
matches one of our class member drug names, filters to PubMedBERT-method
rows with pred0 >= 0.6, aggregates the most frequent MedDRA effects per
drug class. License: CC BY 4.0 (attribution) — commercial OK.

Usage:
    python -m backend.onsides [zip_path] [--limit N]
"""
import csv
import json
import sqlite3
import zipfile
from collections import Counter
from pathlib import Path

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


if __name__ == "__main__":
    from .db import DB_PATH

    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    try:
        print(import_all(conn))
    finally:
        conn.close()

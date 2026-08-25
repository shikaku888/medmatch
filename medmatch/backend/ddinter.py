"""Import DDInter 2.0 drug-drug interactions (240K pairs, CC BY-NC-SA).

License note: CC BY-NC-SA = non-commercial. The project plan authorizes MVP
use; rows carry license='CC BY-NC-SA' so they can be stripped for a
commercial release with one DELETE. Drug names map to our 58 classes by
normalized name matching; pairs with both sides mapped land in
ddinter_interactions.

Usage:
    python -m backend.ddinter
"""
import csv
import json
import sqlite3
from pathlib import Path

from .engine import normalize

DATA_DIR = Path(__file__).parent / "data"
DDINTER_DIR = Path(r"C:/tmp")  # downloads land here; adjust if stored elsewhere

SEVERITY_MAP = {"Major": "major", "Moderate": "moderate", "Minor": "minor"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS ddinter_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cls_a TEXT,
    cls_b TEXT,
    drug_a TEXT NOT NULL,
    drug_b TEXT NOT NULL,
    severity TEXT NOT NULL,
    pair_key TEXT NOT NULL,
    trust REAL NOT NULL DEFAULT 0.9,
    license TEXT NOT NULL DEFAULT 'CC BY-NC-SA',
    source TEXT NOT NULL DEFAULT 'DDInter 2.0'
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ddi_pair ON ddinter_interactions(pair_key);
"""


def _load_class_index() -> dict[str, str]:
    classes = json.loads((DATA_DIR / "drug_classes.json").read_text(encoding="utf-8"))
    drug_names = json.loads((DATA_DIR / "drug_names_en.json").read_text(encoding="utf-8"))
    idx: dict[str, str] = {}
    for c in classes:
        for n in [c["name"], *(c.get("aliases") or [])]:
            idx.setdefault(normalize(n), c["id"])
        for d in c["drugs"]:
            idx.setdefault(normalize(drug_names.get(d.lower(), d)), c["id"])
    return idx


def import_all(conn: sqlite3.Connection, dir_path: Path = DDINTER_DIR) -> dict:
    conn.executescript(SCHEMA)
    cls_index = _load_class_index()
    stats = {"rows": 0, "both_mapped": 0, "unique_pairs": 0}
    seen_pairs = set()
    for code in "ABDHLPRV":
        path = dir_path / f"ddinter_{code}.csv"
        if not path.exists():
            print(f"SKIP missing {path}")
            continue
        with open(path, encoding="utf-8", errors="replace") as fh:
            for row in csv.DictReader(fh):
                stats["rows"] += 1
                drug_a = (row.get("Drug_A") or "").strip()
                drug_b = (row.get("Drug_B") or "").strip()
                sev = SEVERITY_MAP.get(row.get("Level"), "moderate")
                cls_a = cls_index.get(normalize(drug_a))
                cls_b = cls_index.get(normalize(drug_b))
                if not cls_a or not cls_b:
                    continue
                stats["both_mapped"] += 1
                a, b = sorted((cls_a, cls_b))
                key = f"ddi:{a}|{b}"
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                stats["unique_pairs"] += 1
                conn.execute(
                    "INSERT OR IGNORE INTO ddinter_interactions"
                    " (cls_a, cls_b, drug_a, drug_b, severity, pair_key)"
                    " VALUES (?,?,?,?,?,?)",
                    (cls_a, cls_b, drug_a, drug_b, sev, key),
                )
    conn.commit()
    return stats


if __name__ == "__main__":
    from .db import DB_PATH

    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    try:
        print(import_all(conn))
        n = conn.execute("SELECT COUNT(*) FROM ddinter_interactions").fetchone()[0]
        print(f"total ddinter rows: {n}")
    finally:
        conn.close()

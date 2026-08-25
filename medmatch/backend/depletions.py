"""Import medication-depletion evidence (MIT, verified-supplement-evidence).

The "killer feature": drug classes that deplete nutrients, with severity,
effect size, mechanism and PMIDs. Medication groups map to our classes:
statin -> estatinas, ssri -> isrs, ppi -> omeprazol, metformin ->
antidiabeticos, birth-control -> anticonceptivos. Combination rows
(e.g. statin+ppi) fire only when both classes are present.

Usage:
    python -m backend.depletions
"""
import csv
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
SRC_DIR = DATA_DIR / "verified_supp"

# medication_id -> our class id(s); combos are "+"-joined
MED_TO_CLASS = {
    "statin": ("estatinas",),
    "ssri": ("isrs",),
    "ppi": ("omeprazol",),
    "metformin": ("antidiabeticos",),
    "birth-control": ("anticonceptivos",),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS depletions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cls_a TEXT NOT NULL,
    cls_b TEXT,
    ingredient TEXT NOT NULL,
    severity TEXT NOT NULL,
    effect_size TEXT,
    mechanism TEXT,
    pmids TEXT,
    us_users_millions TEXT,
    source TEXT NOT NULL DEFAULT 'Verified Supplement Evidence (MIT)',
    pair_key TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_dep_key ON depletions(pair_key);
"""


def import_depletions(conn: sqlite3.Connection) -> int:
    conn.executescript(SCHEMA)
    conn.execute("DELETE FROM depletions")
    n = 0
    with open(SRC_DIR / "medication-depletion-v1.csv", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            med_id = (row.get("medication_id") or "").strip()
            parts = med_id.split("+")
            classes = []
            ok = True
            for p in parts:
                if p not in MED_TO_CLASS:
                    ok = False
                    break
                classes.extend(MED_TO_CLASS[p])
            if not ok:
                continue
            cls_a, cls_b = (classes[0], classes[1]) if len(classes) > 1 else (classes[0], None)
            ingredient = (row.get("ingredient_depleted") or "").strip()
            severity = {"high": "major", "moderate": "moderate", "low": "minor"}.get(
                (row.get("severity") or "").lower(), "moderate")
            pair_key = f"{cls_a}+{cls_b or '-'}|{ingredient}"
            conn.execute(
                "INSERT OR IGNORE INTO depletions"
                " (cls_a, cls_b, ingredient, severity, effect_size, mechanism, pmids, us_users_millions, pair_key)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (cls_a, cls_b, ingredient, severity, row.get("effect_size"),
                 row.get("mechanism"), row.get("pmids"), row.get("us_users_millions"),
                 pair_key),
            )
            n += 1
    conn.commit()
    return n


if __name__ == "__main__":
    from .db import DB_PATH

    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    try:
        print(f"imported {import_depletions(conn)} depletion rows")
    finally:
        conn.close()

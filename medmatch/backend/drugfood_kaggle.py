"""Import Kaggle drug-food interactions dataset (shayanhusain, 1,423 drugs).

Source data is DrugBank 6.0 derived (CC BY-NC) — rows carry a license flag
for commercial-release stripping. Drug names map to our classes; free-text
advice strings are matched against food keywords to assign one of our 10
food entities. Severity is inferred from the advice language.

Usage:
    python -m backend.drugfood_kaggle [path/to/json]
"""
import json
import re
import sqlite3
from pathlib import Path

from .engine import normalize

DATA_DIR = Path(__file__).parent / "data"
SRC_JSON = Path(r"C:/tmp") / "drugfood.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS drugfood_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cls_a TEXT NOT NULL,
    food_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    effect TEXT,
    source TEXT,
    pair_key TEXT NOT NULL,
    trust REAL NOT NULL DEFAULT 0.8,
    license TEXT NOT NULL DEFAULT 'CC BY-NC (DrugBank)'
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_dfe_pair ON drugfood_evidence(pair_key);
"""

# food keyword -> our food id (ordered: check more specific first)
FOOD_KEYWORDS = [
    ("grapefruit", ["grapefruit"]),
    ("alcohol", ["alcohol", "ethanol", " wine", "beer"]),
    ("vitamin_k_foods", ["vitamin k", "leafy green", "kale", "spinach", "broccoli", "brussels"]),
    ("dairy", ["milk", "dairy", "calcium", "cheese", "yogurt"]),
    ("caffeine", ["caffeine", "coffee", " tea"]),
    ("tyramine_foods", ["tyramine", "aged cheese", "fermented", "cured meat"]),
    ("potassium_foods", ["potassium", "banana", "salt substitute"]),
    ("licorice", ["licorice", "liquorice"]),
    ("high_fiber", ["fiber", "bran", "psyllium", "whole grain"]),
    ("charred_meat", ["charred", "grilled meat", "barbecue"]),
]

_SEV_MAJOR = re.compile(r"avoid|contraindicat|should not|do not|must not", re.I)
_SEV_MINOR = re.compile(r"generally safe|may be taken|no significant", re.I)


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


def _foods_in(text: str) -> list[str]:
    low = text.lower()
    return [fid for fid, kws in FOOD_KEYWORDS if any(k in low for k in kws)]


def _severity(text: str) -> str:
    if _SEV_MAJOR.search(text):
        return "major"
    if _SEV_MINOR.search(text):
        return "minor"
    return "moderate"


def import_all(conn: sqlite3.Connection, src: Path = SRC_JSON) -> dict:
    conn.executescript(SCHEMA)
    conn.execute("DELETE FROM drugfood_evidence")
    cls_index = _load_class_index()
    items = json.loads(src.read_text(encoding="utf-8"))
    stats = {"drugs": 0, "mapped": 0, "rows": 0, "unmapped_food": 0}
    merged: dict[str, list[str]] = {}
    for item in items:
        stats["drugs"] += 1
        drug = (item.get("name") or "").strip()
        cls_id = cls_index.get(normalize(drug))
        if not cls_id:
            continue
        stats["mapped"] += 1
        for advice in item.get("food_interactions") or []:
            for fid in _foods_in(advice):
                key = f"{cls_id}|{fid}"
                merged.setdefault(key, []).append(advice.strip())
    for key, advices in merged.items():
        cls_id, fid = key.split("|")
        text = " | ".join(dict.fromkeys(advices))[:600]
        sev = _severity(text)
        conn.execute(
            "INSERT INTO drugfood_evidence"
            " (cls_a, food_id, severity, effect, source, pair_key)"
            " VALUES (?,?,?,?,?,?)",
            (cls_id, fid, sev, text, "DrugBank 6.0 via Kaggle (shayanhusain)", f"dfe:{key}"),
        )
        stats["rows"] += 1
    conn.commit()
    return stats


if __name__ == "__main__":
    from .db import DB_PATH

    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    try:
        print(import_all(conn))
    finally:
        conn.close()

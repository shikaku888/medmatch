"""iDISK 2.0 importer: dietary supplement knowledgebase (academic KG, free).

Sources (Google Drive, see Data/README.md in houyurain/iDISK2.0):
- dsi_d.csv: 535 supplement-drug interaction pairs (MSKCC + Natural Medicines),
  with free-text Source_Description.
- DSI.csv: 7,876 supplement ingredients with Background/Safety/Mechanism text.

Mapping:
- DSI -> our herbs: UMLS CUI join (herbs already resolved via SUPP.AI) plus
  normalized name matching on DSI names (Name, Common Names, DSLD_Name,
  MSKCC_Name, NHP_Name) against herb name_en/scientific/aliases.
- D (drugs) -> our drug_classes: exact class name/alias match, member match,
  and first-segment match of MSKCC_Name.

Rows land in `idisk_interactions` (trust=0.7, plan3 tier: academic KG) and
`idisk_dsi` (herb enrichment: background/safety/mechanism). Re-runs are
idempotent via UNIQUE(pair_key) / PRIMARY KEY.

Usage:
    python -m backend.idisk
"""
import csv
import json
import sqlite3
from pathlib import Path

from .engine import normalize

DATA_DIR = Path(__file__).parent / "data"
IDISK_DIR = DATA_DIR / "idisk"

TRUST_IDISK = 0.7  # plan3: academic KG tier

SCHEMA = """
CREATE TABLE IF NOT EXISTS idisk_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    herb_id TEXT NOT NULL,
    class_id TEXT NOT NULL,
    dsi_id TEXT NOT NULL,
    d_id TEXT NOT NULL,
    rating TEXT,
    description TEXT,
    source TEXT,
    pair_key TEXT NOT NULL,
    trust REAL NOT NULL DEFAULT 0.7
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_idisk_pair ON idisk_interactions(pair_key);
CREATE TABLE IF NOT EXISTS idisk_dsi (
    dsi_id TEXT PRIMARY KEY,
    herb_id TEXT,
    name TEXT NOT NULL,
    cui TEXT,
    background TEXT,
    safety TEXT,
    mechanism TEXT,
    source_material TEXT
);
"""


def _rows(name: str) -> list[dict]:
    with open(IDISK_DIR / name, encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _load_herbs() -> tuple[list[dict], dict[str, str]]:
    """Return (herbs, normalized-name -> herb_id index)."""
    herbs = json.loads((DATA_DIR / "herbs.json").read_text(encoding="utf-8"))
    idx: dict[str, str] = {}
    for h in herbs:
        for n in [h["name"], h.get("scientific"), *h.get("aliases", [])]:
            if n:
                idx.setdefault(normalize(n), h["id"])
    return herbs, idx


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


def _match_herb_by_name(name_fields: list[str], herb_idx: dict[str, str]) -> str | None:
    for raw in name_fields:
        n = normalize(raw)
        if n in herb_idx:
            return herb_idx[n]
    # token-overlap fallback: query tokens subset of index name tokens
    q = " ".join(normalize(x) for x in name_fields)
    qt = set(q.replace("-", " ").split())
    for idx_name, hid in herb_idx.items():
        it = set(idx_name.replace("-", " ").split())
        if it and (it <= qt or (qt <= it and len(qt) >= 2)):
            return hid
    return None


def _match_class_by_name(name_fields: list[str], cls_idx: dict[str, str]) -> str | None:
    for raw in name_fields:
        n = normalize(raw)
        if n in cls_idx:
            return cls_idx[n]
        # first pipe-segment of MSKCC fields, e.g. "Linezolid (Zyvox...)" | ...
        if "|" in raw:
            first = normalize(raw.split("|")[0])
            if first in cls_idx:
                return cls_idx[first]
        # first parenthesized-prefix, e.g. "Antidepressants/anxiolytics (tricyclics...)"
        base = normalize(raw.split("(")[0].split("/")[0])
        if base in cls_idx:
            return cls_idx[base]
    return None


def import_interactions(conn: sqlite3.Connection) -> dict:
    dsi = {r["iDISK_ID"]: r for r in _rows("DSI.csv")}
    drugs = {r["iDISK_ID"]: r for r in _rows("D.csv")}
    _, herb_idx = _load_herbs()
    cls_idx = _load_class_index()
    # CUI join: herbs resolved by SUPP.AI (supp_cui -> herb_id)
    cui_to_herb = {}
    for herb_id, cui in conn.execute("SELECT DISTINCT herb_id, supp_cui FROM suppai_interactions"):
        cui_to_herb[cui] = herb_id

    stats = {"rows": 0, "herb": 0, "class": 0, "both": 0}
    for r in _rows("dsi_d.csv"):
        stats["rows"] += 1
        d = dsi.get(r["DSI"])
        if not d:
            continue
        herb_id = cui_to_herb.get(d["CUI"]) or _match_herb_by_name(
            [d["Name"], d.get("Common Names", ""), d.get("DSLD_Name", ""),
             d.get("MSKCC_Name", ""), d.get("NHP_Name", "")], herb_idx)
        if not herb_id:
            continue
        stats["herb"] += 1
        dr = drugs.get(r["D"], {})
        class_id = _match_class_by_name(
            [dr.get("Name", ""), dr.get("MSKCC_Name", "")], cls_idx)
        if not class_id:
            continue
        stats["class"] += 1
        stats["both"] += 1
        conn.execute(
            "INSERT OR IGNORE INTO idisk_interactions"
            " (herb_id, class_id, dsi_id, d_id, rating, description, source, pair_key, trust)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (herb_id, class_id, r["DSI"], r["D"], r.get("Interaction Rating"),
             r.get("Source_Description"), r.get("Source"),
             f"idisk:{herb_id}|{class_id}|{r['DSI']}", TRUST_IDISK),
        )
    conn.commit()
    return stats


def import_dsi(conn: sqlite3.Connection) -> dict:
    _, herb_idx = _load_herbs()
    stats = {"rows": 0, "mapped": 0}
    for r in _rows("DSI.csv"):
        stats["rows"] += 1
        herb_id = _match_herb_by_name(
            [r["Name"], r.get("Common Names", ""), r.get("DSLD_Name", ""),
             r.get("MSKCC_Name", ""), r.get("NHP_Name", "")], herb_idx)
        conn.execute(
            "INSERT OR REPLACE INTO idisk_dsi"
            " (dsi_id, herb_id, name, cui, background, safety, mechanism, source_material)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (r["iDISK_ID"], herb_id, r["Name"], r.get("CUI"), r.get("Background"),
             r.get("Safety"), r.get("Mechanism of action"), r.get("Source Material")),
        )
        if herb_id:
            stats["mapped"] += 1
    conn.commit()
    return stats


if __name__ == "__main__":
    from .db import DB_PATH

    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    try:
        conn.executescript(SCHEMA)
        print("interactions:", import_interactions(conn))
        print("dsi:", import_dsi(conn))
        total = conn.execute("SELECT COUNT(*) FROM idisk_interactions").fetchone()[0]
        print(f"total idisk_interactions rows: {total}")
    finally:
        conn.close()

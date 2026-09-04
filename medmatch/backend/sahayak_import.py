"""SAHAYAK (MIT) data importer — nâng QT/Beers/Electrolyte từ hardcoded sang data-driven.

Nguồn: backend/data/sahayak/{cyp450_data,beers_criteria,herb_cyp_interactions}.json
(MIT license — github.com/mohanganesh3/Sahayak)

Usage: python -m backend.sahayak_import
"""
import json
import sqlite3
from pathlib import Path

from .db import DB_PATH

DATA = Path(__file__).parent / "data" / "sahayak"


def run() -> dict:
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS qt_drugs (
        name TEXT PRIMARY KEY, risk_level TEXT);
    CREATE TABLE IF NOT EXISTS electrolyte_effects (
        drug TEXT PRIMARY KEY, category TEXT);
    CREATE TABLE IF NOT EXISTS beers_drugs (
        drug_name TEXT, table_src TEXT, organ_system TEXT,
        category TEXT, rationale TEXT);
    CREATE INDEX IF NOT EXISTS idx_beers_drug ON beers_drugs(drug_name);
    """)

    stats = {}

    # --- 1. QT prolonging drugs ------------------------------------------------
    qt = json.loads((DATA / "cyp450_data.json").read_text(encoding="utf-8")).get("qt_prolonging_drugs") or {}
    n = 0
    for level, names in qt.items():
        for name in names or []:
            conn.execute("INSERT OR REPLACE INTO qt_drugs VALUES (?,?)", (name.lower().strip(), level))
            n += 1
    stats["qt_drugs"] = n

    # --- 2. Electrolyte effects -------------------------------------------------
    el = json.loads((DATA / "cyp450_data.json").read_text(encoding="utf-8")).get("electrolyte_effects") or {}
    n = 0
    for category, names in el.items():
        for name in names or []:
            conn.execute("INSERT OR REPLACE INTO electrolyte_effects VALUES (?,?)", (name.lower().strip(), category))
            n += 1
    stats["electrolyte_effects"] = n

    # --- 3. Beers 2023 (explode drug_names lists) --------------------------------
    beers = json.loads((DATA / "beers_criteria.json").read_text(encoding="utf-8"))
    level_map = {
        "table2_avoid_in_older_adults": "avoid",
        "table3_drug_disease_interactions": "avoid-disease",
        "table4_use_with_caution": "caution",
    }
    n = 0
    for src, level in level_map.items():
        for entry in beers.get(src) or []:
            organ = entry.get("organ_system") or ""
            category = entry.get("therapeutic_category") or entry.get("drug_or_class") or ""
            rationale = (entry.get("rationale") or "").strip()
            names = entry.get("drug_names") or []
            if not names and entry.get("drug_or_class"):
                names = [str(entry["drug_or_class"])]
            for name in names:
                nm = name.lower().strip()
                if len(nm) < 3:
                    continue
                conn.execute(
                    "INSERT INTO beers_drugs VALUES (?,?,?,?,?)",
                    (nm, src, organ, category, rationale[:500]),
                )
                n += 1
    stats["beers_rows"] = n

    # --- 4. Herb → CYP roles (name-based, conservative: strong/substrate only) ----
    herbs = json.loads((DATA / "herb_cyp_interactions.json").read_text(encoding="utf-8")).get("herbs") or []
    n = 0
    for h in herbs:
        aliases = {h.get("name", "").lower().strip()}
        aliases |= {a.lower().strip() for a in h.get("aliases") or [] if a.strip()}
        aliases.discard("")
        for inter in h.get("interactions") or []:
            target = (inter.get("target_name") or "").upper().replace("CYP", "").strip()
            rel = (inter.get("relationship") or "").upper()
            strength = (inter.get("strength") or "").lower()
            role = {"INHIBITS": "inhibitor", "INDUCES": "inducer", "SUBSTRATE": "substrate"}.get(rel)
            if not role or not target:
                continue
            if role == "inhibitor" and strength not in ("strong",):
                continue  # conservative: chỉ inhibitor mạnh mới sinh cảnh báo
            for alias in aliases:
                conn.execute(
                    "INSERT OR REPLACE INTO cyp_roles VALUES ('herb_name', ?, ?, ?)",
                    (alias, role, target),
                )
                n += 1
    stats["herb_cyp_roles"] = n

    conn.commit()

    probe = {
        "qt_digoxin": conn.execute("SELECT risk_level FROM qt_drugs WHERE name='digoxin'").fetchone(),
        "beers_diazepam": conn.execute("SELECT COUNT(*) FROM beers_drugs WHERE drug_name='diazepam'").fetchone()[0],
        "el_furosemide": conn.execute("SELECT category FROM electrolyte_effects WHERE drug='furosemide'").fetchone(),
    }
    conn.close()
    out = {**stats, "probe": {k: (v[0] if isinstance(v, sqlite3.Row) else v) for k, v in probe.items()}}
    print(out)
    return out


if __name__ == "__main__":
    run()

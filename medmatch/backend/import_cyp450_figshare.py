"""Import positive CYP450 substrate labels from the CC BY 4.0 Figshare set."""
from __future__ import annotations

import csv
import re
import sqlite3
import unicodedata
from pathlib import Path

from .db import DB_PATH

DATA_DIR = Path(__file__).parent / "data"
FILES = {
    "1A2": "cyp450_figshare.csv",
    "2C9": "cyp450_figshare_2c9.csv",
    "2C19": "cyp450_figshare_2c19.csv",
    "2D6": "cyp450_figshare_2d6.csv",
    "3A4": "cyp450_figshare_3a4.csv",
    "2E1": "cyp450_figshare_2e1.csv",
}


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 -]", "", value.lower())).strip()


def import_positives(conn: sqlite3.Connection) -> dict:
    index: dict[str, str] = {}
    import json
    for cid, name, drugs, aliases in conn.execute("SELECT id, name_en, drugs, aliases FROM drug_classes"):
        for value in [name, cid, *json.loads(drugs or "[]"), *json.loads(aliases or "[]")]:
            if value:
                index.setdefault(norm(value), cid)

    stats = {"files": 0, "positive_rows": 0, "mapped_rows": 0, "mapped_names": set()}
    for enzyme, filename in FILES.items():
        path = DATA_DIR / filename
        if not path.exists():
            raise FileNotFoundError(path)
        stats["files"] += 1
        with path.open(newline="", encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                if str(row.get("Label", "")).strip() != "1":
                    continue
                stats["positive_rows"] += 1
                cid = index.get(norm(row.get("Name", "")))
                if not cid:
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO cyp_roles"
                    " (entity_type, entity_id, role, enzyme) VALUES (?,?,?,?)",
                    ("drug_class", cid, "substrate", enzyme),
                )
                stats["mapped_rows"] += 1
                stats["mapped_names"].add(row["Name"].strip().lower())
    conn.commit()
    stats["mapped_names"] = len(stats["mapped_names"])
    return stats


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    try:
        print(import_positives(conn))
    finally:
        conn.close()

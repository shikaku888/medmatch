"""Import the CC BY 4.0 Zenodo FDA DailyMed DDI compilation.

Usage:
    python -m backend.import_zenodo_ddi
"""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from .db import DB_PATH

DATA_PATH = Path(__file__).parent / "data" / "zenodo_ddi_2026.csv"
SOURCE_URL = "https://doi.org/10.5281/zenodo.19685458"

SCHEMA = """
CREATE TABLE IF NOT EXISTS zenodo_ddi_2026 (
    drug_a TEXT NOT NULL,
    drug_b TEXT NOT NULL,
    interaction TEXT NOT NULL,
    source TEXT NOT NULL,
    PRIMARY KEY (drug_a, drug_b, interaction)
);
CREATE INDEX IF NOT EXISTS idx_zenodo_ddi_2026_a ON zenodo_ddi_2026(drug_a);
CREATE INDEX IF NOT EXISTS idx_zenodo_ddi_2026_b ON zenodo_ddi_2026(drug_b);
"""


def import_rows(conn: sqlite3.Connection) -> int:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Missing dataset: {DATA_PATH}")
    conn.executescript(SCHEMA)
    conn.execute("DELETE FROM zenodo_ddi_2026")
    rows = []
    with DATA_PATH.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        expected = {"drug 1", "drug 2", "interaction"}
        if set(reader.fieldnames or ()) != expected:
            raise ValueError(f"Unexpected columns: {reader.fieldnames}")
        for row in reader:
            a = (row["drug 1"] or "").strip()
            b = (row["drug 2"] or "").strip()
            effect = (row["interaction"] or "").strip()
            if a and b and effect:
                rows.append((a, b, effect, SOURCE_URL))
    conn.executemany(
        "INSERT OR IGNORE INTO zenodo_ddi_2026"
        " (drug_a, drug_b, interaction, source) VALUES (?,?,?,?)",
        rows,
    )
    conn.commit()
    return conn.execute("SELECT COUNT(*) FROM zenodo_ddi_2026").fetchone()[0]


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    try:
        print(f"imported {import_rows(conn)} Zenodo DDI rows")
    finally:
        conn.close()

"""iDISK product layer: 163K supplement products + 317K ingredient links (local).

Products (DSP.csv) are searchable by name; each product links to its
ingredients (dsp_dsi.csv + DSI.csv names). The API resolves ingredient names
to our herb index so a product can be added to the cabinet as its herbs.

Usage:
    python -m backend.idisk_products
"""
import csv
import json
import sqlite3
from pathlib import Path

from .engine import normalize

DATA_DIR = Path(__file__).parent / "data"
IDISK_DIR = DATA_DIR / "idisk"

SCHEMA = """
CREATE TABLE IF NOT EXISTS idisk_products (
    dsp_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    company TEXT
);
CREATE INDEX IF NOT EXISTS idx_ip_name ON idisk_products(name);
CREATE TABLE IF NOT EXISTS idisk_product_ingredients (
    dsp_id TEXT NOT NULL,
    dsi_name TEXT NOT NULL,
    PRIMARY KEY (dsp_id, dsi_name)
);
CREATE INDEX IF NOT EXISTS idx_ipi_dsp ON idisk_product_ingredients(dsp_id);
"""


def _rows(name: str) -> list[dict]:
    with open(IDISK_DIR / name, encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def import_products(conn: sqlite3.Connection, max_products: int | None = None) -> dict:
    conn.executescript(SCHEMA)
    # wipe product tables only (re-import is idempotent but keep it clean)
    conn.execute("DELETE FROM idisk_product_ingredients")
    conn.execute("DELETE FROM idisk_products")

    dsi_names = {r["iDISK_ID"]: r["Name"] for r in _rows("DSI.csv")}
    stats = {"products": 0, "links": 0}
    for r in _rows("DSP.csv"):
        if r.get("Status") != "Active":
            continue
        stats["products"] += 1
        conn.execute(
            "INSERT INTO idisk_products (dsp_id, name, company) VALUES (?,?,?)",
            (r["iDISK_ID"], r["Name"].strip(), r.get("Company_Name") or ""),
        )
        if max_products and stats["products"] >= max_products:
            break

    for r in _rows("dsp_dsi.csv"):
        name = dsi_names.get(r["DSI"])
        if not name:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO idisk_product_ingredients (dsp_id, dsi_name) VALUES (?,?)",
            (r["DSP"], name),
        )
        stats["links"] += 1
    conn.commit()
    return stats


def search_products(conn: sqlite3.Connection, q: str, limit: int = 10) -> list[dict]:
    like = f"%{q}%"
    rows = conn.execute(
        "SELECT dsp_id, name, company FROM idisk_products"
        " WHERE name LIKE ? COLLATE NOCASE ORDER BY name LIMIT ?",
        (like, limit),
    ).fetchall()
    return [{"dsp_id": r["dsp_id"], "name": r["name"], "company": r["company"]} for r in rows]


def product_ingredients(conn: sqlite3.Connection, dsp_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT dsi_name FROM idisk_product_ingredients WHERE dsp_id = ?", (dsp_id,)
    ).fetchall()
    return [r["dsi_name"] for r in rows]


if __name__ == "__main__":
    from .db import DB_PATH

    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    try:
        stats = import_products(conn)
        n = conn.execute("SELECT COUNT(*) FROM idisk_products").fetchone()[0]
        print(f"{stats} total_products={n}")
    finally:
        conn.close()

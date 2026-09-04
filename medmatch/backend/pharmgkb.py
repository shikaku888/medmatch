"""PharmGKB / ClinPGx import (CC BY-SA 4.0).

PharmGKB chuyển thành ClinPGx: downloads phục vụ tại
https://api.clinpgx.org/v1/download/file/data/<file>.zip (redirect → S3, không
cần auth). Dữ liệu tái phân phối theo Creative Commons Attribution-ShareAlike
4.0 — ghi attribution khi hiển thị.

Harvest:
- pharmgkb_drugs: drugs.tsv -> name, generic/trade/brand tên + RxNorm/ATC/
  PubChem id. Đây là input chính cho build_synonyms (OCR normalize tên thương
  mại -> class) và build_standards (ATC/PubChem external id).
- pharmgkb_relations: relationships.tsv -> tập PGx (gene/chemical/disease) với
  evidence + association + PMIDs, dự trữ cho lớp annotation lâm sàng.

Usage:
    python -m backend.crawler.run pharmgkb
"""
import csv
import datetime as _dt
import json
import re
import sqlite3
import urllib.request
import zipfile
from pathlib import Path

from .db import DATA_DIR
from .license_registry import register_release, sha256_of

csv.field_size_limit(10_000_000)

PGKB_BASE = "https://api.clinpgx.org/v1/download/file/data"
SOURCE = "PharmGKB (ClinPGx)"

LRU_DIR = DATA_DIR / "pharmgkb"
DRUGS_ZIP = LRU_DIR / "drugs.zip"
RELS_ZIP = LRU_DIR / "relationships.zip"
DRUGS_TSV = LRU_DIR / "drugs.tsv"
RELS_TSV = LRU_DIR / "relationships.tsv"

SCHEMA = """
CREATE TABLE IF NOT EXISTS pharmgkb_drugs (
    accession TEXT PRIMARY KEY,
    name TEXT,
    generic_names TEXT,
    trade_names TEXT,
    brand_mixtures TEXT,
    type TEXT,
    cross_refs TEXT,
    rxnorm TEXT,
    atc TEXT,
    pubchem TEXT,
    dosing_guideline INTEGER NOT NULL DEFAULT 0,
    downloaded_at TEXT
);
CREATE TABLE IF NOT EXISTS pharmgkb_relations (
    ent1_id TEXT, ent1_name TEXT, ent1_type TEXT,
    ent2_id TEXT, ent2_name TEXT, ent2_type TEXT,
    evidence TEXT, association TEXT, pk TEXT, pd TEXT, pmids TEXT,
    row_ord INTEGER
);
CREATE INDEX IF NOT EXISTS idx_pgkb_drug_name ON pharmgkb_drugs(name);
CREATE INDEX IF NOT EXISTS idx_pgkb_rxnorm ON pharmgkb_drugs(rxnorm);
"""

UA = "MedMatch/1.0 (research; CC BY-SA 4.0 data attribution)"


def _fetch(url: str, dest: Path):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        dest.write_bytes(r.read())
    return dest


def download(force: bool = False) -> tuple[Path, Path]:
    """Download + unpack zip caches về data/pharmgkb/. Idempotent."""
    LRU_DIR.mkdir(parents=True, exist_ok=True)
    if force or not DRUGS_ZIP.exists():
        _fetch(f"{PGKB_BASE}/drugs.zip", DRUGS_ZIP)
    if force or not RELS_ZIP.exists():
        _fetch(f"{PGKB_BASE}/relationships.zip", RELS_ZIP)
    if force or not DRUGS_TSV.exists():
        with zipfile.ZipFile(DRUGS_ZIP) as z:
            z.extract("drugs.tsv", LRU_DIR)
    if force or not RELS_TSV.exists():
        with zipfile.ZipFile(RELS_ZIP) as z:
            z.extract("relationships.tsv", LRU_DIR)
    return DRUGS_TSV, RELS_TSV


def _ids(v: str) -> str:
    """Split list of ids từ một ô TSV (RxNorm/ATC/PubChem), xử lý cả dấu phẩy."""
    return " ".join(tok for tok in re.split(r"[\s,;]+", (v or "").strip()) if tok)


def _parse_tsv(path: Path):
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            yield row


def import_drugs(conn: sqlite3.Connection, tsv_path: Path = DRUGS_TSV) -> int:
    conn.executescript(SCHEMA)
    conn.execute("DELETE FROM pharmgkb_drugs")
    now = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    n = 0
    for row in _parse_tsv(tsv_path):
        conn.execute(
            "INSERT OR REPLACE INTO pharmgkb_drugs"
            " (accession, name, generic_names, trade_names, brand_mixtures, type,"
            "  cross_refs, rxnorm, atc, pubchem, dosing_guideline, downloaded_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (row.get("PharmGKB Accession Id"),
             (row.get("Name") or "").strip(),
             (row.get("Generic Names") or "").strip(),
             (row.get("Trade Names") or "").strip(),
             (row.get("Brand Mixtures") or "").strip(),
             (row.get("Type") or "").strip(),
             (row.get("Cross-references") or "").strip(),
             _ids(row.get("RxNorm Identifiers")),
             _ids(row.get("ATC Identifiers")),
             _ids(row.get("PubChem Compound Identifiers")),
             1 if (row.get("Dosing Guideline") or "").lower().startswith("y") else 0,
             now),
        )
        n += 1
    conn.commit()
    return n


def import_relations(conn: sqlite3.Connection, tsv_path: Path = RELS_TSV) -> int:
    conn.executescript(SCHEMA)
    conn.execute("DELETE FROM pharmgkb_relations")
    n = 0
    for row in _parse_tsv(tsv_path):
        conn.execute(
            "INSERT INTO pharmgkb_relations"
            " (ent1_id, ent1_name, ent1_type, ent2_id, ent2_name, ent2_type,"
            "  evidence, association, pk, pd, pmids, row_ord)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (row.get("Entity1_id"), (row.get("Entity1_name") or "").strip(),
             (row.get("Entity1_type") or "").strip(),
             row.get("Entity2_id"), (row.get("Entity2_name") or "").strip(),
             (row.get("Entity2_type") or "").strip(),
             (row.get("Evidence") or "").strip(),
             (row.get("Association") or "").strip(),
             (row.get("PK") or "").strip(),
             (row.get("PD") or "").strip(),
             (row.get("PMIDs") or "").strip(),
             n),
        )
        n += 1
    conn.commit()
    return n


def run(conn: sqlite3.Connection, limit: int | None = None, delay: float = 0.0,
        fresh: bool = False, mod: int | None = None, idx: int | None = None) -> dict:
    """Bulk import PharmGKB datasets. limit/fresh chưa dùng — download 1 lần."""
    drugs_tsv, rels_tsv = download()
    stats = {
        "drugs": import_drugs(conn, drugs_tsv),
        "relations": import_relations(conn, rels_tsv),
    }
    register_release(
        conn, "pharmgkb", "PharmGKB drugs + relationships (ClinPGx download)",
        version=DRUGS_TSV.stat().st_mtime.__str__(),
        source_url=PGKB_BASE, terms_url="https://www.pharmgkb.org/page/dataUsagePolicy",
        licence_name="CC BY-SA 4.0", commercial_status="core_open",
        sha256=sha256_of(DRUGS_TSV), parser_version="pharmgkb.run")
    return stats


if __name__ == "__main__":
    import sys

    from .db import get_conn

    conn = get_conn()
    try:
        print("download:", download())
        print("drugs:", import_drugs(conn))
        print("relations:", import_relations(conn))
    finally:
        conn.close()
    print("Wrote raw TSVs to", LRU_DIR)
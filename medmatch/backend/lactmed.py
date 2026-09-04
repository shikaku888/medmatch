"""Import the NLM LactMed Bookshelf bulk NXML release.

The official NCBI Bookshelf FTP archive contains one NXML chapter per substance:
https://ftp.ncbi.nlm.nih.gov/pub/litarch/90/6c/lactmed_NBK501922.tar.gz
The structured sections are retained as reference text; this module never turns
LactMed prose into a prescribing or compatibility verdict.

Usage:
    python -m backend.lactmed [archive.tar.gz]
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
import tarfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from .db import DB_PATH

from .license_registry import register_release, seed_licenses
DEFAULT_ARCHIVE = Path(__file__).parent / "data" / "lactmed" / "lactmed_NBK501922.tar.gz"
SOURCE_URL = "https://ftp.ncbi.nlm.nih.gov/pub/litarch/90/6c/lactmed_NBK501922.tar.gz"
PARSER_VERSION = "lactmed-nxml-v1"

SCHEMA = """
CREATE TABLE IF NOT EXISTS lactmed_records (
    substance_id TEXT PRIMARY KEY,
    substance_name TEXT NOT NULL,
    revised_date TEXT,
    summary_of_use TEXT,
    drug_levels TEXT,
    infant_effects TEXT,
    lactation_effects TEXT,
    alternate_drugs TEXT,
    drug_class TEXT,
    source_url TEXT NOT NULL,
    raw_xml TEXT NOT NULL,
    downloaded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lactmed_name ON lactmed_records(substance_name);
CREATE INDEX IF NOT EXISTS idx_lactmed_name_norm ON lactmed_records(substance_name COLLATE NOCASE);
"""


def _strip(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return re.sub(r"\s+", " ", " ".join(node.itertext())).strip()


def _section(root: ET.Element, *titles: str) -> str:
    wanted = {title.casefold() for title in titles}
    for sec in root.iter():
        if _strip(sec.tag) != "sec":
            continue
        title = next((child for child in sec if _strip(child.tag) == "title"), None)
        title_text = _text(title)
        if title_text.casefold() in wanted:
            text = _text(sec)
            prefix = title_text + " "
            return text[len(prefix):] if text.startswith(prefix) else text
    return ""


def parse_nxml(raw: bytes, source_url: str = SOURCE_URL, downloaded_at: str | None = None) -> dict:
    root = ET.fromstring(raw)
    meta = next((n for n in root.iter() if _strip(n.tag) == "book-part-meta"), root)
    title = next((n for n in meta.iter() if _strip(n.tag) == "title"), None)
    substance_id_node = next((n for n in meta.iter() if _strip(n.tag) == "book-part-id"), None)
    substance_name = _text(title)
    substance_id = (substance_id_node.text or "").strip() if substance_id_node is not None else ""
    if not substance_id or not substance_name:
        raise ValueError("LactMed NXML missing substance id/name")
    revised = next((n for n in meta.iter() if _strip(n.tag) == "date" and n.attrib.get("date-type") == "revised"), None)
    revised_date = None
    if revised is not None:
        parts = {
            _strip(child.tag): (child.text or "").strip()
            for child in revised
            if _strip(child.tag) in {"year", "month", "day"}
        }
        if parts.get("year"):
            revised_date = "-".join([parts["year"], parts.get("month", "01").zfill(2), parts.get("day", "01").zfill(2)])
    summary = _section(root, "Summary of Use during Lactation")
    drug_class = _section(root, "Drug Class")
    return {
        "substance_id": substance_id,
        "substance_name": substance_name,
        "revised_date": revised_date,
        "summary_of_use": summary or None,
        "drug_levels": _section(root, "Drug Levels") or None,
        "infant_effects": _section(root, "Effects in Breastfed Infants") or None,
        "lactation_effects": _section(root, "Effects on Lactation and Breastmilk") or None,
        "alternate_drugs": _section(root, "Alternate Drugs to Consider") or None,
        "drug_class": drug_class or None,
        "source_url": f"https://www.ncbi.nlm.nih.gov/books/{substance_id}/",
        "raw_xml": raw.decode("utf-8", errors="replace"),
        "downloaded_at": downloaded_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _upsert(conn: sqlite3.Connection, record: dict) -> None:
    columns = (
        "substance_id", "substance_name", "revised_date", "summary_of_use",
        "drug_levels", "infant_effects", "lactation_effects", "alternate_drugs",
        "drug_class", "source_url", "raw_xml", "downloaded_at",
    )
    values = [record.get(c) for c in columns]
    conn.execute(
        f"INSERT OR REPLACE INTO lactmed_records ({','.join(columns)}) "
        f"VALUES ({','.join('?' for _ in columns)})", values,
    )


def run(conn: sqlite3.Connection, archive: Path = DEFAULT_ARCHIVE) -> dict:
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    downloaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    stats = {"files": 0, "imported": 0, "errors": 0}
    seed_licenses(conn, {"lactmed"})
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            if (not member.isfile() or not member.name.casefold().endswith(".nxml")
                    or member.name.casefold().endswith("/toc.nxml")):
                continue
            handle = tar.extractfile(member)
            if handle is None:
                continue
            try:
                record = parse_nxml(handle.read(), downloaded_at=downloaded_at)
                _upsert(conn, record)
                stats["imported"] += 1
            except (ET.ParseError, ValueError, UnicodeError) as error:
                stats["errors"] += 1
                print(f"ERR {member.name}: {error}")
            stats["files"] += 1
    conn.commit()
    digest = hashlib.sha256()
    with archive.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    register_release(
        conn,
        "lactmed",
        "NLM Drugs and Lactation Database Bookshelf NXML",
        version=downloaded_at,
        source_url=SOURCE_URL,
        terms_url="https://www.ncbi.nlm.nih.gov/books/NBK547437/",
        licence_name="US federal government work / public-domain reference; NLM trademark and disclaimer apply",
        commercial_status="core_open",
        downloaded_at=downloaded_at,
        sha256=digest.hexdigest(),
        parser_version=PARSER_VERSION,
        notes=f"NXML files={stats['files']}; imported={stats['imported']}",
    )
    stats["rows"] = conn.execute("SELECT COUNT(*) FROM lactmed_records").fetchone()[0]
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("archive", nargs="?", type=Path, default=DEFAULT_ARCHIVE)
    args = ap.parse_args()
    conn = sqlite3.connect(DB_PATH, timeout=120)
    try:
        print(run(conn, args.archive))
    finally:
        conn.close()

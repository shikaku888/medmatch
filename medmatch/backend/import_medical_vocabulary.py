"""Build a local English↔Japanese/Chinese medical vocabulary pack.

The source is MeSpEn_Glossaries, CC BY 4.0. Only translations whose English
term exactly resolves to an existing MedMatch entity are retained. The raw
20 MB archive is not checked into the application; this command materializes
a small, auditable derived pack for offline runtime use.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sqlite3
import unicodedata
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

from .db import DB_PATH

DEFAULT_OUTPUT = Path(__file__).parent / "data" / "multilingual_medical_vocabulary.json"
SOURCE_URL = "https://zenodo.org/api/records/2205690/files/MeSpEn_Glossaries.zip/content"
SOURCE_REPO = "https://github.com/PlanTL-GOB-ES/MeSpEn_Glossaries"
SOURCE_LICENSE = "CC BY 4.0"


def _norm(text: str) -> str:
    """Match backend.engine.normalize exactly, including punctuation handling."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    preserved: list[str] = []
    for ch in decomposed:
        if unicodedata.combining(ch) and not (
            preserved and "\u3040" <= preserved[-1] <= "\u30ff"
        ):
            continue
        preserved.append(ch)
    text = unicodedata.normalize("NFKC", "".join(preserved)).casefold()
    text = "".join(ch if ch.isalnum() or ch in " -" else " " for ch in text)
    return " ".join(text.split())


def _entity_index(conn: sqlite3.Connection) -> dict[str, set[tuple[str, str]]]:
    index: dict[str, set[tuple[str, str]]] = defaultdict(set)

    def add(kind: str, entity_id: str, term: str) -> None:
        key = _norm(term)
        if key:
            index[key].add((kind, entity_id))

    for row in conn.execute("SELECT id, name_en, scientific, aliases FROM herbs"):
        for term in [row["name_en"], row["scientific"], *json.loads(row["aliases"] or "[]")]:
            add("herb", row["id"], term)
    for row in conn.execute("SELECT id, name_en, drugs, aliases FROM drug_classes"):
        for term in [row["name_en"], *json.loads(row["drugs"] or "[]"), *json.loads(row["aliases"] or "[]")]:
            add("drug_class", row["id"], term)
    for row in conn.execute("SELECT id, name_en, aliases FROM foods"):
        for term in [row["name_en"], *json.loads(row["aliases"] or "[]")]:
            add("food", row["id"], term)
    return index


def _read_pairs(archive: zipfile.ZipFile, member: str, english_in_first_column: bool, language: str):
    raw = archive.read(member).decode("utf-8-sig", errors="replace")
    for row in csv.reader(io.StringIO(raw), delimiter="\t"):
        if len(row) < 2:
            continue
        first_column = row[0].replace("\ufeff", "").strip()
        first_column = re.sub(r"^\d+\s+", "", first_column)
        second_column = row[1].replace("\ufeff", "").strip()
        english, localized = (
            (first_column, second_column)
            if english_in_first_column
            else (second_column, first_column)
        )
        if english and localized:
            yield english, localized, language


def _read_local_pairs(path: Path):
    rows = json.loads(path.read_text(encoding="utf-8"))
    for row in rows:
        if not isinstance(row, list) or len(row) < 2:
            continue
        english = re.sub(r"^\d+\s+", "", str(row[0]).replace("\ufeff", "").strip())
        localized = str(row[1]).replace("\ufeff", "").strip()
        if english and localized:
            yield english, localized, "ja"


def build_pack(output: Path, db_path: Path = DB_PATH, source_path: Path | None = None) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        index = _entity_index(conn)
    finally:
        conn.close()

    records: dict[tuple[str, str, str], dict] = {}

    def add_pairs(pairs) -> None:
        for english, localized, language in pairs:
            for kind, entity_id in index.get(_norm(english), ()):
                key = (kind, entity_id, localized)
                records[key] = {
                    "kind": kind,
                    "entity_id": entity_id,
                    "language": language,
                    "term": localized,
                    "english_term": english,
                    "source": "mespen_glossaries",
                }

    source_path = source_path or Path(__file__).parent / "data" / "mespen_glossaries.zip"
    if source_path.exists() and source_path.suffix.lower() == ".json":
        add_pairs(_read_local_pairs(source_path))
    else:
        if source_path.exists():
            archive_bytes = source_path.read_bytes()
        else:
            with urllib.request.urlopen(SOURCE_URL, timeout=180) as response:
                archive_bytes = response.read()
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            add_pairs(_read_pairs(
                archive,
                "MeSpEn_Glossaries/glossaries/English_Japanese_medglossaries.tsv",
                True,
                "ja",
            ))
            add_pairs(_read_pairs(
                archive,
                "MeSpEn_Glossaries/glossaries/Chinese_English_medglossaries.tsv",
                False,
                "zh",
            ))

    items = sorted(records.values(), key=lambda item: (item["language"], item["kind"], item["entity_id"], item["term"]))
    payload = {
        "source": {
            "name": "MeSpEn_Glossaries",
            "repository": SOURCE_REPO,
            "download": SOURCE_URL,
            "license": SOURCE_LICENSE,
            "version": "2018-12-01",
            "languages": ["ja", "zh"],
            "selection": "Exact English-side match to existing MedMatch herb, drug-class, or food entities.",
        },
        "counts": {
            "records": len(items),
            "japanese": sum(item["language"] == "ja" for item in items),
            "chinese": sum(item["language"] == "zh" for item in items),
            "entities": len({(item["kind"], item["entity_id"]) for item in items}),
        },
        "items": items,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload["counts"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--source", type=Path, default=None, help="Local MeSpEn zip or staged Japanese JSON")
    args = parser.parse_args()
    print(json.dumps(build_pack(args.output, args.db, args.source), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

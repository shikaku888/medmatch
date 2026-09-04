"""Export the canonical interaction_unified layer for iOS/API distribution.

The SQLite database remains the source of truth for backend queries. This
compact JSON is an immutable release artifact for clients that need to ship or
cache a snapshot.

Usage:
    python -m backend.export_unified_bundle
"""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .db import DB_PATH

OUT_PATH = Path(__file__).parent / "data" / "unified_bundle.json"
SOURCE_TABLES = (
    "interactions",
    "drug_drug",
    "drug_food",
    "dailymed_interactions",
    "openfda_ddi",
    "suppai_interactions",
    "herb_herb_evidence",
    "chembl_mechanisms",
    "vigi_signals",
    "pharmgkb_relations",
    "can_vig_coprescription",
)


def export(db_path: Path = DB_PATH, out_path: Path = OUT_PATH) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = []
        for row in conn.execute(
            "SELECT pair_key, a_kind, a_id, b_kind, b_id, severity, effect, "
            "mechanism, evidence, confidence, is_inferred "
            "FROM interaction_unified ORDER BY pair_key"
        ):
            item = dict(row)
            item["evidence"] = json.loads(item["evidence"] or "[]")
            rows.append(item)

        source_dbs = {}
        for table in SOURCE_TABLES:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if exists:
                source_dbs[table] = conn.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]

        licenses = [
            dict(row)
            for row in conn.execute(
                "SELECT source_code, licence_name, licence_url, "
                "commercial_use_allowed, attribution_required, share_alike "
                "FROM source_license ORDER BY source_code"
            )
        ]

        payload = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_dbs": source_dbs,
            "licenses": licenses,
            "count": len(rows),
            "pairs": rows,
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = out_path.with_suffix(out_path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(tmp, out_path)
        return {
            "path": str(out_path),
            "count": len(rows),
            "source_dbs": source_dbs,
            "licenses": len(licenses),
        }
    finally:
        conn.close()


if __name__ == "__main__":
    print(export())

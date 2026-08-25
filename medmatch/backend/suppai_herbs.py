"""Build data/suppai_herbs.json from data/suppai_agents.json + the crawled DB.

Every SUPP.AI supplement agent with at least one documented interaction in
the DB becomes a first-class herb with id "suppai:{cui}", so the engine
(search, cabinet, analyze) picks it up automatically. The DB is the source
of truth for "has interactions" — the search API's count field can be stale.
Near-duplicates of tapirro herbs (e.g. "Ashwagandha Root Powder Extract")
are kept as separate entities because they carry their own evidence rows.

Usage:
    python -m backend.suppai_herbs
"""
import json
import re
import sqlite3
import unicodedata
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
AGENTS_PATH = DATA_DIR / "suppai_agents.json"
OUT_PATH = DATA_DIR / "suppai_herbs.json"


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9 \-]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def build(max_aliases: int = 8) -> int:
    from .db import DB_PATH

    agents = json.loads(AGENTS_PATH.read_text(encoding="utf-8"))
    with sqlite3.connect(DB_PATH) as conn:
        has_rows = {r[0] for r in conn.execute("SELECT DISTINCT supp_cui FROM suppai_interactions")}

    out = []
    for cui, meta in agents.items():
        name = (meta.get("name") or "").strip()
        if not name or cui not in has_rows:
            continue
        synonyms = [s for s in (meta.get("synonyms") or []) if s and s.strip()]
        out.append({
            "id": f"suppai:{cui}",
            "name": name,
            "scientific": None,
            "aliases": synonyms[:max_aliases],
        })

    out.sort(key=lambda h: h["name"].lower())
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(out)


if __name__ == "__main__":
    n = build()
    print(f"Wrote {n} new supplement herbs to {OUT_PATH}")

"""PubChem normalization: herb -> primary constituent -> CID + CAS (free API).

PubChem Compound indexes chemical constituents, not plants, so each herb maps
to its well-documented marker compound (curated from public pharmacognosy
knowledge). CID/CAS are the join keys for the unified ingredient layer and
for cross-source dedup (e.g. saw palmetto and pygeum share beta-sitosterol).

Usage:
    python -m backend.pubchem [--limit N] [--delay 0.4]
"""
import argparse
import json
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name"

# herb_id -> marker constituents (high-confidence, public pharmacognosy)
HERB_CONSTITUENTS = {
    "hypericum": ["Hypericin", "Hyperforin"],
    "curcuma": ["Curcumin"],
    "ajo": ["Allicin"],
    "ginkgo": ["Ginkgolide B", "Bilobalide"],
    "ginseng": ["Ginsenoside Rb1"],
    "cardo_mariano": ["Silibinin"],
    "te_verde": ["Epigallocatechin gallate"],
    "guarana": ["Caffeine"],
    "valeriana": ["Valerenic acid"],
    "kava": ["Kavain"],
    "jengibre": ["6-Gingerol"],
    "equinacea": ["Cichoric acid"],
    "saw_palmetto": ["Beta-Sitosterol"],
    "regaliz": ["Glycyrrhizic acid"],
    "romero": ["Rosmarinic acid"],
    "canela": ["Cinnamaldehyde"],
    "menta": ["Menthol"],
    "onagra": ["Gamma-Linolenic acid"],
    "lino": ["Alpha-Linolenic acid"],
    "ashwagandha": ["Withaferin A"],
    "rhodiola": ["Salidroside"],
    "fenogreco": ["Trigonelline"],
    "aloe_vera": ["Aloe-emodin"],
    "salvia": ["Carnosic acid"],
    "dong_quai": ["Ferulic acid"],
    "schisandra": ["Schisandrin"],
    "berberina": ["Berberine"],
    "camu_camu": ["Ascorbic acid"],
    "espino_blanco": ["Vitexin"],
    "pygeum": ["Beta-Sitosterol"],
    "astragalo": ["Astragaloside IV"],
    "arandano": ["Delphinidin"],
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS herb_constituents (
    herb_id TEXT NOT NULL,
    constituent TEXT NOT NULL,
    cid TEXT,
    cas TEXT,
    formula TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (herb_id, constituent)
);
"""

CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.load(r)


def lookup(constituent: str) -> dict | None:
    q = urllib.parse.quote(constituent)
    try:
        prop = _get(f"{BASE}/{q}/property/Title,MolecularFormula/JSON")
        props = prop.get("PropertyTable", {}).get("Properties", [])
        if not props:
            return None
        p = props[0]
        out = {"cid": str(p.get("CID")), "formula": p.get("MolecularFormula"), "cas": None}
        try:
            xrefs = _get(f"{BASE}/{q}/xrefs/RegistryID/JSON")
            ids = xrefs.get("InformationList", {}).get("Information", [{}])[0].get("RegistryID", [])
            for rid in ids:
                rid = rid.lstrip("0") or "0"
                if CAS_RE.match(rid):
                    out["cas"] = rid
                    break
        except Exception:
            out["cas"] = None
        return out
    except Exception:
        return None


def build_map(conn: sqlite3.Connection, limit: int | None, delay: float) -> dict:
    conn.executescript(SCHEMA)
    stats = {"herbs": 0, "constituents": 0, "hits": 0, "misses": 0}
    done = {r[0] for r in conn.execute("SELECT DISTINCT herb_id FROM herb_constituents")}
    for herb_id, constituents in HERB_CONSTITUENTS.items():
        if herb_id in done:
            continue
        if limit is not None and stats["herbs"] >= limit:
            break
        stats["herbs"] += 1
        for const in constituents:
            stats["constituents"] += 1
            hit = lookup(const)
            if hit:
                stats["hits"] += 1
            else:
                stats["misses"] += 1
            conn.execute(
                "INSERT OR REPLACE INTO herb_constituents"
                " (herb_id, constituent, cid, cas, formula) VALUES (?,?,?,?,?)",
                (herb_id, const, hit["cid"] if hit else None,
                 hit["cas"] if hit else None, hit["formula"] if hit else None),
            )
            time.sleep(delay)
    conn.commit()
    return stats


def dedup_report(conn: sqlite3.Connection) -> list[dict]:
    """Herbs sharing the same constituent CID/CAS (chemically related)."""
    rows = conn.execute(
        "SELECT herb_id, constituent, cid, cas FROM herb_constituents"
        " WHERE cid IS NOT NULL"
    ).fetchall()
    groups: dict[str, list] = {}
    for r in rows:
        groups.setdefault(r["cid"], []).append((r["herb_id"], r["constituent"]))
    out = []
    for cid, members in groups.items():
        if len(set(h[0] for h in members)) > 1:
            out.append({"cid": cid, "herbs": sorted(set(h[0] for h in members)),
                        "via": members[0][1]})
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--delay", type=float, default=0.4)
    args = ap.parse_args()
    from .db import DB_PATH

    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        print(build_map(conn, args.limit, args.delay))
        dups = dedup_report(conn)
        print(f"dedup groups (shared CID across herbs): {len(dups)}")
        for d in dups:
            print(" ", d)
    finally:
        conn.close()

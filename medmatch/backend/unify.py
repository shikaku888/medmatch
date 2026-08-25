"""Unified interaction layer (plan Bước 4-5): merge every source into one table.

- ingredient_synonyms: every name variant -> (kind, entity_id) with source.
- standard_ingredient: one canonical row per entity with external IDs
  (RxCUI for drug classes via rxnorm_map, PubChem CID for herbs).
- interaction_unified: deduped pairs across all sources. Conflict
  resolution: severity = max across sources (safety first); effect/mechanism
  from the highest-trust source; evidence = list of {source, trust, doi};
  confidence = max source trust. is_inferred flags CYP rows.

Usage:
    python -m backend.unify
"""
import json
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

SEVERITY_RANK = {"major": 3, "moderate": 2, "minor": 1}

SCHEMA = """
CREATE TABLE IF NOT EXISTS ingredient_synonyms (
    kind TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    synonym TEXT NOT NULL,
    source TEXT NOT NULL,
    PRIMARY KEY (kind, entity_id, synonym)
);
CREATE TABLE IF NOT EXISTS standard_ingredient (
    kind TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    label TEXT NOT NULL,
    external_ids TEXT,
    PRIMARY KEY (kind, entity_id)
);
CREATE TABLE IF NOT EXISTS interaction_unified (
    a_kind TEXT NOT NULL,
    a_id TEXT NOT NULL,
    b_kind TEXT NOT NULL,
    b_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    effect TEXT,
    mechanism TEXT,
    evidence TEXT,
    confidence REAL NOT NULL,
    is_inferred INTEGER NOT NULL DEFAULT 0,
    pair_key TEXT NOT NULL PRIMARY KEY
);
"""


def _norm_key(kind: str, eid: str) -> str:
    return f"{kind}:{eid}"


def build_synonyms(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM ingredient_synonyms")
    n = 0

    def add(kind, eid, name, source):
        nonlocal n
        if name and name.strip():
            conn.execute(
                "INSERT OR IGNORE INTO ingredient_synonyms (kind, entity_id, synonym, source)"
                " VALUES (?,?,?,?)", (kind, eid, name.strip(), source))
            n += 1

    for r in conn.execute("SELECT id, name_en, name_es, scientific, aliases FROM herbs"):
        for a in [r["name_en"], r["name_es"], r["scientific"]] + json.loads(r["aliases"] or "[]"):
            add("herb", r["id"], a, "tapirro/suppai")
    for r in conn.execute("SELECT id, name_en, drugs, aliases FROM drug_classes"):
        for a in [r["name_en"]] + json.loads(r["drugs"] or "[]") + json.loads(r["aliases"] or "[]"):
            add("drug_class", r["id"], a, "tapirro/fda")
    for r in conn.execute("SELECT id, name_en, aliases FROM foods"):
        for a in [r["name_en"]] + json.loads(r["aliases"] or "[]"):
            add("food", r["id"], a, "fda")
    conn.commit()
    return n


def build_standards(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM standard_ingredient")
    n = 0
    rxnorm = json.loads((DATA_DIR / "rxnorm_map.json").read_text(encoding="utf-8")) \
        if (DATA_DIR / "rxnorm_map.json").exists() else {}

    def ext_ids(kind, eid):
        ids = {}
        if kind == "drug_class":
            members = conn.execute("SELECT drugs FROM drug_classes WHERE id = ?", (eid,)).fetchone()
            own = [f"rxnorm:{rxnorm[m.lower()]['rxcui']}" for m in json.loads(members["drugs"] or [])
                   if m.lower() in rxnorm]
            if own:
                ids = {"rxnorm": own[:5]}
        elif kind == "herb":
            cons = conn.execute(
                "SELECT constituent, cid, cas FROM herb_constituents WHERE herb_id = ?", (eid,)
            ).fetchall()
            if cons:
                ids = {"pubchem": [c["cid"] for c in cons if c["cid"]],
                       "cas": [c["cas"] for c in cons if c["cas"]]}
        return json.dumps(ids) if ids else None

    for kind, table in (("herb", "herbs"), ("drug_class", "drug_classes"), ("food", "foods")):
        for r in conn.execute(f"SELECT id, name_en FROM {table}"):
            conn.execute(
                "INSERT OR REPLACE INTO standard_ingredient (kind, entity_id, label, external_ids)"
                " VALUES (?,?,?,?)",
                (kind, r["id"], r["name_en"], ext_ids(kind, r["id"])))
            n += 1
    conn.commit()
    return n


def build_unified(conn: sqlite3.Connection) -> dict:
    conn.execute("DELETE FROM interaction_unified")
    stats = {"pairs": 0, "rows_merged": 0, "conflicts": 0}

    merged: dict[str, dict] = {}

    def add(a_kind, a_id, b_kind, b_id, severity, effect, mechanism, source, trust, doi=None, inferred=False):
        a, b = sorted((_norm_key(a_kind, a_id), _norm_key(b_kind, b_id)))
        key = f"{a}|{b}"
        row = merged.setdefault(key, {
            "a": a, "b": b, "severity": "minor", "effect": None,
            "mechanism": None, "evidence": [], "confidence": 0.0,
            "is_inferred": 0, "has_direct": False, "sevs": {},
        })
        row["has_direct"] |= (not inferred)
        if SEVERITY_RANK.get(severity, 1) > SEVERITY_RANK.get(row["severity"], 1):
            row["severity"] = severity
        if trust >= row["confidence"]:
            row["confidence"] = trust
            if effect:
                row["effect"] = effect
            if mechanism:
                row["mechanism"] = mechanism
        row["evidence"].append({"source": source, "trust": trust, "doi": doi})
        row["sevs"][source] = severity

    # seeds herb x class
    for r in conn.execute("SELECT herb_id, class_id, severity, effect, mechanism, source, doi, trust FROM interactions"):
        add("herb", r["herb_id"], "drug_class", r["class_id"], r["severity"], r["effect"],
            r["mechanism"], r["source"] or "tapirro", r["trust"], r["doi"])
    # seeds drug x drug
    for r in conn.execute("SELECT cls_a, cls_b, drug_a, drug_b, severity, effect, mechanism, source, trust FROM drug_drug"):
        if r["cls_a"] and r["cls_b"]:
            add("drug_class", r["cls_a"], "drug_class", r["cls_b"], r["severity"], r["effect"],
                r["mechanism"], r["source"] or "FDA labeling", r["trust"])
        elif r["drug_a"] and r["drug_b"]:
            add("drug_class", r["drug_a"], "drug_class", r["drug_b"], r["severity"], r["effect"],
                r["mechanism"], r["source"] or "FDA labeling", r["trust"])
    # drug x food seeds
    for r in conn.execute("SELECT cls_a, food_id, severity, effect, mechanism, source, trust FROM drug_food"):
        add("drug_class", r["cls_a"], "food", r["food_id"], r["severity"], r["effect"],
            r["mechanism"], r["source"], r["trust"])
    # dailymed
    for r in conn.execute("SELECT cls_src, cls_mentioned, severity, effect, source, trust FROM dailymed_interactions"):
        add("drug_class", r["cls_src"], "drug_class", r["cls_mentioned"], r["severity"], r["effect"],
            None, r["source"], r["trust"])
    # ddinter
    for r in conn.execute("SELECT cls_a, cls_b, severity, source, trust, drug_a, drug_b FROM ddinter_interactions"):
        add("drug_class", r["cls_a"], "drug_class", r["cls_b"], r["severity"],
            f"{r['drug_a']} + {r['drug_b']}", None, r["source"], r["trust"])
    # suppai (class-mapped only)
    for r in conn.execute("SELECT herb_id, class_id, drug_name, doi, trust FROM suppai_interactions WHERE class_id IS NOT NULL"):
        add("herb", r["herb_id"], "drug_class", r["class_id"], "moderate",
            f"Evidence-backed interaction with {r['drug_name']}", None, "SUPP.AI", r["trust"], r["doi"])
    # idisk
    for r in conn.execute("SELECT herb_id, class_id, description, source, trust FROM idisk_interactions"):
        add("herb", r["herb_id"], "drug_class", r["class_id"], "moderate",
            r["description"], None, r["source"] or "iDISK", r["trust"])
    # herb x herb
    for r in conn.execute("SELECT herb_a, herb_b, doi, trust FROM herb_herb_evidence"):
        add("herb", r["herb_a"], "herb", r["herb_b"], "moderate",
            "Evidence-backed supplement interaction", None, "SUPP.AI (herb-herb)", r["trust"], r["doi"])
    # drugfood evidence
    for r in conn.execute("SELECT cls_a, food_id, severity, effect, source, trust FROM drugfood_evidence"):
        add("drug_class", r["cls_a"], "food", r["food_id"], r["severity"], r["effect"],
            None, r["source"], r["trust"])
    # cyp inference
    roles = conn.execute("SELECT * FROM cyp_roles").fetchall()
    by_entity: dict[tuple, dict[str, set]] = {}
    for r in roles:
        ent = by_entity.setdefault((r["entity_type"], r["entity_id"]),
                                   {"substrate": set(), "inhibitor": set(), "inducer": set()})
        ent[r["role"]].add(r["enzyme"])
    names = {("drug_class", r["id"]): r["name_en"] for r in conn.execute("SELECT id, name_en FROM drug_classes")}
    names.update({("herb", r["id"]): r["name_en"] for r in conn.execute("SELECT id, name_en FROM herbs")})
    for (ta, ia), ra in by_entity.items():
        for (tb, ib), rb in by_entity.items():
            x, y = sorted([(ta, ia), (tb, ib)])
            if x == y:
                continue
            overlap = ((ra.get("inhibitor", set()) & rb.get("substrate", set()))
                       | (ra.get("inducer", set()) & rb.get("substrate", set()))
                       | (rb.get("inhibitor", set()) & ra.get("substrate", set()))
                       | (rb.get("inducer", set()) & ra.get("substrate", set())))
            if not overlap:
                continue
            add(x[0], x[1], y[0], y[1], "moderate",
                f"CYP pathway overlap: {', '.join(sorted(overlap))}",
                "Enzyme pathway inference", "CYP450 inference", 0.5, inferred=True)

    for key, row in merged.items():
        row["is_inferred"] = 0 if row["has_direct"] else 1
        ak, aid = row["a"].split(":", 1)
        bk, bid = row["b"].split(":", 1)
        # dedup evidence entries by source (keep highest trust per source)
        best_ev: dict[str, dict] = {}
        for e in row["evidence"]:
            if e["source"] not in best_ev or e["trust"] > best_ev[e["source"]]["trust"]:
                best_ev[e["source"]] = e
        ev = list(best_ev.values())
        # conflict = sources disagree on severity for the same pair
        sev_values = {v for v in row["sevs"].values()}
        if len(sev_values) > 1:
            stats["conflicts"] += 1
        conn.execute(
            "INSERT INTO interaction_unified"
            " (a_kind, a_id, b_kind, b_id, severity, effect, mechanism, evidence, confidence, is_inferred, pair_key)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (ak, aid, bk, bid, row["severity"], row["effect"], row["mechanism"],
             json.dumps(ev), row["confidence"], row["is_inferred"], key),
        )
        stats["pairs"] += 1
        stats["rows_merged"] += len(ev)
    conn.commit()
    return stats


if __name__ == "__main__":
    from .db import DB_PATH

    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        print("synonyms:", build_synonyms(conn))
        print("standards:", build_standards(conn))
        print("unified:", build_unified(conn))
    finally:
        conn.close()

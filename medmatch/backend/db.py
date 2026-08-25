"""SQLite schema + seeding from translated tapirro data and curated rules."""
import json
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = Path(__file__).parent / "medmatch.db"

SEVERITY_MAP = {"alta": "major", "moderada": "moderate", "baja": "minor"}
# Source trust tiers (plan3): FDA/EMA 1.0 > DDInter/SUPP.AI 0.9 > BotanicaAndina/NaPDI 0.8 > KG 0.7 > inference 0.5
TRUST_FDA_LABEL = 1.0
TRUST_TAPIRRO = 0.9
EVIDENCE_MAP = {
    "Estudios preclínicos": "Preclinical studies",
    "Ensayos clínicos": "Clinical trials",
    "Ensayos clinicos": "Clinical trials",
    "In vitro": "In vitro",
    "Estudios in vitro": "In vitro studies",
    "In vitro + in vivo": "In vitro + in vivo",
    "Reportes de caso": "Case reports",
    "Mecanismo farmacológico": "Pharmacological mechanism",
    "Teórico": "Theoretical",
    "Metaanálisis": "Meta-analysis",
}

# Tables owned by the seeder (wiped on rebuild). Fetched tables such as
# suppai_interactions are created by their importers and MUST NOT be listed
# here — rebuilding seeds preserves them.
SEED_TABLES = ("herbs", "drug_classes", "interactions", "drug_drug", "foods", "drug_food", "cyp_roles")

SCHEMA = """
CREATE TABLE IF NOT EXISTS herbs (
    id TEXT PRIMARY KEY,
    name_en TEXT NOT NULL,
    name_es TEXT,
    scientific TEXT,
    aliases TEXT
);
CREATE TABLE IF NOT EXISTS drug_classes (
    id TEXT PRIMARY KEY,
    name_en TEXT NOT NULL,
    drugs TEXT,
    aliases TEXT
);
CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    herb_id TEXT NOT NULL,
    class_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    effect TEXT,
    mechanism TEXT,
    evidence TEXT,
    source TEXT,
    doi TEXT,
    trust REAL NOT NULL DEFAULT 0.5,
    pair_key TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_inter_herb ON interactions(herb_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_inter_pair ON interactions(pair_key);
CREATE TABLE IF NOT EXISTS drug_drug (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cls_a TEXT, cls_b TEXT,
    drug_a TEXT, drug_b TEXT,
    severity TEXT NOT NULL,
    effect TEXT, mechanism TEXT, source TEXT,
    trust REAL NOT NULL DEFAULT 0.5,
    pair_key TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_dd_pair ON drug_drug(pair_key);
CREATE TABLE IF NOT EXISTS foods (
    id TEXT PRIMARY KEY,
    name_en TEXT NOT NULL,
    aliases TEXT
);
CREATE TABLE IF NOT EXISTS drug_food (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cls_a TEXT NOT NULL,
    food_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    effect TEXT,
    mechanism TEXT,
    source TEXT,
    trust REAL NOT NULL DEFAULT 0.5,
    pair_key TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_df_pair ON drug_food(pair_key);
CREATE TABLE IF NOT EXISTS cyp_roles (
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    role TEXT NOT NULL,
    enzyme TEXT NOT NULL,
    PRIMARY KEY (entity_type, entity_id, role, enzyme)
);
"""


def _load(name):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def build_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    from .drug_food_seed import DRUG_FOOD_RULES, FOODS  # noqa: E402
    from .cyp_seed import CYP_CLASS_ROLES, CYP_HERB_ROLES  # noqa: E402
    translations = _load("translations_en.json")
    drug_names = _load("drug_names_en.json")
    herbs = _load("herbs.json")
    suppai_herbs_path = DATA_DIR / "suppai_herbs.json"
    if suppai_herbs_path.exists():
        herbs = herbs + _load("suppai_herbs.json")
    classes = _load("drug_classes.json")
    interactions = _load("interactions.json")

    from .drug_drug_seed import DRUG_DRUG_RULES, DRUG_LEVEL_RULES  # noqa: E402
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    for t in SEED_TABLES:
        conn.execute(f"DELETE FROM {t}")
    conn.execute("DELETE FROM sqlite_sequence WHERE name IN (?,?)",
                 ("interactions", "drug_drug"))

    seen = set()
    for h in herbs:
        hid = h["id"]
        if hid in seen:
            continue
        seen.add(hid)
        name_en = translations.get(f"herb:{hid}", h["name"])
        aliases = h.get("aliases") or []
        if name_en not in aliases:
            aliases = [name_en] + aliases
        conn.execute(
            "INSERT INTO herbs (id, name_en, name_es, scientific, aliases) VALUES (?,?,?,?,?)",
            (hid, name_en, h["name"], h.get("scientific"), json.dumps(aliases)),
        )

    for c in classes:
        cid = c["id"]
        name_en = translations.get(f"cls:{cid}", c["name"])
        drugs = [drug_names.get(d.lower(), d) for d in c["drugs"]]
        aliases = [name_en] + (c.get("aliases") or [])
        conn.execute(
            "INSERT INTO drug_classes (id, name_en, drugs, aliases) VALUES (?,?,?,?)",
            (cid, name_en, json.dumps(drugs), json.dumps(aliases)),
        )

    seen_pairs = set()
    for i in interactions:
        key = (i["herb"], i["drugClass"])
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        severity = SEVERITY_MAP.get(i["severity"], "minor")
        effect = translations.get(f"effect:{i['herb']}|{i['drugClass']}", i["effect"])
        mechanism = translations.get(f"mech:{i['herb']}|{i['drugClass']}", i["mechanism"])
        evidence = EVIDENCE_MAP.get(i["evidence"], translations.get(f"ev:{i['evidence']}", i["evidence"]))
        conn.execute(
            "INSERT INTO interactions (herb_id, class_id, severity, effect, mechanism, evidence, source, doi, trust, pair_key)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (i["herb"], i["drugClass"], severity, effect, mechanism, evidence,
             i.get("source"), i.get("doi"), TRUST_TAPIRRO,
             f"herb:{i['herb']}|cls:{i['drugClass']}"),
        )

    seen_rules = set()
    for r in DRUG_DRUG_RULES:
        key = tuple(sorted((r["cls_a"], r["cls_b"])))
        if key in seen_rules:
            continue
        seen_rules.add(key)
        conn.execute(
            "INSERT INTO drug_drug (cls_a, cls_b, severity, effect, mechanism, source, trust, pair_key)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (r["cls_a"], r["cls_b"], r["severity"], r["effect"], r["mechanism"], r["source"],
             TRUST_FDA_LABEL, f"cls:{key[0]}|cls:{key[1]}"),
        )
    for r in DRUG_LEVEL_RULES:
        key = tuple(sorted((r["drug_a"], r["drug_b"])))
        if key in seen_rules:
            continue
        seen_rules.add(key)
        conn.execute(
            "INSERT INTO drug_drug (drug_a, drug_b, severity, effect, mechanism, source, trust, pair_key)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (r["drug_a"], r["drug_b"], r["severity"], r["effect"], r["mechanism"], r["source"],
             TRUST_FDA_LABEL, f"drug:{key[0]}|drug:{key[1]}"),
        )
    seen_food_pairs = set()
    for f in FOODS:
        conn.execute(
            "INSERT INTO foods (id, name_en, aliases) VALUES (?,?,?)",
            (f["id"], f["name"], json.dumps(f["aliases"])),
        )
    for r in DRUG_FOOD_RULES:
        key = (r["cls_a"], r["food"])
        if key in seen_food_pairs:
            continue
        seen_food_pairs.add(key)
        conn.execute(
            "INSERT INTO drug_food (cls_a, food_id, severity, effect, mechanism, source, trust, pair_key)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (r["cls_a"], r["food"], r["severity"], r["effect"], r["mechanism"], r["source"],
             TRUST_FDA_LABEL, f"cls:{r['cls_a']}|food:{r['food']}"),
        )
    for etype, roles_map in (("drug_class", CYP_CLASS_ROLES), ("herb", CYP_HERB_ROLES)):
        for eid, roles in roles_map.items():
            for role, enzymes in roles.items():
                for enz in enzymes:
                    conn.execute(
                        "INSERT INTO cyp_roles (entity_type, entity_id, role, enzyme)"
                        " VALUES (?,?,?,?)",
                        (etype, eid, role.rstrip("s"), enz),
                    )

    conn.commit()
    return conn


def get_conn(db_path: Path = DB_PATH) -> sqlite3.Connection:
    if not db_path.exists():
        build_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


if __name__ == "__main__":
    conn = build_db()
    for table in ("herbs", "drug_classes", "interactions", "drug_drug", "foods", "drug_food"):
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {n}")
    conn.close()
    print("DB built at", DB_PATH)

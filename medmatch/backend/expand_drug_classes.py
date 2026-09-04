"""Expand drug_classes table với per-drug micro-classes từ rxnorm_concepts,
sau đó remap suppai_interactions.class_id cho các row hiện đang NULL.

Chiến lược:
1. Lấy tất cả distinct drug_name trong suppai WHERE class_id IS NULL
   (tập nhỏ: ~5-6k distinct names, tránh JOIN nặng)
2. Với mỗi tên: tìm trong rxnorm_names -> rxnorm_concepts (tty=IN/MIN/PIN)
   hoặc trong pharmgkb_drugs để lấy rxcui/atc
3. Nếu tìm thấy và là clinical drug (có rxcui IN-level):
   - Tạo drug_class id = 'rxdrg:<rxcui>' nếu chưa có
   - Update suppai_interactions SET class_id = 'rxdrg:<rxcui>'
4. Cũng mở rộng drug_classes bằng các drug từ pharmgkb_drugs có ATC code
   (group theo ATC level-4 prefix)
5. Report số lượng mới mapped

Không thay đổi 58 class gốc. Micro-class chỉ dùng trong interaction_unified
để tăng coverage drug x herb.

Usage:
    python -m backend.expand_drug_classes [--dry-run]
"""
import argparse
import json
import re
import sqlite3
import unicodedata
from pathlib import Path

DB_PATH = Path(__file__).parent / "medmatch.db"
DATA_DIR = Path(__file__).parent / "data"

# Các TTY ưu tiên từ cao xuống thấp cho RxNorm ingredient lookup
TTY_PREF = {"IN": 0, "MIN": 1, "PIN": 2, "PSN": 3, "SY": 4}

# Danh sách các tên/pattern không phải clinical drug
# (endogenous molecules, food chemicals, lab reagents)
NON_DRUG_PATTERNS = [
    r"^nitric oxide$", r"^ethanol$", r"^glucose$", r"^hydrogen peroxide$",
    r"^adenosine triphosphate$", r"^alkaline phosphatase$",
    r"^phospholipids?$", r"^acetylcholine$", r"^serotonin$",
    r"^albumin$", r"^sodium chloride$", r"^arachidonic acid$",
    r"^histamine$", r"^nitrogen$", r"^glycerol$", r"^urea$",
    r"^creatinine$", r"^aspartic acid$", r"^leptin$",
    r"^polyunsaturated fatty acids?$", r"^linoleic acid$",
    r"^oleic acid$", r"^alanine$", r"^catechin$",
    r"^rabbit allergenic extract$", r"^steroids?$",
    r"^gamma.aminobutyric acid$", r"^manganese$", r"^potassium$",
    r"^potassium chloride$", r"^edetic acid$", r"^quercetin$",
    r"^resveratrol$", r"^curcumin$",  # nutraceuticals - keep as herbs
    r"acid$", r"^amino ", r" extract$", r"^oxygen$",
    r"^water$", r"^saline$", r"^dextrose$",
]
_NON_DRUG_RE = re.compile("|".join(NON_DRUG_PATTERNS), re.IGNORECASE)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9 \-]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_non_drug(name: str) -> bool:
    return bool(_NON_DRUG_RE.search(name.strip()))


def build_rxnorm_name_index(conn: sqlite3.Connection) -> dict[str, tuple[str, str]]:
    """lower(name) -> (rxcui, tty) — pick best TTY per name."""
    idx: dict[str, tuple[str, str]] = {}
    rows = conn.execute(
        "SELECT lower(name) as nm, rxcui, tty FROM rxnorm_names"
        " WHERE tty IN ('IN','MIN','PIN','PSN','SY')"
    ).fetchall()
    for nm, rxcui, tty in rows:
        existing = idx.get(nm)
        if existing is None or TTY_PREF.get(tty, 99) < TTY_PREF.get(existing[1], 99):
            idx[nm] = (rxcui, tty)
    return idx


def build_pharmgkb_index(conn: sqlite3.Connection) -> dict[str, tuple[str, str]]:
    """lower(name) -> (rxnorm, atc) from pharmgkb_drugs."""
    idx: dict[str, tuple[str, str]] = {}
    rows = conn.execute(
        "SELECT lower(name) as nm, rxnorm, atc FROM pharmgkb_drugs"
        " WHERE rxnorm IS NOT NULL AND rxnorm != ''"
    ).fetchall()
    for nm, rxnorm, atc in rows:
        if nm not in idx:
            idx[nm] = (rxnorm.strip().split()[0], (atc or "").strip())
    return idx


def build_rxcui_preferred_name(conn: sqlite3.Connection) -> dict[str, str]:
    """rxcui -> preferred name (IN/MIN preferred)."""
    idx: dict[str, str] = {}
    rows = conn.execute(
        "SELECT rxcui, name, tty FROM rxnorm_concepts ORDER BY rxcui"
    ).fetchall()
    pref: dict[str, tuple[str, int]] = {}
    for rxcui, name, tty in rows:
        rank = TTY_PREF.get(tty, 99)
        if rxcui not in pref or rank < pref[rxcui][1]:
            pref[rxcui] = (name, rank)
    return {k: v[0] for k, v in pref.items()}


def ensure_micro_class(conn: sqlite3.Connection, rxcui: str, name: str,
                        atc: str, dry_run: bool) -> str:
    """Tạo drug_class row 'rxdrg:<rxcui>' nếu chưa có. Return class_id."""
    class_id = f"rxdrg:{rxcui}"
    existing = conn.execute(
        "SELECT id FROM drug_classes WHERE id = ?", (class_id,)
    ).fetchone()
    if not existing and not dry_run:
        aliases_json = json.dumps([name.lower()])
        drugs_json = json.dumps([name.lower()])
        conn.execute(
            "INSERT OR IGNORE INTO drug_classes (id, name_en, drugs, aliases)"
            " VALUES (?, ?, ?, ?)",
            (class_id, name, drugs_json, aliases_json),
        )
    return class_id


def remap_suppai(conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    stats = {
        "distinct_unmapped": 0,
        "skipped_non_drug": 0,
        "rxnorm_matched": 0,
        "micro_classes_created": 0,
        "rows_updated": 0,
    }

    print("Loading indexes...")
    rx_idx = build_rxnorm_name_index(conn)
    pg_idx = build_pharmgkb_index(conn)
    pref_names = build_rxcui_preferred_name(conn)
    print(f"  rxnorm_names index: {len(rx_idx):,} entries")
    print(f"  pharmgkb index:     {len(pg_idx):,} entries")

    # Distinct unmapped drug names (small set)
    unmapped = conn.execute(
        "SELECT DISTINCT drug_name, drug_cui"
        " FROM suppai_interactions WHERE class_id IS NULL"
    ).fetchall()
    stats["distinct_unmapped"] = len(unmapped)
    print(f"Distinct unmapped drugs: {len(unmapped):,}")

    existing_classes = {
        r[0] for r in conn.execute("SELECT id FROM drug_classes")
    }

    name_to_class: dict[str, str] = {}  # drug_name -> class_id

    for drug_name, drug_cui in unmapped:
        lname = drug_name.lower().strip() if drug_name else ""
        if not lname or is_non_drug(lname):
            stats["skipped_non_drug"] += 1
            continue

        # Try rxnorm_names first, then pharmgkb
        rxcui = None
        atc = ""
        hit = rx_idx.get(lname)
        if hit:
            rxcui = hit[0]

        pg_hit = pg_idx.get(lname)
        if pg_hit:
            if not rxcui:
                rxcui = pg_hit[0]
            atc = pg_hit[1]

        # Try normalized version
        if not rxcui:
            norm = normalize(drug_name)
            hit = rx_idx.get(norm)
            if hit:
                rxcui = hit[0]
            pg_hit = pg_idx.get(norm)
            if pg_hit:
                if not rxcui:
                    rxcui = pg_hit[0]
                atc = pg_hit[1]

        if not rxcui:
            continue

        stats["rxnorm_matched"] += 1
        class_id = f"rxdrg:{rxcui}"
        pref_name = pref_names.get(rxcui, drug_name)

        if class_id not in existing_classes:
            ensure_micro_class(conn, rxcui, pref_name, atc, dry_run)
            existing_classes.add(class_id)
            stats["micro_classes_created"] += 1

        name_to_class[drug_name] = class_id

    print(f"Matched: {stats['rxnorm_matched']:,}  micro-classes new: {stats['micro_classes_created']:,}")
    print("Updating suppai_interactions...")

    if not dry_run:
        for drug_name, class_id in name_to_class.items():
            cur = conn.execute(
                "UPDATE suppai_interactions SET class_id = ?"
                " WHERE drug_name = ? AND class_id IS NULL",
                (class_id, drug_name),
            )
            stats["rows_updated"] += cur.rowcount
        conn.commit()

    return stats


def remap_pharmgkb_ddi(conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    """Map pharmgkb_relations Chemical x Chemical -> drug_class pairs
    into drug_drug table nếu cả hai có rxcui."""
    pg_idx = build_pharmgkb_index(conn)
    rx_idx = build_rxnorm_name_index(conn)
    pref_names = build_rxcui_preferred_name(conn)

    # Ensure drug_drug table exists
    conn.executescript("""
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
    """)

    stats = {"pairs_found": 0, "inserted": 0}
    rows = conn.execute(
        "SELECT ent1_name, ent2_name, evidence, association, pmids"
        " FROM pharmgkb_relations"
        " WHERE ent1_type='Chemical' AND ent2_type='Chemical'"
        " AND association NOT LIKE 'not%'"
    ).fetchall()

    for ent1, ent2, evidence, assoc, pmids in rows:
        stats["pairs_found"] += 1
        l1, l2 = ent1.lower(), ent2.lower()
        hit1 = pg_idx.get(l1) or rx_idx.get(l1)
        hit2 = pg_idx.get(l2) or rx_idx.get(l2)
        if not hit1 or not hit2:
            continue
        rxcui1, rxcui2 = hit1[0], hit2[0]
        cls_a = f"rxdrg:{rxcui1}"
        cls_b = f"rxdrg:{rxcui2}"
        a, b = sorted((cls_a, cls_b))
        pair_key = f"pgkb:{a}|{b}"
        effect = f"PharmGKB: {assoc}" if assoc else None
        mech = evidence if evidence else None
        doi = pmids.split(",")[0].strip() if pmids else None
        if not dry_run:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO drug_drug"
                    " (cls_a, cls_b, drug_a, drug_b, severity, effect,"
                    "  mechanism, source, trust, pair_key)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (a, b, ent1, ent2, "moderate", effect,
                     mech, "PharmGKB (CC BY-SA 4.0)", 0.75, pair_key),
                )
                stats["inserted"] += 1
            except Exception:
                pass

    if not dry_run:
        conn.commit()
    return stats


def remap_drugcentral_cyp(conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    """DrugCentral targets: mỗi drug có CYP gene target -> thêm vào cyp_roles
    để CYP inference trong unify.py mở rộng DDI coverage."""
    # Check if drugcentral_targets exists and has CYP genes
    try:
        rows = conn.execute(
            "SELECT DISTINCT drug_name, gene, action_type"
            " FROM drugcentral_targets"
            " WHERE gene LIKE 'CYP%' AND organism='Homo sapiens'"
        ).fetchall()
    except Exception as e:
        return {"error": str(e)}

    pg_idx = build_pharmgkb_index(conn)
    rx_idx = build_rxnorm_name_index(conn)

    stats = {"cyp_rows_found": len(rows), "class_matched": 0, "cyp_roles_added": 0}

    # Build existing class index (58 built-in + rxdrg micro-classes)
    existing_classes = {
        r[0] for r in conn.execute("SELECT id FROM drug_classes")
    }

    # Also load existing cyp_roles to avoid duplicates
    existing_roles: set[tuple] = {
        (r[0], r[1], r[2], r[3])
        for r in conn.execute("SELECT entity_type, entity_id, role, enzyme FROM cyp_roles")
    }

    for drug_name, gene, action_type in rows:
        lname = (drug_name or "").lower().strip()
        hit = pg_idx.get(lname) or rx_idx.get(lname)
        if not hit:
            hit = pg_idx.get(normalize(drug_name)) or rx_idx.get(normalize(drug_name))
        if not hit:
            continue

        rxcui = hit[0]
        class_id = f"rxdrg:{rxcui}"
        if class_id not in existing_classes:
            continue  # micro-class chưa có trong DB, bỏ qua (remap_suppai tạo trước)

        stats["class_matched"] += 1

        # Map DrugCentral action_type -> CYP role
        action = (action_type or "").upper()
        if "INHIBITOR" in action or "BLOCKER" in action:
            role = "inhibitor"
        elif "INDUCER" in action:
            role = "inducer"
        else:
            role = "substrate"  # default nếu không rõ

        enzyme = gene.strip()
        key = ("drug_class", class_id, role, enzyme)
        if key in existing_roles:
            continue
        existing_roles.add(key)

        if not dry_run:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO cyp_roles"
                    " (entity_type, entity_id, role, enzyme)"
                    " VALUES (?,?,?,?)",
                    ("drug_class", class_id, role, enzyme),
                )
                stats["cyp_roles_added"] += 1
            except Exception:
                pass

    if not dry_run:
        conn.commit()
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--db", default=str(DB_PATH))
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    print("=== Step 1: Remap suppai via RxNorm micro-classes ===")
    s1 = remap_suppai(conn, dry_run=args.dry_run)
    print(s1)

    print()
    print("=== Step 2: PharmGKB Chemical x Chemical -> drug_drug ===")
    s2 = remap_pharmgkb_ddi(conn, dry_run=args.dry_run)
    print(s2)

    print()
    print("=== Step 3: DrugCentral CYP targets -> cyp_roles ===")
    s3 = remap_drugcentral_cyp(conn, dry_run=args.dry_run)
    print(s3)

    print()
    total_classes = conn.execute("SELECT COUNT(*) FROM drug_classes").fetchone()[0]
    total_mapped = conn.execute(
        "SELECT COUNT(*) FROM suppai_interactions WHERE class_id IS NOT NULL"
    ).fetchone()[0]
    total_suppai = conn.execute("SELECT COUNT(*) FROM suppai_interactions").fetchone()[0]
    print(f"drug_classes now: {total_classes:,}")
    print(f"suppai mapped: {total_mapped:,}/{total_suppai:,} ({100*total_mapped/total_suppai:.1f}%)")

    conn.close()


if __name__ == "__main__":
    main()

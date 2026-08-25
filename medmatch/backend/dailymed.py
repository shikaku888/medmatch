"""Parse DailyMed (FDA SPL labels, public domain) DRUG INTERACTIONS sections.

For each drug in our class members: find its SPLs via the DailyMed API,
parse the DRUG INTERACTIONS section (LOINC 34067-9), detect mentioned drug
names against our class index, and emit class x class interaction candidates
with the label sentence as effect. trust=1.0 (FDA labeling tier).

Usage:
    python -m backend.dailymed [--limit N] [--delay 0.5] [--mod M --idx K]
"""
import argparse
import json
import re
import sqlite3
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from .engine import normalize

BASE = "https://dailymed.nlm.nih.gov/dailymed/services/v2"
DATA_DIR = Path(__file__).parent / "data"

DDI_CODE = "34067-9"

SCHEMA = """
CREATE TABLE IF NOT EXISTS dailymed_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cls_src TEXT NOT NULL,
    cls_mentioned TEXT NOT NULL,
    drug_src TEXT NOT NULL,
    drug_mentioned TEXT NOT NULL,
    severity TEXT NOT NULL,
    effect TEXT,
    source TEXT,
    pair_key TEXT NOT NULL,
    trust REAL NOT NULL DEFAULT 1.0
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_dm_pair ON dailymed_interactions(pair_key);
"""

REPACK_MARKERS = ("REPACK", "REMEDY", "PREPACK", "COUPLER", "A-S MEDICATION",
                  "CARDINAL HEALTH", "MCKESSON", "AMERISOURCE", "PD-RX",
                  "PREFERRED PHARMACEUTICALS", "LAKE ERIE", "DIRECT RX",
                  "NUCARE", "PROFICIENT RX")

# keyword -> severity (FDA labeling language)
_SEV_PATTERNS = [
    (re.compile(r"contraindicat", re.I), "major"),
    (re.compile(r"should not be used|do not use|must not|avoid", re.I), "major"),
    (re.compile(r"not recommended", re.I), "moderate"),
    (re.compile(r"caution|monitor|dose adjustment|reduce (the )?dose|closely", re.I), "moderate"),
    (re.compile(r"may (increase|decrease|prolong|reduce)", re.I), "moderate"),
]


def _get_json(path: str, params: dict | None = None) -> dict:
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.load(r)


def _get_xml(path: str) -> str:
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def _load_class_index() -> dict[str, str]:
    classes = json.loads((DATA_DIR / "drug_classes.json").read_text(encoding="utf-8"))
    drug_names = json.loads((DATA_DIR / "drug_names_en.json").read_text(encoding="utf-8"))
    idx: dict[str, str] = {}
    for c in classes:
        for n in [c["name"], *(c.get("aliases") or [])]:
            idx.setdefault(normalize(n), c["id"])
        for d in c["drugs"]:
            idx.setdefault(normalize(drug_names.get(d.lower(), d)), c["id"])
    return idx


def collect_drugs() -> dict[str, str]:
    """drug name -> class id, for our class members."""
    classes = json.loads((DATA_DIR / "drug_classes.json").read_text(encoding="utf-8"))
    drug_names = json.loads((DATA_DIR / "drug_names_en.json").read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for c in classes:
        for d in c["drugs"]:
            out[drug_names.get(d.lower(), d).lower()] = c["id"]
    return out


def find_spls(drug_name: str, max_pages: int = 3) -> list[dict]:
    spls = []
    for page in range(1, max_pages + 1):
        d = _get_json("/spls.json", {"drug_name": drug_name, "page": page})
        batch = d.get("data", [])
        if not batch:
            break
        spls.extend(batch)
        if len(batch) < 100:
            break
    return spls


def _is_repack(title: str) -> bool:
    up = title.upper()
    return any(m in up for m in REPACK_MARKERS)


def pick_spls(spls: list[dict], max_labels: int = 5) -> list[dict]:
    originals = [s for s in spls if not _is_repack(s.get("title") or "")]
    pool = originals or spls
    # prefer richer labels (longer titles often = full prescribing info)
    pool.sort(key=lambda s: -len(s.get("title") or ""))
    return pool[:max_labels]


def extract_ddi_text(xml_text: str) -> str:
    """Find the DRUG INTERACTIONS section by TITLE first (some labels have
    wrong LOINC codes), falling back to code 34067-9."""
    root = ET.fromstring(xml_text)
    ns = "{urn:hl7-org:v3}"
    best = None
    for section in root.iter(ns + "section"):
        title_el = section.find(ns + "title")
        title = "".join(title_el.itertext()) if title_el is not None else ""
        title = re.sub(r"\s+", " ", title).strip()
        texts = ["".join(t.itertext()) for t in section.iter(ns + "text")]
        body = " ".join(texts)
        norm_title = title.lower()
        if "drug interaction" in norm_title:
            body = re.sub(r"^\s*\d+\s*", "", body)
            body = re.sub(re.escape(title), "", body, count=1)
            return re.sub(r"\s+", " ", body).strip()
        if best is None:
            code_el = section.find(".//" + ns + "code[@code]")
            if code_el is not None and code_el.get("code") == DDI_CODE:
                best = (title, body)
    if best:
        title, body = best
        body = re.sub(re.escape(title), "", body, count=1)
        return re.sub(r"\s+", " ", body).strip()
    return ""


def severity_for(text: str) -> str:
    for pat, sev in _SEV_PATTERNS:
        if pat.search(text):
            return sev
    return "moderate"


def find_mentions(text: str, cls_index: dict[str, str],
                  exclude: set[str]) -> list[tuple[str, str]]:
    """(drug_name, class_id) mentioned in text, excluding source drug terms."""
    found: dict[str, str] = {}
    # match longest names first to avoid partial matches
    names = sorted(cls_index.keys(), key=len, reverse=True)
    lowered = text.lower()
    for name in names:
        if not name or len(name) < 4:
            continue
        if any(w in name for w in exclude):
            continue
        # word-boundary regex
        pat = re.compile(r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])")
        if pat.search(lowered):
            found[name] = cls_index[name]
    return list(found.items())


def process_drug(drug_name: str, cls_src: str, cls_index: dict[str, str], delay: float,
                 conn: sqlite3.Connection, max_labels: int = 5) -> int:
    spls = find_spls(drug_name)
    if not spls:
        return 0
    inserted = 0
    exclude = {normalize(drug_name)}
    seen_texts: set[str] = set()
    for spl in pick_spls(spls, max_labels):
        try:
            xml_text = _get_xml(f"/spls/{spl['setid']}.xml")
        except Exception:
            continue
        text = extract_ddi_text(xml_text)
        if not text or text in seen_texts:
            continue
        seen_texts.add(text)
        mentions = find_mentions(text, cls_index, exclude)
        neg = re.compile(r"no significant|no interaction|does not (appear|seem|significantly)|lack of|not (shown|observed|expected|reported)|unlikely|did not|no clinically|no pharmacokinetic", re.I)
        for name, cls_mentioned in mentions:
            # skip mentions whose sentence is a negation ("no significant interaction...")
            sent = ""
            for s0 in re.split(r"(?<=[.;])\s+", text):
                if name.lower() in s0.lower():
                    sent = s0
                    break
            if sent and neg.search(sent):
                continue
            if cls_mentioned == cls_src:
                continue
            sev = severity_for(text)
            # take the sentence containing the mention as effect
            sent = ""
            for s in re.split(r"(?<=[.;])\s+", text):
                if name.lower() in s.lower():
                    sent = s.strip()
                    break
            conn.execute(
                "INSERT OR IGNORE INTO dailymed_interactions"
                " (cls_src, cls_mentioned, drug_src, drug_mentioned, severity, effect, source, pair_key, trust)"
                " VALUES (?,?,?,?,?,?,?,?,1.0)",
                (cls_src, cls_mentioned, drug_name, name, sev, sent[:600],
                 f"DailyMed: {spl.get('title')} ({spl.get('setid')})",
                 f"dm:{cls_src}|{cls_mentioned}"),
            )
            inserted += 1
        time.sleep(delay)
    return inserted


def run(conn: sqlite3.Connection, limit: int | None, delay: float,
        mod: int | None = None, idx: int | None = None) -> dict:
    conn.executescript(SCHEMA)
    cls_index = _load_class_index()
    drugs = collect_drugs()
    stats = {"drugs": 0, "inserted": 0, "errors": 0}
    for drug_name, cls_src in drugs.items():
        if mod and (sum(map(ord, drug_name)) % mod) != idx:
            continue
        if limit is not None and stats["drugs"] >= limit:
            break
        stats["drugs"] += 1
        try:
            stats["inserted"] += process_drug(drug_name, cls_src, cls_index, delay, conn)
        except Exception as e:
            stats["errors"] += 1
            print(f"ERR {drug_name}: {e}")
        if stats["drugs"] % 25 == 0:
            print(f"drugs={stats['drugs']} inserted={stats['inserted']} errors={stats['errors']}")
    conn.commit()
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--mod", type=int, default=None)
    ap.add_argument("--idx", type=int, default=None)
    args = ap.parse_args()
    from .db import DB_PATH

    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    try:
        print(run(conn, args.limit, args.delay, mod=args.mod, idx=args.idx))
    finally:
        conn.close()

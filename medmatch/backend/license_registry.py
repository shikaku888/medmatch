"""Source/version/license registry (commercial compliance layer).

Two tables, adapted from the master-sources document (§21.2 Dataset release
registry + §21.3 Licence table) to SQLite:

- dataset_release: mỗi lần import một source phải có 1 row (version, sha256,
  terms_url, licence_name, commercial_status, downloaded_at...).
- source_license: licence metadata per source với các cờ cho phép commercial
  use / redistribution / modification / attribution / share-alike.

Mọi crawl source mới nên gọi register_release() khi import xong. Các cờ trả ra
bởi register_release() giúp module cảnh báo sớm khi đụng source bị cấm.

Usage:
    python -m backend.license_registry          # dump registry
    python -m backend.license_registry --seed   # seed với các source đã doc
"""
import datetime as _dt
import hashlib
import argparse
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS dataset_release (
    source_code TEXT NOT NULL,
    dataset_name TEXT NOT NULL,
    version TEXT,
    period_start TEXT,
    period_end TEXT,
    source_url TEXT,
    terms_url TEXT,
    licence_name TEXT,
    commercial_status TEXT,
    downloaded_at TEXT NOT NULL,
    sha256 TEXT,
    parser_version TEXT,
    notes TEXT,
    PRIMARY KEY (source_code, version)
);
CREATE TABLE IF NOT EXISTS source_license (
    source_code TEXT PRIMARY KEY,
    licence_name TEXT,
    licence_url TEXT,
    commercial_use_allowed INTEGER NOT NULL DEFAULT 0,
    redistribution_allowed INTEGER NOT NULL DEFAULT 0,
    modification_allowed INTEGER NOT NULL DEFAULT 0,
    attribution_required INTEGER NOT NULL DEFAULT 1,
    share_alike INTEGER NOT NULL DEFAULT 0,
    non_commercial_only INTEGER NOT NULL DEFAULT 0,
    raw_redistribution_allowed INTEGER NOT NULL DEFAULT 0,
    reviewed_at TEXT,
    review_notes TEXT
);
"""

# Legal status của từng source trong master doc — để register_release cảnh báo.
# "blocked" = commercial core bị cấm hoặc cần legal review trước.
KNOWN_LICENSES = {
    "openfda": {
        "label": "Public Domain / CC0 (openFDA, US federal)",
        "terms_url": "https://open.fda.gov/license/",
        "commercial": 1, "redist": 1, "mod": 1, "attr": 0, "share_alike": 0,
        "nc": 0, "raw_redist": 1,
    },
    "openfda_events": {
        "label": "Public Domain / CC0 (openFDA event API)",
        "terms_url": "https://open.fda.gov/license/",
        "commercial": 1, "redist": 1, "mod": 1, "attr": 0, "share_alike": 0,
        "nc": 0, "raw_redist": 1,
    },
    "rxnorm_nlm": {
        "label": "NLM-native RxNorm vocabulary (UMLS source terms: see review)",
        "terms_url": "https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html",
        "commercial": 1, "redist": 0, "mod": 0, "attr": 1, "share_alike": 0,
        "nc": 0, "raw_redist": 0,
    },
    "korea_mfds_dur": {
        "label": "data.go.kr portal — 이용허락범위 제한 없음 (no scope restriction)",
        "terms_url": "https://www.data.go.kr/catalog/15059486/openapi.json",
        "commercial": 1, "redist": 1, "mod": 1, "attr": 1, "share_alike": 0,
        "nc": 0, "raw_redist": 1,
    },
    "drugcentral": {
        "label": "CC BY-SA 4.0 (DrugCentral)",
        "terms_url": "https://drugcentral.org/terms",
        "commercial": 1, "redist": 1, "mod": 1, "attr": 1, "share_alike": 1,
        "nc": 0, "raw_redist": 1,
    },
    "chembl": {
        "label": "CC BY-SA 3.0 (ChEMBL)",
        "terms_url": "https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions",
        "commercial": 1, "redist": 1, "mod": 1, "attr": 1, "share_alike": 1,
        "nc": 0, "raw_redist": 1,
    },
    "pharmgkb": {
        "label": "CC BY-SA 4.0 (PharmGKB via ClinPGx)",
        "terms_url": "https://www.pharmgkb.org/page/dataUsagePolicy",
        "commercial": 1, "redist": 1, "mod": 1, "attr": 1, "share_alike": 1,
        "nc": 0, "raw_redist": 1,
    },
    "figshare_cyp450": {
        "label": "CC BY 4.0 (Figshare CYP450 substrate dataset)",
        "terms_url": "https://doi.org/10.6084/m9.figshare.26630515.v4",
        "commercial": 1, "redist": 1, "mod": 1, "attr": 1, "share_alike": 0,
        "nc": 0, "raw_redist": 1,
    },
    "mendeley_drug_food": {
        "label": "CC BY 4.0 (Mendeley Drug-Food Interactions)",
        "terms_url": "https://data.mendeley.com/datasets/xgyt8fhgps/1",
        "commercial": 1, "redist": 1, "mod": 1, "attr": 1, "share_alike": 0,
        "nc": 0, "raw_redist": 1,
    },
    "zenodo_ddi_2026": {
        "label": "CC BY 4.0 (Zenodo DDI release)",
        "terms_url": "https://creativecommons.org/licenses/by/4.0/",
        "commercial": 1, "redist": 1, "mod": 1, "attr": 1, "share_alike": 0,
        "nc": 0, "raw_redist": 1,
    },
    "open_targets": {
        "label": "CC0 generated Open Targets data; upstream sources require review",
        "terms_url": "https://platform-docs.opentargets.org/licence",
        "commercial": 1, "redist": 1, "mod": 1, "attr": 0, "share_alike": 0,
        "nc": 0, "raw_redist": 1,
    },
    "lactmed": {
        "label": "LactMed/NLM — US federal government work, public domain (bulk FTP release)",
        "terms_url": "https://www.ncbi.nlm.nih.gov/books/NBK501922/",
        "commercial": 1, "redist": 1, "mod": 1, "attr": 0, "share_alike": 0,
        "nc": 0, "raw_redist": 1,
    },
    "medlineplus": {
        "label": "MedlinePlus content; outbound reference preferred pending rights review",
        "terms_url": "https://medlineplus.gov/about/using/usingcontent",
        "commercial": 0, "redist": 0, "mod": 0, "attr": 1, "share_alike": 0,
        "nc": 1, "raw_redist": 0,
    },
    "livertox": {
        "label": "LiverTox/NLM reference pointer; bulk terms require verification",
        "terms_url": "https://www.ncbi.nlm.nih.gov/books/NBK548196/",
        "commercial": 0, "redist": 0, "mod": 0, "attr": 1, "share_alike": 0,
        "nc": 1, "raw_redist": 0,
    },
    "mespen_glossaries": {
        "label": "CC BY 4.0 (MeSpEn_Glossaries medical glossaries)",
        "terms_url": "https://creativecommons.org/licenses/by/4.0/",
        "commercial": 1, "redist": 1, "mod": 1, "attr": 1, "share_alike": 0,
        "nc": 0, "raw_redist": 1,
    },
    "onsides": {
        "label": "CC BY 4.0 (OnSIDES)",
        "terms_url": "https://github.com/tatonetti-lab/onsides",
        "commercial": 1, "redist": 1, "mod": 1, "attr": 1, "share_alike": 0,
        "nc": 0, "raw_redist": 1,
    },
    "dailymed": {
        "label": "Public Domain / CC0 (DailyMed SPL, US federal)",
        "terms_url": "https://dailymed.nlm.nih.gov/dailymed/disclaimer.cfm",
        "commercial": 1, "redist": 1, "mod": 1, "attr": 0, "share_alike": 0,
        "nc": 0, "raw_redist": 1,
    },
    "canada_vigilance": {
        "label": "Open Government Licence – Canada (CVOD/data extract)",
        "terms_url": "https://open.canada.ca/en/open-government-licence-canada",
        "commercial": 1, "redist": 1, "mod": 1, "attr": 1, "share_alike": 0,
        "nc": 0, "raw_redist": 1,
    },
    "canada_open": {
        "label": "Open Government Licence – Canada (Health Canada) — verify per dataset",
        "terms_url": "https://open.canada.ca/en/open-government-licence-canada",
        "commercial": 1, "redist": 1, "mod": 1, "attr": 1, "share_alike": 0,
        "nc": 0, "raw_redist": 1,
    },
    "faers": {
        "label": "Public Domain / CC0 (US FDA AEMS/FAERS quarterly files)",
        "terms_url": "https://open.fda.gov/license/",
        "commercial": 1, "redist": 1, "mod": 1, "attr": 0, "share_alike": 0,
        "nc": 0, "raw_redist": 1,
    },
    "caers": {
        "label": "Public Domain / CC0 (openFDA CAERS food/supplement/cosmetic events)",
        "terms_url": "https://open.fda.gov/license/",
        "commercial": 1, "redist": 1, "mod": 1, "attr": 0, "share_alike": 0,
        "nc": 0, "raw_redist": 1,
    },
    "fda_recalls": {
        "label": "Public Domain / CC0 (openFDA enforcement reports, drug + food)",
        "terms_url": "https://open.fda.gov/license/",
        "commercial": 1, "redist": 1, "mod": 1, "attr": 0, "share_alike": 0,
        "nc": 0, "raw_redist": 1,
    },
    "vigi": {
        "label": "WHO VigiBase access (public vigiaccess.org view — NOT a bulk mirror)",
        "terms_url": "https://www.who-umc.org/vigibase/vigibase-services/",
        "commercial": 0, "redist": 0, "mod": 0, "attr": 1, "share_alike": 0,
        "nc": 1, "raw_redist": 0,
    },
    "tapirro": {
        "label": "MIT (tapirro herb-drug-interaction-checker)",
        "terms_url": "https://github.com/tapirro/herb-drug-interaction-checker",
        "commercial": 1, "redist": 1, "mod": 1, "attr": 1, "share_alike": 0,
        "nc": 0, "raw_redist": 1,
    },
    "fda_curated": {
        "label": "Public-domain FDA labeling facts, MedMatch curated",
        "terms_url": "https://open.fda.gov/license/",
        "commercial": 1, "redist": 1, "mod": 1, "attr": 0, "share_alike": 0,
        "nc": 0, "raw_redist": 0,
    },
    "cyp_roles": {
        "label": "MedMatch derived CYP role catalog; upstream sources separately attributed",
        "terms_url": "",
        "commercial": 1, "redist": 1, "mod": 1, "attr": 1, "share_alike": 0,
        "nc": 0, "raw_redist": 0,
    },
    "cyp_inference": {
        "label": "MedMatch derived CYP inference; upstream sources separately attributed",
        "terms_url": "",
        "commercial": 1, "redist": 1, "mod": 1, "attr": 1, "share_alike": 0,
        "nc": 0, "raw_redist": 0,
    },
    "suppai": {
        "label": "SUPP.AI API — commercial reuse requires terms verification",
        "terms_url": "https://supp.ai/",
        "commercial": 0, "redist": 0, "mod": 0, "attr": 1, "share_alike": 0,
        "nc": 1, "raw_redist": 0,
    },
    "idisk": {
        "label": "iDISK/MSKCC interaction data — commercial reuse requires terms verification",
        "terms_url": "https://www.mskcc.org/",
        "commercial": 0, "redist": 0, "mod": 0, "attr": 1, "share_alike": 0,
        "nc": 1, "raw_redist": 0,
    },
    # ---------- blocked-only records (không crawl vào commercial core) ----------
    "ddinter": {
        "label": "CC BY-NC-SA 4.0 (DDInter)",
        "terms_url": "https://ddinter.scbdd.com/",
        "commercial": 0, "redist": 0, "mod": 0, "attr": 1, "share_alike": 1,
        "nc": 1, "raw_redist": 0,
    },
    "kids_dur_csv": {
        "label": "KIDS DUR CSV — non-commercial unless approved",
        "terms_url": "https://www.kids.or.kr/",
        "commercial": 0, "redist": 0, "mod": 0, "attr": 1, "share_alike": 0,
        "nc": 1, "raw_redist": 0,
    },
    "who_newsletter": {
        "label": "WHO Pharmaceuticals Newsletter — CC BY-NC-SA IGO default",
        "terms_url": "https://www.who.int/publications/i/item/pharmaceuticals-newsletter",
        "commercial": 0, "redist": 0, "mod": 0, "attr": 1, "share_alike": 1,
        "nc": 1, "raw_redist": 0,
    },
    "drugbank_free": {
        "label": "DrugBank free/academic — commercial requires paid licence",
        "terms_url": "https://go.drugbank.com/",
        "commercial": 0, "redist": 0, "mod": 0, "attr": 1, "share_alike": 0,
        "nc": 1, "raw_redist": 0,
    },
    "sider": {
        "label": "SIDER — licence must be re-verified",
        "terms_url": "https://sideeffects.embl.de/",
        "commercial": 0, "redist": 0, "mod": 0, "attr": 1, "share_alike": 0,
        "nc": 1, "raw_redist": 0,
    },
    "twosides": {
        "label": "TWOSIDES/NSIDES — licence/reuse must be verified",
        "terms_url": "https://github.com/tatonetti-lab/nsides-release",
        "commercial": 0, "redist": 0, "mod": 0, "attr": 1, "share_alike": 0,
        "nc": 1, "raw_redist": 0,
    },
    "empi_pending": {
        "label": "EMA ePI — content reuse review pending",
        "terms_url": "https://epi.developer.ema.europa.eu/",
        "commercial": 0, "redist": 0, "mod": 0, "attr": 1, "share_alike": 0,
        "nc": 1, "raw_redist": 0,
    },
    "pmda_pending": {
        "label": "PMDA package inserts — legal review required",
        "terms_url": "https://www.pmda.go.jp/",
        "commercial": 0, "redist": 0, "mod": 0, "attr": 1, "share_alike": 0,
        "nc": 1, "raw_redist": 0,
    },
    "jader": {
        "label": "JADER — secondary sale/distribution prohibited (PMDA)",
        "terms_url": "https://www.pmda.go.jp/safety/info-services/drugs/adr-info/suspected-adr/0003.html",
        "commercial": 0, "redist": 0, "mod": 0, "attr": 1, "share_alike": 0,
        "nc": 1, "raw_redist": 0,
    },
}

BLOCKED_STATUS = ("restricted_private", "research_only")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure(conn) -> None:
    conn.executescript(SCHEMA)


def seed_licenses(conn, only: set[str] | None = None) -> int:
    """Điền source_license cho các source có trong KNOWN_LICENSES."""
    ensure(conn)
    n = 0
    for code, lic in KNOWN_LICENSES.items():
        if only and code not in only:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO source_license"
            " (source_code, licence_name, licence_url, commercial_use_allowed,"
            "  redistribution_allowed, modification_allowed, attribution_required,"
            "  share_alike, non_commercial_only, raw_redistribution_allowed,"
            "  reviewed_at, review_notes)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (code, lic["label"], lic["terms_url"], int(lic["commercial"]),
             int(lic["redist"]), int(lic["mod"]), int(lic["attr"]),
             int(lic["share_alike"]), int(lic["nc"]), int(lic["raw_redist"]),
             _dt.date.today().isoformat(), "Seeded from master-sources triage (not legal advice)"),
        )
        n += 1
    conn.commit()
    return n


def license_flags(conn, source_code: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM source_license WHERE source_code = ?", (source_code,)
    ).fetchone()
    if not row:
        return None
    return {k: row[k] for k in row.keys() if k != "source_license_id"}


def assert_commercial_ok(conn, source_code: str) -> bool:
    """True nếu source đã seed & cho phép commercial use; còn lại cảnh báo."""
    lic = license_flags(conn, source_code)
    if lic is None:
        return False
    if not lic.get("commercial_use_allowed"):
        raise RuntimeError(
            f"source `{source_code}` được đánh dấu non-commercial trong registry"
            f" ({lic.get('licence_name')}) — không crawl vào DB commercial."
        )
    return True


def register_release(conn, source_code: str, dataset_name: str, version: str | None = None,
                     period_start: str | None = None, period_end: str | None = None,
                     source_url: str | None = None, terms_url: str | None = None,
                     licence_name: str | None = None, commercial_status: str | None = None,
                     downloaded_at: str | None = None, sha256: str | None = None,
                     parser_version: str | None = None, notes: str | None = None,
                     strict: bool = True) -> None:
    ensure(conn)
    lic = license_flags(conn, source_code)
    if strict:
        assert_commercial_ok(conn, source_code)
    conn.execute(
        "INSERT OR REPLACE INTO dataset_release"
        " (source_code, dataset_name, version, period_start, period_end, source_url,"
        "  terms_url, licence_name, commercial_status, downloaded_at, sha256,"
        "  parser_version, notes)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (source_code, dataset_name, version, period_start, period_end,
         source_url, terms_url or (lic["licence_url"] if lic else None),
         licence_name or (lic["licence_name"] if lic else None),
         commercial_status or ("core_open" if lic and lic["commercial_use_allowed"] else "restricted_private"),
         downloaded_at or _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
         sha256, parser_version, notes),
    )
    conn.commit()


def dump(conn) -> str:
    ensure(conn)
    out = []
    for r in conn.execute("SELECT * FROM dataset_release ORDER BY source_code, downloaded_at"):
        out.append(
            f"[{r['source_code']}] {r['dataset_name']} v{r['version'] or '?'} "
            f"({r['commercial_status'] or '?'}) sha256={str(r['sha256'])[:12] or '?'} "
            f"lic={r['licence_name'] or '?'}"
        )
    for r in conn.execute("SELECT * FROM source_license ORDER BY source_code"):
        out.append(
            f"LIC [{r['source_code']}] commercial={r['commercial_use_allowed']} "
            f"share_alike={r['share_alike']} nc={r['non_commercial_only']} {r['licence_name'] or ''}"
        )
    return "\n".join(out)


if __name__ == "__main__":
    from .db import DB_PATH

    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true", help="seed source_license từ KNOWN_LICENSES")
    args = ap.parse_args()
    from .db import get_conn

    conn = get_conn()
    try:
        if args.seed:
            print(f"seeded {seed_licenses(conn)} license rows")
        print(dump(conn))
    finally:
        conn.close()
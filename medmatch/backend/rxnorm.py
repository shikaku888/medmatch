"""Map drug names to RxNorm RxCUIs (free API, no key).

RxCUI is the join key for cross-source dedup: SUPP.AI drugs and our
drug_classes members both get normalized to RxCUI before pair matching.
Exact matches are trusted; approximate fallbacks are flagged and must
be reviewed before use in dedup.
"""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
CACHE_PATH = DATA_DIR / "rxnorm_map.json"
BASE = "https://rxnav.nlm.nih.gov/REST"


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.load(r)


def lookup_rxcui(name: str) -> tuple[str, str] | None:
    """Return (rxcui, source) or None. source: 'exact' | 'approx'."""
    q = urllib.parse.quote(name)
    d = _get(f"{BASE}/rxcui.json?name={q}")
    ids = d.get("idGroup", {}).get("rxnormId")
    if ids:
        return ids[0], "exact"
    d = _get(f"{BASE}/approximateTerm.json?term={q}&maxEntries=1")
    cands = d.get("approximateGroup", {}).get("candidate", [])
    if cands:
        return cands[0]["rxcui"], "approx"
    return None


def collect_names() -> list[str]:
    names: set[str] = set()
    drug_names = json.loads((DATA_DIR / "drug_names_en.json").read_text(encoding="utf-8"))
    names.update(v.lower() for v in drug_names.values())
    classes = json.loads((DATA_DIR / "drug_classes.json").read_text(encoding="utf-8"))
    for c in classes:
        for d in c["drugs"]:
            names.add(drug_names.get(d.lower(), d).lower())
    return sorted(names)


def build_map(names: list[str], delay: float = 0.3) -> dict:
    out: dict[str, dict] = {}
    for i, name in enumerate(names):
        try:
            hit = lookup_rxcui(name)
        except Exception as e:  # network hiccup -> skip, rerun fills gaps
            print(f"ERR {name}: {e}")
            hit = None
        if hit:
            out[name] = {"rxcui": hit[0], "source": hit[1]}
        if (i + 1) % 25 == 0:
            print(f"{i + 1}/{len(names)} mapped={len(out)}")
        time.sleep(delay)
    return out


if __name__ == "__main__":
    names = collect_names()
    mapping = build_map(names)
    CACHE_PATH.write_text(json.dumps(mapping, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote {len(mapping)}/{len(names)} mappings to {CACHE_PATH}")

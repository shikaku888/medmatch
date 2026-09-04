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
import re
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
MULTILINGUAL_VOCAB_PATH = DATA_DIR / "multilingual_medical_vocabulary.json"

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
CREATE TABLE IF NOT EXISTS drug_name_mapping (
    source TEXT NOT NULL,
    raw_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    rxcui TEXT,
    confidence REAL NOT NULL,
    match_method TEXT NOT NULL,
    reviewed INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (source, raw_name)
);
CREATE INDEX IF NOT EXISTS idx_drug_name_mapping_entity
    ON drug_name_mapping (entity_type, entity_id);
CREATE TABLE IF NOT EXISTS drug_name_mapping_component (
    source TEXT NOT NULL,
    raw_name TEXT NOT NULL,
    component_index INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    rxcui TEXT NOT NULL,
    confidence REAL NOT NULL,
    match_method TEXT NOT NULL,
    PRIMARY KEY (source, raw_name, component_index)
);
CREATE INDEX IF NOT EXISTS idx_drug_name_mapping_component_entity
    ON drug_name_mapping_component (entity_type, entity_id);
CREATE TABLE IF NOT EXISTS drug_name_mapping_review (
    source TEXT NOT NULL,
    raw_name TEXT NOT NULL,
    reason TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    rxcui TEXT,
    confidence REAL NOT NULL,
    candidate_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    note TEXT,
    reviewed_at TEXT,
    PRIMARY KEY (source, raw_name)
);
CREATE INDEX IF NOT EXISTS idx_drug_name_mapping_review_status
    ON drug_name_mapping_review (status, source);
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


def _token_fp(s: str) -> frozenset:
    return frozenset(w for w in re.sub(r"[^A-Za-z0-9]+", " ", s.lower()).split())
def _normalized_name(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^0-9A-Za-z]+", " ", name.casefold())).strip()


def _class_name_index(conn: sqlite3.Connection) -> dict[frozenset, str]:
    index: dict[frozenset, str] = {}
    for row in conn.execute("SELECT id, name_en, drugs, aliases FROM drug_classes"):
        names = [row["name_en"], row["id"], *json.loads(row["drugs"] or "[]"),
                 *json.loads(row["aliases"] or "[]")]
        for name in names:
            if name:
                index.setdefault(_token_fp(name), row["id"])
    return index


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _rxnorm_concepts(conn: sqlite3.Connection) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    columns = _table_columns(conn, "rxnorm_concepts")
    if not columns:
        return {}, {}
    active_filter = " WHERE active = 1" if "active" in columns else ""
    by_cui: dict[str, dict] = {}
    by_name: dict[str, list[dict]] = {}
    for row in conn.execute(
        "SELECT rxcui, name, tty FROM rxnorm_concepts" + active_filter
    ):
        item = dict(row)
        by_cui[item["rxcui"]] = item
        by_name.setdefault(_normalized_name(item["name"]), []).append(item)
    return by_cui, by_name


def _rxnorm_canonical_ingredients(
    conn: sqlite3.Connection,
    rxcui: str,
    concepts: dict[str, dict],
    cache: dict[str, list[str]],
    seen: set[str] | None = None,
) -> list[str]:
    if rxcui in cache:
        return cache[rxcui]
    seen = set() if seen is None else seen
    if rxcui in seen:
        return []
    seen.add(rxcui)
    concept = concepts.get(rxcui)
    if not concept:
        return []
    tty = concept.get("tty")
    if tty == "IN":
        cache[rxcui] = [rxcui]
        return cache[rxcui]
    if tty == "PIN":
        if not _table_columns(conn, "rxnorm_relations"):
            cache[rxcui] = [rxcui]
            return cache[rxcui]
        rows = conn.execute(
            "SELECT rxcui2 FROM rxnorm_relations "
            "WHERE rxcui1 = ? AND rela = 'has_form'",
            (rxcui,),
        ).fetchall()
        parents = [
            row["rxcui2"] for row in rows
            if concepts.get(row["rxcui2"], {}).get("tty") == "IN"
        ]
        cache[rxcui] = parents[:1] or [rxcui]
        return cache[rxcui]
    if not _table_columns(conn, "rxnorm_relations"):
        return []

    direct = conn.execute(
        "SELECT rxcui2, rela FROM rxnorm_relations "
        "WHERE rxcui1 = ? AND rela IN "
        "('has_tradename', 'ingredient_of', 'precise_ingredient_of', 'has_form')",
        (rxcui,),
    ).fetchall()
    ingredients: list[str] = []
    for row in direct:
        target = concepts.get(row["rxcui2"])
        if target and target.get("tty") in {"IN", "PIN"}:
            ingredients.extend(
                _rxnorm_canonical_ingredients(
                    conn, row["rxcui2"], concepts, cache, seen.copy()
                )
            )
    if not ingredients:
        components = conn.execute(
            "SELECT rxcui2 FROM rxnorm_relations "
            "WHERE rxcui1 = ? AND rela IN ('constitutes', 'has_ingredient')",
            (rxcui,),
        ).fetchall()
        for row in components:
            ingredients.extend(
                _rxnorm_canonical_ingredients(
                    conn, row["rxcui2"], concepts, cache, seen.copy()
                )
            )
    cache[rxcui] = list(dict.fromkeys(ingredients))
    return cache[rxcui]


_RXNORM_NON_SPECIFIC_TOKENS = {
    "acid", "anhydrous", "acetate", "bitartrate", "capsule", "chloride",
    "citrate", "delayed", "dextrose", "er", "extended", "form", "hcl",
    "hydrochloride", "human", "inhalation", "liquid", "maleate", "mg",
    "mcg", "monohydrate", "oral", "ophthalmic", "potassium", "release",
    "sodium", "solution", "succinate", "sulfate", "tablet", "tartrate",
    "topical", "water", "xr",
}


def _is_formulation_token(token: str) -> bool:
    return bool(re.fullmatch(r"\d+(?:mg|mcg|g|ml|iu|%)?", token))


def _rxnorm_token_candidates(
    fragment: str,
    active_names: dict[str, list[str]],
) -> list[str]:
    fragment_tokens = set(_normalized_name(fragment).split())
    if not fragment_tokens:
        return []
    candidates: list[tuple[int, int, str]] = []
    for name, ids in active_names.items():
        name_tokens = set(name.split())
        meaningful_tokens = name_tokens - _RXNORM_NON_SPECIFIC_TOKENS
        extra_tokens = fragment_tokens - name_tokens
        if (
            not meaningful_tokens
            or not meaningful_tokens <= fragment_tokens
            or any(
                token not in _RXNORM_NON_SPECIFIC_TOKENS
                and not _is_formulation_token(token)
                for token in extra_tokens
            )
        ):
            continue
        candidates.append((len(meaningful_tokens), len(name), name))
    if not candidates:
        return []
    best_size = max(item[0] for item in candidates)
    best = [item for item in candidates if item[0] == best_size]
    if len({item[2] for item in best}) != 1:
        return []
    return list(dict.fromkeys(active_names[best[0][2]]))


def _resolve_rxnorm_name(
    conn: sqlite3.Connection,
    raw_name: str,
    concepts: dict[str, dict],
    by_name: dict[str, list[dict]],
    curated: dict[str, dict],
    canonical_cache: dict[str, list[str]],
    active_names: dict[str, list[str]],
    depth: int = 0,
) -> tuple[list[str], str]:
    if depth > 2:
        return [], "unmapped"
    normalized = _normalized_name(raw_name)
    alias = _RXNORM_ALIASES.get(normalized)
    if alias:
        ids, _ = _resolve_rxnorm_name(
            conn, alias, concepts, by_name, curated, canonical_cache,
            active_names, depth + 1,
        )
        if ids:
            return ids, "rxnorm_alias"

    trademark_stripped = re.sub(
        r"\s*\((?:r|tm)\)\s*$", "", raw_name, flags=re.I
    ).strip()
    if trademark_stripped != raw_name:
        ids, _ = _resolve_rxnorm_name(
            conn, trademark_stripped, concepts, by_name, curated,
            canonical_cache, active_names, depth + 1,
        )
        if ids:
            return ids, "rxnorm_trademark_stripped"

    suffix_tokens = normalized.split()
    while len(suffix_tokens) > 1 and (
        suffix_tokens[-1] in _RXNORM_FORMULATION_SUFFIXES
        or _is_formulation_token(suffix_tokens[-1])
    ):
        suffix_tokens.pop()
    suffix_base = " ".join(suffix_tokens)
    if suffix_base != normalized:
        ids, _ = _resolve_rxnorm_name(
            conn, suffix_base, concepts, by_name, curated, canonical_cache,
            active_names, depth + 1,
        )
        if ids:
            return ids, "rxnorm_formulation_suffix"

    candidates = sorted(
        by_name.get(normalized, []),
        key=lambda item: {"IN": 0, "PIN": 1, "MIN": 2, "BN": 3}.get(item.get("tty"), 10),
    )
    curated_item = curated.get(normalized)
    if curated_item and curated_item.get("rxcui") in concepts:
        candidates = [concepts[curated_item["rxcui"]]] + [
            item for item in candidates if item["rxcui"] != curated_item["rxcui"]
        ]
    for candidate in candidates:
        ids = _rxnorm_canonical_ingredients(
            conn, candidate["rxcui"], concepts, canonical_cache
        )
        if ids:
            return ids, (
                "pharmgkb_exact"
                if candidate.get("match_source") == "pharmgkb"
                else "rxnorm_exact"
            )

    stripped = re.sub(r"^\s*[.]?\s*\([RS]\)-\s*", "", raw_name, flags=re.I).strip()
    if stripped != raw_name:
        ids, _ = _resolve_rxnorm_name(
            conn, stripped, concepts, by_name, curated, canonical_cache, active_names, depth + 1
        )
        if ids:
            return ids, "rxnorm_stereo_stripped"

    parenthetical = re.search(r"\(([^()]+)\)", raw_name)
    if parenthetical:
        ids, _ = _resolve_rxnorm_name(
            conn, parenthetical.group(1), concepts, by_name, curated,
            canonical_cache, active_names, depth + 1,
        )
        if ids:
            return ids, "rxnorm_parenthetical"

    parts = [
        part.strip()
        for part in re.split(r"\s*/\s*|\s+(?:and|with)\s+|\s*,\s*", raw_name, flags=re.I)
        if part.strip()
    ]
    if len(parts) > 1:
        component_ids: list[str] = []
        for part in parts:
            ids, _ = _resolve_rxnorm_name(
                conn, part, concepts, by_name, curated, canonical_cache,
                active_names, depth + 1,
            )
            if not ids:
                ids = _rxnorm_token_candidates(part, active_names)
            if not ids:
                return [], "unmapped"
            component_ids.extend(ids)
        return list(dict.fromkeys(component_ids)), "rxnorm_components"

    ids = _rxnorm_token_candidates(raw_name, active_names)
    if ids:
        return ids, "rxnorm_token_exact"
    return [], "unmapped"


def _rxnorm_ingredient(conn: sqlite3.Connection, rxcui: str, tty: str | None) -> tuple[str, str]:
    concepts, _ = _rxnorm_concepts(conn)
    actual_tty = tty or concepts.get(rxcui, {}).get("tty")
    ids = _rxnorm_canonical_ingredients(conn, rxcui, concepts, {})
    if ids:
        return ids[0], concepts.get(ids[0], {}).get("name", "")
    if actual_tty in {"IN", "PIN"}:
        return rxcui, concepts.get(rxcui, {}).get("name", "")
    return rxcui, ""


def _rxnorm_lookup(conn: sqlite3.Connection) -> dict[str, dict]:
    path = DATA_DIR / "rxnorm_map.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    concepts, _ = _rxnorm_concepts(conn)
    by_name: dict[str, dict] = {}
    for name, item in raw.items():
        normalized = _normalized_name(name)
        if not normalized or not item.get("rxcui"):
            continue
        rxcui = str(item["rxcui"])
        tty = item.get("tty") or concepts.get(rxcui, {}).get("tty")
        existing = by_name.get(normalized)
        if existing is None or tty in {"IN", "PIN"}:
            by_name[normalized] = {"rxcui": rxcui, "tty": tty}
    return by_name


_RXNORM_ALIASES = {
    "acetylsalicylic acid": "aspirin",
    "adrenalin": "epinephrine",
    "ethinylestradiol": "ethinyl estradiol",
}
_RXNORM_FORMULATION_SUFFIXES = {
    "cr", "d", "dpi", "er", "es", "hfa", "iv", "la", "odt", "pm", "sr", "xl", "xr",
}
_NON_DRUG_EXACT_NAMES = {
    "acetate",
    "methamidophos",
}


def _looks_non_drug(raw_name: str) -> bool:
    normalized = _normalized_name(raw_name)
    return normalized in _NON_DRUG_EXACT_NAMES or bool(re.search(
        r"\b(collection system|diagnostic device|test system|assay|reagent|"
        r"buffer|culture medium|placebo|diluent|catheter|syringe|needle|"
        r"swab|sensor|specimen|kit)\b",
        normalized,
    ))


def _active_name_index(
    concepts: dict[str, dict],
    canonical_cache: dict[str, list[str]],
    conn: sqlite3.Connection,
) -> dict[str, list[str]]:
    active_names: dict[str, list[str]] = {}
    for concept in concepts.values():
        if concept.get("tty") not in {"IN", "PIN"}:
            continue
        ids = _rxnorm_canonical_ingredients(
            conn, concept["rxcui"], concepts, canonical_cache
        )
        if not ids:
            continue
        for ingredient_id in ids:
            ingredient = concepts.get(ingredient_id)
            if not ingredient:
                continue
            full_name = _normalized_name(ingredient["name"])
            names = {full_name}
            names.add(" ".join(
                token for token in full_name.split()
                if token not in _RXNORM_NON_SPECIFIC_TOKENS
            ))
            for name in names:
                if name:
                    active_names.setdefault(name, []).append(ingredient_id)
    return {
        name: list(dict.fromkeys(ids))
        for name, ids in active_names.items()
    }


def _pharmgkb_rxnorm_index(
    conn: sqlite3.Connection,
    concepts: dict[str, dict],
    canonical_cache: dict[str, list[str]],
) -> dict[str, list[str]]:
    if not _table_columns(conn, "pharmgkb_drugs"):
        return {}
    candidates: dict[str, set[frozenset[str]]] = {}
    for row in conn.execute(
        "SELECT name, generic_names, trade_names, brand_mixtures, rxnorm, type "
        "FROM pharmgkb_drugs"
    ):
        if (row["type"] or "").strip() in {"Drug Class", "Pathway"}:
            continue
        component_ids: set[str] = set()
        for rxcui in (row["rxnorm"] or "").split():
            if rxcui in concepts:
                component_ids.update(
                    _rxnorm_canonical_ingredients(
                        conn, rxcui, concepts, canonical_cache
                    )
                )
        if not component_ids:
            continue
        labels = [row["name"]]
        for field in ("generic_names", "trade_names"):
            labels.extend((row[field] or "").replace(";", ",").split(","))
        labels.extend((row["brand_mixtures"] or "").split(";"))
        component_set = frozenset(component_ids)
        for label in labels:
            normalized = _normalized_name(label.strip().strip('"'))
            if normalized:
                candidates.setdefault(normalized, set()).add(component_set)
    return {
        name: sorted(next(iter(component_sets)))
        for name, component_sets in candidates.items()
        if len(component_sets) == 1
    }


def _class_synonym_index(conn: sqlite3.Connection) -> dict[str, str]:
    if not _table_columns(conn, "ingredient_synonyms"):
        return {}
    known_classes = {
        row["id"] for row in conn.execute("SELECT id FROM drug_classes")
    }
    candidates: dict[str, set[str]] = {}
    for row in conn.execute(
        "SELECT synonym, entity_id FROM ingredient_synonyms "
        "WHERE kind = 'drug_class'"
    ):
        normalized = _normalized_name(row["synonym"])
        if normalized and row["entity_id"] in known_classes:
            candidates.setdefault(normalized, set()).add(row["entity_id"])
    return {
        name: next(iter(entity_ids))
        for name, entity_ids in candidates.items()
        if len(entity_ids) == 1
    }


def build_drug_name_mapping(conn: sqlite3.Connection) -> dict[str, int]:
    """Map Zenodo names to canonical RxNorm ingredients without fuzzy matches.

    A product/brand may contain multiple active ingredients.  The legacy
    one-row mapping keeps the first canonical ingredient for compatibility;
    all components are stored in ``drug_name_mapping_component`` and are used
    by the unified builder and runtime engine.
    """
    conn.executescript(SCHEMA)
    conn.execute("DELETE FROM drug_name_mapping")
    conn.execute("DELETE FROM drug_name_mapping_component")
    if _table_columns(conn, "rxnorm_relations"):
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rxnorm_relations_source_rela "
            "ON rxnorm_relations (rxcui1, rela, rxcui2)"
        )
    source_names: dict[str, set[str]] = {}
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='zenodo_ddi_2026'"
    ).fetchone():
        source_names["zenodo_ddi_2026"] = {
            row["name"]
            for row in conn.execute(
                "SELECT drug_a AS name FROM zenodo_ddi_2026 "
                "UNION SELECT drug_b AS name FROM zenodo_ddi_2026"
            )
            if row["name"]
        }
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='drug_drug'"
    ).fetchone():
        source_names["drug_drug"] = {
            row["name"]
            for row in conn.execute(
                "SELECT drug_a AS name FROM drug_drug WHERE drug_a IS NOT NULL "
                "UNION SELECT drug_b AS name FROM drug_drug WHERE drug_b IS NOT NULL"
            )
            if row["name"]
        }

    curated = _rxnorm_lookup(conn)
    concepts, by_name = _rxnorm_concepts(conn)
    canonical_cache: dict[str, list[str]] = {}
    pharmgkb_names = _pharmgkb_rxnorm_index(conn, concepts, canonical_cache)
    for name, component_ids in pharmgkb_names.items():
        for component_id in component_ids:
            by_name.setdefault(name, []).append({
                "rxcui": component_id,
                "tty": concepts[component_id]["tty"],
                "match_source": "pharmgkb",
            })
    active_names = _active_name_index(concepts, canonical_cache, conn)
    classes = _class_name_index(conn)
    class_synonyms = _class_synonym_index(conn)
    counts = {"mapped": 0, "unmapped": 0}
    for source, names in source_names.items():
        for raw_name in sorted(names):
            raw_normalized = _normalized_name(raw_name)
            entity_type = entity_id = rxcui = None
            confidence = 0.0
            match_method = "unmapped"
            component_ids, match_method = _resolve_rxnorm_name(
                conn, raw_name, concepts, by_name, curated, canonical_cache,
                active_names,
            )
            if component_ids:
                entity_type = "drug_ingredient"
                entity_id = component_ids[0]
                rxcui = component_ids[0]
                confidence = {
                    "rxnorm_exact": 1.0,
                    "pharmgkb_exact": 0.98,
                    "rxnorm_alias": 0.98,
                    "rxnorm_components": 0.98,
                    "rxnorm_formulation_suffix": 0.98,
                    "rxnorm_parenthetical": 0.98,
                    "rxnorm_stereo_stripped": 0.98,
                    "rxnorm_trademark_stripped": 0.98,
                    "rxnorm_token_exact": 0.9,
                }.get(match_method, 0.9)
                ingredient_names = [
                    concepts[item]["name"]
                    for item in component_ids
                    if item in concepts
                ]
                normalized = " + ".join(
                    _normalized_name(name) for name in ingredient_names
                ) or raw_normalized
                for index, component_id in enumerate(component_ids):
                    conn.execute(
                        "INSERT INTO drug_name_mapping_component "
                        "(source, raw_name, component_index, entity_type, entity_id, "
                        "rxcui, confidence, match_method) VALUES (?,?,?,?,?,?,?,?)",
                        (
                            source,
                            raw_name,
                            index,
                            "drug_ingredient",
                            component_id,
                            component_id,
                            confidence,
                            match_method,
                        ),
                    )
            elif _looks_non_drug(raw_name):
                entity_type = "non_drug"
                match_method = "excluded_non_drug"
                normalized = raw_normalized
            else:
                class_id = classes.get(_token_fp(raw_name))
                match_method = "class_token_exact" if class_id else match_method
                if not class_id:
                    class_id = class_synonyms.get(raw_normalized)
                    if class_id:
                        match_method = "class_synonym_exact"
                if class_id:
                    entity_type = "drug_class"
                    entity_id = class_id
                    confidence = 0.8 if match_method == "class_token_exact" else 0.75
                normalized = raw_normalized
            conn.execute(
                "INSERT INTO drug_name_mapping "
                "(source, raw_name, normalized_name, entity_type, entity_id, rxcui, "
                "confidence, match_method, reviewed) VALUES (?,?,?,?,?,?,?,?,0)",
                (source, raw_name, normalized, entity_type, entity_id, rxcui,
                 confidence, match_method),
            )
            review_methods = {
                "unmapped",
                "excluded_non_drug",
                "class_token_exact",
                "class_synonym_exact",
                "rxnorm_token_exact",
            }
            if match_method in review_methods:
                candidate_json = json.dumps({
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "rxcui": rxcui,
                    "component_ids": component_ids,
                }, sort_keys=True)
                previous = conn.execute(
                    "SELECT status, reason, candidate_json "
                    "FROM drug_name_mapping_review "
                    "WHERE source = ? AND raw_name = ?",
                    (source, raw_name),
                ).fetchone()
                if previous and (
                    previous["reason"] == match_method
                    and previous["candidate_json"] == candidate_json
                ):
                    conn.execute(
                        "UPDATE drug_name_mapping_review "
                        "SET confidence = ? "
                        "WHERE source = ? AND raw_name = ?",
                        (confidence, source, raw_name),
                    )
                else:
                    conn.execute(
                        "INSERT INTO drug_name_mapping_review "
                        "(source, raw_name, reason, entity_type, entity_id, rxcui, "
                        "confidence, candidate_json, status) VALUES (?,?,?,?,?,?,?,?,?) "
                        "ON CONFLICT(source, raw_name) DO UPDATE SET "
                        "reason=excluded.reason, entity_type=excluded.entity_type, "
                        "entity_id=excluded.entity_id, rxcui=excluded.rxcui, "
                        "confidence=excluded.confidence, candidate_json=excluded.candidate_json, "
                        "status='pending', note=NULL, reviewed_at=NULL",
                        (
                            source,
                            raw_name,
                            match_method,
                            entity_type,
                            entity_id,
                            rxcui,
                            confidence,
                            candidate_json,
                            "pending",
                        ),
                    )
            else:
                conn.execute(
                    "DELETE FROM drug_name_mapping_review "
                    "WHERE source = ? AND raw_name = ?",
                    (source, raw_name),
                )
            counts["mapped" if entity_id else "unmapped"] += 1
    conn.commit()
    return counts


def _pharmgkb_synonyms(conn: sqlite3.Connection, add) -> int:
    """Thêm tên thuốc PharmGKB (generic/trade/brand) làm synonym cho class đã khớp.

    Bridge chính là RxNorm CUI (drug_classes.drugs → rxnorm_map → PharmGKB
    RxNorm Identifiers); fallback khớp token-set theo tên. Nguồn CC BY-SA 4.0.
    """
    added = 0
    rxnorm = json.loads((DATA_DIR / "rxnorm_map.json").read_text(encoding="utf-8")) \
        if (DATA_DIR / "rxnorm_map.json").exists() else {}
    rxcui_cls: dict[str, set[str]] = {}
    name_fp_cls: dict[frozenset, set[str]] = {}
    for r in conn.execute("SELECT id, name_en, drugs, aliases FROM drug_classes"):
        names = json.loads(r["drugs"] or "[]")
        for name in names:
            hit = rxnorm.get(name.lower())
            if hit:
                rxcui_cls.setdefault(hit["rxcui"], set()).add(r["id"])
        for nm in [r["name_en"], r["id"]] + names + json.loads(r["aliases"] or "[]"):
            if nm and nm.strip():
                name_fp_cls.setdefault(_token_fp(nm), set()).add(r["id"])

    for r in conn.execute(
        "SELECT name, generic_names, trade_names, brand_mixtures, type, rxnorm"
        " FROM pharmgkb_drugs"):
        if (r["type"] or "").strip() in ("Drug Class", "Pathway"):
            continue
        cls: set[str] = set()
        for rx in (r["rxnorm"] or "").split():
            cls.update(rxcui_cls.get(rx, set()))
        if not cls and (r["name"] or "").strip():
            cls.update(name_fp_cls.get(_token_fp(r["name"]), set()))
        if not cls:
            continue
        tokens = [(r["name"] or "").strip()]
        tokens += [t.strip() for t in (r["generic_names"] or "").replace(";", ",").split(",")]
        tokens += [t.strip() for t in (r["trade_names"] or "").replace(";", ",").split(",")]
        tokens += [t.strip() for t in (r["brand_mixtures"] or "").split(";")]
        for tok in tokens:
            if not tok or len(tok) < 2:
                continue
            for cid in cls:
                add("drug_class", cid, tok, "pharmgkb")
                added += 1
    return added


def _multilingual_synonyms(conn: sqlite3.Connection, add) -> int:
    """Add the licensed, entity-mapped Japanese/Chinese medical vocabulary pack."""
    if not MULTILINGUAL_VOCAB_PATH.exists():
        return 0
    payload = json.loads(MULTILINGUAL_VOCAB_PATH.read_text(encoding="utf-8"))
    added = 0
    for item in payload.get("items", []):
        if item.get("kind") and item.get("entity_id") and item.get("term"):
            add(
                item["kind"],
                item["entity_id"],
                item["term"],
                item.get("source") or "MeSpEn_Glossaries (CC BY 4.0)",
            )
            added += 1
    return added


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
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='pharmgkb_drugs'"
    ).fetchone():
        n += _pharmgkb_synonyms(conn, add)
    n += _multilingual_synonyms(conn, add)
    conn.commit()
    return n


def build_standards(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM standard_ingredient")
    n = 0
    rxnorm = json.loads((DATA_DIR / "rxnorm_map.json").read_text(encoding="utf-8")) \
        if (DATA_DIR / "rxnorm_map.json").exists() else {}
    ph_map = None
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='pharmgkb_drugs'"
    ).fetchone():
        ph_map = {}
        for p in conn.execute("SELECT rxnorm, atc, pubchem FROM pharmgkb_drugs WHERE rxnorm != ''"):
            for rx in p["rxnorm"].split():
                a, c = ph_map.setdefault(rx, (set(), set()))
                a.update((p["atc"] or "").split())
                c.update((p["pubchem"] or "").split())

    def ext_ids(kind, eid):
        ids = {}
        if kind == "drug_class":
            members = conn.execute("SELECT drugs FROM drug_classes WHERE id = ?", (eid,)).fetchone()
            own = [f"rxnorm:{rxnorm[m.lower()]['rxcui']}" for m in json.loads(members["drugs"] or [])
                   if m.lower() in rxnorm]
            if own:
                ids = {"rxnorm": own[:5]}
            if own and ph_map:
                all_atc, all_cid = set(), set()
                for m in json.loads(members["drugs"] or []):
                    hit = rxnorm.get(m.lower())
                    if not hit or hit["rxcui"] not in ph_map:
                        continue
                    a, c = ph_map[hit["rxcui"]]
                    all_atc |= a
                    all_cid |= c
                if all_atc:
                    ids["atc"] = sorted(all_atc)[:10]
                if all_cid:
                    ids["pubchem"] = sorted(all_cid)[:10]
        elif kind == "herb":
            if not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='herb_constituents'"
            ).fetchone():
                return None
            cons = conn.execute(
                "SELECT constituent, cid, cas FROM herb_constituents WHERE herb_id = ?", (eid,)
            ).fetchall()
            if cons:
                ids = {"pubchem": [c["cid"] for c in cons if c["cid"]],
                       "cas": [c["cas"] for c in cons if c["cas"]]}
        elif kind == "drug_ingredient":
            ids = {"rxnorm": [f"rxnorm:{eid}"]}
        return json.dumps(ids) if ids else None

    for kind, table in (("herb", "herbs"), ("drug_class", "drug_classes"), ("food", "foods")):
        for r in conn.execute(f"SELECT id, name_en FROM {table}"):
            conn.execute(
                "INSERT OR REPLACE INTO standard_ingredient (kind, entity_id, label, external_ids)"
                " VALUES (?,?,?,?)",
                (kind, r["id"], r["name_en"], ext_ids(kind, r["id"])))
            n += 1
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='drug_name_mapping'"
    ).fetchone():
        for row in conn.execute(
            "SELECT entity_id, MIN(rxcui) AS rxcui FROM drug_name_mapping "
            "WHERE entity_type = 'drug_ingredient' AND entity_id IS NOT NULL "
            "GROUP BY entity_id"
        ):
            concept = conn.execute(
                "SELECT name FROM rxnorm_concepts WHERE rxcui = ?", (row["entity_id"],)
            ).fetchone()
            label = concept["name"] if concept else row["entity_id"]
            conn.execute(
                "INSERT OR REPLACE INTO standard_ingredient "
                "(kind, entity_id, label, external_ids) VALUES (?,?,?,?)",
                ("drug_ingredient", row["entity_id"], label,
                 ext_ids("drug_ingredient", row["entity_id"])),
            )
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
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='dailymed_interactions'"
    ).fetchone():
        for r in conn.execute("SELECT cls_src, cls_mentioned, severity, effect, source, trust FROM dailymed_interactions"):
            add("drug_class", r["cls_src"], "drug_class", r["cls_mentioned"], r["severity"], r["effect"],
                None, r["source"], r["trust"])
    # openfda label rows (public domain, FDA tier — cùng shape DailyMed)
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='openfda_ddi'"
    ).fetchone():
        for r in conn.execute("SELECT cls_src, cls_mentioned, severity, effect, source, trust FROM openfda_ddi"):
            add("drug_class", r["cls_src"], "drug_class", r["cls_mentioned"], r["severity"], r["effect"],
                None, r["source"], r["trust"])
    # Zenodo DDI compilation (CC BY 4.0): exact RxNorm ingredient first,
    # class-level fallback only when one or both names remain unmapped.
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='zenodo_ddi_2026'"
    ).fetchone():
        if not conn.execute("SELECT 1 FROM drug_name_mapping LIMIT 1").fetchone():
            build_drug_name_mapping(conn)
        mappings = {
            row["raw_name"]: dict(row)
            for row in conn.execute(
                "SELECT raw_name, entity_type, entity_id, rxcui, confidence, match_method "
                "FROM drug_name_mapping WHERE source = 'zenodo_ddi_2026'"
            )
        }
        component_table = bool(_table_columns(conn, "drug_name_mapping_component"))
        component_rows: dict[str, list[str]] = {}
        if component_table:
            for row in conn.execute(
                "SELECT raw_name, entity_id FROM drug_name_mapping_component "
                "WHERE source = 'zenodo_ddi_2026' ORDER BY raw_name, component_index"
            ):
                component_rows.setdefault(row["raw_name"], []).append(row["entity_id"])
        class_by_name = _class_name_index(conn)

        def ingredient_ids(raw_name: str, mapping: dict) -> list[str]:
            ids = component_rows.get(raw_name)
            if ids:
                return list(dict.fromkeys(ids))
            if mapping.get("entity_type") == "drug_ingredient" and mapping.get("entity_id"):
                return [mapping["entity_id"]]
            return []

        for r in conn.execute(
            "SELECT drug_a, drug_b, interaction, source FROM zenodo_ddi_2026"
        ):
            a_map = mappings.get(r["drug_a"]) or {}
            b_map = mappings.get(r["drug_b"]) or {}
            a_ingredients = ingredient_ids(r["drug_a"], a_map)
            b_ingredients = ingredient_ids(r["drug_b"], b_map)
            if a_ingredients and b_ingredients:
                for a_id in a_ingredients:
                    for b_id in b_ingredients:
                        if a_id == b_id:
                            continue
                        add(
                            "drug_ingredient",
                            a_id,
                            "drug_ingredient",
                            b_id,
                            "moderate",
                            r["interaction"],
                            None,
                            r["source"],
                            0.65,
                        )
                continue
            a_id = (
                a_map.get("entity_id")
                if a_map.get("entity_type") == "drug_class"
                else class_by_name.get(_token_fp(r["drug_a"]))
            )
            b_id = (
                b_map.get("entity_id")
                if b_map.get("entity_type") == "drug_class"
                else class_by_name.get(_token_fp(r["drug_b"]))
            )
            if a_id and b_id and a_id != b_id:
                add(
                    "drug_class",
                    a_id,
                    "drug_class",
                    b_id,
                    "moderate",
                    r["interaction"],
                    None,
                    r["source"],
                    0.65,
                )
    # ddinter (CC BY-NC-SA — absent in commercial builds; re-import for research)
    has_ddinter = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ddinter_interactions'"
    ).fetchone()
    if has_ddinter:
        for r in conn.execute("SELECT cls_a, cls_b, severity, source, trust, drug_a, drug_b FROM ddinter_interactions"):
            add("drug_class", r["cls_a"], "drug_class", r["cls_b"], r["severity"],
                f"{r['drug_a']} + {r['drug_b']}", None, r["source"], r["trust"])
    # suppai (class-mapped only)
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='suppai_interactions'"
    ).fetchone():
        for r in conn.execute("SELECT herb_id, class_id, drug_name, doi, trust FROM suppai_interactions WHERE class_id IS NOT NULL"):
            add("herb", r["herb_id"], "drug_class", r["class_id"], "moderate",
                f"Evidence-backed interaction with {r['drug_name']}", None, "SUPP.AI", r["trust"], r["doi"])
    # idisk
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='idisk_interactions'"
    ).fetchone():
        for r in conn.execute("SELECT herb_id, class_id, description, source, trust FROM idisk_interactions"):
            add("herb", r["herb_id"], "drug_class", r["class_id"], "moderate",
                r["description"], None, r["source"] or "iDISK", r["trust"])
    # herb x herb
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='herb_herb_evidence'"
    ).fetchone():
        for r in conn.execute("SELECT herb_a, herb_b, doi, trust FROM herb_herb_evidence"):
            add("herb", r["herb_a"], "herb", r["herb_b"], "moderate",
                "Evidence-backed supplement interaction", None, "SUPP.AI (herb-herb)", r["trust"], r["doi"])
    # drugfood evidence (DrugBank via Kaggle, CC BY-NC — absent in commercial builds)
    has_dfe = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='drugfood_evidence'"
    ).fetchone()
    if has_dfe:
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
    # ChEMBL mechanism-of-action enrichment (CC BY-SA 4.0): điền mechanism cho
    # cặp drug-class chưa có cách giải thích, kèm evidence (trust 0.7).
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='chembl_mechanisms'"
    ).fetchone():
        mech_by_cls: dict[str, tuple] = {}
        for r in conn.execute(
            "SELECT cls_id, action_type, mechanism_of_action FROM chembl_mechanisms"
            " WHERE mechanism_of_action IS NOT NULL AND mechanism_of_action != ''"):
            if r["cls_id"] not in mech_by_cls:
                mech_by_cls[r["cls_id"]] = (r["action_type"], r["mechanism_of_action"])
        for row in merged.values():
            if row["mechanism"] is not None:
                continue
            ak, aid = row["a"].split(":", 1)
            bk, bid = row["b"].split(":", 1)
            if ak != "drug_class" or bk != "drug_class":
                continue
            for cls_id in (aid, bid):
                info = mech_by_cls.get(cls_id)
                if not info:
                    continue
                action, moa = info
                row["mechanism"] = f"{action}: {moa}" if action else moa
                row["evidence"].append({"source": "ChEMBL", "trust": 0.7, "doi": None})
                break

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
        print("mappings:", build_drug_name_mapping(conn))
        print("standards:", build_standards(conn))
        print("unified:", build_unified(conn))
    finally:
        conn.close()

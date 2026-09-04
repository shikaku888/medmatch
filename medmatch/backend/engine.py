"""Matching + interaction analysis engine."""
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from difflib import get_close_matches

from .db import get_conn
from .patient_context import normalize_patient_context, personalization_summary
SEVERITY_RANK = {"major": 3, "moderate": 2, "minor": 1}
_TRUSTED_INGREDIENT_MAPPING_METHODS = (
    "rxnorm_exact",
    "pharmgkb_exact",
    "rxnorm_alias",
    "rxnorm_components",
    "rxnorm_formulation_suffix",
    "rxnorm_parenthetical",
    "rxnorm_stereo_stripped",
    "rxnorm_trademark_stripped",
    "manual_review",
)

ACTIONS = {
    "major": "Do not combine. Contact your doctor or pharmacist before taking these together.",
    "moderate": "Use with caution. Talk to your healthcare provider; monitoring or a dose adjustment may be needed.",
    "minor": "Generally safe with awareness. Minor additive effects are possible.",
}

_STOP = {
    "extract", "root", "leaf", "powder", "capsule", "capsules", "tablet", "tablets",
    "mg", "mcg", "g", "iu", "vitamin", "mineral", "supplement", "complex", "plus",
    "brand", "original", "advanced", "maximum", "strength", "extra", "daily",
    "serving", "softgel", "softgels", "gummies", "gummy", "drops", "chewable",
}

def normalize(text: str) -> str:
    """Lowercase, strip Latin diacritics, preserve Unicode medical terms."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    preserved: list[str] = []
    for ch in decomposed:
        if unicodedata.combining(ch) and not (
            preserved and "\u3040" <= preserved[-1] <= "\u30ff"
        ):
            continue
        preserved.append(ch)
    text = unicodedata.normalize("NFKC", "".join(preserved))
    text = "".join(ch if ch.isalnum() or ch in " -" else " " for ch in text.casefold())
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text: str) -> set:
    return {t for t in normalize(text).replace("-", " ").split() if t and t not in _STOP}


def _stems(tokens: set) -> set:
    """Cheap plural normalization so 'st john' matches 'st johns wort'."""
    return {t[:-1] if len(t) > 3 and t.endswith("s") else t for t in tokens}


def _coerce_age(value) -> float | None:
    """Accept int/float or numeric strings ('72'); reject everything else. Safety-relevant: never silently drop."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return None

class Engine:
    """In-memory index over the seeded SQLite DB."""

    def __init__(self):
        self.conn = get_conn()
        self.herbs = {}    # norm alias -> row dict
        self.classes = {}  # norm alias -> row dict
        self.foods = {}    # norm alias -> food row dict
        self.drug_to_class = {}  # norm drug name -> class id
        self.has_suppai = self._table_exists("suppai_interactions")
        self.has_idisk = self._table_exists("idisk_interactions")
        self.has_idisk_dsi = self._table_exists("idisk_dsi")
        self.has_herb_herb = self._table_exists("herb_herb_evidence")
        self.has_review = self._table_exists("review_queue")
        self.has_dailymed = self._table_exists("dailymed_interactions")
        self.has_openfda = self._table_exists("openfda_ddi")
        self.has_ddinter = self._table_exists("ddinter_interactions")
        self.has_depletions = self._table_exists("depletions")
        self.has_dfe = self._table_exists("drugfood_evidence")
        self.has_signals = self._table_exists("vigi_signals")
        self.has_beers = self._table_exists("beers_drugs")
        self.has_qt = self._table_exists("qt_drugs")
        self.has_electrolytes = self._table_exists("electrolyte_effects")
        self.has_unified = self._table_exists("interaction_unified") and self._table_exists("drug_name_mapping")
        self.has_mapping_components = self._table_exists("drug_name_mapping_component")
        self.has_canonical = all(
            self._table_exists(table)
            for table in (
                "canonical_finding",
                "finding_evidence",
                "evidence_record",
                "evidence_record_subject",
                "dataset_release",
                "source_license",
            )
        )
        self.use_canonical_read = (
            self.has_canonical
            and os.getenv("CANONICAL_EVIDENCE_READ", "1").strip().casefold()
            in {"1", "true", "yes", "on"}
        )
        self._build_index()

    def _table_exists(self, name: str) -> bool:
        return (
            self.conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
            ).fetchone()
            is not None
        )

    def source_coverage(self) -> list[str]:
        """Return evidence families actually present in this runtime snapshot."""
        sources = ["RxNorm"]
        if self.has_dailymed or self.has_openfda:
            sources.append("FDA labels")
        if self._table_exists("onsides_effects"):
            sources.append("OnSIDES")
        if self.has_suppai and not getattr(self, "use_canonical_read", False):
            sources.append("SUPP.AI")
        if self._table_exists("faers_adverse_events"):
            sources.append("FAERS")
        if self._table_exists("drugcentral_structures"):
            sources.append("DrugCentral")
        if self._table_exists("lactmed_records"):
            sources.append("LactMed")
        if self._table_exists("fda_recalls"):
            sources.append("FDA recalls")
        if self._table_exists("caers_product_events"):
            sources.append("CAERS")
        return sources

    def data_freshness(self, sources: list[str]) -> dict:
        """Expose registry-backed release metadata without inventing dates."""
        source_codes = {
            "RxNorm": ("rxnorm_nlm",), "FDA labels": ("dailymed", "openfda"),
            "OnSIDES": ("onsides",), "SUPP.AI": ("suppai",), "FAERS": ("faers",),
            "DrugCentral": ("drugcentral",), "LactMed": ("lactmed",),
            "FDA recalls": ("fda_recalls",), "CAERS": ("caers",),
        }
        releases: dict[str, dict] = {}
        for source in sources:
            codes = source_codes.get(source) or ()
            if not codes:
                continue
            placeholders = ",".join("?" for _ in codes)
            try:
                row = self.conn.execute(
                    "SELECT version, period_start, period_end, downloaded_at, sha256 "
                    "FROM dataset_release "
                    f"WHERE source_code IN ({placeholders}) "
                    "ORDER BY downloaded_at DESC LIMIT 1",
                    codes,
                ).fetchone()
            except Exception:
                row = None
            if row:
                releases[source] = {
                    key: row[key]
                    for key in ("version", "period_start", "period_end", "downloaded_at", "sha256")
                    if row[key] is not None
                }
        return {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "releases": releases,
        }

    def _reviewed(self, pair_key: str) -> tuple[bool, bool]:
        """(verified, rejected) for a cyp-inferred pair."""
        if not self.has_review:
            return False, False
        row = self.conn.execute(
            "SELECT status FROM review_queue WHERE pair_key = ?", (pair_key,)
        ).fetchone()
        if not row:
            return False, False
        return row["status"] == "verified", row["status"] == "rejected"

    def _build_index(self):
        for row in self.conn.execute("SELECT * FROM herbs"):
            d = dict(row)
            d["aliases"] = json.loads(d["aliases"] or "[]")
            for a in [d["name_en"], d["name_es"], d["scientific"]] + d["aliases"]:
                if a:
                    n = normalize(a)
                    if n and n not in self.herbs:
                        self.herbs[n] = d
        for row in self.conn.execute("SELECT * FROM drug_classes"):
            d = dict(row)
            d["drugs"] = json.loads(d["drugs"] or "[]")
            d["aliases"] = json.loads(d["aliases"] or "[]")
            for a in [d["name_en"]] + d["aliases"] + d["drugs"]:
                if a:
                    n = normalize(a)
                    if n and n not in self.classes:
                        self.classes[n] = d
            for drug in d["drugs"]:
                self.drug_to_class[normalize(drug)] = d["id"]
        for row in self.conn.execute("SELECT * FROM foods"):
            d = dict(row)
            d["aliases"] = json.loads(d["aliases"] or "[]")
            for a in [d["name_en"]] + d["aliases"]:
                if a:
                    n = normalize(a)
                    if n and n not in self.foods:
                        self.foods[n] = d
        # Unified synonym layer (unify.py): every name variant from all sources,
        # incl. EU↔US naming (paracetamol, salbutamol, adrenaline…)
        if self._table_exists("ingredient_synonyms"):
            targets = {"herb": self.herbs, "drug_class": self.classes, "food": self.foods}
            name_rows = {}
            for row in self.conn.execute("SELECT id, name_en FROM herbs"):
                name_rows[("herb", row["id"])] = {"id": row["id"], "name_en": row["name_en"]}
            for row in self.conn.execute("SELECT id, name_en FROM drug_classes"):
                name_rows[("drug_class", row["id"])] = {"id": row["id"], "name_en": row["name_en"]}
            for row in self.conn.execute("SELECT id, name_en FROM foods"):
                name_rows[("food", row["id"])] = {"id": row["id"], "name_en": row["name_en"]}
            for row in self.conn.execute("SELECT kind, entity_id, synonym FROM ingredient_synonyms"):
                target = targets.get(row["kind"])
                entry = name_rows.get((row["kind"], row["entity_id"]))
                if not target or not entry:
                    continue
                n = normalize(row["synonym"])
                if n and n not in target:
                    target[n] = entry
        # Brand/product mappings need a class anchor before ingredient-level
        # precedence can run.  Only trusted or manually reviewed mappings enter.
        class_by_id = {
            value["id"]: value for value in self.classes.values()
        }
        if (
            self._table_exists("drug_name_mapping_component")
            and self._table_exists("standard_ingredient")
        ):
            trusted = ",".join("?" for _ in _TRUSTED_INGREDIENT_MAPPING_METHODS)
            labels = {
                row["entity_id"]: normalize(row["label"])
                for row in self.conn.execute(
                    "SELECT entity_id, label FROM standard_ingredient "
                    "WHERE kind = 'drug_ingredient'"
                )
            }
            raw_components: dict[str, set[str]] = {}
            for row in self.conn.execute(
                "SELECT raw_name, entity_id FROM drug_name_mapping_component "
                "WHERE entity_type = 'drug_ingredient' "
                "AND match_method IN (" + trusted + ")",
                _TRUSTED_INGREDIENT_MAPPING_METHODS,
            ):
                raw_components.setdefault(normalize(row["raw_name"]), set()).add(
                    row["entity_id"]
                )
            for raw_name, ingredient_ids in raw_components.items():
                class_ids = {
                    self.drug_to_class.get(labels[ingredient_id])
                    for ingredient_id in ingredient_ids
                    if labels.get(ingredient_id) in self.drug_to_class
                }
                class_ids.discard(None)
                if len(class_ids) == 1:
                    class_id = next(iter(class_ids))
                    self.classes.setdefault(raw_name, class_by_id[class_id])
        self.class_cyp: dict[str, dict[str, set]] = {}
        self.herb_cyp: dict[str, dict[str, set]] = {}
        for row in self.conn.execute("SELECT * FROM cyp_roles"):
            target = self.class_cyp if row["entity_type"] == "drug_class" else self.herb_cyp
            roles = target.setdefault(row["entity_id"], {"substrate": set(), "inhibitor": set(), "inducer": set()})
            roles[row["role"]].add(row["enzyme"])

    def match(self, name: str, max_results: int = 10) -> list:
        """Return candidate matches with confidence."""
        q = normalize(name)
        if not q:
            return []
        results = []

        def push(entry, kind, alias_norm, score):
            results.append({
                "kind": kind,
                "id": entry["id"],
                "label": entry["name_en"],
                "matched_alias": alias_norm,
                "score": score,
            })

        # exact aliases
        for src, kind in ((self.herbs, "herb"), (self.classes, "drug_class"), (self.foods, "food")):
            for alias, entry in src.items():
                if q == alias:
                    push(entry, kind, alias, 1.0)
        # token containment: query tokens subset of alias tokens or vice versa
        qt = _stems(_tokens(q))
        for src, kind in ((self.herbs, "herb"), (self.classes, "drug_class"), (self.foods, "food")):
            for alias, entry in src.items():
                at = _stems(_tokens(alias))
                if at and (at <= qt or (qt <= at and len(qt) >= 2)):
                    push(entry, kind, alias, 0.92)
        # fuzzy
        for src, kind in ((self.herbs, "herb"), (self.classes, "drug_class"), (self.foods, "food")):
            pool = list(src.keys())
            for alias in get_close_matches(q, pool, n=3, cutoff=0.82):
                entry = src[alias]
                push(entry, kind, alias, 0.85)

        # dedupe by (kind,id) keeping best score
        best = {}
        for r in results:
            key = (r["kind"], r["id"])
            if key not in best or r["score"] > best[key]["score"]:
                best[key] = r
        # Food names take precedence over overlapping herb aliases (for example
        # grapefruit), while drug classes remain the primary medication anchor.
        kind_priority = {"drug_class": 0, "food": 1, "herb": 2}
        ranked = sorted(
            best.values(),
            key=lambda r: (-r["score"], kind_priority.get(r["kind"], 9)),
        )
        return ranked[:max_results]

    def classify_item(self, name: str) -> dict | None:
        """Best single classification of an item name."""
        matches = self.match(name, max_results=10)
        if not matches:
            return None
        # Calcium is both a generic supplement class and a food/ingredient
        # alias. Prefer the food entity so levothyroxine absorption rules fire;
        # explicit ``matched`` payloads can still force drug_class.
        food = next((m for m in matches if m["kind"] == "food" and m["score"] == 1.0), None)
        generic_mineral = next(
            (
                m for m in matches
                if m["kind"] == "drug_class"
                and m["score"] == 1.0
                and m["id"] == "vitaminas_minerales"
            ),
            None,
        )
        if food and generic_mineral:
            return food
        return matches[0]

    # --- interaction lookup ---

    def _ingredient_ids_for_input(self, name: str) -> list[str]:
        if not self.has_unified:
            return []
        normalized = re.sub(
            r"\s+", " ",
            re.sub(r"[^0-9A-Za-z]+", " ", name.casefold()),
        ).strip()
        placeholders = ",".join("?" for _ in _TRUSTED_INGREDIENT_MAPPING_METHODS)
        ids: list[str] = []
        if self.has_mapping_components:
            rows = self.conn.execute(
                "SELECT DISTINCT entity_id FROM drug_name_mapping_component "
                "WHERE entity_type = 'drug_ingredient' "
                "AND match_method IN (" + placeholders + ") "
                "AND (LOWER(raw_name) = LOWER(?) OR raw_name = ?)"
                " ORDER BY component_index",
                (*_TRUSTED_INGREDIENT_MAPPING_METHODS, name.strip(), name.strip()),
            ).fetchall()
            ids.extend(row["entity_id"] for row in rows)
        if not ids:
            rows = self.conn.execute(
                "SELECT DISTINCT entity_id FROM drug_name_mapping "
                "WHERE entity_type = 'drug_ingredient' AND entity_id IS NOT NULL "
                "AND match_method IN (" + placeholders + ") "
                "AND (LOWER(raw_name) = LOWER(?) OR normalized_name = ?)",
                (*_TRUSTED_INGREDIENT_MAPPING_METHODS, name.strip(), normalized),
            ).fetchall()
            ids.extend(row["entity_id"] for row in rows)
        return list(dict.fromkeys(ids))

    def ingredient_pairs(self, ingredient_a: list[str], ingredient_b: list[str]) -> list[dict]:
        if getattr(self, "use_canonical_read", False):
            canonical = [
                item
                for a in ingredient_a
                for b in ingredient_b
                if a != b
                for item in self.canonical_pairs(
                    "drug_ingredient", a, "drug_ingredient", b
                )
            ]
            if canonical:
                return canonical
        if not self.has_unified or not ingredient_a or not ingredient_b:
            return []
        pairs = {(a, b) for a in ingredient_a for b in ingredient_b if a != b}
        if not pairs:
            return []
        predicates = " OR ".join(
            "(a_kind = 'drug_ingredient' AND a_id = ? AND "
            "b_kind = 'drug_ingredient' AND b_id = ?) OR "
            "(a_kind = 'drug_ingredient' AND a_id = ? AND "
            "b_kind = 'drug_ingredient' AND b_id = ?)"
            for _ in pairs
        )
        params = []
        for a, b in pairs:
            params.extend((a, b, b, a))
        rows = self.conn.execute(
            "SELECT * FROM interaction_unified WHERE " + predicates,
            params,
        ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            evidence = item.get("evidence")
            try:
                evidence_rows = json.loads(evidence or "[]")
            except (TypeError, json.JSONDecodeError):
                evidence_rows = []
            item["source"] = (
                evidence_rows[0].get("source")
                if evidence_rows and isinstance(evidence_rows[0], dict)
                else "Unified DDI evidence"
            )
            item["evidence"] = evidence_rows
            item["severity_rank"] = SEVERITY_RANK.get(item["severity"], 1)
            item["action"] = ACTIONS.get(item["severity"], ACTIONS["moderate"])
            out.append(item)
        return out

    def herb_interactions(self, herb_id: str) -> list:
        if getattr(self, "use_canonical_read", False):
            canonical = self._canonical_for_herb(herb_id)
            if canonical:
                return canonical
        rows = self.conn.execute(
            "SELECT i.*, c.name_en AS class_name FROM interactions i"
            " JOIN drug_classes c ON c.id = i.class_id WHERE i.herb_id = ?",
            (herb_id,),
        ).fetchall()
        return [self._interaction_dict(r) for r in rows]

    @staticmethod
    def _interaction_dict(r) -> dict:
        d = dict(r)
        d["severity_rank"] = SEVERITY_RANK.get(d["severity"], 1)
        d["action"] = ACTIONS.get(d["severity"], ACTIONS["minor"])
        return d

    def canonical_pairs(
        self, a_kind: str, a_id: str, b_kind: str | None = None, b_id: str | None = None
    ) -> list[dict]:
        """Return only accepted findings whose selected lineage passes all gates."""
        if not getattr(self, "has_canonical", False):
            return []
        if b_kind is None:
            endpoint_sql = (
                "((cf.a_kind = ? AND cf.a_id = ?) OR "
                "(cf.b_kind = ? AND cf.b_id = ?))"
            )
            params = (a_kind, a_id, a_kind, a_id)
        else:
            endpoint_sql = (
                "((cf.a_kind = ? AND cf.a_id = ? AND cf.b_kind = ? AND cf.b_id = ?) OR "
                "(cf.a_kind = ? AND cf.a_id = ? AND cf.b_kind = ? AND cf.b_id = ?))"
            )
            params = (a_kind, a_id, b_kind, b_id, b_kind, b_id, a_kind, a_id)
        rows = self.conn.execute(
            "SELECT cf.finding_id, cf.pair_key, cf.a_kind, cf.a_id, cf.b_kind, cf.b_id, "
            "cf.finding_type, cf.status AS finding_status, cf.evidence_status, "
            "cf.evidence_level AS finding_evidence_level, cf.evidence_severity, "
            "cf.evidence_confidence AS finding_confidence, cf.effect, cf.mechanism, "
            "cf.action, cf.inferred, cf.context_json, cf.scope_hash, "
            "cf.resolution_policy_version, fe.evidence_id, er.source_code, er.release_id, "
            "er.record_key, er.evidence_type, er.evidence_level, er.evidence_confidence, "
            "er.source_url, er.source_locator, er.doi, er.pmid, er.context_json AS evidence_context "
            "FROM canonical_finding cf "
            "JOIN finding_evidence fe ON fe.finding_id = cf.finding_id "
            "AND fe.role = 'supporting' AND fe.selected = 1 "
            "JOIN evidence_record er ON er.evidence_id = fe.evidence_id "
            "JOIN ingestion_run ir ON ir.ingestion_run_id = er.ingestion_run_id "
            "JOIN dataset_release dr ON dr.source_code = er.source_code "
            "AND dr.version = substr(er.release_id, length(er.source_code) + 2) "
            "JOIN source_license sl ON sl.source_code = er.source_code "
            "WHERE cf.status = 'accepted' AND er.status = 'accepted' "
            "AND ir.status = 'accepted' "
            "AND dr.release_status = 'accepted' "
            "AND (sl.commercial_use_allowed = 1 OR sl.derived_use_allowed = 1) "
            "AND EXISTS (SELECT 1 FROM evidence_record_subject es "
            "WHERE es.evidence_id = er.evidence_id) "
            "AND NOT EXISTS (SELECT 1 FROM evidence_record_subject es "
            "WHERE es.evidence_id = er.evidence_id AND es.mapping_status <> 'accepted') "
            "AND (er.evidence_level <> 'inferred' OR EXISTS ("
            "SELECT 1 FROM evidence_derivation ed "
            "WHERE ed.derived_evidence_id = er.evidence_id)) "
            "AND " + endpoint_sql + " ORDER BY cf.finding_id, fe.evidence_id",
            params,
        ).fetchall()
        out_by_finding = {}
        for row in rows:
            severity = row["evidence_severity"] or "unknown"
            evidence_confidence = row["evidence_confidence"]
            evidence = {
                "evidenceId": row["evidence_id"],
                "sourceCode": row["source_code"],
                "releaseId": row["release_id"],
                "recordKey": row["record_key"],
                "evidenceType": row["evidence_type"],
                "evidenceLevel": row["evidence_level"],
                "evidenceConfidence": evidence_confidence,
                "sourceUrl": row["source_url"],
                "sourceLocator": row["source_locator"],
                "doi": row["doi"],
                "pmid": row["pmid"],
            }
            item = out_by_finding.get(row["finding_id"])
            if item is not None:
                item["evidence"].append(evidence)
                item["evidence_ids"].append(row["evidence_id"])
                continue
            out_by_finding[row["finding_id"]] = {
                "finding_id": row["finding_id"],
                "pair_key": row["pair_key"],
                "a_kind": row["a_kind"],
                "a_id": row["a_id"],
                "b_kind": row["b_kind"],
                "b_id": row["b_id"],
                "finding_type": row["finding_type"],
                "status": row["finding_status"],
                "evidence_status": row["evidence_status"],
                "evidence_level": row["finding_evidence_level"],
                "evidence_severity": severity,
                "evidence_confidence": row["finding_confidence"] or evidence_confidence,
                "severity": severity,
                "effect": row["effect"],
                "mechanism": row["mechanism"],
                "action": row["action"] or ACTIONS.get(severity, ACTIONS["moderate"]),
                "inferred": bool(row["inferred"]),
                "context_json": row["context_json"],
                "scope_hash": row["scope_hash"],
                "resolution_policy_version": row["resolution_policy_version"],
                "source": row["source_code"],
                "source_code": row["source_code"],
                "release_id": row["release_id"],
                "evidence": [evidence],
                "evidence_ids": [row["evidence_id"]],
                "severity_rank": SEVERITY_RANK.get(severity, 1),
            }
        return list(out_by_finding.values())

    def _canonical_for_herb(self, herb_id: str) -> list[dict]:
        out = []
        for item in self.canonical_pairs("herb", herb_id):
            other = (
                item["b_id"] if item["a_kind"] == "herb" and item["a_id"] == herb_id
                else item["a_id"]
            )
            if item["a_kind"] == "herb" and item["a_id"] == herb_id:
                other_kind = item["b_kind"]
            else:
                other_kind = item["a_kind"]
            if other_kind != "drug_class":
                continue
            item = dict(item)
            item["herb_id"] = herb_id
            item["class_id"] = other
            item["class_name"] = self.class_label(other)
            out.append(item)
        return out

    def _canonical_as_class_pairs(self, cls_a: str, cls_b: str) -> list[dict]:
        out = []
        for item in self.canonical_pairs("drug_class", cls_a, "drug_class", cls_b):
            item = dict(item)
            item["cls_a"] = item["a_id"] if item["a_kind"] == "drug_class" else cls_a
            item["cls_b"] = item["b_id"] if item["b_kind"] == "drug_class" else cls_b
            out.append(item)
        return out

    def _canonical_as_food_pairs(self, cls_id: str, food_id: str) -> list[dict]:
        out = []
        for item in self.canonical_pairs("drug_class", cls_id, "food", food_id):
            item = dict(item)
            item["cls_a"] = cls_id
            item["food_id"] = food_id
            out.append(item)
        return out

    def class_pairs(self, cls_a: str, cls_b: str) -> list:
        if getattr(self, "use_canonical_read", False):
            canonical = self._canonical_as_class_pairs(cls_a, cls_b)
            if canonical:
                return canonical
        rows = self.conn.execute(
            "SELECT * FROM drug_drug WHERE"
            " (cls_a = ? AND cls_b = ?) OR (cls_a = ? AND cls_b = ?)",
            (cls_a, cls_b, cls_b, cls_a),
        ).fetchall()
        return [self._interaction_dict(r) for r in rows]

    def dailymed_pairs(self, cls_a: str, cls_b: str) -> list:
        """FDA-label (DailyMed) class x class rows for a pair.
        The stored `effect` column is a raw label-table dump ("Table N: ...") —
        compose a clean sentence from the structured columns instead."""
        if getattr(self, "use_canonical_read", False):
            return []
        if not self.has_dailymed:
            return []
        rows = self.conn.execute(
            "SELECT * FROM dailymed_interactions WHERE"
            " (cls_src = ? AND cls_mentioned = ?) OR (cls_src = ? AND cls_mentioned = ?)",
            (cls_a, cls_b, cls_b, cls_a),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            src = str(d.get("drug_src") or "").strip()
            mentioned = str(d.get("drug_mentioned") or "").strip()
            cls_label = self.class_label(str(d.get("cls_mentioned") or ""))
            sev = str(d.get("severity") or "notable").lower()
            if src and mentioned:
                d["effect"] = (
                    f"FDA label for {src.title()} lists {mentioned.title()} ({cls_label}) "
                    f"as an interacting medication — {sev} severity per DailyMed. "
                    f"Monitor clinical response and adjust therapy as needed."
                )
            else:
                text = re.sub(r"^Table\s*\d+:\s*", "", str(d.get("effect") or ""), flags=re.I).strip()
                if len(text) > 240:
                    text = text[:240].rsplit(" ", 1)[0] + "…"
                d["effect"] = text
            # internal columns are not part of the public interaction shape
            for junk in ("id", "cls_src", "cls_mentioned", "drug_src", "drug_mentioned", "pair_key"):
                d.pop(junk, None)
            d["action"] = ACTIONS.get(d.get("severity"), ACTIONS["moderate"])
            out.append(d)
        return out

    def openfda_pairs(self, cls_a: str, cls_b: str) -> list:
        """openFDA drug/label rows (public domain, FDA tier). Cùng shape DailyMed
        nhưng nguồn từ JSON label API; effect tự compose từ cột có cấu trúc."""
        if getattr(self, "use_canonical_read", False):
            return []
        if not self.has_openfda:
            return []
        rows = self.conn.execute(
            "SELECT * FROM openfda_ddi WHERE"
            " (cls_src = ? AND cls_mentioned = ?) OR (cls_src = ? AND cls_mentioned = ?)",
            (cls_a, cls_b, cls_b, cls_a),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            src = str(d.get("drug_src") or "").strip()
            mentioned = str(d.get("drug_mentioned") or "").strip()
            cls_label = self.class_label(str(d.get("cls_mentioned") or ""))
            sev = str(d.get("severity") or "moderate").lower()
            if src and mentioned:
                d["effect"] = (
                    f"FDA label (openFDA) for {src.title()} lists {mentioned.title()} "
                    f"({cls_label}) as an interacting medication — {sev} severity. "
                    f"Monitor clinical response and adjust therapy as needed."
                )
            else:
                text = str(d.get("effect") or "")
                if len(text) > 240:
                    text = text[:240].rsplit(" ", 1)[0] + "…"
                d["effect"] = text
            for junk in ("id", "cls_src", "cls_mentioned", "drug_src", "drug_mentioned", "pair_key"):
                d.pop(junk, None)
            d["action"] = ACTIONS.get(d.get("severity"), ACTIONS["moderate"])
            out.append(d)
        return out

    def signals_for(self, class_ids: list[str], limit: int = 20) -> list:
        """Real-world ADR signal counts (VigiBase via VigiAccess) cho lớp thuốc."""
        if not self.has_signals or not class_ids:
            return []
        rows = self.conn.execute(
            "SELECT meddra_pt, SUM(count) AS reports FROM vigi_signals"
            f" WHERE cls_id IN ({','.join('?' * len(class_ids))})"
            " GROUP BY meddra_pt ORDER BY reports DESC LIMIT ?",
            (*list(class_ids), limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def ddinter_pairs(self, cls_a: str, cls_b: str) -> list:
        """DDInter class x class rows (CC BY-NC-SA; MVP use per project plan)."""
        if getattr(self, "use_canonical_read", False):
            return []
        if not self.has_ddinter:
            return []
        rows = self.conn.execute(
            "SELECT * FROM ddinter_interactions WHERE"
            " (cls_a = ? AND cls_b = ?) OR (cls_a = ? AND cls_b = ?)",
            (cls_a, cls_b, cls_b, cls_a),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["severity_rank"] = SEVERITY_RANK.get(d["severity"], 1)
            d["action"] = ACTIONS.get(d["severity"], ACTIONS["minor"])
            out.append(d)
        return out

    def depletions_for(self, class_ids: list[str]) -> list:
        """Nutrient depletions triggered by the matched drug classes."""
        if not self.has_depletions or not class_ids:
            return []
        ids = set(class_ids)
        out = []
        rows = self.conn.execute("SELECT * FROM depletions").fetchall()
        for r in rows:
            d = dict(r)
            if d["cls_b"] is None:
                hit = d["cls_a"] in ids
            else:
                hit = d["cls_a"] in ids and d["cls_b"] in ids
            if hit:
                d.pop("cls_a", None)
                d.pop("cls_b", None)
                d.pop("pair_key", None)
                out.append(d)
        return out

    # --- ⑥ Beers Criteria (age >= 65) ---
    BEERS_NOTES = {
        "benzodiacepinas": ("avoid", "Beers 2023: benzodiazepines increase cognitive impairment, delirium and falls in older adults."),
        "imao": ("avoid", "Beers 2023: MAO inhibitors — high risk of orthostatic hypotension and drug interactions in older adults."),
        "isrs": ("caution", "Beers 2023: SSRIs — use with caution (hyponatremia, bleeding, falls risk in older adults)."),
        "digoxina": ("caution", "Beers 2023: avoid digoxin >0.125 mg/day; renal clearance falls with age."),
    }
    # Minimal seed DB fallback for high-salience entries retained in the
    # release contract when the optional Sahayak table is unavailable.
    BEERS_DRUG_NOTES = {
        "amiodarone": (
            "avoid",
            "Beers 2023: amiodarone is generally avoidable as first-line therapy in older adults because of significant toxicity.",
        ),
    }
    ELECTROLYTE_DRUG_NOTES = {
        "furosemide": "Loop diuretics waste potassium and magnesium; low levels can predispose to weakness and arrhythmia.",
    }

    def beers_for(self, class_ids: list[str], age, drug_names: list[str] | None = None) -> list:
        """Beers Criteria flags for users aged 65+. Never lowers anything: additive warning only."""
        age = _coerce_age(age)
        if age is None or age < 65:
            return []
        ids = set(class_ids)
        out = []
        # SAHAYAK Beers 2023 — name-based (453 entries)
        names = [n.lower().strip() for n in (drug_names or []) if n and len(n.strip()) > 3]
        if self.has_beers:
            for name in names:
                for row in self.conn.execute(
                    "SELECT drug_name, table_src, organ_system, category, rationale FROM beers_drugs WHERE drug_name = ? LIMIT 2",
                    (name,),
                ):
                    level = "caution" if row["table_src"] == "table4_use_with_caution" else "avoid"
                    out.append({
                        "class_id": f"drug:{row['drug_name']}",
                        "label": row["drug_name"].title(),
                        "level": level,
                        "note": f"Beers 2023 ({row['organ_system']} — {row['category']}): {row['rationale']}",
                    })
        else:
            for name in names:
                fallback = self.BEERS_DRUG_NOTES.get(name)
                if fallback:
                    level, note = fallback
                    out.append({
                        "class_id": f"drug:{name}",
                        "label": name.title(),
                        "level": level,
                        "note": note,
                    })
        for cid, (level, note) in self.BEERS_NOTES.items():
            if cid in ids:
                out.append({"class_id": cid, "label": self.class_label(cid), "level": level, "note": note})
        if "anticoagulantes" in ids and "antiplaquetarios" in ids:
            out.append({
                "class_id": "anticoagulantes+antiplaquetarios",
                "label": "Anticoagulants + Antiplatelets",
                "level": "avoid",
                "note": "Beers 2023: concurrent anticoagulant + antiplatelet therapy without a clear indication raises major bleeding risk in older adults.",
            })
        return out

    def class_label(self, class_id: str) -> str:
        row = self.conn.execute("SELECT name_en FROM drug_classes WHERE id = ?", (class_id,)).fetchone()
        return row["name_en"] if row else class_id

    # --- ③ QT Prolongation Risk ---
    QT_CLASSES = {"macrolidos": "Macrolides", "antifungicos": "Azole antifungals", "isrs": "SSRI antidepressants (citalopram/escitalopram)", "antirretrovirales": "Antiretrovirals", "antibioticos": "Antibiotics (quinolones/macrolides)", "antipsicoticos": "Antipsychotics", "antiemeticos": "Antiemetics (5-HT3)", "triciclicos": "Tricyclic antidepressants", "antiarritmicos": "Antiarrhythmics"}

    def qt_risk_for(self, class_ids: list[str], profile: dict | None, drug_names: list[str] | None = None) -> list:
        """Additive QT-prolongation risk: count QT drugs + patient risk factors."""
        ids = set(class_ids)
        qt_hits = [label for cid, label in self.QT_CLASSES.items() if cid in ids]
        # SAHAYAK name-based QT list (29 drugs, known/possible/conditional)
        names = [n.lower().strip() for n in (drug_names or []) if n and len(n.strip()) > 3]
        if self.has_qt:
            for name in names:
                row = self.conn.execute("SELECT risk_level FROM qt_drugs WHERE name = ?", (name,)).fetchone()
                if row:
                    qt_hits.append(f"{name.title()} ({row['risk_level'].replace('_', ' ')})")
        factors: list[str] = []
        p = profile or {}
        age = p.get("age")
        age = _coerce_age(age)
        if age is not None and age >= 65:
            factors.append("age >= 65")
        if p.get("gender") == "female":
            factors.append("female sex")
        if p.get("kidneyFunction") in ("moderate_impairment", "severe_impairment"):
            factors.append("renal impairment (electrolyte loss raises torsades risk)")
        if p.get("liverFunction") in ("moderate_impairment", "severe_impairment"):
            factors.append("hepatic impairment (reduced QT-drug clearance)")
        if not qt_hits:
            return []
        score = len(qt_hits) + (2 if len(factors) >= 2 else len(factors))
        # Safety override (brain.md L7-4): >= 3 QT drugs is always HIGH regardless of factors.
        level = "high" if (len(qt_hits) >= 3 or score >= 4) else "moderate" if score >= 2 else "low"
        return [{
            "level": level,
            "qt_classes": qt_hits,
            "factors": factors,
            "screening_only": True,
            "source": "label-derived and SAHAYAK screening data",
            "limitations": [
                "This is not a clinical-grade QT risk score.",
                "CredibleMeds restricted data is not used.",
            ],
        }]
    # --- ④ Electrolyte Depletion (secondary arrhythmia/weakness risk) ---
    ELECTROLYTE_MAP = {
        "antihipertensivos": [("Potassium", "Diuretic component of antihypertensives drives renal K+ loss"), ("Magnesium", "Thiazide/loop diuretics also waste Mg2+")],
        "digoxina": [("Potassium", "Digoxin toxicity risk rises sharply when K+ runs low")],
    }

    def electrolytes_for(self, class_ids: list[str], drug_names: list[str] | None = None) -> list:
        ids = set(class_ids)
        merged: dict[str, dict] = {}
        for cid in ids:
            for electrolyte, why in self.ELECTROLYTE_MAP.get(cid, []):
                entry = merged.setdefault(electrolyte, {"electrolyte": electrolyte, "sources": [], "reasons": []})
                label = self.class_label(cid)
                if label not in entry["sources"]:
                    entry["sources"].append(label)
                if why not in entry["reasons"]:
                    entry["reasons"].append(why)
        names = [n.lower().strip() for n in (drug_names or []) if n and len(n.strip()) > 3]
        if self.has_electrolytes:
            depleting = [n for n in names
                         if self.conn.execute(
                             "SELECT 1 FROM electrolyte_effects WHERE drug=? AND category='potassium_depleting'",
                             (n,),
                         ).fetchone()]
            sensitive = [n for n in names
                         if self.conn.execute(
                             "SELECT 1 FROM electrolyte_effects WHERE drug=? AND category='potassium_sensitive'",
                             (n,),
                         ).fetchone()]
        else:
            depleting = []
            sensitive = []
        if not self.has_electrolytes:
            for name in names:
                why = self.ELECTROLYTE_DRUG_NOTES.get(name)
                if not why:
                    continue
                entry = merged.setdefault("Potassium", {"electrolyte": "Potassium", "sources": [], "reasons": []})
                if name.title() not in entry["sources"]:
                    entry["sources"].append(name.title())
                if why not in entry["reasons"]:
                    entry["reasons"].append(why)
        for n in depleting:
            entry = merged.setdefault("Potassium", {"electrolyte": "Potassium", "sources": [], "reasons": []})
            if n.title() not in entry["sources"]:
                entry["sources"].append(n.title())
            why = f"{n.title()} causes renal K+/Mg2+ wasting (SAHAYAK electrolyte data)"
            if why not in entry["reasons"]:
                entry["reasons"].append(why)
        if depleting and sensitive:
            entry = merged.setdefault("Potassium", {"electrolyte": "Potassium", "sources": [], "reasons": []})
            combo = f"{' + '.join(d.title() for d in depleting)} combined with {'/'.join(x.title() for x in sensitive)} — hypokalemia amplifies toxicity/arrhythmia risk"
            if combo not in entry["reasons"]:
                entry["reasons"].append(combo)
        for e in merged.values():
            if "Potassium" in e["electrolyte"] and any("digoxin" in r.lower() for r in e["reasons"]):
                e["secondary_risk"] = "Arrhythmia / digoxin toxicity — check K+ before dose escalation."
            else:
                e["secondary_risk"] = "Muscle weakness and cramps; severe loss predisposes to rhythm disturbances."
        return list(merged.values())

    # --- ① Cascade Analysis: enzyme-pathway chains (>= 2 hops) ---
    def cascades_for(self, herbs: list, classes: list) -> list:
        """Graph walk over CYP roles: A(inducer E1) -> B(substrate E1, inhibitor E2) -> C(substrate E2)."""
        nodes = []
        for m in herbs + classes:
            roles = self.herb_cyp.get(m["id"]) if m["kind"] == "herb" else self.class_cyp.get(m["id"])
            if roles:
                nodes.append({"label": m["label"], "kind": m["kind"], "id": m["id"], "roles": roles})

        def fmt(enz: str) -> str:
            return "P-glycoprotein" if enz == "p_gp" else f"CYP{enz}"

        chains = []
        for a in nodes:
            for e1 in sorted(a["roles"].get("inducer", set())):
                for b in nodes:
                    if b["id"] == a["id"] or e1 not in b["roles"].get("substrate", set()):
                        continue
                    for e2 in sorted(b["roles"].get("inhibitor", set())):
                        for c in nodes:
                            if c["id"] in (a["id"], b["id"]) or e2 not in c["roles"].get("substrate", set()):
                                continue
                            chains.append({
                                "chain": [
                                    {"label": a["label"], "kind": a["kind"], "role": f"induces {fmt(e1)}"},
                                    {"label": b["label"], "kind": b["kind"], "role": f"substrate of {fmt(e1)}, inhibits {fmt(e2)}"},
                                    {"label": c["label"], "kind": c["kind"], "role": f"substrate of {fmt(e2)}"},
                                ],
                                "enzymes": [e1, e2],
                                "effect": f"{a['label']} induces {fmt(e1)}, lowering {b['label']} exposure; {b['label']} also inhibits {fmt(e2)}, so {c['label']} levels may RISE — net effect hard to predict without monitoring.",
                                "trust": 0.5,
                            })
        return chains[:6]

    # --- ② Schedule Optimizer: absorption-type conflicts ---
    # Only intestinal/timing-fixable mechanisms qualify. Binding alone is not
    # included: plasma-protein binding and metabolism inhibition are not
    # defused by separating doses.
    SCHEDULE_MARKERS = ("absorption", "chelat", "bioavailab", "uptake transporter", "intestinal", "empty stomach", "hours apart", "separately", "separate", "reduces the absorption", "reduce the absorption", "coadministration")

    def schedule_for(self, interactions: list) -> list:
        out = []
        import re as _re

        for inter in interactions:
            text = " ".join(str(inter.get(k) or "") for k in
                            ("mechanism", "effect", "summary", "description", "clinicalImpact")).lower()
            if not any(marker in text for marker in self.SCHEDULE_MARKERS):
                continue
            m = _re.search(r"(?:at least |separated? by |\bat\s)?(\d+)\s*(?:to\s*\d+\s*)?(?:-\s*)?hours?", text)
            hours = int(m.group(1)) if m else 4
            hours = max(2, min(hours, 12))
            out.append({
                "a": inter["a"]["label"],
                "b": inter["b"]["label"],
                "reason": inter.get("effect") or inter.get("mechanism") or inter.get("summary") or "Absorption interference",
                "min_hours": hours,
            })
        return out[:8]

    def food_interactions(self, cls_id: str, food_id: str) -> list:
        if getattr(self, "use_canonical_read", False):
            canonical = self._canonical_as_food_pairs(cls_id, food_id)
            if canonical:
                return canonical
        rows = self.conn.execute(
            "SELECT * FROM drug_food WHERE cls_a = ? AND food_id = ?",
            (cls_id, food_id),
        ).fetchall()
        return [self._interaction_dict(r) for r in rows]
    def drugfood_evidence_pairs(self, cls_id: str, food_id: str) -> list:
        """DrugBank-derived drug-food evidence rows (CC BY-NC flag)."""
        if getattr(self, "use_canonical_read", False):
            return []
        if not self.has_dfe:
            return []
        rows = self.conn.execute(
            "SELECT * FROM drugfood_evidence WHERE cls_a = ? AND food_id = ?",
            (cls_id, food_id),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["severity_rank"] = SEVERITY_RANK.get(d["severity"], 1)
            d["action"] = ACTIONS.get(d["severity"], ACTIONS["minor"])
            out.append(d)
        return out

    def drug_pairs(self, drug_a: str, drug_b: str) -> list:
        if getattr(self, "use_canonical_read", False):
            return []
        rows = self.conn.execute(
            "SELECT * FROM drug_drug WHERE"
            " (drug_a = ? AND drug_b = ?) OR (drug_a = ? AND drug_b = ?)",
            (drug_a, drug_b, drug_b, drug_a),
        ).fetchall()
        return [self._interaction_dict(r) for r in rows]

    def cyp_inference(self, roles_a: dict, roles_b: dict,
                      a_id: str, a_label: str, b_id: str, b_label: str) -> list:
        """Infer hidden interactions from either direction of pathway overlap."""
        out = []

        def fmt(enz: str) -> str:
            return "P-glycoprotein" if enz == "p_gp" else f"CYP{enz}"

        def directed(source: dict, target: dict, source_label: str, target_label: str) -> list:
            rows = []
            for enz in sorted(source.get("inhibitor", set()) & target.get("substrate", set())):
                rows.append({
                    "type": "cyp-inferred",
                    "severity": "moderate",
                    "effect": f"{source_label} inhibits {fmt(enz)}, which metabolizes {target_label} — levels of {target_label} may rise.",
                    "mechanism": f"{fmt(enz)} inhibition (pathway inference; no direct study found for this pair).",
                    "source": "CYP450 pathway inference",
                    "trust": 0.5,
                    "enzyme": enz,
                    "action": ACTIONS["moderate"],
                })
            for enz in sorted(source.get("inducer", set()) & target.get("substrate", set())):
                rows.append({
                    "type": "cyp-inferred",
                    "severity": "moderate",
                    "effect": f"{source_label} induces {fmt(enz)}, which metabolizes {target_label} — efficacy of {target_label} may fall.",
                    "source": "CYP450 pathway inference",
                    "trust": 0.5,
                    "enzyme": enz,
                    "action": ACTIONS["moderate"],
                })
            return rows

        out.extend(directed(roles_a, roles_b, a_label, b_label))
        out.extend(directed(roles_b, roles_a, b_label, a_label))
        return out[:2]

    def herb_detail(self, herb_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM herbs WHERE id = ?", (herb_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["aliases"] = json.loads(d["aliases"] or "[]")
        d["interactions"] = self.herb_interactions(herb_id)
        if self.has_idisk_dsi:
            dsi = self.conn.execute(
                "SELECT background, safety, mechanism, source_material FROM idisk_dsi"
                " WHERE herb_id = ? AND (background != '' OR safety != '' OR mechanism != '')"
                " LIMIT 1", (herb_id,),
            ).fetchone()
            if dsi:
                d["idisk"] = dict(dsi)
        return d

    def class_detail(self, class_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM drug_classes WHERE id = ?", (class_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["drugs"] = json.loads(d["drugs"] or "[]")
        d["aliases"] = json.loads(d["aliases"] or "[]")
        return d

    def suppai_evidence(self, herb_id: str, class_id: str) -> list:
        """Evidence-backed SUPP.AI rows for a herb-class pair (severity None)."""
        if getattr(self, "use_canonical_read", False):
            return []
        if not self.has_suppai:
            return []
        rows = self.conn.execute(
            "SELECT * FROM suppai_interactions WHERE herb_id = ? AND class_id = ?",
            (herb_id, class_id),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["evidence"] = json.loads(d["evidence"] or "[]")
            d["severity"] = None
            out.append(d)
        return out

    def herb_herb_evidence(self, herb_a: str, herb_b: str) -> list:
        """Evidence-backed supplement x supplement rows (severity None)."""
        if getattr(self, "use_canonical_read", False):
            return self.canonical_pairs("herb", herb_a, "herb", herb_b)
        if not self.has_herb_herb:
            return []
        rows = self.conn.execute(
            "SELECT * FROM herb_herb_evidence WHERE"
            " (herb_a = ? AND herb_b = ?) OR (herb_a = ? AND herb_b = ?)",
            (herb_a, herb_b, herb_b, herb_a),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["severity"] = None
            d["evidence"] = json.loads(d["evidence"] or "[]")
            out.append(d)
        return out

    def idisk_evidence(self, herb_id: str, class_id: str) -> list:
        """iDISK (MSKCC/NM) rows for a herb-class pair (severity None)."""
        if getattr(self, "use_canonical_read", False):
            return []
        if not self.has_idisk:
            return []
        rows = self.conn.execute(
            "SELECT * FROM idisk_interactions WHERE herb_id = ? AND class_id = ?",
            (herb_id, class_id),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["severity"] = None
            d["evidence"] = []
            out.append(d)
        return out

    # --- full analysis ---
    def analyze(self, items: list[dict], profile: dict | None = None) -> dict:
        """items: [{name, kind?, matched?}] + optional patient profile -> full 7-layer analysis."""
        p = normalize_patient_context(profile)
        p["pregnancyStatus"] = p["pregnancy"]["status"]
        p["lactationStatus"] = p["lactation"]["status"]
        p["kidneyFunction"] = p["renal"]["status"]
        p["liverFunction"] = p["hepatic"]["status"]
        p["specialConditions"] = p["conditions"]
        matched = []
        interactions = []
        unmatched = []
        seen_keys = set()
        item_time: dict[tuple, str] = {}

        def track_time(kind: str, eid: str, time: str | None):
            if time:
                item_time[(kind, eid)] = time
        for item in items:
            name = (item.get("name") or "").strip()
            if not name:
                continue
            forced = item.get("matched")  # optional explicit {kind,id}
            if forced and forced.get("id"):
                entry = None
                if forced["kind"] == "herb":
                    entry = self.herb_detail(forced["id"])
                    if entry:
                        entry["kind"] = "herb"
                elif forced["kind"] == "drug_class":
                    entry = self.class_detail(forced["id"])
                    if entry:
                        entry["kind"] = "drug_class"
                elif forced["kind"] == "food":
                    frow = self.conn.execute("SELECT * FROM foods WHERE id = ?", (forced["id"],)).fetchone()
                    if frow:
                        matched.append({"input": name, "kind": "food",
                                        "id": frow["id"], "label": frow["name_en"]})
                        track_time("food", frow["id"], item.get("time"))
                if entry:
                    matched.append({"input": name, "kind": entry["kind"],
                                    "id": entry["id"], "label": entry["name_en"]})
                    track_time(entry["kind"], entry["id"], item.get("time"))
            else:
                cls = self.classify_item(name)
                if cls:
                    matched.append({"input": name, **cls})
                    track_time(cls["kind"], cls["id"], item.get("time"))
                else:
                    unmatched.append(name)

        herbs = [m for m in matched if m["kind"] == "herb"]
        classes = [m for m in matched if m["kind"] == "drug_class"]

        # supplement (herb) x drug class (seeded rules)
        covered = set()
        for h in herbs:
            for c in classes:
                for inter in self.herb_interactions(h["id"]):
                    if inter["class_id"] != c["id"]:
                        continue
                    covered.add((h["id"], c["id"]))
                    key = ("herb-class", h["id"], c["id"], inter["effect"])
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    interactions.append({
                        "type": "herb-drug",
                        "a": {"label": h["label"], "id": h["id"], "kind": "herb"},
                        "b": {"label": c["label"], "id": c["id"], "kind": "drug_class"},
                        **inter,
                    })

        # SUPP.AI evidence-backed pairs the seeds don't cover (no severity: evidence-driven)
        if self.has_suppai:
            for h in herbs:
                for c in classes:
                    if (h["id"], c["id"]) in covered:
                        continue
                    for inter in self.suppai_evidence(h["id"], c["id"]):
                        key = ("suppai", h["id"], c["id"], inter["drug_cui"])
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        interactions.append({
                            "type": "herb-drug-evidence",
                            "a": {"label": h["label"], "id": h["id"], "kind": "herb"},
                            "b": {"label": c["label"], "id": c["id"], "kind": "drug_class"},
                            **inter,
                        })

        # iDISK (MSKCC/NM) evidence for pairs the seeds don't cover
        if self.has_idisk:
            for h in herbs:
                for c in classes:
                    if (h["id"], c["id"]) in covered:
                        continue
                    for inter in self.idisk_evidence(h["id"], c["id"]):
                        key = ("idisk", h["id"], c["id"], inter["dsi_id"])
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        interactions.append({
                            "type": "herb-drug-evidence",
                            "a": {"label": h["label"], "id": h["id"], "kind": "herb"},
                            "b": {"label": c["label"], "id": c["id"], "kind": "drug_class"},
                            **inter,
                        })

        # supplement x supplement evidence (SUPP.AI pairs where 'drug' is another herb)
        if self.has_herb_herb or getattr(self, "use_canonical_read", False):
            for i in range(len(herbs)):
                for j in range(i + 1, len(herbs)):
                    for inter in self.herb_herb_evidence(herbs[i]["id"], herbs[j]["id"]):
                        key = ("herb-herb", min(herbs[i]["id"], herbs[j]["id"]),
                               max(herbs[i]["id"], herbs[j]["id"]))
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        interactions.append({
                            "type": "herb-herb-evidence",
                            "a": {"label": herbs[i]["label"], "id": herbs[i]["id"], "kind": "herb"},
                            "b": {"label": herbs[j]["label"], "id": herbs[j]["id"], "kind": "herb"},
                            **inter,
                        })

        # CYP450 pathway inference: herb x class (hidden interactions)
        for h in herbs:
            if getattr(self, "use_canonical_read", False):
                continue


            h_roles = self.herb_cyp.get(h["id"])
            if not h_roles:
                continue
            for c in classes:
                if (h["id"], c["id"]) in covered:
                    continue
                c_roles = self.class_cyp.get(c["id"])
                if not c_roles:
                    continue
                for inf in self.cyp_inference(h_roles, c_roles, h["id"], h["label"], c["id"], c["label"]):
                    a, b = sorted([("herb", h["id"]), ("drug_class", c["id"])])
                    verified, rejected = self._reviewed(f"cyp:{a[1]}|{b[1]}")
                    if rejected:
                        continue
                    if verified:
                        inf["trust"] = 0.9
                    key = ("cyp", "herb", h["id"], c["id"], inf["enzyme"], inf["effect"])
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    interactions.append({
                        "a": {"label": h["label"], "id": h["id"], "kind": "herb"},
                        "b": {"label": c["label"], "id": c["id"], "kind": "drug_class"},
                        **inf,
                    })

        # Ingredient-level DDI evidence takes precedence over class fallback.
        ingredient_matches = []
        for item in matched:
            if item["kind"] != "drug_class":
                continue
            ingredient_ids = self._ingredient_ids_for_input(item["input"])
            if ingredient_ids:
                ingredient_matches.append((item, ingredient_ids))
        for i in range(len(ingredient_matches)):
            for j in range(i + 1, len(ingredient_matches)):
                left, left_ids = ingredient_matches[i]
                right, right_ids = ingredient_matches[j]
                for inter in self.ingredient_pairs(left_ids, right_ids):
                    key = ("ingredient-ingredient", min(left["input"], right["input"]),
                           max(left["input"], right["input"]), inter["pair_key"])
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    interactions.append({
                        "type": "drug-drug",
                        "a": {"label": left["input"], "id": left_ids[0], "kind": "drug_ingredient"},
                        "b": {"label": right["input"], "id": right_ids[0], "kind": "drug_ingredient"},
                        **inter,
                    })
        # drug class x drug class (direct rules)
        dd_pairs = set()
        for i in range(len(classes)):
            for j in range(i + 1, len(classes)):
                for inter in self.class_pairs(classes[i]["id"], classes[j]["id"]):
                    dd_pairs.add(tuple(sorted((classes[i]["id"], classes[j]["id"]))))
                    key = ("class-class", min(classes[i]["id"], classes[j]["id"]),
                           max(classes[i]["id"], classes[j]["id"]), inter["effect"])
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    interactions.append({
                        "type": "drug-drug",
                        "a": {"label": classes[i]["label"], "id": classes[i]["id"], "kind": "drug_class"},
                        "b": {"label": classes[j]["label"], "id": classes[j]["id"], "kind": "drug_class"},
                        **inter,
                    })

        # DailyMed FDA-label pairs for class pairs without a direct rule
        if self.has_dailymed:
            for i in range(len(classes)):
                for j in range(i + 1, len(classes)):
                    if tuple(sorted((classes[i]["id"], classes[j]["id"]))) in dd_pairs:
                        continue
                    for inter in self.dailymed_pairs(classes[i]["id"], classes[j]["id"]):
                        key = ("dailymed", min(classes[i]["id"], classes[j]["id"]),
                               max(classes[i]["id"], classes[j]["id"]), inter["effect"])
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        interactions.append({
                            "type": "drug-drug",
                            "a": {"label": classes[i]["label"], "id": classes[i]["id"], "kind": "drug_class"},
                            "b": {"label": classes[j]["label"], "id": classes[j]["id"], "kind": "drug_class"},
                            **inter,
                        })

        # openFDA label rows (public domain) cho class pair chưa có FDA-label DailyMed
        if self.has_openfda:
            for i in range(len(classes)):
                for j in range(i + 1, len(classes)):
                    if tuple(sorted((classes[i]["id"], classes[j]["id"]))) in dd_pairs:
                        continue
                    if self.has_dailymed and self.dailymed_pairs(classes[i]["id"], classes[j]["id"]):
                        continue  # DailyMed SPL XML đã phủ, không trùng
                    for inter in self.openfda_pairs(classes[i]["id"], classes[j]["id"]):
                        key = ("openfda", min(classes[i]["id"], classes[j]["id"]),
                               max(classes[i]["id"], classes[j]["id"]), inter["effect"])
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        interactions.append({
                            "type": "drug-drug",
                            "a": {"label": classes[i]["label"], "id": classes[i]["id"], "kind": "drug_class"},
                            "b": {"label": classes[j]["label"], "id": classes[j]["id"], "kind": "drug_class"},
                            **inter,
                        })

        # DDInter pairs for class pairs without seed or DailyMed coverage
        if self.has_ddinter:
            for i in range(len(classes)):
                for j in range(i + 1, len(classes)):
                    if tuple(sorted((classes[i]["id"], classes[j]["id"]))) in dd_pairs:
                        continue
                    if self.has_dailymed and self.dailymed_pairs(classes[i]["id"], classes[j]["id"]):
                        continue  # FDA label beats NC-SA source
                    for inter in self.ddinter_pairs(classes[i]["id"], classes[j]["id"]):
                        key = ("ddinter", min(classes[i]["id"], classes[j]["id"]),
                               max(classes[i]["id"], classes[j]["id"]))
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        interactions.append({
                            "type": "drug-drug",
                            "a": {"label": classes[i]["label"], "id": classes[i]["id"], "kind": "drug_class"},
                            "b": {"label": classes[j]["label"], "id": classes[j]["id"], "kind": "drug_class"},
                            **inter,
                        })

        # CYP450 pathway inference: class x class (hidden interactions)
        for i in range(len(classes)):
            if getattr(self, "use_canonical_read", False):
                continue
            ra = self.class_cyp.get(classes[i]["id"])
            if not ra:
                continue
            for j in range(i + 1, len(classes)):
                if tuple(sorted((classes[i]["id"], classes[j]["id"]))) in dd_pairs:
                    continue
                rb = self.class_cyp.get(classes[j]["id"])
                if not rb:
                    continue
                for inf in self.cyp_inference(ra, rb, classes[i]["id"], classes[i]["label"],
                                               classes[j]["id"], classes[j]["label"]):
                    a, b = sorted([("drug_class", classes[i]["id"]), ("drug_class", classes[j]["id"])])
                    verified, rejected = self._reviewed(f"cyp:{a[1]}|{b[1]}")
                    if rejected:
                        continue
                    if verified:
                        inf["trust"] = 0.9
                    key = ("cyp", "cls", classes[i]["id"], classes[j]["id"], inf["enzyme"], inf["effect"])
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    interactions.append({
                        "a": {"label": classes[i]["label"], "id": classes[i]["id"], "kind": "drug_class"},
                        "b": {"label": classes[j]["label"], "id": classes[j]["id"], "kind": "drug_class"},
                        **inf,
                    })

        # drug-level rules between specific drug names
        drugs = [normalize(m["input"]) for m in matched if m["kind"] == "drug_class"]
        for a in drugs:
            for b in drugs:
                if a == b:
                    continue
                for inter in self.drug_pairs(a, b):
                    key = ("drug-drug", min(a, b), max(a, b), inter["effect"])
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    interactions.append({
                        "type": "drug-drug",
                        "a": {"label": inter.pop("drug_a", a), "kind": "drug"},
                        "b": {"label": inter.pop("drug_b", b), "kind": "drug"},
                        **inter,
                    })

        # drug class x food
        foods = [m for m in matched if m["kind"] == "food"]
        for f in foods:
            for c in classes:
                for inter in self.food_interactions(c["id"], f["id"]):
                    key = ("drug-food", c["id"], f["id"], inter["effect"])
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    interactions.append({
                        "type": "drug-food",
                        "a": {"label": c["label"], "id": c["id"], "kind": "drug_class"},
                        "b": {"label": f["label"], "id": f["id"], "kind": "food"},
                        **inter,
                    })
        # timing note: interacting items taken at different times of day
        for inter in interactions:
            ta = item_time.get((inter["a"].get("kind"), inter["a"].get("id")))
            tb = item_time.get((inter["b"].get("kind"), inter["b"].get("id")))
            if ta and tb and ta != tb:
                inter["timing"] = "separated"
        # DrugBank-derived drug-food evidence for pairs the seeds don't cover
        if self.has_dfe:
            covered_food = {(inter.get("cls_a"), inter.get("food_id")) for inter in interactions
                            if inter.get("type") == "drug-food"}
            for f in foods:
                for c in classes:
                    if (c["id"], f["id"]) in covered_food:
                        continue
                    for inter in self.drugfood_evidence_pairs(c["id"], f["id"]):
                        key = ("dfe", c["id"], f["id"], inter["effect"])
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        interactions.append({
                            "type": "drug-food",
                            "a": {"label": c["label"], "id": c["id"], "kind": "drug_class"},
                            "b": {"label": f["label"], "id": f["id"], "kind": "food"},
                            **inter,
                        })
        # Make the resolution granularity explicit for every alert.
        for inter in interactions:
            kinds = {(inter.get("a") or {}).get("kind"), (inter.get("b") or {}).get("kind")}
            inter["matchLevel"] = "ingredient" if "drug" in kinds or "drug_ingredient" in kinds else "class"
        interactions.sort(key=lambda x: -x.get("severity_rank", 1))
        for inter in interactions:
            inter.pop("severity_rank", None)
            inter.pop("cls_a", None)
            inter.pop("cls_b", None)
            inter.pop("drug_a", None)
            inter.pop("drug_b", None)
        dep = self.depletions_for([m["id"] for m in matched if m["kind"] == "drug_class"])
        class_ids = [m["id"] for m in matched if m["kind"] == "drug_class"]
        names = [m.get("label", "") for m in matched] + [i.get("name", "") for i in items]
        beers = self.beers_for(class_ids, p.get("age"), drug_names=names)
        qt_risk = self.qt_risk_for(class_ids, p, drug_names=names)
        electrolytes = self.electrolytes_for(class_ids, drug_names=names)
        personalization = personalization_summary(p, interactions, qt_risk=qt_risk, beers=beers)
        checked_sources = self.source_coverage()
        if interactions:
            result = "interaction_found"
            message = (
                "Documented interaction evidence was found in the checked sources."
                if p.get("language") != "vi"
                else "Đã tìm thấy bằng chứng tương tác trong các nguồn đang kiểm tra."
            )
        elif unmatched:
            result = "unknown_unmatched"
            message = (
                "Some items could not be standardized; the result is unknown for those items."
                if p.get("language") != "vi"
                else "Một số mục chưa chuẩn hóa được; kết quả của các mục đó là chưa biết."
            )
        else:
            result = "no_documented_interaction_found"
            message = (
                "No interaction was found in the sources checked; this does not prove the combination is safe."
                if p.get("language") != "vi"
                else "Không tìm thấy tương tác trong các nguồn đang kiểm tra; điều này không chứng minh kết hợp là an toàn."
            )
        return {
            "result": result,
            "coverage": "partial",
            "checkedSources": checked_sources,
            "dataFreshness": self.data_freshness(checked_sources),
            "message": message,
            "patientContext": p,
            "personalization": personalization,
            "matched": matched,
            "interactions": interactions,
            "unmatched": unmatched,
            "depletions": dep,
            "signals": self.signals_for(class_ids),
            "beers": beers,
            "qt_risk": qt_risk,
            "electrolytes": electrolytes,
            "cascades": self.cascades_for([m for m in matched if m["kind"] == "herb"], [m for m in matched if m["kind"] == "drug_class"]),
            "schedule": self.schedule_for(interactions),
        }

    def stats(self) -> dict:
        return {
            "herbs": self.conn.execute("SELECT COUNT(*) FROM herbs").fetchone()[0],
            "drug_classes": self.conn.execute("SELECT COUNT(*) FROM drug_classes").fetchone()[0],
            "interactions": self.conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0],
            "drug_drug_rules": self.conn.execute("SELECT COUNT(*) FROM drug_drug").fetchone()[0],
            "suppai_interactions": (
                self.conn.execute("SELECT COUNT(*) FROM suppai_interactions").fetchone()[0]
                if self.has_suppai else 0
            ),
            "ddinter_interactions": (
                self.conn.execute("SELECT COUNT(*) FROM ddinter_interactions").fetchone()[0]
                if self.has_ddinter else 0
            ),
            "dailymed_interactions": (
                self.conn.execute("SELECT COUNT(*) FROM dailymed_interactions").fetchone()[0]
                if self.has_dailymed else 0
            ),
            "openfda_interactions": (
                self.conn.execute("SELECT COUNT(*) FROM openfda_ddi").fetchone()[0]
                if self.has_openfda else 0
            ),
            "vigi_signals": (
                self.conn.execute("SELECT COUNT(*) FROM vigi_signals").fetchone()[0]
                if self.has_signals else 0
            ),
            "herb_herb_evidence": (
                self.conn.execute("SELECT COUNT(*) FROM herb_herb_evidence").fetchone()[0]
                if self.has_herb_herb else 0
            ),
            "idisk_interactions": (
                self.conn.execute("SELECT COUNT(*) FROM idisk_interactions").fetchone()[0]
                if self.has_idisk else 0
            ),
        }


_engine = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = Engine()
    return _engine

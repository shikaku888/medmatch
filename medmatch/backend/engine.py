"""Matching + interaction analysis engine."""
import json
import re
import unicodedata
from difflib import get_close_matches

from .db import get_conn

SEVERITY_RANK = {"major": 3, "moderate": 2, "minor": 1}

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
    """Lowercase, strip diacritics, keep alnum + spaces + hyphens."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9 \-]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


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
        self.has_ddinter = self._table_exists("ddinter_interactions")
        self.has_depletions = self._table_exists("depletions")
        self.has_dfe = self._table_exists("drugfood_evidence")
        self._build_index()

    def _table_exists(self, name: str) -> bool:
        return (
            self.conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
            ).fetchone()
            is not None
        )

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
        self.class_cyp: dict[str, dict[str, set]] = {}
        self.herb_cyp: dict[str, dict[str, set]] = {}
        for row in self.conn.execute("SELECT * FROM cyp_roles"):
            target = self.class_cyp if row["entity_type"] == "drug_class" else self.herb_cyp
            roles = target.setdefault(row["entity_id"], {"substrate": set(), "inhibitor": set(), "inducer": set()})
            roles[row["role"]].add(row["enzyme"])
    # --- matching ---
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
        ranked = sorted(best.values(), key=lambda r: -r["score"])
        return ranked[:max_results]

    def classify_item(self, name: str) -> dict | None:
        """Best single classification of an item name."""
        m = self.match(name, max_results=1)
        if not m:
            return None
        return m[0]

    # --- interaction lookup ---
    def herb_interactions(self, herb_id: str) -> list:
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

    def class_pairs(self, cls_a: str, cls_b: str) -> list:
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

    def ddinter_pairs(self, cls_a: str, cls_b: str) -> list:
        """DDInter class x class rows (CC BY-NC-SA; MVP use per project plan)."""
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

    def beers_for(self, class_ids: list[str], age) -> list:
        """Beers Criteria flags for users aged 65+. Never lowers anything: additive warning only."""
        age = _coerce_age(age)
        if age is None or age < 65:
            return []
        ids = set(class_ids)
        out = []
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

    def qt_risk_for(self, class_ids: list[str], profile: dict | None) -> list:
        """Additive QT-prolongation risk: count QT drugs + patient risk factors."""
        ids = set(class_ids)
        qt_hits = [label for cid, label in self.QT_CLASSES.items() if cid in ids]
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
        return [{"level": level, "qt_classes": qt_hits, "factors": factors}]
    # --- ④ Electrolyte Depletion (secondary arrhythmia/weakness risk) ---
    ELECTROLYTE_MAP = {
        "antihipertensivos": [("Potassium", "Diuretic component of antihypertensives drives renal K+ loss"), ("Magnesium", "Thiazide/loop diuretics also waste Mg2+")],
        "digoxina": [("Potassium", "Digoxin toxicity risk rises sharply when K+ runs low")],
    }

    def electrolytes_for(self, class_ids: list[str]) -> list:
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
    # Only intestinal/timing-fixable mechanisms qualify. "binding" alone is NOT included:
    # plasma-protein binding and metabolism inhibition are NOT defused by separating doses.
    SCHEDULE_MARKERS = ("absorption", "chelat", "bioavailab", "uptake transporter", "intestinal")

    def schedule_for(self, interactions: list) -> list:
        out = []
        for inter in interactions:
            text = f"{inter.get('mechanism', '')} {inter.get('effect', '')}".lower()
            if any(marker in text for marker in self.SCHEDULE_MARKERS):
                out.append({
                    "a": inter["a"]["label"],
                    "b": inter["b"]["label"],
                    "reason": inter.get("effect") or inter.get("mechanism") or "Absorption interference",
                    "min_hours": 4,
                })
        return out[:8]

    def food_interactions(self, cls_id: str, food_id: str) -> list:
        rows = self.conn.execute(
            "SELECT * FROM drug_food WHERE cls_a = ? AND food_id = ?",
            (cls_id, food_id),
        ).fetchall()
        return [self._interaction_dict(r) for r in rows]

    def drugfood_evidence_pairs(self, cls_id: str, food_id: str) -> list:
        """DrugBank-derived drug-food evidence rows (CC BY-NC flag)."""
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
        rows = self.conn.execute(
            "SELECT * FROM drug_drug WHERE"
            " (drug_a = ? AND drug_b = ?) OR (drug_a = ? AND drug_b = ?)",
            (drug_a, drug_b, drug_b, drug_a),
        ).fetchall()
        return [self._interaction_dict(r) for r in rows]

    def cyp_inference(self, roles_a: dict, roles_b: dict,
                      a_id: str, a_label: str, b_id: str, b_label: str) -> list:
        """Infer hidden interactions from enzyme pathway overlap (plan3).

        Returns up to 2 rows: inhibitor/substrate (levels may rise) and
        inducer/substrate (efficacy may fall), both directions. trust=0.5.
        """
        out = []

        def fmt(enz: str) -> str:
            return "P-glycoprotein" if enz == "p_gp" else f"CYP{enz}"

        for enz in sorted(roles_a.get("inhibitor", set()) & roles_b.get("substrate", set())):
            out.append({
                "type": "cyp-inferred",
                "severity": "moderate",
                "effect": f"{a_label} inhibits {fmt(enz)}, which metabolizes {b_label} — levels of {b_label} may rise.",
                "mechanism": f"{fmt(enz)} inhibition (pathway inference; no direct study found for this pair).",
                "source": "CYP450 pathway inference",
                "trust": 0.5,
                "enzyme": enz,
                "action": ACTIONS["moderate"],
            })
        for enz in sorted(roles_a.get("inducer", set()) & roles_b.get("substrate", set())):
            out.append({
                "type": "cyp-inferred",
                "severity": "moderate",
                "effect": f"{a_label} induces {fmt(enz)}, which metabolizes {b_label} — efficacy of {b_label} may fall.",
                "source": "CYP450 pathway inference",
                "trust": 0.5,
                "enzyme": enz,
                "action": ACTIONS["moderate"],
            })
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
        if self.has_herb_herb:
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

        interactions.sort(key=lambda x: -x.get("severity_rank", 1))
        for inter in interactions:
            inter.pop("severity_rank", None)
            inter.pop("cls_a", None)
            inter.pop("cls_b", None)
            inter.pop("drug_a", None)
            inter.pop("drug_b", None)
        dep = self.depletions_for([m["id"] for m in matched if m["kind"] == "drug_class"])
        class_ids = [m["id"] for m in matched if m["kind"] == "drug_class"]
        p = profile or {}
        return {
            "matched": matched,
            "interactions": interactions,
            "unmatched": unmatched,
            "depletions": dep,
            "beers": self.beers_for(class_ids, p.get("age")),
            "qt_risk": self.qt_risk_for(class_ids, p),
            "electrolytes": self.electrolytes_for(class_ids),
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

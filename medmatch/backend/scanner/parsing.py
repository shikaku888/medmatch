"""Label/receipt parsing pipeline — ported from personalized-product-scanner/server/services/{ocr,product_parser,receipt_scanner}.ts — do not diverge.

OCR backend swapped tesseract.js → RapidOCR (onnxruntime, CPU, no system deps).
All rule tables/heuristics mirror the TS originals.
"""
from __future__ import annotations

import base64
import binascii
import io
import re
import unicodedata
from datetime import datetime, timezone

import numpy as np

# ---------------------------------------------------------------------------
# ocr.ts — local OCR, no API key
# ---------------------------------------------------------------------------
_OCR = None


def _get_ocr():
    global _OCR
    if _OCR is None:
        from rapidocr_onnxruntime import RapidOCR

        _OCR = RapidOCR()
    return _OCR


def _decode_image(image_base64: str):
    raw = image_base64.strip()
    if raw.startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    raw = re.sub(r"\s+", "", raw)
    if len(raw) % 4:
        raw += "=" * (4 - len(raw) % 4)
    try:
        data = base64.b64decode(raw)
    except (binascii.Error, ValueError):
        data = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))

    from PIL import Image

    img = Image.open(io.BytesIO(data))
    return np.array(img.convert("RGB"))


def normalize_ocr_text(text: str) -> str:
    """Normalize OCR surface forms without correcting uncertain characters."""
    normalized = unicodedata.normalize("NFKC", text or "")
    for source, target in JAPANESE_OCR_SURFACE_NORMALIZATIONS.items():
        normalized = normalized.replace(source, target)
    normalized = re.sub(r"(?<=\d)\s*(?:mcg|ug)\b", "μg", normalized, flags=re.I)
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in normalized.splitlines()).strip()

async def ocr_image_to_text(image_base64: str, mime_type: str = "image/jpeg") -> str:
    if not image_base64:
        return ""
    result, _elapse = _get_ocr()(_decode_image(image_base64))
    if not result:
        return ""
    # result rows are [box, text, confidence]
    raw_text = "\n".join(row[1].strip() for row in result if row and len(row) > 1 and str(row[1]).strip())
    return normalize_ocr_text(raw_text)


# ---------------------------------------------------------------------------
# product_parser.ts
# ---------------------------------------------------------------------------
LABEL_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bvegan\b", re.I), "Vegan"),
    (re.compile(r"\bvegetarian\b", re.I), "Vegetarian"),
    (re.compile(r"\bgluten[\s-]*free\b", re.I), "Gluten-Free"),
    (re.compile(r"\borganic\b", re.I), "Organic"),
    (re.compile(r"\bkosher\b", re.I), "Kosher"),
    (re.compile(r"\bhalal\b", re.I), "Halal"),
    (re.compile(r"\bhypoallergenic\b", re.I), "Hypoallergenic"),
    (re.compile(r"\bnon[\s-]*gmo\b", re.I), "Non-GMO"),
    (re.compile(r"\bsugar[\s-]*free\b", re.I), "Sugar-Free"),
    (re.compile(r"\bparaben[\s-]*free\b", re.I), "Paraben-Free"),
    (re.compile(r"\bfragrance[\s-]*free\b", re.I), "Fragrance-Free"),
    (re.compile(r"\bdermatologist( tested| approved)?\b", re.I), "Dermatologist Tested"),
]

ALLERGEN_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(milk|dairy|lactose|whey|casein)\b|乳成分|乳製品|牛乳|乳糖|乳(?!酸)", re.I), "Milk"),
    (re.compile(r"\b(egg|albumin)\b|卵|鶏卵|卵白|卵黄", re.I), "Egg"),
    (re.compile(r"\b(peanut|groundnut|arachis)\b|落花生|らっかせい|ピーナッツ", re.I), "Peanuts"),
    (re.compile(r"\b(almond|cashew|walnut|hazelnut|pecan|pistachio|macadamia|brazil nut|tree nut)\b|木の実|ナッツ|アーモンド|カシューナッツ|くるみ", re.I), "Tree Nuts"),
    (re.compile(r"\b(soy|soya|soybean)\b|大豆|枝豆|しょうゆ|醤油|味噌|みそ", re.I), "Soy"),
    (re.compile(r"\b(wheat|gluten|barley|rye|spelt)\b|小麦|大麦|ライ麦|麦", re.I), "Gluten / Wheat"),
    (re.compile(r"\b(fish|cod|salmon|tuna)\b|魚|魚介", re.I), "Fish"),
    (re.compile(r"\b(shellfish|shrimp|crab|lobster|crayfish|mollusk|clam|mussel|oyster|squid)\b|えび|エビ|かに|カニ|甲殻類", re.I), "Shellfish"),
    (re.compile(r"\bsesame\b|ごま|ゴマ|胡麻", re.I), "Sesame"),
    (re.compile(r"\bmustard\b|からし|カラシ|辛子", re.I), "Mustard"),
    (re.compile(r"\bcelery\b|セロリ", re.I), "Celery"),
    (re.compile(r"\b(sulphite|sulfite)\b|亜硫酸|二酸化硫黄", re.I), "Sulphites"),
    (re.compile(r"\bgelatin\b|ゼラチン", re.I), "Gelatin"),
]

_COSMETIC_RE = re.compile(
    r"\b(serum|cleanser|moisturi[sz]er|shampoo|conditioner|lotion|cream|skin|skincare|hair|cosmetic|spf|sunscreen|retinol|niacinamide|toner|balm|deodorant|makeup|mascara)\b",
    re.I,
)
_INGREDIENT_SECTION_RE = re.compile(
    r"(?:\b(ingredients?|thành phần|composition|contains|inactive ingredients)\b|原材料名|原材料)",
    re.I,
)
_NOISE_LINE_RE = re.compile(
    r"^(?:product|brand|net wt|made in|best before|lot|exp)\b|^(?:商品名|内容量|賞味期限|保存方法|栄養成分表示|摂取方法)",
    re.I,
)
_JAPANESE_INGREDIENT_HEADER_RE = re.compile(r"原材料名?")
_JAPANESE_CHAR_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
JAPANESE_OCR_SURFACE_NORMALIZATIONS: dict[str, str] = {
    "･": "・",
    "﹒": "・",
    "﹕": ":",
    "：": ":",
}

# /\b[\p{L}][\p{L}\s-]{0,20}[\s-]*free\b/giu — "\w" trick keeps letter semantics
_FREE_CLAIM_RE = re.compile(r"\b[^\W\d_][^\W\d_\s\-]{0,20}[\s\-]*free\b", re.I)

# Japanese package claims such as 小麦不使用 mean the named allergen is
# excluded, not present. Remove only the claim phrase before positive matching.
_JAPANESE_FREE_CLAIM_RE = re.compile(
    r"(?:小麦|大麦|ライ麦|乳成分|乳製品|牛乳|卵|落花生|ピーナッツ|大豆|えび|エビ|かに|カニ|ごま|ゴマ|そば)\s*不使用"
)

_HAS_WORD_RE = re.compile(r"(?:[^\W\d_]){3,}")  # \p{L}{3,}
_DOSAGE_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?\s*(%|mg|mcg|µg|ug|g|kg|ml|iu)\b", re.I)
_ENUM_PAREN_RE = re.compile(r"\((?:[^)]*\bE\s?\d{3,4}[a-z]?\b[^)]*|[^)]*\d[^)]*)\)", re.I)
_SPLIT_DELIM_RE = re.compile(r"[,;、•|·\u2022\n\u2028\u2029]|\bdelivers\b|\bcontains\b(?!\s*(?:no|nothing))", re.I)
_LEADING_JUNK_RE = re.compile(r"^(product\s*[:\-]\s*)", re.I)
_NONE_START_RE = re.compile(r"^(none|nothing)\b", re.I)
_FREE_START_RE = re.compile(r"^[^\W\d_\s\-][^\W\d_\s\-]*\s*-?\s*free\b", re.I)


def _trim_edges(s: str) -> str:
    """JS: .replace(/^[^\\p{L}]+|[^^\\p{L}\\)\\]]+$/gu, ' ')."""
    i, j = 0, len(s)
    while i < j and not s[i].isalpha():
        i += 1
    while j > i and not (s[j - 1].isalpha() or s[j - 1] in ")]"):
        j -= 1
    return s[i:j]


def detect_allergens(text: str) -> list[str]:
    # "gluten-free", "dairy-free"... are safety claims, not allergen content
    content = _FREE_CLAIM_RE.sub(" ", text)
    content = _JAPANESE_FREE_CLAIM_RE.sub(" ", content)
    return [label for rx, label in ALLERGEN_PATTERNS if rx.search(content)]


def detect_labels(text: str) -> list[str]:
    return [label for rx, label in LABEL_PATTERNS if rx.search(text)]


def split_ingredients(section: str) -> list[str]:
    cleaned = _ENUM_PAREN_RE.sub(" ", _DOSAGE_TOKEN_RE.sub(" ", normalize_ocr_text(section)))
    out: list[str] = []
    seen: set[str] = set()
    for part in _SPLIT_DELIM_RE.split(cleaned):
        p = re.sub(r"\s+", " ", _INGREDIENT_SECTION_RE.sub(" ", _trim_edges(part))).strip()
        if len(p) < 2 or len(p) > 64:
            continue
        if not (_HAS_WORD_RE.search(p) or _JAPANESE_CHAR_RE.search(p)):
            continue  # needs a real word or Japanese label term
        if _NOISE_LINE_RE.search(p):
            continue
        # allergen-statement fragments, not ingredients: "none", "Gluten free. Vegan"
        if _NONE_START_RE.match(p):
            continue
        if _FREE_START_RE.match(p):
            continue
        key = p.casefold()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out[:60]


def _detect_brand(lines: list[str]) -> str | None:
    brand_line = next((l for l in lines if re.match(r"^(brand|by|manufactured by|distributed by)\b", l, re.I)), None)
    if brand_line:
        return re.sub(r"\s+", " ", re.sub(r"^(brand|by|manufactured by|distributed by)\s*[:\-]?\s*", "", brand_line, flags=re.I)).strip()
    return None


def _extract_ingredient_section(lines: list[str], header_idx: int) -> str:
    header_line = lines[header_idx]
    header_match = _JAPANESE_INGREDIENT_HEADER_RE.search(header_line)
    if not header_match:
        return ", ".join(lines[header_idx:])

    section_lines = [header_line[header_match.end():]]
    for line in lines[header_idx + 1:]:
        if _NOISE_LINE_RE.search(line) or line.startswith(("【", "[", "［")):
            break
        section_lines.append(line)
    return ", ".join(section_lines)


def parse_ingredients_text(raw_text: str, suggested_name: str | None = None) -> dict:
    """Parse raw ingredient-list text (from OCR or user typing) into a structured product."""
    raw = normalize_ocr_text(raw_text).strip()
    lines = [re.sub(r"\s+", " ", l).strip() for l in raw.splitlines()]
    lines = [l for l in lines if l]

    # Product name: first line that is not an ingredient-section header / noise.
    product_name = suggested_name.strip() if suggested_name else ""
    if not product_name:
        name_line = next(
            (l for l in lines if not _INGREDIENT_SECTION_RE.search(l) and 3 <= len(l) <= 90),
            None,
        )
        product_name = _LEADING_JUNK_RE.sub("", name_line) if name_line else "Scanned product"

    brand = _detect_brand(lines)

    header_idx = next((i for i, l in enumerate(lines) if _INGREDIENT_SECTION_RE.search(l)), -1)
    has_ingredient_section = header_idx >= 0
    section_blob = _extract_ingredient_section(lines, header_idx) if has_ingredient_section else ", ".join(lines)
    ingredients_text = re.sub(r"^[^:：]*[:：]\s*", "", section_blob)
    ingredients_list = split_ingredients(ingredients_text)

    return {
        "productName": product_name,
        "brand": brand,
        "productType": "cosmetic" if _COSMETIC_RE.search(raw) else "food",
        "ingredientsText": ingredients_text,
        "ingredientsList": ingredients_list,
        "hasIngredientSection": has_ingredient_section,
        "allergens": detect_allergens(raw),
        "labels": detect_labels(raw),
    }


async def parse_product_image(image_base64: str, mime_type: str = "image/jpeg") -> dict:
    """Parse a product label photo: local OCR → rule-based structuring."""
    text = await ocr_image_to_text(image_base64, mime_type)
    if not text:
        return {
            "productName": "Unreadable label",
            "productType": "food",
            "ingredientsText": "",
            "ingredientsList": [],
            "allergens": [],
            "labels": [],
        }
    return parse_ingredients_text(text)


# ---------------------------------------------------------------------------
# receipt_scanner.ts
# ---------------------------------------------------------------------------
_MEDICATION_RE = re.compile(r"\b(mg|mcg|tablet|tablets|capsule|capsules|ibuprofen|paracetamol|acetaminophen|aspirin|warfarin|statin|metformin|omeprazole|amoxicillin|antibiotic)\b", re.I)
_SUPPLEMENT_RE = re.compile(r"\b(vitamin|omega|probiotic|supplement|herbal|extract|multivitamin|zinc|magnesium|calcium|coq10|ginseng|turmeric|echinacea)\b", re.I)
_RECEIPT_COSMETIC_RE = re.compile(r"\b(shampoo|soap|cream|lotion|serum|cleanser|toothpaste|deodorant|cosmetic|skincare|sunscreen)\b", re.I)
_HOUSEHOLD_RE = re.compile(r"\b(detergent|cleaner|paper towel|tissue|trash|sponge|bleach|dish soap|fabric)\b", re.I)
_RECEIPT_NOISE_RE = re.compile(r"(total|subtotal|change|cash|card|visa|mastercard|debit|credit|tax|receipt|invoice|thank|store #|till|terminal|balance|points|saved|coupon|\$\s?\d)", re.I)
_PRICE_TAIL_RE = re.compile(r"[\s\d.,$€£]*$")
_QTY_PREFIX_RE = re.compile(r"^\d+\s*[xX*]\s*")

ALLERGEN_KEYS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bmilk|dairy|lactose|whey|cheese|yogurt\b", re.I), "Milk"),
    (re.compile(r"\begg|mayo(nnaise)?\b", re.I), "Egg"),
    (re.compile(r"\bpeanut\b", re.I), "Peanuts"),
    (re.compile(r"\balmond|cashew|walnut|hazelnut|pecan|pistachio|nut\b", re.I), "Tree Nuts"),
    (re.compile(r"\bsoy|soya|tofu|edamame\b", re.I), "Soy"),
    (re.compile(r"\bwheat|gluten|bread|pasta|barley|rye\b", re.I), "Gluten / Wheat"),
    (re.compile(r"\bsalmon|tuna|fish\b", re.I), "Fish"),
    (re.compile(r"\bshrimp|crab|lobster|shellfish|squid|mussel|oyster|clam\b", re.I), "Shellfish"),
    (re.compile(r"\bsesame\b", re.I), "Sesame"),
    (re.compile(r"\bcelery\b", re.I), "Celery"),
]


def _classify_line(line: str) -> str:
    if _MEDICATION_RE.search(line):
        return "medication"
    if _SUPPLEMENT_RE.search(line):
        return "supplement"
    if _RECEIPT_COSMETIC_RE.search(line):
        return "cosmetic"
    if _HOUSEHOLD_RE.search(line):
        return "household"
    return "food"


def _detect_receipt_allergens(line: str) -> list[str]:
    return [label for rx, label in ALLERGEN_KEYS if rx.search(line)]


def _member_allergen_overlap(item: dict, member: dict) -> list[str]:
    known = [(a or "").lower() for a in list(member.get("allergies") or []) + list(member.get("customAllergens") or [])]
    known = [k for k in known if k]
    if not known:
        return []
    haystack = " ".join([item.get("name") or "", *(item.get("detectedAllergens") or [])]).lower()
    return [k for k in known if k and k in haystack]


def _status_from_counts(major_count: int, allergen_hits: int, flagged: int) -> dict:
    if allergen_hits > 0 or major_count > 0:
        return {"status": "danger", "score": max(5, 40 - major_count * 10)}
    if flagged > 1:
        return {"status": "caution", "score": 60}
    return {"status": "safe", "score": 90}


def _parse_receipt_lines(text: str) -> list[str]:
    out = []
    for l in text.splitlines():
        l2 = re.sub(r"\s+", " ", l).strip()
        if len(l2) < 3 or not _HAS_WORD_RE.search(l2):
            continue
        if _RECEIPT_NOISE_RE.search(l2):
            continue
        out.append(l2)
    return out[:24]


def _iso_now() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


async def _audit_item(raw_line: str, index: int, active_profile: dict, family_members: list[dict]) -> dict:
    from backend.scanner.personalization import analyze_ingredient_safety
    from backend.scanner.medmatch_bridge import normalize_ingredient, analyze_medications

    name = (
        re.sub(r"\s+", " ", _PRICE_TAIL_RE.sub("", _QTY_PREFIX_RE.sub("", raw_line))).strip()
        or f"Item {index + 1}"
    )
    product_type = _classify_line(raw_line)
    detected_allergens = _detect_receipt_allergens(raw_line)
    safety = analyze_ingredient_safety([name])
    flagged_additives = [s["name"] for s in safety if s["hazardLevel"] != "safe"]

    # Identify the item in the medical database (Lớp 1 normalizer).
    lookup_name = re.sub(r"\b(tablets?|capsules?|softgels?|gummies|drops|syrup|oil)\b", "", 
                         re.sub(r"\b\d+(?:\.\d+)?\s*(mg|mcg|g|iu|ml)\b.*$", "", name, flags=re.I), flags=re.I)
    lookup_name = re.sub(r"\s+", " ", lookup_name).strip()
    hit = normalize_ingredient(lookup_name) if product_type in ("medication", "supplement") else None

    members = [{**active_profile, "name": active_profile.get("name") or "You"}, *family_members]
    affected: set[str] = set()
    allergen_hit_total = 0
    worst_major = 0
    warning_reason = ""

    for member in members[:6]:
        allergen_hits = _member_allergen_overlap({"name": name, "detectedAllergens": detected_allergens}, member)
        major_count = 0
        if hit and len(member.get("medications") or []):
            try:
                analysis = analyze_medications(
                    [{"name": hit["label"], "kind": hit["kind"], "matched": {"kind": hit["kind"], "id": hit["id"]}}],
                    {
                        "age": member.get("age"),
                        "gender": member.get("gender"),
                        "kidneyFunction": member.get("kidneyFunction"),
                        "liverFunction": member.get("liverFunction"),
                    },
                )
                major_count = sum(1 for i in analysis.get("interactions", []) if i.get("severity") == "major")
                if major_count > 0:
                    pairs = ",".join(
                        f"{(i.get('a') or {}).get('label') or ''}×{(i.get('b') or {}).get('label') or ''}"
                        for i in analysis["interactions"]
                        if i.get("severity") == "major"
                    ).strip(",")
                    warning_reason = f"Interacts with {member.get('name')}'s medications ({pairs})".strip()
            except Exception:
                pass  # backend issue — allergen checks still apply
        if allergen_hits:
            allergen_hit_total += 1
            affected.add(member.get("name") or "Member")
            if not warning_reason:
                warning_reason = f"Contains {', '.join(allergen_hits)} — allergen for {member.get('name')}"
        if major_count > 0:
            affected.add(member.get("name") or "Member")
        worst_major = max(worst_major, major_count)

    status = _status_from_counts(worst_major, allergen_hit_total, len(flagged_additives))
    hit_label = hit["label"] if hit else None
    return {
        "id": f"item_{index + 1}",
        "name": name,
        "category": "Grocery" if product_type == "food" else product_type[:1].upper() + product_type[1:],
        "productType": product_type,
        "ingredientsSummary": hit_label or (name if product_type in ("medication", "supplement") else ""),
        "detectedAllergens": detected_allergens,
        "flaggedAdditives": flagged_additives,
        "status": status["status"],
        "score": status["score"],
        "affectedFamilyMembers": list(affected),
        "warningReason": warning_reason
        or (f"Flagged additives: {', '.join(flagged_additives[:3])}" if len(flagged_additives) >= 2 else None),
        "hitLabel": hit_label,
    }


async def audit_receipt(input: dict, active_profile: dict, all_family_profiles: list[dict]) -> dict:
    receipt_text = input.get("receiptText")
    if receipt_text and receipt_text.strip():
        text = receipt_text
    else:
        text = await ocr_image_to_text(input.get("imageBase64") or "", input.get("mimeType") or "image/jpeg")

    lines = _parse_receipt_lines(text)
    audited = []
    for i in range(min(len(lines), 12)):
        audited.append(await _audit_item(lines[i], i, active_profile, all_family_profiles))

    # In-cart cross-check: interactions BETWEEN receipt items
    identified = [a for a in audited if a["hitLabel"]]
    if len(identified) >= 2:
        try:
            from backend.scanner.medmatch_bridge import analyze_medications

            analysis = analyze_medications(
                [{"name": a["hitLabel"]} for a in identified],
                {
                    "age": active_profile.get("age"),
                    "gender": active_profile.get("gender"),
                    "kidneyFunction": active_profile.get("kidneyFunction"),
                    "liverFunction": active_profile.get("liverFunction"),
                },
            )
            for inter in analysis.get("interactions", []):
                if inter.get("severity") not in ("major", "moderate"):
                    continue
                la = ((inter.get("a") or {}).get("label") or "").lower()
                lb = ((inter.get("b") or {}).get("label") or "").lower()

                def other(label: str, inter=inter, la=la):
                    return inter["b"]["label"] if label == la else inter["a"]["label"]

                for a in audited:
                    lbl = (a["hitLabel"] or "").lower()
                    if not lbl or (lbl != la and lbl != lb):
                        continue
                    a["status"] = "danger" if inter["severity"] == "major" else ("danger" if a["status"] == "danger" else "caution")
                    a["score"] = min(a["score"], 20 if inter["severity"] == "major" else 50)
                    members_set = set(a["affectedFamilyMembers"]) | {active_profile.get("name") or "You"}
                    a["affectedFamilyMembers"] = list(members_set)
                    mech = f" — {inter['mechanism']}" if inter.get("mechanism") else ""
                    a["warningReason"] = f"In-cart interaction: {(inter.get('a') or {}).get('label')} × {(inter.get('b') or {}).get('label')} [{inter['severity']}]{mech}. Also affects: {other(lbl)}"
        except Exception:
            pass  # keep allergen-only audit

    items = audited
    safe_count = sum(1 for i in items if i["status"] == "safe")
    flagged_count = sum(1 for i in items if i["status"] == "caution")
    danger = sum(1 for i in items if i["status"] == "danger")
    overall_score = round(sum(i["score"] for i in items) / len(items)) if items else 100
    ultra_processed = sum(1 for i in items if len(i["flaggedAdditives"]) >= 3)

    family_impact_summary: list[str] = []
    for item in items:
        for member in item["affectedFamilyMembers"]:
            family_impact_summary.append(f'{member}: avoid "{item["name"]}" — {item.get("warningReason") or "flagged in audit"}')

    all_key_allergens = sorted({al for i in items for al in i["detectedAllergens"]}, key=lambda x: x)
    seen_add: set[str] = set()
    critical_additives: list[str] = []
    for a in (add for i in items for add in i["flaggedAdditives"]):
        if a not in seen_add:
            seen_add.add(a)
            critical_additives.append(a)

    return {
        "storeName": input.get("storeNameHint") or (lines[0] if lines else "") or "Unknown store",
        "auditDate": _iso_now(),
        "totalItemsCount": len(items),
        "overallScore": overall_score,
        "status": "danger" if danger > 0 else ("caution" if flagged_count > 0 else "safe"),
        "safeItemsCount": safe_count,
        "flaggedItemsCount": flagged_count,
        "highRiskCount": danger,
        "ultraProcessedPercentage": round((ultra_processed / len(items)) * 100) if items else 0,
        "keyAllergensFound": list(all_key_allergens),
        "criticalAdditivesFound": critical_additives[:8],
        "familyImpactSummary": list(dict.fromkeys(family_impact_summary))[:12],
        "items": items,
    }

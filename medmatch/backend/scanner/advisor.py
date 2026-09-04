"""Deterministic safe-swaps generator + rule-based health advisor.

Ported from personalized-product-scanner/server/services/{smart_swaps,ai_chat}.ts — do not diverge.
Candidates come from the iDISK catalog via the MedMatch backend product search
(called in-process); the medical verdict always comes from the engine, never an LLM.
"""
from __future__ import annotations

import re

from backend.db import get_conn
from backend import idisk_products


# ---------------------------------------------------------------------------
# smart_swaps.ts
# ---------------------------------------------------------------------------
CURATED_FOOD_SWAPS: list[dict] = [
    {
        "id": "swap_fb_1",
        "name": "Organic Whole Oat Milk (Unsweetened)",
        "brand": "Oatly / Califia Farms",
        "productType": "food",
        "category": "Dairy Alternative",
        "score": 95,
        "whyBetter": ["Zero dairy or lactose", "Zero added sugars"],
        "keyBenefits": ["Fortified with Vitamin B12 and D", "Clean single-digit ingredient deck"],
        "cleanHighlights": ["Certified Vegan", "Dairy-Free", "Nut-Free facility"],
        "priceRange": "$$ - Average",
        "activeIngredients": ["Oats", "Water"],
        "certificationBadges": ["USDA Organic", "Non-GMO Project"],
    },
    {
        "id": "swap_fb_2",
        "name": "Roasted Sunflower Seed Butter (Creamy)",
        "brand": "SunButter",
        "productType": "food",
        "category": "Nut Butter Alternative",
        "score": 98,
        "whyBetter": ["100% Free of Top 8 Allergens", "Zero peanuts or tree nuts", "School safe"],
        "keyBenefits": ["7g Plant Protein per serving", "Rich in Vitamin E and Magnesium"],
        "cleanHighlights": ["Peanut-Free", "Tree Nut-Free", "Kosher"],
        "priceRange": "$ - Affordable",
        "activeIngredients": ["Sunflower Seeds", "Salt"],
        "certificationBadges": ["Certified Gluten-Free", "School Safe"],
    },
    {
        "id": "swap_fb_3",
        "name": "Artisan Ancient Grain Sourdough",
        "brand": "Base Culture / Simple Mills",
        "productType": "food",
        "category": "Bakery",
        "score": 91,
        "whyBetter": ["Naturally fermented", "Zero high-fructose corn syrup or bleached flour"],
        "keyBenefits": ["Fermented grain product"],
        "cleanHighlights": ["Gluten-Free Option", "Non-GMO", "No Artificial Preservatives"],
        "priceRange": "$$ - Moderate",
        "activeIngredients": ["Ancient Grain Flour", "Sourdough Culture", "Water", "Salt"],
        "certificationBadges": ["Non-GMO Verified"],
    },
]

CURATED_COSMETIC_SWAPS: list[dict] = [
    {
        "id": "swap_fb_c1",
        "name": "Toleriane Double Repair Matte Face Moisturizer",
        "brand": "La Roche-Posay",
        "productType": "cosmetic",
        "category": "Skincare",
        "score": 97,
        "whyBetter": ["100% Fragrance-Free", "No drying alcohol or essential oils", "Non-comedogenic"],
        "keyBenefits": ["Ceramide-3 + Niacinamide barrier repair", "Prebiotic thermal water"],
        "cleanHighlights": ["Dermatologist Tested", "Oil-Free"],
        "priceRange": "$$ - Mid Tier",
        "activeIngredients": ["Ceramide-3", "Niacinamide", "Thermal Spring Water", "Glycerin"],
        "certificationBadges": ["National Eczema Association Accepted"],
    },
    {
        "id": "swap_fb_c2",
        "name": "Ultra Gentle Hydrating Daily Cleanser",
        "brand": "Vanicream / CeraVe",
        "productType": "cosmetic",
        "category": "Cleanser",
        "score": 99,
        "whyBetter": ["Free of parabens, sulfates, formaldehyde releasers", "Zero botanical allergens"],
        "keyBenefits": ["Maintains skin lipid mantle", "Safe for eczema and rosacea"],
        "cleanHighlights": ["Fragrance-Free", "Preservative-Free", "Hypoallergenic"],
        "priceRange": "$ - Value",
        "activeIngredients": ["Glycerin", "Cetearyl Alcohol", "Ceramide-3"],
        "certificationBadges": ["National Eczema Association"],
    },
]


def _search_idisk(query: str, limit: int = 6) -> list[dict]:
    try:
        if not query.strip():
            return []
        conn = get_conn()
        results = []
        for p in idisk_products.search_products(conn, query.strip(), limit=min(limit, 20)):
            ingredients = idisk_products.product_ingredients(conn, p["dsp_id"])
            results.append({**p, "ingredients": ingredients[:12]})
        return results
    except Exception:
        return []


def _forbidden_tokens(profile: dict, product: dict) -> list[str]:
    meds = [(m or "").lower() for m in (profile.get("medications") or [])]
    interactions = ((product.get("medMatch") or {}).get("interactions")) or []
    avoided = []
    for i in interactions:
        for side in ("a", "b"):
            lbl = (i.get(side) or {}).get("label")
            if lbl:
                avoided.append(lbl.lower())
    seen: set[str] = set()
    out = []
    for t in meds + avoided:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _swap_anchors(product: dict) -> list[str]:
    """Anchor ingredients the swap must replace (matched entities beat raw strings)."""
    anchors: list[str] = []
    for m in ((product.get("medMatch") or {}).get("matched")) or []:
        label = m.get("label")
        if label and label not in anchors:
            anchors.append(label)
    for ing in (product.get("ingredientsList") or [])[:10]:
        word = re.sub(r"\s*\d+(?:\.\d+)?\s*(mg|mcg|iu|%)\b.*$", "", ing, flags=re.I).strip()
        if len(word) >= 4 and not any(a.lower() == word.lower() for a in anchors):
            anchors.append(word)
        if len(anchors) >= 3:
            break
    return anchors[:3]


def _merchandising_candidates(items: list[dict]) -> list[dict]:
    return [
        {
            **item,
            "recommendation_type": "merchandising_candidate",
            "medical_recommendation": False,
            "claims_note": "Catalog or supplier claims require independent verification.",
        }
        for item in items
    ]


async def generate_safe_swaps(current_product: dict, user_profile: dict) -> list[dict]:
    anchors = _swap_anchors(current_product)
    forbidden = _forbidden_tokens(user_profile, current_product)
    seen: set[str] = set()
    candidates: list[dict] = []

    for anchor in anchors:
        query = anchor.split()[-1] if anchor.split() else anchor
        anchor_key = anchor.lower()
        pool = _search_idisk(query, 8)
        for p in pool:
            name_key = p["name"].lower()
            if name_key in seen:
                continue
            ingredients = [i.lower() for i in (p.get("ingredients") or [])]
            # a swap must NOT contain the anchor we are replacing, nor any user medication token
            if anchor_key in name_key or any(anchor_key in i for i in ingredients):
                continue
            if any(
                f and (f in i or f in name_key)
                for f in forbidden
                for i in ingredients
            ):
                continue
            if all(not i for i in ingredients) and not re.search(r"vitamin|omega|probiotic|extract|herb", name_key, re.I):
                continue
            seen.add(name_key)
            candidates.append(
                {
                    "id": p.get("dsp_id"),
                    "name": p["name"],
                    "brand": p.get("company") or "iDISK catalog",
                    "productType": "food",
                    "category": f"Alternative to {anchor}",
                    "score": 88,
                    "whyBetter": [
                        f"Does not contain {anchor}",
                        "Candidate screened against current medication tokens; verify the full label.",
                    ],
                    "keyBenefits": (p.get("ingredients") or [])[:4],
                    "cleanHighlights": ["Interaction-checked by MedMatch engine"],
                    "activeIngredients": (p.get("ingredients") or [])[:6],
                }
            )
            if len(candidates) >= 5:
                break
        if len(candidates) >= 5:
            break

    if candidates:
        return _merchandising_candidates(candidates)
    curated = CURATED_FOOD_SWAPS if current_product.get("productType") == "food" else CURATED_COSMETIC_SWAPS
    return _merchandising_candidates(curated)


# ---------------------------------------------------------------------------
# ai_chat.ts
# ---------------------------------------------------------------------------
SEVERITY_RANK = {
    "contraindicated": 0,
    "major": 1,
    "moderate": 2,
    "minor": 3,
    "mild": 3,
    "evidence": 4,
}

DISCLAIMER = {
    "en": "This is reference information from public databases — not medical advice. Please confirm with your doctor or pharmacist.",
    "vi": "Đây là thông tin tham khảo từ dữ liệu công khai — không phải lời khuyên y tế. Hãy xác nhận với bác sĩ hoặc dược sĩ.",
}

# Mechanism → plain-language explanation per language
_MECH_PLAIN = {
    "bleed": {
        "en": "both can make your blood slower to clot — the bleeding risk adds up",
        "vi": "cả hai đều làm máu khó đông hơn — nguy cơ chảy máu sẽ cộng dồn",
    },
    "serotonin": {
        "en": "they push serotonin the same direction, which in rare cases can spiral into serotonin syndrome (agitation, fever, tremor)",
        "vi": "cả hai cùng đẩy serotonin lên, hiếm khi có thể dẫn tới hội chứng serotonin (kích động, sốt, run)",
    },
    "sedat": {
        "en": "the drowsiness multiplies — driving or machinery becomes risky",
        "vi": "tác dụng buồn ngủ nhân đôi — lái xe hay vận hành máy sẽ nguy hiểm",
    },
    "absorb": {
        "en": "one blocks the other from being absorbed, so it may simply stop working",
        "vi": "một chất cản trở hấp thu chất kia, khiến thuốc có thể mất tác dụng",
    },
    "hypoglyc": {
        "en": "blood sugar can drop lower than intended",
        "vi": "đường huyết có thể giảm thấp hơn dự kiến",
    },
    "qt": {
        "en": "together they can disturb the heart's electrical rhythm (QT prolongation)",
        "vi": "kết hợp có thể gây rối loạn nhịp điện tim (kéo dài QT)",
    },
    "cyp": {
        "en": "they compete for the same liver enzyme, so drug levels in your blood can swing up or down",
        "vi": "cả hai tranh cùng enzym gan, nồng độ thuốc trong máu có thể tăng vọt hoặc tụt",
    },
    "potass": {
        "en": "potassium can swing out of range, which the heart is very sensitive to",
        "vi": "kali có thể lệch khỏi vùng an toàn — tim rất nhạy cảm với điều này",
    },
}


def _plain_reason(text: str, lang: str) -> str:
    t = (text or "").lower()
    for key, phrases in _MECH_PLAIN.items():
        if key in t:
            return phrases.get(lang) or phrases["en"]
    return ""


def _worst(med_match: dict | None):
    rows = (med_match or {}).get("interactions") or []
    if not rows:
        return None, []
    ranked = sorted(rows, key=lambda i: SEVERITY_RANK.get(i.get("severity"), 9))
    return ranked[0], ranked


_VERDICT = {
    "en": {
        "contraindicated": "Please do not combine these — this is a known dangerous pairing.",
        "major": "Short answer: this is a risky combination — talk to your doctor before continuing.",
        "moderate": "Short answer: usable with care, but worth a heads-up to your doctor or pharmacist.",
        "minor": "Short answer: generally fine — just something small to keep in mind.",
        "none": "No documented interaction was found in the checked sources; this does not prove the combination is safe.",
        "unknown": "The result is unknown because one or more items were not recognized or checked. Do not treat the combination as safe.",
    },
    "vi": {
        "contraindicated": "Đừng kết hợp những thứ này — đây là cặp đã được ghi nhận là nguy hiểm.",
        "major": "Trả lời ngắn: đây là kết hợp rủi ro — hãy trao đổi với bác sĩ trước khi tiếp tục.",
        "moderate": "Trả lời ngắn: dùng được nếu cẩn thận, nhưng nên báo bác sĩ/dược sĩ biết.",
        "minor": "Trả lời ngắn: nhìn chung ổn — chỉ cần lưu ý nhỏ.",
        "none": "Không tìm thấy tương tác trong các nguồn đang kiểm tra; điều này không chứng minh kết hợp là an toàn.",
        "unknown": "Chưa thể kết luận vì có một hoặc nhiều mục chưa được nhận dạng hoặc kiểm tra.",
    },
}

_ACTIONS = {
    "en": {
        "contraindicated": ["Do not start or combine these on your own.", "Contact your prescriber before the next dose."],
        "major": ["Don't change anything on your own — call your doctor or pharmacist first.", "Know the warning signs (see below) and act early if they appear."],
        "moderate": ["Keep doses apart in time if that applies (see the schedule note).", "Mention this combination at your next appointment.", "Watch for the symptoms described above."],
        "minor": ["No change needed — just stay alert to how you feel.", "Worth mentioning in passing at your next check-up."],
        "none": ["Keep the checked-source limitation in mind; do not treat this as a safety clearance.", "If you add anything new later, re-scan — the answer can change."],
        "unknown": ["Confirm the item names or label details, then scan again.", "Do not treat an unmatched item as safe."],
    },
    "vi": {
        "contraindicated": ["Đừng tự ý bắt đầu hay kết hợp — liên hệ bác sĩ trước liều tiếp theo."],
        "major": ["Không tự thay đổi gì — gọi bác sĩ/dược sĩ trước.", "Nhớ các dấu hiệu cảnh báo (bên dưới) và xử lý sớm nếu xuất hiện."],
        "moderate": ["Cách thời điểm uống nếu áp dụng được (xem ghi chú lịch uống).", "Nhắc kết hợp này ở lần khám tới.", "Theo dõi các triệu chứng đã nêu."],
        "minor": ["Không cần thay đổi — chỉ lưu ý cảm giác cơ thể.", "Đủ để nhắc qua ở lần khám định kỳ."],
        "none": ["Hãy nhớ giới hạn của các nguồn đã kiểm tra; đừng xem đây là xác nhận an toàn.", "Nếu thêm thuốc/TPCN mới sau này, hãy quét lại — kết luận có thể đổi."],
        "unknown": ["Xác nhận lại tên mục hoặc chi tiết trên nhãn rồi quét lại.", "Không xem mục chưa nhận dạng là an toàn."],
    },
}


_RED_FLAGS = {
    "en": {
        "bleed": "unusual bruising, dark/tarry stools, blood in urine, prolonged nosebleeds",
        "serotonin": "agitation, fever, fast heartbeat, tremor, sweating",
        "sedat": "extreme drowsiness, confusion, slowed breathing",
        "hypoglyc": "shakiness, sweating, sudden hunger, confusion (low blood sugar)",
        "qt": "fainting, racing or irregular heartbeat",
        "potass": "muscle weakness, cramps, palpitations",
        "cyp": "sudden change in how strong the medication feels",
    },
    "vi": {
        "bleed": "bầm tím bất thường, đi ngoài đen, nước tiểu có máu, chảy máu cam lâu",
        "serotonin": "kích động, sốt, tim đập nhanh, run, toát mồ hôi",
        "sedat": "buồn ngủ cực độ, lú lẫn, thở chậm",
        "hypoglyc": "run tay, toát mồ hôi, đói cồn cào, lú lẫn (hạ đường huyết)",
        "qt": "ngất, tim đập nhanh hoặc loạn nhịp",
        "potass": "yếu cơ, chuột rút, hồi hộp",
        "cyp": "thuốc bỗng mạnh hoặc yếu bất thường",
    },
}


def _pick(text: str, pool: dict, lang: str):
    t = (text or "").lower()
    for key, val in pool.items():
        if key in t:
            if isinstance(val, dict):
                return (val.get(lang) or val.get("en")), key
            return val, key
    return None, None


def _narrative_interaction(i: dict, lang: str) -> str:
    a = ((i.get("a") or {}).get("label")) or "one item"
    b = ((i.get("b") or {}).get("label")) or "another"
    why = i.get("mechanism") or i.get("effect") or ""
    if lang == "vi":
        head = f"**{a} + {b}**"
        plain = _pick(why, _MECH_PLAIN, "vi")
        body = plain[0] if plain[0] else (why or "có ghi nhận tương tác")
        act = i.get("action") or ""
        return f"- {head}: {body}." + (f" Ghi chú của nguồn: {act}" if act else "")
    head = f"**{a} + {b}**"
    plain = _pick(why, _MECH_PLAIN, "en")
    body = plain[0] if plain[0] else (why or "documented interaction")
    act = i.get("action") or ""
    return f"- {head}: {body}." + (f" Source note: {act}" if act else "")


# --- Optional AI phrasing layer (Gemini) — OFF trừ khi có GEMINI_API_KEY ------
# Verdict/facts LUÔN từ engine; LLM chỉ diễn giải lại câu chữ, cấm thêm fact.
import os as _os


async def _gemini_polish(answer: str, question: str, lang: str) -> str | None:
    # DISABLED for App Store / local-first build: no Gemini, no PHI leak
    return None
    key = _os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    try:
        import httpx

        sys_prompt = (
            "You are a friendly pharmacist polishing an existing answer for a health-scanner app. "
            "STRICT RULES: keep EVERY fact, drug name, number, hour, severity and the disclaimer "
            "exactly as given; add NO new medical claims; do not answer the question beyond the "
            "provided answer; keep markdown bold/bullets; output language: "
            + ("Vietnamese" if lang == "vi" else "English")
            + "; warm, clear, <=190 words. Return only the rewritten answer."
        )
        async with httpx.AsyncClient(timeout=7.0) as client:
            res = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}",
                json={
                    "system_instruction": {"parts": [{"text": sys_prompt}]},
                    "contents": [{"role": "user", "parts": [{"text": f"User question: {question}\n\nAnswer to polish:\n{answer}"}]}],
                    "generationConfig": {"temperature": 0.4, "maxOutputTokens": 512},
                },
            )
        if res.status_code != 200:
            print("Gemini polish HTTP", res.status_code)
            return None
        cands = (res.json() or {}).get("candidates") or []
        parts = (((cands[0] or {}).get("content") or {}).get("parts")) or []
        text = "".join(pp.get("text", "") for pp in parts).strip()
        # an toàn: từ chối output mất disclaimer
        if not text or ("medical advice" not in text and "không phải lời khuyên y tế" not in text):
            return None
        return text
    except Exception as err:
        print("Gemini polish failed (non-fatal):", err)
        return None


async def ask_medmatch_advisor(question: str, product_context: dict | None, user_profile: dict) -> str:
    """Reference answer from structured data: verdict → what it means → what to do → evidence.
    Deterministic, language-aware (en/vi), constrained to engine findings."""
    lang = (user_profile or {}).get("language") or "en"
    if lang not in ("en", "vi"):
        lang = "en"
    q = (question or "").lower().strip()
    med_match = (product_context or {}).get("medMatch")
    worst, ranked = _worst(med_match)

    # Guard: need something to reason about
    recognized = [m for m in (med_match or {}).get("matched") or []]
    if not product_context or (not med_match and not (product_context.get("ingredientsList") or [])):
        return (
            {"en": "I can only reason from a scanned product — scan a label or barcode first, then ask me about it.",
             "vi": "Mình chỉ suy luận từ sản phẩm đã quét — hãy quét nhãn hoặc mã vạch trước rồi hỏi nhé."}[lang]
            + "\n\n" + DISCLAIMER[lang]
        )

    sev = worst["severity"] if worst else None
    unmatched = (med_match or {}).get("unmatched") or []
    verdict_key = sev or ("unknown" if not med_match or unmatched else "none")
    verdict = _VERDICT[lang].get(verdict_key) or _VERDICT[lang]["unknown"]
    lines: list[str] = [verdict, ""]

    # 1. What we recognized (transparency = trust)
    if recognized:
        names = ", ".join(str(m.get("label")) for m in recognized[:6])
        if lang == "vi":
            lines.append(f"Mình đã nhận dạng: {names}.")
        else:
            lines.append(f"Here's what I recognized: {names}.")
        unmatched = (med_match or {}).get("unmatched") or []
        if unmatched:
            if lang == "vi":
                lines.append(f"Chưa nhận dạng được: {', '.join(str(u) for u in unmatched[:4])} — nghĩa là phần này chưa được kiểm tra.")
            else:
                lines.append(f"Not recognized (so not checked): {', '.join(str(u) for u in unmatched[:4])}.")
    checked_sources = (med_match or {}).get("checkedSources") or []
    if checked_sources:
        lines.append(
            ("Nguồn đã kiểm tra: " if lang == "vi" else "Sources checked: ")
            + ", ".join(str(source) for source in checked_sources)
        )
    freshness = (med_match or {}).get("dataFreshness") or {}
    if freshness.get("generatedAt"):
        lines.append(
            ("Dữ liệu kiểm tra lúc: " if lang == "vi" else "Checked at: ")
            + str(freshness["generatedAt"])
        )

    # 2. Interactions in human terms (worst first, max 3)
    if ranked:
        if lang == "vi":
            lines.append("")
            lines.append("**Điều gì đang xảy ra:**")
        else:
            lines.append("")
            lines.append("**What's going on:**")
        for i in ranked[:3]:
            lines.append(_narrative_interaction(i, lang))

    # 3. Depletions / QT / Beers / schedule as "one more thing"
    extras: list[str] = []
    for d in (med_match or {}).get("depletions") or []:
        if lang == "vi":
            extras.append(f"{d.get('ingredient')} có thể bị cạn kiệt do thuốc — hỏi bác sĩ về việc bổ sung.")
        else:
            extras.append(f"{d.get('ingredient')} can get depleted by these drugs — ask about supplementing.")
    for b_ in (med_match or {}).get("beers") or []:
        if lang == "vi":
            extras.append(f"Tiêu chuẩn Beers 2023: {b_.get('label')} — {b_.get('note')}")
        else:
            extras.append(f"Beers Criteria (65+): {b_.get('label')} — {b_.get('note')}")
    for s_ in (med_match or {}).get("schedule") or []:
        if lang == "vi":
            extras.append(f"Lịch uống: {s_.get('a')} và {s_.get('b')} cách nhau ít nhất {s_.get('min_hours')} giờ.")
        else:
            extras.append(f"Timing: take {s_.get('a')} and {s_.get('b')} at least {s_.get('min_hours')} hours apart.")
    if extras:
        lines.append("")
        lines.append(("**Một điều nữa:**" if lang == "vi" else "**One more thing:**"))
        lines.extend(f"- {e}" for e in extras[:3])

    # 4. Red flags (only when there's a real risk)
    red_text = ""
    if ranked and worst and SEVERITY_RANK.get(sev, 9) <= 2:
        reasons = " ".join(str(i.get("mechanism") or "") + str(i.get("effect") or "") for i in ranked[:3])
        red, key = _pick(reasons, _RED_FLAGS[lang], lang)
        if not red:
            red = _RED_FLAGS[lang]["bleed"] if key is None else red
        red_text = red
        lines.append("")
        if lang == "vi":
            lines.append(f"**Dấu hiệu cần đi khám ngay:** {red}.")
        else:
            lines.append(f"**Seek care promptly if you notice:** {red}.")

    # 5. What to do
    acts = _ACTIONS[lang].get(verdict_key) or _ACTIONS[lang]["unknown"]
    lines.append("")
    lines.append("**Nếu là mình**" if lang == "vi" else "**What I'd do:**")
    lines.extend(f"{idx}. {a}" for idx, a in enumerate(acts[:3], 1))

    # 6. Evidence line
    if ranked and worst:
        if lang == "vi":
            lines.append("")
            lines.append(f"Mức tin cậy: { {'contraindicated': 'rất cao (nguồn chính phủ)', 'major': 'cao', 'moderate': 'trung bình', 'minor': 'thấp'}.get(sev, 'thấp') } — dựa trên dữ liệu công khai (FDA nhãn, SUPP.AI DOI, FAERS).")
        else:
            lines.append("")
            lines.append(f"Confidence: { {'contraindicated': 'very high (government sources)', 'major': 'high', 'moderate': 'moderate', 'minor': 'low'}.get(sev, 'low') } — based on public data (FDA labels, SUPP.AI DOIs, FAERS).")

    lines.append("")
    lines.append(DISCLAIMER[lang])
    deterministic = "\n\n".join(lines)
    polished = await _gemini_polish(deterministic, question, lang)
    return polished or deterministic

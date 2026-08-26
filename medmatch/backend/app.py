"""MedMatch AI — backend API.

Product safety companion for the US/EU market: scans supplement/drug
names and checks documented interactions, then explains risks in plain
language. Informational only; never prescribes.
"""
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .db import get_conn
from .engine import get_engine

STATIC_DIR = Path(__file__).parent.parent / "static"

app = FastAPI(title="MedMatch AI", version="0.1.0")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class AnalyzeItem(BaseModel):
    name: str | None = None
    label: str | None = None
    kind: str | None = None
    matched: dict | None = None
    time: str | None = None


class AnalyzeRequest(BaseModel):
    items: list[AnalyzeItem]
    profile: dict | None = None


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/stats")
async def stats():
    return get_engine().stats()


@app.get("/api/search")
async def search(q: str = "", limit: int = 12):
    results = get_engine().match(q, max_results=limit)
    enriched = []
    for r in results:
        if r["kind"] == "herb":
            detail = get_engine().herb_detail(r["id"])
            r["scientific"] = detail.get("scientific") if detail else None
            r["warns_against"] = [i["class_name"] for i in (detail.get("interactions") or [])][:5]
        elif r["kind"] == "food":
            pass  # plain food item, no enrichment
        else:
            detail = get_engine().class_detail(r["id"])
            r["examples"] = (detail.get("drugs") or [])[:5] if detail else []
        enriched.append(r)
    return {"query": q, "results": enriched}


@app.get("/api/herb/{herb_id}")
async def herb_detail(herb_id: str):
    detail = get_engine().herb_detail(herb_id)
    if not detail:
        raise HTTPException(404, "Herb not found")
    return detail


@app.get("/api/class/{class_id}")
async def class_detail(class_id: str):
    detail = get_engine().class_detail(class_id)
    if not detail:
        raise HTTPException(404, "Drug class not found")
    return detail

@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    payload = []
    for i in req.items:
        item = i.model_dump()
        item["name"] = item.get("name") or item.get("label") or ""
        payload.append(item)
    return get_engine().analyze(payload, profile=req.profile)


# --- barcode lookup via Open Food Facts (free, no key) ---
def _fetch_off(barcode: str) -> dict | None:
    url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
    req = urllib.request.Request(url, headers={"User-Agent": "MedMatchAI/0.1 (health reference tool)"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _fetch_upcitemdb(barcode: str) -> dict | None:
    """Fallback barcode lookup via UPCitemdb (100/day free, needs key)."""
    key = os.environ.get("UPCITEMDB_KEY")
    if not key:
        return None
    url = "https://api.upcitemdb.com/prod/trial/lookup"
    req = urllib.request.Request(url, data=json.dumps({"upc": barcode}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        items = data.get("items") or []
        if not items:
            return None
        it = items[0]
        return {"name": it.get("title") or it.get("description"),
                "brand": it.get("brand"), "ingredients": []}
    except Exception:
        return None


@app.get("/api/lookup/{barcode}")
async def lookup(barcode: str):
    if not barcode.isdigit() or len(barcode) < 6:
        raise HTTPException(400, "Invalid barcode")
    data = _fetch_off(barcode)
    if not data or data.get("status") != 1:
        fallback = _fetch_upcitemdb(barcode)
        if not fallback:
            raise HTTPException(404, "Product not found (Open Food Facts + UPCitemdb)")
        return {"barcode": barcode, "name": fallback["name"], "brands": fallback["brand"],
                "ingredients": [], "matched_ingredients": [], "source": "UPCitemdb"}
    p = data["product"]
    ingredients = []
    for key in ("ingredients_text", "ingredients_text_en"):
        text = p.get(key)
        if text:
            ingredients = [s.strip() for s in text.split(",") if s.strip()]
            break
    if not ingredients and isinstance(p.get("ingredients"), list):
        ingredients = [i.get("text", "") for i in p["ingredients"] if i.get("text")]

    # pre-match ingredients against our herb index
    engine = get_engine()
    matched_ingredients = []
    seen_ids = set()
    for ing in ingredients[:40]:
        m = engine.match(ing, max_results=1)
        if m and m[0]["kind"] == "herb" and m[0]["score"] >= 0.85 and m[0]["id"] not in seen_ids:
            seen_ids.add(m[0]["id"])
            d = engine.herb_detail(m[0]["id"])
            matched_ingredients.append({
                "input": ing,
                "herb_id": m[0]["id"],
                "label": m[0]["label"],
                "warns_against": [i["class_name"] for i in (d.get("interactions") or [])][:6],
            })
    return {
        "barcode": barcode,
        "name": p.get("product_name") or p.get("product_name_en") or p.get("generic_name") or "Unknown product",
        "brands": p.get("brands"),
        "quantity": p.get("quantity"),
        "categories": p.get("categories"),
        "ingredients": ingredients[:40],
        "matched_ingredients": matched_ingredients,
        "source": "Open Food Facts",
    }


@app.get("/api/review/next")
async def review_next():
    from .db import get_conn
    from . import quality_gate
    return quality_gate.next_pending(get_conn()) or {}


@app.post("/api/review/{queue_id}")
async def review_do(queue_id: int, status: str = "verified", note: str = ""):
    from .db import get_conn
    from . import quality_gate
    if not quality_gate.review(get_conn(), queue_id, status, note):
        raise HTTPException(404, "Not found or already reviewed")
    return {"status": "ok"}

# iDISK product search: name -> product -> ingredients (herb-resolved)
@app.get("/api/products")
async def products(q: str = "", limit: int = 10):
    if not q.strip():
        return {"query": q, "results": []}
    from .db import get_conn
    from . import idisk_products
    conn = get_conn()
    results = []
    for p in idisk_products.search_products(conn, q.strip(), limit=min(limit, 20)):
        ingredients = idisk_products.product_ingredients(conn, p["dsp_id"])
        results.append({**p, "ingredients": ingredients[:12]})
    return {"query": q, "results": results}



@app.get("/api/unified/stats")
async def unified_stats():
    from .db import get_conn
    conn = get_conn()
    return {
        "pairs": conn.execute("SELECT COUNT(*) FROM interaction_unified").fetchone()[0],
        "inferred": conn.execute("SELECT COUNT(*) FROM interaction_unified WHERE is_inferred=1").fetchone()[0],
        "standards": conn.execute("SELECT COUNT(*) FROM standard_ingredient").fetchone()[0],
        "synonyms": conn.execute("SELECT COUNT(*) FROM ingredient_synonyms").fetchone()[0],
        "multi_source_pairs": conn.execute(
            "SELECT COUNT(*) FROM interaction_unified WHERE json_array_length(evidence) >= 2"
        ).fetchone()[0],
    }


@app.get("/api/unified/pair")
async def unified_pair(a_kind: str, a_id: str, b_kind: str, b_id: str):
    import json as _json
    from .db import get_conn
    conn = get_conn()
    key = "|".join(sorted([f"{a_kind}:{a_id}", f"{b_kind}:{b_id}"]))
    row = conn.execute(
        "SELECT * FROM interaction_unified WHERE pair_key = ?", (key,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Pair not found in unified layer")
    d = dict(row)
    d["evidence"] = _json.loads(d["evidence"] or "[]")
    return d


@app.get("/api/ai_reviews/stats")
async def ai_reviews_stats():
    from .db import get_conn
    conn = get_conn()
    rows = conn.execute("SELECT verdict, COUNT(*) n FROM ai_reviews GROUP BY verdict").fetchall()
    total = conn.execute("SELECT COUNT(*) FROM ai_reviews").fetchone()[0]
    return {
        "total": total,
        "by_verdict": {r["verdict"]: r["n"] for r in rows},
        "accuracy": round(100 * sum(r["n"] for r in rows if r["verdict"] == "correct") / total, 1) if total else 0,
    }


@app.get("/api/ai_reviews/flagged")
async def ai_reviews_flagged(limit: int = 20):
    """Pairs the AI flagged as incorrect, with reasoning."""
    from .db import get_conn
    conn = get_conn()
    names = {}
    for kind, table in (("herb", "herbs"), ("drug_class", "drug_classes"), ("food", "foods")):
        names.update({(kind, r["id"]): r["name_en"] for r in conn.execute(f"SELECT id, name_en FROM {table}")})
    out = []
    for r in conn.execute(
        "SELECT ur.*, ar.verdict, ar.reasoning FROM ai_reviews ar"
        " JOIN interaction_unified ur ON ur.pair_key = ar.pair_key"
        " WHERE ar.verdict = 'incorrect' LIMIT ?", (min(limit, 100),)
    ):
        d = dict(r)
        d["a_label"] = names.get((d["a_kind"], d["a_id"]), d["a_id"])
        d["b_label"] = names.get((d["b_kind"], d["b_id"]), d["b_id"])
        d["evidence"] = None  # keep payload light
        out.append(d)
    return {"flagged": out}


@app.get("/api/class/{class_id}/effects")
async def class_effects(class_id: str, limit: int = 15):
    """Top OnSIDES side effects for a drug class."""
    from .db import get_conn
    conn = get_conn()
    rows = conn.execute(
        "SELECT effect, SUM(n) n FROM onsides_effects WHERE cls_a = ?"
        " GROUP BY effect ORDER BY n DESC LIMIT ?", (class_id, min(limit, 30))
    ).fetchall()
    if not rows:
        raise HTTPException(404, "No side effect data for this class")
    return {"class_id": class_id,
            "effects": [{"effect": r["effect"], "reports": r["n"]} for r in rows],
            "source": "OnSIDES (CC BY 4.0, PubMedBERT from FDA/EMA/EMC/KEGG labels)"}


@app.get("/favicon.ico")
async def favicon():
    return FileResponse(STATIC_DIR / "favicon.svg")

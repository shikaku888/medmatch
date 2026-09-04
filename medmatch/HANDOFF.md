# HANDOFF — Trạng thái hiện tại & việc cần làm tiếp

> Cập nhật: 2026-09-04. Đọc file này trước khi làm bất cứ việc gì.
> Nhật ký chi tiết: `medmatch/WORKLOG.md`. Kế hoạch tổng: `medmatch/NEXT_WORK_PLAN.md`.

## Quyết định đã chốt (không làm lại)

1. **Bỏ Consensus API** — user quyết định. Không tích hợp, không crawl Consensus (ToS cấm bulk crawl; Pro account không cấp quyền bulk). Nếu cần bulk research sau này: PubMed E-utilities / Europe PMC / OpenAlex.
2. **Không crawl PMDA/JADER/JAPIC** — điều khoản PMDA cấm tự động tải và redistribution ngoài mục đích y tế của chính đơn vị. PMDA/JADER vẫn giữ trạng thái `pmda_pending` / `jader` (restricted) trong `backend/license_registry.py`.
3. **Kiến trúc hai tầng** (đã chốt với user):
   - SQLite clinical runtime (interaction, labels, LactMed, recalls, CAERS, product index) — read-only, giữ gọn.
   - Product resolver on-demand (OFF/USDA/openFDA/DSLD live + cache) cho coverage "không giới hạn" mà không phình DB.
   - Không bulk-import OFF/USDA vào SQLite (runtime đã 5.2 GB, fly.toml volume chỉ 5 GB).
4. **VPS thay Fly được** — user sẽ cấp VPS sau; deploy = Docker image + bind mount runtime snapshot + Caddy/Traefik HTTPS. Cần tối thiểu: disk ≥ 20 GB, RAM ≥ 4 GB, 2 vCPU.

## Trạng thái đã hoàn thành (verified)

- Runtime snapshot cuối: `deploy/runtime/medmatch.db` — 69 tables, 10,790,201 rows, `integrity=ok`,
  SHA-256 `0895d10ff3fe0305ae1789713c32488e506ae637df391e6528cd61140d73703a`.
- Nguồn đã import (canonical `backend/medmatch.cleaned.db` + runtime):
  - DrugCentral: 4,995 structures / 23,236 synonyms / 5,372 ATC / 5,148 struct-ATC / 20,978 target facts (`backend/drugcentral.py`)
  - LactMed: 1,957 NXML records (`backend/lactmed.py`)
  - FDA Recalls: 47,216 (17,899 drug + 29,317 food) (`backend/recalls.py`)
  - CAERS: 151,589 reports → 428,229 aggregates (`backend/caers.py`)
  - FDA label enrichment: 250,356 indications, 164,369 inactive-ingredient sections, 50,750 NDC excipient joins (`backend/enrich_labels.py`)
  - Product index: 507,426 rows; 101,500 NDC/EAN có excipient text (`backend/product_index.py`, insert theo tên cột — đừng sửa lại thành positional!)
- API mới: `/api/drug/{id}/clinical-summary`, `/indications`, `/atc`, `/mechanism`, `/lactation`, `/recalls`, `/caers-events`.
  Scan (`/api/scan`, `/api/scan/image`, `/api/scan/text`) có `safetyEvidence` + `excipients`.
- Frontend: `MedMatchResults` panel "Clinical reference layers" (ATC/MOA/indication/LactMed/recall/CAERS),
  `ScanResultCard` panel "Product safety signals". Class-level summary bị chặn không hiển thị product-specific claims (scope guard).
- Tests: `102 passed, 10 skipped`. Frontend tsc + vite build PASS. Browser smoke PASS (393px).
- Nhật: MeSpEn synonym pack trong runtime — 4,435 ja synonyms, ~849 drug classes, ~305 herbs; OCR ja baseline recall 35.4% (benchmark trong `backend/data/japanese_ocr_benchmark/`).

## Việc cần làm tiếp (theo thứ tự ưu tiên)

### P0 — Product resolver thống nhất (coverage "quét được nhiều nhất")
- Tạo `backend/scanner/resolver.py` (hoặc mở rộng router): một đường lookup duy nhất
  barcode/name/ingredients → local index → cache → OFF → USDA → openFDA NDC → DSLD → LNHPD (Canada, on-demand qua
  `health-products.canada.ca/api/natural-licences/ProductLicence/?id=<NPN>`) → unresolved queue.
- Response contract: `{status: found|partial|unknown, product, ingredients, unmatched, sources, limitations}`.
  Không biến `unknown` thành `safe`.
- Cache kết quả provider vào bảng product-cache riêng (key, normalized fields, source, fetched_at, ttl, sha256).
  Không lưu raw provider JSON vào clinical DB.
- Thêm LNHPD license entry vào `license_registry.py` (`canada_open` đã có, dùng source_code đó).

### P0 — Dữ liệu Nhật: mở rộng hợp pháp (ưu tiên user)
- MeSpEn đã tải đầy đủ: `backend/data/mespen_glossaries.zip` (17,932 cặp ja; bản pack hiện chỉ lọc exact-match
  → 2,194 items). Đã xác nhận còn **~2,083 cặp ja khớp exact-match nữa không nằm trong pack** do thứ tự lọc —
  rà lại `import_medical_vocabulary.py` (hàm `_norm` vs engine `normalize`) và rebuild pack để bắt hết
  (file staging tạm: `backend/data/mespen_ja_full.json`).
- Thêm nguồn synonym Nhật CC BY/open khác nếu tìm được (không crawl PMDA).
- Bổ sung **Japanese allergen/label detection** trong `backend/scanner/personalization.py`: hiện danh sách
  allergen/diet là tiếng Anh; nhãn Nhật ghi `卵, 乳, 小麦, そば, 落花生, えび, かに, アレルギー表示` — chưa được detect.
  Đây là gap thực tế khi user hỏi "thành phần bao bì thực phẩm Nhật có check được không": OCR + tách ingredient OK,
  nhưng cảnh báo allergen/diet tiếng Nhật CHƯA có.
- Bổ sung Japanese additive terms (着色料/保存料/酸化防止剤…) vào parsing noise/additive lists nếu phù hợp.


### P0 — Mở rộng dữ liệu US khi có VPS (disk 40–50 GB)
VPS giải phóng ràng buộc dung lượng. Thứ tự import đề xuất (đã kiểm tra license + dung lượng):
1. **USDA FoodData Central (branded)** — Public Domain, ~1.4M sản phẩm có barcode/UPC. CSV full ~5–8 GB;
   import cột (gtin_upc, description, brand_owner, ingredients, branded_food_category) → product_index.
   Đây là gap lớn nhất cho food scanning hiện nay.
2. **Open Food Facts US subset** — CC BY-SA, lọc country=us, chỉ lấy cột code/product_name/brands/ingredients_text/
   labels_tags/allergens_tags. Có thể tải dump "openfoodfacts-products.csv" và lọc lúc import (không giữ raw).
3. **Giữ nguyên raw FDA archives** (`backend/data/openfda/*.zip`, FAERS quarters, OnSIDES zip) trên VPS để
   re-aggregate khi cần — hiện đã đủ, chỉ cần chuyển lên server.
4. RxNorm full + DrugCentral raw đã nằm trong `backend/medmatch.cleaned.db` (~11 GB) — copy nguyên file lên VPS,
   không cần tải lại.
Budget disk VPS 40–50 GB: source DB ~11 GB + FDA/OnSIDES archives ~5 GB + FDC/OFF import ~10 GB + runtime
snapshot ~6 GB + backup/rollback ~6 GB → vẫn còn headroom.
Lưu ý: mọi bulk import đi qua importer riêng có register_release; không import thẳng vào runtime snapshot.
### P1 — Deploy VPS (khi user cấp)
- Viết `docker-compose.yml` + Caddyfile (HTTPS tự động) thay `fly.toml`; hướng dẫn mount `/data` với
  `deploy/runtime/medmatch.db` + manifest + evaluation file.
- `start-medmatch.bat` giữ cho local; VPS dùng `MEDMATCH_DB=/data/medmatch.db`.
- Volume sizing: ≥ 20 GB disk, 4 GB RAM, 2 vCPU.

### P1 — Runtime snapshot đang 5.2 GB
- Cân nhắc exclude thêm bảng lớn khỏi runtime build (`faers_adverse_events` 8M rows có thể pre-aggregate;
  `caers_product_events` 428k có thể giữ) — chỉ làm nếu không phá API. Đo trước khi cắt.

### P2 — Đã biết và chấp nhận
- NDC directory không có UPC/inactive ingredients → excipient chỉ từ FDA labels (đã có 50,750).
- OCR ja recall 35% — chưa cải thiện crop fallback (đã benchmark, khuyến nghị không bật).
- 131 CYP findings pending pharmacist review (không tự verify).

## Lệnh chạy & kiểm chứng nhanh

```bash
# API local (runtime snapshot):
set MEDMATCH_DB=deploy\runtime\medmatch.db && python -m uvicorn backend.app:app --port 8765
python -m pytest tests/ -q --basetemp=.pytest-basetemp
# Frontend:
cd ../personalized-product-scanner && bun x tsc --noEmit && bun run build
# Publish bundle:
set SCANNER_BASE=/scanner/&& set SCANNER_OUT=dist-medmatch&& bun run build
# rồi copy dist-medmatch -> ../medmatch/static/scanner
# Rebuild runtime (đóng mọi process đang giữ file trước!):
python deploy/build_runtime_db.py --source backend/medmatch.cleaned.db --output deploy/runtime/medmatch.db --force
```

### P1 — Bảo mật VPS (dữ liệu user là PHI)
Tách 2 loại dữ liệu:
- Clinical/public (FDA, USDA, DrugCentral, product index): public data, mất chỉ tốn re-import.
  Không cần encrypt; cần backup định kỳ (restic/borg encrypted → local hoặc B2).
- User data (`/data/devices/`): profile, medications, allergies, scan history = PHI. Ưu tiên chuyển sang
  Postgres managed có encryption (Supabase/Neon) thay vì SQLite trên VPS; nếu giữ SQLite thì ít nhất
  LUKS full-disk + backup encrypted.
Hardening bắt buộc: SSH key-only + cấm root + fail2ban; ufw chỉ 80/443/22; HTTPS bắt buộc (Caddy);
secrets trong `.env` chmod 600, không bake vào image; `dev_cert.pem`/`dev_key.pem` trong backend/data
không được deploy lên VPS.

## Cạm bẫy đã gặp (đừng lặp lại)

- `build_runtime_db.py` fail `WinError 5` nếu có server/browser đang mở runtime DB → stop process trước.
- `product_index` insert phải theo tên cột (đã có 1 lần ghi lệch cột excipients/matched).
- LSP/pytest trên DB 11 GB: chỉ dùng `MEDMATCH_DB` env trỏ đúng file; mặc định `backend/medmatch.db` là seed nhỏ.
- Background jobs có thể tự clamp timeout 3600s — job dài cần chia nhỏ.

## Cập nhật phiên 2026-09-04

- `DONE (local)` — Unified resolver tại `backend/scanner/resolver.py`: barcode/name/ingredient → local index → normalized cache riêng `product-cache.db` → Open Food Facts → USDA/openFDA → DSLD → Health Canada LNHPD (`canada_open`); contract giữ `found|partial|unknown`, không biến unknown thành safe.
- `DONE (local)` — `/api/product/resolve`, scanner barcode và name fallback dùng cùng resolver; openFDA NDC được phân loại `drug`.
- `DONE (local)` — MeSpEn importer dùng cùng normalization với engine, nhận local zip/staged JSON; pack rebuilt `4,478` records (`2,196` ja, `2,282` zh).
- `DONE (local)` — Japanese allergen/additive detection và negative-claim handling đã thêm vào parser/personalization.

- `DONE (local)` — Resolver unknowns are now recorded in privacy-safe `unresolved_products` with hashed lookup keys and retry counts.
- `DONE (local)` — Admin endpoint `GET /api/product/unresolved` requires `PRODUCT_RESOLVER_ADMIN_TOKEN` or `ADMIN_API_TOKEN`.
- `DONE (local)` — Latest backend verification: `108 passed, 10 skipped`; queue focused `6 passed`; admin endpoint smoke `200`.
- `DONE (local)` — Verification: focused `28 passed`; full backend `107 passed, 10 skipped`; API smoke ingredient-only `200 partial`.
- `DONE (local)` — Runtime footprint measured at `5,236,011,008` bytes; FAERS aggregate was already grouped by drug/PT/quarter, so runtime pruning keeps only keys reachable through `drug_classes`/`drug_name_mapping`. `3,986,972` unreachable FAERS rows removed.
- `DONE (local)` — Runtime republished at `4,474,957,824` bytes (`3,990,034` FAERS rows), integrity `ok`, manifest SHA-256 `57b2da9e84c941602b0c9d69cbe99914748a6bf96379ea3322c836a8838f4891`; builder now enforces a 5,000,000,000-byte budget.
- `DONE (local)` — Added root `docker-compose.yml` with API/Caddy, read-only runtime snapshot mounts, separate `/data/devices` PHI volume, `/data/state` rate-limit volume, health-gated proxy, and automatic HTTPS via `deploy/Caddyfile`.
- `DONE (local)` — Added deployment config smoke tests; runtime/deployment slice `31 passed`; full backend regression `113 passed, 10 skipped`. `docker compose config` passed with a temporary sample `.env`; no `.env` or token remains in the repository.
- `DECISION` — VPS 60 GB dùng serving-only: crawl/import trên máy ingest hoặc CI có disk lớn, build và kiểm tra snapshot/image bên ngoài, upload artifact đã kiểm tra lên VPS, không giữ raw staging trên VPS.
- `DONE (local)` — USDA Branded Foods April 2026 đã crawl vào PC: archive `448,767,220` bytes, SHA-256 `26050a5d03197469813754743a21ee0fad4ccf22b6aac2a995846a987719fc49`; thêm `464,497` food barcode rows vào `backend/medmatch.cleaned.db`.
- `DONE (local)` — Runtime rebuild sau USDA: `971,923` product rows, `464,497` food rows, `4,691,533,824` bytes, SHA-256 `a935942795059aebacaa732e7291630bfa5429599fa8ac2b634f1558b815c319`; sample barcode WESSON lookup pass.
- `DONE (local)` — Added multilingual product identity graph in `backend/scanner/product_graph.py`: product family, market SKU, consented observation, formulation fingerprint, and reviewable cross-market links are separated from clinical DB and device profiles.
- `DONE (local)` — Added `POST /api/product/contributions` with explicit `shareProductFacts=true`; pending observations require admin approval before reuse. Approved records resolve for later users as `community_verified`, without storing raw images or user profile data.
- `DONE (local)` — Added admin review/candidate routes and regression coverage; exact brand + ingredient fingerprint creates a candidate only, never an automatic safety merge. Full backend regression: `117 passed, 10 skipped`.

# MedMatch — nhật ký tiến trình

File này là sổ giao việc liên tục cho các lần làm việc sau.

## Quy ước bắt buộc

- Mỗi việc là một mục có trạng thái `TODO`, `DOING`, `DONE` hoặc `BLOCKED`.
- Trước khi sửa: ghi mục tiêu và file/symbol liên quan.
- Ngay sau khi hoàn thành một việc: cập nhật mục đó, ghi file đã sửa và lệnh kiểm tra.
- Không đánh dấu `DONE` nếu chưa có bằng chứng từ test, smoke hoặc runtime.
- Việc `BLOCKED` phải ghi rõ blocker bên ngoài; lần sau tiếp tục từ mục `TODO` ưu tiên cao nhất.
- Nhật ký này bổ sung cho `PROGRESS.md`; trạng thái code và kết quả kiểm tra là nguồn sự thật.

## Baseline — 2026-09-03

- Frontend `bun x tsc --noEmit`: PASS.
- Frontend `bun run build`: PASS; 1,935 modules transformed.
- Backend ban đầu: 82 passed, 12 failed, 9 skipped.
- Lỗi ban đầu gồm thiếu bảng `qt_drugs`, `beers_drugs`, `ingredient_synonyms`, `interaction_unified`; batch barcode và vocabulary Nhật/Trung cũng fail.
- `deploy/runtime/medmatch.db` có snapshot đầy đủ; `backend/medmatch.db` local chỉ có seed schema cơ bản.

## Thứ tự ưu tiên hiện tại

1. `DONE` — Đồng bộ source DB đầy đủ, unify/provenance và runtime snapshot; SSRI × NSAID đã có canonical evidence regulatory.
2. `DONE` — Thêm 4 nhóm interaction: SSRI–NSAID, levothyroxine–calcium, lisinopril–potassium, metformin–alcohol.
3. `DONE` — Sửa batch barcode và multilingual vocabulary trên seed-only DB.
4. `DONE` — Chạy focused và full backend regression.
5. `BLOCKED` — Còn blocker external: CYP pharmacist review, iOS signing/domain, Docker/Fly deploy.

## Nhật ký thay đổi

### 2026-09-03

- `DONE` — Tạo quy ước nhật ký liên tục trong file này.
- `DONE` — Ghi baseline frontend/backend và phát hiện DB source thiếu bảng runtime.
- `DONE` — `backend/engine.py` thêm guard cho optional tables; seed-only DB không còn crash khi thiếu QT/Beers/electrolyte tables.
- `DONE` — `backend/db.py` bootstrap `ingredient_synonyms` cho seed DB; sửa `build_db()` dùng `sqlite3.Row` cho synonym builder.
- `DONE` — Thêm fallback Beers `amiodarone` và electrolyte `furosemide` khi Sahayak tables không có.
- `DONE` — Thêm fallback canonical → seed cho herb/class/food interaction khi canonical layer rỗng; canonical findings có sẵn vẫn được ưu tiên.
- `DONE` — Thêm FDA rule `SSRI × NSAID`; thêm alias `calcium` và `potassium` vào food seed; thêm test 4 priority cases.
- `DONE` — Cập nhật `start-medmatch.bat` dùng `deploy/runtime/medmatch.db`; fail rõ ràng nếu canonical snapshot chưa được build.
- `DONE` — Focused priority regression: 7 passed.
- `DONE` — Full backend regression: 94 passed, 10 skipped.
- `DONE` — `backend/product_index.py` nay resolve ingredients của DSLD và copy mapping sang UPC/EAN variant thay vì ghi `matched=[]`.
- `DONE` — Thêm regression test DSLD barcode index; 3 focused tests pass.
- `BLOCKED` — Runtime snapshot hiện có 131 CYP rows `pending` ở trust 0.5; cần pharmacist review, không tự verify.
- `DONE` — Rebuild runtime product index an toàn qua SQLite backup/promote: DSLD 43,295/45,521 mapped; UPC 96,916/99,864; EAN 89,282/92,042; NDC 231,577/269,999. Manifest/checksum và `PRAGMA integrity_check` đều PASS.
- `DONE` — Xác nhận `backend/medmatch.cleaned.db` là full source DB (8,911,081,472 bytes, integrity `ok`), rebuild thành source canonical 9,306,173,440 bytes; giữ bản rollback `backend/medmatch.cleaned.db.previous`.
- `BLOCKED` — iOS project chưa nằm trong source; workflow `.github/workflows/ios-release.yml` tạo `ios/` trên macOS bằng `npx cap add ios`, rồi build/upload TestFlight. Apple Vision native OCR chưa có; hiện OCR là Tesseract.js/RapidOCR web/backend.
- `BLOCKED` — `capacitor.config.json` còn URL placeholder. Đã sửa `scripts/check-release-readiness.mjs` để reject placeholder; local check fail đúng với blocker, check với `SCANNER_URL=https://example.com/scanner/` pass.
- `BLOCKED` — Docker CLI có nhưng Docker daemon không chạy (`dockerDesktopLinuxEngine` pipe missing); Fly CLI không cài (`command not found`). Chưa thể xác minh deploy live từ workstation.
- `DONE` — Final backend regression after DSLD index test: 95 passed, 10 skipped.
- `DONE` — Chạy `build_synonyms`, `build_drug_name_mapping`, `build_standards`, `build_unified`, `product_index`: 40,775 synonyms; mapping 3,237 mapped/534 unmapped; 3,927 standards; 61,123 unified pairs, 384 conflicts; 507,426 product rows.
- `DONE` — Sửa `evidence_backfill.py` để refresh canonical finding bằng UPSERT, thay selected lineage khi unified row thay đổi, và phân loại nguồn FDA là `regulatory`.
- `DONE` — Provenance refresh: 61,123 findings, 63,345 evidence, 63,345 links; SSRI × NSAID = `major`, `regulatory`, confidence 1.0, `inferred=0`, source `fda_curated`.
- `DONE` — Runtime republish với R5 evaluation: 10/10 passed; snapshot integrity `ok`; manifest SHA-256 `4a27d1de683a1450d4a3f4c9c5d78f884c438c24f9da6897661dc025728e9e62`.
- `DONE` — Full regression sau thay đổi provenance: 96 passed, 10 skipped; focused evidence schema: 4 passed.
- `DONE` — Bổ sung Japanese cho onboarding và schedule timing (`OnboardingFlow.tsx`, `ScheduleTimeline.tsx`); frontend typecheck PASS, production build PASS, browser smoke xác nhận chọn `日本語` và hiển thị copy onboarding.
- `DONE (local)` — Implement reminder API/storage, profile-scoped CRUD, export/delete inclusion, browser permission UI, page fallback and service-worker/Periodic Background Sync channel; local lifecycle smoke PASS. Real device/background-delivery validation remains pending.
- `DONE (local)` — Added optional profile-scoped pharmacogenomics context (genotype/phenotype/indication), family-profile persistence, normalized patient-context exposure, and UI evidence review via `/api/pharmacogenomics/check`; no automatic dosing.
- `DONE (local)` — Added explicit health-context scenario coverage for pregnancy, lactation, renal, hepatic, and pediatric age boundaries; focused validation: 35 passed.
- `DONE (local)` — Generated and synced Capacitor iOS project (`bunx cap add ios`, `bunx cap sync ios`); `cap doctor` confirms Xcode is absent on Windows, so native build/sign/device validation remains blocked.
- `DONE (local)` — Browser smoke reaches the Camera HUD live viewfinder and renders the fallback scanner frame; physical camera/PWA install validation remains blocked without HTTPS and a real device.
- `DONE (local)` — Commercial license registry gates remain enforced; non-commercial/review-pending sources are not promoted into a commercial release.
- `DONE` — Final validation: backend full regression `100 passed, 10 skipped`; frontend typecheck PASS; production/static and Capacitor bundles build with 1,936 modules; iOS sync PASS.
- `DONE` — Sửa tiếp onboarding copy: warning example không còn rơi về tiếng Anh khi chọn non-VI; cả 7 ngôn ngữ dùng chuỗi bản địa hóa riêng.

## Gap audit sau smoke — 2026-09-03

- `P0 release blocker` — chưa có domain HTTPS thật trong `capacitor.config.json`; release check chỉ pass với URL override, không đủ để ship TestFlight/PWA production.
- `P0 deploy blocker` — chưa có live deployment smoke; Docker daemon và Fly CLI chưa khả dụng trên workstation.
- `DONE (local)` — Reminder/notification gap đã có implementation local; chưa claim production delivery cho mọi browser/device.
- `P1 evidence gap` — 131 CYP findings vẫn `pending` trust 0.5, cần pharmacist review trước khi promote.
- `P1 data gap` — Mendeley drug-food raw constituent evidence now has `/api/drug/{id}/food-evidence`; lactation remains an outbound LactMed pointer.
- `DONE (local)` — Pharmacogenomics profile/check flow is wired; health-context scenarios now validate pregnancy/lactation/renal/hepatic/pediatric boundaries.
- `P2 legal/device gap` — iOS project generated/synced but Xcode/macOS is unavailable; Camera HUD browser smoke passes, while physical camera/PWA validation needs HTTPS/device; commercial gates need legal approval for restricted sources.
- `Next` — kiểm thử reminder và PGx trên thiết bị thật; cần nguồn LactMed được phép dùng và pharmacist review CYP trước khi quay lại deploy/domain.

### 2026-09-03 — Supplemental evidence expansion

- `DONE (local)` — Added official openFDA CAERS bulk importer (`backend/caers.py`): 151,589 reports → 428,229 product/reaction aggregates; reports remain observational and product↔reaction attribution is not inferred.
- `DONE (local)` — Added official openFDA drug+food enforcement importer (`backend/recalls.py`): 47,216 records (17,899 drug + 29,317 food), source-aware stable keys preserve repeated event IDs.
- `DONE (local)` — Added NLM LactMed NXML importer (`backend/lactmed.py`): 1,957 records from official FTP; local lactation endpoint now returns summary, levels, infant effects, lactation effects and alternatives.
- `DONE (local)` — Added DrugCentral selected-table importer (`backend/drugcentral.py`): 4,995 structures, 23,236 synonyms, 5,372 ATC rows, 5,148 structure-ATC mappings, 20,978 target/MOA facts; no indication relation was fabricated because the 2023 dump has no indication COPY table.
- `DONE (local)` — FDA bulk label enrichment (`backend/enrich_labels.py`) filled `250,356` indication sections, `164,369` inactive-ingredient label sections, and joined `50,750` NDC products to authoritative inactive-ingredient text.
- `DONE (local)` — Product index rebuilt column-order safely: `507,426` rows, `101,500` NDC/EAN rows with excipient text; matched entity JSON remains in `matched`, not the excipient column.
- `DONE (local)` — `/api/drug/{id}/indications` now returns verbatim FDA label excerpts when available; ATC/target data is never used to infer indications.
- `DONE (local)` — Added `/api/drug/{id}/clinical-summary`; class-level summaries explicitly suppress product-specific indication/lactation/recall/CAERS claims and label examples as class-level.
- `DONE (local)` — `/api/scan`, `/api/scan/image`, and `/api/scan/text` now attach product-level `safetyEvidence`; UI renders FDA recall and CAERS signals with verification and causality warnings.
- `DONE (local)` — MedMatchResults now renders ATC, targets/MOA, FDA indications, LactMed, recalls and CAERS through the unified summary; class-level scope guard verified visually at 393px.
- `DONE (local)` — Runtime republished after label/product-index enrichment: `integrity=ok`, 69 tables, 10,790,201 rows, SHA-256 `0895d10ff3fe0305ae1789713c32488e506ae637df391e6528cd61140d73703a`.
- `DONE (local)` — Backend regression: `102 passed, 10 skipped`; frontend `tsc --noEmit` and Vite production build passed; browser scan smoke showed the product safety panel and FDA/CAERS signals.

### 2026-09-04 — Unified resolver and Japanese safety terms

- `DONE (local)` — Added `backend/scanner/resolver.py`: one barcode/name/ingredient contract with local index → normalized cache → Open Food Facts → USDA/openFDA → DSLD → Health Canada LNHPD fallback; unknown stays explicit and cache stores normalized fields only in separate `product-cache.db`.
- `DONE (local)` — Migrated scanner barcode and name fallback paths plus `/api/product/resolve` to the unified resolver; openFDA NDC results are typed as `drug`.
- `DONE (local)` — Aligned MeSpEn importer normalization with engine normalization, added local zip/staged JSON source support, and rebuilt `multilingual_medical_vocabulary.json` (`4,478` records; `2,196` Japanese; `2,282` Chinese).
- `DONE (local)` — Added Japanese allergen synonyms, Japanese additive-category caution signals, and negative-claim handling (`小麦不使用` etc.) in parser/personalization.
- `DONE (local)` — Focused resolver/Japanese regression: `28 passed`; full backend regression: `107 passed, 10 skipped`; resolver endpoint ingredient-only smoke returned `200 partial`.

- `DONE (local)` — Added privacy-safe `unresolved_products` queue to the separate resolver cache DB; unknown barcode/name attempts are deduplicated and counted by hashed lookup key.
- `DONE (local)` — Added admin-gated `GET /api/product/unresolved` using `PRODUCT_RESOLVER_ADMIN_TOKEN` or `ADMIN_API_TOKEN`.
- `DONE (local)` — Queue focused tests: `6 passed`; full backend regression: `108 passed, 10 skipped`; admin endpoint smoke returned `200`.

### 2026-09-04 — Runtime footprint and VPS Compose

- `DONE (local)` — Measured the accepted runtime snapshot at `5,236,011,008` bytes. FAERS data is already grouped by drug/PT/quarter; added runtime-only reachability pruning instead of dropping quarter/PT detail. The rebuild removed `3,986,972` unreachable aggregate rows.
- `DONE (local)` — Added a 5,000,000,000-byte runtime budget guard and manifest field for pruned rows. Promoted snapshot: `4,474,957,824` bytes, `3,990,034` FAERS rows, integrity `ok`, SHA-256 `57b2da9e84c941602b0c9d69cbe99914748a6bf96379ea3322c836a8838f4891`.
- `DONE (local)` — Added root `docker-compose.yml` for the API plus Caddy HTTPS proxy. Clinical runtime DB/manifest/evaluation are read-only mounts; scanner PHI and rate-limit state use separate writable mounts.
- `DONE (local)` — Added `tests/test_deployment_config.py`; runtime/deployment tests `31 passed`; full backend regression `113 passed, 10 skipped`; `docker compose config` passed with a temporary sample environment file.
- `DECISION` — Chốt kiến trúc tiết kiệm: ingest/crawl ngoài VPS, build runtime snapshot và image ngoài VPS, upload artifact đã verify; VPS 60 GB chỉ serve snapshot, scanner PHI và state.

### 2026-09-04 — Local USDA branded-food crawl

- `DONE (local)` — Downloaded official USDA FoodData Central Branded CSV archive (April 2026), `448,767,220` bytes, SHA-256 `26050a5d03197469813754743a21ee0fad4ccf22b6aac2a995846a987719fc49`.
- `DONE (local)` — Added `backend/import_usda_foods.py`; imported `464,497` food barcode rows into `backend/medmatch.cleaned.db` (`1,535,393` duplicate source rows ignored, `60` invalid rows skipped).
- `DONE (local)` — Rebuilt runtime with USDA index: `971,923` total products, `464,497` food rows, `4,691,533,824` bytes, integrity verified during build, SHA-256 `a935942795059aebacaa732e7291630bfa5429599fa8ac2b634f1558b815c319`.
- `DONE (local)` — Sample USDA barcode lookup returned product `WESSON Vegetable Oil 1 GAL`, type `food`.

### 2026-09-04 — Local Open Food Facts US crawl

- `DONE (local)` — Downloaded the official Open Food Facts full TSV dump for US filtering: `1,275,171,186` bytes, SHA-256 `f72687ee8bc6522054fe69dbfda6b91902c16af1ec2e043cde27bc6c29ad8176`.
- `DONE (local)` — Added `backend/import_openfoodfacts_us.py`; imported `81,913` new US barcode rows, ignored `773,600` duplicates, skipped `54,617` invalid rows, and filtered `3,622,637` non-US rows.
- `DONE (local)` — Rebuilt runtime with USDA + Open Food Facts US: `1,793,936` products, `1,286,510` foods, `4,915,445,760` bytes, integrity `ok`, SHA-256 `14cac9ee9ceab1b9be11000855da0950450060691406321ebc51c40cd47427d9`.
- `DONE (local)` — Sample Open Food Facts barcode lookup passed: `00000028` → `Hershey’s Syrup`.
- `DONE (local)` — PC barcode coverage audit: runtime has `1,793,936` unique codes (`269,999` drug, `237,427` supplement, `1,286,510` food). Coverage against imported sources is `100%`: USDA `464,996/464,996`; OFF-US `855,510/855,510`; union `1,293,455/1,293,455`.

### 2026-09-04 — Multilingual contribution and product identity graph

- `DONE (local)` — Added `backend/scanner/product_graph.py`, a separate graph DB for product families, market SKUs, multilingual observations, formulation fingerprints, and cross-market links. It never stores raw images, receipts, profiles, or device tokens.
- `DONE (local)` — Added explicit-consent contribution API: `POST /api/product/contributions`; facts remain pending until admin approval or rejection.
- `DONE (local)` — Added admin review routes for observations and cross-market candidates. Exact brand + ingredient fingerprint creates a reviewable candidate only; it is never auto-merged into safety facts.
- `DONE (local)` — Approved observations are reusable by later resolver requests as `community_verified`; regression/API smoke passed and full backend regression is `117 passed, 10 skipped`.

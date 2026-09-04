# MedMatch AI — Roadmap hợp nhất runtime

**Cập nhật:** 2026-09-01  
**Mục tiêu:** MedMatch là app chính; React scanner chỉ là frontend source.
## Kiến trúc đích

```text
medmatch :8765
├── /                 React scanner UI đẹp (production frontend)
├── /api/*            FastAPI API duy nhất
├── backend/engine.py MedMatch engine 7 lớp
├── backend/scanner/  Scanner backend Python
└── backend/medmatch.db
```

`personalized-product-scanner/` là **frontend source chính thức**. Sau mỗi build, bundle React được đưa vào `medmatch/static/scanner/` và FastAPI phục vụ bundle đó ở `/`. Frontend vanilla hiện tại của MedMatch (`static/index.html`, `static/app.js`) chỉ giữ làm legacy/reference trong giai đoạn chuyển đổi; không phải UI production cuối cùng.

Express `server.ts` không phải backend production. Logic nghiệp vụ phải nằm trong `medmatch/backend/`.

## Nguyên tắc bảo toàn

- Không xóa tính năng cũ trước khi có parity test.
- Giữ React scanner làm frontend production; không quay lại UI vanilla basic.
- Không tạo bản engine hoặc storage thứ hai.
- Không lấy README/PROGRESS làm bằng chứng nếu code và runtime ngược lại.
- Mọi kết quả phải chỉ rõ direct interaction, condition warning, allergy, nutrition, electrolyte, QT, Beers, schedule và evidence.
- FDA disclaimer giữ nguyên nội dung bắt buộc.
- Không đưa nguồn dữ liệu có license NC vào commercial build.

## Giai đoạn 0 — Baseline và parity matrix

- [x] Xác định `medmatch` là app chính.
- [x] Xác định React scanner là frontend source.
- [x] Kiểm kê route FastAPI thật trong `backend/app.py` và `backend/scanner/router.py`.
- [x] Kiểm kê route duplicate trong `personalized-product-scanner/server.ts`.
- [x] Kiểm kê i18n, schedule timeline, profile, history và routine từ source.
- [x] Tạo parity matrix route → UI → storage → test.
- [x] Ghi nhận tính năng có thật và tính năng chỉ được mô tả nhưng chưa có code.
- [x] Ghi nhận provenance/license registry còn thiếu cho tapirro, iDISK, Sahayak, Verified Supplement Evidence và SUPP.AI.

### Release slice parity matrix

| Contract | UI | Storage | Test |
|---|---|---|---|
| Scan envelope + `matchAssessment` | `ScannerView`, `ScanResultCard` | `ScannerDB.history` | `tests/test_release_slice.py` |
| Typed MedMatch analysis | `MedMatchResults`, `ScheduleTimeline` | Engine SQLite | `test_product_entity_filter*` |
| Profile/family fields | `ProfileView`, family modal | `ScannerDB` JSON | existing API smoke + storage roundtrip |
| Draft confirm boundary | Draft review panel | history only after scan analysis | `test_draft_confirmation_does_not_write_history` |
| PWA root/scanner assets | React root and `/scanner/` | static bundle | browser offline smoke |

## Giai đoạn 1 — Một runtime FastAPI

- [x] Port scan draft/confirm vào `backend/scanner/router.py`.
- [x] Port local product-index lookup vào FastAPI scanner.
- [x] Chuẩn hóa response `ProductScanResult` giữa mọi scan mode.
- [x] Dùng một storage profile/family/history/routine/cache trong FastAPI runtime.
- [x] Cho React scanner chạy same-origin dưới `/scanner/`.
- [x] Chuyển Vite dev sang proxy FastAPI; không dùng Express business API.
- [x] Sửa `start-medmatch.bat` chỉ khởi động MedMatch FastAPI.
- [x] Build React vào `medmatch/static/scanner/`.
- [x] Xác nhận `/`, `/scanner/`, `/api/*` cùng một origin.

## Giai đoạn 2 — Bảo toàn tính năng

- [x] Bảo toàn i18n 6 ngôn ngữ trên React production UI và PWA root/scanner.
- [x] Bảo toàn engine 7 lớp và các section cảnh báo.
- [x] Bảo toàn schedule conflict, schedule optimizer và `scheduleTimes`.
- [ ] Xác minh reminder notification; nếu chưa có code thì tách thành feature mới, không ghi là đã hoàn thành.
- [x] Bảo toàn profile bệnh nền, thuốc, dị ứng và chế độ ăn.
- [x] Bảo toàn family/caregiver profile switching.
- [x] Bảo toàn barcode, OCR text/image, receipt, batch scan, skincare và cross-reactivity.
- [x] Bảo toàn smart swaps, AI chat, analytics, history, compare và PDF/print.
- [x] Bảo toàn PWA manifest/service worker/offline behavior.

## Giai đoạn 3 — Tính đúng đắn y khoa và trạng thái UI

- [x] Chặn false-positive normalizer: food ingredient không tự map thành drug.
- [x] Tách entity type trước khi chạy interaction engine.
- [x] Sửa batch summary dùng trực tiếp `matchAssessment.status`.
- [x] Tách direct interaction khỏi condition/diet/allergy/electrolyte warnings.
- [x] Hiển thị rõ bệnh nền và thuốc đang được áp dụng.
- [x] Tách số interaction khỏi số evidence.
- [ ] Đánh dấu rõ CYP inference và evidence không trực tiếp.
- [x] Kiểm tra ngưỡng sodium/hypertension và các luật condition khác.
- [ ] Giữ commercial-license gate xanh.

## Giai đoạn 4 — Kiểm thử end-to-end

- [x] Golden test profile tăng huyết áp + Amlodipine + low sodium.
- [x] Golden test profile cao tuổi + Beers/QT/electrolyte.
- [x] Golden test eczema/sensitive skin.
- [x] Golden test pregnancy.
- [x] Golden test barcode có sản phẩm và thiếu sản phẩm.
- [x] Golden test ảnh Ingredients hợp lệ và ảnh mặt trước không đủ dữ liệu.
- [x] Golden test confirm/reject draft không ghi history trước confirm.
- [x] Golden test batch nhiều sản phẩm và cross-item.
- [ ] Golden test đủ 6 ngôn ngữ.
- [x] Benchmark OCR Japanese labels với visible key-term ground truth và partial ingredient recall; full CER/WER chưa đánh giá.
- [x] Browser smoke test `/scanner/` bằng FastAPI một URL.
- [x] Browser smoke test root React `/` bằng FastAPI một URL.

## Giai đoạn 5 — Phát hành

- [x] Xóa đường chạy production Express; `deploy/start.sh` chạy FastAPI foreground.
- [x] Cập nhật lệnh khởi động và tài liệu theo runtime một URL.
- [ ] Build Docker/Cloud Run từ `medmatch` (Dockerfile/start.sh đã FastAPI-only; build/deploy thật còn chờ Docker/GCP credentials).
- [ ] Xác nhận database mount và giới hạn SQLite/GCS FUSE.
- [ ] Xác nhận HTTPS, camera, OCR và PWA install.
- [x] Cập nhật changelog phát hành.

## Changelog

### 2026-09-01

- Chốt lại `medmatch` là app chính.
- Ghi nhận FastAPI scanner đã có phần lớn route nhưng thiếu scan draft/confirm.
- Ghi nhận Express `server.ts` đang chứa backend duplicate.
- Ghi nhận code hiện có schedule timeline và `scheduleTimes`, chưa có notification reminder thật.
- Bắt đầu kế hoạch hợp nhất runtime và bảo toàn toàn bộ tính năng.
- Đã port các route `/api/scan/draft`, `/api/scan/draft/image`, `/api/scan/draft/{id}/confirm` vào FastAPI.
- Đã nối barcode draft và scan chính vào local `product_index` của MedMatch.
- Đã build React source vào `medmatch/static/scanner/`.
- Đã smoke test `http://127.0.0.1:8765/scanner/` với barcode thật `0033964039711`.
- Đã xác nhận profile Arthur (68 tuổi, hypertension, Amlodipine, Metformin) hiển thị các cảnh báo direct, CYP, electrolyte và nutrient depletion trên một origin.
- Đã sửa `matchAssessment` của barcode scan: medication interactions nay được hợp nhất vào status/score/summary; major interaction không còn hiển thị như `COMPATIBLE`.
- Đã chuẩn hóa envelope `ProductScanResult` cho barcode, image, text, name và batch scan; source contract nhận cả `product-index:*`, DSLD, openFDA và name recognition.
- Đã chặn entity false-positive từ formulation materials, ưu tiên typed canonical entity và lọc interaction không liên quan tới product ingredient.
- Đã sửa batch persistence để lưu kết quả sau cross-item aggregation.
- Đã đồng bộ family profile với medications, age, organ function, pregnancy và scheduleTimes; bổ sung root PWA aliases `/index.html`, `/manifest.webmanifest`, `/sw.js`.
- Đã nối Vite dev server vào FastAPI qua `/api` proxy; smoke test Vite UI và API cùng một backend.
- Đã smoke test receipt, batch, skincare, cross-reactivity, smart swaps, AI chat, analytics, history, compare, OCR image và service worker offline.
- Đã bổ sung golden tests cho profile hypertension/low-sodium, elderly Beers/QT/electrolyte, pregnancy và eczema/sensitive skin.
- Đã bổ sung golden tests cho barcode found/missing, OCR ingredient completeness và giới hạn batch 10 mã.
- Đã sửa `build_db()` để giữ/reconstruct RxNorm micro-classes, tránh orphan references trong SUPP.AI sau rebuild.
- Đã thu thập 25 ảnh Commons có metadata license và 12 ảnh Japanese do người dùng cung cấp trong bộ benchmark cục bộ.
- Đã chạy RapidOCR trên 37 ảnh: 37/37 run thành công, 28/37 có ký tự Nhật; chưa gọi đây là accuracy vì chưa có ground truth.
- Đã rà soát đủ 12 ảnh user trong benchmark; 9 ảnh có 48 visible key terms, 3 ảnh negative/không có nhãn Nhật.
- Đã thêm conservative Japanese OCR normalization và parser support cho `原材料名`, dấu phân cách `、`, allergen terms và đơn vị `ug/mcg`.
- Đã chạy crop OCR 3 vùng overlap: Japanese-output coverage user tăng 10/12 → 11/12 nhưng key-term recall giảm 17/48 → 16/48 và median latency tăng 1,445.0ms → 5,554.1ms; giữ baseline làm mặc định.
- Đã thêm MeSpEn_Glossaries CC BY 4.0: 4,458 medical synonyms được map offline (2,193 Japanese + 2,265 Chinese, 1,612 entities); bỏ Korean khỏi pack mới.
- Đã rebuild `ingredient_synonyms`: 40,771 rows; smoke test `イブプロフェン` → NSAIDs và `阿莫西林` → Antibiotics đều resolve local, không HTTP.

### 2026-09-02

- Đã build Docker image `medmatch-api:local` từ runtime snapshot compact.
- Đã smoke container qua `/api/health`, `/api/privacy`, `/api/provenance`,
  `/api/analyze`, barcode `/api/scan` và `/api/user-data/purge`.
- Đã thêm manifest checksum/version/rollback pointer; refresh lỗi giữ nguyên
  snapshot accepted.
- Đã chuyển rate limit sang SQLite shared store, hỗ trợ nhiều worker và
  trusted proxy headers có cấu hình.
- Đã xác minh backup/restore SQLite và checksum sidecar trên fixture.
- Public deploy, volume production, HTTPS/domain smoke và Docker Cloud Run
  credentials vẫn là blocker bên ngoài máy local.

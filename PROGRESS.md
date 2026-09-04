# TIẾN ĐỘ & DEBUG NOTES — MedMatch AI

**Cập nhật:** 2026-09-01 · **Repo:** G:\aisuckhoe (git, branch master) · **Commit cuối:** xem `git log --oneline -5`
**Nhật ký liên tục:** xem `medmatch/WORKLOG.md` trước khi bắt đầu việc mới; cập nhật file đó ngay sau mỗi task hoàn thành.

---

## 1. Chạy app

| App | Lệnh | URL |
|---|---|---|
| **MedMatch** (FastAPI + React PWA + 7-layer engine) | `start-medmatch.bat` hoặc `cd G:\aisuckhoe\medmatch && python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765` | `http://127.0.0.1:8765/` |

- React dev standalone: `cd G:\aisuckhoe\personalized-product-scanner && bun run dev` → Vite `:5173`; `/api/*` proxy tới FastAPI `:8765`.
- Production: FastAPI là runtime duy nhất, phục vụ React tại `/` và `/scanner/`, cùng toàn bộ `/api/*`.
- Test backend: `python -m pytest tests/ -q` (cần cài `requirements-test.txt`); test frontend: `bun x tsc --noEmit`.
- **Production bundle:** `SCANNER_BASE=/scanner/ SCANNER_OUT=dist-medmatch bun run build`, sau đó publish vào `medmatch/static/scanner/`.

## 2. Đã hoàn thành

| Hạng mục | Chi tiết | Commit |
|---|---|---|
| De-Gemini scanner | OCR = RapidOCR local (`medmatch/backend/scanner/parsing.py`); parser nhãn/receipt, advisor chat, Smart Swaps và skincare đã port vào FastAPI `backend/scanner/`. React chỉ gọi API same-origin | roadmap hợp nhất |
| UI 7 lớp | React `MedMatchResults`/`ScheduleTimeline` render interactions, cascades, QT, electrolytes, Beers, schedule và depletions | — |
| Tích hợp FastAPI | `backend/scanner/router.py` cung cấp `/api/scan`, `/api/medmatch`, `/api/products`, `/api/lookup` và toàn bộ scanner modules; không còn Express BFF trong dev/production path | runtime một URL |
| Offline/PWA | `medmatch/static/scanner/sw.js` cache-first assets, network-first navigation, không cache `/api/`; root aliases `/manifest.webmanifest` và `/sw.js` đã smoke offline | runtime một URL |
| License commercial-clean | Đã DROP `ddinter_interactions` (CC BY-NC-SA) + `drugfood_evidence` (CC BY-NC); `unify.py` guard; test `test_commercial_license_clean` chặn tái phạm; backup research: `backend/data/_nc_backup/` (gitignored) | `66fb4f8` |
| Đa ngôn ngữ 6 thứ (en/vi/fr/de/it/es) | Scanner: dict vi ~180 keys, 21/21 components wire `language` prop + `t()`; medmatch: `static/i18n.js` + selector + re-render động. FDA disclaimer giữ VERBATIM tiếng Anh + dòng dịch bên dưới | `39b3f3b`, `ca577bf` |
| **Data: DailyMed mở rộng** | 744 → **762 cặp** class×class (134 thuốc quét thêm, shard `--mod 8 --idx 0-3`) | trong DB |
| **Data: NIH DSLD** | **145,650 sản phẩm có mã vạch**, thành phần đã nhập; cascade lookup: chỉ mục nội bộ → OFF → **NIH DSLD** → UPCitemdb | đã hợp nhất |
| **Chỉ mục sản phẩm hợp nhất** | **507,426 dòng**: NDC 269,999 · UPC 99,864 · EAN 92,042 · DSLD ID 45,521 | đã hợp nhất |
| Pre-triage review queue | 155/286 cặp CYP-inferred verified (đối chiếu nguồn authoritative); **131 pending chờ dược sĩ thật** | trong DB |
| Test thực tế battery | Script đo A/B/C/D — xem §3 | — |

## 3. Số liệu test thực tế (trước → sau)

| Test | Trước | Sau |
|---|---|---|
| A. Normalization 35 tên US/EU/TPCN | 34/35 (97%, thiếu `paracetamol`) | **35/35 (100%)** |
| B. Cặp tương tác kinh điển | 6/10 | **7/11** (thêm paracetamol×warfarin) |
| C. Barcode US (OFF+DSLD) | 4/8, thuốc/TPCN 404 | DSLD pipeline sẵn sàng (7,472 barcode) |
| D. Latency analyze 8 mục | 372–463ms | không đổi (đã tốt) |

## 4. Việc cần debug / làm tiếp (theo ưu tiên)

1. **4 cặp tương tác vẫn miss** — nguyên nhân CẤU TRÚC (không phải thiếu crawl): DailyMed parser chỉ map class×class thuốc; còn lại là drug×food/class-rule:
   - `sertraline + ibuprofen` (SSRI×NSAID, GI bleed) — cần luật class-level trong `drug_drug_seed.py` (tìm class id NSAID trong `drug_classes`)
   - `levothyroxine + calcium`, `lisinopril + potassium`, `metformin + alcohol` — cần luật class×food trong `drug_food_seed.py` (foods có sẵn: alcohol, potassium? kiểm tra `SELECT id FROM foods`)
   - Pattern: thêm vào seed → `python -m backend.db` → `python -m backend.unify` → chạy lại test B (kỳ vọng 11/11)
2. **131 cặp CYP pending** (`/api/review/next`, trust 0.5) — cần dược sĩ thật Verify/Reject. 155 cặp đã auto-verified bằng cách đối chiếu DailyMed/DDInter/tapirro (xem note trong `review_queue.note`).
3. **Đối chiếu UPC/EAN** — 191,906 dòng chỉ mục đã có thông tin sản phẩm nhưng chưa có mapping thành phần; cần làm tiếp trước khi kết luận tương tác tự động.
4. **Vite dev stale graph**: sửa file nhiều lần liên tiếp → tab mở sẵn render trắng (root trống, không lỗi console). **Fix: restart `scanner-app`**. Production build không bị.
5. **Cosmetic:** topbar scanner tràn nhẹ với nhãn VI dài; một số mô tả card trong ScannerView còn EN; label allergen/diet options trong ProfileView còn EN (mảng module-level — pattern `t('key', label)` sẵn sàng).
6. **`/api/stats` scanner (:3000) chưa tồn tại** — rơi vào catch-all trả HTML (medmatch :8765 thì có).
7. **Repo:** CSV DSLD (~800MB) + `_nc_backup/` + `medmatch.db` đã gitignore — đừng `git add -f`. Repo sau gc: 16.5MB.

## 5. Ghi chú kỹ thuật quan trọng

- **Contract `Engine.analyze` trả 9 keys** (đừng viết test assert 4 keys cũ): `matched, interactions, unmatched, depletions, cascades, schedule, qt_risk, electrolytes, beers`. `beers`/`qt_risk` chỉ có dữ liệu khi `profile.age >= 65`.
- **License:** commercial build KHÔNG được chứa nguồn NC. Test `test_commercial_license_clean` sẽ fail nếu ai re-import DDInter/DrugBank quên gỡ. Nguồn free hiện tại: DailyMed (public domain), FDA labeling rules, SUPP.AI, iDISK, OnSIDES (CC BY 4.0), PubChem, tapirro (MIT), DSLD (public domain).
- **Cascade lookup barcode:** OFF → NIH DSLD (bảng `dsld_products`, import từ `backend/data/dsld/*.csv` — user tự tải tay vì Cloudflare chặn client lập trình) → UPCitemdb (cần key free).
- **Engine match index** giờ nạp cả `ingredient_synonyms` — thêm synonym mới = chỉ cần INSERT vào bảng đó + restart (không cần sửa engine).
- **Sửa file scanner nhiều lần liên tiếp → restart `bun run dev`** (vite stale graph, xem §4.4).
- Kế hoạch tổng: `KeHoach_XayDung_MedMatchAI_v2.md` · kiến trúc 7 lớp: `brain.md` · tích hợp UI: `KeHoach_TichHop_Frontend_MedMatchAI.md` (Giai đoạn 1-3 xong, Giai đoạn 4 còn Health Dashboard/Compare đã làm một phần, offline cache xong).

---

## 6. 🎯 MỤC TIÊU CUỐI: iOS APP LÊN APP STORE (chốt 2026-08-27)

**Quyết định kiến trúc chốt:**
1. **Deploy một container, một URL** — FastAPI phục vụ React và API trực tiếp. `deploy/Dockerfile` dùng Python runtime; `deploy/start.sh` chỉ chạy uvicorn foreground. Cơ sở dữ liệu hợp nhất khoảng 5.7GB đi qua **GCS FUSE volume** (`MEDMATCH_DB` env, `db.py` đã hỗ trợ) — tránh giới hạn 100MB source của Cloud Build. Giữ `--max-instances 1` vì SQLite + GCS FUSE.
2. **FastAPI :PORT = runtime duy nhất** (Cloud Run dùng `$PORT`, local dùng `8765`); không còn BFF Express trên đường chạy production.
3. **iOS = Capacitor wrap** React app (KHÔNG rewrite React Native). Đúng hướng plan1 đã đề: camera + OCR nhãn.

**Chuỗi tiền điều kiện App Store (theo thứ tự):**
1. **Deploy engine lên cloud** — app trên điện thoại KHÔNG gọi được localhost. Cloud Run dùng cùng một URL cho UI và API.
2. **Native hóa 2 tính năng** (Capacitor plugin):
   - Camera/quét barcode: ZXing hiện chạy được trên iOS Safari (getUserMedia) — giữ, thêm Capacitor Camera plugin cho chụp nhãn.
   - OCR: chuyển sang **Apple Vision (text recognition)** qua Capacitor plugin khi chạy trên iOS; Tesseract.js làm fallback web.
3. **Capacitor init**: `npm i @capacitor/core @capacitor/cli` → `npx cap init` → `npx cap add ios` (⚠️ bước `pod install` cần macOS — build iOS trên Windows KHÔNG được; dùng Mac thật hoặc CI: GitHub Actions macOS runner / Codemagic).
4. **Apple Developer Account** ($99/năm) + App Store Connect tạo app.
5. **Compliance app y tế (App Review 1.4.1):**
   - Disclaimer y tế đã có VERBATIM (FDA) ✓ — phải hiển thị ở màn đầu tiên/kết quả, không chỉ footer
   - KHÔNG hứa chẩn đoán/điều trị — wording hiện tại đã an toàn ("reference information")
   - Privacy Nutrition Labels: dữ liệu tủ thuốc nằm local (localStorage) = không thu thập ✓ — nếu sau này sync cloud thì phải mã hóa + khai báo
   - Tài khoản demo + video demo cho reviewer
6. **Trước khi submit:** test B đạt ≥10/11 (thêm 4-6 luật seed FDA — xem §4.1), 131 cặp CYP pending cần dược sĩ duyệt hoặc tạm ẩn trust 0.5 khỏi kết quả iOS.

**Khởi động local:** chạy `start-medmatch.bat` (FastAPI + React tại `:8765`, tự mở trình duyệt).

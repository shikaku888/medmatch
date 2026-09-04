# MEDMATCH — AUDIT TOÀN BỘ APP & PLAN ĐÓNG GÓI
_Ngày audit: 2026-08-27 · Method: introspect app đang chạy + smoke test thật + inventory code. Không có mục nào viết theo cảm tính._

---

## 1. Kiến trúc (như đang chạy thực tế)

```
                    ┌─ /            vanilla UI (an toàn thuốc, PWA, cabinet localStorage)
users ── HTTPS ──►  │  /scanner/    React SPA 6.3MB (Health Scanner đầy đủ)
                    │  /api/*       FastAPI 53 endpoints
                    │
                    ├─ backend/engine.py      7-lớp: match→analyze→CYP450 inference
                    ├─ backend/scanner/*      11 module (port từ Express BFF cũ)
                    ├─ deploy/runtime/medmatch.db  compact read-only runtime snapshot
                    ├─ devices/<token>.json   storage per-device (multi-user)
                    └─ coverage_events.jsonl  telemetry hit/miss từng scan
Nguồn ngoài: OFF/OBF · USDA · openFDA NDC · PubMed · (iDISK nội bộ)
```

## 2. Backend — 53 endpoints · smoke 100% với fixture đúng

| Nhóm | Endpoints | Trạng thái |
|---|---|---|
| Engine (vanilla UI) | search, herb/class detail, analyze, lookup, products, unified, ai_reviews, review, class effects | ✅ 17/17 — 6 cảnh báo smoke đầu là fixture sai (id thật `anticoagulantes`, `estatinas`) |
| Scanner core | scan, scan/text, scan/image (OCR), scan/receipt, batch-scan, medmatch/check+stats | ✅ 6/6 test thật (Nutella, SLEEPWELL ảnh, hóa đơn, pantry) |
| Người dùng | profile, family-profiles (CRUD+switch), history (CRUD+favorite), analytics, skincare-routine (CRUD+audit) | ✅ 11/11 — per-device qua cookie `mt_device`, test cô lập 2 thiết bị |
| Trợ lý | ai-chat, smart-swaps (kèm verify gate), pubmed, herb-drug-interactions, markets, demo-products, cross-reactivity | ✅ 7/7 |
| Vận hành | coverage/stats (mới), health | ✅ |

**Kết luận backend: 0 bug mở.** pytest 19 passed.

## 3. Frontend — mọi tính năng đã được bấm tay-ảo qua UI thật (không đọc code suông)

| # | Tính năng | Bằng chứng chạy thật | Rỗng? |
|---|---|---|---|
| 1 | Barcode scan + result card | Nutella: danger 50/100, milk-allergy, PubMed 16586+ studies | Thật |
| 2 | Photo OCR (upload ảnh) | Ảnh SLEEPWELL → Melatonin + DOI 10.1016/j.pain.2012.08.016 trust 0.9 | Thật |
| 3 | Raw Text scan | Niacinamide/Retinol/Parfum → COSMETIC + conflicts | Thật |
| 4 | Medication Names | Advil 200mg → NSAIDs (sau khi vá 9 alias) | Thật |
| 5 | Camera HUD | Mở stream OK; **chỉ chạy secure-context** (HTTPS) | Thật (cần HTTPS) |
| 6 | Smart Swaps | 5 candidate iDISK + medMatchVerification gate | Thật |
| 7 | AI Dietitian chat | Câu trả lời sinh từ engine, không LLM | Thật |
| 8 | Dị ứng chéo (6 hội chứng) | Birch/Latex/Crustacean/Mugwort/Ragweed/Dust | Thật |
| 9 | Kệ skincare (4 default + audit) | Score + conflicts render | Thật |
| 10 | Cửa hàng 13 store + filter quốc gia | US/UK/FR/DE/IT/ES chips | Thật |
| 11 | Hóa đơn AI Vision | Sample receipt thật (Tesco UK, Pharmacy US) | Thật |
| 12 | History + Favorite + filter | SLEEPWELL favorite=true API ✓ | Thật |
| 13 | Analytics dashboard | Đếm thật từ history | Thật |
| 14 | Profile + presets | Chip Soy → Save → API [peanut,milk,soy] ✓ | Thật |
| 15 | Family profiles | 4 default + switch/crud 200 | Thật |
| 16 | PWA (manifest+SW) | SW active, scope /scanner/, offline shell | Thật |
| 17 | i18n 6 ngôn ngữ | VI render toàn bộ | Thật |
| 18 | **Pro paywall modal** | Chỉ là màn sales | **Trang trí** (cố ý) |

**Kết luận frontend: 17/18 thật; 1 mục trang trí cố ý.** Bugs đã vá theo phát hiện của bạn: header tràn ngang mobile (857→393px), crash Analytics với cosmetic (nutrition null).

## 4. Dữ liệu & engine

| Lớp | Số liệu |
|---|---|
| Herbs / drug classes | 1,216 / 58 |
| Tương tác herb-drug (tapirro) | 565 · drug-drug rules 57 · DailyMed 762 · SUPP.AI 71,900 · herb-herb 13,355 · iDISK 76 |
| Lớp hợp nhất | 22,680 cặp · 1,284 standard · 6,749 synonyms · CYP-inferred 111 |
| Danh mục sản phẩm | iDISK 69,348 (NHP Canada) |
| Nguồn live | OFF/OBF barcode+search · USDA · openFDA NDC · PubMed |

## 5. Khoảng trống & rủi ro (xếp theo tác động user)

| P | Khoảng trống | Ảnh hưởng | Giải pháp đã có/đang làm |
|---|---|---|---|
| **P0** | MISS barcode/brand chưa có trong nguồn mở (Centrum, Nature Made, barcode nhà thuốc) | Trial user thấy "sai/thiếu" | ✅ Telemetry `/api/coverage/stats` → top-miss thành worklist; 404 có hint dẫn sang OCR/name-mode; MISS trung thực thay vì dữ liệu sai |
| **P0** | Chưa có server public | Không ai ngoài LAN dùng được | Dockerfile, compact snapshot builder, `.dockerignore`, health check và fly.toml đã chuẩn bị; public deploy còn pending |
| ~~**P1**~~ | ~~DSLD chưa import~~ | — | ✅ **XONG**: 214K hàng đã import + nối vào scan; NDC local index 135K; synonyms DE/FR/IT |
| **P1** | OCR chạy trên server (CPU) | Load khi nhiều user upload ảnh | Chuyển OCR client-side (tesseract.js — vanilla UI đã làm mẫu) khi >100 upload/ngày |
| **P2** | iOS: chưa có tài khoản Apple + build | Không lên App Store | Workflow CI sẵn — chờ account 99$ |
| **P2** | Pro paywall trang trí | Không thu tiền | Quyết định business sau khi có user |
| **P3** | Đa ngôn ngữ backend message | UX nhất quán | i18n message catalog |

## 6. PLAN ĐÓNG GÓI — 4 phase, mỗi phase có tiêu chí nghiệm thu

### Phase 1 — "Deployable" (mục tiêu: link công khai chạy thật) · ~1 buổi
- [x] Build compact runtime snapshot; full source DB/raw datasets không vào image
- [x] Entrypoint seed atomic + integrity check; API không chạy importer khi boot
- [ ] Tạo/extend Fly volume tối thiểu 5 GB, cấu hình secrets ngoài repository
- [ ] Push image lên Fly.io (`fly deploy`) hoặc VPS+Caddy
- [ ] Domain + HTTPS xanh; smoke health/privacy/provenance/analyze/scan/purge qua domain
- [x] Công cụ backup/restore atomic, online và có integrity check
- [ ] Diễn tập restore `medmatch.db`, log rotation và coverage telemetry retention
- **Nghiệm thu: mở link trên 3G điện thoại, scan được 5/5 sản phẩm mẫu**

### Phase 2 — "Beta 50 users" (~1 tuần chạy)
- [x] Import DSLD (P1) — đã có local product index; chỉ refresh lại theo top-miss
- [ ] Weekly: xem coverage/stats, bổ sung alias/thuộc tính theo top-miss
- [ ] Thêm "Góp ý sản phẩm thiếu" nút trên 404 card (1 giờ) → user tự nuôi worklist
- **Nghiệm thu: hit-rate ≥85% trên nhóm sản phẩm beta dùng nhiều nhất; 0 crash 7 ngày**

### Phase 3 — "App Store" (~song song Phase 2)
- [ ] Bạn: Apple Developer + tạo API key → 4 secrets vào GitHub
- [ ] Tôi: tag `ios-v1` → CI build → TestFlight → review materials (đã có privacy policy + disclaimers)
- **Nghiệm thu: IPA cài được qua TestFlight trên iPhone thật; pass review hoặc có phản hồi xử lý**

### Phase 4 — "Launch" (sau Phase 2 đạt)
- [ ] CH Play build (tái dùng server, thêm android workflow — 1 buổi)
- [ ] Onboarding 3 màn giải thích phạm vi phủ + hướng dẫn khi miss
- [ ] Pricing decision cho Pro modal

## 7. Việc CẦN BẠN (tôi không làm thay được)
1. Chọn Fly.io hay VPS + mua (10 phút) → tôi deploy ngay phiên sau
2. Apple Developer 99$ (chỉ chặn iOS, không chặn Phase 1-2)
3. Quyết định thị trường đầu tiên: US/UK (dữ liệu đang mạnh nhất) hay VN (cần thêm nguồn VN — OpenFoodFacts VN mỏng)

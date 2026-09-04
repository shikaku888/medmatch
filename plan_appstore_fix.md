# Plan App Store — MedMatch iOS (US/EU) — Tránh treo review / từ chối

Tạo: 2026-08-28  |  Cơ sở: review code medmatch (backend/app, advisor, router, db, static)
Mục tiêu: app iOS đưa lên App Store, bán subscription (Pro $19/mo, Caregiver $69/mo), tuân thủ ARG, không bị treo review y tế / privacy.

---

## 1. Tóm tắt rủi ro từ review trước (phải fix P0)

| Rủi ro | File / dòng | Tác động App Store |
|---|---|---|
| **PHI gửi ra Google Gemini** (nếu `GEMINI_API_KEY` set) | `backend/scanner/advisor.py:367` | ARG 5.1.1 / 5.1.2: tiết lộ dữ liệu sức khỏe cho bên 3 không khai báo → từ chối / treo |
| **Dữ liệu y tế lưu server-side** (`backend/data/devices/<token>.json`) | `backend/app.py:37-47`, `storage.py:416-439` | Vi phạm tuyên bố privacy (`README.md:166` “không rời trình duyệt”); cần AES-256 + audit trước khi đồng bộ |
| **Cookie `mt_device` 10 năm, thiếu `Secure`** | `app.py:45` | Security; nếu HTTPS tự ký (`start_https.bat`) → dễ bị sniff |
| **Chat tiếng Việt cho user Mỹ** (bilingual) | `advisor.py:211`, `i18n.js:47+` | Không phải lỗi, nhưng nếu user không đọc EN → bỏ qua FDA disclaimer (`static/app.js:584` hard EN) → ARG 1.3 / 5.1 có thể bắt “misleading health info” |
| **Review queue CYP 0.5 chưa duyệt** | `db.py` / `engine.py` | Hiển thị “tương tác suy luận” cho user phương Tây mà không rõ “not verified” → ARG 1.3 |
| **Không có xác thực / CSRF** cho `/api/ai-chat`, `/api/profile` | `router.py:238`, `router.py:202` | Không trực tiếp từ chối, nhưng nếu có leak data → ARG 5.1 kết hợp |
| **Dữ liệu NC (DDInter) đã gỡ đúng** | `db.py` (không có `ddinter_interactions`) | OK; giữ backup `_nc_backup/` không load |
| **Subscription chưa có IAP** | `README.md:16`, chưa có StoreKit | ARG 3.1.1: phải dùng Apple IAP cho digital goods; không được dùng Stripe/web cho nội dung số trong app |

---

## 2. Phased Fix Plan (thực hiện tuần tự, không nhảy P1 trước P0)

### Phase 1 — DATA / PRIVACY / MEDICAL LIABILITY (P0) — 1 tuần

**Mục tiêu:** App Store sẽ không từ chối vì “health data sent to unverified third party” hoặc “false privacy claims”.

1.1. **Tắt / khóa hoàn toàn `_gemini_polish`**
- `backend/scanner/advisor.py:367-450`: Đặt `if not key: return None` (đã có), nhưng **đảm bảo key không bị set ngầm** trong `.env`/Docker; thêm `assert os.getenv("GEMINI_API_KEY") is None` ở startup nếu app build cho App Store.
- Nếu muốn giữ “polish”: phải có **consent screen rõ ràng** ở UI (`static/index.html`) + **BAA với Google** + khai báo trong App Privacy (`Data Used: Health & Fitness`, `Data Shared: Third-party analytics / AI — with consent`). Khuyên: **bỏ hoàn toàn cho MVP App Store**.

1.2. **Xóa / mã hóa server-side PHI (`backend/data/devices/`)**
- Tùy chọn A (khuyên cho App Store): Chuyển cabinet hoàn toàn về **Apple HealthKit / Core Data / Secure Enclave** (local on device), bỏ middleware lưu JSON server. Điều này phù hợp tuyên bố `README.md:166` và tránh HIPAA/BAA phức tạp.
- Tùy chọn B (nếu cần sync): Mã hóa AES-256 file trước lưu (`backend/dev_cert.py` chỉ tạo cert, không mã hóa); thêm audit log 6 năm (`plan1.md`); ký BAA nếu dùng server Mỹ.
- **Hành động ngay:** Xóa tất cả file `backend/data/devices/*.json` trong build; thêm `.gitignore` cho `devices/`; thay `get_user_db()` bằng `LocalStorageDB` (hoặc `UserDefaults` trong native iOS wrapper).

1.3. **Sửa cookie / security**
- `backend/app.py:45`: Thêm `secure=True`, `same_site="lax"` (đã), giảm `max_age` → `86400*30` (30 ngày); thêm `httponly=True` (đã).
- Nếu app iOS native: **bỏ cookie** hoàn toàn; dùng `URLSession` + `AppStorage` (Keychain) cho device token.

1.4. **App Privacy (App Store Connect)**
- Khai báo đúng (không khai gian):
  - **Health & Fitness:** Yes (medication/sup list)
  - **Usage Data:** No (hoặc Yes chỉ nếu có analytics, phải khai)
  - **Third-party sharing:** **No** (sau khi bỏ Gemini; nếu giữ phải khai rõ model name + purpose)
  - **Tracking:** No (không có IDFA / quảng cáo)
  - **Data retention:** “Not linked to user”; nếu có server: phải nói rõ “encrypted at rest, retained 6 years per audit requirements”
- Đảm bảo không có “hidden” collection qua Tesseract/OCR (chỉ xử lý cục bộ).

1.5. **Medical Disclaimer — bắt buộc cho ARG 1.3 / 5.1.1**
- `static/index.html:107`: Đã có 2 dòng: (a) FDA verbatim hardcoded EN (`app.js:584`); (b) “Not professional medical advice”.
- **Thêm vào UI chính (mỗi màn hình check/result):** Banner cố định, không thể tắt: *“This is reference information only — not a diagnosis or treatment plan. Consult a licensed physician or pharmacist. Interaction data may be incomplete. See full FDA disclaimer at bottom.”*
- Nếu có bản `vi`: thêm dòng nhỏ dưới banner EN: *“Bản dịch tiếng Việt chỉ mang tính tham khảo; văn bản pháp lý chính thức là tiếng Anh ở trên.”*
- **Không được** để chat response (tiếng Việt) thay thế disclaimer; `advisor.py:211` đã đúng nhưng cần đảm bảo luôn in cùng với verdict.

---

### Phase 2 — LANGUAGE / CONTENT / HEALTH CLAIMS (P0 song song) — 3-5 ngày

2.1. **Quyết định ngôn ngữ chính thức cho US App Store: EN**
- `i18n.js`: Giữ `vi` làm tùy chọn, nhưng **mặc định `en`** khi app khởi động trên thiết bị vùng US (`Locale.current.identifier` hoặc `Locale.preferredLanguages` trong native).
- Nếu user chọn `vi`: vẫn cho phép, nhưng **không cho phép `vi` là ngôn ngữ duy nhất cho health explanation** — phải có bản EN song song ở footer / disclaimer.
- Xóa hoặc hạn chế các thuật ngữ tiếng Việt có thể gây nhầm lẫn với thuật ngữ y tế Mỹ (ví dụ “các dấu hiệu cần đi khám ngay” có thể hiểu là “seek emergency care”, cần rõ ràng).

2.2. **Loại bỏ / làm rõ các cặp CYP-inferred cho public**
- `engine.py` + `db.py`: `review_queue` 289 cặp `trust=0.5`.
- **Hành động:** Trong app iOS, chỉ hiển thị các cặp đã được `Verify` (trust → 0.9) cho user thường; các cặp còn lại chỉ cho dược sĩ (Caregiver / Professional mode có xác thực). Nếu muốn hiển thị cho tất cả: phải thêm label rõ: *“Inferred from enzyme pathways — not directly documented; discuss with a pharmacist.”* (`i18n.js:63` đã có, nhưng cần highlight màu vàng/cảnh báo).

2.3. **Không tạo claim mới từ LLM**
- `advisor.py`: Policy đã đúng. Nhưng cần thêm bước kiểm tra sau polish: `if "treat" in polished.lower() or "cure" in polished.lower() or "diagnose" in polished.lower(): return deterministic`.
- Ngoài ra, không dùng LLM để trả lời câu hỏi sức khỏe chung (nếu user hỏi “What is diabetes?”) — chỉ trả lời dựa trên `product_context` đã quét.

---

### Phase 3 — BUILD iOS NATIVE / HYBRID (P1, song song Phase 2) — 2-3 tuần

Vì App Store không chấp nhận pure PWA (cần native binary), phải làm một trong hai:

**Option A (khuyên — ít rủi ro App Store nhất): React Native / Expo + Native Module cho camera/barcode + OCR**
- Giữ logic backend (`backend/app.py`) nhưng gọi qua HTTPS, **không lưu PHI server** (hoặc dùng end-to-end encrypt nếu cần sync).
- Native camera: dùng `react-native-camera` hoặc `expo-camera` + `expo-barcode-scanner`; OCR dùng Vision framework qua native bridge (thay Tesseract.js web để tránh tải JS nặng và đảm bảo privacy local).
- Subscription: dùng `react-native-iap` (StoreKit 2 wrapper).

**Option B: SwiftUI native wrapper quanh WebView**
- Chỉ dùng nếu muốn giữ nguyên `static/app.js`. Nhưng Apple từng từ chối các app WebView chỉ là “shell” nếu không có native feature (camera/OCR phải native). Nên tích hợp `AVCaptureSession` + `Vision VNRecognizeBarcodesRequest` + `VNRecognizeTextRequest` native, rồi truyền kết quả vào WebView.
- **Khuyên:** Option A cho tốc độ; Option B nếu muốn giữ web UI nguyên vẹn nhưng cần native camera/OCR.

3.1. **Yêu cầu kỹ thuật iOS cho App Store**
- **Target iOS**: ≥ 16 (để dùng StoreKit 2, Vision framework mới).
- **Camera / Barcode**: Phải hoạt động off-line (không bắt buộc mạng); nếu dùng backend lookup (`/api/lookup/{barcode}`), phải có offline fallback (local DB hoặc cache).
- **PWA / Service Worker**: Không cần trong native app; bỏ `sw.js` khỏi bundle iOS.
- **Icon / Manifest**: Cần `AppIcon` set cho iPhone/iPad; mô tả trong `Info.plist` phải rõ: *“Reference health information — not medical advice.”*

3.2. **Backend điều chỉnh cho App Store**
- Nếu giữ backend: phải chạy trên server **US / EU** có BAA (nếu xử lý PHI), HTTPS với cert hợp lệ (Let’s Encrypt), không dùng `dev_cert.pem`.
- Nếu chuyển local-only: backend chỉ cần cho seed dữ liệu (`db.py`) và lookup barcode (public, không chứa user meds). User cabinet hoàn toàn local.

---

### Phase 4 — SUBSCRIPTION (Apple IAP) — P1 song song

Dựa `README.md:16`: Freemium 5 scans/mo → Pro $19/mo → Caregiver $69/mo.

4.1. **Cấu hình StoreKit 2 trong App Store Connect**
- **Subscription Group**: “MedMatch Premium”
- **Products**:
  - `pro_monthly` — $19.99 / month (US) / tương đương EU
  - `caregiver_monthly` — $69.99 / month
  - `free` — không cần IAP, chỉ giới hạn 5 scan (local counter)
- **Giá**: Must match địa phương; không được “bait-and-switch” (giá quảng cáo khác giá thực).

4.2. **Luật ARG 3.1.1 / 3.1.2**
- **Description rõ ràng trong app và App Store**: *“Subscription unlocks unlimited scans, smart swaps, and caregiver profiles. Free tier: 5 scans/month. Auto-renewing until canceled.”*
- **Restore**: Phải có nút “Restore Purchases” (dùng `restoreCompletedTransactions`).
- **Cancel**: Hướng dẫn trong app (link đến Settings → Subscriptions hoặc hướng dẫn nội bộ).
- **Không khóa essential feature**: Nếu đã quảng cáo “Check interactions” là tính năng chính, không được khóa hoàn toàn sau 5 scan (phải cho xem kết quả cơ bản). Freemium hợp lý: giới hạn số lần quét, không giới hạn xem kết quả đã quét (hoặc cho xem 1-2 cặp cảnh báo chính).
- **Không dùng external payment link**: Không cho phép thanh toán qua Stripe/Web trong app (vi phạm ARG 3.1.3). Nếu muốn Web billing cho web users, phải có màn hình riêng cho iOS không có link thanh toán ngoài.

---

### Phase 5 — REVIEW PREPARATION (P2) — trước submit

5.1. **Nội dung phải có trong submit**
- **Demo video (Bắt buộc cho health app)**: Quay từ iPhone thật: (1) Mở app → (2) Chọn EN → (3) Scan barcode / nhập tay → (4) Xem kết quả với banner FDA + disclaimer → (5) Tap “Check” → (6) Chat advisor với câu hỏi về sản phẩm đã quét (không phải câu hỏi y tế chung) → (7) Nút “Print / Save PDF” → (8) Màn hình settings subscription.
- **Screenshots**: Ít nhất 1 screenshot có banner disclaimer rõ ràng (font đủ lớn); 1 screenshot ngôn ngữ EN; 1 screenshot subscription screen; 1 screenshot review queue (nếu có) có label “Inferred / Not verified by clinician”.
- **App Store Description** (dùng tiếng Anh cho US):
  - Mở đầu: *“MedMatch is a reference information tool for supplement and medication interactions. It is not a substitute for professional medical advice.”*
  - Giải thích dữ liệu: *“Data from FDA labels (DailyMed), NIH DSLD, SUPP.AI, and openFDA. No external tracking. Your cabinet stays private on your device.”*
  - Không dùng từ “diagnose”, “treat”, “cure”, “prevent disease” (tránh ARG 1.2 / 5.1).
- **Private Note cho reviewer** (không công khai):
  - *“Health reference app under enforcement discretion. All medical explanations are derived from structured databases (FDA, DailyMed, SUPP.AI) with verbatim disclaimers. Vietnamese language is optional translation only; primary regulatory text is English per 21 CFR § 101.93(c). No AI-generated medical claims (LLM only polishes existing engine output; Gemini disabled in this build).”*
  - *“Subscription requires Apple IAP; no external purchase links in app.”*

5.2. **Medical Expert Review (nên có)**
- Nếu App Store yêu cầu (thường không bắt buộc cho “reference info”, nhưng nếu app bị hold vì y tế): chuẩn bị thư từ dược sĩ / bác sĩ xác nhận: *“App provides reference interaction data, does not diagnose or prescribe, includes required FDA disclaimers.”*
- Thành viên trong team hoặc đối tác (`backend/scanner/router.py` có “pharmacist triage” cho review queue) có thể ký.

5.3. **TestFlight & Internal Testing**
- Test trên iPhone 15 Pro (US region), iOS 17+.
- Kiểm tra: camera barcode (AVFoundation), OCR nhãn (Vision), subscription purchase/restore, ngôn ngữ switch EN ↔ VI, offline mode, privacy (không có network request gửi meds nemesis).

---

## 3. Checklist Hành động (từng bước, có thể giao cho agent hoặc làm thủ công)

```markdown
- [ ] P0: Tắt GEMINI_API_KEY trong .env / Docker / build; thêm assert; sửa advisor.py:367
- [ ] P0: Xóa backend/data/devices/; thêm .gitignore; thay storage.py bằng local DB hoặc encrypt
- [ ] P0: Sửa app.py cookie (secure, max_age 30d); bỏ cookie nếu native iOS
- [ ] P0: Thêm banner FDA cố định trong static/app.js + native UI; thêm dòng “VI translation” nếu lang=vi
- [ ] P0: Kiểm tra db không có ddinter_interactions (đã OK); giữ backup nhưng không load
- [ ] P1: Quyết định native framework (React Native / SwiftUI); bắt đầu build
- [ ] P1: Tích hợp native camera + Vision barcode/OCR; bỏ Tesseract web-only phụ thuộc
- [ ] P1: Thêm StoreKit 2 subscription group (pro_monthly, caregiver_monthly) trong App Store Connect
- [ ] P1: Implement IAP restore + description rõ; không khóa essential feature hoàn toàn
- [ ] P1: Sửa review queue hiển thị: thêm “Not verified by clinician” cho trust=0.5
- [ ] P2: Quay demo video, chụp screenshot với disclaimer; viết App Store description EN
- [ ] P2: Submit TestFlight → Internal Test → App Store Review (đi kèm Private Note y tế)
```

---

## 4. Câu hỏi cần confirm từ bạn (doi nguoi chot)

Trước khi bắt build, cần quyết:

1. **Native hay WebView wrapper?** (Nếu WebView → cần native camera/OCR bridge; nếu React Native → nhiều code mới)
2. **Giữ backend server không?** (Nếu có → cần BAA/HIPAA; nếu không → cabinet local, chỉ lookup barcode công khai)
3. **Subscription giá chính xác (US):** Pro $19/mo, Caregiver $69/mo đúng chưa? Có free tier 5 scan/mo không?
4. **Tiếng Việt:** Giữ làm tùy chọn hay bỏ cho MVP US? (Khuyên giữ nhưng bật default EN + banner)
5. **Có sẵn dược sĩ ký thư review không?** (Nếu không → cần tìm hoặc tự ký với disclaimer đủ mạnh)

---

*Document tạo từ review code: `medmatch/backend/app.py`, `scanner/advisor.py`, `router.py`, `db.py`, `static/index.html`, `README.md`.*

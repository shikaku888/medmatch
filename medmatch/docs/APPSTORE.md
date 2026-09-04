# Lộ trình đưa MedMatch lên App Store (iOS) — chạybook từng bước

> Nguyên tắc bất di bất dịch: engine y tế (SQLite 298MB) chạy trên **server của bạn**;
> app iOS là lớp vỏ native (Capacitor) trỏ về server. Mọi bước dưới đây đã được
> chuẩn bị sẵn file/config — bạn chỉ làm các việc đánh dấu **[BẠN]**.

## Giai đoạn 0 — Việc chỉ bạn làm được (song song được)

| # | Việc | Chi phí | Thời gian |
|---|---|---|---|
| 1 | Đăng ký **Apple Developer Program**: https://developer.apple.com/programs → enrolled với Apple ID cá nhân | 99 USD/năm | Duyệt 24-48h |
| 2 | Thuê VPS (Ubuntu 22.04, 2GB RAM là đủ) + trỏ 1 domain về IP đó | ~5 USD/tháng | 30 phút |
| 3 | Sau khi được duyệt dev: App Store Connect → Users and Access → **Integrations** → tạo App Store Connect API key (Admin, lưu file `.p8`) | 0 | 10 phút |

## Giai đoạn 1 — Triển khai server (tôi config sẵn, bạn chạy 4 lệnh)

Trên VPS, trong thư mục project:

```bash
# 1. Copy toàn bộ H:\aisuckhoe\medmatch lên VPS (scp/rsync hoặc git)
# 2. Cài + chạy bằng Caddy (tự cấp HTTPS Let's Encrypt — hết cảnh báo cert)
sudo apt install -y caddy python3-venv
cd medmatch && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# 3. Systemd (file mẫu: deploy/medmatch.service — sửa đường dẫn rồi copy)
sudo cp deploy/medmatch.service /etc/systemd/system/ && sudo systemctl enable --now medmatch
# 4. Caddyfile (deploy/Caddyfile — sửa domain)
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile && sudo systemctl reload caddy
```

Kiểm tra: `https://<domain>/scanner/` mở được, `/api/health` → `{"status":"ok"}`.

## Giai đoạn 2 — Kho code + CI build iOS (0 USD, không cần Mac)

1. **[BẠN]** Tạo GitHub repo **public**, push project scanner
   (`H:\aisuckhoe\personalized-product-scanner` — đã có sẵn `.github/workflows/ios-release.yml`).
2. **[BẠN]** Repo → Settings → Secrets → Actions, thêm 4 secret:
   `APPSTORE_ISSUER_ID`, `APPSTORE_KEY_ID`, `APPSTORE_P8_B64` (base64 file .p8), `TEAM_ID`.
3. Repo → Settings → Variables → Actions, thêm `SCANNER_URL`, ví dụ
   `https://scanner.example.com/scanner/`. CI sẽ ghi URL này vào
   `capacitor.config.json` trước khi validate và build.
4. Gắn tag `ios-v1` → Actions build web, sinh project iOS, thêm camera
   permission, ký archive và upload **TestFlight**.
5. **[BẠN]** App Store Connect → My Apps → **+** → New App (Name, Bundle ID
   `vn.medmatch.scanner`, SKU bất kỳ) → iOS app xuất hiện trong TestFlight.
6. Test bằng app TestFlight trên iPhone (invite chính bạn).

## Giai đoạn 3 — Vật liệu review (tôi soạn sẵn mẫu, bạn duyệt)

- `docs/privacy-policy.md` — đưa lên `https://<domain>/privacy` (bắt buộc có URL).
- App Privacy labels: Device Identifier → App Functionality → *not linked to
  identity*. Health data: **collected by the scanner** (profile, medication,
  allergy, diet, routine and scan history), stored under a random device token;
  no account identity is required. This declaration must match the public
  privacy policy and actual retention behavior.
- App có nút **Export my data** và **Delete all data** trong Profile; kiểm tra
  cả hai trên TestFlight trước khi khai báo privacy.
- Screenshot: simulator iPhone 15/6.7" — chụp 5-6 màn (Scan, Kết quả Nutella, Swaps,
  Analytics, Receipt).
- Metadata: phụ đề "Kiểm tra tương tác thuốc & TPCN", từ khóa, mô tả (dùng nội dung README).
- Bản v1 không có billing/paywall/IAP; không hiển thị giá hoặc trial giả.
- Disclaimer FDA/EMC đã có sẵn ở footer app + màn kết quả — giữ nguyên khi review.

## Rủi ro đã được phòng

| Rủi ro Apple | Phòng |
|---|---|
| Guideline 4.2 "webview trống trơn" | Splash native + safe-area + camera WKWebView + tabs riêng trong header + bản cập nhật nội dung native bundle khi offline |
| Guideline 1.4 y tế | Vị trí "thông tin tham khảo", không chẩn đoán/kê liều, disclaimer FDA verbatim |
| Camera permission thiếu | `NSCameraUsageDescription` do Capacitor sinh — đã khai báo mục đích trong bước sync |


## R4/R5 release gate

Trước khi tạo tag `ios-v*` hoặc `android-v*`, phải có bằng chứng beta web đạt
R3: hit-rate ≥85%, crash-free 7 ngày, latency p50/p95 và refresh report có
checksum/lineage/rollback. Refresh runtime phải tạo cả:

```text
deploy/runtime/medmatch.db
deploy/runtime/medmatch.db.manifest.json
deploy/runtime/medmatch.db.evaluation.json
```

Docker/Fly bật `REQUIRE_R5_EVALUATION=1`; startup sẽ dừng nếu report thiếu,
sai fixture version hoặc có case fail. Không tạo tag nếu `SCANNER_URL` chưa là
HTTPS URL kết thúc bằng `/scanner/`.

R4 hiện không bật billing, paywall, affiliate hoặc account sync. Profile thuốc,
dị ứng, lab, routine và lịch sử thuộc device-scoped storage; App Privacy phải
khai báo đúng health data thực tế.
## Sau này muốn CH Play

Dùng chung server + thêm `.github/workflows/android.yml` (Capacitor android, máy này build
được trực tiếp). Nói tôi khi bạn sẵn sàng — ~1 phiên làm việc.

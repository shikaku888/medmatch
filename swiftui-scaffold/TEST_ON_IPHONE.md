# Test ngay trên iPhone — không cần Expo

## Cách nhanh (test UI + camera)
1. `cd H:\aisuckhoe\medmatch`
2. Chạy `start_https.bat` (tạo `dev_cert.pem` lần đầu nếu chưa)
3. iPhone cùng Wi-Fi → mở `https://<IP-PC>:8443/scanner/`
4. Chrome cảnh báo cert → Advanced → Proceed (chỉ lần 1)
5. Đã có PWA + camera barcode + OCR (Tesseract.js lazy) hoạt động

## Tại sao không cần Expo cho bước này
- Frontend thật: `personalized-product-scanner/dist-scanner/` (React, Vite)
- Đã tích hợp qua `medmatch/backend/app.py` `/scanner/`
- `capacitor.config.json` sẵn nếu sau này muốn native iOS (Capacitor) thay vì Expo

## Nếu muốn native App Store sau khi test ổn
- Mac + Xcode → `npx cap add ios` hoặc SwiftUI scaffold
- Không cần Expo; Capacitor giữ UI React hiện tại

# Android Build từ React SPA (Capacitor) — nhanh

Thư mục gốc: H:\aisuckhoe\personalized-product-scanner

## 1. Cài nền Android
cd personalized-product-scanner
npm install @capacitor/android
npx cap add android

## 2. Cập nhật capacitor.config.json (thêm android)
PUT >3:
  "android": {
    "packageName": "vn.medmatch.scanner",
    "backgroundColor": "#0f172a",
    "allowMixedContent": true,
    "permissions": ["CAMERA", "INTERNET"]
  }

## 3. Billing Android (thay StoreKit)
# Dùng @capacitor-community/purchases hoặc cordova-plugin-purchase
npm install @capacitor-community/purchases
# Cấu hình product IDs: pro_monthly / caregiver_monthly giống StoreKit
# Thay thế StoreKit restore bằng Google Play Billing restore

## 4. Đồng bộ & build
npx cap sync android
# Mở Android Studio (cần Mac hoặc Linux/Windows với Android Studio)
cd android && ./gradlew assembleDebug

## 5. Giải phóng từ Windows (nếu không có Mac)
# Android Studio trên Windows có thể build APK từ source Capacitor (không cần Mac)
# Nhưng App Store submit vẫn cần Mac; Google Play submit từ Windows được

## 6. Lưu ý pháp lý cho Android
- FDA disclaimer phải có trên UI React (đã có trong static/index.html + i18n)
- Không claim dược sĩ (đã sửa)
- Không dùng DDInter/NC data trong build (đã gỡ)
- App Privacy Android: không tracking; localStorage chỉ local

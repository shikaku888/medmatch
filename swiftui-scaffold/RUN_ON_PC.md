# Chạy SwiftUI trên PC (không có Mac)

## Không thể trực tiếp
SwiftUI + StoreKit + AVFoundation chỉ compile được trên macOS + Xcode. Windows không chạy `.swift` iOS native.

## Cách thực tế

### 1. Thuê Mac cloud (nhanh nhất cho test/submission)
- MacStadium / AWS EC2 Mac / Rent Mac mini (~$1-4/giờ)
- Kết nối SSH / VNC; cài Xcode; clone `swiftui-scaffold`; compile/test
- Đủ để build IPA, test Sim, upload TestFlight

### 2. Bạn bè / đồng nghiệp có Mac
- Copy `swiftui-scaffold/` sang Mac; mở `swiftui-scaffold/MedMatch/MedMatch.xcodeproj` (tạo từ scaffold)
- Chạy `swift build` + `xcodebuild` hoặc mở Xcode, compile ra simulator

### 3. Chỉ cần xem UI / layout (đã có)
- `swiftui-scaffold/DEMO_PREVIEW_V2.html` — layout sạch, có consent + cabinet + sub
- Sửa HTML để thử bố cục trước khi mất thời gian compile

### 4. Nếu muốn compile từ Windows (không SwiftUI)
- Chuyển sang **React Native** (Expo) hoặc **Flutter** → compile từ Windows qua Android/iOS build server
- Nhưng phải viết lại UI từ đầu; không dùng `swiftui-scaffold`

## Submit App Store bắt buộc Mac
- Archive → Transporter → App Store Connect cần macOS + Apple Developer ($99/năm)
- TestFlight cần device iOS thực + Apple ID

Khuyên: nếu chỉ validate layout + copy → dùng HTML preview + thuê Mac 2-3 giờ để compile/test trước khi submit.

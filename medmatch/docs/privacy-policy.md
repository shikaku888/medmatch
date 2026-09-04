# Privacy Policy — MedMatch AI

_Effective date: 2026-08-26_

**Short version:** We do not require your name, email, phone number, or an account.
That does **not** mean scanner data never leaves the device.

## What we store

- **In your browser/app:** an opaque random `mt_device` cookie that lets the
  scanner reconnect to the same device namespace. The cookie is valid for up
  to 365 days.
- **On our server, keyed by that token:** scanner profile and family-profile
  fields, medications, allergies, diet, routines, reminders, optional
  pharmacogenomic context, product lookup results, and scan history. These are
  health-related data even when no account is present.
- **Retention:** profile, family-profile, routine, reminder, pharmacogenomic
  context, and history data remain until you explicitly delete them. History is
  capped at 100 entries and the lookup cache at 200 entries. The current build
  has no automatic expiry for orphaned device files.
- Clearing browser storage or reinstalling the app removes your local token;
  it does not immediately delete the server-side file. Use the in-app delete
  action or the documented delete endpoint.

## What we do NOT do

- No accounts, emails, or phone numbers.
- No advertising SDKs or behavioral tracking.
- Limited operational coverage telemetry may retain a truncated product lookup
  key, hit/miss result, source, and timestamp for recognition-quality work.
  It does not include profile fields or a device identifier. The current log
  is capped at 10 MiB; the oldest events are discarded when it reaches the cap.
- We never sell health-related data.

## AI and third parties queried

- The public build uses a deterministic local advisor. Profile, medication, and
  allergy fields are not sent to an AI provider.
- Product lookup and scientific-reference queries may send a barcode, product
  name, ingredient text, or search term to the public service requested:
  Open Food Facts / Open Beauty Facts, USDA FoodData Central, NCBI
  PubMed/PubChem, NIH DailyMed, openFDA, or RxNorm.
- Label photos used for OCR are processed in memory and are not stored by
  MedMatch.

## Medical disclaimer

MedMatch provides reference information from public data (FDA, EMA/HMPC, NIH,
published literature). It is not medical advice, diagnosis, or treatment.
Always consult a licensed physician or pharmacist before changing any
medication routine. Interaction data may be incomplete.

## Deletion and export

- **Export:** `GET /api/data/export` returns the current device namespace.
- **Delete:** `DELETE /api/data` clears the device namespace.
- **Purge:** `POST /api/user-data/purge` clears the namespace and removes its
  per-device server file when possible.
- Deleting browser storage alone is not a server deletion request.

## Security

- The public deployment must enforce HTTPS. Local development may use HTTP.
- The server-side file is keyed by an opaque random `httponly` cookie, not by
  a name, email, or phone number.
- Hosting providers may retain standard infrastructure logs under their own
  policies. MedMatch does not write client IPs into the device database.

---

# Chính sách quyền riêng tư (tiếng Việt)

**Ngắn gọn:** Chúng tôi không yêu cầu tên, email, số điện thoại hay tài khoản.
Điều đó **không** có nghĩa dữ liệu scanner không bao giờ rời khỏi thiết bị.

## Chúng tôi lưu gì

- **Trên trình duyệt/app:** cookie `mt_device` ngẫu nhiên, không mang ý nghĩa
- **Trên server, gắn với token đó:** hồ sơ và hồ sơ gia đình, thuốc, dị ứng,
  chế độ ăn, routine, reminder, ngữ cảnh dược di truyền tùy chọn, kết quả tra
  cứu sản phẩm và lịch sử quét. Đây vẫn là dữ liệu liên quan sức khỏe dù không
  có tài khoản.
- **Thời hạn lưu:** profile, family profile, routine, reminder, ngữ cảnh dược di
  truyền và history được giữ đến khi bạn yêu cầu xóa. History tối đa 100 mục,
  cache tra cứu tối đa 200 mục. Bản hiện tại chưa tự động xóa file thiết bị mồ côi.
  xóa ngay file server. Hãy dùng nút xóa trong app hoặc endpoint bên dưới.

## Chúng tôi KHÔNG làm gì

- Không tài khoản, email hay số điện thoại.
- Không SDK quảng cáo hay theo dõi hành vi.
- Telemetry vận hành giới hạn có thể lưu key tra cứu sản phẩm đã cắt ngắn,
  kết quả hit/miss, source và thời điểm để cải thiện độ nhận diện. Không lưu
  profile và không lưu định danh thiết bị. Log hiện tại tối đa 10 MiB; event cũ
  bị loại khi chạm giới hạn.
- Không bán dữ liệu liên quan sức khỏe.

## AI và bên thứ ba được truy vấn

- Bản public dùng advisor deterministic chạy local. Profile, thuốc và dị ứng
  không được gửi tới AI provider.
- Truy vấn tra sản phẩm/tài liệu có thể gửi barcode, tên sản phẩm, text thành
  phần hoặc từ khóa tới dịch vụ public được yêu cầu: Open Food Facts /
  Open Beauty Facts, USDA FoodData Central, NCBI PubMed/PubChem, NIH DailyMed,
  openFDA hoặc RxNorm.
- Ảnh nhãn dùng cho OCR được xử lý trong bộ nhớ và MedMatch không lưu ảnh.

## Tuyên bố miễn trừ y tế

MedMatch cung cấp thông tin tham khảo từ dữ liệu công khai (FDA, EMA/HMPC,
NIH, tài liệu khoa học). Không phải tư vấn y tế, chẩn đoán hay điều trị.
Luôn tham vấn bác sĩ/dược sĩ có chứng chỉ trước khi thay đổi phác đồ thuốc.
Dữ liệu tương tác có thể chưa đầy đủ.

## Xóa và xuất dữ liệu

- **Xuất:** `GET /api/data/export` trả về namespace của thiết bị hiện tại.
- **Xóa:** `DELETE /api/data` xóa namespace của thiết bị hiện tại.
- **Purge:** `POST /api/user-data/purge` xóa namespace và cố gắng xóa file
  server riêng của thiết bị.
- Chỉ xóa storage trình duyệt không phải là yêu cầu xóa dữ liệu server.

## Bảo mật

- Bản public phải bắt buộc HTTPS. Local development có thể dùng HTTP.
- File server được định danh bằng cookie `httponly` ngẫu nhiên, không phải tên,
  email hay số điện thoại.
- Nhà cung cấp hosting có thể lưu log hạ tầng tiêu chuẩn theo chính sách riêng.
  MedMatch không ghi IP client vào device database.

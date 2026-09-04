# Vận hành thực tế — sau khi build iOS (A hoặc B)

## A. Backend / Data (stateless lookup — không PHI)
- API resilience: `backend/app.py` `/api/lookup/{barcode}` dùng Open Food Facts → cần timeout + fallback (UPCitemdb/EcomSource) + retry 1 lần; log lỗi không chứa meds.
- Rate limit: Open Food Facts ~100 req/phút; nếu nhiều user cùng lúc → throttling cần queue hoặc cache (đã có lookup_cache.db).
- Data refresh: `python -m backend.suppai --crawl-all` (~1h) + `backend.unify` định kỳ; cần cron/job tự động, không manual.
- Không thêm API có phí trừ khi cần (MeđData $29/mo chỉ nếu muốn cao cấp hơn open data).

## B. Logic vận hành cần sửa khi chạy thực
1. Engine `interactions` trả `evidence` list; SwiftUI cần hiển thị DOI/PMID + `is_inferred` (CYP 0.5) rõ ràng.
2. `schedule` (tách giờ uống): cần tính min_hours giữa các cặp; nếu user chọn giờ khác nhau → hiển thị ghi chú "tách giờ giảm rủi ro".
3. `unmatched` (không nhận diện): phải cho phép user thêm thủ công + tìm kiếm `idisk` / `rxnorm` — không bỏ qua.
4. `depletions` (thuốc làm cạn dinh dưỡng): cần nguồn (Verified Supplement Evidence MIT) luôn hiển thị source.
5. `review_queue`: do không có dược sĩ ký → mọi cặp CYP-inferred (trust 0.5) phải có label màu vàng + không cho là "đã duyệt".
6. `ai_chat` (`ask_medmatch_advisor`): đã tắt Gemini; cần đảm bảo `question` không vượt 300 ký tự; sanitize; không trả lời ngoài product_context.

## C. iOS / SwiftUI vận hành
- `ConsentModal`: chỉ hiện lần đầu; lưu `@AppStorage`; không lặp lại sau restore.
- `BarcodeScanner`: AVFoundation + Vision; không dùng Tesseract.js web (chậm, cần mạng). Nếu cần OCR nhãn → tích hợp Tesseract native hoặc Vision text (đủ cho nhãn tiếng Anh/Latin).
- `StoreKit`: cần kiểm tra receipt server-side (Apple đề xuất) — thêm endpoint nhẹ `/api/storekit/validate` nhận receipt từ device, trả `is_active`; không cần lưu meds.
- `SwiftData`: cần thêm migration nếu schema đổi (thêm `InteractionRow` index); backup tự động qua iCloud (optional) hoặc export PDF.
- `Offline`: lookup barcode cần cache kết quả ~24h (SQLite local hoặc UserDefaults); nếu không có mạng vẫn xem cabinet đã quét.

## D. Bảo mật / Pháp lý thực tế
- HTTPS: thay `dev_cert.pem` bằng cert thực (Let's Encrypt / ACM) trước publish — hiện tại tự ký chỉ cho test nội bộ.
- Không đồng bộ meds lên server: `localStorage`/`SwiftData` chỉ local; nếu sau này cần đồng bộ → encrypt AES-256 + BAA trước (theo plan1).
- App Privacy: khai báo đúng (Health, Usage, No tracking, No third-party sharing sau khi tắt Gemini).
- FDA disclaimer: phải có trên mọi màn kết quả; không thể bỏ chỉ vì "đã đồng ý lần đầu".

## E. Nghiên cứu API / dữ liệu bổ sung (tùy chọn, không bắt buộc cho MVP)
- `SUPP.AI` crawl (đã có `suppai.py`); crawl định kỳ để cập nhật 59K tương tác + DOI.
- `NIH DSLD` / `iDISK` (đã có `idisk.py`, `dsld.py`); import sản phẩm + tương tác nếu muốn mở rộng sản phẩm.
- `Open Food Facts` + `PubChem`: đã dùng cho barcode lookup miễn phí.
- `DailyMed` parse (đã có `dailymed.py`); cập nhật nhãn FDA định kỳ.
- `FAERS` (openFDA): precompute counts cho từng drug (đã có `faers.py`).
- Không thêm DDInter / Kaggle (NC-SA / NC) vào build thương mại.

## F. Giao diện / UX vận hành
- Feedback từ test iPhone (`start_https.bat`) → điều chỉnh bố cục; không cần sửa backend nếu UI đúng.
- Video demo: quay từ iPhone thật (không phải simulator) cho App Store; nói rõ "reference information, not medical advice".
- Screenshot: chụp từng màn (Scan, Check result với badge FDA, Subscription, Consent) — cần banner FDA rõ trên màn kết quả.

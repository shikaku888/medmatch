# 📋 Kế Hoạch Xây Dựng MedMatch AI

**Phiên bản:** 1.0 | **Ngày:** 2026-08-25 | **Trạng thái:** Sẵn sàng triển khai

---

## 🎯 Tổng Quan Chiến Lược: "70-20-10"

Xây dựng cơ sở dữ liệu và ứng dụng theo nguyên tắc:

| Tỷ lệ | Lớp dữ liệu | Mô tả |
|--------|-------------|-------|
| **70%** | Nguồn hoàn toàn tự do | FDA DailyMed, openFDA, NIH DSLD/ODS, RxNorm, PubChem, SUPP.AI, iDISK 2.0, OnSIDES, BotanicaAndina (CC-BY-SA) → làm nền tảng chính, hiển thị trực tiếp cho người dùng |
| **20%** | Nguồn kiểm chứng bổ sung | Các nguồn có hạn chế license → chỉ dùng để kiểm chứng chéo dữ liệu, phát hiện tín hiệu mới, không hiển thị trực tiếp |
| **10%** | Giá trị riêng độc đáo | Logic suy luận CYP450, tính năng "thuốc làm cạn kiệt dinh dưỡng", kiểm chứng thủ công bởi dược sĩ, UX trải nghiệm tốt → điểm thắng đối thủ không thể sao chép |

**Mục tiêu:** Không cạnh tranh bằng "nhiều dữ liệu nhất" — cạnh tranh bằng "đáng tin cậy nhất + hữu ích nhất".

---

## 🗺️ Roadmap Tổng Thể Theo Giai Đoạn

### Giai đoạn A: Nền Tảng Dữ Liệu Cốt Lõi (Tuần 1-4)
*Ưu tiên CAO NHẤT — đủ để ra MVP mạnh mẽ*

| Tuần | Công việc | Nguồn dữ liệu | Kết quả mong đợi |
|------|----------|---------------|-----------------|
| **1** | Crawl SUPP.AI | supp.ai API | ~59,000 tương tác TPCN-thuốc, có evidence DOI |
| **1** | Import DDInter 2.0 | DDInter website download CSV | ~240,000 tương tác thuốc-thuốc, có mức độ nghiêm trọng & cơ chế |
| **2** | Import iDISK 2.0 | GitHub houyurain/iDISK2.0 | 174,000+ entities TPCN, từ đồng nghĩa, tương tác |
| **2** | Import tapirro herb-drug JSON | GitHub tapirro/herb-drug-interaction-checker | 592 tương tác thảo dược-thuốc có cấu trúc |
| **2-3** | Setup chuẩn hóa tên thuốc | RxNorm API (NLM) | Map tên thuốc bất kỳ → RxCUI chuẩn quốc tế |
| **3** | Setup chuẩn hóa hóa chất | PubChem PUG REST API | Map tên TPCN → CAS Registry Number + PubChem CID |
| **3-4** | Xây dựng bảng hợp nhất cơ bản | Logic tự xây dựng | Bảng `interaction_unified` đã khử trùng lặp, có trọng số nguồn |

### Giai đoạn B: Làm Giàu & Bằng Chứng (Tuần 5-6)
*Tạo sự khác biệt & tăng độ tin cậy*

| Tuần | Công việc | Nguồn | Kết quả |
|------|----------|--------|---------|
| **5** | Import Verified Supplement Evidence DB | GitHub erinheit451/verified-supplement-evidence | 🏆 **Tính năng killer**: Thuốc nào làm cạn kiệt chất dinh dưỡng nào + gợi ý bổ sung |
| **5** | Import dữ liệu CYP450 enzyme | FDA CYP450 Table + SAHAYAK repo | Danh sách chất nền / chất ức chế / chất thúc đẩy theo enzyme |
| **5-6** | Xây dựng engine suy luận CYP450 | Logic tự xây dựng | Phát hiện ~50,000 cặp tương tác "ẩn" thông qua đường dẫn enzyme |
| **6** | Crawl DailyMed / openFDA FAERS | DailyMed bulk download + openFDA API | Làm nguồn bằng chứng: số báo cáo sự cố thực tế từ chính phủ |
| **6** | Import Kaggle Drug-Food Interactions | Kaggle dataset shayanhusain/drug-food-interactions-dataset | Tương tác thuốc ↔ thực phẩm & thảo dược phổ biến |
| **6** | Xây dựng hệ thống xếp hạng độ tin cậy | Logic tự xây dựng | Trọng số nguồn: FDA/NIH (1.0) > DDInter/SUPP.AI (0.9) > học thuật (0.7) > suy luận (0.5) |

### Giai đoạn C: Mở Rộng & Kiểm Chứng (Tuần 7-8)
*Tăng độ bao phủ & xác thực chất lượng*

| Tuần | Công việc | Nguồn | Kết quả |
|------|----------|--------|---------|
| **7** | Import BotanicaAndina | botanicaandina.com | 592 tương tác thảo dược có 5,049 tham chiếu PubMed |
| **7** | Import OnSIDES | GitHub tatonetti-lab/onsides | 3.6 triệu cặp thuốc-tác dụng phụ từ nhãn FDA |
| **7-8** | Kiểm chứng thủ công top 500 cặp phổ biến | Thuê dược sĩ trên Upwork/Fiverr | Đánh dấu "✓ Được dược sĩ kiểm chứng" → tăng độ tin cậy vượt trội |
| **8** | Tích hợp Barcode Lookup cascade | Open Food Facts → UPCitemdb → EcomSource.ai | Tra cứu sản phẩm từ mã vạch, hỗ trợ nhận diện sản phẩm mới |
| **8** | Xử lý OCR nhãn sản phẩm | ML Kit Text Recognition + parse logic | Trích xuất thành phần từ ảnh nhãn sản phẩm |

### Giai đoạn D: Tinh Chỉnh & Nâng Cấp (Tuần 9+)
*Tùy chọn, khi có người dùng & doanh thu*

| Công việc | Nguồn | Mục đích |
|----------|--------|----------|
| Import PrimeKG | Harvard Dataverse | Phân tích đường dẫn sinh học, giải thích cơ chế sâu hơn |
| Import TwoSIDES | nsides.io | Cảnh báo thống kê: "Dữ liệu FAERS ghi nhận X báo cáo khi kết hợp A+B" |
| Fine-tune PubMedBERT | SuppKG data | Dự đoán các tương tác mới chưa được ghi nhận |
| Tối ưu cache & hiệu năng | Redis / pgvector | Giảm thời gian phản hồi API |

---

## 🔄 Chi Tiết Bước Crawl SUPP.AI (Hiện Tại)

### Mục tiêu
Lấy toàn bộ dữ liệu tương tác TPCN-thuốc từ SUPP.AI (Allen Institute for AI, non-profit, miễn phí hoàn toàn).

### Quy trình thực hiện

**Bước 1: Lấy danh sách tất cả agents (TPCN + thuốc)**
- Gọi API `/agents` với phân trang (limit=100 mỗi trang)
- Lặp cho đến khi không còn dữ liệu
- Lưu thông tin cơ bản: id, name, type, description, synonyms, categories

**Bước 2: Lấy tương tác cho từng agent**
- Với mỗi agent, gọi API `/interactions/{agent_id}` với limit=200
- Trích xuất các trường: drug_id, drug_name, drug_type, severity, mechanism, summary, description, doi, pmid, num_evidence_sentences
- Chuẩn hóa mức độ nghiêm trọng về dạng thống nhất: major / moderate / mild

**Bước 3: Lưu vào database**
- Tạo 2 bảng riêng: `suppai_agent` và `suppai_interaction`
- Insert theo lô để tăng tốc độ
- Có cơ chế chống trùng lặp (unique constraint trên cặp agent_a_id + agent_b_id)

**Bước 4: Cơ chế Resume**
- Lưu danh sách các agent đã hoàn thành vào file
- Nếu bị gián đoạn giữa chừng, chạy lại script sẽ tiếp tục từ vị trí dừng, không chạy lại từ đầu

**Bước 5: Import vào bảng tổng hợp**
- Sau khi crawl xong, import dữ liệu từ `suppai_interaction` vào `interaction_raw` với `source='suppai'`, `confidence=0.90`

### Thông số kỹ thuật
- **Sleep giữa các request**: 0.2-0.3 giây (tôn trọng server)
- **Ước tính thời gian**: 15-20 phút
- **Tổng số request**: ~4,000 (2,044 lấy danh sách + 2,044 lấy tương tác)
- **Kích thước dữ liệu**: ~50-80MB JSON

### Lưu ý
- SUPP.AI không yêu cầu API key
- Mỗi tương tác có DOI/PMID → đây là điểm mạnh, hiển thị cho người dùng thấy bằng chứng khoa học
- Dữ liệu từ tổ chức non-profit, mục đích nghiên cứu → sử dụng hợp lý

---

## ➡️ Các Bước Tiếp Theo Sau SUPP.AI — Thứ Tự Ưu Tiên

### Bước 2: Import DDInter 2.0
- Tải 8 file CSV từ trang chủ DDInter (theo phân loại ATC)
- Import vào bảng staging riêng
- Chuẩn hóa tên thuốc qua RxNorm
- Import vào `interaction_raw` với `source='ddinter'`, `confidence=0.90`
- ⚠️ Lưu ý license CC BY-NC-SA: dùng cho giai đoạn MVP, sau này bổ sung nguồn khác làm chính

### Bước 3: Import iDISK 2.0
- Clone repo GitHub `houyurain/iDISK2.0`
- Import các file CSV chính:
  - `ingredient.csv`: Thành phần hoạt động + đồng nghĩa
  - `interaction.csv`: Tương tác TPCN-thuốc
  - `dsp.csv`: Thông tin sản phẩm TPCN
  - `disease.csv`: Bệnh lý liên quan
- iDISK đặc biệt giá trị cho **từ đồng nghĩa TPCN** → dùng để xây dựng bảng ánh xạ tên

### Bước 4: Xây dựng lớp chuẩn hóa tên
**Đây là bước quan trọng nhất để hợp nhất dữ liệu từ nhiều nguồn:**

**Đối với thuốc:**
- Gọi RxNorm API với tên gốc → lấy RxCUI
- Lưu mapping: tên gốc → RxCUI → tên chuẩn
- Thêm các tên thông dụng từ RxTerms API

**Đối với TPCN:**
- Ưu tiên ánh xạ từ iDISK trước
- Sau đó tra cứu PubChem PUG REST → lấy CAS + CID
- Tự xây dựng từ điển đồng nghĩa cho những tên phổ biến không có trong nguồn chính thức (VD: Vitamin C = Ascorbic Acid, Omega-3 = EPA/DHA)

**Kết quả:** Bảng `standard_ingredient` (mỗi thành phần 1 dòng duy nhất) + bảng `ingredient_synonym` (mọi tên gọi khác đều map về chuẩn)

### Bước 5: Hợp nhất dữ liệu vào bảng chung
- Với mỗi bản ghi trong `interaction_raw`, ánh xạ 2 thành phần về `standard_id`
- Sắp xếp thứ tự nhất quán (id_a < id_b) để tránh trùng lặp đảo ngược
- Nếu cùng cặp xuất hiện từ nhiều nguồn:
  - Giữ mức độ nghiêm trọng **cao nhất** (ưu tiên an toàn)
  - Giữ cơ chế từ nguồn có **độ tin cậy cao nhất**
  - Gộp tất cả các nguồn vào mảng `evidence_sources`
  - Tăng `evidence_count` tương ứng
  - `confidence_score` = giá trị cao nhất trong các nguồn
- Nếu là suy luận từ CYP450 → đánh dấu `is_inferred = TRUE`, `confidence = 0.50`

### Bước 6: Tính năng "Thuốc làm cạn kiệt dinh dưỡng" 🏆
- Tải repo GitHub `erinheit451/verified-supplement-evidence`
- Import file `medication-depletion-v1.csv`
- Dữ liệu bao gồm: Thuốc A → làm cạn kiệt chất dinh dưỡng B → mức độ → gợi ý liều bổ sung
- **Đây là tính năng bán hàng mạnh nhất**: không chỉ cảnh báo "xấu" mà còn gợi ý "giải pháp"

### Bước 7: Engine suy luận CYP450
- Import dữ liệu từ FDA CYP450 Table: chất nền / chất ức chế mạnh-trung bình-yếu / chất thúc đẩy theo từng enzyme (CYP1A2, CYP2C9, CYP2C19, CYP2D6, CYP3A4...)
- Logic suy luận:
  - Nếu A là chất nền của enzyme X, VÀ B là chất ức chế mạnh enzyme X → suy ra tương tác mức **major**
  - Nếu A là chất nền của enzyme X, VÀ B là chất ức chế trung bình enzyme X → suy ra tương tác mức **moderate**
  - Nếu A là chất nền của enzyme X, VÀ B là chất thúc đẩy enzyme X → suy ra tương tác mức **moderate** (giảm nồng độ thuốc)
- Luôn hiển thị rõ: "Dựa trên cơ chế chuyển hóa enzyme, chưa có báo cáo lâm sàng trực tiếp"

---

## ✅ Checklist Tiến Độ

### Dữ liệu & Backend

| Bước | Trạng thái | Ghi chú |
|---|---|---|
| 📋 Thiết kế kiến trúc 4 lớp dữ liệu | ✅ Hoàn thành | |
| 📋 Thiết kế cấu trúc bảng database | ✅ Hoàn thành | |
| 📋 Lập danh sách đầy đủ nguồn dữ liệu | ✅ Hoàn thành | |
| 🔄 Crawl SUPP.AI | 🔄 **Đang thực hiện** | Bước hiện tại của bạn |
| ⬜ Import DDInter 2.0 CSV | ⏳ Tiếp theo | |
| ⬜ Import iDISK 2.0 | ⏳ | |
| ⬜ Import tapirro herb-drug JSON | ⏳ | |
| ⬜ Setup RxNorm chuẩn hóa tên thuốc | ⏳ | Quan trọng nhất cho hợp nhất |
| ⬜ Setup PubChem chuẩn hóa hóa chất | ⏳ | |
| ⬜ Xây dựng bảng standard_ingredient + synonym | ⏳ | |
| ⬜ Logic hợp nhất & khử trùng lặp | ⏳ | |
| ⬜ Import Verified Supplement Evidence DB | ⏳ | 🏆 Tính năng killer |
| ⬜ Import CYP450 + xây dựng suy luận engine | ⏳ | Tính năng độc đáo |
| ⬜ Import DailyMed / FAERS làm bằng chứng | ⏳ | |
| ⬜ Import Kaggle Drug-Food | ⏳ | |
| ⬜ Kiểm chứng thủ công top 500 cặp | ⏳ | Tăng độ tin cậy vượt trội |
| ⬜ Tích hợp Barcode Lookup APIs | ⏳ | |
| ⬜ OCR nhãn sản phẩm + parse thành phần | ⏳ | |

### App Di Động

| Bước | Trạng thái |
|---|---|
| 📱 Khởi tạo project | 🔄 Đang thực hiện |
| 📱 Cơ sở dữ liệu cục bộ SQLite | ⏳ |
| 📱 Tìm kiếm FTS5 thành phần | ⏳ |
| 📱 Màn hình chọn nhiều thành phần | ⏳ |
| 📱 Gọi API backend kiểm tra tương tác | ⏳ |
| 📱 Hiển thị kết quả theo mức độ nguy hiểm | ⏳ |
| 📱 Tích hợp ML Kit Barcode Scanning | ⏳ |
| 📱 Tích hợp ML Kit Text Recognition (OCR) | ⏳ |
| 📱 Lịch sử tra cứu | ⏳ |
| 📱 Đồng bộ dữ liệu tham chiếu định kỳ | ⏳ |

---

## ⚠️ Lưu Ý Quan Trọng

### Pháp lý & Đạo đức
- **Nguồn an toàn dùng trực tiếp**: SUPP.AI, RxNorm, PubChem, DailyMed, openFDA, NIH DSLD/ODS, WHO ATC, EMA public data → không có vấn đề license
- **Nguồn cần thận trọng**: DDInter (CC BY-NC-SA — dùng cho MVP, sau này chuyển nguồn chính sang DailyMed parse), BotanicaAndina (CC-BY-SA — cần ghi nguồn nếu phân phối lại)
- **Nguyên tắc vàng**: Khi có 2 nguồn mâu thuẫn → lấy nguồn có độ tin cậy cao hơn, và ưu tiên mức độ nghiêm trọng cao hơn để an toàn người dùng
- **Disclaimer bắt buộc**: Mọi màn hình kết quả phải có tuyên bố rõ ràng: "Thông tin này chỉ mang tính tham khảo, không thay thế tư vấn bác sĩ/dược sĩ"

### Kỹ thuật dữ liệu
- **Luôn giữ nguồn gốc**: Mỗi bản ghi phải có cột `source` rõ ràng
- **Không bao giờ gọi dữ liệu suy luận là "sự thật"**: Luôn ghi rõ "Dựa trên cơ chế chuyển hóa enzyme" hoặc "Dự đoán từ mô hình AI"
- **Kiểm chứng thủ công là đầu tư tốt nhất**: $50-150 thuê dược sĩ kiểm chứng top 500 cặp phổ biến → tạo ra sự khác biệt về độ tin cậy mà đối thủ khó cạnh tranh
- **Dữ liệu không tự động đúng**: Ngay cả nguồn chính phủ cũng có thể lỗi thời. Quy trình cập nhật định kỳ hàng tháng là cần thiết

### Chiến lược kinh doanh
- **Điểm thắng không phải dữ liệu nhiều nhất**: Người dùng sức khỏe cần "đáng tin cậy nhất", không phải "nhiều nhất"
- **Tính năng bán hàng thực sự**:
  1. "Thuốc bạn đang uống làm cạn kiệt CoQ10 → gợi ý bổ sung"
  2. "✓ Được dược sĩ kiểm chứng"
  3. Giải thích đơn giản, dễ hiểu, không dùng thuật ngữ y khoa phức tạp
- **App trả phí thắng không chỉ vì dữ liệu**: Họ thắng vì đội ngũ dược sĩ cập nhật liên tục, hỗ trợ khách hàng, và thương hiệu đã xây dựng lâu năm. Bạn có thể thắng ở trải nghiệm người dùng tốt hơn và giá cả hợp lý hơn.

---

## 📚 Nguồn Dữ Liệu Tham Khảo Nhanh

| Nhóm | Nguồn | Link | License | Ưu tiên |
|------|--------|------|---------|--------|
| **TPCN-thuốc** | SUPP.AI | supp.ai/api | Miễn phí (non-profit) | ⭐⭐⭐⭐⭐ |
| **TPCN-thuốc** | iDISK 2.0 | github.com/houyurain/iDISK2.0 | Miễn phí nghiên cứu | ⭐⭐⭐⭐⭐ |
| **Thuốc-thuốc** | DDInter 2.0 | ddinter2.scbdd.com/download | CC BY-NC-SA | ⭐⭐⭐⭐⭐ |
| **Chuẩn hóa thuốc** | RxNorm API | rxnav.nlm.nih.gov/REST | Miễn phí | ⭐⭐⭐⭐⭐ |
| **Chuẩn hóa hóa chất** | PubChem PUG REST | pubchem.ncbi.nlm.nih.gov/rest/pug | Miễn phí | ⭐⭐⭐⭐⭐ |
| **Bằng chứng** | DailyMed Bulk | dailymed.nlm.nih.gov | Miền công cộng | ⭐⭐⭐⭐⭐ |
| **Bằng chứng** | openFDA FAERS | api.fda.gov/drug/event | Miền công cộng | ⭐⭐⭐⭐⭐ |
| **Tính năng killer** | Verified Supplement Evidence | github.com/erinheit451/verified-supplement-evidence | Miễn phí | ⭐⭐⭐⭐⭐ |
| **CYP450** | FDA Table | fda.gov/drugs/drug-interactions-labeling | Miễn phí | ⭐⭐⭐⭐⭐ |
| **Thảo dược** | BotanicaAndina | botanicaandina.com | CC-BY-SA | ⭐⭐⭐⭐ |
| **Thảo dược** | tapirro JSON | github.com/tapirro/herb-drug-interaction-checker | MIT | ⭐⭐⭐⭐ |
| **Tác dụng phụ** | OnSIDES | github.com/tatonetti-lab/onsides | Miễn phí | ⭐⭐⭐⭐ |
| **Thuốc-thực phẩm** | Kaggle Dataset | kaggle.com/datasets/shayanhusain/drug-food-interactions-dataset | Miễn phí | ⭐⭐⭐⭐ |
| **Barcode lookup** | Open Food Facts | world.openfoodfacts.org/api/v2 | Miễn phí, không giới hạn | ⭐⭐⭐⭐ |
| **Barcode lookup** | UPCitemdb | api.upcitemdb.com/prod/trial | 100/ngày free | ⭐⭐⭐ |

---

*Tài liệu này được thiết kế để AI code có thể đọc hiểu và triển khai. Mỗi bước đã mô tả rõ mục đích, nguồn dữ liệu và kết quả mong đợi — không cần hướng dẫn code chi tiết.*

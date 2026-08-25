# 📋 Kế Hoạch Xây Dựng MedMatch AI

**Phiên bản:** 2.0 (Củng cố 20% & 10%) | **Ngày:** 2026-08-25 | **Trạng thái:** Sẵn sàng triển khai

---

## 🎯 Tổng Quan Chiến Lược: "70-20-10" Được Củng CỐ MẠNH

Xây dựng cơ sở dữ liệu và ứng dụng theo nguyên tắc:

| Tỷ lệ | Lớp dữ liệu | Mô tả chi tiết |
|--------|-------------|----------------|
| **70%** | Nguồn hoàn toàn tự do | FDA DailyMed, openFDA, NIH DSLD/ODS, RxNorm, PubChem, SUPP.AI, iDISK 2.0, OnSIDES, BotanicaAndina (CC-BY-SA) → làm nền tảng chính, hiển thị trực tiếp cho người dùng |
| **20%** | Nguồn kiểm chứng chéo & tín hiệu bổ sung | **medgraph Cascade Analysis**, SAHAYAK enzyme mapping, CredibleMeds QT list, CPIC/DPWG pharmacogenomics guidelines, Beers Criteria → dùng để kiểm chứng dữ liệu nền, phát hiện tín hiệu nguy cơ mới, **không hiển thị trực tiếp** mà **tổng hợp thành tính năng độc đáo** |
| **10%** | Giá trị riêng độc đáo — **7 tính năng không ai có** | ① Cascade Analysis Engine ② Medication Schedule Optimizer ③ QT Prolongation Risk Assessment ④ Electrolyte Depletion Warnings ⑤ Evidence Grading System (GRADE) ⑥ Beers Criteria Checker ⑦ Tính năng "thuốc làm cạn kiệt dinh dưỡng" + kiểm chứng thủ công bởi dược sĩ |

**Mục tiêu:** Không cạnh tranh bằng "nhiều dữ liệu nhất" — cạnh tranh bằng **"đáng tin cậy nhất + hữu ích nhất + thông minh nhất"**.

---

## 🔥 Phần 10% — 7 TÍNH NĂNG ĐỘC ĐÁO VƯỢT TRỌI

Đây là điểm bạn thực sự thắng đối thủ — không ai có thể sao chép dễ dàng:

### 🏆 Tính năng 1: Cascade Analysis Engine (từ HieuNTg/medgraph)
**Khác biệt:** Hầu hết app chỉ kiểm tra từng cặp A-B. MedGraph phát hiện **chuỗi tương tác qua nhiều bước enzyme**:

> "Ketoconazole ức chế CYP3A4 → Simvastatin là chất nền CYP3A4 → nồng độ Simvastatin tăng 10-20 lần → nguy cơ tiêu cơ vân"

Ngay cả khi không có tài liệu nào ghi trực tiếp cặp A-C, engine vẫn phát hiện nguy cơ thông qua trung gian enzyme.

**Cách triển khai:**
- Xây dựng knowledge graph: Thuốc → (inhibits/induces/substrate) → Enzyme → (substrate) → Thuốc khác
- Dùng NetworkX hoặc SQL truy vấn đa bước
- Hiển thị rõ: "⚠️ Phát hiện chuỗi nguy cơ qua đường dẫn enzyme CYP3A4"
- Nguồn dữ liệu: FDA CYP450 Table + DrugBank open subset + SAHAYAK repo (3,276 quan hệ enzyme-thuốc, 49 thảo dược-enzyme → 52,758 cặp tiềm ẩn)

### 🏆 Tính năng 2: Medication Schedule Optimizer (từ davide-beltrame/medication-schedule-optimizer)
**Khác biệt:** Không chỉ cảnh báo "có tương tác" mà còn **đưa ra giải pháp**:

> "ℹ️ Tương tác hấp thu giữa Levothyroxine và Calcium. **Giải pháp:** Uống Levothyroxine lúc 6:00 sáng (đói), Calcium lúc 14:00 chiều. Cách nhau 8 giờ để tránh tương tác."

Khoảng 20-30% tương tác có thể giải quyết bằng cách điều chỉnh thời gian uống.

**Logic:**
- Tương tác hấp thu: cách nhau 2-4 giờ
- Tương tác enzyme: không thể giải quyết bằng thời gian → cảnh báo cần tham khảo bác sĩ
- Quy tắc đặc biệt:
  - Levothyroxine: 30-60 phút trước bữa sáng, cách 4-6 giờ so với thuốc dạ dày
  - Bile acid sequestrants: thuốc khác uống 4 giờ trước hoặc sau
  - Antacid + kháng sinh: cách nhau 2-4 giờ
- Tạo 2-3 khung giờ cố định: 6h (đói), 8h (cùng bữa sáng), 14h (chiều), 20h (tối)

### 🏆 Tính năng 3: QT Prolongation Risk Assessment
**Khác biệt:** Đánh giá nguy cơ **rối loạn nhịp tim đe dọa tính mạng** khi kết hợp nhiều thuốc:

> "⚠️ Nguy cơ cao kéo dài khoảng QT: Bạn đang dùng Ciprofloxacin + Escitalopram + Hydrochlorothiazide. Cả 3 đều kéo dài QT, và HCTZ làm giảm Kali → tăng nguy cơ Torsades de Pointes."

**Dữ liệu:**
- CredibleMeds QTDrugs List (danh sách thuốc gây kéo dài QT)
- Tisdale Risk Score (đánh giá tổng hợp nhiều yếu tố)
- SAHAYAK repo: 279 thuốc gây kéo dài QT
- Các nhóm thuốc chính: kháng sinh macrolide/fluoroquinolone, thuốc chống loạn nhịp, thuốc chống loạn thần, thuốc chống trầm cảm SSRI, thuốc chống nôn

### 🏆 Tính năng 4: Electrolyte Depletion Warnings
**Khác biệt:** Phát hiện **chuỗi nguy cơ thứ cấp** qua điện giải:

> "⚠️ Furosemide (lợi tiểu) làm cạn kiệt Kali và Magie. Bạn cũng đang dùng Digoxin. Thiếu Kali làm tăng độc tính của Digoxin → nguy cơ rối loạn nhịp tim. Gợi ý: Theo dõi điện giải định kỳ."

**Dữ liệu:**
- Diuretics → thiếu Kali, Magie, Natri, Kẽm, CoQ10
- PPI (omeprazole...) → thiếu Magie → gây thiếu Kali thứ cấp → thiếu Canxi
- Cisplatin → thiếu Magie nặng, kéo dài nhiều năm
- Aminoglycoside antibiotics → thiếu Magie, Kali
- Mối liên kết: Thiếu Magie → thận không giữ được Kali → thiếu Kali → tăng độc tính Digoxin / tăng nguy cơ kéo dài QT

### 🏆 Tính năng 5: Evidence Grading System (GRADE)
**Khác biệt:** Không chỉ nói "có tương tác" mà còn nói **"chắc chắn đến đâu"**:

| Cấp độ bằng chứng | Mô tả | Hiển thị cho user |
|---|---|---|
| **Cao** | Nhiều RCT + meta-analysis nhất quán | "✅ Được chứng minh bằng nhiều nghiên cứu lâm sàng" |
| **Trung bình** | Nghiên cứu đơn lẻ hoặc có hạn chế | "ℹ️ Có bằng chứng từ nghiên cứu lâm sàng" |
| **Thấp** | Nghiên cứu quan sát, case report | "⚠️ Có báo cáo trường hợp, cần thêm bằng chứng" |
| **Rất thấp** | In vitro, suy luận enzyme, AI dự đoán | "🔬 Dựa trên cơ chế sinh học, chưa có báo cáo lâm sàng trực tiếp" |

**Logic tính điểm:**
- FDA/EMA nhãn chính thức → Cao
- SUPP.AI có DOI/PMID từ RCT → Cao
- DDInter có cơ chế rõ ràng → Trung bình
- FAERS thống kê → Thấp
- Suy luận CYP450 → Rất thấp
- Nhiều nguồn đồng thuận → nâng 1 cấp

### 🏆 Tính năng 6: Beers Criteria Checker
**Khác biệt:** Đánh giá thuốc **không phù hợp cho người cao tuổi** (≥65 tuổi):

> "⚠️ Theo tiêu chuẩn Beers 2023: Benzodiazepines (như Diazepam bạn đang dùng) không được khuyến nghị cho người trên 65 tuổi do tăng nguy cơ sa ngã, suy giảm nhận thức và phụ thuộc."

**Dữ liệu:**
- American Geriatrics Society Beers Criteria 2023
- SAHAYAK repo tích hợp Beers 2023
- Bao gồm: thuốc chống loạn thần cũ, benzodiazepines, thuốc kháng cholinergic, thuốc chống viêm không steroid liều cao...

### 🏆 Tính năng 7: Tính năng "Thuốc làm cạn kiệt dinh dưỡng" + Kiểm chứng thủ công
**Đã có trong kế hoạch cũ**, cần nhấn mạnh lại:
- Verified Supplement Evidence DB: Statins → CoQ10, Metformin → B12, PPIs → Magie...
- Top 500 cặp phổ biến nhất → thuê dược sĩ kiểm chứng thủ công → đánh dấu "✓ Được dược sĩ kiểm chứng"

---

## 🔬 Phần 20% — Nguồn Kiểm Chứng Chéo & Tín Hiệu Bổ Sung

Các nguồn này **không hiển thị trực tiếp** cho người dùng, mà dùng để:
1. ✅ Kiểm chứng lại dữ liệu từ 70% nền
2. 🔍 Phát hiện tín hiệu nguy cơ mới mà nguồn nền chưa có
3. 🧠 Cung cấp dữ liệu cho các tính năng độc đáo ở phần 10%

| Nguồn | Link | Cung cấp gì | Dùng cho tính năng nào |
|--------|------|-------------|------------------------|
| **HieuNTg/medgraph** | github.com/HieuNTg/medgraph | Cascade analysis framework, NetworkX graph engine, FastAPI backend | ① Cascade Analysis Engine |
| **SAHAYAK Project** | github.com/mohanganesh3/Sahayak | 3,276 enzyme-drug, 127 inhibitor edges, 49 herb-enzyme, 279 QT-prolonging drugs, 54 electrolyte effects, **52,758 cặp gián tiếp** | ① Cascade, ③ QT Risk, ④ Electrolyte |
| **CredibleMeds / QTMeds** | crediblemeds.org / qtmeds.com | 7,736 chất được phân tích về nguy cơ kéo dài QT, 13,861 thuốc trong DB | ③ QT Prolongation Risk |
| **CPIC Guidelines** | cpicpgx.org/guidelines | Khuyến nghị liều theo kiểu gen CYP2D6, CYP2C19 cho thuốc chống trầm cảm, chống đông, giảm đau... | Tương lai: Pharmacogenomics |
| **DPWG Guidelines** | (Dutch) | Tương tự CPIC, có khuyến nghị điều chỉnh liều cụ thể hơn | Tương lai: Pharmacogenomics |
| **Beers Criteria 2023** | American Geriatrics Society | Danh sách thuốc tránh cho người cao tuổi | ⑥ Beers Checker |
| **GRADE System** | (Chuẩn quốc tế) | Phương pháp xếp hạng bằng chứng y khoa | ⑤ Evidence Grading |
| **davide-beltrame/medication-schedule-optimizer** | github.com/davide-beltrame/medication-schedule-optimizer | Algorithm sắp xếp lịch uống thuốc | ② Schedule Optimizer |
| **Electrolyte depletion data** | PMC papers + Kitrus.ai data | Thuốc nào làm cạn kiệt Kali, Magie, Canxi, Natri | ④ Electrolyte Warnings |

---

## 🗺️ Roadmap Tổng Thể — Được Cập Nhật

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

### Giai đoạn B: Làm Giàu & Tính Năng Độc Đáo (Tuần 5-8)
*Tạo sự khác biệt thực sự — đây là điểm bạn thắng*

| Tuần | Công việc | Nguồn | Tính năng |
|------|----------|--------|-----------|
| **5** | Import Verified Supplement Evidence DB | GitHub erinheit451/verified-supplement-evidence | 🏆 **Tính năng 7**: Thuốc làm cạn kiệt dinh dưỡng |
| **5** | Import dữ liệu CYP450 enzyme | FDA Table + SAHAYAK repo | Nền tảng cho Tính năng 1 |
| **5-6** | Xây dựng engine suy luận CYP450 cơ bản | Logic tự xây dựng | Tương tác "ẩn" qua enzyme |
| **6** | Crawl DailyMed / openFDA FAERS | DailyMed bulk + openFDA API | Nguồn bằng chứng cho Tính năng 5 |
| **6** | Import Kaggle Drug-Food | Kaggle dataset | Tương tác thuốc ↔ thực phẩm |
| **6** | Xây dựng Evidence Grading System | GRADE standard | 🏆 **Tính năng 5**: Xếp hạng bằng chứng |
| **7** | Import BotanicaAndina | botanicaandina.com | 592 tương tác thảo dược |
| **7** | Import OnSIDES | GitHub tatonetti-lab/onsides | 3.6 triệu cặp thuốc-tác dụng phụ |
| **7-8** | Xây dựng Cascade Analysis Engine | medgraph framework + SAHAYAK data | 🏆 **Tính năng 1**: Phát hiện chuỗi nguy cơ |
| **8** | Xây dựng Medication Schedule Optimizer | davide-beltrame algorithm | 🏆 **Tính năng 2**: Tối ưu lịch uống thuốc |
| **8** | Import QT-prolonging drug list + electrolyte data | CredibleMeds + SAHAYAK + PMC papers | 🏆 **Tính năng 3 & 4**: QT Risk + Electrolyte |

### Giai đoạn C: Hoàn Thiện & Kiểm Chứng (Tuần 9-10)
*Tăng độ tin cậy & bao phủ*

| Tuần | Công việc | Nguồn | Kết quả |
|------|----------|--------|---------|
| **9** | Import Beers Criteria 2023 | AGS publication | 🏆 **Tính năng 6**: Kiểm tra thuốc cho người cao tuổi |
| **9** | Tích hợp Barcode Lookup cascade | Open Food Facts → UPCitemdb → EcomSource.ai | Tra cứu sản phẩm từ mã vạch |
| **9-10** | Kiểm chứng thủ công top 500 cặp phổ biến | Thuê dược sĩ trên Upwork/Fiverr | Đánh dấu "✓ Được dược sĩ kiểm chứng" |
| **10** | Xử lý OCR nhãn sản phẩm | ML Kit Text Recognition + parse logic | Trích xuất thành phần từ ảnh nhãn |
| **10** | Tích hợp tất cả 7 tính năng vào kết quả hiển thị | Logic tổng hợp | Kết quả hoàn chỉnh với nhiều lớp cảnh báo |

### Giai đoạn D: Tinh Chỉnh & Nâng Cấp Tương Lai (Tuần 11+)
*Khi có người dùng & doanh thu*

| Công việc | Mục đích |
|----------|----------|
| Import TwoSIDES | Cảnh báo thống kê FAERS: "X báo cáo thực tế khi kết hợp A+B" |
| Import PrimeKG | Phân tích đường dẫn sinh học sâu hơn |
| Tích hợp CPIC/DPWG guidelines | Tính năng tương lai: Người dùng nhập kết quả xét nghiệm gen → đánh giá cá nhân hóa |
| Fine-tune PubMedBERT | Dự đoán các tương tác mới chưa được ghi nhận |
| Tối ưu cache & hiệu năng | Giảm thời gian phản hồi API |

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

## ✅ Checklist Tiến Độ — Được Cập Nhật

### Dữ liệu & Backend

| Bước | Trạng thái | Ghi chú |
|---|---|---|
| 📋 Thiết kế kiến trúc 70-20-10 | ✅ Hoàn thành | Phiên bản 2.0 đã củng cố 20% & 10% |
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
| ⬜ Import Verified Supplement Evidence DB | ⏳ | 🏆 Tính năng 7 |
| ⬜ Import CYP450 + xây dựng suy luận engine | ⏳ | Nền tảng tính năng 1 |
| ⬜ Xây dựng Evidence Grading System (GRADE) | ⏳ | 🏆 Tính năng 5 |
| ⬜ Xây dựng Cascade Analysis Engine | ⏳ | 🏆 Tính năng 1 |
| ⬜ Xây dựng Medication Schedule Optimizer | ⏳ | 🏆 Tính năng 2 |
| ⬜ Import QT-prolonging + electrolyte data | ⏳ | 🏆 Tính năng 3 & 4 |
| ⬜ Import Beers Criteria 2023 | ⏳ | 🏆 Tính năng 6 |
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
- **Nguồn an toàn dùng trực tiếp (70%)**: SUPP.AI, RxNorm, PubChem, DailyMed, openFDA, NIH DSLD/ODS, WHO ATC, EMA public data → không có vấn đề license
- **Nguồn kiểm chứng (20%)**: medgraph, SAHAYAK, CredibleMeds, CPIC/DPWG, Beers Criteria → **không hiển thị trực tiếp**, chỉ dùng để tổng hợp thành tính năng độc đáo và kiểm chứng
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
- **7 tính năng bán hàng thực sự**:
  1. "🔍 Phát hiện chuỗi nguy cơ qua đường dẫn enzyme mà các app khác bỏ lỡ"
  2. "📅 Không chỉ cảnh báo — còn gợi ý lịch uống thuốc để tránh tương tác"
  3. "❤️ Đánh giá nguy cơ rối loạn nhịp tim khi kết hợp nhiều thuốc"
  4. "⚡ Cảnh báo thiếu hụt điện giải và nguy cơ thứ cấp"
  5. "📊 Mỗi cảnh báo đều có xếp hạng mức độ bằng chứng rõ ràng"
  6. "👴 Kiểm tra thuốc phù hợp cho người cao tuổi theo tiêu chuẩn quốc tế"
  7. "💊 Thuốc bạn đang uống làm cạn kiệt CoQ10 → gợi ý bổ sung"
- **App trả phí thắng không chỉ vì dữ liệu**: Họ thắng vì đội ngũ dược sĩ cập nhật liên tục, hỗ trợ khách hàng, và thương hiệu đã xây dựng lâu năm. Bạn có thể thắng ở **thông minh hơn, hữu ích hơn, dễ dùng hơn**.

---

## 📚 Nguồn Dữ Liệu Tham Khảo Nhanh

### Nhóm 70% — Nền tảng chính

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

### Nhóm 20% — Kiểm chứng & tín hiệu bổ sung

| Nguồn | Link | Dùng cho |
|--------|------|----------|
| **HieuNTg/medgraph** | github.com/HieuNTg/medgraph | Cascade Analysis Engine framework |
| **SAHAYAK Project** | github.com/mohanganesh3/Sahayak | Enzyme mapping, QT drugs, electrolyte data |
| **CredibleMeds** | crediblemeds.org | QT-prolonging drug list |
| **CPIC Guidelines** | cpicpgx.org/guidelines | Tương lai: Pharmacogenomics |
| **Beers Criteria 2023** | American Geriatrics Society | Kiểm tra thuốc cho người cao tuổi |
| **davide-beltrame/medication-schedule-optimizer** | github.com/davide-beltrame/medication-schedule-optimizer | Algorithm tối ưu lịch uống thuốc |
| **GRADE System** | (Chuẩn quốc tế Cochrane/WHO) | Xếp hạng bằng chứng |

### Barcode Lookup

| API | Free Tier | Ưu tiên |
|-----|-----------|---------|
| **Open Food Facts** | Không giới hạn, không key | ⭐⭐⭐⭐ |
| **UPCitemdb** | 100/ngày free | ⭐⭐⭐ |

---

*Tài liệu này được thiết kế để AI code có thể đọc hiểu và triển khai. Mỗi bước đã mô tả rõ mục đích, nguồn dữ liệu và kết quả mong đợi — không cần hướng dẫn code chi tiết.*

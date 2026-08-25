# 📋 Kế Hoạch Tổng Quan: Tích Hợp Frontend `personalized-product-scanner` Vào MedMatch AI

**Phiên bản:** 1.0 | **Ngày:** 2026-08-25 | **Trạng thái:** Sẵn sàng triển khai

---

## 🎯 Tổng Quan Dự Án

### Frontend hiện có
- **Nguồn:** Google AI Studio template → `personalized-product-scanner`
- **Công nghệ:** React 19 + TypeScript + Vite + Tailwind CSS v4 + Express
- **Đối tượng ban đầu:** Quét thực phẩm & mỹ phẩm, kiểm tra dị ứng, thành phần an toàn
- **Điểm mạnh:** Giao diện đẹp, hiện đại; 16 tính năng/modal sẵn có; đa ngôn ngữ; tích hợp sẵn barcode scanning & OCR

### Mục tiêu chuyển đổi
Biến frontend từ **"Personalized Product Scanner"** thành **"MedMatch AI — Drug & Supplement Interaction Checker"**, giữ lại 80% giao diện & cơ sở hạ tầng, thay thế 20% logic cốt lõi, thêm 7 tính năng độc đáo.

---

## ✅ Điểm Mạnh Cần Giữ Nguyên

| Thành phần | Giá trị giữ lại |
|-----------|----------------|
| **Giao diện Tailwind + Motion** | Hiện đại, mượt mà, chuyên nghiệp |
| **Cấu trúc 7 tabs** | Scanner / History / Compare / Smart Swaps / Health Dashboard / Profile → tái sử dụng hoàn toàn |
| **Hệ thống Profile người dùng** | Dị ứng, chế độ ăn, bệnh lý, hồ sơ gia đình → chỉ cần bổ sung trường |
| **ZXing Barcode Scanning** | Đã tích hợp sẵn, chỉ cần điều chỉnh luồng xử lý |
| **OCR Image Scan endpoint** | Đã có `/api/scan/image`, có thể thay Gemini bằng ML Kit sau |
| **16 modal/features** | Evidence, Family Profiles, AI Chat, Batch Scan, Receipt Audit, Market Catalog, Cross-Reactivity, Skincare Radar, Herb-Drug → nhiều cái tái sử dụng được |
| **Hệ thống i18n** | EN/FR/DE/IT/ES → sẵn sàng mở rộng tiếng Việt sau này |
| **Health Dashboard** | Có thể chuyển thành "Bảng phân tích tương tác thuốc" |
| **Smart Swaps** | Có thể chuyển thành "Gợi ý TPCN thay thế an toàn" |
| **Cơ sở hạ tầng Vite + Express** | Build nhanh, phát triển thuận tiện |

---

## 🔴 Các Vấn Đề Cần Sửa Đổi — Tổng Quan

| Vấn đề | Mức độ | Hướng giải quyết chính |
|--------|--------|------------------------|
| **Trọng tâm sản phẩm sai** | 🔴 Cao | Chuyển từ thực phẩm/mỹ phẩm → thuốc/TPCN làm chính |
| **Logic đánh giá sai nền tảng** | 🔴 Cao | Thay `assessProductMatch` bằng gọi API MedMatch AI backend 7 lớp |
| **Dữ liệu thảo dược-thuốc yếu** | 🔴 Cao | Xóa hard-coded, thay bằng database tổng hợp SUPP.AI + DDInter + iDISK |
| **Profile thiếu trường quan trọng** | 🟡 Trung bình | Bổ sung tuổi, thuốc đang uống, chức năng thận/gan, mang thai... |
| **Phụ thuộc quá nhiều Gemini** | 🟡 Trung bình | AI chỉ dùng cho giải thích/tư vấn, không cho cảnh báo y khoa chính |
| **Chưa có 7 tính năng độc đáo** | 🔴 Cao | Tích hợp lần lượt: Cascade, Schedule, QT Risk, Electrolyte, Evidence Grading, Beers, Depletion |
| **Hiển thị kết quả chưa phù hợp** | 🟡 Trung bình | Đổi từ điểm số kiểu Yuka → danh sách tương tác theo mức độ nghiêm trọng y khoa |
| **Backend cần tách biệt** | 🟡 Trung bình | Giữ Express làm BFF, tách FastAPI riêng cho logic y khoa |

---

## 🗺️ Kế Hoạch Sửa Đổi 4 Giai Đoạn

### Giai đoạn 1: Điều Chỉnh Nền Tảng (Tuần 1-2)
*Thay đổi cấu trúc cơ bản, chuẩn bị cho logic mới*

| Công việc | Mô tả chi tiết | File liên quan |
|-----------|---------------|----------------|
| **1.1 Mở rộng kiểu dữ liệu** | Thêm `ProductType`: `'drug' | 'supplement' | 'herb'`; Thêm các trường thuốc: `generic_name`, `rxnorm_rxcui`, `atc_code`, `drug_class`, `dosage_form` | `src/types.ts` |
| **1.2 Bổ sung trường Profile** | Thêm `age`, `gender`, `pregnancyStatus`, `kidneyFunction`, `liverFunction`, chuẩn hóa `currentMedications` | `src/types.ts`, `src/components/ProfileView.tsx` |
| **1.3 Điều chỉnh ScannerView** | Thêm tab chuyển đổi: "Quét mã vạch" / "Gõ tên thuốc" / "Chọn từ danh sách phổ biến"; Ưu tiên quét nhãn thuốc/TPCN | `src/components/ScannerView.tsx` |
| **1.4 Đổi hệ thống mức độ nghiêm trọng** | Từ `safe/caution/warning/danger` → chuẩn y khoa: `contraindicated/major/moderate/mild/safe` | `src/types.ts`, `src/components/ScanResultCard.tsx` |
| **1.5 Đổi định vị & tên app** | Đổi tên hiển thị, logo, mô tả thành "MedMatch AI — Drug & Supplement Interaction Checker" | `index.html`, `src/components/Header.tsx`, `metadata.json` |

### Giai đoạn 2: Thay Thế Logic Cốt Lõi (Tuần 3-4)
*Thay trái tim của hệ thống — từ đánh giá dị ứng thực phẩm sang kiểm tra tương tác thuốc*

| Công việc | Mô tả chi tiết | File liên quan |
|-----------|---------------|----------------|
| **2.1 Xây dựng Lớp 1 Input Normalizer** | Tạo service 4 bước: chuẩn hóa chuỗi → tra cứu đồng nghĩa → fuzzy matching → fallback. Map mọi tên thành phần về `standard_id` duy nhất | `server/services/input_normalizer.ts` (file mới) |
| **2.2 Xóa database hard-coded** | Xóa `HERB_DRUG_DATABASE` trong `herb_drug_interactions.ts` | `server/services/herb_drug_interactions.ts` |
| **2.3 Tích hợp gọi API MedMatch AI** | Tạo service gọi đến FastAPI backend `/api/check-interactions`, nhận danh sách `standard_id` trả về kết quả tương tác | `server/services/medmatch_api_client.ts` (file mới) |
| **2.4 Thay thế `assessProductMatch`** | Hàm cũ đánh giá dị ứng → thay bằng gọi Input Normalizer + MedMatch API Client + tổng hợp kết quả | `server/services/matcher.ts` |
| **2.5 Điều chỉnh luồng `/api/scan`** | Sửa endpoint để dùng logic mới, trả về kết quả tương tác thay vì đánh giá dị ứng | `server.ts` |
| **2.6 Đổi hiển thị kết quả** | `ScanResultCard` hiển thị theo mức độ nghiêm trọng y khoa, mỗi cảnh báo có: mức độ, 2 thành phần, cơ chế, bằng chứng, khuyến nghị | `src/components/ScanResultCard.tsx` |

### Giai đoạn 3: Thêm 7 Tính Năng Độc Đáo (Tuần 5-8)
*Điểm khác biệt thực sự so với đối thủ*

| Tuần | Tính năng | Mô tả tích hợp | Component/File mới |
|-------|-----------|---------------|-------------------|
| **5** | **① Evidence Grading System** | Thêm thẻ xếp hạng bằng chứng vào mỗi cảnh báo: ✅ Cao / ℹ️ Trung bình / ⚠️ Thấp / 🔬 Rất thấp | `ScanResultCard.tsx` (thêm section) |
| **5** | **⑦ Medication Depletion** | Thêm section: "💊 Thuốc bạn đang uống có thể làm cạn kiệt..." + gợi ý bổ sung | `ScanResultCard.tsx` + gọi API MedMatch |
| **6** | **① Cascade Analysis Engine** | Thêm section: "🔍 Phát hiện chuỗi nguy cơ qua đường dẫn enzyme" + sơ đồ đường A→enzyme→B→enzyme→C | `CascadeAnalysisModal.tsx` (file mới) + mở rộng từ `EvidenceModal` |
| **6** | **⑥ Beers Criteria Checker** | Nếu user ≥65 tuổi, thêm badge: "👴 Theo tiêu chuẩn Beers 2023, thuốc này cần thận trọng" | Logic trong MedMatch API + hiển thị trong `ScanResultCard` |
| **7** | **② Schedule Optimizer** | Tạo modal hiển thị "📅 Lịch uống thuốc đề xuất" với bảng thời gian để tránh tương tác hấp thu | `ScheduleOptimizerModal.tsx` (file mới) |
| **7** | **④ Electrolyte Depletion** | Thêm section: "⚡ Cảnh báo thiếu hụt điện giải" + liên kết đến nguy cơ thứ cấp (rối loạn nhịp...) | `ScanResultCard.tsx` (thêm section) |
| **8** | **③ QT Prolongation Risk** | Thêm badge đặc biệt: "❤️ Nguy cơ kéo dài khoảng QT" + giải thích các yếu tố nguy cơ cộng gộp | Logic trong MedMatch API + hiển thị trong `ScanResultCard` |
| **8** | **Điều chỉnh Smart Swaps** | Đổi từ gợi ý thực phẩm sạch → "Gợi ý TPCN thay thế an toàn" (cùng công dụng, không tương tác) | `SmartSwapsView.tsx` + logic mới trong backend |

### Giai đoạn 4: Tinh Chỉnh & Tối Ưu (Tuần 9+)
*Hoàn thiện trải nghiệm & hiệu năng*

| Công việc | Mô tả chi tiết |
|-----------|---------------|
| **4.1 Thay OCR Gemini bằng ML Kit** | Chuyển xử lý OCR sang chạy trên thiết bị (iOS Vision hoặc Google ML Kit) — nhanh, miễn phí, offline |
| **4.2 Tối ưu Health Dashboard** | Chuyển từ "Phân tích thực phẩm" thành "Bảng phân tích tương tác thuốc": tổng số cảnh báo, phân bố mức độ, top tương tác gặp nhiều nhất |
| **4.3 Điều chỉnh CompareView** | So sánh 2 sản phẩm dựa trên mức độ tương tác với hồ sơ người dùng, thay vì so sánh thành phần thực phẩm |
| **4.4 Tích hợp Family Profiles đúng cách** | Mỗi thành viên gia đình có hồ sơ thuốc riêng, khi chuyển hồ sơ tự động đánh giá lại kết quả quét |
| **4.5 Tối ưu hiệu năng & offline** | Cache kết quả tra cứu phổ biến vào SQLite local, tối ưu hóa FTS5 tìm kiếm nhanh |
| **4.6 Điều chỉnh AI Chat** | Giữ lại làm tính năng phụ trợ Pro, nhưng rõ ràng phân biệt với cảnh báo y khoa chính |
| **4.7 Tích hợp Batch Scan & Receipt Audit** | Chuyển từ kiểm tra hóa đơn thực phẩm → kiểm tra danh sách thuốc/TPCN mua về |

---

## 🧩 Bản Đồ Tích Hợp 7 Lớp Logic Vào Frontend

```
┌─────────────────────────────────────────────────────────────────┐
│                     FRONTEND REACT + VITE                        │
│                                                                 │
│  ScannerView / ProfileView / HistoryView / CompareView...       │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  EXPRESS BFF (Backend For Frontend)                      │   │
│  │                                                          │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │  LỚP 1: INPUT NORMALIZER                          │  │   │
│  │  │  • Chuẩn hóa chuỗi                                │  │   │
│  │  │  • Tra cứu bảng ingredient_synonym                │  │   │
│  │  │  • Fuzzy matching lỗi OCR/chính tả                │  │   │
│  │  │  • Kết quả: danh sách standard_id                 │  │   │
│  │  └──────────────────────┬─────────────────────────────┘  │   │
│  │                         │ HTTPS / JSON                    │   │
│  └─────────────────────────┼────────────────────────────────┘   │
│                            │                                   │
└────────────────────────────┼───────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                MEDMATCH AI FASTAPI BACKEND (RIÊNG)              │
│                                                                 │
│  LỚP 2: Multi-Source Query Engine → tra cứu interaction_unified │
│  LỚP 3: Conflict Resolution → giải quyết mâu thuẫn nguồn        │
│  LỚP 4: 7 Inference Engines (Cascade, Schedule, QT Risk...)     │
│  LỚP 5: Evidence Grader → xếp hạng GRADE                        │
│  LỚP 6: Result Synthesizer → tổng hợp & giải thích dễ hiểu      │
│  LỚP 7: Safety Override → quy tắc an toàn ghi đè               │
│                                                                 │
│  Nguồn dữ liệu: SUPP.AI + DDInter + iDISK + RxNorm + CYP450...   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Lộ Trình Timeline Tổng Quan

```
TUẦN 1-2: NỀN TẢNG
├─ Mở rộng types.ts
├─ Bổ sung trường Profile
├─ Điều chỉnh ScannerView
├─ Đổi hệ thống mức độ nghiêm trọng
└─ Đổi tên & định vị app

TUẦN 3-4: LOGIC CỐT LÕI
├─ Xây dựng Input Normalizer (Lớp 1)
├─ Tích hợp gọi API MedMatch AI
├─ Thay thế assessProductMatch
├─ Điều chỉnh luồng /api/scan
└─ Đổi hiển thị kết quả

TUẦN 5-8: 7 TÍNH NĂNG ĐỘC ĐÁO
├─ Tuần 5: Evidence Grading + Medication Depletion
├─ Tuần 6: Cascade Analysis + Beers Criteria
├─ Tuần 7: Schedule Optimizer + Electrolyte Depletion
└─ Tuần 8: QT Risk + Smart Swaps điều chỉnh

TUẦN 9+: TINH CHỈNH
├─ Thay OCR bằng ML Kit
├─ Tối ưu Health Dashboard
├─ Điều chỉnh CompareView
├─ Tích hợp Family Profiles đúng cách
└─ Tối ưu hiệu năng & offline
```

---

## 🔑 Các Nguyên Tắc Thiết Kế Quan Trọng

### 1. Nguyên tắc tách biệt trách nhiệm
- **Frontend**: Chỉ hiển thị, thu thập đầu vào, quản lý trạng thái người dùng
- **Express BFF**: Xử lý các tác vụ riêng cho frontend (profile, lịch sử, OCR, AI chat phụ trợ), gọi API MedMatch
- **FastAPI Backend**: Chứa toàn bộ logic y khoa, database, 7 lớp xử lý — **độc lập, có thể thay đổi frontend mà không ảnh hưởng**

### 2. Nguyên tắc dữ liệu y khoa
- **Dữ liệu cảnh báo chính phải đến từ database có kiểm chứng** (SUPP.AI, DDInter, FDA, NIH...), không phải AI sinh ra
- **AI chỉ dùng cho**: giải thích, tóm tắt, tư vấn bổ trợ, trò chuyện — luôn rõ ràng phân biệt với cảnh báo chính
- **Mọi cảnh báo phải có nguồn gốc rõ ràng**: hiển thị nguồn dữ liệu và mức độ bằng chứng

### 3. Nguyên tắc an toàn
- **Ưu tiên an toàn người dùng trên hết**: Khi có mâu thuẫn, luôn chọn mức độ nghiêm trọng cao hơn
- **Không bao giờ nói chắc chắn 100%**: Luôn có disclaimer "Thông tin tham khảo, không thay thế tư vấn y tế"
- **Dữ liệu suy luận phải được đánh dấu rõ**: "Dựa trên cơ chế sinh học, chưa có báo cáo lâm sàng trực tiếp"

### 4. Nguyên tắc trải nghiệm người dùng
- **Đơn giản hóa**: Dịch thuật ngữ y khoa phức tạp ra lời thường hiểu
- **Hành động cụ thể**: Mỗi cảnh báo đi kèm khuyến nghị hành động rõ ràng ("Tránh", "Uống cách nhau 4 giờ", "Thảo luận với bác sĩ")
- **Minh bạch**: Nói rõ mức độ chắc chắn của mỗi cảnh báo (Cao/Trung bình/Thấp/Rất thấp)

---

## 📝 Tiếp Theo

Sau khi có kế hoạch tổng quan này, chúng ta sẽ đi sâu vào chi tiết từng lớp:

1. **✅ Lớp 1: Input Normalizer** — cách xử lý mọi tên gọi khác nhau (đã thảo luận sơ bộ)
2. **⬜ Lớp 2: Multi-Source Query Engine** — cách tra cứu đa nguồn hiệu quả
3. **⬜ Lớp 3: Conflict Resolution** — cách giải quyết mâu thuẫn giữa các nguồn
4. **⬜ Lớp 4: 7 Inference Engines** — chi tiết từng tính năng độc đáo
5. **⬜ Lớp 5-7: Evidence Grading, Result Synthesizer, Safety Override**
6. **⬜ Tích hợp từng tính năng vào giao diện frontend cụ thể**

Bạn có muốn chúng ta bắt đầu đi sâu vào **Lớp 1: Input Normalizer chi tiết** không?

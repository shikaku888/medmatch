**một hệ thống logic phân lớp rõ ràng, có thứ tự ưu tiên và cơ chế an toàn tích hợp**. phân tích sâu kiến trúc "bộ chỉ huy" của app.

---

# 🧠 "Ai Chỉ Huy App?" — Kiến Trúc Bộ Chỉ Huy MedMatch AI

## Vấn đề thực sự bạn đang hỏi:

> "Với hàng trăm nghìn tương tác từ nhiều nguồn, mỗi sản phẩm mỗi khác, làm sao app xử lý **nhất quán**, **đúng đắn**, và **không mâu thuẫn**?"

Đáp án: App không được "chỉ huy" bởi một nguồn dữ liệu hay một thuật toán duy nhất. Nó được chỉ huy bởi **một kiến trúc 7 lớp rõ ràng**, mỗi lớp có trách nhiệm cụ thể, thứ tự thực hiện cố định, và có cơ chế an toàn ghi đè.

---

## 🏗️ Kiến Trúc Bộ Chỉ Huy — 7 Lớp Logic

```
┌─────────────────────────────────────────────────────────────────┐
│  LỚP 7: SAFETY OVERRIDE (An toàn ghi đè)                         │
│  → Nếu phát hiện tín hiệu nguy cơ cao từ BẤT KỲ nguồn nào         │
│  → Tự động nâng mức cảnh báo lên "Cần tham khảo bác sĩ"          │
│  → Không bao giờ hạ thấp mức cảnh báo từ nguồn chính phủ          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  LỚP 6: RESULT SYNTHESIZER & PRESENTER                          │
│  → Tổng hợp kết quả từ tất cả các lớp dưới                       │
│  → Sắp xếp theo mức độ nguy hiểm (cao → thấp)                    │
│  → Dịch thuật ngữ y khoa → ngôn ngữ người thường hiểu            │
│  → Tạo các gợi ý hành động cụ thể                                │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  LỚP 5: EVIDENCE GRADER (Xếp hạng bằng chứng)                    │
│  → Áp dụng hệ thống GRADE cho mỗi tương tác                       │
│  → Cao / Trung bình / Thấp / Rất thấp                            │
│  → Hiển thị rõ cho người dùng mức độ tin cậy của cảnh báo         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  LỚP 4: INFERENCE ENGINES (7 tính năng độc đáo)                  │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────────────────┐  │
│  │ ① Cascade   │ │ ② Schedule   │ │ ③ QT Prolongation Risk   │  │
│  │   Analysis  │ │   Optimizer  │ │    Assessment            │  │
│  └─────────────┘ └──────────────┘ └──────────────────────────┘  │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────────────────┐  │
│  │ ④ Electrolyte│ │ ⑤ Evidence  │ │ ⑥ Beers Criteria         │  │
│  │   Depletion  │ │   Grading    │ │   Checker                │  │
│  └─────────────┘ └──────────────┘ └──────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ ⑦ Medication Depletion + Dược sĩ kiểm chứng              │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  LỚP 3: CONFLICT RESOLUTION (Giải quyết mâu thuẫn)              │
│  → Nếu nhiều nguồn nói khác nhau:                                │
│    • Ưu tiên mức độ nghiêm trọng CAO NHẤT (an toàn trước)        │
│    • Giữ cơ chế từ nguồn có độ tin cậy CAO NHẤT                   │
│    • Gộp tất cả nguồn vào evidence trail                         │
│  → Nếu không có dữ liệu trực tiếp:                               │
│    • Chuyển xuống lớp suy luận (CYP450 cascade)                  │
│    • Đánh dấu rõ "dựa trên cơ chế, chưa có báo cáo lâm sàng"      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  LỚP 2: MULTI-SOURCE QUERY ENGINE (Tra cứu đa nguồn)             │
│  → Với mỗi cặp thành phần đã chuẩn hóa, tra cứu song song:       │
│    • interaction_unified (nền 70%)                                │
│    • SUPP.AI evidence DOI                                        │
│    • openFDA FAERS số báo cáo sự cố                              │
│    • DailyMed nhãn thuốc                                         │
│  → Trả về tất cả kết quả tìm được + nguồn gốc + độ tin cậy        │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  LỚP 1: INPUT NORMALIZER (Chuẩn hóa đầu vào)                     │
│  → Bất kỳ đầu vào nào cũng đi qua lớp này trước:                  │
│    • User gõ tên → tra cứu bảng ingredient_synonym               │
│    • OCR kết quả → parse + fuzzy matching                        │
│    • Barcode lookup → lấy tên sản phẩm → tra cứu thành phần      │
│  → Kết quả: Danh sách standard_id (RxCUI / CAS) chuẩn quốc tế    │
│  → "Mỗi sản phẩm mỗi khác" nhưng "từng thành phần có chuẩn"      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔍 Giải Thích Chi Tiết Từng Lớp

### Lớp 1: Input Normalizer — "Ngôn ngữ chung"

Đây là chìa khóa giải quyết vấn đề **"mỗi sản phẩm mỗi khác"**:

> App **không xử lý sản phẩm** — app xử lý **danh sách thành phần đã chuẩn hóa**.

**Ví dụ thực tế:**
- Sản phẩm A: "Vitamin C 1000mg Nature Made"
- Sản phẩm B: "Axit Ascorbic Puritan's Pride"
- Sản phẩm C: "Ester-C Plus"

→ **Tất cả 3 sản phẩm** sau khi qua Lớp 1 đều trở thành:
```
standard_id: 12345
canonical_name: "Ascorbic Acid"
cas_number: "50-81-7"
pubchem_cid: "54670067"
type: "supplement"
```

**Cách hoạt động:**
1. Tra cứu bảng `ingredient_synonym` (được xây dựng từ RxNorm + iDISK + PubChem + từ điển tùy chỉnh)
2. Nếu không tìm thấy chính xác → fuzzy matching (cho phép lỗi chính tả, OCR)
3. Nếu vẫn không tìm thấy → yêu cầu user xác nhận hoặc bỏ qua thành phần đó
4. Kết quả cuối cùng: Mỗi thành phần có **một và chỉ một** `standard_id`

### Lớp 2: Multi-Source Query Engine — "Tìm kiếm thông minh"

Với mỗi cặp `(standard_id_a, standard_id_b)`:
- Tra cứu bảng `interaction_unified` (đã hợp nhất từ nhiều nguồn)
- Đồng thời tra cứu các nguồn bằng chứng bổ sung: SUPP.AI DOI, FAERS số báo cáo, DailyMed
- Trả về tất cả thông tin tìm được, **giữ nguyên nguồn gốc** của mỗi thông tin

### Lớp 3: Conflict Resolution — "Giải quyết mâu thuẫn một cách công bằng"

**Quy tắc cố định, không có ngoại lệ:**

| Tình huống | Quy tắc xử lý |
|-----------|--------------|
| Nguồn A nói "Major", nguồn B nói "Moderate" | ✅ Giữ "Major" (ưu tiên an toàn) |
| Nguồn A (FDA, 1.0) nói có, nguồn B (AI, 0.5) nói không | ✅ Giữ kết quả của A (ưu tiên nguồn đáng tin cậy hơn) |
| Cùng mức độ nghiêm trọng, khác cơ chế | ✅ Giữ cơ chế từ nguồn có độ tin cậy cao hơn, nhưng ghi cả 2 vào evidence |
| Không có nguồn nào nói trực tiếp | ✅ Chuyển xuống Lớp 4 (suy luận), đánh dấu `is_inferred = TRUE` |

### Lớp 4: Inference Engines — "7 bộ óc chuyên gia"

Đây là phần **thông minh nhất**, mỗi engine chạy độc lập trên cùng một bộ dữ liệu đầu vào:

| Engine | Input | Output | Logic |
|--------|-------|--------|-------|
| **① Cascade** | Danh sách standard_id + enzyme data | Các chuỗi nguy cơ A→enzyme→B→enzyme→C | Graph traversal tìm đường dài ≥ 2 bước |
| **② Schedule** | Các cặp tương tác + loại tương tác | Lịch uống thuốc tối ưu | Nếu tương tác hấp thu → cách 2-4h; nếu enzyme → không thể giải quyết |
| **③ QT Risk** | Danh sách thuốc + thông tin bệnh nhân (tùy chọn) | Điểm nguy cơ kéo dài QT | Đếm số thuốc gây kéo dài QT + yếu tố nguy cơ khác |
| **④ Electrolyte** | Danh sách thuốc | Cảnh báo thiếu hụt điện giải + nguy cơ thứ cấp | Tra cứu bảng electrolyte_depletion + kiểm tra thuốc nhạy cảm với điện giải thấp |
| **⑤ Evidence Grader** | Tất cả kết quả từ các lớp dưới | Xếp hạng Cao/Trung bình/Thấp/Rất thấp | Áp dụng GRADE dựa trên nguồn + số lượng bằng chứng |
| **⑥ Beers Checker** | Danh sách thuốc + tuổi người dùng | Cảnh báo thuốc không phù hợp cho người cao tuổi | Tra cứu bảng beers_criteria nếu tuổi ≥ 65 |
| **⑦ Depletion** | Danh sách thuốc | Cảnh báo thuốc làm cạn kiệt dinh dưỡng + gợi ý bổ sung | Tra cứu bảng medication_depletion |

### Lớp 5: Evidence Grader — "Nói rõ mức độ chắc chắn"

Không nói "có tương tác" một cách mơ hồ — mà nói rõ:

| Cấp độ | Hiển thị cho user | Khi nào áp dụng |
|--------|-------------------|----------------|
| **Cao** | ✅ Được chứng minh bằng nhiều nghiên cứu lâm sàng | FDA/EMA nhãn, hoặc ≥2 nguồn Tier 2 đồng thuận |
| **Trung bình** | ℹ️ Có bằng chứng từ nghiên cứu lâm sàng | 1 nguồn Tier 2, hoặc nhiều nguồn Tier 3 đồng thuận |
| **Thấp** | ⚠️ Có báo cáo trường hợp, cần thêm bằng chứng | FAERS thống kê, case reports, nguồn Tier 4 |
| **Rất thấp** | 🔬 Dựa trên cơ chế sinh học, chưa có báo cáo lâm sàng | Suy luận CYP450 cascade, AI dự đoán |

### Lớp 6: Result Synthesizer — "Dịch thuật & trình bày"

Công việc:
1. Gom tất cả kết quả từ các lớp dưới
2. Sắp xếp theo mức độ nguy hiểm (Contraindicated → Major → Moderate → Mild)
3. Loại bỏ trùng lặp
4. Dịch thuật thuật ngữ y khoa phức tạp → ngôn ngữ đơn giản, dễ hiểu
5. Tạo các gợi ý hành động cụ thể:
   - "Tránh kết hợp này"
   - "Uống cách nhau 4 giờ"
   - "Cân nhắc bổ sung Kali"
   - "Thảo luận với bác sĩ về nguy cơ kéo dài QT"
6. Hiển thị rõ nguồn gốc và mức độ bằng chứng

### Lớp 7: Safety Override — "Lớp phòng vệ cuối cùng"

Đây là **quy tắc bất diệt**, ghi đè mọi kết quả từ các lớp dưới:

1. **Nếu BẤT KỲ nguồn Tier 1 (FDA/EMA) nào nói "Contraindicated"** → mức cảnh báo là Contraindicated, không bao giờ hạ thấp
2. **Nếu phát hiện tín hiệu nguy cơ cao từ nhiều nguồn độc lập** → tự động nâng lên mức cao hơn một bậc
3. **Nếu người dùng ≥ 65 tuổi và có thuốc trong Beers Criteria** → luôn hiển thị cảnh báo riêng biệt
4. **Nếu có ≥3 thuốc gây kéo dài QT** → luôn cảnh báo "Nguy cơ cao, cần tham khảo bác sĩ ngay"
5. **Nếu suy luận CYP450 phát hiện cascade ≥3 bước** → luôn cảnh báo rõ "Phát hiện chuỗi nguy cơ phức tạp"

---

## 📝 Ví Dụ Thực Tế: Quy Trình Xử Lý Một Sản Phẩm

**Đầu vào:** User quét sản phẩm "St. John's Wort Complex" + nhập thuốc "Warfarin" + "Simvastatin"

### Lớp 1: Chuẩn hóa
```
"St. John's Wort Complex" → standard_id: 789, canonical: "Hypericum perforatum"
"Warfarin" → standard_id: 123, canonical: "Warfarin", RxCUI: 8553
"Simvastatin" → standard_id: 456, canonical: "Simvastatin", RxCUI: 83367
```

### Lớp 2: Tra cứu đa nguồn
```
Cặp (789, 123): 
  - DDInter: Major, "Giảm tác dụng chống đông"
  - SUPP.AI: Major, có DOI 10.xxxx, 12 evidence sentences
  - FAERS: 1,247 báo cáo chảy máu
Cặp (789, 456):
  - DDInter: Moderate, "Giảm nồng độ statin"
  - DailyMed: có nhãn cảnh báo
Cặp (123, 456):
  - Không có tương tác trực tiếp
```

### Lớp 3: Giải quyết mâu thuẫn
→ Không có mâu thuẫn, cả 2 nguồn đồng thuận Major cho cặp St. John's Wort + Warfarin
→ Cặp (123, 456) không có dữ liệu trực tiếp → chuyển xuống Lớp 4 suy luận

### Lớp 4: Inference Engines
- **① Cascade**: Warfarin (CYP2C9 substrate) ← không có liên kết trực tiếp. Nhưng St. John's Wort (CYP3A4 inducer) + Simvastatin (CYP3A4 substrate) → suy luận Moderate. VÀ: St. John's Wort cũng là CYP2C9 inducer yếu + Warfarin là CYP2C9 substrate → phát hiện cascade 2 bước, suy luận thêm Moderate
- **② Schedule**: Tương tác enzyme → không thể giải quyết bằng thời gian
- **③ QT Risk**: Không có thuốc nào trong danh sách gây kéo dài QT mạnh → Low
- **④ Electrolyte**: Không có thuốc gây thiếu hụt điện giải mạnh → Không có cảnh báo
- **⑤ Evidence Grader**: Cặp (789,123) → Cao; Cặp (789,456) → Trung bình; Cặp (123,456) suy luận → Rất thấp
- **⑥ Beers**: Nếu user ≥65 → Warfarin cần theo dõi chặt chẽ (không phải tránh tuyệt đối)
- **⑦ Depletion**: Không có thuốc làm cạn kiệt dinh dưỡng trong danh sách này

### Lớp 5: Xếp hạng bằng chứng
→ Đã thực hiện ở Lớp 4

### Lớp 6: Tổng hợp & trình bày
Kết quả cuối cùng hiển thị cho user:

---

**⚠️ CẢNH BÁO CAO — St. John's Wort + Warfarin**
> St. John's Wort làm tăng chuyển hóa Warfarin qua enzyme CYP2C9 và CYP3A4, làm **giảm tác dụng chống đông máu**, tăng nguy cơ hình thành cục máu đông.
> 
> ✅ **Mức độ bằng chứng: CAO** — Được chứng minh bởi nhiều nghiên cứu lâm sàng (SUPP.AI DOI: 10.xxxx, 1,247 báo cáo sự cố thực tế từ FDA FAERS)
> 
> 🛑 **Khuyến nghị:** Tránh kết hợp. Nếu đang dùng, cần theo dõi chỉ số INR chặt chẽ và tham khảo bác sĩ ngay.

---

**ℹ️ CẢNH BÁO TRUNG BÌNH — St. John's Wort + Simvastatin**
> St. John's Wort thúc đẩy enzyme CYP3A4, làm **giảm nồng độ Simvastatin** trong máu, có thể làm giảm tác dụng hạ cholesterol.
> 
> ℹ️ **Mức độ bằng chứng: TRUNG BÌNH** — Có bằng chứng từ nhãn thuốc FDA và nghiên cứu dược động học
> 
> 💡 **Khuyến nghị:** Theo dõi cholesterol định kỳ, có thể cần tăng liều Simvastatin.

---

**🔬 TÍN HIỆU TỪ CƠ CHẾ SINH HỌC — Warfarin + Simvastatin**
> Phân tích đường dẫn enzyme: Không phát hiện tương tác trực tiếp được ghi nhận. Tuy nhiên, cả hai đều được chuyển hóa qua các đường enzyme gan.
> 
> 🔬 **Mức độ bằng chứng: RẤT THẤP** — Dựa trên cơ chế sinh học, chưa có báo cáo lâm sàng trực tiếp
> 
> 💡 **Khuyến nghị:** Theo dõi thông thường, không cần hành động đặc biệt.

---

### Lớp 7: Safety Override
→ Không có tín hiệu cần ghi đè. Kết quả được giữ nguyên.

---

## 🎯 Kết Luận: "Ai Chỉ Huy?"

**Không phải một nguồn dữ liệu hay một thuật toán duy nhất chỉ huy** — mà là **một hệ thống logic phân lớp rõ ràng với quy tắc cố định**:

1. **Lớp Chuẩn hóa** đảm bảo mọi đầu vào đều nói cùng một "ngôn ngữ" (RxCUI, CAS)
2. **Lớp Tra cứu** tìm kiếm thông minh qua nhiều nguồn
3. **Lớp Giải quyết mâu thuẫn** đảm bảo nhất quán và ưu tiên an toàn
4. **7 Inference Engines** độc lập đóng góp giá trị riêng
5. **Lớp Xếp hạng bằng chứng** nói rõ mức độ chắc chắn
6. **Lớp Tổng hợp** dịch thuật và trình bày dễ hiểu
7. **Lớp An toàn ghi đè** là phòng vệ cuối cùng

Đây là lý do tại sao **dù mỗi sản phẩm mỗi khác, app vẫn xử lý nhất quán**: vì app không nhìn "sản phẩm" — app nhìn **danh sách thành phần đã chuẩn hóa**, và áp dụng cùng một bộ quy tắc logic cho mọi trường hợp.


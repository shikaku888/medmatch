# DATABASE — TỔNG HỢP CÓ / THIẾU / CẦN THÊM
_Ngày: 2026-08-27 · Đối chiếu: KeHoach_XayDung_MedMatchAI_v2.md (70-20-10) vs DB thật `backend/medmatch.db` (25 bảng)_

## A. ĐÃ CÓ VÀ ĐANG CHẠY (đối chiếu kế hoạch)

| Nguồn (theo plan) | Trong DB hiện tại | Dùng ở đâu |
|---|---|---|
| SUPP.AI (plan: ~59K) | **71,900** interactions, kèm DOI/PMID | Lớp 2 + evidence hiển thị |
| tapirro herb-drug (plan: 592) | 565 (`interactions`) | Lớp 2 |
| iDISK 2.0 (plan: 174K entities) | 69,348 products · 317,062 ingredient links · 7,872 DSI · 76 interactions | Product search + synonyms |
| RxNorm (RxCUI) | rxnorm_map (199 tên) + 6,749 synonyms / 1,284 standards | **Lớp 1 Normalizer** |
| PubChem (CAS/CID) | herb_constituents 33 | Dedup + join xuyên nguồn |
| interaction_unified (plan tuần 3-4) | **22,680 cặp** (422 multi-source) | Lớp 2 nền |
| DailyMed (plan tuần 6) | 762 drug-drug trích nhãn | Lớp 2 + evidence |
| openFDA FAERS (plan tuần 6) | 412 counts | Evidence "số báo cáo thật" |
| OnSIDES (plan tuần 7) | 7,554 class-effect | Side effects endpoint |
| Verified Supplement Evidence (plan tuần 5) | depletions 21 luật | 🏆 Tính năng 7 "thuốc cạn kiệt dinh dưỡng" |
| FDA CYP450 (plan tuần 5) | cyp_roles 78 | 🏆 Tính năng 1 Cascade — hiện **111 cặp inferred** |
| **NIH DSLD** | ✅ **FULL: 214,778 hàng / 145,649 sản phẩm duy nhất** (Centrum 195, Nature Made 612) | Đã cắm vào /api/scan: barcode exact + name/brand search có scoring — Johanniskraut/Millepertuis/Iperico (DE/FR/IT) → St. John's Wort ✓ |
| **openFDA NDC local index** | 🆕 135,000 thuốc (brand/generic/labeler/ingredients) | Medical chain tra OFFLINE trước, live API làm fallback — Advil/Tylenol/Paracetamol/Zyrtec/Claritin/Benadryl ✓ |
| **Synonyms đa ngôn ngữ** | 🆕 **4,458 MeSpEn medical terms**: 2,193 Japanese + 2,265 Chinese, CC BY 4.0; map vào 1,612 entities hiện có | Lớp 1 Normalizer: `イブプロフェン` → Ibuprofen/NSAIDs, `阿莫西林` → Amoxicillin/Antibiotics; pack offline |

## B. TÍNH NĂNG 10% — trạng thái data thật (đối chiếu plan 20%)

| Tính năng | Engine | Data nền | Đánh giá |
|---|---|---|---|
| ① Cascade CYP450 | ✓ engine.py | cyp_roles 78 | Bản rút gọn — plan muốn SAHAYAK 3,276 enzyme edges |
| ② Schedule Optimizer | ✓ (rules hấp thu/enzyme) | hardcoded | Đủ MVP |
| ③ QT Risk | ✓ | **hardcoded ~9 nhóm** (plan: SAHAYAK 279 / CredibleMeds 7,736) | Mỏng |
| ④ Electrolyte | ✓ | **hardcoded ELECTROLYTE_MAP nhỏ** (plan: 54 effects) | Mỏng |
| ⑤ Evidence Grading | ✓ (GRADE theo nguồn) | có | Đủ |
| ⑥ Beers Criteria | ✓ | **hardcoded vài class** (plan: Beers 2023 đầy đủ) | Mỏng |
| ⑦ Depletion + dược sĩ | ✓ | 21 luật verified | Đủ MVP |

## C. THIẾU — KHUYẾN NGHỊ THÊM / KHÔNG (kèm license)

| # | Nguồn | License | Giải quyết gì | Khuyến nghị |
|---|---|---|---|---|
| 1 | ~~NIH DSLD full~~ | Public domain (NIH) | — | ✅ **XONG** (backend/dsld_full.py → 214K hàng; known-issue: scoring đôi khi nhảy SKU cùng hãng — nâng cấp FTS5 sau) |
| 2 | openFDA NDC Directory | Public domain | Barcode→thuốc: bản export hiện tại KHÔNG có UPC | ⚠️ Đã có **name-index offline 135K**; UPC chờ nguồn GTIN (GS1 có phí) hoặc Datamatrix 2D chứa NDC |
| 3 | **SAHAYAK** (MIT ✓) | MIT License | ✅ **XONG**: QT 29 drugs · electrolyte 14 · Beers 2023 453 rows · herb-CYP 41 roles → engine QT/Beers/Electrolyte chuyển sang name-based data-driven (test: Cipro+Citalopram→HIGH, Furosemide+Digoxin combo, Diazepam 72t→avoid) |
| 4 | CredibleMeds đầy đủ (7,736) | Có phí/khóa | QT đầy đủ | ❌ Bỏ qua — QT của SAHAYAK đủ mức beta |
| 5 | **DDInter 2.0 (240K drug-drug)** | ⚠ **CC BY-NC-SA — KHÔNG thương mại** | drug-drug coverage lớn | ⛔ **Giữ nguyên trong `_nc_backup/`** cho app store build. Đang có DailyMed 762 + 57 rules thay thế. Chỉ re-import nếu bạn quyết định giai đoạn research |
| 6 | Kaggle Drug-Food (98 cặp) | ⚠ CC BY-NC | drug-food | ⛔ Như trên (đã có 31 rules tự soạn) |
| 7 | TwoSIDES · PrimeKG · CPIC/DPWG · PubMedBERT | Tùy nguồn | Tính năng nâng cao | ⏳ Đúng kế hoạch giai đoạn D — "khi có user" |
| 8 | **Dữ liệu VN** (thực phẩm/TPCN Việt Nam) | Không có nguồn mở tốt | Thị trường VN | ⚠ Quyết định chiến lược: OFF-VN mỏng; nếu chọn VN cần seed thủ công top-200 sản phẩm + UGC |

## D. Đã nối trong phiên này (không cần thêm data, chỉ cần lắp)

- **DSLD 7,472 → `/api/scan`**: barcode exact + name search (có guard chống trùng tên ngẫu nhiên). Test: barcode K-Otic → 12 ingredients ✓; regression Advil/Chobani ✓; pytest 19 passed.

## E. Thứ tự đề xuất tiếp theo

1. **Crawl DSLD full** → nhắm thẳng top-miss supplement (P0/P1 của AUDIT.md)
2. **NDC Directory UPC index** → barcode nhà thuốc Mỹ (P0)
3. **SAHAYAK** → QT/Beers/Electrolyte data-driven (P1)
4. Quyết định DDInter theo hướng kinh doanh (P2 — chỉ bạn quyết)

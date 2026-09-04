# DATA STRATEGY — "Không bao giờ bao trùm, nhưng không bao giờ bỏ lỡ"
_Ngày: 2026-08-27 · Trả lời: TikTok Shop, sản phẩm mới mỗi ngày, làm sao khi không có trong data_

## Triết lý cốt lõi

> **App không phân tích SẢN PHẨM — app phân tích THÀNH PHẦN đã chuẩn hóa.**

TikTok Shop có thể ra 1,000 gummy mới mỗi ngày, nhưng tất cả được làm từ một tập
nguyên liệu **hữu hạn** (~2,000-5,000 loại phổ biến phủ 95%+ sản phẩm tiêu dùng).
Vậy nên chiến lược đúng là đầu tư vào **nhận dạng thành phần**, không phải đuổi theo
catalog sản phẩm vô hạn.

## Flow khi KHÔNG có sản phẩm trong data (đã chạy thật)

```
User quét/ nhập ──► Barcode trong OFF/USDA/DSLD/NDC? ──CÓ──► Phân tích đầy đủ
                        │ KHÔNG
                        ▼
              Ảnh nhãn (Photo OCR) ──► RapidOCR đọc ──► parse thành phần
                        │
                        ▼
              Lớp 1 Normalizer: synonym (6,773+) → RxNorm live (NIH, free)
                        │ miss → RxNorm sửa typo/brand → match lại → LƯU synonym
                        ▼ (self-learning: lần sau instant)
              Partial-recognition: nhận dạng được ≥1 entity trong tên?
                        │ CÓ → phân tích phần nhận dạng được,
                        │      khai báo rõ "chưa kiểm tra: X, Y"
                        │ KHÔNG → 404 trung thực + hint: "chụp nhãn (OCR) hoặc nhập tên"
                        ▼
              coverage_events.jsonl ghi lại mọi hit/miss
                        → /api/coverage/stats = worklist bổ sung tuần sau
```

**Bằng chứng chạy thật (phiên này):**

| Query | Trước | Sau |
|---|---|---|
| `Paracetmol 500mg tablets` (typo) | 404 | **Partial match → Acetaminophen** (RxNorm live; lần 2 quét nhanh hơn nhờ tự học) |
| `Sleep well gummy melatonin 5mg` (kiểu TikTok) | 404 | openFDA: Sleep Well T012 + thành phần |
| `Centrum grown ups multivitamin` (câu lạ) | 404 | Partial: Multivitamin Preparation |
| `aspirin cardio 81` | 404 | Partial: Antiplatelet agent |

## 3 tầng dữ liệu — AI key KHÔNG cần lúc launch

| Tầng | Nguồn | Phí | Khi nào |
|---|---|---|---|
| **1. Local** | 214K DSLD · 135K NDC offline · 71,900 SUPP.AI · 22,680 unified · 6,773 synonyms (tự học) | 0đ | Luôn luôn — hoạt động offline |
| **2. Free public APIs** | OFF/OBF barcode+search · USDA · **RxNorm live (rxcui/properties)** · openFDA name · PubMed | 0đ, không key | Khi local miss |
| **3. AI Vision (optional)** | Gemini/GPT Vision đọc nhãn mờ, gợi ý entity cho nguyên liệu lạ | ~$0.002/scan | **Sau khi có doanh thu**; tắt mặc định; mọi kết quả AI đánh dấu "AI-suggested, unverified" |

Vì sao không dùng AI key ngay: (1) Tier 1+2 đã phủ đại đa số ca thật; (2) gửi ảnh nhãn
lên LLM = câu chuyện privacy khi review; (3) LLM tự do sinh văn bản = rủi rohallucination
trên app y tế — trái với nguyên tắc "verdict luôn từ engine".

## Self-learning loop (đã chạy)

1. Mỗi lần RxNorm/normalizer giải mã được input lạ → **tự INSERT vào
   `ingredient_synonyms`** (source='rxnorm-live')
2. Lần quét sau: fast-path tra synonym → **instant, 0 HTTP**
3. Mỗi lần miss → `coverage_events.jsonl` → `/api/coverage/stats` top-miss
   → bạn/dev bổ sung synonym/alias đúng thứ tự tần suất

→ **Càng nhiều user, app càng thông minh mà không cần ai đổ data.**

## Việc data còn lại (theo thứ tự)

1. FTS5 index cho DSLD scoring (fix Nature-Made-jumps-SKU; nhỏ)
2. PubChem live cho hóa chất lạ (nhận dạng "đây là hóa chất đã biết, chưa có data tương tác")
3. mở rộng synonym pack DE/FR/IT (5 herb entity chưa có trong bảng herbs)
4. AI Vision tier 3 — chờ doanh thu, không chặn launch


## CƠ CHẾ CẬP NHẬT DATA SAU LAUNCH (đã mô phỏng chứng minh)

**Nguyên tắc: data nằm ở server → user KHÔNG bao giờ cần update app để nhận data mới.**

| Loại update | Cách | User thấy khi nào |
|---|---|---|
| Synonym/thêm entity (sửa miss) | 1 dòng SQL vào `ingredient_synonyms` | **Ngay lập tức** — fastpath đọc DB live, không restart |
| SKU mới vào catalog (DSLD/NDC) | Importer idempotent nạp thêm hàng | **Ngay lập tức** — lookup đọc DB live |
| Dataset lớn mới (đĩa nguồn mới) | Thay file nguồn trong image → `fly deploy` → entrypoint tự chạy importer vào volume DB | Sau lần deploy (~2 phút) |
| Frontend code | Build mới + bump SW cache version | Refresh trang |

**An toàn dữ liệu người dùng khi deploy:** `medmatch.db` (gồm synonyms tự học +
review queue) nằm trên **Fly Volume** — deploy thay code, không đè data sống.
Entrypoint `deploy/start.sh`: seed-nếu-thiếu → chạy importer idempotent → uvicorn.

**Mô phỏng đã chạy:** barcode `030005571100` hôm nay → MISS trung thực; vài ngày sau
dev thêm SKU vào catalog (không restart, không update app) → quét lại → đầy đủ phân tích ✓

**Known-issue (cosmetic):** Nature Made D3 có thể trả SKU Vitamin C cùng hãng
(alphabet scoring) — fix bằng FTS5 ranking khi chạm perf, không chặn launch.

# PRODUCT REVIEW — App này bán được không? Thiếu gì? (người dùng thật sẽ nghĩ gì)
_Ngày: 2026-08-27 · Góc nhìn: reviewer + user persona thật, đối chiếu code đang chạy_

---

## 1. Verdict thẳng

**Có thể bán — nhưng KHÔNG phải ở trạng thái "nhiều tính năng". App bán được nhờ MỘT khoảnh khắc: quét sản phẩm → app cảnh báo "hỗn hợp này xung đột với thuốc bạn đang uống" kèm bằng chứng.** Mọi thứ khác là phụ trợ.

Thị trường thật (5 nước mục tiêu):
- ~66% người Mỹ trưởng thành uống ≥1 thuốc kê đơn; thị trường supplement ~$180B/năm
- Hàng triệu lượt search/tháng kiểu "can I take melatonin with ibuprofen"
- Yuka 55M users nhưng **yếu** mảng supplement×thuốc — đây là khe hở của ta
- Đối thủ gần nhất (Drugs.com, Medisafe) UX lâm sàng, khô khan — khe hở UX của ta

→ Định vị một câu: **"Yuka dành cho người đang uống thuốc."**

## 2. Chẩn đoán "ít tính năng / chưa khôn" — 4 gốc rễ thật

| # | Gốc rễ | Bằng chứng trong app | Hậu quả cảm giác |
|---|---|---|---|
| 1 | **Cold-start không cá nhân hóa** | Lần đầu mở app quét yogurt → "safe" → chán. Engine cá nhân hóa mạnh nhưng user chưa nhập thuốc thì chẳng có gì để cá nhân hóa | "App này cho tôi biết gì mà ChatGPT không?" |
| 2 | **Trí tuệ engine bị chôn trong API** | Schedule Optimizer (Tính năng ②) tính xong lịch uống tối ưu nhưng UI chỉ hiện 1 dòng text; Evidence grading có nhưng hiện mờ | User không thấy app "thông minh" dù nó đang thông minh |
| 3 | **18 tính năng nửa vời** | Skincare radar, receipt, batch… mỗi cái MVP-thin | App loang loáng, không có hero loop |
| 4 | **Giọng trả lời chưa tự nhiên đủ** | Đã nâng cấp pharmacist-voice (verdict→meaning→action→evidence) nhưng vẫn template | Đặt cạnh ChatGPT là thua về "nghe" |

## 3. Nếu TÔI LÀ USER (persona: 48 tuổi, uống Lipitor + amlodipine, hay mua supplement ở Costco)

**Tôi cần, theo thứ tự:**

| # | Điều tôi cần | App đã có? | Việc còn lại |
|---|---|---|---|
| 1 | **Onboarding bắt thuốc trước**: lần đầu mở app hỏi "Bạn đang uống thuốc gì?" — gõ 3 chữ ra gợi ý, lưu cabinet | Nửa (ProfileView có ô medicines, nhưng không ai biết phải nhập TRƯỚC) | 🎯 **Flow onboarding 3 màn** — small effort, đổi cả trải nghiệm |
| 2 | Quét cái gì cũng ra kết luận cá nhân **cho riêng tôi** trong 3 giây | ✓ engine + matchAssessment | — |
| 3 | Hỏi tự nhiên "uống melatonin với thuốc của tôi được không?" → câu trả lời nghe người | ✓ advisor mới | Thêm AI-phrasing layer (optional, có fallback) |
| 4 | **Xung đột thì cho tôi PHƯƠNG ÁN thay thế**, không chỉ cảnh báo | ✓ Smart Swaps (iDISK + verify) | Nổi bật hơn trong result card |
| 5 | **Lịch uống trực quan**: "Levothyroxine 6h sáng — Calcium 2h chiều" | ⚠ Engine tính rồi (`schedule_for`) nhưng chưa vẽ | 🎯 UI timeline — engine xong, chỉ thiếu vẽ |
| 6 | Nhớ tôi: cabinet theo profile, không nhập lại | ✓ localStorage + family profiles | — |
| 7 | By chứng khoa học hiện ra khi tôi nghi ngờ | ✓ DOI + FAERS counts | — |
| 8 | Con tôi / mẹ già tôi dùng gì an toàn | ✓ Family + Beers | — |

**Những gì khiến tôi XOÁT app:** quét gì cũng "safe" (data miss) · trả lời như robot · paywall ập mặt · 5 chạm mới tới kết luận.

## 4. Vì sao "app chưa khôn" là CẢM GIÁC hơn là THỰC — và cách sửa đúng

Engine thực sự có 7 lớp intelligence (cascade CYP, QT, Beers, electrolyte, GRADE,
schedule, depletion) — nhiều hơn đa số đối thủ consumer. Vấn đề là **trí tuệ không
được bề mặt hóa**. Ba mũi khai thác, không cần thêm engine mới:

1. **Onboarding meds-first** (mục 3.1) → mọi scan sau đó tự nhiên mang tính cá nhân
2. **Timeline lịch uống** (mục 3.5) → tính năng không đối thủ có, engine đã compute
3. **AI-phrasing layer** (optional): LLM diễn giải findings của engine thành hội thoại
   tự nhiên — **constrained to engine output** (pattern của Sahayak: "report generation
   constrained by graph-backed findings"), verdict luôn từ engine, không hallucination.
   Fallback template khi không key. Chi phí ~$0.002/hỏi, tắt được.

→ Không thêm "tính năng" — **bóc trí tuệ có sẵn ra mặt**. Đây là cách app "khôn" lên
mà không tăng nợ kỹ thuật.

## 5. Kinh doanh — mô hình phù hợp nhất với trust-first y tế

| Cấp | Có gì | Giá |
|---|---|---|
| Free | Quét không giới hạn + cảnh báo tương tác + cabinet 1 người | 0 (mồi trust, như Yuka) |
| **Pro** | Family profiles · Receipt audit không giới hạn · AI advisor · Xuất PDF cho bác sĩ · Timeline lịch uống | $3-5/tháng |
| **Revenue phụ** | Smart Swaps → link affiliate mua替代 (mô hình Yuka, không quảng cáo) | % |

Không làm quảng cáo — app y tế + quảng cáo = mất trust = chết.

## 6. Thứ tự làm (sau hosting, trước launch)

| # | Việc | Effort | Tác động |
|---|---|---|---|
| 1 | Onboarding meds-first 3 màn (type-ahead dùng `/api/search`) | ~1 buổi | ⭐⭐⭐ giải quyết gốc rễ #1 |
| 2 | Timeline schedule view (dữ liệu có sẵn `schedule`) | ~1 buổi | ⭐⭐ tính năng độc quyền nổi mặt |
| 3 | AI phrasing layer (optional key, fallback template) | ~1 buổi | ⭐⭐ cảm giác "khôn" |
| 4 | Gọn hero loop: dồn UI về scan-result-action, các phụ lục thu thành tab phụ | ~1 buổi | ⭐⭐ tập trung |
| 5 | Pro modal → thật (IAP/Stripe sau khi có user) | khi có user | $ |

## 7. Câu trả lời cuối cho "bán được không?"

- **Bán được nếu**: hero loop (1) chạy mượt — cá nhân hóa từ lần đầu mở app; và (2) mọi
  câu trả lời giữ chuẩn trung thực hiện có (đó là lý do người ta tin app y tế).
- **Không bán được nếu**: launch với cold-start hiện tại (user mới không nhập thuốc →
  trải nghiệm = "một cái máy tra cứu") — dù data 10 lần cũng vậy.
- Ưu tiên tiếp theo sau deploy: **mục #1 và #2 bảng trên**, không phải thêm nguồn data mới.

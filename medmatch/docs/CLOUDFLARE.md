# Chạy app qua Cloudflare (2 phương án — chọn 1)

## Vì sao KHÔNG đưa "backend lên Cloudflare Workers"

Workers chỉ chạy JS/WASM (isolate V8), không có Python + không đọc file SQLite 298MB.
Muốn "thuần Cloudflare" phải viết lại toàn bộ engine + 71K tương tác sang Workers/D1 —
nhưng ta đã có engine Python 7-lớp chạy chuẩn. Đúng vai trò của Cloudflare cho stack
này là **mạng phía trước (HTTPS + domain + ẩn nguồn)**, không phải nơi chạy code.

## Phương án A — Cloudflare Tunnel từ PC nhà (0 USD, không cần VPS)

Phù hợp: dùng cho bản thân/gia đình/nhóm nhỏ; PC phải bật khi muốn dùng.

```bash
# 1. Tạo tài khoản Cloudflare free → Zero Trust → Networks → Tunnels → Create tunnel
# 2. Tải cloudflared.exe về, chạy lệnh mà dashboard đưa (dạng):
cloudflared service install <TOKEN>
# 3. Trong dashboard map hostname:
#    app.ten-mien-cua-ban.com  →  http://localhost:8765
```

Serverlocal chạy bằng `start.bat`. Kết quả: `https://app.ten-mien.com/scanner/`
— HTTPS thật của Cloudflare, không cert warning, camera OK, IP nhà bị ẩn.
Lưu ý: đi qua proxy Cloudflare nên tắt cache cho /api/* (mặc định CF không cache
response không khai báo — OK dùng luôn).

## Phương án B — VPS + Cloudflare DNS proxy (khuyến nghị cho App Store)

1. VPS chạy `deploy/medmatch.service` + Caddy như APPSTORE.md (origin có HTTPS riêng).
2. DNS record `app.domain.com` → IP VPS, bật **Proxy** (đám mây cam) trong Cloudflare.
   - SSL/TLS mode: **Full (strict)**.
   - Lợi ích: ẩn IP origin, chống DDoS free, cache asset tĩnh `/scanner/assets/*`.

## So sánh nhanh

| | A: Tunnel từ PC | B: VPS + CF |
|---|---|---|
| Phí | 0 USD | ~5 USD/tháng |
| Uptime | PC phải bật | 24/7 |
| Đủ điều kiện App Store review | ⚠ rủi ro (review có lúc máy tắt) | ✓ |
| Camera HTTPS | ✓ | ✓ |

→ Gia đình/bản thân: A ngay hôm nay. Lên App Store: B.

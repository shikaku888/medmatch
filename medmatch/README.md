# MedMatch — Supplement & Drug Safety Checker

Ứng dụng web (mobile-first, PWA-ready) cho thị trường **Mỹ / châu Âu**: quét sản phẩm của người dùng, nhận diện thành phần (TPCN/thảo dược/thuốc), phát hiện **tương tác nguy hiểm** và giải thích rủi ro bằng ngôn ngữ dễ hiểu — kèm nguồn bằng chứng.

> ⚕️ Thông tin tham khảo, KHÔNG phải tư vấn y tế. Xem phần [Pháp lý](#pháp-lý).

## Goal của MedMatch

MedMatch được tạo ra để giúp mỗi người hiểu **nguy cơ của toàn bộ những gì họ
đang dùng** — thuốc kê đơn, thuốc không kê đơn, thực phẩm bổ sung, thảo dược,
thực phẩm, hoạt chất và các sản phẩm mới — trong chính bối cảnh sức khỏe của họ.

Mục tiêu không phải là sở hữu một danh sách sản phẩm lớn, mà là xây dựng một
engine có độ bao phủ ngày càng rộng bằng cách:

- chuẩn hóa mọi sản phẩm về hoạt chất và entity có định danh;
- hợp nhất càng nhiều nguồn dữ liệu hợp pháp, đáng tin cậy và có version càng tốt;
- cá nhân hóa theo thuốc, liều, thời điểm dùng, bệnh nền, thai kỳ, xét nghiệm và
  chức năng gan/thận;
- phân biệt rõ bằng chứng lâm sàng, tín hiệu quan sát được và suy luận cơ chế;
- cảnh báo được cả tương tác đã biết lẫn rủi ro tiềm ẩn, nhưng không biến
  “chưa tìm thấy bằng chứng” thành “an toàn”;
- giải thích được vì sao cảnh báo áp dụng cho từng người và cung cấp đường
  truy nguyên nội bộ cho mọi kết luận.

Nguồn dữ liệu thương mại chỉ được dùng khi có quyền sử dụng phù hợp. UI có thể
hiển thị ngắn gọn, nhưng backend phải giữ provenance, phiên bản, thời điểm cập
nhật và record ID; không được mô tả sai nguồn dữ liệu. Khi bằng chứng chưa đủ,
MedMatch phải nói rõ giới hạn và hướng người dùng đến dược sĩ/bác sĩ thay vì
đưa ra cảm giác an toàn giả.

Đây là **safety-first, coverage-expanding, evidence-traceable** — mục tiêu bất
biến của mọi phase phát triển tiếp theo.


---

## Tóm tắt 3 file plan đã nghiên cứu (`G:\aisuckhoe`)

### plan1.md — Phân tích & cải tiến mở rộng
- **Nguồn dữ liệu cốt lõi**: tapirro/herb-drug-interaction-checker (MIT, 592 tương tác TPCN–thuốc), DDInter 2.0 (240K drug-drug, license NC-SA), MedData API ($29/tháng), PubChem, RxNorm, openFDA.
- **Kiến trúc hybrid RAG**: OCR (iOS Vision) → chuẩn hóa tên (RxNorm/PubChem) → tra tương tác có cấu trúc → truy vấn bằng chứng (vector DB) → AI tổng hợp câu trả lời.
- **Pháp lý**: HIPAA checklist (mã hóa AES-256, BAA, audit log 6 năm), FDA disclaimer VERBATIM (21 CFR § 101.93(c)), SaMD enforcement discretion nếu chỉ "cung cấp thông tin tham khảo", GDPR/CCPA.
- **Growth**: ASO + Apple Search Ads + TikTok UGC + content SEO; freemium 5 lần quét/tháng → Pro $19/tháng → Caregiver $69/tháng.
- **Chi phí MVP**: $8–28/tháng (gần như miễn phí nhờ nguồn open data).

### plan2.md — Tổng hợp nguồn dữ liệu & tối ưu chi phí
- **"Data Union"**: không có API miễn phí duy nhất bao phủ hết → tổng hợp nhiều nguồn, chuẩn hóa & khử trùng lặp.
- **Miễn phí tốt nhất**: SUPP.AI (59,096 tương tác TPCN–thuốc, có evidence DOI), NIH DSLD API, iDISK 2.0, RxNorm, PubChem, Open Food Facts (barcode).
- **Barcode từ Amazon/TikTokShop**: cascade Open Food Facts → UPCitemdb → EcomSource; backup bằng OCR ảnh nhãn + NIH DSLD.
- **Xoay API key**: pattern round-robin / LRU / error-based failover (dùng `apikeyrotator`, `rotato`) — chỉ dùng khi cần, ưu tiên API không giới hạn.

### plan3.md — Kiến trúc tổng hợp hoàn chỉnh
- **Tính năng khác biệt**: suy luận **CYP450 enzyme pathway** → phát hiện tương tác "ẩn" (A ức chế enzyme mà B dùng → cảnh báo dù chưa có tài liệu trực tiếp).
- **Xếp hạng độ tin cậy nguồn** khi mâu thuẫn: FDA/EMA (1.0) > DDInter/SUPP.AI (0.9) > BotanicaAndina/NaPDI (0.8) > KG học thuật (0.7) > suy luận enzyme (0.5).
- **4 lớp dữ liệu**: Bằng chứng → Chuẩn hóa (RxNorm/PubChem/ATC) → Tương tác tổng hợp → Suy luận thông minh.
- **Kế hoạch 3 giai đoạn**: (1) tải & import 100% miễn phí, (2) hợp nhất & khử trùng lặp + engine CYP450, (3) mở rộng liên tục + dược sĩ kiểm chứng.

### Điều MVP này hiện thực hóa
Plan khuyến nghị bắt đầu với **tapirro herb-drug + RxNorm + PubChem** — bản MVP này dùng đúng hướng đó, cộng thêm:
- Toàn bộ 592 tương tác TPCN–thuốc (565 cặp duy nhất) đã được **dịch sang tiếng Anh** (bản gốc tiếng Tây Ban Nha).
- **57 luật drug-drug** (49 class-level + 8 drug-level) biên soạn từ FDA labeling (đây là phần DDInter NC-SA không dùng được cho sản phẩm thương mại — thay bằng luật công khai từ nhãn thuốc FDA).
- Barcode lookup qua **Open Food Facts** (miễn phí, không cần key).

---

## Chạy thử

```bash
cd G:\aisuckhoe\medmatch
pip install -r requirements.txt
python -m backend.db            # seed SQLite (chỉ cần 1 lần)
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
# mở http://127.0.0.1:8765
```

Chạy test dữ liệu:

```bash
pip install -r requirements-test.txt
python -m pytest tests/ -v
```

Quét camera barcode cần Chrome/Edge (BarcodeDetector API); trình duyệt khác nhập tay.

---

## Product Scanner (app tích hợp)

React SPA từ `G:\aisuckhoe\personalized-product-scanner` đã được tích hợp và chạy **cùng 1 server FastAPI** (Express BFF cũ đã bỏ, toàn bộ service được port sang Python trong `backend/scanner/`):

- UI mới: `http://127.0.0.1:8765/scanner/` (tab 🛒 Scanner ở app chính) — quét barcode/OCR nhãn/hóa đơn, tủ skincare, dị ứng chéo, AI chat, smart swaps, cửa hàng.
- Backend: cùng origin — `/api/scan`, `/api/scan/image|text|receipt`, `/api/batch-scan`, `/api/profile`, `/api/family-profiles`, `/api/smart-swaps`, `/api/ai-chat`, `/api/analytics`, `/api/markets`, …
- Dữ liệu scanner: lưu server-side trong `SCANNER_DATA_DIR` theo cookie `mt_device`; local dev mặc định là `backend/data/devices/`, production là `/data/devices`.

## Chuẩn bị deploy public

Runtime image không copy full source DB hoặc raw datasets. `backend/medmatch.db`
và `deploy/runtime/` đều gitignored; build input phải được restore từ một
protected artifact/volume ngoài repository, không commit DB vào source control.
Trên máy ingest/CI có disk lớn hơn VPS:

```bash
python deploy/build_runtime_db.py \
  --source backend/medmatch.cleaned.db \
  --output deploy/runtime/medmatch.db \
  --force
docker build -t medmatch-api:local .
docker save medmatch-api:local | gzip > medmatch-api.tar.gz
```

Chỉ upload các artifact đã kiểm tra sang VPS:

```bash
scp medmatch-api.tar.gz user@vps:/srv/medmatch/
scp deploy/runtime/medmatch.db* user@vps:/srv/medmatch/runtime/
ssh user@vps 'docker load < /srv/medmatch/medmatch-api.tar.gz'
```

Smoke local ở terminal khác:

```bash
curl -f http://127.0.0.1:8080/api/health
curl -f http://127.0.0.1:8080/api/privacy
curl -f http://127.0.0.1:8080/api/provenance
curl -f -X POST http://127.0.0.1:8080/api/analyze \
  -H "Content-Type: application/json" \
  --data '{"items":[{"name":"warfarin","kind":"medication"}],"profile":{}}'
curl -f -X POST http://127.0.0.1:8080/api/scan \
  -H "Content-Type: application/json" \
  --data '{"barcode":"3017620422003"}'
curl -f -X POST http://127.0.0.1:8080/api/user-data/purge
```

Purge phải chạy với cookie smoke riêng, không dùng cookie của người dùng thật.

Backup/restore dùng SQLite online backup, không cần dừng API. Sidecar manifest
được sao chép và cập nhật checksum cho từng artifact; không restore DB mà bỏ
qua manifest.

Fly.io dùng `fly.toml`, volume `medmatch_data` tối thiểu 5 GB và secret
`ADMIN_API_TOKEN` phải được cấu hình ngoài repository. Chỉ chạy `fly deploy`
sau khi image build, runtime DB integrity/checksum và smoke đều pass. Refresh
data là quy trình build snapshot mới rồi deploy, không chạy importer trong API
boot.

VPS Docker Compose dùng Caddy cho HTTPS và giữ API không public trực tiếp:

```bash
mkdir -p /srv/medmatch/runtime /srv/medmatch/devices /srv/medmatch/state /srv/medmatch/graph
chmod 700 /srv/medmatch/devices /srv/medmatch/state /srv/medmatch/graph
cat > .env <<'EOF'
MEDMATCH_DOMAIN=api.example.com
MEDMATCH_RUNTIME_DIR=/srv/medmatch/runtime
MEDMATCH_DEVICES_DIR=/srv/medmatch/devices
MEDMATCH_STATE_DIR=/srv/medmatch/state
MEDMATCH_GRAPH_DIR=/srv/medmatch/graph
ADMIN_API_TOKEN=thay-bang-token-ngau-nhien
EOF

# Copy medmatch.db, medmatch.db.manifest.json, and
# medmatch.db.evaluation.json into /srv/medmatch/runtime first.
docker compose config
docker load < /srv/medmatch/medmatch-api.tar.gz
docker compose up -d
curl -f https://api.example.com/api/health
```

`/srv/medmatch/runtime` chứa snapshot clinical read-only; `/srv/medmatch/devices`
chứa dữ liệu scanner theo thiết bị và có thể chứa PHI; `/srv/medmatch/state`
chứa rate-limit state; `/srv/medmatch/graph` chứa các product facts đã được
admin duyệt từ contribution pipeline. Bốn volume này nằm ngoài image. Không
commit `.env`, token, device data, hoặc bản sao database vào repository. Caddy
tự xin và gia hạn Let's Encrypt certificate; DNS của `MEDMATCH_DOMAIN` phải
trỏ về VPS trước khi khởi động service.

```bash
python deploy/backup_runtime_db.py backup \
  --source /data/medmatch.db \
  --output /backup/medmatch-YYYYMMDD-HHMMSS.db

python deploy/backup_runtime_db.py restore \
  --source /backup/medmatch-YYYYMMDD-HHMMSS.db \
  --target /data/medmatch.db \
  --force
```

Rebuild SPA sau khi sửa frontend:

```bash
cd G:\aisuckhoe\personalized-product-scanner
bun install
SCANNER_BASE=/scanner/ SCANNER_OUT=dist-scanner bun run build
xcopy /E /Y dist-scanner G:\aisuckhoe\medmatch\static\scanner\
```

## Test trên điện thoại (Wi-Fi nhà)

Camera + cài PWA yêu cầu HTTPS → dùng cert self-signed kèm sẵn:

```bat
start_https.bat        # sinh backend/data/dev_cert.pem lần đầu, chạy cổng 8443
```

1. Điện thoại nối **cùng Wi-Fi** với máy tính.
2. Mở `https://<LAN-IP>:8443/scanner/` (IP hiện ra khi chạy script, vd `https://192.168.50.226:8443/scanner/`).
3. Chrome cảnh báo cert → **Advanced → Proceed** (chỉ lần đầu). Sau đó camera barcode, OCR ảnh hoạt động bình thường.
4. Trên Android Chrome: menu ⋮ → *Add to Home screen* để cài như app.

Chế độ HTTP thường cho test trên PC: `start.bat` (cổng 8765).

## Cấu trúc

```
medmatch/
├── backend/
│   ├── app.py            # FastAPI: /api/search, /api/analyze, /api/lookup/{barcode}
│   ├── engine.py         # fuzzy matching + engine tương tác + CYP450 inference
│   ├── db.py             # SQLite schema + seed (rebuild bảo toàn dữ liệu crawl)
│   ├── drug_drug_seed.py # 57 luật drug-drug (49 class-level + 8 drug-level)
│   ├── drug_food_seed.py # 31 luật drug-food + 10 thực phẩm
│   ├── cyp_seed.py       # CYP450 roles (substrate/inhibitor/inducer) cho suy luận
│   ├── rxnorm.py         # map tên thuốc → RxCUI (199 tên, chuẩn hóa xuyên nguồn)
│   ├── suppai.py         # crawl SUPP.AI interactions + evidence (DOI/PMID)
│   ├── scanner/          # Product Scanner backend (port từ Express BFF:
│   │                     #   router.py, storage.py, ext_clients.py,
│   │                     #   personalization.py, herbal_skincare.py,
│   │                     #   advisor.py, parsing.py, medmatch_bridge.py)
│   ├── idisk.py          # import iDISK 2.0 interactions + DSI knowledgebase
│   └── data/             # tapirro JSON gốc + bản dịch + rxnorm_map.json + idisk/
├── static/               # frontend vanilla JS + PWA (manifest, sw.js, OCR)
│   └── scanner/          # Product Scanner SPA build (React, Vite → /scanner/)
├── tests/                # pytest integrity suite
```

## Dữ liệu

| Nguồn | Nội dung | License |
|---|---|---|
| [tapirro/herb-drug-interaction-checker](https://github.com/tapirro/herb-drug-interaction-checker) | 565 tương tác thảo dược–thuốc (đã dịch EN) | MIT |
| FDA labeling (biên soạn thủ công) | 57 luật drug-drug + 8 luật drug-level | Kiến thức công khai |
| [DailyMed](https://dailymed.nlm.nih.gov) (SPL labels, parse tự động) | **803 cặp drug-drug** (465 major) trích từ section DRUG INTERACTIONS của nhãn FDA, kèm trích dẫn label | Public domain (US gov) |
| ~~DDInter 2.0~~ | ❌ **Đã gỡ khỏi commercial build** (1,144 cặp class-level, CC BY-NC-SA). Backup nghiên cứu: `backend/data/_nc_backup/`. Re-import: đặt CSV rồi `python -m backend.ddinter` | ⚠️ CC BY-NC-SA — chỉ dùng research, KHÔNG phân phối
| [Verified Supplement Evidence](https://github.com/erinheit451/verified-supplement-evidence) | 🏆 21 luật **thuốc làm cạn kiệt dinh dưỡng** (statin→CoQ10, PPI→B12/Mg...) + 72 gợi ý sản phẩm | MIT |
| ~~Kaggle drug-food (DrugBank 6.0)~~ | ❌ **Đã gỡ khỏi commercial build** (98 cặp, CC BY-NC). Backup: `backend/data/_nc_backup/drugfood_evidence.json`. Re-import: `python -m backend.drugfood_kaggle` | ⚠️ CC BY-NC — chỉ dùng research
| [PubChem PUG REST](https://pubchem.ncbi.nlm.nih.gov/rest/pug) | 33 hoạt chất marker của 32 thảo dược → CID + CAS + formula (join key cho lớp hợp nhất + dedup: saw_palmetto ≡ pygeum qua β-Sitosterol) | Public domain |
| Lớp hợp nhất (`backend/unify.py`) | `interaction_unified` 22,671 cặp (23,210 rows từ 7 nguồn, 226 severity conflicts) — **commercial build, không NC** + `standard_ingredient` 1,284 + `ingredient_synonyms` 9,086 | Nội bộ |
| [OnSIDES](https://github.com/tatonetti-lab/onsides) | 7,554 cặp (class, drug, tác dụng phụ MedDRA PT) từ 6.9M rows nhãn FDA/EMA/EMC/KEGG | CC BY 4.0 |
| AI verification | 184 cặp được model đánh giá: 125 đúng / 52 sai / 7 không chắc → phát hiện & lọc 59 artifact phủ định | Nội bộ |

Nạp dữ liệu bổ sung (một lần; resume được, idempotent):

```bash
python -m backend.rxnorm                 # map tên thuốc → RxCUI (199 tên)
python -m backend.suppai --delay 0.4     # targeted crawl: 250 herbs
python -m backend.suppai --enumerate     # liệt kê 2,044 TPCN → suppai_agents.json (~40 phút)
python -m backend.suppai_herbs           # tạo herbs mới từ agents (dedup vs tapirro)
python -m backend.suppai --crawl-all     # crawl toàn bộ 59K interactions (~1 giờ)
python -m backend.suppai --remap-local   # map lại NULL class_id offline
python -m backend.suppai --remap-herb-herb  # tách 13K cặp TPCN×TPCN từ dữ liệu
python -m backend.idisk                  # import iDISK interactions + DSI KB
python -m backend.idisk_products         # import 69K sản phẩm + 317K links
python -m backend.faers                  # precompute FAERS counts (openFDA)
python -m backend.quality_gate seed      # tạo review queue cho CYP-inferred
python -m backend.dailymed --mod 4 --idx 0  # parse DailyMed labels (4 shards: idx 0-3)
python -m backend.unify                 # build lớp hợp nhất (unified + synonyms + standards)
```

## Tính năng hiện có

- Kiểm tra tương tác đa nguồn: seeds tapirro (565), FDA drug-drug (57 + 803 DailyMed), SUPP.AI evidence (71,900), iDISK MSKCC (76), drug-food (31), herb-herb (13,355), CYP inference (289 cặp).


- Thực phẩm là entity hạng nhất: thêm "grapefruit", "alcohol", "caffeine"... vào tủ thuốc và check tương tác.
- Phân tích theo thời gian dùng: chọn giờ uống cho từng item; cặp khác giờ hiển thị ghi chú "tách giờ uống giảm rủi ro".
- Báo cáo PDF: nút "Print / Save as PDF" trên kết quả check (print CSS tự tách kết quả).
- Engine suy luận CYP450: phát hiện tương tác "ẩn" qua enzyme pathway — trust 0.5, hiển thị enzyme.
- Caregiver mode: nhiều hồ sơ tủ thuốc, lưu server-side theo cookie `mt_device`
  opaque random (không account).
- PWA: manifest + service worker — cài được lên màn hình chính.
- OCR nhãn: nút "Scan label text" (Tesseract.js lazy-load) — chụp ảnh nhãn, nhận diện thành phần.
- Product search: 69,348 sản phẩm iDISK (NHP Canada) — tìm theo tên, auto-add thành phần vào tủ.
- FAERS counts: số báo cáo sự cố thực tế (openFDA) cho từng thuốc.
- Review queue: tab Review cho dược sĩ duyệt cặp CYP-inferred — Verify (trust → 0.9) / Reject (loại khỏi kết quả).

## Privacy

- Legacy vanilla cabinet/profile data dùng `localStorage`.
- Scanner profile, family profiles và history được gửi tới backend và lưu
  server-side theo cookie `mt_device` opaque random token; hiện chưa có account.
- Full policy được expose tại `/privacy`; UI footer và `GET /api/privacy` dùng
  cùng contract retention/endpoint với policy.

## Pháp lý

- FDA disclaimer hiển thị VERBATIM ở footer + màn kết quả.
- App ở mức "cung cấp thông tin tham khảo" (không chẩn đoán/kê liều) → nằm trong enforcement discretion của FDA; tham vấn luật sư y tế trước khi phát hành App Store.
- Luật drug-drug chỉ là tóm tắt; không đảm bảo đầy đủ.

## Roadmap

Roadmap thực thi hiện tại nằm ở
[`NEXT_WORK_PLAN.md`](NEXT_WORK_PLAN.md#roadmap-hiện-tại--sau-phase-2).
Thứ tự ưu tiên: release/privacy/deploy gate → meds-first onboarding và result
UX → dose/timing/patient safety → beta coverage operations → mobile/business.

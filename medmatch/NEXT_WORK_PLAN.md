# MedMatch — Kế hoạch công việc tiếp theo

> Mục tiêu: hoàn thiện app safety-first chạy được khi public mà **không cần API AI model runtime**.
>
> Nguyên tắc: dữ liệu có provenance; kết quả deterministic; không biến “không tìm thấy” thành “an toàn”; chỉ sửa lỗi phát sinh từ dữ liệu mới hoặc từ kiểm chứng production.

## Goal bất biến của app

MedMatch tồn tại để giúp từng người hiểu nguy cơ của **toàn bộ những gì họ
đang dùng** — thuốc, sản phẩm, hoạt chất trong thực phẩm bổ sung, thảo dược và
thực phẩm — trong đúng bối cảnh sức khỏe của họ.

Mọi phase phải phục vụ cùng một mục tiêu:

- mở rộng độ bao phủ bằng các nguồn dữ liệu hợp pháp, có version và có thể
  truy nguyên;
- chuẩn hóa sản phẩm về hoạt chất/entity trước khi phân tích;
- cá nhân hóa theo thuốc, liều, đường dùng, thời điểm, bệnh nền, thai kỳ,
  xét nghiệm và chức năng gan/thận;
- phân biệt bằng chứng trực tiếp, tín hiệu quan sát và suy luận cơ chế;
- cảnh báo rủi ro một cách hữu ích nhưng không biến “không tìm thấy” thành
  “an toàn”;
- giữ provenance đầy đủ trong backend và không mô tả sai nguồn dữ liệu.

Nguồn trả phí chỉ được tích hợp sau khi xác nhận quyền sử dụng, quyền lưu trữ,
quyền dùng cho sản phẩm thương mại và giới hạn hiển thị. Giao diện có thể gọn,
nhưng mọi finding phải có lineage nội bộ. Khi bằng chứng chưa đủ, hệ thống
phải hạ mức chắc chắn hoặc trả về unknown, không tạo niềm tin giả.

## Kế hoạch triển khai năm phase — tuần tự, không chồng lấn

Mỗi phase phải hoàn thành toàn bộ hạng mục con và đạt exit gate trước khi phase
tiếp theo bắt đầu. Không mở rộng thêm crawler khi contract của phase hiện tại
chưa ổn định.

### Phase 1 — Evidence Provenance

**Mục tiêu:** mọi dữ liệu và mọi cảnh báo đều truy nguyên được.

Hạng mục:

1. Chốt canonical evidence contract: entity, pair, context, outcome,
   evidence level, confidence, source và freshness.
2. Tạo `source_registry`, `source_snapshots`, `evidence_records` và
   `ingestion_runs`; lưu provider, license class, version, checksum, retrieved
   time và record ID.
3. Chuẩn hóa provenance cho seed, DailyMed/openFDA, SUPP.AI, OnSIDES, FAERS,
   PubChem, RxNorm, Mendeley, PharmGKB và mọi source mới.
4. Gắn evidence list vào finding runtime; không làm mất provenance khi
   deduplicate hoặc unify.
5. Phân biệt `documented`, `observational`, `inferred` và `unknown`.
6. Bảo toàn raw snapshot bất biến; parser mới tạo ingestion run mới, không ghi
   đè snapshot đã được kiểm chứng.

**Exit gate:**

- mọi finding đều có source lineage hoặc bị loại khỏi runtime;
- có thể truy từ finding → evidence record → source snapshot → record ID;
- refresh lỗi, checksum sai hoặc source hết hạn không được đánh dấu success;
- test chứng minh không có licensed/research data bị trộn vào commercial layer
  nếu thiếu license metadata.

### Phase 2 — Patient Context

**Mục tiêu:** cùng một cặp hoạt chất có thể tạo risk khác nhau cho từng người.

Hạng mục:

1. Chốt schema patient context versioned: medications, dose, route, frequency,
   timing, supplements, foods, allergies, conditions và age.
2. Tích hợp thật `specialConditions`, pregnancy status/trimester và lactation;
   không chỉ truyền field qua API rồi bỏ qua trong engine.
3. Thêm renal/hepatic staging và nếu có thể thêm eGFR, AST/ALT, INR,
   potassium, magnesium với đơn vị, thời điểm đo và reference range.
4. Chuẩn hóa medication identity theo ingredient, strength, route và
   formulation; giữ brand chỉ là alias.
5. Thêm context rules cho pregnancy, renal/hepatic impairment, QT,
   anticoagulation, diabetes, hypertension, seizure risk, transplant và
   allergy/cross-reactivity.
6. Bắt buộc hiển thị lý do cá nhân hóa: field nào làm risk tăng hoặc giảm.

**Exit gate:**

- cùng một interaction fixture cho hai patient profiles tạo đúng hai risk
  output khác nhau khi context yêu cầu;
- profile thiếu dữ liệu trả `unknown` hoặc screening, không tự suy ra normal;
- dose/route/timing được giữ đến finding và không bị mất khi deduplicate;
- pregnancy, lactation và conditions có test riêng, không chỉ test schema;
- không lưu profile server-side nếu chưa đạt isolation/privacy gate.

### Phase 3 — Licensed Providers

**Mục tiêu:** mở rộng coverage bằng nguồn thương mại nhưng đúng quyền và không
làm hỏng các nguồn công khai hiện có.

Hạng mục:

1. Chốt provider adapter contract: authenticate, fetch, cache, parse,
   normalize, license policy, rate limit và health status.
2. Tạo adapter riêng cho từng provider; không dùng một crawler generic để né
   điều khoản hoặc gom dữ liệu không rõ quyền.
3. Trước mỗi integration phải ghi rõ:
   - quyền dùng nội bộ hay thương mại;
   - quyền lưu raw/derived data;
   - quyền hiển thị source;
   - retention/cache limit;
   - attribution requirement;
   - termination/deletion requirement.
4. Đưa dữ liệu licensed vào private evidence layer nếu hợp đồng chỉ cho phép
   backend use; không xuất raw records ra client.
5. Map hoạt chất bằng RxNorm/UNII/PubChem/InChIKey hoặc mapping thủ công đã
   review; fuzzy match chỉ đưa vào review queue.
6. Theo dõi coverage delta: nguồn mới phải chứng minh thêm coverage hữu ích,
   không chỉ tăng số dòng trùng lặp.

**Exit gate:**

- provider có license metadata và contract test;
- refresh có retry, rate limit, cache, checksum và rollback;
- dữ liệu provider không làm mất nguồn free hoặc làm thay đổi severity mà
   không có conflict record;
- entity normalization rate, duplicate rate và stale rate đạt ngưỡng định
   trước;
- nếu provider ngừng hoạt động, app vẫn trả kết quả với coverage giảm rõ ràng,
   không giả vờ full coverage.

### Phase 4 — Risk Resolution

**Mục tiêu:** biến nhiều nguồn mâu thuẫn thành cảnh báo an toàn, dễ hiểu và
không phóng đại bằng chứng.

Hạng mục:

1. Chốt conflict policy: regulatory label ưu tiên khi đúng context; clinical
   evidence, observational evidence và inference có thứ tự riêng.
2. Tách:
   - `evidenceSeverity`: mức độ bằng chứng/tác động được nguồn mô tả;
   - `personalizedUrgency`: mức cần hành động với patient context hiện tại.
3. Không dùng majority vote mù quáng; lưu toàn bộ source conflicts và lý do
   chọn kết luận runtime.
4. Tạo action gate cho major/contraindicated/high personalized risk:
   avoid, contact pharmacist/doctor, check INR/K/Mg/eGFR hoặc không tự ngừng
   thuốc.
5. Giữ inferred CYP/QT ở dạng screening nếu chưa có bằng chứng trực tiếp;
   không đưa inference ngang hàng với nhãn thuốc.
6. Chuẩn hóa các trạng thái:
   `interaction_found`, `screening_signal`, `no_documented_interaction_found`,
   `unknown_unmatched`.
7. Mọi câu trả lời AI/advisor chỉ được diễn giải finding đã có; verdict không
   được sinh tự do từ LLM.

**Exit gate:**

- conflict fixture cho kết quả deterministic và giải thích được;
- cảnh báo high-risk luôn có action và escalation;
- unknown/unmatched không bị render thành safe;
- mỗi severity/urgency đều truy về evidence và patient factors;
- pharmacist review queue xử lý được inference low-trust trước khi nâng trust.

### Phase 5 — Evaluation Operations

**Mục tiêu:** duy trì chất lượng sau mỗi lần crawl, refresh hoặc thay parser.

Hạng mục:

1. Xây evaluation dataset versioned theo nhóm:
   drug-drug, drug-food, herb-drug, herb-herb, disease contraindication,
   pregnancy, renal/hepatic, QT, allergy, dose và timing.
2. Với từng case lưu expected entities, expected evidence tier, expected
   severity/urgency, expected action và acceptable uncertainty.
3. Đo coverage, precision, recall, normalization rate, unmatched rate,
   duplicate rate, conflict rate, freshness và false-positive rate.
4. Thêm refresh gates: row count, checksum, schema, provenance completeness,
   mapping quality, changed finding review và rollback.
5. Chạy focused tests sau mỗi source; chạy full regression và API/UI smoke
   trước release.
6. Lập audit report cho mỗi release: source versions, ingestion runs,
   coverage delta, known limitations, rejected mappings và reviewer decisions.
7. Theo dõi production misses qua `coverage_events`; ưu tiên bổ sung entity
   theo tần suất và impact, không theo cảm tính.

**Exit gate:**

- mỗi data refresh có report trước/sau;
- regression chặn được severity drift và accidental source loss;
- có bộ case high-risk được review thủ công;
- mọi release đều tái tạo được finding từ snapshot và parser version;
- có rollback rõ ràng khi source mới làm precision hoặc safety giảm.

## Thứ tự thực hiện bắt buộc

1. Hoàn tất Phase 1 trước: không thêm provider mới khi provenance chưa đầy đủ.
2. Hoàn tất Phase 2 tiếp theo: đặc biệt là conditions, pregnancy/lactation và
   dose/labs; đây là phần quyết định tính “mỗi người một rủi ro”.
3. Chỉ sau đó mở Phase 3 để tích hợp nguồn thương mại hợp pháp.
4. Phase 4 xử lý conflict, severity, urgency và action trước khi quảng bá độ
   bao phủ.
5. Phase 5 trở thành gate bắt buộc của mọi lần refresh về sau, không phải công
   việc làm một lần cuối dự án.

Không đo thành công bằng số lượng record crawl được. Đo bằng số entity được
chuẩn hóa, số finding có bằng chứng truy nguyên, coverage hữu ích, precision,
recall, độ tươi và khả năng giải thích đúng cho từng patient context.


## 0. Trạng thái tại thời điểm dừng
# Audit ledger — current workspace

The sections below preserve the original planning notes. This ledger is the
source of truth for the current implementation status and prevents treating
completed work as pending.

| Area | Status | Evidence |
|---|---|---|
| P0.1 profile/history isolation | DONE | Device-scoped storage, no-identity memory DB, concurrent isolation tests |
| P0.2 unknown/no-documentation semantics | DONE | `no_documented_interaction_found`, `unknown_unmatched`, UI unmatched display |
| P0.3 ingredient identity and mapping review | DONE | RxNorm/component mapping, trusted runtime gate, review queue and report |
| P0.4 FAERS adverse-event API | DONE | Deduplicated aggregate, role counts, quarter filter, causality limitations |
| P0.5 label safety APIs | DONE | Label, warnings, contraindications, population sections with provenance |
| P1.1 OnSIDES full release | DONE | v3.1.1 raw `21,343,508`, aggregate `126,773`, ingredient endpoint, exact-RxNorm intersection `1,439` |
| P1.2 CYP450 | PARTIAL | `1,023` roles including `2E1`; engine inference contract and role semantics need final audit |
| P1.3 Mendeley Drug-Food | PARTIAL | `9,276` raw rows and evidence endpoint; constituent ontology mapping remains intentionally absent |
| P1.4 LactMed | DONE (local) | Official NCBI FTP NXML imported: `1,957` records; local lactation endpoint returns structured reference sections |
| P1.5 ClinPGx/PharmGKB | PARTIAL | `127,786` relations and endpoints; no genotype-based clinical recommendation |
| P1.6 population context | PARTIAL | Engine đã có patient-context v1, urgency/reasons và tests; UI collection, risk-rule coverage và context display còn thiếu |
| P1.7 canonical evidence provenance | DONE | Additive schema, deterministic IDs, source alias/release reconciliation; 61,123 findings, 63,344 active evidence, 12,793 accepted findings, 48,330 candidates, 35,223 CYP derivation links |
| P1.8 supplemental safety sources | DONE (local) | CAERS `151,589` reports/`428,229` aggregates; FDA recalls `47,216`; DrugCentral structures/ATC/target facts; runtime endpoints and freshness metadata |
| P2 hardening | PARTIAL | Privacy, rate limits, provenance and outbound references exist; deployment/claims audit remains |

### Explicit remaining gaps and limitations

- OpenFDA targeted refresh is now complete for `sirolimus`: manifest status `ok`,
  `attempts=3`, and `26` current label records.
- The ontology intersection is deliberately ingredient-level. It joins source
  families by exact RxNorm IN/PIN identity; it does not merge OnSIDES MedDRA
  effects with FAERS terms or free-text label sections without a validated
  crosswalk.
- `label_section` currently contains populated `warnings` and `drug_interactions` columns; absent pregnancy, renal, hepatic and pediatric sections must remain `unknown`.
- The local LactMed layer covers breastfeeding reference sections, but does not replace clinical review of infant age, prematurity, dose, timing, or maternal/infant conditions.
- DrugCentral 2023 selected tables provide ATC and target/MOA enrichment; its dump has no indication relation, so `/indications` remains explicitly outbound-reference-only.
- Current NDC directory records expose active ingredients but no inactive-ingredient field; excipient count is therefore zero until an authoritative SPL excipient source is imported.
- CAERS and FDA recall matches are product/name signals; absence of a match is not a safety clearance.

## Roadmap hiện tại — sau Phase 2

Roadmap này là thứ tự ưu tiên thực tế của workspace hiện tại. Không mở rộng
provider hoặc monetization trước khi release gate và safety UX đạt.

### R0 — Release hardening và public deploy (P0, blocker)

**Mục tiêu:** có một bản deploy công khai, reproducible, không làm mất dữ liệu
hoặc biến lỗi vận hành thành kết quả “an toàn”.

- Tách runtime database khỏi raw/staging data. `backend/medmatch.db` hiện là
  `14,798,082,048` bytes, trong khi `fly.toml` chỉ cấp volume `3gb`; Docker
  không thể tiếp tục copy nguyên DB này vào image.
- Tạo slim canonical runtime snapshot; raw artifacts và staging giữ ngoài image,
  có checksum/version/rollback pointer.
- Tách import job writable khỏi API process read-only. `deploy/start.sh` hiện
  chạy importer ở mỗi boot rồi mới bật `MEDMATCH_DB_READ_ONLY=1`; chuyển import
  sang release job hoặc migration step có lock.
- Deploy Fly/VPS với HTTPS, backup DB, log rotation, health check và smoke API.
- Đưa rate limit ra edge/shared store khi chạy nhiều worker; kiểm tra cookie
  device, body limits, CORS, admin token và purge flow.
- README and privacy policy now state scanner data is server-side in the
  device-token namespace; the legacy vanilla cabinet remains explicitly
  localStorage-only.

**Đã xử lý trong local release gate:**

- Snapshot builder ghi manifest checksum/version và giữ bản accepted trước đó
  ở `medmatch.db.previous`; refresh lỗi không thay thế snapshot accepted.
- API rate limit dùng SQLite shared store trong volume, có `TRUST_PROXY_HEADERS`
  tùy chọn cho edge proxy và trả lỗi `503` nếu store không khả dụng.
- Backup/restore sao chép sidecar manifest và cập nhật checksum theo artifact.

**Exit gate:**

- Image/runtime snapshot nằm trong giới hạn storage và build lặp lại được.
- Import lỗi không làm hỏng accepted snapshot; rollback đã diễn tập.
- Domain HTTPS chạy health, provenance, analyze, scan và purge.
- Không có claim privacy mâu thuẫn giữa README, UI và privacy policy.

**Tiến độ:** builder đã tạo snapshot `deploy/runtime/medmatch.db` với 62 bảng,
10,402,105 bản ghi, 44 index và `integrity=ok`; kích thước output
`2,964,180,992` bytes từ source `14,798,082,048` bytes. Manifest có checksum,
version và rollback pointer; local Docker image đã build và smoke qua health,
privacy, provenance, analyze, scan và purge. Backup/restore đã xác minh
checksum sidecar trên fixture. Public deploy, volume thật, backup/restore
production và domain smoke vẫn còn pending.

### R1 — Hero loop: onboarding → scan → action (P0)

**Mục tiêu:** user mới nhận giá trị ngay lần đầu, không gặp cold-start “không
thấy tương tác”.

- Onboarding 3 màn: nhập thuốc trước, type-ahead qua `/api/search`, xác nhận
  ingredient/class, sau đó mới quét sản phẩm.
- Hiển thị rõ context đang áp dụng: profile, thuốc, dose/route/timing,
  pregnancy/lactation, conditions và missing context.
- Surface `personalization.reasons` và `personalizedUrgency` trong result card;
  giữ `evidenceSeverity` riêng, không đổi severity nguồn theo patient context.
- Hiển thị unknown/miss và đường dẫn “thử OCR / nhập tên / góp ý sản phẩm”,
  tuyệt đối không render miss thành safe.
- Đưa Smart Swaps và action “contact pharmacist/doctor/check INR…” lên cùng
  result, không chôn trong tab phụ.

**Exit gate:**

- User mới hoàn thành onboarding và có kết quả đầu tiên trong tối đa 3 phút.
- Pregnancy, lactation, renal/hepatic và conditions đều hiển thị lý do khi
  làm urgency tăng.
- Thiếu profile field hiển thị unknown, không tự điền normal.
- Mobile smoke 393px không overflow và không mất cảnh báo/action.

### R2 — Dose/timing và patient safety UX (P1)

**Mục tiêu:** biến context đã có trong engine thành quyết định dễ dùng, không
đưa ra prescribing instruction.

- Cho mỗi medication nhập ingredient, strength, dose, unit, route,
  formulation, frequency và timing.
- Vẽ schedule timeline từ `schedule_for`; chỉ khuyến nghị tách giờ khi
  mechanism là absorption/timing-fixable.
- Hiển thị lab context có đơn vị/thời điểm/reference range; action phù hợp là
  “review/check with clinician”, không tự tính liều.
- Bổ sung test riêng cho dose/route/timing, INR, eGFR, AST/ALT, K/Mg,
  pregnancy trimester, lactation và allergy/cross-reactivity.
- Giữ family profiles device-scoped; không chuyển PHI sang server account trước
  khi hoàn tất isolation/privacy review.

**Exit gate:**

- Hai profile trên cùng fixture cho hai urgency/action khác nhau và giải thích
  được factor.
- Dose/route/timing/lab metadata còn nguyên sau matching và deduplication.
- Không có UI copy nào khuyên tự ngừng thuốc hoặc tự thay đổi liều.

### R3 — Beta 50 users và coverage operations (P1)

**Mục tiêu:** đo precision/coverage thật trước khi thêm data hoặc tính năng.

- Bật coverage dashboard admin với top misses đã redacted; thêm nút “missing
  product” từ barcode/brand/OCR miss.
- Version evaluation fixtures: drug-drug, drug-food, herb-drug, pregnancy,
  renal/hepatic, QT, allergy, dose và timing.
- Theo dõi hit-rate, unmatched-rate, duplicate-rate, severity drift,
  stale-rate, crash-free days và latency p50/p95.
- Weekly review top misses; chỉ thêm alias/mapping có evidence và regression.
- Refresh accepted canonical release theo runbook; candidate/restricted source
  không đi vào runtime.

**Exit gate:**

- Hit-rate nhóm sản phẩm beta đạt tối thiểu 85%.
- Không crash trong 7 ngày beta.
- Mỗi refresh có before/after report, checksum, lineage và rollback result.

### R4 — App Store và business (P2, sau R3)

- Apple Developer/TestFlight và Android build chỉ sau khi public web beta ổn
  định.
- Quyết định Pro sau khi có retention/usage thật; không dựng paywall trước.
- Nếu thu tiền: phân định rõ account, billing, deletion/export, support và
  PHI boundary; không coi device token là account.
- Affiliate Smart Swaps chỉ cho candidate đã qua verification và disclosure.

**Không làm trước:** crawler/provider mới, LLM verdict tự do, bulk-copy
LactMed/licensed content, hoặc account sync chứa health profile.


## Execution order

1. **R0 release hardening:** shrink/package DB, separate importer job, backup,
   HTTPS, shared rate limiting, privacy/claims audit.
2. **R1 hero loop:** meds-first onboarding, context display, reasons, unknown/miss
   UX, Smart Swaps/action placement.
3. **R2 safety UX:** dose/route/formulation/frequency, schedule timeline, labs,
   patient-context rules and mobile smoke.
4. **R3 beta operations:** evaluation fixtures, coverage telemetry, top-miss loop,
   refresh reports, 85% beta hit-rate and 7 crash-free days.
5. **R4 distribution/business:** TestFlight/Android, pricing, account/billing and
   affiliate decisions only after beta evidence.


### Operational refresh runbook

1. Snapshot `backend/medmatch.db` and verify free disk space.
2. Import/refresh one source into its own tables; never delete the current
   validated snapshot before the replacement passes row-count and checksum
   checks.
3. For a targeted OpenFDA label refresh:
   ```bash
   python -m backend.refresh_openfda --drug sirolimus
   ```
4. For the OnSIDES full release:
   ```bash
   python -m backend.onsides backend/data/onsides/onsides-v3.1.1.zip --full
   ```
5. Rebuild canonical mappings, unified interactions and the source intersection:
   ```bash
   python -m backend.unify
   python -m backend.evidence_ontology
   ```
6. Run focused source tests, then the full regression:
   ```bash
   python -m pytest tests/test_onsides_full.py tests/test_integrity.py -q --basetemp=.pytest-basetemp
   python -m pytest tests/ -q --basetemp=.pytest-basetemp
   ```
6. Start the API and verify `/api/health`, `/api/provenance`,
   `/api/unified/stats`, and source-specific endpoints before deployment.
7. Review `crawl_manifest` for non-OK rows; do not call a refresh complete
   while any failed item remains unexplained or explicitly waived.

### Runtime

- API đang chạy tại `127.0.0.1:8765`.
- Health endpoint đúng là `GET /api/health`.
- OCR dùng RapidOCR/ONNX local, không cần API key AI.
- `/api/ai-chat` hiện là deterministic advisor; Gemini polish đã disable.
- `/api/smart-swaps` dùng rule/catalog, không dùng model runtime.
- Runtime vẫn có external data calls cho Open Food Facts/USDA/UPCitemdb; đây là dependency dữ liệu, không phải AI model.

### Database snapshot đã xác minh

| Thành phần | Số lượng |
|---|---:|
| `herbs` | 1.216 |
| `drug_classes` | 1.650 |
| `interactions` | 565 |
| `drug_drug` rules | 57 |
| `suppai_interactions` | 71.900 |
| `herb_herb_evidence` | 13.355 |
| `dailymed_interactions` | 763 |
| `openfda_ddi` | 771 |
| `onsides_effects` legacy class aggregate | 7.554 |
| `onsides_effects_raw` full v3.1.1 | 21.343.508 |
| `onsides_ingredient_effects` full aggregate | 126.773 |
| `onsides_high_confidence` | 342 |
| `fda_reaction` raw | 5.609.664 |
| `faers_adverse_events` aggregate | 7.977.006 |
| `label_section` | 262.271 |
| `pharmgkb_relations` | 127.786 |
| `cyp_roles` | 1.023 |
| `interaction_unified` | 61.123 |
| `standard_ingredient` | 3.927 |
| `ingredient_synonyms` | 34.977 |
| Zenodo DDI raw | 36.581 |
| Mendeley Drug-Food raw | 9.276 |

### Đã hoàn tất trong vòng dữ liệu mới

- `backend/import_zenodo_ddi.py`
  - Import `backend/data/zenodo_ddi_2026.csv`.
  - Bảng riêng: `zenodo_ddi_2026`.
  - License source: CC BY 4.0.
- `backend/import_cyp450_figshare.py`
  - Import positive substrate labels từ đủ 6 file Figshare.
  - Database hiện có `1A2`, `2C9`, `2C19`, `2D6`, `3A4`, `2E1` và `p_gp`
    trong `cyp_roles`; substrate evidence không bị biến thành inhibitor.
- `backend/import_mendeley_drug_food.py`
  - Import raw evidence vào `mendeley_drug_food_2021` (`9.276` rows).
  - Runtime giữ constituent evidence riêng, không ép vào food category heuristic.
- `backend/onsides.py`
  - Full OnSIDES v3.1.1 đã import vào `onsides_effects_raw`
    (`21.343.508` rows) và `onsides_ingredient_effects` (`126.773` aggregates).
  - `onsides_effects` (`7.554`) chỉ còn là legacy class aggregate.
- `backend/unify.py`
  - Đưa các Zenodo DDI rows map được vào unified layer bằng mapping exact/component
    bảo thủ; fuzzy candidates chỉ vào review queue.
- `backend/db.py`
  - `cyp_roles` không còn bị xóa khi rebuild.
  - Seed CYP dùng `INSERT OR IGNORE`, tránh duplicate-key và giữ enrichment đã import.
- Product index đã rebuild.
- Regression gần nhất: `64 passed, 2 skipped`.

## 1. Không làm lại

- Không chạy full DailyMed crawl theo từng thuốc một lần nữa.
- Không crawl lại SUPP.AI, DSLD, NDC, iDISK, FAERS khi chưa có câu hỏi coverage cụ thể.
- Không import DDInter/Kaggle Drug-Food vào commercial build vì license NC/NC-SA.
- Không dùng CredibleMeds raw nếu chưa có commercial license.
- Không thêm LLM chỉ để diễn giải text. Facts phải đi từ engine và evidence.

---

# 2. Ưu tiên P0 — bắt buộc trước public

## P0.1. Cô lập profile/history theo user hoặc bỏ server-side storage

### Vấn đề

`get_user_db()` fallback về token `anonymous`, nhưng middleware trong `backend/app.py` hiện không tạo/set `mt_device` cookie dù đã import `set_device_token`.

Profile, family profiles, history, routine và analytics có nguy cơ dùng chung file giữa người dùng public.

### Quyết định cần thực hiện

Chọn một trong hai hướng, ưu tiên hướng A:

- **A — local-first thật sự:** profile/history/routine lưu ở browser/device; backend chỉ xử lý request stateless.
- **B — server profile:** tạo device/session token an toàn, cookie HttpOnly/SameSite/Secure, storage keyed theo token, giới hạn retention và có cơ chế xóa dữ liệu.

Không dùng một JSON file chung cho tất cả public users.

### Acceptance criteria

- Hai client độc lập không đọc được profile/history của nhau.
- Không có request nào thiếu identity mà vẫn ghi vào storage chung.
- Test concurrent request không trộn ContextVar hoặc cache instance.
- Có privacy statement cho profile, medications, allergies và scan history.

## P0.2. Sửa semantics “không có tương tác”

### Vấn đề

Advisor hiện có thông điệp tương đương “nothing documented against this combination”. Người dùng có thể hiểu là an toàn tuyệt đối.

### Thay đổi

Dùng trạng thái rõ ràng:

```json
{
  "result": "no_documented_interaction_found",
  "coverage": "partial",
  "checkedSources": [
    "FDA labels",
    "OnSIDES",
    "FAERS",
    "SUPP.AI",
    "RxNorm"
  ],
  "unmatched": [],
  "message": "Không tìm thấy tương tác trong các nguồn hiện đang kiểm tra; điều này không chứng minh kết hợp là an toàn."
}
```

Phân biệt:

- `safe` — chỉ dùng nếu có rule xác nhận an toàn, hiện chưa nên dùng.
- `no_documented_interaction_found` — không thấy trong coverage hiện tại.
- `unknown_unmatched` — chưa chuẩn hóa được ingredient.
- `interaction_found` — có evidence.

### Acceptance criteria

- Advisor không gọi “good news” nếu còn unmatched.
- UI hiển thị số item chưa nhận dạng.
- Mỗi kết quả có source coverage và data freshness.

## P0.3. Thêm ingredient-level identity

### Vấn đề

Một phần DDI hiện map vào drug class. Class-level alert có thể over-generalize và Zenodo DDI hiện chỉ map được:

- 36.581 raw rows.
- 3.722 rows có cả hai phía map được.
- 1.761 class pairs.

### Mapping bắt buộc

```text
raw drug name
→ RxNorm RxCUI / RxNorm ingredient
→ standard active ingredient
→ UNII/PubChem/ATC nếu có
→ drug class dùng cho rule fallback
```

### Schema đề xuất

```sql
CREATE TABLE IF NOT EXISTS drug_name_mapping (
    source TEXT NOT NULL,
    raw_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    rxcui TEXT,
    confidence REAL NOT NULL,
    match_method TEXT NOT NULL,
    reviewed INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (source, raw_name)
);
```

Không dùng fuzzy matching để tạo cảnh báo major. Fuzzy match chỉ dùng làm review queue.

### Acceptance criteria

- Có report mapped/unmapped theo source.
- Mỗi DDI alert biết là ingredient-level hay class-level.
- DDI không tạo pair khi hai tên map vào cùng active ingredient.
- Có evidence source và interaction text gốc.

## P0.4. Tạo adverse-event API từ dữ liệu đã có

### Dữ liệu nền

`fda_reaction` đã có 5.609.664 rows, `fda_report` có case metadata và `fda_drug` có drug role/name.

### Endpoint đề xuất

```text
GET /api/drug/{drug_id}/adverse-events?limit=30
GET /api/drug/{drug_id}/adverse-events?quarter=2026Q2
GET /api/class/{class_id}/adverse-events?limit=30
```

### Response tối thiểu

```json
{
  "drug_id": "...",
  "events": [
    {
      "term": "...",
      "case_count": 123,
      "serious_case_count": 45,
      "first_seen": "...",
      "last_seen": "...",
      "source": "FDA FAERS"
    }
  ],
  "limitations": [
    "Spontaneous reports do not prove causality.",
    "Counts are not incidence or absolute risk."
  ],
  "updated_at": "..."
}
```

### Cần xử lý

- Join drug name/product ingredient với RxNorm/standard ingredient.
- Deduplicate case/version đúng cách.
- Phân biệt `PS`, `SS`, `C` trong `role_cod`.
- Aggregate theo unique case, không đếm từng reaction row như unique patient.
- Index theo normalized drug name, `prod_ai`, `pt`, `quarter`.
- Không dùng FAERS count để tự động tạo `major` severity.

### Acceptance criteria

- Có endpoint cho ít nhất một drug đã biết.
- Có test chống đếm trùng case.
- Có disclaimer causality trên API/UI.
- Có timestamp và quarter.

## P0.5. Expose label safety sections

### Dữ liệu nền

`label_section` đã có 262.271 rows, hiện chủ yếu lưu `drug_interactions` và `warnings`. App chưa expose đủ nội dung label.

### Sections cần chuẩn hóa

- Boxed warning.
- Contraindications.
- Warnings and precautions.
- Adverse reactions.
- Drug interactions.
- Pregnancy.
- Lactation.
- Pediatric use.
- Geriatric use.
- Renal impairment.
- Hepatic impairment.
- Overdosage.
- Dosage and administration.

### Endpoint đề xuất

```text
GET /api/drug/{drug_id}/label
GET /api/drug/{drug_id}/warnings
GET /api/drug/{drug_id}/contraindications
GET /api/drug/{drug_id}/populations
```

### Response cần có

```json
{
  "drug_id": "...",
  "sections": [
    {
      "section": "contraindications",
      "text": "...",
      "set_id": "...",
      "effective_time": "20260715",
      "source_url": "...",
      "source": "DailyMed/OpenFDA"
    }
  ]
}
```

Không cho UI biến label excerpt thành lời kê đơn. Đây là reference information.

---

# 3. Ưu tiên P1 — bổ sung coverage lớn

## P1.1. Import OnSIDES full release

### Trạng thái hiện tại

Full OnSIDES v3.1.1 đã được crawl/import và validate:

- `onsides_effects_raw`: `21.343.508` rows.
- `onsides_ingredient_effects`: `126.773` ingredient/effect aggregates.
- `onsides_high_confidence`: `342` high-confidence pairs.
- Geography: US/EU/UK/JP.
- Local release archive: `backend/data/onsides/onsides-v3.1.1.zip`.
- Runtime endpoint: `GET /api/drug/{drug_id}/adverse-effects`.

`onsides_effects` với `7.554` rows là legacy class aggregate, không phải
full-release coverage.

### License

- Data: CC BY 4.0.
- Software: MIT riêng biệt.
- Cần attribution, link license và ghi rõ modifications.

### Đã hoàn tất

- Bảng raw/source riêng, không xóa legacy aggregate.
- Map product → RxNorm product → RxNorm ingredient.
- Lưu source geography, label id, MedDRA term/id và prediction fields.
- Aggregate ingredient-effect phục vụ API.

### Còn lại

- Tạo intersection view/table giữa OnSIDES và các evidence source khác để
  đánh dấu multi-source support mà không đổi severity tự động.

### Acceptance criteria

- Có số liệu before/after theo ingredient/effect.
- Không import MedDRA mapping thiếu license mà không ghi provenance.
- Có endpoint drug-level adverse events.
- High-confidence intersection được đánh dấu riêng.

## P1.2. Hoàn thiện CYP450

### Hiện trạng

Figshare đã import positive substrate labels cho 6 enzyme; database có
`1A2`, `2C9`, `2C19`, `2D6`, `3A4`, `2E1` và `p_gp` trong `cyp_roles`.
Engine format/inference xử lý enzyme theo dữ liệu role, không dùng label âm
như evidence an toàn.

### Việc còn lại

- Thêm test contract riêng cho `2E1` substrate evidence.
- Giữ rõ role `substrate`, `inhibitor`, `inducer`; không suy diễn inhibitor
  từ substrate-only data.

### Nguồn

- Dataset: https://doi.org/10.6084/m9.figshare.26630515.v4
- Metadata: https://api.figshare.com/v2/articles/26630515
- License: CC BY 4.0.

## P1.3. Mendeley Drug-Food theo evidence riêng

### Hiện trạng

`mendeley_drug_food_2021` có 9.276 rows. Dữ liệu là food constituent ↔ drug constituent, không phải trực tiếp common food category ↔ drug class.

### Không làm

- Không substring-match mọi “food constituent” vào grapefruit/alcohol/dairy.
- Không tự gán major severity.

### Hướng đúng

Tạo endpoint evidence riêng:

```text
GET /api/drug/{drug_id}/food-evidence
```

Hiển thị:

- food constituent;
- drug constituent;
- interaction text;
- SMILES/CID nếu map được;
- evidence source;
- confidence;
- “research evidence”, không phải FDA contraindication.

Sau đó mới xây ontology:

```text
food constituent
→ PubChem CID
→ food ontology/category
→ normalized drug ingredient
```

### Nguồn

- https://data.mendeley.com/datasets/xgyt8fhgps/1
- License: CC BY 4.0.

## P1.4. LactMed cho breastfeeding

### Giá trị

- Drug level trong breast milk.
- Infant exposure.
- Infant adverse effects.
- Therapeutic alternatives.
- Literature references.

### Nguồn

- https://www.ncbi.nlm.nih.gov/books/NBK501922/
- Terms pointer: https://integrationacademy.ahrq.gov/resources/19391

### Feature

```text
GET /api/drug/{drug_id}/lactation
```

Profile cần có:

```json
{
  "lactation": true,
  "infant_age_months": 4
}
```

Không dùng pregnancy status để suy luận lactation status.

## P1.5. ClinPGx/PharmGKB

### Hiện trạng

DB đã có 127.786 PharmGKB relations, nhưng chưa có user flow genotype/phenotype và chưa có endpoint recommendation rõ ràng.

### Feature đề xuất

```text
GET /api/drug/{drug_id}/pharmacogenomics
POST /api/pharmacogenomics/check
```

Chỉ trả recommendation khi user cung cấp genotype/phenotype. Không cảnh báo PGx dựa trên tên thuốc đơn thuần.

### License

- ClinPGx/PharmGKB: CC BY-SA 4.0.
- Attribution và share-alike bắt buộc.
- https://www.clinpgx.org/page/dataUsagePolicy
- https://www.clinpgx.org/

## P1.6. Pregnancy, renal, hepatic và pediatric context

### Profile fields cần chuẩn hóa

```json
{
  "age": 68,
  "pregnancy": {
    "status": "pregnant",
    "weeks": 18
  },
  "lactation": false,
  "kidneyFunction": {
    "status": "moderate_impairment",
    "egfr": 42
  },
  "liverFunction": {
    "status": "normal",
    "childPugh": null
  },
  "allergies": ["penicillin"],
  "medications": [
    {
      "name": "warfarin",
      "dose": "5 mg",
      "route": "oral",
      "frequency": "daily"
    }
  ]
}
```

### Rule safety

- Thiếu context → `unknown`, không suy luận “normal”.
- Pregnancy warning lấy từ label/authoritative source.
- Kidney/liver warnings lấy từ section cụ thể; không tự tính dose nếu chưa có validated dosing rule.
- Pediatric và geriatric alerts cần age boundary rõ ràng.

---

# 4. Ưu tiên P2 — nguồn bổ trợ, không block public MVP

## P2.1. Open Targets

Phù hợp cho:

- drug-target relationship;
- drug-disease/indication context;
- explanation và research enrichment.

Không dùng làm nguồn chính cho DDI.

- https://platform.opentargets.org/
- License documentation: https://platform-docs.opentargets.org/licence
- Open Targets generated data được nêu là CC0; vẫn phải kiểm tra upstream source license.

## P2.2. QT risk

Không dùng CredibleMeds raw nếu chưa có license commercial.

Hướng an toàn hơn:

- label-derived QT warnings;
- FAERS QT signal chỉ là signal;
- open TQT dataset để research/triage;
- hiển thị screening warning, không tuyên bố clinical-grade risk score.

## P2.3. MedlinePlus

Dùng link outbound/reference trước; không bulk-copy drug information nếu chưa kiểm tra quyền nội dung.

- Drug/supplement index: https://medlineplus.gov/druginformation.html
- Content terms: https://medlineplus.gov/about/using/usingcontent

## P2.4. LiverTox

Có giá trị cho drug-induced liver injury và herbal hepatotoxicity. Hiện research xác nhận site freely available, nhưng cần kiểm tra điều khoản bulk redistribution trước khi embed nguyên văn.

- https://www.ncbi.nlm.nih.gov/books/NBK548196
- https://www.ncbi.nlm.nih.gov/books/NBK547852

---

# 5. Feature matrix cần có trước public

| Feature | Data source | Engine/API status | Priority |
|---|---|---|---|
| Drug-drug interaction | FDA labels, Zenodo DDI, existing rules | Có class-level; ingredient mapping còn thiếu | P0 |
| Herb-drug interaction | SUPP.AI, iDISK, tapirro | Có | P0 |
| Herb-herb interaction | SUPP.AI | Có | P1 |
| Drug-food | FDA rules + Mendeley raw | Có 31 rules; Mendeley chưa expose | P1 |
| Adverse reactions | FAERS raw + OnSIDES + CAERS | Drug-level FAERS/OnSIDES and supplement CAERS endpoints available; causality disclaimer retained | P0 |
| Contraindications | Label sections | Data có; endpoint available | P0 |
| Boxed warnings | DailyMed/OpenFDA labels | Endpoint available; absent sections remain unknown | P0 |
| Pregnancy | Label sections | Profile/rules thiếu | P1 |
| Lactation | NLM LactMed NXML | 1,957 local records; structured endpoint available | P1 |
| Renal impairment | Label sections | Profile có một phần; rule thiếu | P1 |
| Hepatic impairment | Label sections | Profile có một phần; rule thiếu | P1 |
| Pediatric | Label + OnSIDES-PED nếu có | Chưa có flow đầy đủ | P1 |
| Geriatric/Beers | SAHAYAK + rules | Có nhưng coverage còn mỏng | P1 |
| QT risk | SAHAYAK + label | Có screening mỏng | P2 |
| CYP450 | Seed + Figshare positives | Có; 2E1 chưa hỗ trợ | P1 |
| Pharmacogenomics | ClinPGx/PharmGKB | Data có; user flow thiếu | P1 |
| Allergy/excipients | NDC/DSLD/product label | Active NDC imported; inactive field absent in current release, no guessed excipients | P0 |
| Duplicate ingredient | RxNorm/NDC/DSLD | Cần thêm active-moiety dedupe | P0 |
| Product barcode | DSLD/NDC/Open Food Facts | Có local-first + network fallback | P0 |
| ATC classification | DrugCentral | `/api/drug/{id}/atc`, 5,148 mappings | P1 |
| Mechanism/targets | DrugCentral | `/api/drug/{id}/mechanism`, target/action/MOA facts | P1 |
| Product recalls | openFDA enforcement | `/api/drug/{id}/recalls`, drug + food 47,216 records | P1 |

---

# 6. Public API hardening

## 6.1. Rate limits và payload

- Giới hạn body `/api/scan/receipt` và `/api/batch-scan`.
- Giới hạn số item `/api/analyze`.
- Rate limit theo IP/device cho barcode/search.
- Timeout và circuit breaker cho Open Food Facts/USDA/UPCitemdb.
- Không để external API fail làm mất kết quả local.

## 6.2. SQLite/runtime

- Runtime app đọc DB read-only nếu có thể.
- Crawler/rebuild chạy process riêng.
- Không rebuild DB khi API đang phục vụ traffic.
- Checkpoint WAL sau rebuild ở maintenance window.
- Lưu sha256 và release version cho data artifacts.
- Backup trước mỗi import.

## 6.3. CORS và deployment

- Nếu frontend cùng origin: giữ same-origin.
- Nếu mobile/remote frontend: cấu hình CORS allowlist, không dùng `*` với credentials.
- `/api/health` không yêu cầu auth.
- Admin review endpoints phải có auth; không public `/api/review/*`.

## 6.4. Privacy/legal

- Không gửi medications/allergies/profile đến AI model.
- Không lưu PHI server-side nếu không cần.
- Có privacy policy, retention, delete/export flow.
- Hiển thị source attribution của CC BY/CC BY-SA.
- Có disclaimer FAERS: report không chứng minh causality, không phải incidence/risk.
- Có disclaimer app là reference, không chẩn đoán/kê đơn.

## 6.5. Smart swaps

Các claim curated hiện có cần audit:

- “glyphosate residue-free certified”;
- “lower glycemic spike”;
- “sensitive skin safe”;
- certification/brand claims khác.

Nếu không có source cụ thể:

- bỏ claim;
- hoặc đánh dấu merchandising metadata;
- hoặc chỉ trả candidate ingredients + engine verification.

Không để fallback curated product được hiểu là medical recommendation.

---

# 7. Test plan

## Unit/integrity

```bash
python -m pytest tests/test_integrity.py tests/test_release_slice.py --basetemp=.pytest-basetemp
```

Cần thêm test cho:

- no documented interaction semantics;
- unmatched item không bị tính là safe;
- FAERS unique case aggregation;
- DDI cùng active ingredient không tạo self-pair;
- DDI mapped vs unmapped report;
- CYP2E1 behavior nếu bật;
- `build_db()` giữ imported `cyp_roles`;
- user storage isolation;
- Mendeley raw row không tự động biến thành major alert.

## API smoke

```bash
curl -s http://127.0.0.1:8765/api/health
curl -s http://127.0.0.1:8765/api/stats
curl -s http://127.0.0.1:8765/api/unified/stats
curl -s "http://127.0.0.1:8765/api/search?q=ibuprofen"
```

Sau khi có endpoint mới:

```bash
curl -s "http://127.0.0.1:8765/api/drug/<id>/adverse-events"
curl -s "http://127.0.0.1:8765/api/drug/<id>/label"
curl -s "http://127.0.0.1:8765/api/drug/<id>/food-evidence"
```

## Regression scenarios

- Ibuprofen + warfarin: bleeding warning.
- Grapefruit + statin: drug-food warning.
- Amoxicillin + penicillin allergy: allergy path.
- Drug name không map được: unknown/unmatched, không phải safe.
- Nhật/Trung: `イブプロフェン`, `阿莫西林` vẫn resolve.
- Người cao tuổi + diazepam: Beers warning.
- Renal impairment + nephrotoxic combination: context warning.
- Pregnancy/lactation: chỉ cảnh báo khi profile có status.
- Two independent clients: profile/history không bị lộ chéo.
- External food API timeout: local result vẫn trả được.

---

# 8. Definition of Done cho public MVP

App chỉ được xem là sẵn sàng khi:

- [x] Profile/history isolation đã kiểm chứng.
- [x] Core scan/analyze chạy không cần AI model API.
- [x] OCR local có fallback lỗi rõ ràng.
- [x] DDI có ingredient-level mapping hoặc trả unknown đúng nghĩa.
- [x] Adverse reactions có API drug-level.
- [x] Contraindications/warnings có API và source/effective date.
- [x] FAERS không bị trình bày như causality/incidence.
- [x] “No interaction found” không bị trình bày thành “safe”.
- [x] Allergy/duplicate active ingredient được xử lý.
- [x] Pregnancy/lactation/renal/hepatic thiếu dữ liệu thì trả unknown.
- [x] Source attribution và license registry đầy đủ.
- [x] Rate limit, payload limit, timeout và cache hoạt động.
- [x] Admin review endpoint không public.
- [x] Regression suite pass.
- [x] Smoke test trên build/deployment thực tế pass.

---

# 9. Thứ tự làm việc đề xuất cho ngày mai

## Buổi 1 — P0 safety semantics và storage

1. Audit/fix `mt_device` hoặc chuyển profile/history về local-first.
2. Sửa response schema `no_documented_interaction_found`.
3. Thêm tests cho unmatched/unknown/storage isolation.

## Buổi 2 — FAERS + label API

4. Thiết kế aggregate/index cho `fda_reaction`, `fda_report`, `fda_drug`.
5. Thêm drug-level adverse-event endpoint.
6. Thêm label safety-section endpoint.
7. Smoke test với drug có dữ liệu thật.

## Buổi 3 — OnSIDES full

8. Lấy release OnSIDES mới nhất từ GitHub Releases.
9. Import raw vào bảng riêng.
10. Validate row counts, source, license, RxNorm mapping.
11. Chỉ sau validation mới switch aggregate/API sang OnSIDES full.

## Buổi 4 — DDI mapping và profile context

12. Tạo `drug_name_mapping`.
13. Map Zenodo DDI qua RxNorm/RxCUI.
14. Thêm duplicate active-moiety detection.
15. Chuẩn hóa pregnancy/lactation/renal/hepatic fields.

## Cuối ngày — verification

16. Rebuild unified/index một lần trong maintenance window.
17. Restart API.
18. Chạy unit/integrity/regression.
19. Chạy API smoke và các scenario ở mục 7.
20. Ghi lại counts, release versions, checksums và limitations.

---

# 10. Nguồn cần giữ trong provenance/license registry

| Source code | License/status | Cách dùng |
|---|---|---|
| `fda_faers` | Public Domain / CC0 | Raw + aggregate ADR; phải ghi limitation causality |
| `onsides` | CC BY 4.0 | Full adverse events; attribution + modification note |
| `zenodo_ddi_2026` | CC BY 4.0 | DDI evidence; attribution |
| `figshare_cyp450` | CC BY 4.0 | Positive substrate evidence |
| `mendeley_drug_food` | CC BY 4.0 | Raw research food evidence |
| `pharmgkb/clinpgx` | CC BY-SA 4.0 | PGx; attribution + share-alike |
| `open_targets` | CC0 cho generated data theo docs; upstream caveat | Target/indication enrichment |
| `dailymed/openfda_label` | Official public regulatory source; local API/bulk releases accepted | Label evidence; quote/display policy vẫn theo release |
| `tapirro` | MIT; `seed-v1` accepted | Citation-backed seed evidence |
| `fda_curated` | Public-domain FDA facts, curated; `seed-v1` accepted | Curated seed rules, không gọi là raw openFDA |
| `cyp_roles/cyp_inference` | Derived internal; `runtime-v1`/`algorithm-v1` accepted | Screening signal; upstream role derivation bắt buộc |
| `suppai` | Terms/commercial reuse chưa verify; candidate | Không promote vào commercial runtime |
| `idisk` | Terms/commercial reuse chưa verify; candidate | Không promote vào commercial runtime |
| `lactmed` | Public-domain pointer được ghi nhận bởi AHRQ; verify NLM bulk terms | Breastfeeding reference |
| `medlineplus` | Content rights khác nhau; ưu tiên outbound link | Không bulk-copy khi chưa kiểm tra |
| `crediblemeds` | Restricted/proprietary | Không import commercial raw |
| `ddinter` | CC BY-NC-SA | Chỉ research build, không commercial |
| `kaggle_drug_food` | NC/NC-SA | Không commercial |

---

## Kết luận

App không cần AI model API để public. Việc cần làm trước không phải thêm chatbot mà là:

1. bảo vệ profile/history;
2. expose adverse reactions và label safety;
3. map DDI theo active ingredient;
4. không đánh đồng absence-of-evidence với safety;
5. bổ sung pregnancy/lactation/renal/hepatic/allergy context;
6. giữ provenance/license/limitations trên từng kết quả.

Ngày mai bắt đầu từ **P0.1 → P0.2 → P0.4 → P0.5**, sau đó mới import OnSIDES full.

# MedMatch — Lộ trình mở rộng dữ liệu y tế và sức khỏe

> Mục tiêu: tăng độ phủ sản phẩm, thành phần, tương tác, phản ứng bất lợi và ngữ cảnh cá nhân hóa mà không làm suy giảm provenance, license compliance hoặc safety semantics.
>
> Nguyên tắc: **không crawl tràn lan**. Mỗi nguồn phải có câu hỏi coverage cụ thể, license được duyệt, mapping định danh, evidence level và release có thể rollback.

## 1. Phạm vi hiện tại

Kiến trúc hiện tại:

```text
React PWA /scanner/
        │
        ▼
FastAPI /api/*
        │
        ├── scanner/router.py
        ├── scanner/medmatch_bridge.py
        ├── scanner/personalization.py
        ├── engine.py
        ├── canonical evidence layer
        └── SQLite runtime snapshot
```

Các lớp dữ liệu chính:

- Product identity: barcode, NDC, DSLD, UPC/EAN, Open Food Facts/Open Beauty Facts, USDA.
- Entity normalization: RxNorm, synonyms, standards, PubChem và các mapping nội bộ.
- Clinical/regulatory evidence: DailyMed, openFDA, curated FDA, Zenodo DDI, OnSIDES, FAERS.
- Health context: pregnancy, lactation, renal/hepatic, age, labs, conditions, pharmacogenomics.
- Runtime: FastAPI đọc compact read-only snapshot; importer không chạy khi API boot.
- Feedback: `coverage_events.jsonl` ghi hit/miss, latency, unmatched và stale.

## 2. Baseline dữ liệu đã xác nhận

| Hạng mục | Runtime hiện tại |
|---|---:|
| `product_index` | 507,426 |
| DSLD products | 145,650 |
| NDC products | 135,000 |
| `interaction_unified` | 61,123 |
| `canonical_finding` | 61,123 |
| Accepted canonical findings | 12,793 |
| Candidate findings chưa promote | 48,330 |
| FAERS adverse-event aggregate | 7,977,006 |
| Label sections | 262,271 |
| PharmGKB relations | 127,786 |
| Herbs | 1,216 |
| Drug classes | 1,650 |

Accepted findings chưa đồng nghĩa với bằng chứng lâm sàng mạnh. Runtime hiện có các nhóm `regulatory`, `supported_signal`, `screening_signal`, `inferred` và `unknown`; các nhóm này phải được giữ riêng trên API/UI.

## 3. Rủi ro cần đóng trước khi crawl mới

### P0. Runtime và source coverage

- `backend/medmatch.db` là seed DB; `deploy/runtime/medmatch.db` mới là snapshot đầy đủ.
- `engine.source_coverage()` chưa phản ánh đầy đủ FAERS aggregate, ChEMBL, DrugCentral, PharmGKB, Mendeley, Canada Vigilance và các source đã được build.
- `/api/provenance` cần phân biệt active, candidate, blocked và stale source.

**Acceptance:** production không chạy nhầm seed DB; `checkedSources` khớp với dữ liệu thật trong runtime.

### P0. Unknown không được coi là safe

`backend/scanner/personalization.py` hiện mặc định ingredient không có hazard record là `safe` và gán các thông điệp như `GRAS` hoặc `No toxicological flags recorded`.

Cần đổi thành:

```text
unknown
not_evaluated
insufficient_evidence
```

Chỉ trả `safe` khi có evidence/rule được chấp nhận và đúng scope.

**Acceptance:** regression test chứng minh ingredient chưa biết không thể render thành safe.

### P0. Không tạo evidence giả

PubMed fallback không được trả study count cố định hoặc citation generic như dữ liệu thật.

Khi external API lỗi:

```json
{
  "studyCount": null,
  "status": "unavailable",
  "citations": [],
  "limitations": ["PubMed could not be queried"]
}
```

**Acceptance:** không có synthetic count; frontend hỗ trợ `studyCount: number | null`.

### P0. License gate

Không đưa các nguồn đang bị registry block vào commercial runtime:

- SUPP.AI.
- iDISK.
- DDInter.
- DrugBank free/restricted data.
- SIDER/TWOSIDES.
- VigiBase/VigiAccess.
- JADER/KIDS DUR.
- LactMed, LiverTox, MedlinePlus nếu chưa có quyền bulk redistribution.

Các nguồn này chỉ có thể là research-only hoặc reference/outbound cho tới khi legal review thay đổi trạng thái.

### P0. Coverage worklist

`coverage_events.jsonl` đã ghi đủ metric cơ bản nhưng `/api/coverage/stats` chỉ trả hash cho top miss. Cần thêm secure admin worklist hoặc flow `Report missing product` có consent.

Không đưa PHI hoặc dữ liệu label chưa được redaction vào dashboard công khai.

## 4. Nguồn dữ liệu và cách sử dụng

| Domain | Nguồn ưu tiên | Cách dùng |
|---|---|---|
| Product/barcode | DSLD, NDC, OFF/OBF, USDA | Identity, composition, nutrition; không phải clinical evidence |
| Regulatory label | DailyMed, openFDA | Warning, contraindication, interaction, pregnancy, lactation, renal/hepatic, pediatric, geriatric, monitoring |
| Drug interaction | FDA curated, DailyMed, openFDA, Zenodo DDI | Exact ingredient/class interaction; giữ source và evidence level riêng |
| Mechanism | ChEMBL, DrugCentral | Target/mechanism enrichment; không tự nâng severity |
| Adverse reaction | FAERS, OnSIDES, Canada Vigilance, Korea MFDS nếu được duyệt | Reported signals; không suy ra incidence hoặc causality |
| Drug-food | Mendeley Drug-Food, USDA, PubChem | Map constituent → substance → enzyme/transporter → drug |
| Clinical studies | PubMed, Europe PMC, ClinicalTrials.gov | Citation, study metadata, candidate evidence; không tự quyết định clinical severity |
| PGx | PharmGKB/ClinPGx, CPIC/DPWG nếu được duyệt | Evidence review; không tự động điều chỉnh dose |
| Allergy/cross-reactivity | FDA/EU/UK/Canada allergen declarations, allergen ontology, PubMed/Europe PMC | Allergen component, protein family, population-scoped cross-reactivity |
| Cosmetics | INCI, nguồn regulatory cosmetic phù hợp license | Ingredient identity, contact allergen và regional restriction |
| Vietnam/APAC | Cơ quan quản lý và official label theo từng thị trường | Tạo release khu vực riêng; không dịch tự động thành evidence authoritative |

Open Food Facts/USDA chỉ mô tả sản phẩm, thành phần hoặc dinh dưỡng. Không dùng chúng làm nguồn kết luận tương tác thuốc.

## 5. Quy tắc intake cho GitHub

GitHub chỉ là kênh phân phối. Trước khi nhập một repository/dataset phải kiểm tra:

1. License của repository.
2. License riêng của data file hoặc release asset.
3. Điều khoản commercial use, redistribution và derived data.
4. Release/tag/commit SHA cố định.
5. URL, checksum, parser version và thời điểm tải.
6. Schema và row count trước/sau parse.
7. Phân loại `commercial_runtime`, `research_only` hoặc `reference_only`.

GitHub ingestion chỉ đọc release/assets/contents hoặc file đã pin theo commit. Không scrape README, Issues, Discussions, comments, review hoặc user opinions thành dữ liệu an toàn y tế.

Các source GitHub đã có trong hệ thống như tapirro và Sahayak vẫn phải đi qua registry/release gate khi refresh.

## 6. Pipeline ingestion chuẩn

```text
discover source
    ↓
license gate
    ↓
download/API fetch
    ↓
checksum + immutable artifact
    ↓
source staging table
    ↓
identity normalization
    ↓
candidate mapping/review
    ↓
evidence_record + provenance
    ↓
conflict reconciliation
    ↓
canonical_finding
    ↓
quality/evaluation gate
    ↓
compact runtime snapshot
    ↓
atomic promote/rollback
```

### Metadata bắt buộc

Mỗi source adapter phải có:

```text
source_code
provider
source_type: api | bulk | github_release | reference
authority_tier
license
terms_url
commercial_use
raw_redistribution
derived_use
region
language
refresh_frequency
rate_limit
parser_version
```

Mỗi evidence record phải có:

```text
source_code
release_id
ingestion_run_id
source_record_id
parser_version
evidence_level
status
evidence_confidence
context_json
limitations
```

### API fetch

Bắt buộc hỗ trợ:

- Timeout và retry có giới hạn.
- Exponential backoff và rate limit theo provider.
- ETag/Last-Modified nếu provider hỗ trợ.
- Pagination cursor.
- Response hash.
- Cache và circuit breaker.
- Manifest cho từng request/page.
- Không xóa accepted data khi một target refresh thất bại.

Không chạy importer trong FastAPI startup.

## 7. Data model mở rộng

Tận dụng các bảng hiện có:

- `source_license`.
- `dataset_release`.
- `ingestion_run`.
- `evidence_artifact`.
- `evidence_record`.
- `evidence_record_subject`.
- `evidence_derivation`.
- `finding_conflict`.
- `crawl_manifest`.

Chỉ thêm bảng khi cần domain mới:

```text
entity_identifier
entity_mapping
mapping_review
product_composition
product_component
effect_concept
effect_crosswalk
reaction_signal
allergen_component
cross_reactivity_relationship
```

Các identifier cần hỗ trợ:

```text
GTIN / UPC / EAN
NDC
RxCUI
UNII
PubChem CID
InChIKey
ChEBI
ATC
INCI
MedDRA
Gene/allele identifiers
```

`context_json` phải chuẩn hóa cho:

```text
population
age
pregnancy_trimester
lactation
renal_stage
hepatic_stage
dose
route
formulation
food_preparation
country
language
report_role
```

## 8. Lộ trình triển khai

### Phase 0 — Data governance và safety gate

**Mục tiêu:** làm cho coverage hiện tại trung thực và an toàn.

Công việc:

- Bắt buộc runtime DB rõ ràng.
- Sửa `source_coverage` và `/api/provenance`.
- Sửa PubMed fallback.
- Đổi unknown ingredient khỏi `safe`.
- Đồng bộ README, `DATA_STRATEGY.md`, `DATABASES.md`, `NEXT_WORK_PLAN.md` với runtime.
- Tách source active/candidate/blocked/reference.
- Chuẩn hóa crawler orchestration; inventory hiện chưa có đầy đủ `backend/crawler/` dù một số importer tham chiếu `backend.crawler.run`.

Nghiệm thu:

- 0 blocked source trong commercial canonical layer.
- 0 synthetic clinical count.
- 0 unknown ingredient render thành safe.
- Refresh lỗi giữ nguyên snapshot accepted.

### Phase 1 — Product identity và composition

**Mục tiêu:** tăng tỷ lệ scan thành công trước khi thêm evidence mới.

Product mapping còn thiếu đã xác nhận:

| Code type | Chưa map |
|---|---:|
| DSLD | 2,226 |
| UPC | 2,948 |
| EAN | 2,760 |
| NDC | 38,422 |
| **Tổng** | **46,356** |

Công việc:

- Ưu tiên NDC và top barcode miss.
- Map exact product → ingredient → normalized entity.
- Lưu composition version/provenance.
- Thêm secure missing-product worklist.
- Tách barcode hit, name hit và OCR hit.

Nghiệm thu:

- Beta top products đạt hit-rate tối thiểu 85% theo mục tiêu R3.
- Mapping rate tăng theo từng release.
- Mọi accepted composition có source, release và mapping status.

### Phase 2 — Regulatory và population safety

Công việc:

- Targeted refresh DailyMed/openFDA theo top scanned drugs và high-risk classes.
- Extract boxed warning, contraindication, adverse reaction, pregnancy, lactation, renal/hepatic, pediatric, geriatric và monitoring.
- Thêm `/api/drug/{id}/population-safety`.
- Hiển thị missing context thay vì suy đoán an toàn.

Nghiệm thu:

- Label evidence có section, source record và release.
- Missing pregnancy/renal/hepatic data trả `unknown`, không trả safe.
- Không full-recrawl nếu không có coverage question cụ thể.

### Phase 3 — Adverse reactions và pharmacovigilance

Công việc:

- Sửa `checkedSources` để phản ánh FAERS aggregate.
- Expose FAERS và OnSIDES với limitation rõ.
- Aggregate Canada Vigilance sau legal/parser review.
- Đánh giá Korea MFDS.
- Chuẩn hóa reaction term, role, quarter, region và seriousness.
- Thêm `/api/drug/{id}/reaction-signals`.

Nghiệm thu:

- UI dùng nhãn `reported association`.
- Không gọi case count là incidence.
- Không merge FAERS/OnSIDES/label nếu chưa có crosswalk hợp lệ.

### Phase 4 — Drug-food, constituent và clinical evidence

Công việc:

- Normalize 9,276 Mendeley drug-food rows.
- Xây food constituent → substance → enzyme/transporter mapping.
- Thêm PubMed/Europe PMC/ClinicalTrials metadata.
- Tạo candidate queue cho evidence extraction.
- Giữ reference-only khi không được phép redistribute nội dung.

Nghiệm thu:

- Không dùng food-category heuristic thay cho constituent mapping.
- Clinical citation có PMID/DOI hoặc được đánh dấu unavailable/reference-only.
- External API lỗi không làm thay đổi safety result thành evidence found.

### Phase 5 — Herb/supplement và GitHub source intake

Công việc:

- Tìm nguồn monograph/supplement được phép commercial.
- Không promote SUPP.AI/iDISK khi license chưa được duyệt.
- Xây GitHub release adapter pin theo commit.
- Phân biệt clinical, observational, case report, mechanistic và inferred.
- Giữ CYP findings pending cho tới khi pharmacist review.

Nghiệm thu:

- Mọi source có legal metadata.
- Mọi record có lineage tới source artifact.
- Restricted source bị chặn trước bước canonicalization.

### Phase 6 — Cross-reactivity, allergy và cosmetic safety

Công việc:

- Migrate `CROSS_REACTIVITY_RULES` khỏi hardcode sang source-backed data.
- Thêm allergen component, protein family, population và cooking/preparation context.
- Mở rộng drug allergy groups bằng label/evidence.
- Thêm provenance cho risk range và clinical advice.
- Tách food allergy, drug allergy và cosmetic contact allergen.

Nghiệm thu:

- Mọi high-risk relationship có citation/review status.
- Risk range không hiển thị nếu thiếu population/source.
- Rule chưa đủ bằng chứng chỉ là `screening_signal` hoặc `unknown`.

### Phase 7 — PGx, Vietnam/APAC và beta operations

Công việc:

- Hoàn thiện PharmGKB/ClinPGx evidence review.
- Đánh giá CPIC/DPWG theo license.
- Xây release khu vực Việt Nam/APAC bằng official label/product sources.
- Weekly top-miss review.
- Refresh report, checksum, schema gate, rollback drill.
- Beta validation trên sản phẩm user thực sự scan.

Nghiệm thu:

- Không tự động điều chỉnh dose từ PGx.
- Không dịch LLM thành clinical evidence authoritative.
- R3: hit-rate ≥85% trên nhóm beta, 0 crash trong 7 ngày.
- Mỗi refresh có before/after report và rollback result.

## 9. API và frontend contract

API nên bổ sung hoặc chuẩn hóa:

```text
GET /api/product/{id}/composition
GET /api/product/{id}/provenance
GET /api/ingredient/{id}/evidence
GET /api/drug/{id}/population-safety
GET /api/drug/{id}/reaction-signals
GET /api/cross-reactivity/{entity}
GET /api/coverage/worklist
```

Frontend `src/types.ts` cần hỗ trợ:

- `screening_signal`.
- `supported_signal`.
- `unknown`.
- `evidenceId` và `sourceRecordId`.
- `limitations`.
- `population`.
- `studyCount: number | null`.
- Cross-reactivity provenance và review status.

UI phải phân biệt:

```text
Documented interaction
Clinical evidence
Reported signal
Screening signal
Not enough data
Requires pharmacist review
```

Không hiển thị “safe” chỉ vì không tìm thấy record.

## 10. Metrics và test gates

### Coverage

- Barcode hit rate.
- Name/OCR hit rate.
- Ingredient mapping rate.
- Unmatched rate.
- Hit rate theo quốc gia và product type.
- Top-50/top-100 beta products.

### Evidence quality

- Accepted/candidate ratio.
- Lineage completeness.
- Exact mapping rate.
- Duplicate rate.
- Conflict rate.
- Stale rate.
- Blocked-source count.

### Safety

- High-risk recall.
- False-positive rate.
- Unknown-not-safe regression.
- Severity drift.
- Missing-context visibility.
- Cross-reactivity review coverage.

### Operations

- Refresh success rate.
- Snapshot rollback success.
- Scan latency p50/p95.
- External API error rate.
- Crash-free days.

Test areas cần mở rộng:

```text
test_source_coverage.py
test_product_composition.py
test_adverse_signal_semantics.py
test_cross_reactivity_provenance.py
test_pubmed_fallback.py
test_license_gate.py
```

Đồng thời mở rộng các test hiện có cho:

```text
test_safety_semantics.py
test_evidence_schema.py
test_runtime_snapshot.py
test_openfda_refresh.py
test_patient_context.py
```

## 11. Thứ tự thực thi bắt buộc

```text
1. Runtime DB, license và provenance
2. Unknown/safe semantics và PubMed fallback
3. Product composition mapping
4. Targeted regulatory labels
5. FAERS/OnSIDES/Canada reaction signals
6. Food constituent và clinical metadata
7. Licensed herb/supplement sources
8. Evidence-backed cross-reactivity
9. PGx và Vietnam/APAC
10. Beta coverage loop và refresh operations
```

Không đánh giá thành công bằng số dòng crawl. Chỉ coi là thành công khi số user scan được sản phẩm/ingredient đúng tăng lên, evidence có provenance, license hợp lệ, semantics không gây hiểu nhầm và snapshot có thể rollback.

# MedMatch — Canonical Evidence Contract & Provenance Schema

_Trạng thái: Phase 1 đã triển khai additive schema, backfill và source/release
reconciliation; canonical read đã bật production sau khi đạt dual-read parity._

Phase 1 hiện có:

- `backend/evidence_schema.py`: schema, migration idempotent và deterministic IDs;
- `backend/evidence_backfill.py`: backfill bảo thủ từ `interaction_unified`;
- `backend/source_reconciliation.py`: alias provider, release manifest, rekey và
  acceptance gate có audit;
- `backend/db.py`: tự provision schema trên writable connection;
- 61.123 canonical findings, 63.344 evidence records active và 63.344 lineage
  links; 12.793 findings/evidence được promote, 48.330 findings còn candidate.


## 1. Quyết định nền tảng

MedMatch phân biệt ba lớp dữ liệu:

1. **Source evidence** — bản ghi nguyên thủy hoặc bản ghi đã parse từ một source
   cụ thể.
2. **Canonical finding** — kết luận chuẩn hóa của MedMatch sau khi hợp nhất các
   evidence records.
3. **Personalized assessment** — mức khẩn cấp/action sau khi áp dụng patient
   context. Lớp này thuộc Phase 2/4 và không được ghi ngược vào evidence gốc.

Không được dùng một trường `trust` duy nhất để đại diện cho mọi ý nghĩa. Contract
mới tách:

- `source_reliability`: độ tin cậy của dataset/provider;
- `mapping_confidence`: độ chắc chắn khi map raw name vào entity;
- `evidence_confidence`: độ chắc chắn của assertion;
- `personalized_urgency`: mức cần hành động với một patient cụ thể.

`evidence_severity` không đồng nghĩa với `personalized_urgency`.

## 2. Canonical vocabulary

### 2.1 Entity kinds

Giá trị chuẩn hiện tại:

```text
drug_ingredient | drug_class | herb | food | nutrient | chemical |
condition | product | effect
```

Mỗi entity runtime phải có `kind`, `entity_id`, `label`. `raw_name` chỉ là input
hoặc tên trong source; không dùng raw name làm khóa hợp nhất.

### 2.2 Evidence types

```text
drug_drug | drug_food | herb_drug | herb_herb |
label_section | adverse_event | mechanism | depletion |
pharmacogenomics | population_context | product_composition
```

### 2.3 Evidence levels

```text
regulatory              # nhãn/quy định chính thức
clinical_guideline      # hướng dẫn lâm sàng
clinical_study          # thử nghiệm/nghiên cứu lâm sàng
observational           # nghiên cứu quan sát
case_report             # báo cáo ca
pharmacovigilance       # FAERS/VigiBase và tín hiệu hậu mãi
mechanistic             # cơ chế dược lý/in-vitro
inferred                # suy luận của MedMatch từ evidence khác
reference_only          # chỉ trỏ ra nguồn, chưa được copy/parse
unknown                  # chưa đủ phân loại
```

### 2.4 Severity

```text
contraindicated | major | moderate | minor | unknown | not_applicable
```

`unknown` là giá trị hợp lệ. Không được mặc định thành `minor` khi source không
có severity.

### 2.5 Record status

```text
candidate | accepted | rejected | superseded | withdrawn | reference_only
```

`accepted` là điều kiện để promote finding vào runtime; backfill có thể tạo
candidate finding staging để giữ unresolved lineage. `candidate` dành cho
mapping/evidence chờ review; `rejected` vẫn giữ để audit nhưng không được query
như kết luận.

## 3. Contract JSON canonical finding

Đây là contract version 1 cho output nội bộ và API. API có thể rút gọn phần
hiển thị, nhưng không được bỏ `findingId`, `evidenceLevel`, `evidenceIds` hoặc
`limitations` khỏi payload máy đọc.

```json
{
  "contractVersion": "medmatch.finding.v1",
  "findingId": "finding:sha256:...",
  "pair": {
    "a": {
      "kind": "herb",
      "entityId": "st_johns_wort",
      "label": "St. John's Wort",
      "input": "St Johns Wort"
    },
    "b": {
      "kind": "drug_class",
      "entityId": "anticoagulantes",
      "label": "Anticoagulants",
      "input": "warfarin"
    },
    "pairKey": "drug_class:anticoagulantes|herb:st_johns_wort",
    "matchLevel": "class"
  },
  "classification": {
    "type": "herb_drug",
    "status": "documented",
    "evidenceLevel": "regulatory",
    "evidenceSeverity": "major",
    "evidenceConfidence": 0.94,
    "inferred": false,
    "resolutionPolicyVersion": "risk-resolution-v1"
  },
  "outcome": {
    "effect": "Reduced warfarin exposure",
    "mechanism": "CYP2C9/P-gp induction",
    "action": "Avoid or use only with clinician-supervised monitoring",
    "monitoring": ["INR"]
  },
  "context": {
    "population": ["adult"],
    "dose": null,
    "route": null,
    "conditions": [],
    "pregnancy": null,
    "renal": null,
    "hepatic": null,
    "scopeHash": "sha256:..."
  },
  "evidence": [
    {
      "evidenceId": "evidence:sha256:...",
      "role": "supporting",
      "sourceCode": "suppai",
      "releaseId": "suppai:2026-03",
      "recordKey": "suppai:...",
      "locator": {
        "url": "https://...",
        "doi": "10....",
        "pmid": null,
        "sourceRecordId": "..."
      },
      "sourceReliability": 0.9,
      "evidenceConfidence": 0.94,
      "displayPolicy": "attribution_required"
    }
  ],
  "provenance": {
    "derived": false,
    "parserVersions": ["suppai-parser-v2"],
    "ingestionRunIds": ["ingest:..."],
    "lineageComplete": true
  },
  "limitations": [
    "Dose, route and patient laboratory values were not supplied."
  ]
}
```

### Contract rules

- `findingId` ổn định với cùng entity pair, evidence scope và policy version.
- `pairKey` chuẩn hóa bằng cách sort hai phía theo `kind:entityId`.
- `context.scopeHash` ngăn việc hợp nhất hai assertion khác population/dose/route.
- `evidenceSeverity` được phép `null` ở source evidence không có severity, nhưng
  canonical finding phải trả `unknown` nếu không đủ cơ sở để gán mức.
- `evidenceConfidence` nằm trong `[0, 1]`; không dùng số này như xác suất biến cố
  lâm sàng.
- `inferred=true` bắt buộc có `derivation` và không được tự động nâng lên
  `regulatory` hoặc `clinical_guideline`.
- `lineageComplete=false` thì finding không được xuất hiện ở commercial runtime,
  trừ khi trạng thái là `reference_only` hoặc `unknown` và UI nói rõ giới hạn.
- `source_quote` chỉ được trả ra client nếu license cho phép. Nếu không, trả
  locator/attribution phù hợp và giữ quote ở private storage hoặc không lưu.

## 4. SQLite schema canonical

### 4.1 Nguồn và license

`source_license` và `dataset_release` đã tồn tại trong codebase. Chúng là nền
compatibility hiện tại; schema v1 bổ sung các cột sau bằng migration idempotent,
không đổi tên bảng trong bước đầu.

```sql
ALTER TABLE source_license ADD COLUMN provider TEXT;
ALTER TABLE source_license ADD COLUMN dataset_kind TEXT;
ALTER TABLE source_license ADD COLUMN authority_tier TEXT;
ALTER TABLE source_license ADD COLUMN display_policy TEXT NOT NULL DEFAULT 'show_attribution';
ALTER TABLE source_license ADD COLUMN derived_use_allowed INTEGER NOT NULL DEFAULT 0;
ALTER TABLE source_license ADD COLUMN legal_review_status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE source_license ADD COLUMN reviewed_by TEXT;

ALTER TABLE dataset_release ADD COLUMN release_status TEXT NOT NULL DEFAULT 'accepted';
ALTER TABLE dataset_release ADD COLUMN published_at TEXT;
ALTER TABLE dataset_release ADD COLUMN fetched_at TEXT;
ALTER TABLE dataset_release ADD COLUMN content_type TEXT;
ALTER TABLE dataset_release ADD COLUMN size_bytes INTEGER;
ALTER TABLE dataset_release ADD COLUMN row_count INTEGER;
ALTER TABLE dataset_release ADD COLUMN schema_hash TEXT;
ALTER TABLE dataset_release ADD COLUMN artifact_ref TEXT;
ALTER TABLE dataset_release ADD COLUMN ingestion_run_id TEXT;
```

Giá trị chuẩn:

```text
authority_tier: regulatory | clinical | academic | commercial | community | inferred
release_status: candidate | accepted | failed | superseded | withdrawn
legal_review_status: pending | approved | restricted | rejected
 display_policy: show_source | show_attribution | licensed_category_only | reference_only | hidden_internal_only
```

`hidden_internal_only` chỉ mô tả giới hạn hiển thị hợp đồng; không có nghĩa là
được phép khai báo sai nguồn hoặc xóa provenance.

### 4.2 Ingestion run

```sql
CREATE TABLE IF NOT EXISTS ingestion_run (
    ingestion_run_id TEXT PRIMARY KEY,
    source_code TEXT NOT NULL,
    release_id TEXT,
    parser_version TEXT NOT NULL,
    contract_version TEXT NOT NULL DEFAULT 'medmatch.evidence.v1',
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'accepted', 'failed', 'rolled_back')),
    input_sha256 TEXT,
    schema_hash TEXT,
    rows_seen INTEGER NOT NULL DEFAULT 0,
    rows_accepted INTEGER NOT NULL DEFAULT 0,
    rows_rejected INTEGER NOT NULL DEFAULT 0,
    rows_changed INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    error_summary TEXT,
    artifact_ref TEXT,
    notes TEXT,
    FOREIGN KEY (source_code) REFERENCES source_license(source_code)
);
CREATE INDEX IF NOT EXISTS idx_ingestion_source_status
    ON ingestion_run(source_code, status, started_at);
```

Một release có thể có nhiều run; chỉ một run được chọn làm current accepted
snapshot. Không xóa run thất bại.

### 4.3 Raw artifact manifest

Raw file lớn không nên nhét vào SQLite. Chỉ lưu immutable reference:

```sql
CREATE TABLE IF NOT EXISTS evidence_artifact (
    artifact_id TEXT PRIMARY KEY,
    ingestion_run_id TEXT NOT NULL,
    uri TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER,
    content_type TEXT,
    encrypted INTEGER NOT NULL DEFAULT 1,
    retention_class TEXT NOT NULL DEFAULT 'release',
    raw_access_allowed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (ingestion_run_id) REFERENCES ingestion_run(ingestion_run_id),
    UNIQUE(ingestion_run_id, sha256)
);
```

`uri` có thể là local volume/object storage. `raw_access_allowed=0` là mặc định
cho source commercial hoặc reference-only.

### 4.4 Atomic source evidence

```sql
CREATE TABLE IF NOT EXISTS evidence_record (
    evidence_id TEXT PRIMARY KEY,
    source_code TEXT NOT NULL,
    release_id TEXT NOT NULL,
    ingestion_run_id TEXT NOT NULL,
    record_key TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    evidence_level TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'accepted',
    title TEXT,
    statement TEXT,
    effect TEXT,
    mechanism TEXT,
    evidence_severity TEXT,
    evidence_confidence REAL,
    published_at TEXT,
    valid_from TEXT,
    valid_until TEXT,
    source_record_id TEXT,
    source_url TEXT,
    source_locator TEXT,
    doi TEXT,
    pmid TEXT,
    quote_text TEXT,
    context_json TEXT NOT NULL DEFAULT '{}',
    raw_payload_sha256 TEXT,
    normalized_payload_sha256 TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (source_code) REFERENCES source_license(source_code),
    FOREIGN KEY (ingestion_run_id) REFERENCES ingestion_run(ingestion_run_id),
    UNIQUE(source_code, release_id, record_key, normalized_payload_sha256),
    CHECK (evidence_confidence IS NULL OR
           (evidence_confidence >= 0 AND evidence_confidence <= 1)),
    CHECK (evidence_severity IS NULL OR evidence_severity IN
           ('contraindicated', 'major', 'moderate', 'minor', 'unknown', 'not_applicable'))
);
CREATE INDEX IF NOT EXISTS idx_evidence_record_pair_lookup
    ON evidence_record(source_code, evidence_type, evidence_level, status);
CREATE INDEX IF NOT EXISTS idx_evidence_record_source_record
    ON evidence_record(source_code, source_record_id);
```

`record_key` là khóa ổn định của source, không phải row number nếu source có khóa
nghiệp vụ tốt hơn. `normalized_payload_sha256` phát hiện parser thay đổi hoặc
record cùng khóa nhưng nội dung khác.

### 4.5 Evidence subjects và mapping

```sql
CREATE TABLE IF NOT EXISTS evidence_record_subject (
    evidence_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    entity_kind TEXT NOT NULL,
    entity_id TEXT,
    raw_name TEXT NOT NULL,
    mapping_method TEXT NOT NULL,
    mapping_confidence REAL,
    mapping_status TEXT NOT NULL DEFAULT 'accepted',
    external_ids_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (evidence_id, ordinal),
    FOREIGN KEY (evidence_id) REFERENCES evidence_record(evidence_id),
    CHECK (mapping_confidence IS NULL OR
           (mapping_confidence >= 0 AND mapping_confidence <= 1)),
    CHECK (mapping_status IN ('candidate', 'accepted', 'rejected', 'unknown'))
);
CREATE INDEX IF NOT EXISTS idx_evidence_subject_entity
    ON evidence_record_subject(entity_kind, entity_id, mapping_status);
```

`entity_id IS NULL` chỉ hợp lệ khi `mapping_status` là `candidate` hoặc `unknown`.
Fuzzy match không được ghi `accepted` nếu chưa qua trusted mapping/review gate.

### 4.6 Canonical finding

```sql
CREATE TABLE IF NOT EXISTS canonical_finding (
    finding_id TEXT PRIMARY KEY,
    pair_key TEXT NOT NULL,
    a_kind TEXT NOT NULL,
    a_id TEXT NOT NULL,
    b_kind TEXT NOT NULL,
    b_id TEXT NOT NULL,
    finding_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'accepted',
    evidence_status TEXT NOT NULL,
    evidence_level TEXT NOT NULL,
    evidence_severity TEXT NOT NULL DEFAULT 'unknown',
    evidence_confidence REAL,
    effect TEXT,
    mechanism TEXT,
    action TEXT,
    inferred INTEGER NOT NULL DEFAULT 0,
    context_json TEXT NOT NULL DEFAULT '{}',
    scope_hash TEXT NOT NULL,
    resolution_policy_version TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    CHECK (evidence_status IN ('documented', 'supported_signal', 'screening_signal', 'unknown')),
    CHECK (evidence_level IN
           ('regulatory', 'clinical_guideline', 'clinical_study', 'observational',
            'case_report', 'pharmacovigilance', 'mechanistic', 'inferred',
            'reference_only', 'unknown')),
    CHECK (evidence_severity IN
           ('contraindicated', 'major', 'moderate', 'minor', 'unknown', 'not_applicable')),
    CHECK (evidence_confidence IS NULL OR
           (evidence_confidence >= 0 AND evidence_confidence <= 1)),
    UNIQUE(pair_key, finding_type, scope_hash, resolution_policy_version)
);
CREATE INDEX IF NOT EXISTS idx_canonical_finding_pair
    ON canonical_finding(a_kind, a_id, b_kind, b_id, status);
CREATE INDEX IF NOT EXISTS idx_canonical_finding_level
    ON canonical_finding(evidence_level, evidence_severity, status);
```

`personalized_urgency` không nằm trong bảng này. Nó được tính ở Phase 2/4 từ
patient context, để không làm bẩn evidence snapshot.

### 4.7 Lineage và conflict

```sql
CREATE TABLE IF NOT EXISTS finding_evidence (
    finding_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    role TEXT NOT NULL,
    source_severity TEXT,
    source_confidence REAL,
    selected INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    PRIMARY KEY (finding_id, evidence_id),
    FOREIGN KEY (finding_id) REFERENCES canonical_finding(finding_id),
    FOREIGN KEY (evidence_id) REFERENCES evidence_record(evidence_id),
    CHECK (role IN ('supporting', 'contradicting', 'context', 'derivation')),
    CHECK (source_confidence IS NULL OR
           (source_confidence >= 0 AND source_confidence <= 1))
);
CREATE INDEX IF NOT EXISTS idx_finding_evidence_selected
    ON finding_evidence(finding_id, selected, role);

CREATE TABLE IF NOT EXISTS evidence_derivation (
    derived_evidence_id TEXT NOT NULL,
    upstream_evidence_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    operation_version TEXT NOT NULL,
    PRIMARY KEY (derived_evidence_id, upstream_evidence_id, operation),
    FOREIGN KEY (derived_evidence_id) REFERENCES evidence_record(evidence_id),
    FOREIGN KEY (upstream_evidence_id) REFERENCES evidence_record(evidence_id)
);

CREATE TABLE IF NOT EXISTS finding_conflict (
    conflict_id TEXT PRIMARY KEY,
    finding_id TEXT NOT NULL,
    dimension TEXT NOT NULL,
    source_values_json TEXT NOT NULL,
    selected_value TEXT,
    resolution TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    reviewer_status TEXT NOT NULL DEFAULT 'system_resolved',
    created_at TEXT NOT NULL,
    FOREIGN KEY (finding_id) REFERENCES canonical_finding(finding_id),
    CHECK (dimension IN ('severity', 'effect', 'mechanism', 'action', 'mapping', 'scope')),
    CHECK (reviewer_status IN ('system_resolved', 'needs_review', 'reviewed'))
);
CREATE INDEX IF NOT EXISTS idx_finding_conflict_review
    ON finding_conflict(reviewer_status, created_at);
```

Quy tắc: mọi finding hợp nhất từ từ hai evidence records trở lên phải có
`finding_evidence`; mọi severity conflict phải có `finding_conflict`, kể cả khi
policy chọn severity cao nhất.

## 5. Mapping các nguồn hiện tại

| Source hiện tại | `evidence_type` | `evidence_level` | Ghi chú |
|---|---|---|---|
| tapirro `interactions` | `herb_drug` | theo evidence gốc; thiếu thì `unknown` | giữ DOI/source/effect/mechanism |
| curated FDA seeds | drug pair/food pair | `regulatory` | source record là seed key + parser version |
| DailyMed/openFDA labels | `label_section` hoặc `drug_drug` | `regulatory` | setid/label URL/section làm locator |
| SUPP.AI | `herb_drug`/`herb_herb` | theo paper evidence | severity null không tự biến thành minor |
| OnSIDES | `adverse_event` | `pharmacovigilance` | giữ MedDRA ID, region, label ID |
| FAERS | `adverse_event` | `pharmacovigilance` | signal/count, không khẳng định causality |
| Mendeley Drug-Food | `drug_food`/`mechanism` | `observational` hoặc `mechanistic` | giữ constituent và SMILES |
| PharmGKB/ClinPGx | `pharmacogenomics` | `clinical_guideline` hoặc `observational` | không tự tạo dose recommendation |
| `evidence_ontology_intersection` | `population_context` | `inferred` | derived; phải link upstream releases |
| CYP engine | `mechanism` | `inferred` | bắt buộc `evidence_derivation` từ CYP roles |
| `interaction_unified` | canonical finding output | không phải raw evidence | migrate sang `canonical_finding` + lineage |

Các bảng nguồn hiện tại không bị xóa trong Phase 1. Chúng trở thành source-specific
staging/read models; canonical tables là lớp contract chung.

## 6. ID, hash và thời gian

- Tất cả timestamp lưu UTC ISO-8601 với timezone.
- `release_id = source_code + ':' + version`.
- `record_key` do connector tạo từ khóa nghiệp vụ ổn định của source.
- `evidence_id = 'evidence:sha256:' + SHA256(source_code, release_id, record_key,
  normalized_payload_sha256)`.
- `pair_key` sort theo `kind:entity_id` sau khi mapping accepted.
- `scope_hash = SHA256(canonical JSON(context))`; JSON phải sort keys và loại bỏ
  field null không mang ý nghĩa.
- `finding_id = 'finding:sha256:' + SHA256(contract_version, pair_key,
  finding_type, scope_hash, resolution_policy_version)`.
- Không dùng row number SQLite, thứ tự import hoặc URL tạm làm identity duy nhất.

## 7. Invariants bắt buộc

1. Không có `evidence_record` accepted nếu thiếu source, release, ingestion run,
   parser version hoặc normalized payload hash.
2. Không có finding accepted nếu không có ít nhất một `finding_evidence` selected
   và `lineageComplete=true` khi xuất runtime.
3. Evidence `reference_only` không được copy raw quote vào commercial DB.
4. Evidence `inferred` phải có ít nhất một upstream record trong
   `evidence_derivation` và `inferred=1` ở finding.
5. Mapping candidate/unknown không được dùng để tạo canonical pair trong runtime.
6. Source release `failed`, `withdrawn` hoặc `superseded` không được làm current
   release.
7. Cùng source + release + record key + payload hash phải idempotent.
8. Parser mới không xóa snapshot cũ; nó tạo ingestion run mới.
9. Severity conflict không được mất source value; resolution phải ghi policy và
   conflict record.
10. FAERS/VigiBase counts là signal, không được chuyển thành causal interaction
    chỉ vì count lớn.
11. `no_documented_interaction_found` chỉ có nghĩa trong coverage snapshot hiện
    tại; không được sinh `safe` từ việc query không có dòng.
12. Không phát hành thông tin provenance giả hoặc gán dữ liệu licensed vào nhãn
    “free official source”.

## 8. Migration không phá vỡ hệ thống hiện tại

### Bước 1 — additive schema

- Tạo các bảng mới và cột bổ sung ở trên.
- Bật `PRAGMA foreign_keys = ON` cho connection mới sau khi các importer đã
  được kiểm tra với khóa tham chiếu.
- Không đổi response cũ ngay; thêm feature flag cho canonical finding payload.

### Bước 2 — backfill có kiểm soát

- Tạo synthetic release `legacy-unknown` cho source cũ không có version/manifest;
  trạng thái là `candidate` hoặc `needs_review`, không đánh dấu như release mới.
- Backfill source record IDs từ khóa ổn định của từng importer.
- Backfill `evidence_record_subject` bằng mapping exact/trusted hiện có.
- Mapping fuzzy, unresolved hoặc source thiếu license đưa vào review queue.

### Bước 3 — dual read, không dual write lâu dài

- Importer ghi staging + canonical trong cùng một ingestion run.
- Engine đọc canonical finding mặc định (`CANONICAL_EVIDENCE_READ` unset hoặc `1`);
  đặt `CANONICAL_EVIDENCE_READ=0` chỉ dùng làm rollback có kiểm soát.
- `tests/test_canonical_runtime.py` chạy dual-read trên fixture herb-class,
  class-class, class-food và unmatched; so sánh pair, severity, effect,
  mechanism và `result`.
- Adapter chỉ trả finding `accepted` với selected evidence đã qua release,
  license, subject mapping và derivation gates.
- Source staging vẫn được giữ cho importer và rollback; không còn là read path
  mặc định của engine.

### Bước 4 — provenance API

Mở rộng `/api/provenance` với:

```json
{
  "contractVersion": "medmatch.evidence.v1",
  "currentReleases": [],
  "ingestionRuns": [],
  "sourceCoverage": [],
  "lineageStatus": {
    "acceptedFindings": 0,
    "completeFindings": 0,
    "incompleteFindings": 0
  }
}
```

Không trả raw payload hoặc quote của provider commercial nếu license không cho
phép. API phải trả status `reference_only`/`licensed_category_only` thay vì im
lặng bỏ nguồn.

### Bước 5 — rollback

- Nếu run mới fail checksum, schema, mapping hoặc precision gate, giữ current
  accepted release.
- Đánh dấu run mới `failed` hoặc `rolled_back`.
- Rollback chỉ đổi pointer current release; không xóa raw artifact, evidence
  record hoặc audit log.

## 9. Definition of Done cho Phase 1

- Có schema migration idempotent và test trên DB trống + DB hiện tại.
- Mỗi source đang active có `source_license`, accepted/reviewed release và
  ingestion run.
- Có thể truy từ một UI finding đến evidence record, source release, parser
  version, artifact checksum và source locator.
- `interaction_unified` không còn là nơi duy nhất giữ evidence JSON; canonical
  finding có lineage chuẩn.
- Một source bị disable không làm mất dữ liệu source khác hoặc tạo `safe` giả.
- Hai lần import cùng artifact tạo cùng IDs và không tăng duplicate.
- Conflict fixture chứng minh source values không bị mất khi resolution chọn một
  giá trị.
- API provenance và export/report không làm lộ raw data vượt license.

Phase 2 chỉ bắt đầu sau khi toàn bộ gate trên đạt. Patient context, pregnancy,
disease conditions, dose và laboratory values phải được gắn ở lớp personalized
assessment sau đó; không nhét dữ liệu cá nhân vào source evidence snapshot.

## 10. Source alias/release reconciliation

`backend/source_reconciliation.py` là bước chuyển tiếp từ legacy backfill sang
canonical source/release. Resolver phải ưu tiên provider thật trước khi fallback
về `legacy_<slug>`:

- `DailyMed: ...` → `dailymed`;
- `openFDA ...` → `openfda`;
- `SUPP.AI` → `suppai`;
- DOI Zenodo `10.5281/zenodo.19685458` → `zenodo_ddi_2026`;
- `ChEMBL` → `chembl`;
- citation trong `interactions.json` → dataset `tapirro`, không tạo một provider
  mới cho từng paper;
- `MSKCC` → `idisk`, vẫn candidate vì chưa có commercial license manifest;
- nhãn FDA được MedMatch curate → `fda_curated`, tách khỏi raw openFDA;
- `CYP450 inference` → `cyp_inference`; mỗi inferred evidence phải link tới
  role catalog `cyp_roles` qua `evidence_derivation`.

Một evidence record chỉ được promote khi đồng thời có:

1. canonical `source_code` và `release_id`;
2. release `release_status='accepted'`;
3. `source_license.commercial_use_allowed=1` hoặc
   `derived_use_allowed=1`;
4. ingestion run có trạng thái accepted;
5. subjects tồn tại và đều có `mapping_status='accepted'`;
6. inferred evidence có ít nhất một row `evidence_derivation`.

Rekey source/release không sửa đè `evidence_id`: record cũ chuyển thành
`superseded`, record mới nhận deterministic ID theo source/release mới, links và
subjects được copy, còn quyết định được ghi vào
`source_reconciliation_record`. Source thiếu terms hoặc release vẫn ghi nhận
candidate/unresolved; tuyệt đối không promote theo tên label hoặc vì API miễn phí.

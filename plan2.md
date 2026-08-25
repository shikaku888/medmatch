Tôi sẽ đọc các skill hướng dẫn và tìm kiếm sâu hơn vào nguồn dữ liệu, GitHub repos, và cách xử lý TPCN từ Amazon/TikTokShop.Tôi sẽ áp dụng phương pháp Super Analyst 2.0 để phân tích sâu vấn đề này. Đây là bài toán **Level 3 (Phức tạp)** đòi hỏi nghiên cứu đa chiều về nguồn dữ liệu, kỹ thuật tổng hợp và chiến lược tối ưu chi phí.

## 🎯 Intelligence Planning

Tôi cần tìm kiếm thông tin về các mặt sau:
1. **GitHub repos sâu hơn** - không chỉ những repo nổi mà cả các dự án nhỏ hơn, datasets, scripts crawl
2. **Xử lý TPCN từ Amazon/TikTokShop** - cách quét mã vạch, lookup sản phẩm, extract thành phần
3. **Chiến lược xoay account API** - kỹ thuật dùng nhiều account free tier
4. **Nguồn dữ liệu chính phủ & học thuật khác** - EMA (EU), WHO, Kaggle, Hugging Face datasets
5. **Nguồn dữ liệu TPCN chuyên sâu** - các cơ sở dữ liệu chuyên về thảo dược, vitamin

Bắt đầu thu thập thông tin:Tiếp tục tìm kiếm sâu hơn về các nguồn dữ liệu chuyên sâu, EMA châu Âu, Kaggle datasets và kỹ thuật xoay account API chi tiết.Tiếp tục tìm kiếm về iDISK, SUPP.AI, SuppKG và chi tiết kỹ thuật barcode lookup + xoay account API.Tôi đã thu thập đủ dữ liệu từ nhiều nguồn. Bây giờ tôi sẽ áp dụng phương pháp **MECE** (Mutually Exclusive, Collectively Exhaustive) để phân loại và tổng hợp tất cả các nguồn dữ liệu, cùng với chiến lược xoay account API chi tiết và cách xử lý sản phẩm từ Amazon/TikTokShop.

---

# 🔬 Phân Tích Sâu: Tổng Hợp Nguồn Dữ Liệu & Chiến Lược Tối Ưu Chi Phí

## 📋 Tổng Quan Chiến Lược

Vấn đề cốt lõi: **Không có API miễn phí duy nhất nào bao quát toàn bộ dữ liệu tương tác thuốc-TPCN**. Giải pháp: **Xây dựng một "Data Union"** - tổng hợp từ nhiều nguồn khác nhau, mỗi nguồn đóng góp một mảnh ghép, sau đó hợp nhất và khử trùng lặp.

```
┌─────────────────────────────────────────────────────────────┐
│            DATA UNION STRATEGY - MedMatch AI                │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Drug-Drug   │  │ Drug-TPCN   │  │ TPCN-TPCN & Thực phẩm│ │
│  │ (DDInter,   │  │ (SUPP.AI,   │  │ (NIH ODS, Kaggle,   │ │
│  │  Drugbank)  │  │  iDISK,     │  │  Drug-Food dataset) │ │
│  └──────┬──────┘  │  NP-KG)     │  └──────────┬──────────┘ │
│         │         └──────┬──────┘             │            │
│         └────────────────┼────────────────────┘            │
│                          ↓                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │            KNOWLEDGE GRAPH HỢP NHẤT                  │   │
│  │  • Chuẩn hóa tên (RxNorm + PubChem + CAS)            │   │
│  │  • Khử trùng lặp, xếp hạng độ tin cậy nguồn           │   │
│  │  • Thêm cơ chế CYP450 enzyme pathways                 │   │
│  │  • Bổ sung bằng chứng từ FAERS/SUPP.AI evidence       │   │
│  └──────────────────────────┬──────────────────────────┘   │
│                             ↓                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  INPUT LAYER: Nhận diện sản phẩm                     │   │
│  │  • iOS Vision OCR + Barcode scan                     │   │
│  │  • Barcode Lookup APIs (Open Food Facts, UPCitemdb)  │   │
│  │  • Amazon/TikTokShop product data enrichment         │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. 🗂️ Phân Loại MECE Các Nguồn Dữ Liệu

### A. Nguồn Dữ Liệu TƯƠNG TÁC THUỐC-TPCN (Trọng Tâm)

| Nguồn | Loại dữ liệu | Quy mô | Chi phí | Cách tích hợp | Độ ưu tiên |
|-------|-------------|--------|---------|--------------|------------|
| **🔥 SUPP.AI** | Tương tác TPCN-thuốc, có evidence từ bài báo khoa học | 2,044 TPCN, 2,866 thuốc, **59,096 tương tác** | **HOÀN TOÀN MIỄN PHÍ** (Allen Institute for AI, non-profit) | `GET https://supp.ai/api/agent/search?q={query}` → tìm agent → lấy interactions. Không cần API key! | ⭐⭐⭐⭐⭐ |
| **iDISK 2.0** | Dietary Supplement Knowledgebase | 174,317 entities (8,091 DSI, 163,806 DSP, 786 bệnh, 625 thuốc...) | **Miễn phí** (GitHub download) | Tải từ `github.com/houyurain/iDISK2.0` → import vào PostgreSQL/Neo4j | ⭐⭐⭐⭐⭐ |
| **NIH DSLD API** | Dữ liệu nhãn TPCN chính thức từ chính phủ Mỹ | Hàng chục nghìn nhãn sản phẩm | **Miễn phí, không cần key** | `https://dsldapi.od.nih.gov/dsld/v1/labels` → search theo tên thành phần/sản phẩm | ⭐⭐⭐⭐ |
| **NP-KG v2.0** | Natural Product-Drug Interactions Knowledge Graph | 30 natural products, dữ liệu từ GSRS + châu Âu | **Miễn phí** (Zenodo download) | Tải TSV từ Zenodo → import vào graph DB | ⭐⭐⭐⭐ |
| **tapirro herb-drug JSON** | Tương tác thảo dược-thuốc có cấu trúc | 250 thảo dược, 53 nhóm thuốc, **592 tương tác** | **Miễn phí** (MIT license) | Import JSON trực tiếp vào DB | ⭐⭐⭐⭐ |
| **SuppKG** | Dietary Supplement Knowledge Graph từ literature | 56,635 nodes, 595,222 edges, 2,928 DS-specific nodes | **Miễn phí** (paper mô tả, cần build từ SemRepDS) | Tham khảo paper PMC9335448 để build pipeline | ⭐⭐⭐ |
| **MedData API** | Drug-drug + 250+ drug-supplement pairs từ NIH | 250+ cặp TPCN-thuốc | Free tier 250 calls/tháng, $29/tháng+ | REST API, dùng trong giai đoạn đầu hoặc xoay account | ⭐⭐⭐ |

### B. Nguồn Dữ Liệu TƯƠNG TÁC THUỐC-THUỐC

| Nguồn | Quy mô | Chi phí | Cách tích hợp | Độ ưu tiên |
|-------|--------|---------|--------------|------------|
| **DDInter 2.0** | 240K+ tương tác, 1,833 loại thuốc | **Miễn phí** (CC BY-NC-SA) | Tải CSV → host local DB | ⭐⭐⭐⭐⭐ |
| **Rxnorm-Mapper API** | DDInter 2.0 + RxNorm + FAERS | **Miễn phí** (self-host) | Fork `github.com/AsmaaMHadir/Rxnorm-Mapper` → tự host | ⭐⭐⭐⭐ |
| **DDI Reference API (fhirfly.io)** | FDA-approved interaction text + RxNorm enrichment | Free tier | REST API | ⭐⭐⭐ |
| **bonebenders.com API** | Public drug interaction API | **Miễn phí**, có dump JSON hoàn chỉnh | `GET https://drug-interaction-api.dott-bruschi.workers.dev/api/dataset/v1.json` | ⭐⭐⭐ |
| **DrugBank open subset** | Khoảng 10K tương tác | **Miễn phí** (open data) | Tải từ DrugBank website | ⭐⭐⭐ |

### C. Nguồn CHUẨN HÓA TÊN & TRA CỨU HÓA CHẤT

| Nguồn | Mục đích | Chi phí | Cách tích hợp |
|-------|----------|---------|--------------|
| **RxNorm API** | Chuẩn hóa tên thuốc → RxCUI | **Miễn phí, không key** | `https://rxnav.nlm.nih.gov/REST/rxcui.json?name={drug_name}` |
| **RxNorm Full Download** | Bulk download toàn bộ dữ liệu | **Miễn phí** (cần UMLS license) | `https://download.nlm.nih.gov/umls/kss/rxnorm/RxNorm_full_current.zip` |
| **PubChem PUG REST** | Chuẩn hóa hóa chất, lấy CAS/CID | **Miễn phí** | `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/property/.../JSON` |
| **FDA NDC Directory** | Map NDC code → tên thuốc | **Miễn phí** | Bulk download JSON |
| **WHO INN** | Tên thuốc quốc tế | **Miễn phí** | Download từ WHO website |

### D. Nguồn BẰNG CHỨNG & SỰ CỐ BẤT LỢI

| Nguồn | Mục đích | Chi phí | Cách tích hợp |
|-------|----------|---------|--------------|
| **openFDA FAERS** | Báo cáo sự cố bất lợi thực tế | **Miễn phí** | `https://api.fda.gov/drug/event.json` |
| **DailyMed Bulk Download** | Toàn bộ nhãn thuốc FDA XML | **Miễn phí** | `dm_spl_monthly_update_*.zip` (1.64GB/tháng) |
| **DailyMed Data Processor** | Script xử lý DailyMed XML | **Miễn phí** | Fork `github.com/pharmaDB/dailymed_data_processor` |
| **WHO VigiBase API** | Cơ sở dữ liệu phản ứng có hại toàn cầu | Miễn phí cho nghiên cứu | `api.who-umc.org` (cần đăng ký) |

### E. Nguồn TƯƠNG TÁC THUỐC-THỰC PHẨM & TPCN-TPCN

| Nguồn | Mục đích | Chi phí |
|-------|----------|---------|
| **Kaggle: Drug-Food Interactions** | Dataset tương tác thuốc-thực phẩm & thảo dược | **Miễn phí** |
| **NIH ODS Fact Sheets** | Thông tin tương tác cho từng TPCN | **Miễn phí** |
| **Drug-Food Interaction BioBERT** | Model AI dự đoán tương tác thuốc-thực phẩm | **Miễn phí** (GitHub code) |

### F. Knowledge Graphs & Datasets Học Thuật

| Nguồn | Mô tả | Quy mô |
|-------|-------|--------|
| **PrimeKG** | Harvard biomedical KG | 129,375 nodes, 8.1M edges |
| **Hetionet** | Tích hợp 29 databases | 47,031 nodes, 2.25M edges |
| **DRKG** | Drug Repurposing KG | Tích hợp DrugBank, Hetionet, GNBR... |
| **SIDER** | Side Effect Resource | Tác dụng phụ của thuốc |
| **OnSIDES/TwoSIDES** | Tác dụng phụ & tương tác từ nhãn thuốc | CSV files |
| **DGIdb 4.0** | Drug-Gene interactions | 70,000+ interactions |

---

## 2. 🛠️ GitHub Repos Chi Tiết (Những Gì Tôi Chưa Nói)

### Repos Cốt Lõi Có Thể Fork & Tích Hợp Ngay

| Repo | Star/Fork | Giá trị cho MedMatch AI | Cách dùng |
|------|-----------|------------------------|-----------|
| **[jmponcebe/PharmaGraphRAG](https://github.com/jmponcebe/PharmaGraphRAG)** | Mới | **GraphRAG hoàn chỉnh** với Neo4j + FDA FAERS + DailyMed | Học kiến trúc RAG cho dược phẩm, có thể fork làm backend |
| **[HieuNTg/medgraph](https://github.com/HieuNTg/medgraph)** | Mới | **Cascade Detection** - phát hiện tương tác qua đường enzyme CYP450, không chỉ pairwise | Tính năng đột phá, khác biệt hoàn toàn so với đối thủ |
| **[AsmaaMHadir/Rxnorm-Mapper](https://github.com/AsmaaMHadir/Rxnorm-Mapper)** | Mới | Wrapper API hoàn chỉnh: RxNorm + DDInter + FAERS + RxClass | Tự host làm backend chính, tiết kiệm 2-3 tháng dev |
| **[houyurain/iDISK2.0](https://github.com/houyurain/iDISK2.0)** | Mới | **Dataset iDISK 2.0** - Dietary Supplement Knowledgebase | Import dữ liệu TPCN chuẩn hóa |
| **[sanyabt/np-kg](https://github.com/sanyabt/np-kg)** | Mới | Natural Product-Drug Interaction KG framework | Học cách build KG cho TPCN |
| **[p32929/rotato](https://github.com/p32929/rotato)** | Mới | **Node.js proxy server xoay API key tự động** khi gặp 429 | Dùng cho các API có rate limit |
| **[pharmaDB/dailymed_data_processor](https://github.com/pharmaDB/dailymed_data_processor)** | Mới | Script Python xử lý DailyMed XML | Bulk download & parse nhãn thuốc |
| **[carriebennette/supplement-drug-viz](https://github.com/carriebennette/supplement-drug-viz)** | Mới | Code ví dụ dùng SUPP.AI API | Học cách gọi SUPP.AI đúng cách |
| **[nalgondalokesh/drug-food-interaction-biobert](https://github.com/nalgondalokesh/drug-food-interaction-biobert)** | Mới | BioBERT model dự đoán tương tác thuốc-thực phẩm | Thêm tính năng tương tác thực phẩm |
| **[Programmercito/nih-client](https://github.com/Programmercito/nih-client)** | Mới | NPM client cho NIH ODS API | Tích hợp nhanh dữ liệu TPCN từ NIH |

---

## 3. 📱 Xử Lý Sản Phẩm Từ Amazon & TikTokShop

### ✅ CÓ THỂ XỬ LÝ ĐƯỢC - Đây là chiến lược:

#### A. Flow Xử Lý Sản Phẩm Từ Nền Tảng Thương Mại Điện Tử

```
User quét mã vạch sản phẩm
        ↓
[Step 1] iOS Vision VNDetectBarcodesRequest → lấy UPC/EAN/GTIN
        ↓
[Step 2] Barcode Lookup (cascade strategy):
        ├──→ Open Food Facts API (miễn phí, không key, 3M+ food/supplement)
        ├──→ UPCitemdb (100 lookups/ngày free, 500M+ items)
        ├──→ EcomSource.ai (100 lookups/ngày free, 1.6B+ sản phẩm, CÓ Amazon data)
        └──→ Barcode Spider (free basic search, 1B+ entries)
        ↓
[Step 3] Nếu có ASIN/Amazon ID:
        ├──→ SerpApi Amazon Product API (free tier 100 searches/tháng)
        └──→ Lấy product description, ingredients, images
        ↓
[Step 4] Nếu TikTok Shop product URL:
        ├──→ SocialCrawl.dev TikTok Shop Product API (có free tier)
        └──→ syphoon.com scraper (lấy specifications, ingredients)
        ↓
[Step 5] Trích xuất thành phần:
        ├──→ Nếu có "Supplement Facts" trong description → parse text
        ├──→ Nếu có ảnh nhãn → iOS Vision OCR (như flow chính)
        └──→ Nếu chỉ có tên sản phẩm → tra cứu NIH DSLD API
        ↓
[Step 6] Chuẩn hóa & Kiểm tra tương tác (flow bình thường)
```

#### B. Các Barcode Lookup APIs Chi Tiết

| API | Free Tier | Database | Có TPCN không? | Cách gọi |
|-----|-----------|----------|----------------|----------|
| **Open Food Facts** | **Không giới hạn**, không cần key | 3M+ sản phẩm | ✅ Có nhiều TPCN/thực phẩm chức năng | `https://world.openfoodfacts.org/api/v2/product/{barcode}.json` |
| **UPCitemdb** | 100 lookups/ngày, không cần key | 500M+ items | ✅ Có | `https://api.upcitemdb.com/prod/trial/lookup?upc={code}` |
| **EcomSource.ai** | 100 lookups/ngày | 1.6B+ sản phẩm | ✅ Có, **kèm Amazon ASIN & rank** | API key đăng ký free |
| **ToolStock UPC Database** | Không cần key, miễn phí | 1.5M+ entries | ⚠️ Ít hơn | REST API |
| **Barcode Spider** | Free basic search | 1B+ entries | ✅ Có | Web + API |

#### C. Lưu Ý Quan Trọng Về Amazon/TikTokShop

- **TikTok Shop**: Từ 20/3/2026, **bắt buộc người bán cung cấp thông tin thành phần** cho sản phẩm sức khỏe/thực phẩm chức năng → dữ liệu có thể trích xuất được
- **Amazon**: Nhiều TPCN có "Important information" section liệt kê thành phần → SerpApi có thể parse được
- **Hạn chế**: Không phải sản phẩm nào cũng có thành phần được list đầy đủ trên trang bán hàng → **luôn cần backup bằng OCR ảnh nhãn** hoặc tra cứu NIH DSLD

---

## 4. 🔄 Chiến Lược Xoay Account API Chi Tiết

### A. Nguyên Tắc & Các Pattern

**Khi nào cần xoay?**
- API có rate limit theo ngày (như MedData API 250 calls/tháng)
- API có rate limit theo phút (như openFDA 240 req/phút với key)
- Free tier bị giới hạn nhưng cần nhiều request hơn

**3 Pattern chính:**

| Pattern | Mô tả | Dùng khi nào |
|---------|-------|-------------|
| **Round Robin Đơn Giản** | Xoay vòng tuần tự qua các key | Các key có cùng giới hạn, đơn giản |
| **Least Recently Used (LRU)** | Dùng key ít được dùng nhất | Cần cân bằng tải đều |
| **Error-Based Failover** | Dùng key A đến khi gặp 429, tự động chuyển sang B | Các API có rate limit không đồng đều |

### B. Tools & Thư Viện Sẵn Có

| Tool | Ngôn ngữ | Tính năng |
|------|----------|-----------|
| **[apikeyrotator](https://pypi.org/project/apikeyrotator/)** (PyPI) | Python | Tự động phân loại lỗi, cooldown, load từ .env |
| **[rotato](https://github.com/p32929/rotato)** | Node.js | Proxy server hoàn chỉnh, hỗ trợ streaming, hot config |
| **[keymux](https://www.npmjs.com/package/keymux)** | Node.js | Thay thế OpenAI client, tracking budget per key |
| **[openrouter-free](https://pypi.org/project/openrouter-free/)** | Python | Quản lý nhiều OpenRouter key, native hỗ trợ LlamaIndex/LangChain |

### C. Implementation Pattern - Python Ví Dụ

```python
# Cài đặt: pip install apikeyrotator python-dotenv requests

from apikeyrotator import APIKeyRotator
import requests
import time
from typing import Optional

class MedMatchAPIRotator:
    def __init__(self):
        # Load keys từ .env: MEDDATA_API_KEYS=key1,key2,key3
        self.rotator = APIKeyRotator()
        
        # Hoặc tự implement đơn giản:
        self.keys = [
            "meddata_key_1_from_email_1",
            "meddata_key_2_from_email_2", 
            "meddata_key_3_from_email_3",
        ]
        self.current_key_index = 0
        self.key_cooldowns = {}  # key -> timestamp khi hết cooldown
        
    def get_available_key(self) -> Optional[str]:
        """Lấy key khả dụng, bỏ qua các key đang cooldown"""
        now = time.time()
        for i in range(len(self.keys)):
            idx = (self.current_key_index + i) % len(self.keys)
            key = self.keys[idx]
            if key not in self.key_cooldowns or now >= self.key_cooldowns[key]:
                self.current_key_index = (idx + 1) % len(self.keys)
                return key
        return None  # Tất cả đều đang cooldown
    
    def call_meddata_api(self, supplement: str, drug: str) -> dict:
        """Gọi API với auto-rotation khi gặp 429"""
        max_attempts = len(self.keys) * 2
        
        for attempt in range(max_attempts):
            key = self.get_available_key()
            if key is None:
                # Tất cả key đều cooldown, chờ 60s
                time.sleep(60)
                continue
            
            headers = {"Authorization": f"Bearer {key}"}
            params = {"supplement": supplement, "drug": drug}
            
            try:
                response = requests.get(
                    "https://api.meddata.example.com/interactions",
                    headers=headers,
                    params=params,
                    timeout=10
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    # Rate limit, cooldown key này 1 giờ
                    self.key_cooldowns[key] = time.time() + 3600
                    print(f"Key {key[:8]}... hit rate limit, cooling down 1h")
                    continue
                else:
                    response.raise_for_status()
                    
            except requests.exceptions.RequestException as e:
                print(f"Request failed: {e}")
                continue
        
        raise Exception("All API keys exhausted or rate limited")
```

### D. Chiến Lược Đăng Ký Nhiều Account

| API | Free Tier | Cách xoay hiệu quả |
|-----|-----------|-------------------|
| **MedData API** | 250 calls/tháng/key | 3-5 account với các email khác nhau → 750-1,250 calls/tháng |
| **UPCitemdb** | 100 lookups/ngày/IP | Kết hợp với proxy IP rotation + nhiều account |
| **EcomSource.ai** | 100 lookups/ngày | Nhiều account email khác nhau |
| **SerpApi** | 100 searches/tháng | 2-3 account → 200-300 searches/tháng |
| **openFDA** | 240 req/phút có key, không giới hạn ngày | Đăng ký 2-3 API keys → 480-720 req/phút |
| **RxNorm API** | Không giới hạn rõ ràng | Không cần xoay, dùng trực tiếp |
| **SUPP.AI** | Không giới hạn công khai | Dùng trực tiếp, không cần key |
| **NIH DSLD API** | Không giới hạn công khai | Dùng trực tiếp, không cần key |

**Lưu ý đạo đức & pháp lý:**
- ✅ **Hợp lệ**: Đăng ký nhiều account với các email khác nhau cho mục đích phát triển & test
- ⚠️ **Cần thận trọng**: Không spam quá nhiều request, tôn trọng rate limit của nhà cung cấp
- ❌ **Không nên**: Dùng bot tạo hàng trăm account tự động → có thể bị ban IP/legal action
- 💡 **Chiến lược thông minh**: Ưu tiên các API **hoàn toàn không giới hạn** (SUPP.AI, RxNorm, DSLD) trước, chỉ xoay các API trả phí có free tier khi thực sự cần

---

## 5. 🏗️ Kiến Trúc Tổng Hợp Dữ Liệu Đề Xuất

### A. Pipeline Xây Dựng Knowledge Graph

```
Giai đoạn 1: Tải & Import (Một lần + định kỳ cập nhật)
┌─────────────────────────────────────────────────────────────┐
│  1. DDInter 2.0 CSV → PostgreSQL drug_interactions table    │
│  2. tapirro herb-drug JSON → supplement_drug_interactions   │
│  3. iDISK 2.0 dataset → supplements_entities table          │
│  4. SUPP.AI bulk crawl → supp_ai_interactions table         │
│  5. RxNorm full download → drug_names_mapping table         │
│  6. PubChem CID/CAS mapping → chemical_identifiers table    │
│  7. NIH ODS Fact Sheets crawl → supplement_safety_info      │
└──────────────────────────────┬──────────────────────────────┘
                               ↓
Giai đoạn 2: Chuẩn hóa & Hợp Nhất
┌─────────────────────────────────────────────────────────────┐
│  • Map tất cả tên thuốc về RxCUI (RxNorm API)               │
│  • Map tất cả tên TPCN về chuẩn hóa (iDISK + PubChem)       │
│  • Gán CAS Registry Number cho mỗi hoạt chất                 │
│  • Khử trùng lặp: cùng một cặp tương tác từ nhiều nguồn      │
│  • Xếp hạng độ tin cậy nguồn:                                │
│    - Tier 1: FDA/NIH chính thức (cao nhất)                   │
│    - Tier 2: DDInter, SUPP.AI evidence-based                 │
│    - Tier 3: Dự đoán từ KG/model AI (thấp nhất)             │
└──────────────────────────────┬──────────────────────────────┘
                               ↓
Giai đoạn 3: Làm Giàu & Mở Rộng
┌─────────────────────────────────────────────────────────────┐
│  • Thêm CYP450 enzyme pathways (medgraph repo)              │
│  • Thêm bằng chứng từ FAERS (số báo cáo sự cố)               │
│  • Thêm evidence sentences từ SUPP.AI                        │
│  • Thêm tương tác thuốc-thực phẩm (Kaggle dataset)           │
│  • Thêm tương tác TPCN-TPCN (NIH ODS + phân tích)            │
└──────────────────────────────┬──────────────────────────────┘
                               ↓
Giai đoạn 4: Export & Serve
┌─────────────────────────────────────────────────────────────┐
│  • Export ra PostgreSQL cho truy vấn nhanh                   │
│  • Export ra Neo4j cho phân tích đường dẫn cascade           │
│  • Build REST API wrapper (FastAPI/Flask)                    │
│  • Cache các truy vấn phổ biến (Redis)                       │
└─────────────────────────────────────────────────────────────┘
```

### B. Layered Query Engine Khi Runtime

```
Khi user quét sản phẩm → có danh sách thành phần:
        ↓
[Layer 1] Structured DB Lookup (PostgreSQL)
│  ├──→ Tìm trong bảng hợp nhất đã chuẩn hóa
│  └──→ Nếu tìm thấy → trả kết quả ngay (90% trường hợp phổ biến)
        ↓ (không tìm thấy hoặc cần thêm bằng chứng)
[Layer 2] Real-time API Enrichment
│  ├──→ SUPP.AI API (miễn phí, không giới hạn)
│  ├──→ openFDA FAERS (miễn phí)
│  └──→ NIH DSLD API (miễn phí)
        ↓ (cần dữ liệu thương mại điện tử)
[Layer 3] E-commerce Enrichment
│  ├──→ Open Food Facts barcode lookup
│  ├──→ UPCitemdb / EcomSource.ai
│  └──→ Amazon/TikTokShop scraper (nếu cần)
        ↓
[Layer 4] AI Synthesis
   └──→ Tổng hợp kết quả từ tất cả các layer → giải thích dễ hiểu
```

---

## 6. 📅 Kế Hoạch Thực Hiện Theo Giai Đoạn

### Giai đoạn 1: Nền Tảng Dữ Liệu Cốt Lõi (Tuần 1-4)

**Mục tiêu:** Xây dựng Knowledge Graph cơ bản với dữ liệu MIỄN PHÍ hoàn toàn

| Tuần | Công việc | Công cụ/Nguồn |
|------|----------|---------------|
| **1** | Setup PostgreSQL + import **DDInter 2.0** CSV | DDInter website download |
| **1** | Import **tapirro herb-drug** JSON (592 tương tác) | GitHub `tapirro/herb-drug-interaction-checker` |
| **2** | Tải & import **iDISK 2.0** dataset | GitHub `houyurain/iDISK2.0` |
| **2** | Tích hợp **RxNorm API** chuẩn hóa tên thuốc | `rxnav.nlm.nih.gov/REST` |
| **3** | Tích hợp **SUPP.AI API** làm bằng chứng | `supp.ai/api` |
| **3** | Tích hợp **NIH DSLD API** tra cứu nhãn TPCN | `dsldapi.od.nih.gov` |
| **4** | Tích hợp **PubChem PUG REST** chuẩn hóa hóa chất | `pubchem.ncbi.nlm.nih.gov/rest/pug` |
| **4** | Build **cơ chế xếp hạng độ tin cậy** nguồn | Logic tự xây dựng |

**Kết quả:** Database có ~240K drug-drug + ~60K drug-supplement interactions, chuẩn hóa tên, miễn phí 100%

### Giai đoạn 2: Mở Rộng & Làm Giàu (Tuần 5-8)

| Tuần | Công việc | Công cụ/Nguồn |
|------|----------|---------------|
| **5** | Bulk download **DailyMed** full labels → parse `drug_interactions` section | `dailymed.nlm.nih.gov` + `pharmaDB/dailymed_data_processor` |
| **5** | Tích hợp **openFDA FAERS** đếm số báo cáo sự cố | `api.fda.gov/drug/event.json` |
| **6** | Thêm **CYP450 enzyme pathways** | Fork `HieuNTg/medgraph` học thuật |
| **6** | Import **Kaggle Drug-Food Interactions** dataset | Kaggle |
| **7** | Build **Barcode Lookup cascade** (Open Food Facts → UPCitemdb) | Các API miễn phí |
| **7** | Setup **API key rotator** cho các API có free tier | `apikeyrotator` PyPI hoặc tự build |
| **8** | Tích hợp **Amazon/TikTokShop enrichment** | SerpApi + SocialCrawl (free tier + xoay account) |

### Giai đoạn 3: Tối Ưu & Nâng Cấp (Tuần 9-12)

| Tuần | Công việc |
|------|----------|
| **9** | Import **NP-KG** natural product data | Zenodo download |
| **10** | Setup **Neo4j graph database** cho phân tích cascade | Fork `jmponcebe/PharmaGraphRAG` |
| **11** | Build **cache layer** (Redis) cho các truy vấn phổ biến |
| **12** | Performance tuning, bulk test với 1000+ truy vấn |

---

## 7. 💰 Tóm Tắt Chi Phí & Ưu Tiên

### Các Nguồn HOÀN TOÀN MIỄN PHÍ (Ưu tiên cao nhất)

| Nguồn | Giá trị | Hạn chế duy nhất |
|-------|---------|-----------------|
| **SUPP.AI** | 59K tương tác TPCN-thuốc + evidence | Không có |
| **DDInter 2.0** | 240K tương tác thuốc-thuốc | License NC-SA (cần xem xét khi bán) |
| **RxNorm API** | Chuẩn hóa tên thuốc | Không có |
| **NIH DSLD API** | Dữ liệu nhãn TPCN chính phủ | Không có |
| **PubChem PUG REST** | Chuẩn hóa hóa chất | Không có |
| **openFDA** | Nhãn thuốc + FAERS | 240 req/phút (dễ dàng vượt qua với nhiều key) |
| **DailyMed Bulk** | Toàn bộ nhãn thuốc XML | Cần download & parse |
| **iDISK 2.0** | TPCN Knowledgebase | Cần tự import |
| **tapirro herb-drug** | 592 tương tác thảo dược | Quy mô nhỏ |
| **Open Food Facts** | Barcode lookup | Chủ yếu food, ít TPCN hơn |

### Các Nguồn Cần Xoay Account (Free Tier)

| API | Free Tier | Số account đề xuất | Tổng capacity |
|-----|-----------|-------------------|---------------|
| MedData API | 250 calls/tháng | 3 | 750 calls/tháng |
| UPCitemdb | 100 lookups/ngày | 2 | 200 lookups/ngày |
| EcomSource.ai | 100 lookups/ngày | 2 | 200 lookups/ngày |
| SerpApi (Amazon) | 100 searches/tháng | 2 | 200 searches/tháng |
| openFDA API key | 240 req/phút | 2 | 480 req/phút |

### Lời Khuyên Cuối Cùng

**Bắt đầu với 100% nguồn miễn phí trước** - SUPP.AI + DDInter + RxNorm + NIH DSLD + PubChem + tapirro JSON. 5 nguồn này đủ để xây dựng MVP mạnh mẽ với **hàng trăm nghìn tương tác**, hoàn toàn không tốn chi phí API.

Chỉ khi user tăng trưởng và cần nhiều dữ liệu hơn, mới xem xét:
1. Xoay account free tier cho các API bổ sung
2. Đăng ký gói trả phí thấp ($20-29/tháng) cho các API cốt lõi
3. Thuê dược sĩ kiểm chứng các tương tác phổ biến nhất để tăng độ tin cậy

Concept của bạn có đủ dữ liệu miễn phí để xây dựng sản phẩm hoàn chỉnh. Vấn đề không phải "thiếu dữ liệu" mà là **làm sao tổng hợp và chuẩn hóa chúng một cách thông minh**.
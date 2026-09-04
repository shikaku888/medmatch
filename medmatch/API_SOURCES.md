# MedMatch – Drug Interaction Data Sources

A curated list of drug‑interaction APIs (free and commercial) that can be integrated into the MedMatch backend. Each entry includes the provider, license/terms, pricing tier, typical coverage, and a short note.

---

## 🟢 Free / Open‑source / Public‑domain

| # | API / Source | License / Terms | Pricing | Typical Coverage | Notes |
|---|--------------|-----------------|---------|------------------|-------|
| 1 | **openFDA** (`https://api.fda.gov`) | Public domain (U.S. Government) – free for commercial use with attribution. | Free (10 requests/second, scalable with key). | Drug‑drug, drug‑food, drug‑event (FAERS), recalls, label data, FDA drug interactions. | Primary free source; rate‑limits apply; good for real‑time look‑ups. |
| 2 | **tapirro herb‑drug‑interaction‑checker** (GitHub) | MIT License – permissive, allows commercial use, keep copyright notice. | Free (data set included in the repo). | 565 herb‑drug interactions, 592 TPCN‑drug pairs, 250 medicinal plants. | Already embedded in the project; can be served directly from backend. |
| 3 | **PubChem PUG REST** (`https://pubchem.ncbi.nlm.nih.gov/rest/pug`) | Public domain (NCBI/NLM). | Free, no key required. | Chemical structures, CID/CAS, some enzyme markers, metabolite info. | Useful for CYP450 inference and substance identification. |
| 4 | **OnSIDES** (GitHub) | CC‑BY 4.0 – requires attribution, allowed for commercial products. | Free (data download). | 7 554 drug‑drug/interaction pairs from FDA/EMA/EMC/KEGG. | Provide detailed MedDRA PT and source attribution. |
| 5 | **Verified Supplement Evidence** (GitHub) | MIT License – commercial allowed. | Free (dataset included). | 21 drug‑nutrient depletion interactions, 72 supplement recommendations. | Good for “nutrient depletion” use‑case. |
| 6 | **RxNorm** (UMLS) | Public domain. | Free. | Normalized drug names, RxCUI mapping, ingredient synonyms. | Foundational for all mapping/lookup operations. |

---

## 🟡 Free tier with limitations (may need upgrade for production)

| # | API / Source | License / Terms | Free tier | Paid / Commercial upgrade | Coverage |
|---|--------------|-----------------|-----------|--------------------------|----------|
| 7 | **Arborpharmchem Drugs API** (`https://www.arborpharmchem.com/drugs-api/`) | Commercial license (details on site). | Free tier: limited number of requests per month (e.g., 1 000). | Paid plans: higher quota, SLA, priority support. | Drug‑drug, drug‑food, drug‑condition, severity, mechanism of action. |
| 8 | **VigiAccess API** (WHO‑UMC) (`https://who-umc.org/vigibase-data-access/vigiaccess-api/`) | Free for commercial use – no explicit license restriction. | Free (unlimited queries after simple registration with email). | Optional premium package for faster support / larger data dumps. | Real‑world adverse‑drug‑reaction reports from VigiBase; good for “safety signal” detection. |
| 9 | **CredibleMeds / RxISK** (`https://crediblemeds.org/`, `https://rxisk.org/`) | Free for personal/non‑commercial; commercial license available. | Free tier: list of high‑risk drug interactions (≈ 200‑300 entries). | Paid license: full dataset, API access, bulk download. | Focus on clinically important interactions (e.g., QT prolongation, severe hypotension). |

---

## 🔴 Commercial / Paid APIs (high‑quality, licensed data)

| # | API / Source | License / Terms | Pricing (typical) | Coverage / Strengths | When to consider |
|---|--------------|-----------------|-------------------|----------------------|------------------|
| 10 | **DrugBank** (`https://www.drugbank.ca/`) | Commercial license – requires purchase (per‑developer or site‑license). | **Trial**: limited access (few hundred drugs). **Enterprise**: $15 K‑$30 K / year (full database). | > 10 000 drug‑drug interactions, detailed CYP450 enzyme pathways, mechanism of action, pharmacology, food‑drug interactions, clinical trials. | When the project needs the most exhaustive, curated interaction data and is willing to pay for depth and reliability. |
| 11 | **Micromedex** (Wolters Kluwer) | Commercial license – per‑institution pricing. | Typically $1 K‑$5 K / year (depends on user count). | Comprehensive drug‑drug, drug‑food, dosing, guidelines, IV compatibility, disease‑specific interactions. | For regulated health‑care apps that must cite premium, peer‑reviewed sources. |
| 12 | **Lexicomp** (Wolters Kluwer) | Commercial license – similar pricing to Micromedex. | $1 K‑$4 K / year. | Drug‑drug, drug‑food, alternative therapy interactions, laboratory monitoring guidelines. | Alternative to Micromedex; often bundled with other Wolters Kluwer products. |
| 13 | **Arborpharmchem (paid plan)** (`https://www.arborpharmchem.com/drugs-api/`) | Commercial license – after free tier. | **Pro**: ~$100‑$300 / month for 10 000‑50 000 requests/mo. **Enterprise**: custom. | Same as free tier but with higher quota, SLA, additional fields (e.g., pharmacy‑level data). | If free tier hits limits and you need guaranteed uptime and support. |
| 14 | **OpenAI / Gemini Interactions API** (beta) (refer to recent announcements) | Commercial via OpenAI usage‑based pricing. | Pay‑as‑you‑go (≈ $0.002‑$0.01 per 1 K tokens). | Natural‑language generation of interaction summaries, may use latest biomedical literature. | When you want LLM‑driven narrative explanations alongside structured data. |

---

## 📦 How to integrate

1. **Prioritise free / open sources** (openFDA, tapirro, PubChem, OnSIDES, Verified Supplement Evidence) for the MVP – no cost, MIT/CC‑BY licences are easy to comply with.
2. **Add Arborpharmchem or VigiAccess** once the free quotas are approached; they provide additional drug‑food and real‑world ADR data.
3. **If the product targets clinical‑grade safety** or needs to differentiate from competitors, evaluate DrugBank, Micromedex or Lexicomp and purchase a license.
4. **Implement a wrapper layer** (`backend/api_interact.py`) that:
   - Calls the free APIs first.
   - Falls back to the paid API when rate‑limit or data‑gap occurs.
   - Normalises all responses into a common schema (`interaction_id`, `drug_a`, `drug_b`, `severity`, `mechanism`, `source`, `citation`).
   - Stores the source metadata for the `NOTICE` / `LICENSE` file required by the project.

---

## 📄 License‑compliance reminder

- **MIT / CC‑BY** – keep the original copyright notice in the code or a `NOTICE` file; acceptable for commercial products.
- **Public domain** – no legal requirement, but attribution is good practice.
- **Commercial licenses** – follow the specific terms (often require displaying the vendor name, paying fees, or restricting redistribution). Add a `LICENSE` file in the repo that references the purchased product and version.

---

*Generated on 2025‑08‑31 for the MedMatch project.*
## 🟡 Newly discovered sources (additional research, 2025)

| # | API / Source | License / Terms | Pricing | Coverage / Notes |
|---|--------------|-----------------|---------|-------------------|
| 15 | **ChEMBL API** (`https://www.ebi.ac.uk/chembl/webservices/core/`) | **CC BY‑SA 4.0** (attribution + share alike); commercial permissible if attribution kept. | **Free** (no key required for basic queries; bulk downloads available). | Bioactivity, drug‑target interactions, ADMET, enzyme (CYP) annotations, literature links. Excellent for enrichment of interaction mechanism data. |
| 16 | **OpenPHACTS** (`https://www.openphactsfoundation.org/platform/`) | **Commercial‑grade API** – provides unified pharmaceutical data; licensing depends on use case (free for research, commercial license available). | **Free** for academic/research; **paid** commercial license for products. | Aggregates ChEMBL, DrugBank, Uniprot, etc.; provides semantic links (drug → target → pathway). Useful if you want a single endpoint rather than calling multiple APIs. |
| 17 | **Therapeutics Data Commons (TDC)** (`https://tdcommons.ai/`) | **Open source / MIT** for code; data licenses vary by dataset (mostly public domain or CC0 for core ADMET). | **Free** (download datasets + API endpoints). | ADMET prediction, drug‑target interaction benchmarks, drug‑drug interaction datasets (DDI corpus). Good for training/custom ML models or validating predictions. |
| 18 | **Layered Drug‑Food Interaction Engine** (GitHub repo by `shravya...` / `AcadMate`) | MIT / academic open source (check repo LICENSE). | **Free** (self‑hosted). | Modular rule engine for drug‑food interactions; can be integrated as a backend microservice if you need custom rules. |

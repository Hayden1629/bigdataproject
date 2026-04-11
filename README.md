# FDA FAERS Drug Safety Intelligence Platform

**Team 11 — Adverse Drug Event Analysis Using FDA FAERS Data**  
Amogha Yalgi · Austin Ganje · Hannah Huang · Hayden Herstrom · Rachel Le

---

## Executive Summary

The FDA Adverse Event Reporting System (FAERS) contains over 31 million voluntary adverse drug event reports submitted by patients, healthcare providers, and manufacturers. The data is notoriously messy: drug names are free-text, reaction terms vary by reporter, and duplicates accumulate across quarterly updates. This platform transforms raw FAERS data into an analyst-facing pharmacovigilance intelligence tool.

We built a five-tab Streamlit dashboard that provides:

- **Overview** — global dataset KPIs, quarter-over-quarter trending, world choropleth map, top drug and reaction rankings, country and reporter-type breakdowns.
- **Drug Explorer** — type any drug name (brand, generic, misspelling) and instantly retrieve full adverse event profiles: top reactions, outcomes, demographic breakdown, labeled indications, co-reported drugs, and AI-generated signal interpretation (Claude Haiku).
- **Drug Comparison** — side-by-side comparison of two drugs: overlaid quarterly trend, shared reaction rate analysis (per 1,000 cases), outcome distributions, and signal tables.
- **Signal Intelligence** — Proportional Reporting Ratio (PRR) and chi-squared pharmacovigilance signals across 511,218 drug-reaction pairs, color-coded HIGH / MEDIUM / LOW with interactive scatter plot and CSV export.
- **Reaction Explorer** — semantic search in plain English ("heart attack", "throwing up", "brain fog") mapped to MedDRA Preferred Terms via a curated synonym dictionary and fuzzy fallback.

**Dataset:** FDA FAERS public quarterly extracts, 2023 Q3 – 2025 Q2 (8 quarters), ~2.85 million deduplicated cases.

---

## Key Features

| Feature | Implementation |
|---|---|
| Drug name normalization | RxNorm API (NLM) + fuzzy matching (RapidFuzz WRatio) |
| Reaction semantic search | Curated lay-term → MedDRA PT synonym map (128 entries) + fuzzy fallback |
| Pharmacovigilance signals | PRR / ROR / chi-squared (Evans et al. 2001 thresholds) |
| Drug comparison | Side-by-side KPIs, shared reaction rates per 1,000 cases, overlaid trend |
| AI signal interpretation | Claude Haiku generates plain-English pharmacovigilance summaries |
| World map | Plotly choropleth — 117 countries with report volume |
| Deduplication | Max `caseversion` per `caseid` per FDA guidance |
| Performance | Pre-computed Parquet cache; all queries < 100 ms |
| Containerization | Docker + docker-compose |

---

## Dataset

| Metric | Value |
|---|---|
| Source | [FDA FAERS Public Dashboard](https://www.fda.gov/drugs/questions-and-answers-fdas-adverse-event-reporting-system-faers/fda-adverse-event-reporting-system-faers-public-dashboard) |
| Quarters ingested | 2022Q3 – 2024Q4 (8 quarters) |
| Deduplicated cases | ~2.85 million |
| Unique drug names | 87,845 |
| Unique MedDRA PTs | 18,401 |
| PRR signal pairs | 511,218 |
| HIGH signals (PRR ≥ 4, N ≥ 5, χ² ≥ 4) | 188,348 |

FAERS consists of 7 relational tables linked by `primaryid`: demographics (`demo`), drugs (`drug`), reactions (`reac`), outcomes (`outc`), report sources (`rpsr`), therapy dates (`ther`), and indications (`indi`).

---

## Architecture

```
FDA FAERS Quarterly ZIPs
        │
        ▼
utils/download_data.py          # Download and extract raw ASCII files
utils/load_into_df.py           # Load into pandas DataFrames
utils/resave_as_parquet.py      # Convert to Parquet (columnar, fast reads)
        │
        ▼
data/parquet_recent/            # 7 Parquet tables (demo, drug, reac, outc, ...)
        │
        ▼
claude_test/precompute.py       # One-time: build PRR table, drug/reac summaries,
        │                       # quarterly trend caches → claude_test/cache/
        ▼
claude_test/cache/              # Pre-computed Parquet files (fast startup)
  ├── prr_table.parquet         # 511,218 drug–reaction PRR signals
  ├── drug_summary.parquet      # Per-drug case counts
  ├── reac_summary.parquet      # Per-reaction case counts
  ├── quarterly_drug.parquet    # Drug × quarter case counts
  └── quarterly_reac.parquet    # Reaction × quarter case counts
        │
        ▼
claude_test/app.py              # Streamlit dashboard (4 tabs)
```

**Supporting modules:**

| Module | Responsibility |
|---|---|
| `data_loader.py` | Load + cache all 7 FAERS tables; deduplication |
| `queries.py` | Cached query layer; stable cache keys per drug/reaction search |
| `analytics.py` | Pure computation: KPIs, aggregations, trend series |
| `signal_detection.py` | PRR/ROR/chi2 signal retrieval from pre-computed table |
| `drug_normalizer.py` | RxNorm API lookup + fuzzy FAERS name matching |
| `reaction_search.py` | Lay-term → MedDRA PT synonym dictionary + fuzzy fallback |
| `signal_interpreter.py` | Claude Haiku AI-generated plain-English signal summaries |

---

## Signal Detection Methodology

Pharmacovigilance disproportionality analysis following Evans et al. (2001):

```
PRR = (a / (a+b)) / (c / (c+d))

where:
  a = reports with drug D AND reaction R
  b = reports with drug D, without R
  c = reports without D, with R
  d = reports without D or R

Chi-squared (Yates corrected):
  χ² = N(|ad - bc| - 0.5N)² / ((a+b)(c+d)(a+c)(b+d))
```

Signal thresholds:

| Level | PRR | N (drug-reaction) | χ² |
|---|---|---|---|
| HIGH | ≥ 4 | ≥ 5 | ≥ 4 |
| MEDIUM | ≥ 2 | ≥ 3 | ≥ 4 |
| LOW | ≥ 1.5 | ≥ 3 | — |

Signals are ranked by chi-squared (not PRR) to avoid inflation from small cell counts.

---

## Installation and Setup

### Prerequisites

- Python 3.10+
- ~2 GB disk for Parquet data files
- Internet access (for RxNorm API calls at runtime)

### 1. Clone and install dependencies

```bash
git clone https://github.com/Hayden1629/bigdataproject.git
cd bigdataproject
pip install -r claude_test/requirements.txt
```

### 2. Download FAERS data

```bash
python utils/download_data.py        # Downloads quarterly ZIP files
python utils/load_into_df.py         # Parses ASCII → DataFrames
python utils/resave_as_parquet.py    # Saves as Parquet to data/parquet_recent/
```

### 3. Pre-compute signal cache (run once, ~3–5 minutes)

```bash
python claude_test/precompute.py
```

This builds all files under `claude_test/cache/`. After this step, all dashboard queries run in under 100 ms.

### 4. Launch the dashboard

```bash
streamlit run claude_test/app.py
```

Navigate to `http://localhost:8501`.

### Docker (alternative)

```bash
cd claude_test
docker-compose up --build
```

---

## Usage

### Drug Explorer

1. Enter any drug name in the search box (brand name, generic, partial name, or misspelling).
2. The platform queries the RxNorm API to find canonical names and related identifiers, then matches all FAERS records containing those terms.
3. Results include: case count, outcome distribution, top 20 adverse reactions, quarterly trend, demographic breakdown (age, sex, reporter type), labeled indications, co-reported drugs, and PRR signals with forest plot.

### Reaction Explorer

1. Enter a plain-English symptom description ("chest pain", "throwing up", "memory loss").
2. The platform maps your query to MedDRA Preferred Terms via a curated synonym dictionary (80+ lay terms) and fuzzy string matching.
3. Results include matched PT list with scores, case counts, top associated drugs, outcomes, and quarterly trend.

### Signal Intelligence

1. Use the filter panel to select signal level (HIGH / MEDIUM / LOW), minimum case count, and optional drug or reaction text filter.
2. The PRR scatter plot shows log₂(PRR) vs. log₁₀(N) for each signal, colored by level.
3. The signal table is sortable and downloadable as CSV.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Data storage | Apache Parquet (via pandas + pyarrow) |
| Drug normalization | RxNorm REST API (NLM/NIH, free) |
| Fuzzy matching | RapidFuzz (WRatio scorer) |
| Signal detection | PRR/ROR/chi-squared (custom Python) |
| Dashboard | Streamlit |
| Visualization | Plotly |
| Containerization | Docker + docker-compose |

---

## Repository Structure

```
bigdataproject/
├── README.md
├── claude_test/                # Dashboard application
│   ├── app.py                  # Main Streamlit app (4 tabs)
│   ├── queries.py              # Cached query layer
│   ├── data_loader.py          # FAERS table loading + caching
│   ├── analytics.py            # Aggregation and KPI functions
│   ├── signal_detection.py     # PRR signal retrieval
│   ├── drug_normalizer.py      # RxNorm + fuzzy drug name matching
│   ├── reaction_search.py      # Semantic reaction search
│   ├── precompute.py           # One-time cache builder
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── cache/                  # Pre-computed Parquet files (gitignored)
├── data/
│   └── parquet_recent/         # FAERS source tables (gitignored, large)
├── utils/                      # Data download and conversion utilities
├── rubric_and_plan/            # Assignment materials
└── flier/                      # Project flier (PDF)
```

---

## References

- Evans, S.J.W., Waller, P.C., Davis, S. (2001). Use of proportional reporting ratios (PRRs) for signal generation from spontaneous adverse drug reaction reports. *Pharmacoepidemiology and Drug Safety*, 10(6), 483–486.
- FDA FAERS Public Dashboard: https://www.fda.gov/drugs/fda-adverse-event-monitoring-system-aems/fda-adverse-event-monitoring-system-aems-public-dashboard
- NLM RxNorm API: https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html
- MedDRA: Medical Dictionary for Regulatory Activities (MSSO)

---

This project repository is created in partial fulfillment of the requirements for the Big Data Analytics course offered by the Master of Science in Business Analytics program at the Carlson School of Management, University of Minnesota.

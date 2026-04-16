# FDA FAERS Drug Safety Intelligence Platform

**Team 11 — Adverse Drug Event Analysis Using FDA FAERS Data**  
Amogha Yalgi · Austin Ganje · Hannah Huang · Hayden Herstrom · Rachel Le  
Carlson MSBA 6331 · Spring 2026

---

## Running the Dashboard

```bash
# Install dependencies (once)
pip install -r dashboard/requirements.txt

# Build a small recent dataset for testing
python3 utils/STARTHERE.py --mode recent
FAERS_PARQUET_DIR=data/parquet_recent FAERS_CACHE_DIR=dashboard/cache_recent python3 dashboard/precompute.py

# Launch the dashboard on that dataset
python3 utils/run_dashboard.py --mode recent

# Run the test suite first, then launch (aborts on failure)
python3 utils/run_dashboard.py --mode recent --test
```

Open `http://localhost:8501`.

> For the full setup walkthrough, see **[dashboard/GUIDE.md](dashboard/GUIDE.md)**. For Databricks + Spark deployment, see **[DATABRICKS_DEPLOYMENT.md](DATABRICKS_DEPLOYMENT.md)**.

---

## What It Does

An exploratory pharmacovigilance platform built on deduplicated FDA FAERS adverse event reports (2023 Q3 – 2025 Q2). The dashboard is organized around five analyst workflows:

| Tab | Description |
|---|---|
| **Overview** | Global KPIs, quarterly trend, top drugs/reactions, world choropleth map, QoQ trending, global HIGH signal table |
| **Drug Explorer** | Search any drug name → full adverse event profile: reactions, outcomes, demographics, geography, indications, co-medications, PRR signals, AI summary, and live research context |
| **Drug Comparison** | Side-by-side comparison of two drugs: overlaid trend, shared reaction rates per 1,000 cases, outcome distributions, HIGH signal tables |
| **Signal Intelligence** | Filterable PRR/chi² signal landscape across 511K drug-reaction pairs, scatter plot + downloadable table |
| **Reaction Explorer** | Search in plain English ("heart attack", "throwing up") → mapped to MedDRA terms → top associated drugs, signals, trend |

---

## Key Features

| Feature | Implementation |
|---|---|
| Drug name normalization | RxNorm API (NLM) + RapidFuzz fuzzy matching |
| Reaction semantic search | 128-entry lay-term → MedDRA synonym map + fuzzy fallback |
| Pharmacovigilance signals | PRR / ROR / chi-squared (Evans et al. 2001) — 511K pairs pre-computed |
| Drug comparison | Side-by-side KPIs, shared reaction rates per 1,000 cases, overlaid trend |
| AI signal interpretation | Claude Haiku (`claude-haiku-4-5`) plain-English summaries — set `ANTHROPIC_API_KEY` |
| Clinical trials | ClinicalTrials.gov v2 API — real-time, no key required |
| Literature search | PubMed eutils — real-time, supports MeSH field tags, no key required |
| Deduplication | Max `caseversion` per `caseid` per FDA guidance |
| Dataset modes | Run against a smaller recent parquet set for testing or the full parquet history for final analysis |
| Performance | Pre-computed Parquet cache, indexed lookup tables, and persistent disk cache for external API responses (RxNorm, openFDA, ClinicalTrials, PubMed) — repeated drug searches never hit the network after the first lookup |
| Cloud-ready | Data paths configurable via `FAERS_PARQUET_DIR` / `FAERS_CACHE_DIR` env vars |
| Containerized | Docker + docker-compose |

---

## Dataset

| Metric | Value |
|---|---|
| Source | FDA FAERS public quarterly ASCII extracts |
| Quarters | 2023 Q3 – 2025 Q2 (8 quarters) |
| Deduplicated cases | ~2.85 million |
| Unique drug names | 87,845 |
| Unique MedDRA PTs | 18,401 |
| PRR signal pairs | 511,218 |
| HIGH signals | 188,348 |

For day-to-day development you can use the smaller `recent` parquet build. For final results, switch to `full` and rebuild the cache:

```bash
python3 utils/STARTHERE.py --mode full
FAERS_PARQUET_DIR=data/parquet FAERS_CACHE_DIR=dashboard/cache_full python3 dashboard/precompute.py
python3 utils/run_dashboard.py --mode full
```

---

## Repository Structure

```
bigdataproject/
├── README.md
├── dashboard/                   # Dashboard application (run from here)
│   ├── app.py                   # Thin Streamlit entrypoint
│   ├── queries.py               # Cached query layer backed by indexed case lookups
│   ├── data_loader.py           # FAERS loading, deduplication, and reusable lookup tables
│   ├── analytics.py             # Pure pandas KPIs and aggregations
│   ├── api_cache.py             # Persistent disk cache for external API calls
│   ├── drug_normalizer.py       # RxNorm API + fuzzy drug name matching
│   ├── reaction_search.py       # Lay-term → MedDRA semantic search
│   ├── research_connector.py    # ClinicalTrials.gov + PubMed live connectors
│   ├── precompute.py            # One-time cache builder (run before first launch)
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── GUIDE.md                 # Full developer and user guide
│   ├── ui.py                    # Shared styling, UI helpers, and chart builders
│   ├── sidebar.py               # Global filter/sidebar renderer
│   ├── views/                   # One module per dashboard tab
│   ├── .streamlit/config.toml   # Streamlit settings
│   ├── cache_recent/            # Cache for recent parquet dataset
│   └── cache_full/              # Cache for full parquet dataset
├── data/
│   ├── parquet_recent/          # Smaller recent parquet dataset for testing
│   └── parquet/                 # Full parquet history
├── utils/                       # Data download and conversion scripts
│   ├── download_faers.sh        # Download quarterly ZIPs from FDA
│   ├── load_faers.py            # Parse ASCII → pandas tables
│   ├── STARTHERE.py             # Build recent/full parquet datasets
│   └── run_dashboard.py         # Launch dashboard with matching env vars
├── rubric_and_plan/             # Assignment materials
├── DATABRICKS_DEPLOYMENT.md     # Databricks + Spark deployment guide
├── DATA_DICTIONARY.md           # FAERS column definitions
└── flier/                       # Project flier
```

---

## Signal Detection Methodology

Proportional Reporting Ratio (PRR) following Evans et al. (2001):

```
PRR = (a / (a+b)) / (c / (c+d))

  a = reports with drug D AND reaction R
  b = reports with drug D, without R
  c = reports without D, with R
  d = reports without D or R
```

| Signal Level | PRR | Co-occurrences (N) | χ² |
|---|---|---|---|
| HIGH | ≥ 4 | ≥ 5 | ≥ 4 |
| MEDIUM | ≥ 2 | ≥ 3 | ≥ 4 |
| LOW | ≥ 1.5 | ≥ 3 | — |

FAERS is a spontaneous reporting system. Signals indicate disproportionate co-reporting — they do not establish causality.

---

## References

- Evans, S.J.W., Waller, P.C., Davis, S. (2001). Use of proportional reporting ratios (PRRs) for signal generation from spontaneous adverse drug reaction reports. *Pharmacoepidemiology and Drug Safety*, 10(6), 483–486.
- FDA FAERS: https://www.fda.gov/drugs/fda-adverse-event-monitoring-system-aems
- NLM RxNorm API: https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html

---

*This project repository is created in partial fulfillment of the requirements for the Big Data Analytics course offered by the Master of Science in Business Analytics program at the Carlson School of Management, University of Minnesota.*

# FDA FAERS Drug Safety Intelligence Platform

**Team 11 — Adverse Drug Event Analysis Using FDA FAERS Data**  
Amogha Yalgi · Austin Ganje · Hannah Huang · Hayden Herstrom · Rachel Le  
Carlson MSBA 6331 · Spring 2026

---

## Running the Dashboard

```bash
# Install dependencies (once)
pip install -r dashboard/requirements.txt

# Build the signal cache (once, ~3–5 minutes)
python dashboard/precompute.py

# Launch
streamlit run dashboard/app.py
```

Open `http://localhost:8501`.

> For the full setup walkthrough (downloading raw FAERS data, Docker, cloud deployment), see **[dashboard/GUIDE.md](dashboard/GUIDE.md)**.

---

## What It Does

An exploratory pharmacovigilance platform built on 2.85 million deduplicated FDA FAERS adverse event reports (2023 Q3 – 2025 Q2). Six tabs:

| Tab | Description |
|---|---|
| **Overview** | Global KPIs, quarterly trend, top drugs/reactions, world choropleth map, QoQ trending, global HIGH signal table |
| **Drug Explorer** | Search any drug name → full adverse event profile: reactions, outcomes, demographics, geography, indications, co-medications, PRR signals, AI summary |
| **Drug Comparison** | Side-by-side comparison of two drugs: overlaid trend, shared reaction rates per 1,000 cases, outcome distributions, HIGH signal tables |
| **Signal Intelligence** | Filterable PRR/chi² signal landscape across 511K drug-reaction pairs, scatter plot + downloadable table |
| **Reaction Explorer** | Search in plain English ("heart attack", "throwing up") → mapped to MedDRA terms → top associated drugs, signals, trend |
| **Research Hub** | Live search: ClinicalTrials.gov (trials by condition or drug) + PubMed (literature by drug/symptom) |

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
| Performance | Pre-computed Parquet cache; all queries < 100 ms |
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

---

## Repository Structure

```
bigdataproject/
├── README.md
├── dashboard/                   # Dashboard application (run from here)
│   ├── app.py                   # Main Streamlit app — 6 tabs
│   ├── queries.py               # Streamlit-cached query layer
│   ├── data_loader.py           # FAERS table loading, deduplication, path config
│   ├── analytics.py             # Pure pandas KPIs and aggregations
│   ├── signal_detection.py      # PRR signal retrieval from pre-computed table
│   ├── drug_normalizer.py       # RxNorm API + fuzzy drug name matching
│   ├── reaction_search.py       # Lay-term → MedDRA semantic search
│   ├── signal_interpreter.py    # Claude Haiku AI signal summaries
│   ├── research_connector.py    # ClinicalTrials.gov + PubMed live connectors
│   ├── precompute.py            # One-time cache builder (run before first launch)
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── GUIDE.md                 # Full developer and user guide
│   ├── .streamlit/config.toml   # Dark theme + server settings
│   └── cache/                   # Pre-computed Parquet files (gitignored)
│       ├── prr_table.parquet    # 511K drug-reaction signals
│       ├── drug_summary.parquet
│       ├── reac_summary.parquet
│       ├── quarterly_drug.parquet
│       └── quarterly_reac.parquet
├── data/
│   └── parquet_recent/          # FAERS source tables — 7 parquet files (gitignored)
├── utils/                       # Data download and conversion scripts
│   ├── download_faers.sh        # Download quarterly ZIPs from FDA
│   └── load_faers.py            # Parse ASCII → pandas → Parquet
├── rubric_and_plan/             # Assignment materials
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

*Created in partial fulfillment of Big Data Analytics (MSBA 6331), Carlson School of Management, University of Minnesota.*

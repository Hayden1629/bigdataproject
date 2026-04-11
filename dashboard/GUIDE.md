# FAERS Drug Safety Intelligence — Developer & User Guide

**Team 11 · Carlson MSBA 6331 · Spring 2026**

---

## Quick Start (local)

```bash
# From the project root (bigdataproject/)
pip install -r dashboard/requirements.txt   # first time only
python dashboard/precompute.py              # first time only (~3–5 min)
streamlit run dashboard/app.py
```

Open `http://localhost:8501` in your browser.

> **Prerequisite:** FAERS parquet data must be in `data/parquet_recent/` and the
> signal cache must be built. See [Setup](#setup) below if starting from scratch.

---

## What This Dashboard Does

An exploratory pharmacovigilance platform built on **FDA FAERS** — the Adverse Event
Reporting System that collects voluntary reports of drug side effects from patients,
healthcare providers, and manufacturers. The dataset covers 2023 Q3 through 2025 Q2
(~2.85 million deduplicated cases).

The dashboard answers questions like:
- *"What are the most commonly reported side effects of Ozempic?"*
- *"How does dupilumab compare to tralokinumab on adverse event rates?"*
- *"Which drugs have the strongest statistical signal for liver injury?"*
- *"Is nausea trending up for semaglutide over the last 8 quarters?"*
- *"What does the FDA approval history look like for tirzepatide?"*
- *"What clinical trials are currently recruiting for atrial fibrillation?"*

---

## Tab-by-Tab Guide

The app has **five tabs**: Overview · Drug Explorer · Drug Comparison · Signal Intelligence · Reaction Explorer.

**Sidebar filters** (visible on all tabs):
- **Quarters** — multi-select to include/exclude specific quarters
- **Drug role** — Primary Suspect (PS), All, Secondary Suspect (SS), Concomitant (C). Most analyses use PS.
- **Top N** slider — controls how many rows appear in bar charts

---

### Overview

The landing view of the full FAERS dataset.

| Section | What it shows |
|---|---|
| KPI row | Total cases, deaths, hospitalisations, life-threatening outcomes, unique drugs, MedDRA PTs |
| Reports Per Quarter | Line chart of total case volume by quarter, 2023 Q3–2025 Q2 |
| Top Drugs | Bar chart of most-reported drugs across all quarters |
| Top Reactions | Bar chart of most-reported MedDRA Preferred Terms |
| Signal Summary | Count of HIGH / MEDIUM / LOW PRR signals in the dataset |
| Quarter-over-Quarter Trends | Top 10 drugs and reactions with the largest case increase between the two most recent quarters |
| Top Elevated Signals | Table of the 10 most extreme HIGH signals (N ≥ 50) |

A loading spinner is shown while the dataset initialises. On a warm server (already been accessed), the page loads in under a second — see [Performance](#performance) below.

---

### Drug Explorer

Search any drug by brand name, generic name, or active ingredient. The input is
normalized through the **RxNorm API** (NLM), which resolves synonyms and returns
related drug names. All FAERS records matching any of those names are aggregated.

**Try:** `zepbound`, `ozempic`, `keytruda`, `dupilumab`, `warfarin`, `naloxone`

A step-by-step status console shows the lookup progress as it runs.

| Section | What it shows |
|---|---|
| RxNorm banner + chips | Canonical name, RxCUI, all matched brand/generic variants |
| **FDA Approval Card** | Application type (NDA / ANDA / BLA), sponsor, first approval date, latest regulatory action, dosage forms, route(s), marketing status — with links to the FDA Portal and Orange Book |
| KPI row | Total cases, deaths (%), hospitalisations, life-threatening, any serious outcome |
| Top Adverse Reactions | Horizontal bar chart of top MedDRA PTs by report count |
| Outcome Distribution | Donut chart: death / hospitalisation / life-threatening / disability / other |
| Quarterly Trend | Case volume over time |
| Demographics | Sex breakdown (donut), age group distribution, reporter type, top countries |
| Clinical Context | Prescribed-for indications (top 12), commonly co-reported drugs (top 12) |
| PRR Signals | Table + forest plot of statistically elevated drug-reaction signals (PRR / chi²) |
| AI Interpretation | Plain-English pharmacovigilance signal summary (3–5 sentences) |
| **Research Context** | Auto-populated sub-tabs for this drug: Clinical Trials (ClinicalTrials.gov) and Literature (PubMed) |

#### FDA Approval Card

Appears automatically below the RxNorm banner whenever the drug is found in the
openFDA Drugs@FDA database. Shows the primary NDA/ANDA/BLA record with links to
the **Orange Book** and the **FDA Drug Portal**. Cached for 24 hours.

*Note: patent expiry dates are not available through the free openFDA API. The Orange
Book link in the card takes you directly to the patent/exclusivity page for that
application number.*

#### AI Interpretation

Requires an LLM API key. The app tries providers in this order:

1. **Anthropic Claude Haiku** — set `ANTHROPIC_API_KEY`
2. **Groq Llama 3.1 8B** (free tier) — set `GROQ_API_KEY`

Groq's free tier supports 14,400 requests per day and requires no credit card.
Sign up at [console.groq.com](https://console.groq.com) to get a key. Results are
cached for 1 hour. If neither key is present, the section is hidden with a soft note.

#### Research Context

Auto-searches for the drug in two live external databases. The search uses the
**active ingredient name** (e.g. "tirzepatide" for Zepbound), not the full RxNorm
clinical drug string, so results are relevant.

- **Clinical Trials** — top 8 intervention trials from ClinicalTrials.gov v2 API.
  Shows NCT ID (linked), title, status (color-coded), phase, sponsor, enrollment.
- **Literature** — top 8 results from PubMed eutils for `{ingredient} adverse events`.
  Shows PMID (linked), title (linked), authors, journal, publication date, DOI.

Both run unauthenticated. Results are cached for 1 hour.

---

### Drug Comparison

Side-by-side adverse event profile of two drugs. Useful for therapeutic alternatives,
biosimilars, or competing drugs in the same class.

**Example pairs:** ozempic vs mounjaro · keytruda vs opdivo · dupilumab vs tralokinumab · apixaban vs rivaroxaban

| Section | What it shows |
|---|---|
| Key Metrics | Cases, deaths, hospitalisations, life-threatening, serious outcomes — Drug A vs Drug B |
| Quarterly Trend Overlay | Both drugs on the same axis with different colors |
| Shared Reactions (rate) | Reactions per 1,000 cases, grouped bars, for reactions appearing in both drug sets |
| Individual Rankings | Top reactions independently ranked for each drug |
| Outcome Donuts | Outcome distribution for each drug |
| HIGH Signal Tables | Top PRR HIGH signals for each drug |

---

### Signal Intelligence

Global pharmacovigilance signal landscape across all drug-reaction pairs.

PRR and chi-squared flag drug-reaction combinations that appear together far more
than chance would predict. **This does not prove causality** — FAERS is a voluntary
reporting system.

| Section | What it shows |
|---|---|
| Filter row | Signal level, min co-occurrences, optional drug/reaction text filter |
| KPI row | Total HIGH / MEDIUM / LOW counts, drugs and reactions covered |
| Signal Landscape Scatter | log₂(PRR) vs. log₁₀(N), color-coded by level. Dotted line = PRR 2 (Evans threshold). |
| Signal Table | Sortable table of top 500 matching signals |
| CSV Download | Full filtered signal export |

**Signal thresholds:**

| Level | PRR | N (co-occurrences) | χ² |
|---|---|---|---|
| HIGH | ≥ 4 | ≥ 5 | ≥ 4 |
| MEDIUM | ≥ 2 | ≥ 3 | ≥ 4 |
| LOW | ≥ 1.5 | ≥ 3 | — |

---

### Reaction Explorer

Start from a symptom and discover which drugs are most associated with it. Uses
semantic search to map plain-English descriptions to MedDRA Preferred Terms.

**Try:** `heart attack`, `throwing up`, `hair loss`, `brain fog`, `memory loss`, `liver damage`

| Section | What it shows |
|---|---|
| MedDRA Matching | Ranked matched Preferred Terms with fuzzy scores. Select which PTs to include. |
| KPI row | Cases reporting that reaction, deaths, serious outcomes |
| Top Associated Drugs | Bar chart of drugs most frequently co-reported with this reaction |
| Outcome Distribution | Donut for cases involving this reaction |
| Quarterly Trend | Case volume for this reaction over time |
| Drug PRR Signals | Drugs with statistically elevated signals for this reaction (MEDIUM+ only) |

---

## Setup

### Prerequisites

- Python 3.10+
- ~2 GB disk space for parquet data
- FAERS parquet data in `data/parquet_recent/` (7 tables: demo, drug, reac, outc, rpsr, ther, indi)

### 1. Install dependencies

```bash
pip install -r dashboard/requirements.txt
```

### 2. Download and convert FAERS data (skip if data already exists)

```bash
bash utils/download_faers.sh          # Download quarterly ZIP files from FDA
python utils/load_faers.py            # Parse ASCII → DataFrames → Parquet
```

### 3. Build the pre-computed signal cache (run once, ~3–5 min)

```bash
python dashboard/precompute.py
```

This creates five parquet files in `dashboard/cache/`:

| File | Contents |
|---|---|
| `prr_table.parquet` | 511K drug-reaction PRR / ROR / chi² signals (~45 MB) |
| `drug_summary.parquet` | Per-drug case counts |
| `reac_summary.parquet` | Per-reaction case counts |
| `quarterly_drug.parquet` | Drug × quarter case counts |
| `quarterly_reac.parquet` | Reaction × quarter case counts |

After this step, all dashboard queries run in under 100 ms.

### 4. (Optional) Enable AI signal interpretation

Set **one** of the following before launching:

```bash
# Option A — Anthropic (paid)
export ANTHROPIC_API_KEY=sk-ant-...

# Option B — Groq (free, 14,400 req/day — get key at console.groq.com)
export GROQ_API_KEY=gsk_...
```

If neither key is set, the AI section is hidden and everything else works normally.

### 5. Run the dashboard

```bash
streamlit run dashboard/app.py
```

**Tip:** For demos or presentations, start the server a minute or two early. The
background warm-up thread loads all data into memory immediately on server start, so
the first browser load is near-instant rather than waiting 15–30 seconds.

---

## Performance

### How caching works

| Mechanism | What it stores | Scope |
|---|---|---|
| `@st.cache_resource` | Large DataFrames (FAERS tables, PRR table) | One shared copy across all sessions and reruns. Never re-serialized. |
| `@st.cache_data` | Derived query results (KPIs, charts, drug lookups) | Per unique set of arguments. Copied via Arrow on access. |

### Background warm-up thread

On server start, `app.py` fires a single background thread (guarded by a module-level
flag in `data_loader.py` so it only runs once) that pre-loads all six parquet files
and the two most expensive overview queries. The thread runs concurrently while
Streamlit renders the first page request.

**Effect:**
- **Cold start (first user, server just started):** data loads during the spinner, ~15–30 s
- **Warm (server started > ~30 s ago):** `load_tables()` returns from memory, spinner
  shows for < 1 s
- **All subsequent users / reruns:** instant

### Pre-computed cache

All PRR signal calculations (~511K drug-reaction pairs) are done offline by
`precompute.py` and stored as Parquet. The dashboard never recomputes signals at
query time — it only filters and sorts an in-memory DataFrame.

---

## File Reference

| File | Purpose |
|---|---|
| `app.py` | Main Streamlit app. Five tabs, global sidebar, all chart builders, CSS (FDA blue/white theme). Background cache warm-up thread. |
| `queries.py` | Streamlit-cached query layer. Wraps analytics functions with stable string cache keys so repeated drug/reaction searches return instantly. |
| `data_loader.py` | Loads all 7 FAERS parquet tables, deduplicates by `caseversion`, normalizes drug names and reaction PTs. Path-configurable via env vars. Provides `warm_all_tables()` and `_warm_started` flag for background pre-loading. |
| `analytics.py` | Pure pandas computation — no Streamlit state. KPIs, aggregations, trend series, demographic breakdowns, concomitant drugs, indications. |
| `signal_detection.py` | Query interface over the pre-computed PRR table. `signals_for_drug`, `signals_for_reaction`, `global_top_signals`, `signal_counts`. |
| `drug_normalizer.py` | RxNorm REST API lookup for canonical names + RxCUI. Fuzzy matching (RapidFuzz) against FAERS drug name vocabulary. |
| `reaction_search.py` | Maps plain-English symptoms to MedDRA Preferred Terms via a 128-entry curated synonym map with fuzzy fallback. |
| `signal_interpreter.py` | LLM-based pharmacovigilance signal summaries. Tries Anthropic Claude Haiku first, then Groq Llama 3.1 as a free fallback. 1-hour cache. Returns empty string if no key is set. |
| `research_connector.py` | Live REST connectors: ClinicalTrials.gov v2 API, PubMed eutils, and openFDA Drugs@FDA. All unauthenticated. 1-hour cache (24-hour for FDA data). |
| `precompute.py` | One-time offline job: PRR/ROR/chi² for top 500 drugs × all 18K MedDRA PTs. Writes 5 parquet files to `cache/`. |
| `.streamlit/config.toml` | Light theme (FDA blue/white), server settings (headless, maxUpload), fast reruns. |

---

## Cloud Deployment Notes

### Environment variables

| Variable | Default | Cloud value |
|---|---|---|
| `FAERS_PARQUET_DIR` | `../data/parquet_recent` | `/dbfs/mnt/faers/parquet_recent` (DBFS) or S3/ADLS path |
| `FAERS_CACHE_DIR` | `dashboard/cache/` | `/dbfs/mnt/faers/cache` |
| `ANTHROPIC_API_KEY` | — | Set in secrets manager |
| `GROQ_API_KEY` | — | Set in secrets manager (free alternative) |

### Databricks deployment

1. Upload FAERS parquet tables to DBFS or an external mount (`/dbfs/mnt/faers/`)
2. Run `precompute.py` as a Databricks Job (can be parallelized with Spark for larger datasets)
3. Deploy as a **Databricks App** (supports Streamlit natively) or on a cluster driver with port forwarding
4. Set `FAERS_PARQUET_DIR` and `FAERS_CACHE_DIR` to point to DBFS paths

For large-scale PRR computation with Spark, the main change is in `precompute.py`:
swap `pd.DataFrame` for `pyspark.sql.DataFrame` in the pivot/crosstab section.
The rest of the app (read-only queries on pre-computed parquet) works with pandas as-is.

### Docker

```bash
# From project root
cd dashboard
docker-compose up --build
```

The compose file mounts `data/parquet_recent/` and `dashboard/cache/` as read-only
volumes so data can be updated without rebuilding the image.

---

## Data Notes

- **Deduplication:** Each `caseid` can appear across multiple quarterly files as amended reports. We keep only the row with the highest `caseversion`, per FDA guidance.
- **Drug roles:** `PS` = Primary Suspect (drug most likely causing the reaction), `SS` = Secondary Suspect, `C` = Concomitant (taken at same time). Most pharmacovigilance analyses filter to PS.
- **MedDRA:** Medical Dictionary for Regulatory Activities — the international standard vocabulary for adverse events. "Preferred Terms" (PTs) are the atomic-level terms used throughout this dashboard.
- **FAERS is spontaneous reporting:** A high PRR means a drug-reaction pair is reported together disproportionately. This warrants attention but does **not** establish causality.
- **openFDA / FDA approval data:** NDA = brand drug approved via New Drug Application, ANDA = generic approved via Abbreviated NDA, BLA = biologic approved via Biologics License Application. Patent expiry is not available through the free API; the Orange Book link in the approval card takes you to the full patent/exclusivity data.

---

## References

- Evans, S.J.W., Waller, P.C., Davis, S. (2001). Use of proportional reporting ratios (PRRs) for signal generation from spontaneous adverse drug reaction reports. *Pharmacoepidemiology and Drug Safety*, 10(6), 483–486.
- FDA FAERS: https://www.fda.gov/drugs/fda-adverse-event-monitoring-system-aems
- NLM RxNorm API: https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html
- ClinicalTrials.gov API v2: https://clinicaltrials.gov/data-api/api
- NCBI PubMed eutils: https://www.ncbi.nlm.nih.gov/books/NBK25499/
- openFDA Drugs@FDA: https://open.fda.gov/apis/drug/drugsfda/
- Groq free LLM API: https://console.groq.com

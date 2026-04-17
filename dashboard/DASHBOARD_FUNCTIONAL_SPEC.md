# FAERS Dashboard Functional Spec (Current Implementation)

This document captures what the dashboard does today so it can be reimplemented without losing functionality.

Primary app entrypoint: `dashboard/app.py`

## 1) Product Purpose

- Interactive FAERS safety exploration app with 3 tabs:
  - `Overview`
  - `Drug Explorer`
  - `Reaction Explorer`
- Data source is FAERS parquet plus precomputed cache parquet files.
- App supports global filters (quarters + drug role + top N), then tab-specific analysis.

## 2) High-Level Runtime Flow

1. Streamlit page/UI setup (`configure_page`, `inject_css`, `render_header`) in `dashboard/app.py`.
2. Background warm-up thread starts once per server process (`dl.warm_all_tables()`).
3. Startup loads:
   - drug name lookup table (`load_drug_name_lookup`)
   - full reaction term list (`get_all_reaction_terms`)
   - quarter list (`get_quarters`)
4. Sidebar renders global filters and dataset stats.
5. Three tabs render using the selected global filters.

## 3) Global Sidebar Behavior

Implemented in: `dashboard/sidebar.py`

### 3.1 Controls

- **Quarter multi-select** as checkbox list in a scroll container.
  - Default: all quarters checked.
  - Encoded as `q_key` via `queries._quarters_key` (`ALL` or sorted pipe-delimited string).
- **Drug role filter** select box:
  - `Primary Suspect (PS)` -> `PS`
  - `All roles` -> `all`
  - `Secondary Suspect (SS)` -> `SS`
  - `Concomitant (C)` -> `C`
- **Top N per chart** slider (5 to 50, default 20, step 5).

### 3.2 Sidebar Dataset Summary Table

- Cases
- Deaths
- Unique drugs
- MedDRA PTs
- Mode (`Recent sample` vs `Full history`)
- Quarter range

Computed from:
- `queries.global_kpis()`
- `data_loader.get_dataset_profile()`

### 3.3 About Block

- Static explanatory text and FDA FAERS dashboard link.

## 4) Tab: Overview

Implemented in: `dashboard/views/overview.py`

### 4.1 KPI Cards

Displays:
- Total Cases
- Deaths Reported (+ death % of cases)
- Hospitalisations
- Life-threatening
- Unique Drug Entities
- Unique Reaction Categories (MedDRA PTs)

Data sources:
- `queries.global_kpis()`

### 4.2 Figure: Top 15 Drugs by Report Volume

- Horizontal bar chart.
- X: `n_cases`, Y: `drug`.
- Source: `data_loader.load_drug_summary()` precomputed table.

### 4.3 Figure: Top 15 Reactions by Report Volume

- Horizontal bar chart.
- X: `n_cases`, Y: `pt`.
- Source: `data_loader.load_reac_summary()` precomputed table.

### 4.4 Section: Quarter-over-Quarter Trends

- Two horizontal bar charts:
  - Top 10 drugs with largest delta between last two quarters.
  - Top 10 reactions with largest delta between last two quarters.
- Includes absolute delta and percent change labels.

Data sources:
- `queries.trending_drugs(top_n=10)` using `quarterly_drug.parquet`
- `queries.trending_reactions(top_n=10)` using `quarterly_reac.parquet`

### 4.5 Figure: Reports Per Quarter

- Line chart of total reports by quarter.
- Source: `queries.global_quarterly_trend()`.

## 5) Tab: Drug Explorer

Implemented in: `dashboard/views/drug.py`

## 5.1 Empty State (no drug query)

- Shows suggested example searches.
- Shows `Most Reported Drugs — Full Dataset` table (top 20 from drug summary cache).

### 5.2 Drug Search + Name Matching Pipeline

User input -> FAERS drug-name set, implemented in `dashboard/drug_normalizer.py`:

1. **RxNorm lookup** (`rxnorm_lookup`)
   - Calls `https://rxnav.nlm.nih.gov/REST/drugs.json?name=...`
   - Picks best RxCUI + canonical name.
   - Calls `.../rxcui/{rxcui}/allRelatedInfo.json` for related names.
   - Returns: `rxcui`, `canonical`, `related[]`.
   - Cached in-memory and on disk.

2. **Direct substring match** in FAERS normalized names (`drugname_norm`, `prod_ai_norm`).

3. **RxNorm-to-FAERS bridge match**
   - Tokenized substring matching between RxNorm canonical/related names and FAERS name universe.

4. **Fuzzy fallback** (RapidFuzz `token_set_ratio`)
   - Uses threshold and max result limits.

5. **LLM fallback** (`llm_normalize`)
   - If still unmatched after fuzzy.

6. **Canon expansion**
   - For matched rows, include corresponding `canon` values so brand and ingredient map together.

Result is final list of matched FAERS drug strings (sorted).

### 5.3 Parallel Data Fetch After Matching

In `views/drug.py`, via `ThreadPoolExecutor`, it concurrently fetches:

- Drug class: `research_connector.get_drug_class(rxcui)`
- FDA approval info (brand canonical + optional ingredient fallback)
- FDA label info (brand canonical + optional ingredient fallback)
- Main analytic bundle: `queries.drug_query_bundle(...)`

### 5.4 Drug Header + Meta

- Displays canonical drug name.
- Displays RxCUI if present.
- Displays primary class tag (ATC/VA first available).
- Displays chips for related RxNorm names.
- Displays count of matched FAERS strings and active role filter.

### 5.5 FDA Regulatory Card (if data present)

Shows fields from openFDA/drugsfda:
- Application type
- Application number
- Sponsor
- First approval date
- Latest action date
- Dosage forms
- Routes
- Marketing status
- Links to FDA portal and Orange Book

### 5.6 FDA Boxed Warning Banner (if present)

- Shows truncated boxed warning text from openFDA label payload.

### 5.7 Drug KPI Row

Displays:
- Total Cases
- Deaths (+ death %)
- Hospitalisations
- Life-threatening
- Any Serious Outcome (+ serious %)

From `bundle["kpi"]` returned by `queries.drug_query_bundle`.

### 5.8 Table: Recent Drug Records

Shows up to 100 records (default call) with columns such as:
- Role
- Drug Name
- Active Ingredient
- Route
- Dose fields

Role codes mapped to labels (PS/SS/C/I).

### 5.9 Figure: Top Adverse Reactions (MedDRA PTs)

- Horizontal bar chart.
- X: reaction count, Y: PT.
- From `bundle["top_reactions"]`.

### 5.10 Figure: Outcome Distribution

- Donut chart.
- From `bundle["outcomes"]`.

### 5.11 Figure: Quarterly Report Volume

- Line chart from `bundle["trend"]`.
- Optional vertical annotation for FDA approval quarter when available.

### 5.12 Demographics & Geography

4-column block:
- Sex donut
- Age-group vertical bar
- Reporter-type vertical bar
- Top reporter countries table

From `bundle["demographics"]` and `bundle["countries"]`.

### 5.13 Clinical Context

Two charts:
- Prescribed-for indications (top)
- Commonly co-reported drugs (top)

From `bundle["indications"]` and `bundle["concomitants"]`.

### 5.14 “At A Glance” Summary

Auto-generated short bullets derived from top reaction, trend delta, and top indication.

### 5.15 Optional External Context (expander, opt-in)

Toggle: `Load live research and FDA enforcement context`

Tabs:
- Clinical Trials (ClinicalTrials.gov)
- Literature (PubMed)
- Recalls & Enforcement (openFDA enforcement)

### 5.16 Matched Drug Name Strings (expander)

- Table listing all matched FAERS drug strings used in query.

### 5.17 Dormant/Commented Feature

- PRR signal display section exists but is commented out in `views/drug.py`.
- Would show table + forest plot if enabled and signal table available.

## 6) Tab: Reaction Explorer

Implemented in: `dashboard/views/reaction.py`

### 6.1 Empty State

- Shows suggested plain-language examples.
- Shows `Most Reported Adverse Reactions` table (top 20 from reaction summary cache).

### 6.2 Symptom/Reaction Matching Pipeline

Implemented in: `dashboard/reaction_search.py`

Input query -> list of MedDRA PT matches (with score):

1. **Lay synonym dictionary match** (`LAY_SYNONYMS`) score 100.
   - Maps plain terms (e.g., "heart attack", "throwing up") to MedDRA PTs.
2. **Substring PT vocabulary match** with tiered scores:
   - exact = 98
   - PT contains query = 95
   - query contains PT = 90
3. **Fuzzy fallback** using RapidFuzz `WRatio`
   - high cutoff (`>=87`) to reduce single-word false positives.
4. Sorted by score descending; truncated to max results.

### 6.3 PT Selection UI

- Multiselect with default top 3 matched PTs.
- Side table with top scored PT matches.

### 6.4 Reaction KPI Row

Displays:
- Cases reporting reaction
- Deaths in those cases (+ death %)
- Any serious outcome
- Number of selected MedDRA terms

From `queries.reaction_kpis`.

### 6.5 “At A Glance” Summary

- Top associated drug statement.
- Recent volume change statement.

### 6.6 Figure: Top Associated Drugs

- Horizontal bar chart.
- Uses active role filter.
- From `queries.reaction_top_drugs`.

### 6.7 Figure: Outcome Distribution

- Donut chart from `queries.reaction_outcomes`.

### 6.8 Figure: Quarterly Report Volume

- Line chart from `queries.reaction_trend`.

## 7) Query Layer (Core Computation)

Implemented in: `dashboard/queries.py`

### 7.1 Key Active Query Bundles

- `drug_query_bundle(...)` (main Drug Explorer engine)
  - Resolves case IDs from lookup indexes
  - Subsets indexed tables by primaryid
  - Computes KPIs, trend, reactions, outcomes, demographics, countries, indications, concomitants, recent records
- `reaction_kpis`, `reaction_top_drugs`, `reaction_outcomes`, `reaction_trend`
- `global_kpis`, `global_quarterly_trend`, `trending_drugs`, `trending_reactions`, etc.

### 7.2 Lookup Strategy

- Uses precomputed lookup tables for drug/reaction/quarter -> primaryid mappings.
- For per-case subsetting, uses primaryid-indexed DataFrames.

### 7.3 Caching

- Heavy resources: `@st.cache_resource`
- Query outputs: `@st.cache_data`

## 8) Data Loading and Cache Tables

Implemented in: `dashboard/data_loader.py`

### 8.1 Raw FAERS Load Path

- `load_tables()` reads full parquet tables, normalizes columns, and applies defensive dedup/filter behavior.
- This is expensive and intended as fallback.

### 8.2 Precomputed Runtime Tables

Current cache loaders include:
- `demo_slim.parquet`
- `fact_drug_quarter.parquet`
- `fact_reac_quarter.parquet`
- `drug_name_lookup.parquet`
- `drug_records_slim.parquet`
- `reac_slim.parquet`
- `outc_slim.parquet`
- `indi_slim.parquet`
- `drug_summary.parquet`
- `reac_summary.parquet`
- `quarterly_drug.parquet`
- `quarterly_reac.parquet`
- `prr_table.parquet`
- `global_kpis.parquet`
- `lookup_quarter_cases.parquet`
- `lookup_drug_cases.parquet`
- `lookup_drug_role_cases.parquet`
- `lookup_reaction_cases.parquet`

### 8.3 Warm-Up

- `warm_all_tables()` loads major cache tables and lookup tables in background thread at startup.

## 9) Precompute Pipeline

Implemented in: `dashboard/precompute.py`

Builds and writes cache artifacts:

- Drug summary (`drug_summary.parquet`)
- Reaction summary (`reac_summary.parquet`)
- Quarterly drug trends (`quarterly_drug.parquet`)
- Quarterly reaction trends (`quarterly_reac.parquet`)
- PRR table (`prr_table.parquet`)
- App fact/slice tables (`fact_*`, `demo_slim`, `drug_name_lookup`, `drug_records_slim`, `reac_slim`, `outc_slim`, `indi_slim`)
- Lookup tables (`lookup_*.parquet`)
- Global KPI cache (`global_kpis.parquet`)

## 10) External Integrations (Live APIs)

Implemented in: `dashboard/research_connector.py`

- ClinicalTrials.gov (`search_clinical_trials`)
- PubMed eutils (`search_pubmed`)
- openFDA Drugs@FDA (`get_fda_approval_info`)
- NLM RxClass (`get_drug_class`)
- openFDA Label (`get_drug_label`)
- openFDA Enforcement (`get_drug_enforcement`)

These are cached in-memory and on disk (TTL varies by endpoint).

## 11) What Is Persisted vs Computed On Demand

Persisted/precomputed:
- Summary/trend/fact/lookup/kpi tables (parquet).

Computed on demand:
- Final filtered aggregates per user query (`drug_query_bundle`, reaction queries).
- Optional external context calls when expander toggle enabled.
- Name matching and reaction-term mapping from input text.

## 12) Current Functional Surface Checklist

### Global
- [x] Quarter filter (checkbox list)
- [x] Drug role filter
- [x] Top-N slider
- [x] Dataset summary block

### Overview Tab
- [x] Global KPI cards
- [x] Top drugs chart
- [x] Top reactions chart
- [x] QoQ trending drugs chart
- [x] QoQ trending reactions chart
- [x] Reports-per-quarter chart

### Drug Explorer Tab
- [x] Drug search box + examples
- [x] RxNorm + FAERS name matching pipeline
- [x] Parallel loading of analytics + external metadata
- [x] Header with canonical name / RxCUI / class / related chips
- [x] FDA approval card
- [x] Boxed warning banner
- [x] KPI cards
- [x] Recent records table
- [x] Top reactions chart
- [x] Outcome donut
- [x] Quarterly trend line (+ approval marker if available)
- [x] Demographics block (sex/age/reporter/countries)
- [x] Clinical context block (indications + concomitants)
- [x] At-a-glance summary
- [x] Optional external context tabset (trials/pubmed/enforcement)
- [x] Matched-name expander table
- [x] PRR section present but currently commented out

### Reaction Explorer Tab
- [x] Reaction search box + examples
- [x] Plain-language -> MedDRA matching pipeline
- [x] PT multiselect + score table
- [x] KPI cards
- [x] Top associated drugs chart
- [x] Outcome donut
- [x] Quarterly trend line
- [x] At-a-glance summary

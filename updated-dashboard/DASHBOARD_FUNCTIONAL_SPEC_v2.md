# FAERS Dashboard Functional Spec v2

This version integrates the persona-specific sub-tabs (Provider View, Manufacturer View) into the Drug Explorer, adds a new top-level Manufacturer Lookup tab, and adds implementation guidance for performance on a local machine and on Databricks/Spark.

Primary app entrypoint: `dashboard/app.py`

## 1) Product Purpose

Interactive FAERS safety exploration app. Tabs:

1. **Overview** (global KPIs + trends)
2. **Drug Explorer** (search a drug, drill into adverse events) with three sub-tabs:
   - Default / Full View
   - Provider View (clinical lens)
   - Manufacturer View (per-drug manufacturer lens)
3. **Manufacturer Lookup** (search a manufacturer, see their portfolio)
4. **Reaction Explorer** (search a symptom, see associated drugs)

Data source: FAERS quarterly parquet plus a set of precomputed cache parquet files. Global filters (quarters, drug role, Top N) apply to every tab.

## 2) High-Level Runtime Flow

1. Streamlit page/UI setup (`configure_page`, `inject_css`, `render_header`) in `dashboard/app.py`.
2. Background warm-up thread starts once per server process (`dl.warm_all_tables()`).
3. Startup loads:
   - drug name lookup table (`load_drug_name_lookup`)
   - full reaction term list (`get_all_reaction_terms`)
   - quarter list (`get_quarters`)
   - manufacturer name lookup (`load_manufacturer_lookup`) **[new]**
4. Sidebar renders global filters and dataset stats.
5. Four top-level tabs render using the selected global filters.

## 3) Global Sidebar Behavior

Unchanged from v1. Implemented in `dashboard/sidebar.py`.

### 3.1 Controls

- Quarter multi-select (checkbox list, default all).
- Drug role filter: `PS` / `all` / `SS` / `C`.
- Top N per chart slider (5-50, default 20).

### 3.2 Dataset Summary

Cases, Deaths, Unique drugs, MedDRA PTs, Mode (sample vs full), Quarter range. From `queries.global_kpis()` and `data_loader.get_dataset_profile()`.

### 3.3 About Block

Static explanatory text and FDA FAERS dashboard link.

## 4) Tab: Overview

Unchanged from v1. Implemented in `dashboard/views/overview.py`.

### 4.1 KPI Cards
Total Cases, Deaths (+death %), Hospitalisations, Life-threatening, Unique Drug Entities, Unique MedDRA PTs. From `queries.global_kpis()`.

### 4.2 Top 15 Drugs by Report Volume
Horizontal bar. Source: `load_drug_summary()`.

### 4.3 Top 15 Reactions by Report Volume
Horizontal bar. Source: `load_reac_summary()`.

### 4.4 Quarter-over-Quarter Trends
Two horizontal bars: top 10 drugs and reactions with largest delta between last two quarters. From `queries.trending_drugs(top_n=10)` and `queries.trending_reactions(top_n=10)`.

### 4.5 Reports Per Quarter
Line chart. From `queries.global_quarterly_trend()`.

## 5) Tab: Drug Explorer

Implemented in: `dashboard/views/drug.py`

The drug search box and name matching pipeline (section 5.1-5.2 below) are shared across all three sub-tabs. After matching resolves to a set of FAERS drug strings, the user picks one of three sub-tabs and the view renders.

### 5.1 Empty State (no drug query)

- Suggested example searches.
- "Most Reported Drugs - Full Dataset" table (top 20 from drug summary cache).

### 5.2 Drug Search + Name Matching Pipeline

User input -> FAERS drug-name set, implemented in `dashboard/drug_normalizer.py`:

1. **RxNorm lookup** (`rxnorm_lookup`)
   - Calls `https://rxnav.nlm.nih.gov/REST/drugs.json?name=...`
   - Picks best RxCUI + canonical name, fetches related names.
   - Returns: `rxcui`, `canonical`, `related[]`. Cached in-memory and on disk.
2. **Direct substring match** in FAERS normalized names (`drugname_norm`, `prod_ai_norm`).
3. **RxNorm-to-FAERS bridge match** (tokenized substring matching).
4. **Fuzzy fallback** (RapidFuzz `token_set_ratio`).
5. **LLM fallback** (`llm_normalize`) if still unmatched.
6. **Canon expansion** for matched rows so brand and ingredient map together.

Result: final list of matched FAERS drug strings (sorted).

### 5.3 Parallel Data Fetch After Matching

Via `ThreadPoolExecutor`, concurrently fetches:

- Drug class: `research_connector.get_drug_class(rxcui)`
- FDA approval info (brand canonical + optional ingredient fallback)
- FDA label info
- Main analytic bundle: `queries.drug_query_bundle(...)`
- **[new]** Provider bundle: `queries.drug_provider_bundle(...)`
- **[new]** Manufacturer bundle: `queries.drug_manufacturer_bundle(...)`

All three bundles share the same resolved primaryid set, so matching happens once.

### 5.4 Drug Header + Meta (shown above all sub-tabs)

- Canonical drug name, RxCUI (if present), primary class tag (ATC/VA).
- Chips for related RxNorm names.
- Count of matched FAERS strings and active role filter.

### 5.5 FDA Regulatory Card (shown in Default View only)

Fields from openFDA/drugsfda: application type/number, sponsor, first approval date, latest action date, dosage forms, routes, marketing status. Links to FDA portal and Orange Book.

### 5.6 FDA Boxed Warning Banner (shown in Default View only)

Truncated boxed warning text from openFDA label payload.

### Sub-tab: 5.A Default / Full View

This is the existing Drug Explorer layout.

#### 5.A.1 Drug KPI Row
Total Cases, Deaths (+death %), Hospitalisations, Life-threatening, Any Serious Outcome (+serious %). From `bundle["kpi"]`.

#### 5.A.2 Recent Drug Records Table
Up to 100 records with Role, Drug Name, Active Ingredient, Route, Dose fields. Role codes mapped to labels (PS/SS/C/I).

#### 5.A.3 Top Adverse Reactions (MedDRA PTs)
Horizontal bar chart. From `bundle["top_reactions"]`.

#### 5.A.4 Outcome Distribution
Donut chart. From `bundle["outcomes"]`.

#### 5.A.5 Quarterly Report Volume
Line chart from `bundle["trend"]`. Optional vertical annotation for FDA approval quarter.

#### 5.A.6 Demographics & Geography
4-column block: Sex donut, Age-group bar, Reporter-type bar, Top reporter countries table. From `bundle["demographics"]` and `bundle["countries"]`.

#### 5.A.7 Clinical Context
Two charts: Prescribed-for indications (top) and Commonly co-reported drugs (top). From `bundle["indications"]` and `bundle["concomitants"]`.

#### 5.A.8 "At A Glance" Summary
Auto-generated bullets from top reaction, trend delta, and top indication.

#### 5.A.9 Optional External Context (expander, opt-in)
Tabs: Clinical Trials (ClinicalTrials.gov), Literature (PubMed), Recalls & Enforcement (openFDA enforcement).

#### 5.A.10 Matched Drug Name Strings (expander)
Table listing all matched FAERS drug strings used in query.

#### 5.A.11 Dormant: PRR Signal Section
Currently commented out. Would show table + forest plot if enabled.

### Sub-tab: 5.B Provider View [new]

Clinical lens. Scoped to the matched primaryid set. Implemented in `dashboard/views/drug_provider.py`, backed by `queries.drug_provider_bundle(primaryids)`.

#### 5.B.1 Active Ingredient List
Ordered list of distinct `prod_ai` values across matched records, with counts. Helps the provider confirm the brand-to-ingredient mapping.

#### 5.B.2 Clinical Counts Row (six bar charts, 2x3 grid)
Top N per chart controlled by global slider.

- **Role code**: count by `role_cod` (PS, SS, C, I) with human labels.
- **Route**: count by `route` (oral, intravenous, topical...).
- **Dose**: count by normalized `(dose_amt, dose_unit)` bucket. Dose_vbm free text is **not** used; rows with missing amount/unit grouped as "Not reported".
- **Dose form**: count by `dose_form`.
- **Dose frequency**: count by `dose_freq`.
- **Reactions**: count by `pt` (same as 5.A.3 but in this tab for parity).

#### 5.B.3 Outcomes
Bar chart (not donut) of `outc_cod` with human labels (DE=Death, LT=Life-threatening, HO=Hospitalization, DS=Disability, CA=Congenital anomaly, RI=Required intervention, OT=Other).

#### 5.B.4 Indications
Top N bar of `indi_pt`, mirroring clinical context from Default view.

#### 5.B.5 Case Table (scrolling, paginated)
100 rows per page. Columns:
- `lit_ref` (literature reference; empty string if none)
- role, route, dose (amt+unit), dose_form, dose_freq
- top reaction for the case
- outcome codes (comma-joined)
- top indication

Filter toggle: **"Only cases with literature reference"**. Most FAERS reports lack lit_ref (roughly 1-5% of reports); toggle lets providers narrow to academically-sourced cases.

### Sub-tab: 5.C Manufacturer View [new]

Per-drug manufacturer lens. Scoped to the matched primaryid set. Implemented in `dashboard/views/drug_manufacturer.py`, backed by `queries.drug_manufacturer_bundle(primaryids)`.

#### 5.C.1 Active Ingredient List
Same as 5.B.1 (distinct `prod_ai` with counts).

#### 5.C.2 Manufacturer Counts (bar chart)
Top N by `mfr_sndr` (demo table), with canonical manufacturer name (see Section 9.4 normalization).

#### 5.C.3 Country Counts (bar chart)
Top N by `occr_country`.

#### 5.C.4 Outcome Counts (bar chart)
Top N by `outc_cod` with human labels.

#### 5.C.5 Dose Form Counts (bar chart)
Top N by `dose_form`.

#### 5.C.6 Case Table (scrolling, paginated)
Columns: `event_dt`, manufacturer, country, active ingredient, dose form, outcomes (joined). 100 rows per page, sortable by event_dt descending.

#### 5.C.7 Reports Per Quarter (line chart)
Total reports per quarter for the matched drug, overall. Optionally split by top-3 manufacturers (legend).

## 6) Tab: Manufacturer Lookup [new]

Implemented in: `dashboard/views/manufacturer.py`. Peer to Drug Explorer. The user enters a manufacturer name and sees their portfolio across FAERS.

### 6.1 Empty State
- Suggested examples (e.g., "Pfizer", "Moderna", "Johnson & Johnson").
- "Most Reported Manufacturers" table (top 20 from precomputed `manufacturer_summary.parquet`).

### 6.2 Manufacturer Name Matching Pipeline
Implemented in: `dashboard/manufacturer_normalizer.py`.

FAERS manufacturer strings are inconsistent ("Pfizer Inc", "Pfizer, Inc.", "PFIZER INC."). Matching uses only FAERS data (no external authority):

1. **Canonical lookup** in `manufacturer_name_lookup.parquet` (precomputed).
   - Each raw `mfr_sndr` maps to a canonical form produced by: lowercase -> strip punctuation -> trim common suffixes (`inc`, `incorporated`, `corp`, `corporation`, `ltd`, `limited`, `llc`, `plc`, `co`, `ag`, `s.a.`, `gmbh`).
   - Exact match on canonical form.
2. **Substring match** on canonical form.
3. **Fuzzy fallback** (RapidFuzz `token_set_ratio`, threshold 85).

Future work: hierarchical parent-company mapping (e.g., "Genentech" -> "Roche"). Not in initial scope.

Returns a list of matched canonical manufacturer names and the set of raw `mfr_sndr` strings that map to them.

### 6.3 Parallel Fetch
`queries.manufacturer_query_bundle(canonical_names)` returns all sections below in one call.

### 6.4 Header
Canonical manufacturer name(s), count of raw FAERS strings matched, total cases in dataset.

### 6.5 KPI Row
Total Cases, Deaths (+death %), Unique drugs attributed, Countries reporting.

### 6.6 Counts Row (bar charts)
- **Drug name**: top N by `drugname` under this manufacturer.
- **Active ingredient**: top N by `prod_ai`.
- **Outcomes**: top N by `outc_cod`.
- **Indications**: top N by `indi_pt`.
- **Countries**: top N by `occr_country`.

### 6.7 Case Table (scrolling, paginated)
Columns: `event_dt`, drug name, active ingredient, country, outcome codes, top indication. 100 rows per page, sortable by event_dt.

### 6.8 Reports Per Quarter (line chart)
From `fact_manufacturer_quarter.parquet`.

### 6.9 Matched Manufacturer Strings (expander)
Table of raw `mfr_sndr` values that map to the chosen canonical name(s).

## 7) Tab: Reaction Explorer

Unchanged from v1. Implemented in: `dashboard/views/reaction.py`.

### 7.1 Empty State
Suggested plain-language examples. "Most Reported Adverse Reactions" table.

### 7.2 Symptom/Reaction Matching Pipeline
In `dashboard/reaction_search.py`: lay synonym dictionary -> substring PT vocabulary match (tiered) -> RapidFuzz fuzzy fallback. Sorted by score.

### 7.3 PT Selection UI
Multiselect with default top 3. Side table with top scored matches.

### 7.4 Reaction KPI Row
Cases reporting, deaths (+death %), any serious outcome, number of selected terms. From `queries.reaction_kpis`.

### 7.5 "At A Glance" Summary
Top associated drug; recent volume change.

### 7.6 Top Associated Drugs
Horizontal bar. Uses active role filter. From `queries.reaction_top_drugs`.

### 7.7 Outcome Distribution
Donut from `queries.reaction_outcomes`.

### 7.8 Quarterly Report Volume
Line from `queries.reaction_trend`.

## 8) Query Layer

Implemented in: `dashboard/queries.py`.

### 8.1 Active Query Bundles

Existing:
- `drug_query_bundle(...)` for Default View
- `reaction_kpis`, `reaction_top_drugs`, `reaction_outcomes`, `reaction_trend`
- `global_kpis`, `global_quarterly_trend`, `trending_drugs`, `trending_reactions`

New:
- `drug_provider_bundle(primaryids, top_n, role_filter, quarters)` returning `{ingredients, role_counts, route_counts, dose_counts, dose_form_counts, dose_freq_counts, reactions, outcomes, indications, cases}`.
- `drug_manufacturer_bundle(primaryids, top_n, role_filter, quarters)` returning `{ingredients, manufacturer_counts, country_counts, outcome_counts, dose_form_counts, cases, quarterly_trend}`.
- `manufacturer_query_bundle(canonical_names, top_n, role_filter, quarters)` returning `{kpi, drug_counts, ingredient_counts, outcome_counts, indication_counts, country_counts, cases, quarterly_trend}`.

All three new bundles share the single-pass pattern used by `drug_query_bundle`: resolve primaryids via lookup tables once, then derive every panel from that indexed subset.

### 8.2 Lookup Strategy

Existing: precomputed lookup tables for drug/reaction/quarter -> primaryid.

New: `lookup_manufacturer_cases.parquet` maps canonical manufacturer name -> list of primaryids.

### 8.3 Caching

- `@st.cache_resource` for heavy resources (tables loaded once per server process).
- `@st.cache_data` for query outputs (per-input memoization).

## 9) Data Loading and Cache Tables

Implemented in: `dashboard/data_loader.py`.

### 9.1 Raw FAERS Load Path
`load_tables()` reads full parquet, normalizes columns, defensive dedup. Expensive; fallback only.

### 9.2 Precomputed Runtime Tables (existing)
`demo_slim`, `fact_drug_quarter`, `fact_reac_quarter`, `drug_name_lookup`, `drug_records_slim`, `reac_slim`, `outc_slim`, `indi_slim`, `drug_summary`, `reac_summary`, `quarterly_drug`, `quarterly_reac`, `prr_table`, `global_kpis`, `lookup_quarter_cases`, `lookup_drug_cases`, `lookup_drug_role_cases`, `lookup_reaction_cases`.

### 9.3 Precomputed Runtime Tables [new]

- `manufacturer_name_lookup.parquet` — raw `mfr_sndr` -> canonical name mapping with counts.
- `manufacturer_summary.parquet` — top manufacturers by case volume (analog of `drug_summary`).
- `fact_manufacturer_quarter.parquet` — (canonical_mfr, year_q) -> n_cases.
- `lookup_manufacturer_cases.parquet` — canonical_mfr -> primaryid list.
- `dose_bucket_slim.parquet` — case-level table with `(primaryid, drug_seq, dose_amt_bucket, dose_unit_norm)`. Bucketing rules documented in `precompute.py`.

### 9.4 Manufacturer Canonicalization Rules

Implemented in `dashboard/manufacturer_normalizer.py` and applied once at precompute time:

1. Lowercase.
2. Strip punctuation except spaces.
3. Collapse whitespace.
4. Strip trailing corporate suffix tokens (iteratively): `inc`, `incorporated`, `corp`, `corporation`, `company`, `co`, `ltd`, `limited`, `llc`, `plc`, `ag`, `gmbh`, `sa`, `nv`, `bv`, `oyj`, `kk`.
5. Trim.

Result written to `canonical_mfr` column alongside original `mfr_sndr`. Downstream queries join on `canonical_mfr`.

### 9.5 Warm-Up
`warm_all_tables()` loads major cache tables and lookup tables in background thread at startup. Adds manufacturer lookups.

## 10) Precompute Pipeline

Implemented in: `dashboard/precompute.py`. Idempotent, runs offline. On local dev, a single `python -m dashboard.precompute` rebuilds everything. Target runtime on 13GB FAERS: under 20 minutes on an SSD, 16GB RAM machine.

### 10.1 Build Order

1. Read raw quarterly parquet partitioned by `(year, quarter)`.
2. Normalize: lowercase drug names, reaction PTs, manufacturer names. Apply canonicalization rules from 9.4.
3. Build `demo_slim`, `drug_records_slim`, `reac_slim`, `outc_slim`, `indi_slim` (column-pruned, primaryid-indexed).
4. Build lookup tables (drug, reaction, manufacturer, quarter -> primaryid).
5. Build summary tables (drug, reaction, manufacturer).
6. Build quarterly fact tables (drug, reaction, manufacturer).
7. Build `global_kpis`.
8. Build `prr_table`.
9. Build `dose_bucket_slim`.

Each step writes to parquet with Snappy compression, partitioned where appropriate (see 12.2).

## 11) External Integrations

Unchanged. Implemented in: `dashboard/research_connector.py`.

- ClinicalTrials.gov (`search_clinical_trials`)
- PubMed eutils (`search_pubmed`)
- openFDA Drugs@FDA (`get_fda_approval_info`)
- NLM RxClass (`get_drug_class`)
- openFDA Label (`get_drug_label`)
- openFDA Enforcement (`get_drug_enforcement`)

Cached in-memory and on disk; TTL varies by endpoint.

## 12) Performance & Scaling Strategy

Design goal: **every user interaction hits only precomputed tables or narrow indexed scans**. The 13GB raw FAERS set is touched only by the offline precompute pipeline.

### 12.1 Core Rules

1. **No raw-table scans at query time.** All tabs read from slim/fact/lookup tables (megabytes, not gigabytes).
2. **Resolve primaryids via lookup tables first**, then subset pre-indexed slim tables. This is the single-pass pattern already used by `drug_query_bundle`.
3. **Column pruning.** Every parquet read names the columns it needs (via `pl.scan_parquet(...).select(...)` or `pyarrow.parquet.read_table(columns=...)`). Avoid `SELECT *`.
4. **Predicate pushdown.** Filters on `year_q` and `canonical_drug` should execute at the parquet scan level, not after load. Polars lazy frames handle this automatically.
5. **Precompute all counts.** Any "top N by X" the UI shows should be a precomputed table. Runtime work is limited to slicing that table by the active filters.
6. **Paginate tables.** Never render more than 100 rows at a time. Use offset/limit parameters in the query bundle.
7. **String normalization once, at precompute.** Lowercase, strip, canonicalize manufacturer/drug/reaction strings in the pipeline, never in the hot path.

### 12.2 Parquet Layout

Partition strategy:

- `drug_records_slim.parquet` partitioned by `(year, quarter)`. Enables the sidebar quarter filter to skip irrelevant files entirely.
- `fact_*_quarter.parquet` single file (small; partitioning adds no value under ~100MB).
- Lookup tables single file, sorted by key.

Compression: Snappy (default; balances size and decompression speed). Page size: default 1MB. Row group size: 128MB (good for columnar scans).

### 12.3 Engine Choice (Local)

**Polars** for precompute and query-time transforms. Reasons:
- Lazy API supports predicate pushdown and projection pushdown natively.
- Faster than pandas on single-node multi-core machines.
- API maps cleanly to PySpark DataFrames, easing the Databricks port.

**DuckDB** as optional alternative for ad-hoc SQL queries during development. Not required in the hot path.

Avoid pandas for data loading; it materializes full frames and doesn't prune columns.

### 12.4 Streamlit Caching

- `@st.cache_resource` for loaded parquet tables. One copy per server process, shared across sessions.
- `@st.cache_data` for query bundle outputs. Keyed on (drug_canonical, quarters_key, role_filter, top_n). Bundles are small (KB-MB) so the cache footprint stays bounded.
- Background warm-up thread loads all cache tables at startup so the first user request doesn't pay the cold-start cost.
- External API responses (RxNorm, FDA) cached on disk with TTL.

### 12.5 Matching Pipeline Latency

- RxNorm and FDA calls run concurrently via `ThreadPoolExecutor`. These are the slowest link (network-bound, 200-800ms typical). Disk cache makes repeat searches instant.
- Fuzzy matching runs on a pre-loaded set of normalized FAERS drug strings (~200K entries). RapidFuzz `extract` completes in under 50ms.
- LLM fallback only fires when fuzzy matching returns nothing. Rare in practice.

### 12.6 Expected Latency Budget

| Action | Target | Mechanism |
|---|---|---|
| Switch tabs | <100ms | Streamlit re-render only; data already cached |
| Change global filter | <500ms | Filter applied to cached slim tables |
| Drug search (cache hit) | <200ms | RxNorm/FDA from disk cache |
| Drug search (cold) | 1-3s | RxNorm + FDA network calls in parallel |
| Provider/Manufacturer sub-tab switch | <100ms | Bundles fetched in parallel at drug-load time |
| Manufacturer Lookup search | <500ms | Canonical lookup + slim-table filter |
| Scrolling table page turn | <100ms | Paginated slice |

### 12.7 Memory Budget

Target: peak 4GB for the Streamlit process on a 16GB dev machine.

- Slim tables (all loaded): ~1.5GB
- Lookup tables (all loaded): ~300MB
- Summary + fact tables: ~200MB
- Query cache headroom: ~1GB
- Streamlit + Python overhead: ~500MB

If memory becomes tight, move `drug_records_slim` to lazy-scan-only (don't hold in memory, rely on parquet predicate pushdown). Costs ~50ms per query but frees ~800MB.

## 13) Databricks / Spark Migration Path

The local design is deliberately Spark-portable. Migration is mostly a storage and engine swap, not an architectural rewrite.

### 13.1 Storage

Local: plain parquet files on disk.
Databricks: same files uploaded to Unity Catalog as **Delta tables** (parquet + transaction log). Delta adds:
- ACID guarantees for the precompute pipeline (safe concurrent writes).
- Time travel (roll back a bad precompute run).
- Z-ordering on `(canonical_drug, canonical_mfr, primaryid)` for fast point lookups.
- Auto-compaction so small files from quarterly updates don't hurt scan performance.

### 13.2 Engine

Local: Polars lazy frames.
Databricks: PySpark DataFrames. Swap `pl.scan_parquet` -> `spark.read.format("delta").load(...)`. The transform chain (select, filter, groupBy, agg, join) is near-identical in API surface; most code ports line-for-line.

### 13.3 Precompute Pipeline

Local: `python -m dashboard.precompute` runs Polars transforms.
Databricks: same logic as a Databricks Job with PySpark. Runs on a small cluster; FAERS is small by Spark standards, 2-4 workers is plenty. Delta Live Tables is an option if declarative pipelines are preferred.

### 13.4 Query Layer

Local: query functions call Polars on in-memory/lazy frames.
Databricks: two options.
- **Option A**: Same code runs against PySpark via `pyspark.pandas` or DataFrame API. Simple; adds Spark JVM startup latency (~2-5s per cold call).
- **Option B** (recommended for dashboard): precomputed tables stay small enough to serve from a **Databricks SQL Warehouse** or even a local cache fetched at app startup. Dashboard queries hit the warehouse via the SQL connector. Sub-second response times.

Keep the `queries.py` module as an abstraction layer; swap the backend under it without changing view code.

### 13.5 Deployment

Local: `streamlit run dashboard/app.py`.
Databricks: **Databricks Apps** (hosted Streamlit). Handles auth, scaling, and warehouse connections. No code changes beyond backend swap and credential config.

### 13.6 External APIs

Unchanged. RxNorm/FDA/PubMed calls work identically from local and Databricks environments. Disk cache becomes a Unity Catalog volume on Databricks.

### 13.7 Checklist for Porting

- [ ] Move parquet files to Unity Catalog volumes, convert to Delta.
- [ ] Port `precompute.py` from Polars to PySpark (mechanical translation).
- [ ] Add Z-ordering on hot columns.
- [ ] Swap `data_loader.py` backend from parquet reader to SQL Warehouse client.
- [ ] Configure `queries.py` to hit SQL Warehouse.
- [ ] Deploy app to Databricks Apps with warehouse credentials.
- [ ] Verify latency budgets still hold.

## 14) What Is Persisted vs Computed On Demand

Persisted (precomputed):
- Summary / trend / fact / lookup / KPI tables (parquet locally, Delta on Databricks).
- Manufacturer canonicalization mapping.
- Dose buckets.

Computed on demand:
- Final filtered aggregates per user query (`drug_query_bundle`, `drug_provider_bundle`, `drug_manufacturer_bundle`, `manufacturer_query_bundle`, reaction queries).
- Optional external context calls when expander toggled.
- Name matching and reaction-term mapping from input text.

## 15) Current Functional Surface Checklist

### Global
- [X] Quarter filter (checkbox list)
- [X] Drug role filter
- [X] Top-N slider
- [X] Dataset summary block

### Overview Tab
- [X] Global KPI cards
- [X] Top drugs chart
- [X] Top reactions chart
- [X] QoQ trending drugs chart
- [X] QoQ trending reactions chart
- [X] Reports-per-quarter chart

### Drug Explorer Tab
- [X] Drug search box + examples
- [X] RxNorm + FAERS name matching pipeline
- [X] Parallel loading of analytics + external metadata
- [X] Header with canonical name / RxCUI / class / related chips
- [ ] **Sub-tab chrome: Default / Provider / Manufacturer**

#### Default Sub-tab (existing)
- [X] FDA approval card
- [X] Boxed warning banner
- [X] KPI cards
- [X] Recent records table
- [X] Top reactions chart
- [X] Outcome donut
- [X] Quarterly trend line
- [X] Demographics block
- [X] Clinical context block
- [X] At-a-glance summary
- [X] Optional external context tabset
- [X] Matched-name expander
- [ ] PRR section (currently commented)

#### Provider Sub-tab [new]
- [ ] Active ingredient list
- [ ] Role code / Route / Dose / Dose form / Dose freq / Reactions counts grid
- [ ] Outcomes bar chart
- [ ] Indications bar chart
- [ ] Case table with lit_ref filter

#### Manufacturer Sub-tab [new]
- [ ] Active ingredient list
- [ ] Manufacturer / Country / Outcomes / Dose form counts
- [ ] Case table
- [ ] Reports-per-quarter line (optional manufacturer split)

### Manufacturer Lookup Tab [new]
- [ ] Manufacturer search box + examples
- [ ] Canonicalization + fuzzy matching pipeline
- [ ] Header + KPI row
- [ ] Drug / Ingredient / Outcomes / Indications / Countries counts
- [ ] Case table
- [ ] Reports-per-quarter line
- [ ] Matched raw-string expander

### Reaction Explorer Tab
- [X] Reaction search box + examples
- [X] Plain-language -> MedDRA matching pipeline
- [X] PT multiselect + score table
- [X] KPI cards
- [X] Top associated drugs chart
- [X] Outcome donut
- [X] Quarterly trend line
- [X] At-a-glance summary

### Performance & Infra [new]
- [ ] `drug_records_slim` partitioned by `(year, quarter)`
- [ ] Polars lazy scans in hot path
- [ ] Manufacturer canonicalization applied at precompute
- [ ] `fact_manufacturer_quarter`, `manufacturer_summary`, `lookup_manufacturer_cases` built
- [ ] `dose_bucket_slim` built
- [ ] Streamlit warm-up thread covers all new tables
- [ ] Latency budget verified (Section 12.6)
- [ ] Databricks port checklist (Section 13.7) tracked separately

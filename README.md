# FAERS Analytics Dashboard

[Live Dashboard](https://faers-dash-7474656618229428.aws.databricksapps.com/)

## Executive Summary

FAERS Analytics Dashboard is an AI-powered big data project that transforms millions of messy FDA adverse event reports into actionable drug safety insights. It addresses the scale, inconsistency, and usability limitations of FAERS data by combining cloud-scale processing, AI-driven normalization, and an interactive dashboard for trend discovery and signal detection.

The project centralizes public quarterly FAERS extracts, processes them with Databricks Spark, standardizes drug and reaction terminology with AI support, and presents findings in a Streamlit dashboard. It is designed for pharma teams, analysts, regulators, and healthcare systems that need faster, clearer, and more accessible safety intelligence.

## Problem Statement

FAERS data is large, messy, and difficult to analyze at scale. The flyer highlights four major challenges: roughly 1 million new reports per year, inconsistent free-text data entry, limited dashboard usability, and clinical terminology that is hard for non-specialists to navigate.

## Solution Overview

The solution combines three layers:

- **Centralized storage** for public quarterly FAERS data.
- **AI-powered modeling** to normalize messy drug names, cluster related adverse event terms, and generate readable signal summaries.
- **Real-time insights** through a Streamlit dashboard with drill-down support for drugs, events, trends, manufacturers, and providers [file:1].

## Technology Stack

| Layer | Tools | Purpose |
|---|---|---|
| Data source | FDA FAERS public quarterly extracts | Source adverse event reports |
| Processing | Databricks, Apache Spark | Deduplication, cleansing, and aggregation at scale |
| Storage | Parquet datasets, cache tables | Efficient downstream analytics and dashboard loading |
| AI / NLP | RxNorm API, semantic clustering, generative summaries | Standardize drug names, cluster reaction terms, and explain signals |
| App layer | Streamlit | Interactive dashboard and exploration UI |
| Deployment | Databricks Apps | Hosted production dashboard |
| Local setup | Python setup script | One-step bootstrap for dependencies, data prep, and launch |

## One-Step Setup

The repository now includes a single setup script that bootstraps and runs the dashboard on macOS or Windows.

### Quick Start

From the repository root:

```bash
python utils/setup_dashboard.py --mode recent --run
```

This command will:

- Install Python dependencies from `requirements.txt`.
- Download any missing FAERS quarterly files.
- Build parquet datasets in `data/parquet_recent` or `data/parquet`.
- Build dashboard cache tables in `dashboard/cache_recent` or `dashboard/cache_full`.
- Launch Streamlit.
- Open the dashboard at `http://localhost:8501`.

## Setup Modes

### Recent dataset
Smaller, dev-friendly dataset for faster iteration.

```bash
python utils/setup_dashboard.py --mode recent --run
```

### Full dataset
Full historical FAERS dataset.

```bash
python utils/setup_dashboard.py --mode full --run
```

## Useful Flags

Skip dependency installation:

```bash
python utils/setup_dashboard.py --mode recent --skip-deps
```

Force re-download of quarterly zip files:

```bash
python utils/setup_dashboard.py --mode recent --force-download
```

Force rebuild of parquet and/or cache:

```bash
python utils/setup_dashboard.py --mode recent --force-parquet --force-cache
```

Setup only, without launching the dashboard:

```bash
python utils/setup_dashboard.py --mode recent
```

## Optional Quarter Range

You can limit processing to a specific quarter window:

```bash
python utils/setup_dashboard.py --mode full --start-quarter 2023Q1 --end-quarter 2025Q4 --run
```

## End-to-End Pipeline

1. **Ingest**
   - Load quarterly FAERS files from FDA public releases.
   - Move raw data into the processing environment.

2. **Clean**
   - Deduplicate records.
   - Handle inconsistent formatting and noisy free-text fields with Spark-based processing.

3. **Standardize**
   - Normalize drug names into standardized identifiers.
   - Standardize adverse event and reaction terminology.
   - Group semantically similar terms together.

4. **Analyze**
   - Identify key drugs, manufacturers, and reactions.
   - Detect quarter-over-quarter movers, trend spikes, and emerging safety signals.

5. **Explain**
   - Generate plain-language summaries for flagged signals.
   - Provide reviewer-facing explanations for why a case or trend was surfaced.

6. **Publish**
   - Materialize cache tables for dashboard performance.
   - Serve the interactive app in Streamlit and Databricks Apps.

## Core Capabilities

- Smart semantic search across related medical terms.
- Risk detection for unexpected drug-event relationships.
- AI-generated signal summaries for non-clinical users.
- Interactive filtering and drill-down across drugs, events, trends, and outcomes.

## Business Value

This project delivers value across multiple user groups:

- **Pharma companies** can monitor competitor safety signals and improve risk management.
- **Analysts and regulators** can identify public health risks faster and reduce manual review.
- **Healthcare systems** can better track adverse event patterns and support decision-making.

## Quantifiable Impact

The flyer highlights several measurable outcomes:

- **16.9M** cases unified.
- **40** earlier signal detection.
- **3x** deeper insight.
- **80** less manual cleaning.
- **98/100** match accuracy for reaction clustering and related-term mapping.


## Repository Structure

```text
.
├── dashboard/
│   ├── app.py
│   └── precompute.py
├── data/
│   ├── parquet_recent/
│   ├── parquet/
│   ├── cache_recent/
│   └── cache_full/
├── utils/
│   └── setup_dashboard.py
├── requirements.txt
└── README.md
```

## Entry Points

- **Setup script:** `utils/setup_dashboard.py`
- **Dashboard app:** `dashboard/app.py`
- **Cache builder:** `dashboard/precompute.py`

## Team

- Austin Ganje
- Hayden Herstrom
- Amogha Yalgi
- Hannah Huang
- Rachel Le

## Acknowledgements

We acknowledge the Carlson School of Management IT department for technical support on this project [file:1].

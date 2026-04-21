# FAERS Dashboard (One-Step Setup)

**Now deployed on Databricks:** https://faers-dash-7474656618229428.aws.databricksapps.com/

This repo now uses a **single setup script** to bootstrap and run the dashboard on macOS or Windows.

## Quick Start

From the repository root:

```bash
python utils/setup_dashboard.py --mode recent --run
```

That one command will, idempotently:

1. Install Python dependencies (`requirements.txt`)
2. Download missing FAERS quarterly files
3. Build parquet datasets (`data/parquet_recent` or `data/parquet`)
4. Build dashboard cache tables (`dashboard/cache_recent` or `dashboard/cache_full`)
5. Launch Streamlit

Open: `http://localhost:8501`

## Modes

- `recent`: smaller dev-friendly dataset (default)
- `full`: full historical dataset

Examples:

```bash
# recent dataset
python utils/setup_dashboard.py --mode recent --run

# full dataset
python utils/setup_dashboard.py --mode full --run
```

## Useful Flags

```bash
# skip dependency installation
python utils/setup_dashboard.py --mode recent --skip-deps

# force re-download quarter zips
python utils/setup_dashboard.py --mode recent --force-download

# force rebuild parquet and/or cache
python utils/setup_dashboard.py --mode recent --force-parquet --force-cache

# setup only (do not launch dashboard)
python utils/setup_dashboard.py --mode recent
```

## Quarter Range (Optional)

You can restrict processing to a quarter window:

```bash
python utils/setup_dashboard.py --mode full --start-quarter 2023Q1 --end-quarter 2025Q4 --run
```

## Notes

- The setup script is idempotent: if data/parquet/cache already exist, it skips rebuilds unless forced.
- Some very recent quarters may not be published yet by FDA; the script skips unavailable quarters and continues.

## Entry Points

- Setup script: `utils/setup_dashboard.py`
- Dashboard app: `dashboard/app.py`
- Cache builder: `dashboard/precompute.py`

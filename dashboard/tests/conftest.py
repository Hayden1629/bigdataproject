"""
conftest.py

Session-scoped fixtures for the FAERS dashboard test suite.

Strategy
--------
* Generate synthetic parquet fixtures once per pytest session (fast: ~0.5 s).
* Set FAERS_PARQUET_DIR / FAERS_CACHE_DIR env vars BEFORE any dashboard module
  is imported, so data_loader picks up the test paths at module-load time.
* Expose normalised DataFrames that mirror data_loader.load_tables() output
  without requiring Streamlit caching context.
* Individual test modules can import analytics / signal_detection functions
  directly and pass these DataFrames in.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import pytest

# ── Paths ──────────────────────────────────────────────────────────────────────
_TESTS_DIR   = Path(__file__).parent
_FIXTURE_DIR = _TESTS_DIR / "fixtures"
_CACHE_DIR   = _FIXTURE_DIR / "cache"
_DASHBOARD   = _TESTS_DIR.parent

# Set env vars BEFORE any dashboard module import so data_loader picks them up.
os.environ["FAERS_PARQUET_DIR"] = str(_FIXTURE_DIR)
os.environ["FAERS_CACHE_DIR"]   = str(_CACHE_DIR)

# Make the dashboard package and tests directory importable.
for _p in (str(_DASHBOARD), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Generate fixtures once (idempotent) ───────────────────────────────────────
from generate_fixtures import generate as _generate  # noqa: E402

_generate()   # no-op if fixtures already present


# ── Raw parquet loaders (session-scoped → loaded once per test run) ───────────

@pytest.fixture(scope="session")
def fixture_dir() -> Path:
    return _FIXTURE_DIR


@pytest.fixture(scope="session")
def cache_dir() -> Path:
    return _CACHE_DIR


@pytest.fixture(scope="session")
def raw_demo() -> pd.DataFrame:
    return pd.read_parquet(_FIXTURE_DIR / "demo.parquet")


@pytest.fixture(scope="session")
def raw_drug() -> pd.DataFrame:
    return pd.read_parquet(_FIXTURE_DIR / "drug.parquet")


@pytest.fixture(scope="session")
def raw_reac() -> pd.DataFrame:
    return pd.read_parquet(_FIXTURE_DIR / "reac.parquet")


@pytest.fixture(scope="session")
def raw_outc() -> pd.DataFrame:
    return pd.read_parquet(_FIXTURE_DIR / "outc.parquet")


@pytest.fixture(scope="session")
def raw_indi() -> pd.DataFrame:
    return pd.read_parquet(_FIXTURE_DIR / "indi.parquet")


@pytest.fixture(scope="session")
def raw_ther() -> pd.DataFrame:
    return pd.read_parquet(_FIXTURE_DIR / "ther.parquet")


@pytest.fixture(scope="session")
def raw_rpsr() -> pd.DataFrame:
    return pd.read_parquet(_FIXTURE_DIR / "rpsr.parquet")


@pytest.fixture(scope="session")
def prr_table() -> pd.DataFrame:
    return pd.read_parquet(_CACHE_DIR / "prr_table.parquet")


@pytest.fixture(scope="session")
def drug_summary() -> pd.DataFrame:
    return pd.read_parquet(_CACHE_DIR / "drug_summary.parquet")


@pytest.fixture(scope="session")
def reac_summary() -> pd.DataFrame:
    return pd.read_parquet(_CACHE_DIR / "reac_summary.parquet")


@pytest.fixture(scope="session")
def quarterly_drug() -> pd.DataFrame:
    return pd.read_parquet(_CACHE_DIR / "quarterly_drug.parquet")


@pytest.fixture(scope="session")
def quarterly_reac() -> pd.DataFrame:
    return pd.read_parquet(_CACHE_DIR / "quarterly_reac.parquet")


# ── Normalised tables — mirrors data_loader.load_tables() output ──────────────

@pytest.fixture(scope="session")
def tables(raw_demo, raw_drug, raw_reac, raw_outc, raw_indi, raw_ther, raw_rpsr) -> dict[str, pd.DataFrame]:
    """
    Builds the same normalised dict that data_loader.load_tables() produces,
    but using pandas directly (no Streamlit cache context required).
    """
    # -- Demo: dedup by caseid, keep highest caseversion ----------------------
    demo = raw_demo.copy()
    demo["caseversion"] = (
        pd.to_numeric(demo["caseversion"], errors="coerce").fillna(0).astype(int)
    )
    demo = demo.sort_values("caseversion").drop_duplicates("caseid", keep="last")

    # Synthetic columns that real FAERS data carries but fixtures omit
    demo["age_grp"]          = "A"           # all adults in our synthetic set
    demo["occp_cod"]         = demo["reporter_type"]   # HP/CS/OT
    demo["reporter_country"] = demo["occr_country"]    # US/CA/GB/DE/FR

    valid_pids = set(demo["primaryid"].unique())

    # -- Drug normalisation ---------------------------------------------------
    drug = raw_drug[raw_drug["primaryid"].isin(valid_pids)].copy()
    drug["drugname_norm"] = drug["drugname"].str.upper().str.strip()
    drug["prod_ai_norm"]  = drug["prod_ai"].str.upper().str.strip()
    drug["canon"]         = drug["prod_ai_norm"].fillna(drug["drugname_norm"])
    # Merge quarter from demo so analytics.quarterly_trend_for_drug live-fallback works
    drug = drug.merge(demo[["primaryid", "quarter"]], on="primaryid", how="left")

    # -- Reaction normalisation -----------------------------------------------
    reac = raw_reac[raw_reac["primaryid"].isin(valid_pids)].copy()
    reac["pt_norm"] = reac["pt"].str.strip().str.title()
    # Synthetic quarter from demo join (real FAERS keeps quarter in demo only)
    reac = reac.merge(demo[["primaryid", "quarter"]], on="primaryid", how="left")

    # -- Outcomes / ancillary -------------------------------------------------
    outc = raw_outc[raw_outc["primaryid"].isin(valid_pids)].copy()
    indi = raw_indi[raw_indi["primaryid"].isin(valid_pids)].copy()
    ther = raw_ther[raw_ther["primaryid"].isin(valid_pids)].copy()
    rpsr = raw_rpsr[raw_rpsr["primaryid"].isin(valid_pids)].copy()

    return {
        "demo": demo,
        "drug": drug,
        "reac": reac,
        "outc": outc,
        "indi": indi,
        "ther": ther,
        "rpsr": rpsr,
    }

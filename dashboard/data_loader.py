"""
data_loader.py

Loads FAERS parquet files with deduplication and type normalisation.

Caching strategy
----------------
* load_tables(), load_prr_table(), load_*_summary() → @st.cache_resource
  These are large, read-only reference DataFrames.  cache_resource creates ONE
  shared copy in memory and reuses it across all sessions and reruns — no
  Arrow serialisation / deserialisation overhead per call.  On a 2 GB dataset
  this is the single biggest speed win vs cache_data.

* Small derived lists (reaction terms, quarters) → @st.cache_data
  Safe to copy because they are tiny.
"""

from __future__ import annotations

import os
import pandas as pd
import streamlit as st

_HERE = os.path.dirname(os.path.abspath(__file__))

# ── Path configuration ────────────────────────────────────────────────────────
# Override with env vars for cloud deployment (Databricks DBFS, S3, ADLS, etc.)
#   FAERS_PARQUET_DIR — path to the 7 FAERS parquet tables (demo, drug, reac, …)
#   FAERS_CACHE_DIR   — path to the pre-computed signal/summary parquet cache
_PARQUET_DIR = os.environ.get(
    "FAERS_PARQUET_DIR",
    os.path.abspath(os.path.join(_HERE, "..", "data", "parquet_recent")),
)
_CACHE_DIR = os.environ.get(
    "FAERS_CACHE_DIR",
    os.path.join(_HERE, "cache"),
)

TABLE_NAMES = ["demo", "drug", "reac", "outc", "rpsr", "ther", "indi"]


@st.cache_resource(show_spinner="Loading FAERS tables…")
def load_tables() -> dict[str, pd.DataFrame]:
    """Load all FAERS tables, deduplicate, and normalise key columns.

    Uses cache_resource so the large DataFrames are shared across all user
    sessions rather than copied per-session (cache_data behaviour).
    """
    tables: dict[str, pd.DataFrame] = {}
    for name in TABLE_NAMES:
        path = os.path.join(_PARQUET_DIR, f"{name}.parquet")
        tables[name] = pd.read_parquet(path)

    # ── Deduplicate demo ───────────────────────────────────────────────────────
    demo = tables["demo"].copy()
    demo["caseversion"] = (
        pd.to_numeric(demo["caseversion"], errors="coerce").fillna(0).astype(int)
    )
    demo = demo.sort_values("caseversion").drop_duplicates("caseid", keep="last")
    tables["demo"] = demo

    # ── Filter all other tables to deduplicated primaryids ────────────────────
    valid_pids = set(demo["primaryid"].unique())
    for name in ["drug", "reac", "outc", "rpsr", "ther", "indi"]:
        tables[name] = tables[name][tables[name]["primaryid"].isin(valid_pids)].copy()

    # ── Normalise drug names ───────────────────────────────────────────────────
    drug = tables["drug"].copy()
    drug["drugname_norm"] = drug["drugname"].str.upper().str.strip()
    drug["prod_ai_norm"]  = drug["prod_ai"].str.upper().str.strip()
    drug["canon"] = drug["prod_ai_norm"].fillna(drug["drugname_norm"])
    tables["drug"] = drug

    # ── Normalise reaction PTs ─────────────────────────────────────────────────
    reac = tables["reac"].copy()
    reac["pt_norm"] = reac["pt"].str.strip().str.title()
    tables["reac"] = reac

    return tables


@st.cache_data(show_spinner=False)
def get_all_reaction_terms() -> list[str]:
    """All unique MedDRA PTs present in the FAERS data, sorted."""
    return sorted(load_tables()["reac"]["pt_norm"].dropna().unique().tolist())


@st.cache_data(show_spinner=False)
def get_all_drug_names() -> list[str]:
    """Unique canonical (prod_ai) drug names, sorted."""
    drug = load_tables()["drug"]
    names = drug["canon"].dropna().unique()
    return sorted(n for n in names if n and len(n) > 1)


@st.cache_data(show_spinner=False)
def get_quarters() -> list[str]:
    return sorted(load_tables()["demo"]["quarter"].dropna().unique().tolist())


@st.cache_data(show_spinner=False)
def get_n_total() -> int:
    return len(load_tables()["demo"])


# ── Pre-computed cache tables ─────────────────────────────────────────────────
# Also cache_resource: these are large parquet files loaded once and shared.

@st.cache_resource(show_spinner="Loading signal table…")
def load_prr_table() -> pd.DataFrame | None:
    path = os.path.join(_CACHE_DIR, "prr_table.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    return None


@st.cache_resource(show_spinner=False)
def load_drug_summary() -> pd.DataFrame | None:
    path = os.path.join(_CACHE_DIR, "drug_summary.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    return None


@st.cache_resource(show_spinner=False)
def load_reac_summary() -> pd.DataFrame | None:
    path = os.path.join(_CACHE_DIR, "reac_summary.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    return None


@st.cache_resource(show_spinner=False)
def load_quarterly_drug() -> pd.DataFrame | None:
    path = os.path.join(_CACHE_DIR, "quarterly_drug.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    return None


@st.cache_resource(show_spinner=False)
def load_quarterly_reac() -> pd.DataFrame | None:
    path = os.path.join(_CACHE_DIR, "quarterly_reac.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    return None


# ── Background cache warm-up ──────────────────────────────────────────────────
# This flag lives in the module namespace, which Python keeps alive across all
# Streamlit reruns (modules stay in sys.modules). So _warm_started = True after
# the first run and the background thread only ever fires once per server start.

_warm_started: bool = False


def warm_all_tables() -> None:
    """Call every cache_resource loader so data is in memory before any user arrives."""
    load_tables()
    load_prr_table()
    load_drug_summary()
    load_reac_summary()
    load_quarterly_drug()
    load_quarterly_reac()

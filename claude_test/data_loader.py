"""
data_loader.py

Loads FAERS parquet files with deduplication and type normalisation.
All heavy loading is wrapped in @st.cache_data so it runs once per session.

Deduplication rule: keep the row with the highest caseversion per caseid.
This ensures each real-world adverse event is counted only once even if it
was re-submitted across multiple quarters.
"""

from __future__ import annotations

import os
import pandas as pd
import streamlit as st

_HERE        = os.path.dirname(os.path.abspath(__file__))
_PARQUET_DIR = os.path.abspath(os.path.join(_HERE, "..", "data", "parquet_recent"))
_CACHE_DIR   = os.path.join(_HERE, "cache")

TABLE_NAMES = ["demo", "drug", "reac", "outc", "rpsr", "ther", "indi"]


@st.cache_data(show_spinner=False)
def load_tables() -> dict[str, pd.DataFrame]:
    """Load all FAERS tables, deduplicate, and normalise key columns."""
    tables = {}
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
    drug = tables["drug"]
    drug["drugname_norm"] = drug["drugname"].str.upper().str.strip()
    drug["prod_ai_norm"]  = drug["prod_ai"].str.upper().str.strip()
    # Canonical name: prefer prod_ai (more standardised)
    drug["canon"] = drug["prod_ai_norm"].fillna(drug["drugname_norm"])
    tables["drug"] = drug

    # ── Normalise reaction PTs ─────────────────────────────────────────────────
    reac = tables["reac"]
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

@st.cache_data(show_spinner=False)
def load_prr_table() -> pd.DataFrame | None:
    path = os.path.join(_CACHE_DIR, "prr_table.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    return None


@st.cache_data(show_spinner=False)
def load_drug_summary() -> pd.DataFrame | None:
    path = os.path.join(_CACHE_DIR, "drug_summary.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    return None


@st.cache_data(show_spinner=False)
def load_reac_summary() -> pd.DataFrame | None:
    path = os.path.join(_CACHE_DIR, "reac_summary.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    return None


@st.cache_data(show_spinner=False)
def load_quarterly_drug() -> pd.DataFrame | None:
    path = os.path.join(_CACHE_DIR, "quarterly_drug.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    return None


@st.cache_data(show_spinner=False)
def load_quarterly_reac() -> pd.DataFrame | None:
    path = os.path.join(_CACHE_DIR, "quarterly_reac.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    return None

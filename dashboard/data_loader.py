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

try:
    import streamlit as st
except ImportError:
    from types import SimpleNamespace
    def _noop(*args, **kwargs):
        return args[0] if args and callable(args[0]) else (lambda f: f)
    st = SimpleNamespace(cache_resource=_noop, cache_data=_noop)

from logger import get_logger

log = get_logger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))


def _default_cache_dir(parquet_dir: str) -> str:
    base = os.path.basename(os.path.normpath(parquet_dir))
    if base == "parquet_recent":
        cache_name = "cache_recent"
    elif base == "parquet":
        cache_name = "cache_full"
    else:
        cache_name = f"cache_{base}"
    return os.path.join(_HERE, cache_name)

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
    _default_cache_dir(_PARQUET_DIR),
)

TABLE_NAMES = ["demo", "drug", "reac", "outc", "rpsr", "ther", "indi"]


@st.cache_resource(show_spinner="Loading FAERS tables…")
def load_tables() -> dict[str, pd.DataFrame]:
    """Load all FAERS tables, deduplicate, and normalise key columns.

    Uses cache_resource so the large DataFrames are shared across all user
    sessions rather than copied per-session (cache_data behaviour).
    """
    import time
    t0 = time.perf_counter()
    log.info("Loading FAERS parquet tables from %s", _PARQUET_DIR)

    tables: dict[str, pd.DataFrame] = {}
    for name in TABLE_NAMES:
        path = os.path.join(_PARQUET_DIR, f"{name}.parquet")
        t1 = time.perf_counter()
        tables[name] = pd.read_parquet(path)
        log.debug("  Loaded %-6s  %9s rows  (%.2fs)", name, f"{len(tables[name]):,}", time.perf_counter() - t1)

    # ── Deduplication is done at build time by STARTHERE.py ──────────────────
    # demo.parquet already contains only the latest caseversion per caseid, and
    # all other tables have already been filtered to matching primaryids.

    demo = tables["demo"].copy()

    # ── Derive synthetic columns if not present (test fixtures may omit them) ──
    # age_grp: bucket numeric age into MedDRA age groups
    if "age_grp" not in demo.columns:
        age = pd.to_numeric(demo.get("age", pd.Series(dtype=float)), errors="coerce")
        demo["age_grp"] = pd.cut(
            age,
            bins=[-1, 1, 11, 17, 64, 150],
            labels=["N", "I", "C", "A", "E"],
        ).astype(str).replace("nan", pd.NA)

    # occp_cod: fall back to reporter_type when present
    if "occp_cod" not in demo.columns:
        demo["occp_cod"] = demo.get("reporter_type", pd.Series("OT", index=demo.index))

    # reporter_country: fall back to occr_country when present
    if "reporter_country" not in demo.columns:
        demo["reporter_country"] = demo.get("occr_country", pd.Series("", index=demo.index))

    tables["demo"] = demo

    # ── Normalise drug names ───────────────────────────────────────────────────
    drug = tables["drug"].copy()
    drug["drugname_norm"] = drug["drugname"].str.upper().str.strip()
    drug["prod_ai_norm"]  = drug["prod_ai"].str.upper().str.strip()
    drug["canon"] = drug["prod_ai_norm"].fillna(drug["drugname_norm"])
    # Propagate quarter from demo so quarter-filter helpers work on the drug table
    if "quarter" not in drug.columns:
        drug = drug.merge(demo[["primaryid", "quarter"]], on="primaryid", how="left")
    tables["drug"] = drug

    # ── Normalise reaction PTs ─────────────────────────────────────────────────
    reac = tables["reac"].copy()
    reac["pt_norm"] = reac["pt"].str.strip().str.title()
    # Propagate quarter from demo so quarter-filter helpers work on the reac table
    if "quarter" not in reac.columns:
        reac = reac.merge(demo[["primaryid", "quarter"]], on="primaryid", how="left")
    tables["reac"] = reac

    # ── Propagate quarter to auxiliary tables (indi, rpsr, ther) ──────────────
    _pid_quarter = demo[["primaryid", "quarter"]]
    for _tbl in ["indi", "rpsr", "ther"]:
        _t = tables[_tbl]
        if "quarter" not in _t.columns:
            tables[_tbl] = _t.merge(_pid_quarter, on="primaryid", how="left")

    log.info("load_tables complete: %s cases, %s drug rows, %s reaction rows  (%.2fs total)",
             f"{len(tables['demo']):,}", f"{len(tables['drug']):,}", f"{len(tables['reac']):,}",
             time.perf_counter() - t0)
    return tables


@st.cache_resource(show_spinner=False)
def load_lookup_tables() -> dict[str, pd.DataFrame]:
    """Build compact lookup tables used by the query layer.

    These tables trade a small amount of startup work for much faster repeated
    dashboard interactions by avoiding full scans of the large source tables.
    """
    import time
    t0 = time.perf_counter()
    log.info("Building lookup tables...")
    tables = load_tables()

    demo_quarters = (
        tables["demo"][["quarter", "primaryid"]]
        .drop_duplicates()
        .sort_values(["quarter", "primaryid"])
        .set_index("quarter")
    )
    drug_cases = (
        tables["drug"][["canon", "primaryid"]]
        .drop_duplicates()
        .sort_values(["canon", "primaryid"])
        .set_index("canon")
    )
    drug_role_cases = (
        tables["drug"][["canon", "role_cod", "primaryid"]]
        .drop_duplicates()
        .sort_values(["canon", "role_cod", "primaryid"])
        .set_index(["canon", "role_cod"])
    )
    reaction_cases = (
        tables["reac"][["pt_norm", "primaryid"]]
        .drop_duplicates()
        .sort_values(["pt_norm", "primaryid"])
        .set_index("pt_norm")
    )

    result = {
        "quarter_cases": demo_quarters,
        "drug_cases": drug_cases,
        "drug_role_cases": drug_role_cases,
        "reaction_cases": reaction_cases,
    }
    log.info("Lookup tables ready: %s quarters, %s drug entries, %s reaction entries  (%.2fs)",
             len(demo_quarters.index.unique()), len(drug_cases), len(reaction_cases),
             time.perf_counter() - t0)
    return result


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


@st.cache_data(show_spinner=False)
def get_dataset_profile() -> dict[str, str | int]:
    demo = load_tables()["demo"]
    quarters = sorted(demo["quarter"].dropna().unique().tolist())
    mode = "Recent sample" if os.path.basename(os.path.normpath(_PARQUET_DIR)) == "parquet_recent" else "Full history"
    return {
        "mode": mode,
        "parquet_dir": _PARQUET_DIR,
        "cache_dir": _CACHE_DIR,
        "quarter_start": quarters[0] if quarters else "Unknown",
        "quarter_end": quarters[-1] if quarters else "Unknown",
        "n_quarters": len(quarters),
    }


# ── Pre-computed cache tables ─────────────────────────────────────────────────
# Also cache_resource: these are large parquet files loaded once and shared.

def _load_cache_parquet(name: str, path: str) -> pd.DataFrame | None:
    if os.path.exists(path):
        df = pd.read_parquet(path)
        log.info("Loaded cache table %-20s  %s rows", name, f"{len(df):,}")
        return df
    log.warning("Cache table not found: %s  (run precompute.py to build it)", path)
    return None


@st.cache_resource(show_spinner="Loading signal table…")
def load_prr_table() -> pd.DataFrame | None:
    return _load_cache_parquet("prr_table", os.path.join(_CACHE_DIR, "prr_table.parquet"))


@st.cache_resource(show_spinner=False)
def load_drug_summary() -> pd.DataFrame | None:
    return _load_cache_parquet("drug_summary", os.path.join(_CACHE_DIR, "drug_summary.parquet"))


@st.cache_resource(show_spinner=False)
def load_reac_summary() -> pd.DataFrame | None:
    return _load_cache_parquet("reac_summary", os.path.join(_CACHE_DIR, "reac_summary.parquet"))


@st.cache_resource(show_spinner=False)
def load_quarterly_drug() -> pd.DataFrame | None:
    return _load_cache_parquet("quarterly_drug", os.path.join(_CACHE_DIR, "quarterly_drug.parquet"))


@st.cache_resource(show_spinner=False)
def load_quarterly_reac() -> pd.DataFrame | None:
    return _load_cache_parquet("quarterly_reac", os.path.join(_CACHE_DIR, "quarterly_reac.parquet"))


# ── Background cache warm-up ──────────────────────────────────────────────────
# This flag lives in the module namespace, which Python keeps alive across all
# Streamlit reruns (modules stay in sys.modules). So _warm_started = True after
# the first run and the background thread only ever fires once per server start.

_warm_started: bool = False


def warm_all_tables() -> None:
    """Call every cache_resource loader so data is in memory before any user arrives."""
    import time
    t0 = time.perf_counter()
    log.info("Background cache warm-up starting...")
    load_tables()
    load_lookup_tables()
    load_prr_table()
    load_drug_summary()
    load_reac_summary()
    load_quarterly_drug()
    load_quarterly_reac()
    log.info("Background cache warm-up complete (%.2fs)", time.perf_counter() - t0)

"""
test_data_loader.py

Tests for data_loader.py — deduplication, normalisation, and path configuration.
These tests read directly from the synthetic parquet fixtures without going
through Streamlit caching (cache functions are tested for their side-effects
only in test_app_smoke.py).
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

# conftest.py already set FAERS_PARQUET_DIR / FAERS_CACHE_DIR and added
# dashboard/ to sys.path before we get here.

_FIXTURE_DIR = Path(__file__).parent / "fixtures"
_CACHE_DIR   = _FIXTURE_DIR / "cache"


# ── Fixture file existence ─────────────────────────────────────────────────────

class TestFixtureFiles:
    SOURCE_TABLES = ["demo", "drug", "reac", "outc", "indi", "ther", "rpsr"]
    CACHE_TABLES  = [
        "prr_table", "drug_summary", "reac_summary",
        "quarterly_drug", "quarterly_reac",
    ]

    @pytest.mark.parametrize("name", SOURCE_TABLES)
    def test_source_parquet_exists(self, name: str) -> None:
        assert (_FIXTURE_DIR / f"{name}.parquet").exists(), f"Missing {name}.parquet"

    @pytest.mark.parametrize("name", CACHE_TABLES)
    def test_cache_parquet_exists(self, name: str) -> None:
        assert (_CACHE_DIR / f"{name}.parquet").exists(), f"Missing cache/{name}.parquet"


# ── Deduplication logic ────────────────────────────────────────────────────────

class TestDemoDeduplication:
    """
    generate_fixtures.py creates 20 duplicate caseids (caseids 1-20) with two
    primaryids each.  After dedup we should have exactly N_CASES - 20 rows.
    """

    def test_dedup_reduces_row_count(self, raw_demo: pd.DataFrame) -> None:
        raw_n = len(raw_demo)
        deduped = (
            raw_demo
            .sort_values("caseversion")
            .drop_duplicates("caseid", keep="last")
        )
        # 20 duplicates introduced, so deduped should have 20 fewer rows
        assert len(deduped) == raw_n - 20

    def test_dedup_keeps_highest_caseversion(self, raw_demo: pd.DataFrame) -> None:
        deduped = (
            raw_demo
            .sort_values("caseversion")
            .drop_duplicates("caseid", keep="last")
        )
        # For caseids 1-20 the fixture assigns caseversion=2 to the first 20 rows
        duplicated_caseids = list(range(1, 21))
        subset = deduped[deduped["caseid"].isin(duplicated_caseids)]
        assert (subset["caseversion"] == 2).all(), "Should keep caseversion=2 rows"

    def test_no_duplicate_caseids_after_dedup(self, raw_demo: pd.DataFrame) -> None:
        deduped = (
            raw_demo
            .sort_values("caseversion")
            .drop_duplicates("caseid", keep="last")
        )
        assert deduped["caseid"].is_unique


# ── Drug normalisation ────────────────────────────────────────────────────────

class TestDrugNormalisation:
    def test_drugname_norm_is_uppercase(self, tables: dict) -> None:
        drug = tables["drug"]
        assert (drug["drugname_norm"] == drug["drugname_norm"].str.upper()).all()

    def test_prod_ai_norm_no_leading_trailing_spaces(self, tables: dict) -> None:
        drug = tables["drug"]
        assert (drug["prod_ai_norm"] == drug["prod_ai_norm"].str.strip()).all()

    def test_canon_column_present_and_not_null(self, tables: dict) -> None:
        drug = tables["drug"]
        assert "canon" in drug.columns
        assert drug["canon"].notna().all()

    def test_expected_drug_names_present(self, tables: dict) -> None:
        drug = tables["drug"]
        canons = set(drug["canon"].unique())
        for name in ["ASPIRIN", "WARFARIN", "METFORMIN"]:
            assert name in canons, f"{name} not found in canon column"


# ── Reaction normalisation ────────────────────────────────────────────────────

class TestReacNormalisation:
    def test_pt_norm_is_title_case(self, tables: dict) -> None:
        reac = tables["reac"]
        assert (reac["pt_norm"] == reac["pt_norm"].str.title()).all()

    def test_pt_norm_no_null(self, tables: dict) -> None:
        reac = tables["reac"]
        assert reac["pt_norm"].notna().all()

    def test_bleeding_reaction_present(self, tables: dict) -> None:
        reac = tables["reac"]
        assert "Bleeding" in reac["pt_norm"].values


# ── Valid PIDs propagation ────────────────────────────────────────────────────

class TestPidPropagation:
    def test_drug_pids_subset_of_demo_pids(self, tables: dict) -> None:
        demo_pids = set(tables["demo"]["primaryid"].unique())
        drug_pids = set(tables["drug"]["primaryid"].unique())
        assert drug_pids.issubset(demo_pids)

    def test_reac_pids_subset_of_demo_pids(self, tables: dict) -> None:
        demo_pids = set(tables["demo"]["primaryid"].unique())
        reac_pids = set(tables["reac"]["primaryid"].unique())
        assert reac_pids.issubset(demo_pids)

    def test_outc_pids_subset_of_demo_pids(self, tables: dict) -> None:
        demo_pids = set(tables["demo"]["primaryid"].unique())
        outc_pids = set(tables["outc"]["primaryid"].unique())
        assert outc_pids.issubset(demo_pids)


# ── Env-var path override ─────────────────────────────────────────────────────

class TestEnvVarPaths:
    def test_parquet_dir_env_var_is_set(self) -> None:
        assert os.environ.get("FAERS_PARQUET_DIR") == str(_FIXTURE_DIR)

    def test_cache_dir_env_var_is_set(self) -> None:
        assert os.environ.get("FAERS_CACHE_DIR") == str(_CACHE_DIR)

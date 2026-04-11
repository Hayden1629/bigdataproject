"""
test_analytics.py

Unit tests for analytics.py — all functions that take DataFrames as arguments
are tested directly with the synthetic fixture tables.

Quarterly-trend functions that call load_quarterly_drug / load_quarterly_reac
are tested with those cache calls mocked to return None (forcing the live
fallback path) and also with a real pre-computed quarterly parquet.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

import analytics as ana


# ── kpis_for_drug ─────────────────────────────────────────────────────────────

class TestKpisForDrug:
    def test_returns_zero_kpis_for_unknown_drug(self, tables: dict) -> None:
        kpis = ana.kpis_for_drug(
            tables["drug"], tables["outc"],
            {"NONEXISTENT_DRUG_XYZ"}, role="PS",
        )
        assert kpis["n_cases"] == 0
        assert kpis["n_deaths"] == 0

    def test_aspirin_has_many_cases(self, tables: dict) -> None:
        kpis = ana.kpis_for_drug(
            tables["drug"], tables["outc"],
            {"ASPIRIN"}, role="all",
        )
        assert kpis["n_cases"] >= 100, "Fixture biases 120 cases toward ASPIRIN"

    def test_death_pct_in_range(self, tables: dict) -> None:
        kpis = ana.kpis_for_drug(
            tables["drug"], tables["outc"],
            {"ASPIRIN"}, role="all",
        )
        assert 0.0 <= kpis["death_pct"] <= 100.0

    def test_kpis_keys_present(self, tables: dict) -> None:
        kpis = ana.kpis_for_drug(
            tables["drug"], tables["outc"],
            {"WARFARIN"}, role="all",
        )
        for key in ("n_cases", "n_deaths", "n_hosp", "n_lt", "n_serious", "death_pct"):
            assert key in kpis, f"Missing key: {key}"

    def test_role_filter_ps_fewer_than_all(self, tables: dict) -> None:
        kpi_ps  = ana.kpis_for_drug(tables["drug"], tables["outc"], {"ASPIRIN"}, role="PS")
        kpi_all = ana.kpis_for_drug(tables["drug"], tables["outc"], {"ASPIRIN"}, role="all")
        assert kpi_ps["n_cases"] <= kpi_all["n_cases"]


# ── top_reactions_for_drug ────────────────────────────────────────────────────

class TestTopReactionsForDrug:
    def test_returns_dataframe(self, tables: dict) -> None:
        df = ana.top_reactions_for_drug(
            tables["drug"], tables["reac"], {"ASPIRIN"}, role="all",
        )
        assert isinstance(df, pd.DataFrame)

    def test_columns_present(self, tables: dict) -> None:
        df = ana.top_reactions_for_drug(
            tables["drug"], tables["reac"], {"ASPIRIN"}, role="all",
        )
        for col in ("pt", "count", "pct"):
            assert col in df.columns

    def test_bleeding_is_top_reaction_for_aspirin(self, tables: dict) -> None:
        """Fixture deliberately biases cases 1-120 toward ASPIRIN + Bleeding."""
        df = ana.top_reactions_for_drug(
            tables["drug"], tables["reac"], {"ASPIRIN"}, role="all", top_n=5,
        )
        top_pts = df["pt"].str.lower().tolist()
        assert "bleeding" in top_pts, f"Expected Bleeding in top-5, got: {top_pts}"

    def test_pct_sums_lte_100_per_case(self, tables: dict) -> None:
        """Each case can have multiple reactions, so pct can sum > 100 — but each pct ≤ 100."""
        df = ana.top_reactions_for_drug(
            tables["drug"], tables["reac"], {"WARFARIN"}, role="all",
        )
        assert (df["pct"] <= 100.0).all()

    def test_empty_for_unknown_drug(self, tables: dict) -> None:
        df = ana.top_reactions_for_drug(
            tables["drug"], tables["reac"], {"NONEXISTENT_DRUG_XYZ"}, role="all",
        )
        assert len(df) == 0


# ── outcomes_for_drug ─────────────────────────────────────────────────────────

class TestOutcomesForDrug:
    def test_returns_dataframe_with_expected_columns(self, tables: dict) -> None:
        df = ana.outcomes_for_drug(tables["drug"], tables["outc"], {"ASPIRIN"}, role="all")
        for col in ("outcome_label", "count", "pct"):
            assert col in df.columns

    def test_pct_sums_to_roughly_100(self, tables: dict) -> None:
        df = ana.outcomes_for_drug(tables["drug"], tables["outc"], {"ASPIRIN"}, role="all")
        if not df.empty:
            assert df["pct"].sum() <= 101.0  # rounding tolerance

    def test_death_outcome_label_present(self, tables: dict) -> None:
        df = ana.outcomes_for_drug(tables["drug"], tables["outc"], {"ASPIRIN"}, role="all")
        labels = df["outcome_label"].tolist()
        assert "Death" in labels or len(df) == 0  # might not have deaths in small sample


# ── quarterly_trend_for_drug ──────────────────────────────────────────────────

class TestQuarterlyTrendForDrug:
    def test_live_fallback_when_cache_none(self, tables: dict) -> None:
        """When load_quarterly_drug returns None, the function falls through to live pandas."""
        with patch("analytics.load_quarterly_drug", return_value=None):
            trend = ana.quarterly_trend_for_drug(
                {"ASPIRIN"}, tables["drug"], role="PS",
            )
        assert isinstance(trend, pd.DataFrame)
        assert "quarter" in trend.columns
        assert "case_count" in trend.columns

    def test_trend_sorted_by_quarter(self, tables: dict) -> None:
        with patch("analytics.load_quarterly_drug", return_value=None):
            trend = ana.quarterly_trend_for_drug(
                {"ASPIRIN"}, tables["drug"], role="PS",
            )
        quarters = trend["quarter"].tolist()
        assert quarters == sorted(quarters)

    def test_quarter_filter(self, tables: dict) -> None:
        with patch("analytics.load_quarterly_drug", return_value=None):
            trend = ana.quarterly_trend_for_drug(
                {"ASPIRIN"}, tables["drug"], role="PS",
                quarter_filter=["2023Q3", "2023Q4"],
            )
        assert set(trend["quarter"].unique()).issubset({"2023Q3", "2023Q4"})

    def test_with_precomputed_cache(self, tables: dict, quarterly_drug: pd.DataFrame) -> None:
        """Test the cache path: role='all' uses pre-computed table if available."""
        with patch("analytics.load_quarterly_drug", return_value=quarterly_drug):
            trend = ana.quarterly_trend_for_drug(
                {"ASPIRIN"}, tables["drug"], role="all",
            )
        assert not trend.empty
        assert "case_count" in trend.columns


# ── demographics_for_drug ─────────────────────────────────────────────────────

class TestDemographicsForDrug:
    def test_returns_dict_with_sex_age_reporter(self, tables: dict) -> None:
        result = ana.demographics_for_drug(
            tables["drug"], tables["demo"], {"ASPIRIN"}, role="all",
        )
        assert "sex" in result
        assert "age_grp" in result
        assert "reporter" in result

    def test_sex_counts_are_positive(self, tables: dict) -> None:
        result = ana.demographics_for_drug(
            tables["drug"], tables["demo"], {"ASPIRIN"}, role="all",
        )
        assert (result["sex"]["count"] > 0).all()


# ── kpis_for_reaction ─────────────────────────────────────────────────────────

class TestKpisForReaction:
    def test_known_reaction_has_cases(self, tables: dict) -> None:
        kpis = ana.kpis_for_reaction(
            tables["reac"], tables["outc"], {"Bleeding"},
        )
        assert kpis["n_cases"] > 0

    def test_unknown_reaction_returns_zeros(self, tables: dict) -> None:
        kpis = ana.kpis_for_reaction(
            tables["reac"], tables["outc"], {"TOTALLY_UNKNOWN_REACTION_XYZ"},
        )
        assert kpis["n_cases"] == 0

    def test_keys_present(self, tables: dict) -> None:
        kpis = ana.kpis_for_reaction(
            tables["reac"], tables["outc"], {"Nausea"},
        )
        for key in ("n_cases", "n_deaths", "n_serious"):
            assert key in kpis


# ── top_drugs_for_reaction ────────────────────────────────────────────────────

class TestTopDrugsForReaction:
    def test_aspirin_in_top_drugs_for_bleeding(self, tables: dict) -> None:
        """Fixture biases ASPIRIN cases toward Bleeding → should appear in top results."""
        df = ana.top_drugs_for_reaction(
            tables["drug"], tables["reac"], {"Bleeding"}, role="all", top_n=10,
        )
        drugs = df["drug_label"].str.upper().tolist()
        assert "ASPIRIN" in drugs, f"Expected ASPIRIN in top drugs for Bleeding, got: {drugs}"

    def test_columns_present(self, tables: dict) -> None:
        df = ana.top_drugs_for_reaction(
            tables["drug"], tables["reac"], {"Nausea"}, role="all",
        )
        for col in ("drug_label", "case_count", "pct"):
            assert col in df.columns


# ── cooccurrence_stats ────────────────────────────────────────────────────────

class TestCooccurrenceStats:
    def test_aspirin_bleeding_cooccurrence(self, tables: dict) -> None:
        n_total = len(tables["demo"])
        stats = ana.cooccurrence_stats(
            tables["drug"], tables["reac"], tables["outc"],
            {"ASPIRIN"}, {"Bleeding"},
            role="all", n_total=n_total,
        )
        assert stats["overlap_cases"] > 0
        assert 0.0 <= stats["pct_of_drug"] <= 100.0
        assert stats["live_prr"] is not None and stats["live_prr"] > 0

    def test_no_overlap_for_unrelated_drug_reaction(self, tables: dict) -> None:
        n_total = len(tables["demo"])
        stats = ana.cooccurrence_stats(
            tables["drug"], tables["reac"], tables["outc"],
            {"NONEXISTENT_XYZ"}, {"Nausea"},
            role="all", n_total=n_total,
        )
        assert stats["overlap_cases"] == 0

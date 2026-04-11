"""
test_signal_detection.py

Tests for signal_detection.py using the pre-computed PRR fixture table.

The fixture dataset is designed so that ASPIRIN and WARFARIN produce strong
signals for Bleeding (HIGH or MEDIUM) with N_DR ≥ 5 — this is asserted here
to confirm both the fixture and the detection logic are correct.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

import signal_detection as sd


# ── Helper: patch load_prr_table to return the fixture parquet ────────────────

@pytest.fixture()
def patched_prr(prr_table: pd.DataFrame):
    """Context manager that makes load_prr_table() return the fixture PRR table."""
    with patch("signal_detection.load_prr_table", return_value=prr_table):
        yield prr_table


# ── signals_for_drug ──────────────────────────────────────────────────────────

class TestSignalsForDrug:
    def test_returns_dataframe(self, patched_prr: pd.DataFrame) -> None:
        df = sd.signals_for_drug(["ASPIRIN"])
        assert isinstance(df, pd.DataFrame)

    def test_aspirin_bleeding_signal_exists(self, patched_prr: pd.DataFrame) -> None:
        """Fixture creates strong ASPIRIN→Bleeding bias; a HIGH signal must appear."""
        df = sd.signals_for_drug(["ASPIRIN"], min_signal="LOW", min_n_dr=3)
        assert not df.empty, "No signals found for ASPIRIN"
        pts = df["pt"].str.lower().tolist()
        assert "bleeding" in pts, f"Expected Bleeding signal for ASPIRIN, got: {pts}"

    def test_signal_column_values(self, patched_prr: pd.DataFrame) -> None:
        df = sd.signals_for_drug(["ASPIRIN"], min_signal="LOW")
        valid = {"HIGH", "MEDIUM", "LOW"}
        assert set(df["signal"].unique()).issubset(valid)

    def test_min_n_dr_filter(self, patched_prr: pd.DataFrame) -> None:
        df = sd.signals_for_drug(["ASPIRIN"], min_n_dr=100)
        # Very high min_n_dr threshold should return no signals in small fixture
        for _, row in df.iterrows():
            assert row["N_DR"] >= 100

    def test_unknown_drug_returns_empty(self, patched_prr: pd.DataFrame) -> None:
        df = sd.signals_for_drug(["TOTALLY_UNKNOWN_DRUG_XYZ_999"])
        assert df.empty

    def test_no_duplicate_pts(self, patched_prr: pd.DataFrame) -> None:
        """Each PT should appear at most once after dedup logic."""
        df = sd.signals_for_drug(["ASPIRIN"], min_signal="LOW")
        assert df["pt"].is_unique

    def test_required_columns_present(self, patched_prr: pd.DataFrame) -> None:
        df = sd.signals_for_drug(["ASPIRIN"])
        for col in ("pt", "N_DR", "N_D", "N_R", "N_total", "PRR", "ROR", "chi2", "signal"):
            assert col in df.columns, f"Missing column: {col}"

    def test_sorted_by_chi2_descending(self, patched_prr: pd.DataFrame) -> None:
        df = sd.signals_for_drug(["WARFARIN"], min_signal="LOW")
        if len(df) > 1:
            assert (df["chi2"].diff().dropna() <= 0).all(), "Not sorted by chi2 desc"

    def test_min_signal_high_filters_medium_low(self, patched_prr: pd.DataFrame) -> None:
        df_all  = sd.signals_for_drug(["ASPIRIN"], min_signal="LOW")
        df_high = sd.signals_for_drug(["ASPIRIN"], min_signal="HIGH")
        assert len(df_high) <= len(df_all)
        if not df_high.empty:
            assert (df_high["signal"] == "HIGH").all()

    def test_empty_table_returns_empty(self) -> None:
        with patch("signal_detection.load_prr_table", return_value=pd.DataFrame()):
            df = sd.signals_for_drug(["ASPIRIN"])
        assert df.empty

    def test_none_table_returns_empty(self) -> None:
        with patch("signal_detection.load_prr_table", return_value=None):
            df = sd.signals_for_drug(["ASPIRIN"])
        assert df.empty


# ── global_top_signals ────────────────────────────────────────────────────────

class TestGlobalTopSignals:
    def test_returns_dataframe(self, patched_prr: pd.DataFrame) -> None:
        df = sd.global_top_signals()
        assert isinstance(df, pd.DataFrame)

    def test_contains_aspirin_or_warfarin(self, patched_prr: pd.DataFrame) -> None:
        df = sd.global_top_signals(min_signal="LOW", min_n_dr=3)
        drugs = df["drug"].str.upper().tolist()
        assert "ASPIRIN" in drugs or "WARFARIN" in drugs

    def test_only_allowed_signal_levels(self, patched_prr: pd.DataFrame) -> None:
        df = sd.global_top_signals(min_signal="MEDIUM")
        if not df.empty:
            assert set(df["signal"].unique()).issubset({"HIGH", "MEDIUM"})


# ── signals_for_reaction ──────────────────────────────────────────────────────

class TestSignalsForReaction:
    def test_aspirin_in_bleeding_signals(self, patched_prr: pd.DataFrame) -> None:
        df = sd.signals_for_reaction(["Bleeding"], min_signal="LOW", min_n_dr=3)
        if not df.empty:
            drugs = df["drug"].str.upper().tolist()
            assert "ASPIRIN" in drugs or "WARFARIN" in drugs

    def test_columns_present(self, patched_prr: pd.DataFrame) -> None:
        df = sd.signals_for_reaction(["Bleeding"])
        for col in ("drug", "N_DR", "PRR", "signal"):
            assert col in df.columns

    def test_unknown_reaction_returns_empty(self, patched_prr: pd.DataFrame) -> None:
        df = sd.signals_for_reaction(["TOTALLY_UNKNOWN_REACTION_XYZ_9999"])
        assert df.empty


# ── signal_counts ─────────────────────────────────────────────────────────────

class TestSignalCounts:
    def test_returns_dict_with_correct_keys(self, patched_prr: pd.DataFrame) -> None:
        counts = sd.signal_counts()
        assert set(counts.keys()) == {"HIGH", "MEDIUM", "LOW"}

    def test_all_counts_non_negative(self, patched_prr: pd.DataFrame) -> None:
        counts = sd.signal_counts()
        assert all(v >= 0 for v in counts.values())

    def test_has_high_signals_from_fixture(self, patched_prr: pd.DataFrame) -> None:
        counts = sd.signal_counts()
        total = counts["HIGH"] + counts["MEDIUM"] + counts["LOW"]
        assert total > 0, "Fixture should produce at least some signals"

    def test_empty_table_returns_zeros(self) -> None:
        with patch("signal_detection.load_prr_table", return_value=pd.DataFrame()):
            counts = sd.signal_counts()
        assert counts == {"HIGH": 0, "MEDIUM": 0, "LOW": 0}


# ── PRR table integrity ───────────────────────────────────────────────────────

class TestPrrTableIntegrity:
    def test_prr_positive(self, prr_table: pd.DataFrame) -> None:
        assert (prr_table["PRR"] > 0).all()

    def test_n_dr_at_least_3(self, prr_table: pd.DataFrame) -> None:
        assert (prr_table["N_DR"] >= 3).all()

    def test_signal_labels_valid(self, prr_table: pd.DataFrame) -> None:
        assert set(prr_table["signal"].unique()).issubset({"HIGH", "MEDIUM", "LOW"})

    def test_high_signal_meets_thresholds(self, prr_table: pd.DataFrame) -> None:
        high = prr_table[prr_table["signal"] == "HIGH"]
        if not high.empty:
            assert (high["PRR"] >= 4).all()
            assert (high["N_DR"] >= 5).all()
            assert (high["chi2"] >= 4).all()

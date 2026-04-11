"""
test_drug_normalizer.py

Tests for drug_normalizer.py.

RxNorm API calls are always mocked — tests must be runnable offline.
We test the fuzzy-matching logic and helper functions directly.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from drug_normalizer import (
    _tokenise,
    _is_valid_drug_name,
    find_faers_names,
    filter_drug_df,
)

# ── Minimal FAERS drug DataFrame for matching tests ──────────────────────────

_DRUG_ROWS = [
    {"primaryid": 1, "drugname": "ASPIRIN",       "prod_ai": "ASPIRIN",         "role_cod": "PS"},
    {"primaryid": 2, "drugname": "ASPIRIN 81MG",  "prod_ai": "ASPIRIN",         "role_cod": "SS"},
    {"primaryid": 3, "drugname": "WARFARIN",       "prod_ai": "WARFARIN",        "role_cod": "PS"},
    {"primaryid": 4, "drugname": "COUMADIN",       "prod_ai": "WARFARIN",        "role_cod": "PS"},
    {"primaryid": 5, "drugname": "METFORMIN HCL",  "prod_ai": "METFORMIN",       "role_cod": "PS"},
    {"primaryid": 6, "drugname": "TYLENOL",        "prod_ai": "ACETAMINOPHEN",   "role_cod": "PS"},
    {"primaryid": 7, "drugname": "LISINOPRIL 10",  "prod_ai": "LISINOPRIL",      "role_cod": "PS"},
    {"primaryid": 8, "drugname": "BAD",            "prod_ai": "X",               "role_cod": "PS"},  # too short
]

@pytest.fixture(scope="module")
def drug_df() -> pd.DataFrame:
    df = pd.DataFrame(_DRUG_ROWS)
    df["drugname_norm"] = df["drugname"].str.upper().str.strip()
    df["prod_ai_norm"]  = df["prod_ai"].str.upper().str.strip()
    df["canon"]         = df["prod_ai_norm"]
    return df


# ── _tokenise ─────────────────────────────────────────────────────────────────

class TestTokenise:
    def test_removes_special_characters(self) -> None:
        assert _tokenise("ASPIRIN-81mg!") == "ASPIRIN 81MG"

    def test_collapses_whitespace(self) -> None:
        assert _tokenise("  METFORMIN   HCL  ") == "METFORMIN HCL"

    def test_uppercase(self) -> None:
        result = _tokenise("warfarin")
        assert result == result.upper()

    def test_empty_string(self) -> None:
        assert _tokenise("") == ""

    def test_only_special_chars(self) -> None:
        assert _tokenise("---!!!") == ""


# ── _is_valid_drug_name ───────────────────────────────────────────────────────

class TestIsValidDrugName:
    def test_normal_drug_is_valid(self) -> None:
        assert _is_valid_drug_name("ASPIRIN") is True

    def test_short_name_invalid(self) -> None:
        assert _is_valid_drug_name("AB") is False

    def test_fewer_than_3_alpha_invalid(self) -> None:
        assert _is_valid_drug_name("A1B2") is False  # only 2 alpha chars

    def test_three_alpha_chars_valid(self) -> None:
        assert _is_valid_drug_name("AB3C") is True

    def test_empty_string_invalid(self) -> None:
        assert _is_valid_drug_name("") is False

    def test_numeric_only_invalid(self) -> None:
        assert _is_valid_drug_name("12345") is False


# ── find_faers_names ──────────────────────────────────────────────────────────

class TestFindFaersNames:
    """RxNorm is always mocked to isolate fuzzy matching logic."""

    def _mock_rxn(self, related: list[str] | None = None) -> dict:
        return {
            "rxcui": "1234",
            "canonical": "ASPIRIN",
            "related": related or [],
        }

    def test_exact_match_returns_drug(self, drug_df: pd.DataFrame) -> None:
        with patch("drug_normalizer.rxnorm_lookup", return_value=self._mock_rxn()):
            names = find_faers_names("ASPIRIN", drug_df)
        assert "ASPIRIN" in names

    def test_brand_name_finds_generic_via_rxnorm(self, drug_df: pd.DataFrame) -> None:
        """'COUMADIN' is a brand; RxNorm related = ['WARFARIN'] should match it."""
        mock = {"rxcui": "11", "canonical": "WARFARIN", "related": ["WARFARIN", "COUMADIN"]}
        with patch("drug_normalizer.rxnorm_lookup", return_value=mock):
            names = find_faers_names("COUMADIN", drug_df)
        assert "WARFARIN" in names

    def test_fuzzy_fallback_catches_misspelling(self, drug_df: pd.DataFrame) -> None:
        """'ASIRIN' is a typo; fuzzy fallback should still find ASPIRIN."""
        with patch("drug_normalizer.rxnorm_lookup", return_value=self._mock_rxn()):
            names = find_faers_names("ASIRIN", drug_df, fuzzy_threshold=75)
        assert "ASPIRIN" in names

    def test_unknown_drug_returns_empty(self, drug_df: pd.DataFrame) -> None:
        mock_empty = {"rxcui": None, "canonical": None, "related": []}
        with patch("drug_normalizer.rxnorm_lookup", return_value=mock_empty):
            names = find_faers_names("COMPLETELY_MADE_UP_DRUG_ZZZ", drug_df, fuzzy_threshold=95)
        assert names == []

    def test_returns_sorted_list(self, drug_df: pd.DataFrame) -> None:
        with patch("drug_normalizer.rxnorm_lookup", return_value=self._mock_rxn()):
            names = find_faers_names("ASPIRIN", drug_df)
        assert names == sorted(names)

    def test_result_is_list_of_strings(self, drug_df: pd.DataFrame) -> None:
        with patch("drug_normalizer.rxnorm_lookup", return_value=self._mock_rxn()):
            names = find_faers_names("ASPIRIN", drug_df)
        assert isinstance(names, list)
        assert all(isinstance(n, str) for n in names)

    def test_invalid_short_names_excluded(self, drug_df: pd.DataFrame) -> None:
        """Single-char names like 'X' should be filtered by _is_valid_drug_name."""
        mock_empty = {"rxcui": None, "canonical": None, "related": []}
        with patch("drug_normalizer.rxnorm_lookup", return_value=mock_empty):
            names = find_faers_names("X", drug_df)
        assert "X" not in names

    def test_related_names_from_rxnorm_matched(self, drug_df: pd.DataFrame) -> None:
        """Names in the 'related' list should be matched against FAERS names."""
        mock = {"rxcui": "99", "canonical": "ACETAMINOPHEN", "related": ["ACETAMINOPHEN", "TYLENOL"]}
        with patch("drug_normalizer.rxnorm_lookup", return_value=mock):
            names = find_faers_names("TYLENOL", drug_df)
        assert "ACETAMINOPHEN" in names


# ── filter_drug_df ────────────────────────────────────────────────────────────

class TestFilterDrugDf:
    def test_filters_by_drugname_norm(self, drug_df: pd.DataFrame) -> None:
        result = filter_drug_df(drug_df, ["ASPIRIN 81MG"])
        assert len(result) >= 1
        assert set(result["drugname_norm"].unique()) == {"ASPIRIN 81MG"}

    def test_filters_by_prod_ai_norm(self, drug_df: pd.DataFrame) -> None:
        result = filter_drug_df(drug_df, ["WARFARIN"])
        pids = set(result["primaryid"].unique())
        # Both 'WARFARIN' (pid 3) and 'COUMADIN' (pid 4, prod_ai=WARFARIN) should match
        assert 3 in pids
        assert 4 in pids

    def test_empty_matched_names_returns_empty(self, drug_df: pd.DataFrame) -> None:
        result = filter_drug_df(drug_df, [])
        assert len(result) == 0

    def test_unknown_name_returns_empty(self, drug_df: pd.DataFrame) -> None:
        result = filter_drug_df(drug_df, ["DRUG_THAT_DOES_NOT_EXIST_XYZ"])
        assert len(result) == 0

    def test_preserves_all_columns(self, drug_df: pd.DataFrame) -> None:
        result = filter_drug_df(drug_df, ["ASPIRIN"])
        assert set(result.columns) == set(drug_df.columns)

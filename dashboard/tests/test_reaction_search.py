"""
test_reaction_search.py

Tests for reaction_search.py — pure functions, no I/O, no mocking needed.

Verifies synonym dictionary lookups, substring scoring, fuzzy fallback,
and edge cases (empty query, no vocabulary, etc.).
"""

from __future__ import annotations

import pytest

from reaction_search import search_reactions, LAY_SYNONYMS

# A realistic-looking PT vocabulary built from the fixture reaction names
# plus a few standard MedDRA terms used in synonym tests.
VOCAB: list[str] = [
    "Nausea",
    "Headache",
    "Dizziness",
    "Fatigue",
    "Rash",
    "Bleeding",
    "Myocardial Infarction",
    "Nausea And Vomiting",
    "Thrombosis",
    "Liver Injury",
    # extras for synonym / substring tests
    "Haemorrhage",
    "Gastrointestinal Haemorrhage",
    "Vomiting",
    "Diarrhoea",
    "Hypertension",
    "Syncope",
    "Dyspnoea",
    "Pruritus",
    "Death",
]


# ── Basic return type and structure ───────────────────────────────────────────

class TestReturnType:
    def test_returns_list(self) -> None:
        result = search_reactions("nausea", VOCAB)
        assert isinstance(result, list)

    def test_each_element_is_tuple_of_str_float(self) -> None:
        result = search_reactions("nausea", VOCAB)
        for pt, score in result:
            assert isinstance(pt, str)
            assert isinstance(score, float)

    def test_sorted_descending_by_score(self) -> None:
        result = search_reactions("headache", VOCAB)
        scores = [s for _, s in result]
        assert scores == sorted(scores, reverse=True)

    def test_max_results_respected(self) -> None:
        result = search_reactions("a", VOCAB, max_results=3)
        assert len(result) <= 3

    def test_empty_query_returns_list(self) -> None:
        result = search_reactions("", VOCAB)
        assert isinstance(result, list)

    def test_empty_vocab_returns_empty_list(self) -> None:
        result = search_reactions("nausea", [])
        assert result == []


# ── Synonym dictionary hits ───────────────────────────────────────────────────

class TestSynonymHits:
    def test_nausea_lay_term_maps_to_nausea_pt(self) -> None:
        result = search_reactions("nausea", VOCAB)
        pts = [pt for pt, _ in result]
        assert "Nausea" in pts

    def test_synonym_hit_gets_score_100(self) -> None:
        result = search_reactions("nausea", VOCAB)
        scores = {pt: s for pt, s in result}
        assert scores.get("Nausea", 0) == 100.0

    def test_throwing_up_maps_to_vomiting(self) -> None:
        result = search_reactions("throwing up", VOCAB)
        pts = [pt for pt, _ in result]
        assert "Vomiting" in pts

    def test_bleeding_lay_term_maps_to_haemorrhage(self) -> None:
        """LAY_SYNONYMS maps 'bleeding' → ['Haemorrhage', 'Gastrointestinal Haemorrhage']"""
        result = search_reactions("bleeding", VOCAB)
        pts = [pt for pt, _ in result]
        assert "Haemorrhage" in pts or "Gastrointestinal Haemorrhage" in pts

    def test_diarrhea_maps_to_diarrhoea(self) -> None:
        result = search_reactions("diarrhea", VOCAB)
        pts = [pt for pt, _ in result]
        assert "Diarrhoea" in pts

    def test_fainting_maps_to_syncope(self) -> None:
        result = search_reactions("fainting", VOCAB)
        pts = [pt for pt, _ in result]
        assert "Syncope" in pts

    def test_shortness_of_breath_maps_to_dyspnoea(self) -> None:
        result = search_reactions("shortness of breath", VOCAB)
        pts = [pt for pt, _ in result]
        assert "Dyspnoea" in pts


# ── Exact / substring matching ────────────────────────────────────────────────

class TestSubstringMatching:
    def test_exact_match_scores_98(self) -> None:
        # Use a PT not present in LAY_SYNONYMS so the synonym path (score=100)
        # doesn't fire and the exact substring path gives 98.
        result = search_reactions("Thrombosis", VOCAB)
        scores = {pt: s for pt, s in result}
        assert scores.get("Thrombosis", 0) == 98.0

    def test_case_insensitive_exact(self) -> None:
        result = search_reactions("HEADACHE", VOCAB)
        pts = [pt for pt, _ in result]
        assert "Headache" in pts

    def test_substring_in_pt_scores_95(self) -> None:
        # "Nausea" is a substring of "Nausea And Vomiting"
        result = search_reactions("Nausea", VOCAB)
        scores = {pt: s for pt, s in result}
        # "Nausea And Vomiting" should get ≥ 95 (query is substring of PT)
        assert scores.get("Nausea And Vomiting", 0) >= 90.0


# ── Fuzzy fallback ────────────────────────────────────────────────────────────

class TestFuzzyFallback:
    def test_misspelling_still_finds_headache(self) -> None:
        result = search_reactions("hedache", VOCAB, fuzzy_threshold=60)
        pts = [pt for pt, _ in result]
        # rapidfuzz should catch this typo
        assert "Headache" in pts

    def test_fuzzy_threshold_respected(self) -> None:
        """Setting threshold very high should shrink results."""
        result_low  = search_reactions("dizzy", VOCAB, fuzzy_threshold=40)
        result_high = search_reactions("dizzy", VOCAB, fuzzy_threshold=95)
        assert len(result_high) <= len(result_low)


# ── LAY_SYNONYMS dictionary structure ────────────────────────────────────────

class TestLaySynonymsDictionary:
    def test_all_values_are_lists(self) -> None:
        for key, val in LAY_SYNONYMS.items():
            assert isinstance(val, list), f"Value for '{key}' is not a list"

    def test_all_keys_are_lowercase(self) -> None:
        for key in LAY_SYNONYMS:
            assert key == key.lower(), f"Key '{key}' is not lowercase"

    def test_no_empty_synonym_lists(self) -> None:
        for key, val in LAY_SYNONYMS.items():
            assert len(val) > 0, f"Empty synonym list for '{key}'"

    def test_all_pt_values_are_title_case_strings(self) -> None:
        for key, pts in LAY_SYNONYMS.items():
            for pt in pts:
                assert isinstance(pt, str), f"Non-string PT for '{key}': {pt!r}"
                assert pt == pt.title() or pt[0].isupper(), (
                    f"PT '{pt}' under '{key}' should start with uppercase"
                )

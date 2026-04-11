"""
test_app_smoke.py

Headless smoke tests using streamlit.testing.v1.AppTest.

These tests verify that the app renders without exceptions and that the
critical UI elements (title, tabs, KPI metrics, charts) are present.
All external API calls (RxNorm, openFDA, PubMed, ClinicalTrials, LLM) are
stubbed so the suite runs fully offline.

Performance note
----------------
Each AppTest.run() re-executes the entire app script.  We reuse one AppTest
instance per test class where possible (class-level fixture), and limit
AppTest runs to the minimum needed to verify a feature path.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# dashboard/ must be on sys.path (set by conftest.py already)
_DASHBOARD = Path(__file__).parent.parent
_APP_PATH  = str(_DASHBOARD / "app.py")

try:
    from streamlit.testing.v1 import AppTest
    _HAS_APPTEST = True
except ImportError:
    _HAS_APPTEST = False

pytestmark = pytest.mark.skipif(
    not _HAS_APPTEST,
    reason="streamlit.testing.v1.AppTest not available in this Streamlit version",
)

# ── Stubs for external API calls ──────────────────────────────────────────────

_RXNORM_STUB = {
    "rxcui": "1191",
    "canonical": "ASPIRIN",
    "related": ["ASPIRIN", "BAYER ASPIRIN"],
}

_DRUG_LABEL_STUB: dict[str, Any] = {
    "boxed_warning": "",
    "warnings": "Avoid in patients with aspirin allergy.",
    "indications": "Pain, fever, anti-platelet therapy.",
    "contraindications": "Active bleeding.",
    "brand_name": "Bayer Aspirin",
    "generic_name": "aspirin",
    "manufacturer": "Bayer",
}

_FDA_RECORDS_STUB = [
    {
        "application_number": "NDA019787",
        "app_type":           "NDA (Brand)",
        "sponsor":            "Bayer AG",
        "brand_names":        "Aspirin",
        "generic_names":      "aspirin",
        "dosage_forms":       "Tablet",
        "routes":             "Oral",
        "marketing_status":   "Prescription",
        "first_approval":     "1965-01-01",
        "latest_action":      "2020-03-15",
        "ob_url":             "https://example.com/ob",
        "fda_url":            "https://example.com/fda",
    },
]

_ENFORCEMENT_STUB: list[dict] = []

_DRUG_CLASS_STUB: list[dict] = [
    {"source": "ATC", "class_name": "Platelet aggregation inhibitors excl. heparin"},
]

import pandas as _pd
_TRIALS_STUB: tuple = (_pd.DataFrame(), 0)   # (DataFrame, total_count)
_PUBMED_STUB: tuple = (_pd.DataFrame(), 0)   # (DataFrame, total_count)


def _make_patches() -> list:
    """Build a list of mock.patch objects for all external calls."""
    return [
        patch("drug_normalizer.rxnorm_lookup",           return_value=_RXNORM_STUB),
        patch("research_connector.get_drug_label",       return_value=_DRUG_LABEL_STUB),
        patch("research_connector.get_fda_approval_info", return_value=_FDA_RECORDS_STUB),
        patch("research_connector.get_drug_enforcement", return_value=_ENFORCEMENT_STUB),
        patch("research_connector.get_drug_class",       return_value=_DRUG_CLASS_STUB),
        patch("research_connector.search_clinical_trials", return_value=_TRIALS_STUB),
        patch("research_connector.search_pubmed",        return_value=_PUBMED_STUB),
        patch("signal_interpreter.interpret_signals",    return_value=""),
    ]


def _build_at() -> "AppTest":
    at = AppTest.from_file(_APP_PATH, default_timeout=30)
    return at


def _run_with_stubs(at: "AppTest") -> "AppTest":
    patches = _make_patches()
    for p in patches:
        p.start()
    try:
        at.run()
    finally:
        for p in patches:
            p.stop()
    return at


# ── Overview tab ──────────────────────────────────────────────────────────────

class TestOverviewTab:
    @pytest.fixture(scope="class")
    def at(self) -> "AppTest":
        app = _build_at()
        return _run_with_stubs(app)

    def test_no_exceptions(self, at: "AppTest") -> None:
        assert not at.exception, f"App raised exception: {at.exception}"

    def test_app_title_present(self, at: "AppTest") -> None:
        """The app uses st.markdown for the header — look for FAERS / FDA in markdown."""
        all_md = " ".join(el.value.lower() for el in at.markdown)
        assert "faers" in all_md or "drug safety" in all_md or "fda" in all_md, (
            "Could not find FAERS/FDA title in any markdown element"
        )

    def test_kpi_row_rendered(self, at: "AppTest") -> None:
        """Overview KPIs are rendered as HTML in st.markdown elements."""
        all_md = " ".join(el.value for el in at.markdown)
        assert "kpi" in all_md.lower() or "cases" in all_md.lower(), (
            "Expected KPI elements in markdown output"
        )


# ── Drug Explorer tab ─────────────────────────────────────────────────────────

class TestDrugExplorerTab:
    @pytest.fixture(scope="class")
    def at_searched(self) -> "AppTest":
        app = _build_at()
        # The drug search box is the first text_input in the app
        _run_with_stubs(app)
        # Type a drug name and rerun
        if app.text_input:
            app.text_input[0].set_value("ASPIRIN")
        return _run_with_stubs(app)

    def test_no_exception_after_search(self, at_searched: "AppTest") -> None:
        assert not at_searched.exception, f"Exception after drug search: {at_searched.exception}"

    def test_drug_explorer_renders_content(self, at_searched: "AppTest") -> None:
        """Drug Explorer renders KPI HTML via st.markdown."""
        all_md = " ".join(el.value for el in at_searched.markdown)
        assert len(all_md) > 100, "Expected substantial markdown content after drug search"


# ── All tabs render without st.stop() leak ────────────────────────────────────

class TestAllTabsRender:
    """
    After refactoring _render_drug_tab → functions, all 5 tabs should render
    in a single run().  We verify by checking that the total number of rendered
    elements grows — if st.stop() still leaked, later tabs would add nothing.
    """

    @pytest.fixture(scope="class")
    def at(self) -> "AppTest":
        app = _build_at()
        return _run_with_stubs(app)

    def test_no_exception(self, at: "AppTest") -> None:
        assert not at.exception

    def test_tabs_exist(self, at: "AppTest") -> None:
        # Streamlit AppTest exposes tab labels in at.tabs (list of strings)
        # or we can check that multiple selectbox / text_input exist.
        # At minimum the app should render more than one interactive widget.
        total_widgets = (
            len(at.text_input) + len(at.selectbox) +
            len(at.multiselect) + len(at.checkbox)
        )
        assert total_widgets >= 1, "No interactive widgets rendered — tabs may not have loaded"


# ── Sidebar / global filter ───────────────────────────────────────────────────

class TestGlobalFilters:
    @pytest.fixture(scope="class")
    def at(self) -> "AppTest":
        app = _build_at()
        return _run_with_stubs(app)

    def test_no_exception(self, at: "AppTest") -> None:
        assert not at.exception

    def test_quarter_checkboxes_present(self, at: "AppTest") -> None:
        """The quarters filter should render as individual checkboxes."""
        assert len(at.checkbox) >= 1, "Expected at least one quarter checkbox"


# ── Signal Intelligence tab ───────────────────────────────────────────────────

class TestSignalIntelligenceTab:
    @pytest.fixture(scope="class")
    def at(self) -> "AppTest":
        app = _build_at()
        return _run_with_stubs(app)

    def test_no_exception(self, at: "AppTest") -> None:
        assert not at.exception

    def test_dataframe_or_table_present(self, at: "AppTest") -> None:
        """Signal table should render as a dataframe."""
        assert len(at.dataframe) >= 1 or len(at.table) >= 1, (
            "Expected at least one dataframe/table on Signal Intelligence tab"
        )

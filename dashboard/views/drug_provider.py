from __future__ import annotations

import streamlit as st

from dashboard import charts
from dashboard.logging_utils import get_logger


logger = get_logger(__name__)


def render(bundle: dict, top_n: int) -> None:
    logger.info(
        "Provider view render: cases=%s top_n=%s", len(bundle.get("cases", [])), top_n
    )
    st.markdown("#### Active Ingredients")
    st.dataframe(bundle["ingredients"], width="stretch", hide_index=True)

    st.markdown("#### Clinical Counts")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["role_counts"],
                "n_cases",
                "role_cod",
                f"Role code distribution (top {top_n})",
            ),
            width="stretch",
            key="drug_provider_role_counts",
        )
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["dose_form_counts"],
                "n_cases",
                "dose_form",
                f"Dosage form distribution (top {top_n})",
            ),
            width="stretch",
            key="drug_provider_dose_form_counts",
        )
    with c2:
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["route_counts"],
                "n_cases",
                "route",
                f"Administration route distribution (top {top_n})",
            ),
            width="stretch",
            key="drug_provider_route_counts",
        )
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["dose_freq_counts"],
                "n_cases",
                "dose_freq",
                f"Dose frequency distribution (top {top_n})",
            ),
            width="stretch",
            key="drug_provider_dose_freq_counts",
        )
    with c3:
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["dose_counts"],
                "n_cases",
                "dose",
                f"Dose distribution (top {top_n})",
            ),
            width="stretch",
            key="drug_provider_dose_counts",
        )
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["reactions"],
                "n_cases",
                "pt",
                f"Top reactions (top {top_n})",
            ),
            width="stretch",
            key="drug_provider_reaction_counts",
        )

    o1, o2 = st.columns(2)
    with o1:
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["outcomes"], "n_cases", "outc_cod", "Outcome distribution"
            ),
            width="stretch",
            key="drug_provider_outcomes",
        )
    with o2:
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["indications"], "n_cases", "indi_pt", "Top indications"
            ),
            width="stretch",
            key="drug_provider_indications",
        )

    st.markdown("#### Case Table")
    only_lit = st.toggle(
        "Only cases with literature reference", value=False, key="provider_only_lit"
    )
    cases = bundle["cases"]
    if only_lit and not cases.empty and "lit_ref" in cases.columns:
        cases = cases[cases["lit_ref"].astype(str).str.strip() != ""]

    page = st.number_input("Page", min_value=1, value=1, step=1, key="provider_page")
    start = (page - 1) * 100
    st.dataframe(cases.iloc[start : start + 100], width="stretch", hide_index=True)

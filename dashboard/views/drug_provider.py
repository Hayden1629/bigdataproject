from __future__ import annotations

import streamlit as st

from dashboard import charts
from dashboard.logging_utils import get_logger
from dashboard.ui import render_section_intro, render_table


logger = get_logger(__name__)


def render(bundle: dict, top_n: int) -> None:
    logger.info(
        "Provider view render: cases=%s top_n=%s", len(bundle.get("cases", [])), top_n
    )
    render_section_intro("Provider view")

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

    render_table(bundle["ingredients"], height=280)

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
            bundle["dose_form_counts"],
            "n_cases",
            "dose_form",
            f"Dosage form distribution (top {top_n})",
        ),
        width="stretch",
        key="drug_provider_dose_form_counts",
    )
    f1, f2 = st.columns(2)
    with f1:
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
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["outcomes"], "n_cases", "outc_cod", "Outcome distribution"
            ),
            width="stretch",
            key="drug_provider_outcomes",
        )
        st.caption(
            "DE = Death · LT = Life-Threatening · HO = Hospitalization · "
            "DS = Disability · CA = Congenital Anomaly · RI = Required Intervention · "
            "OT = Other Serious"
        )
    with f2:
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["dose_counts"],
                "n_cases",
                "dose",
                f"Dose amount (top {top_n})",
            ),
            width="stretch",
            key="drug_provider_dose_counts",
        )
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["indications"], "n_cases", "indi_pt", "Top indications"
            ),
            width="stretch",
            key="drug_provider_indications",
        )

    render_section_intro("Cases")
    cases = bundle["cases"]
    if not cases.empty and "lit_ref" in cases.columns:
        cases = cases.drop(columns=["lit_ref"])

    page = st.number_input("Page", min_value=1, value=1, step=1, key="provider_page")
    start = (int(page) - 1) * 100
    render_table(cases.iloc[start : start + 100], height=430)

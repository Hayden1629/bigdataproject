from __future__ import annotations

import streamlit as st

from dashboard import charts
from dashboard.logging_utils import get_logger


logger = get_logger(__name__)


def render(bundle: dict, top_n: int) -> None:
    logger.info(
        "Drug manufacturer view render: cases=%s top_n=%s",
        len(bundle.get("cases", [])),
        top_n,
    )
    st.markdown("#### Active Ingredients")
    st.dataframe(bundle["ingredients"], width="stretch", hide_index=True)

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["manufacturer_counts"],
                "n_cases",
                "manufacturer",
                f"Top manufacturers (top {top_n})",
            ),
            width="stretch",
            key="drug_mfr_manufacturer_counts",
        )
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["outcome_counts"],
                "n_cases",
                "outc_cod",
                f"Outcome distribution (top {top_n})",
            ),
            width="stretch",
            key="drug_mfr_outcome_counts",
        )
    with c2:
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["country_counts"],
                "n_cases",
                "country",
                f"Top reporting countries (top {top_n})",
            ),
            width="stretch",
            key="drug_mfr_country_counts",
        )
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["dose_form_counts"],
                "n_cases",
                "dose_form",
                f"Dosage form distribution (top {top_n})",
            ),
            width="stretch",
            key="drug_mfr_dose_form_counts",
        )

    st.markdown("#### Case Table")
    page = st.number_input("Page", min_value=1, value=1, step=1, key="drug_mfr_page")
    start = (page - 1) * 100
    st.dataframe(
        bundle["cases"].iloc[start : start + 100],
        width="stretch",
        hide_index=True,
    )

    st.markdown("#### Case reports by quarter")
    st.plotly_chart(
        charts.line_chart(
            bundle["quarterly_trend"], "year_q", "n_cases", "Case reports by quarter"
        ),
        width="stretch",
        key="drug_mfr_quarterly_trend",
    )

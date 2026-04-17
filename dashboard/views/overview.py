from __future__ import annotations

import streamlit as st

from dashboard import charts, queries
from dashboard.logging_utils import get_logger
from dashboard.ui import metric_card


logger = get_logger(__name__)


def render(filters: dict) -> None:
    quarters = tuple(filters["quarters"])
    role_filter = filters["role_filter"]

    kpi = queries.global_kpis(quarters, role_filter)
    logger.info(
        "Overview render: quarters=%s role=%s cases=%s",
        len(quarters),
        role_filter,
        kpi["cases"],
    )

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        metric_card("Total Cases", f"{kpi['cases']:,}")
    with c2:
        metric_card("Deaths", f"{kpi['deaths']:,}", f"{kpi['death_pct']:.1f}%")
    with c3:
        metric_card("Hospitalisations", f"{kpi['hospitalisations']:,}")
    with c4:
        metric_card("Life-threatening", f"{kpi['life_threatening']:,}")
    with c5:
        metric_card("Unique Drug Entities", f"{kpi['unique_drugs']:,}")
    with c6:
        metric_card("Unique MedDRA PTs", f"{kpi['unique_reactions']:,}")

    st.markdown("### Top drugs and reactions")
    left, right = st.columns(2)
    top_drugs = queries.load_drug_summary().head(15)
    top_reac = queries.load_reac_summary().head(15)
    with left:
        st.plotly_chart(
            charts.bar_horizontal(
                top_drugs, "n_cases", "drugname", "Top 15 drugs by case reports"
            ),
            width="stretch",
            key="overview_top_drugs",
        )
    with right:
        st.plotly_chart(
            charts.bar_horizontal(
                top_reac, "n_cases", "pt", "Top 15 reactions by case reports"
            ),
            width="stretch",
            key="overview_top_reactions",
        )

    st.markdown("### Quarter-over-quarter movers")
    d1, d2 = st.columns(2)
    td = queries.trending_drugs(top_n=10)
    tr = queries.trending_reactions(top_n=10)
    with d1:
        st.plotly_chart(
            charts.bar_horizontal(
                td,
                "delta",
                "drugname",
                "Top 10 drug quarter-over-quarter increases",
            ),
            width="stretch",
            key="overview_qoq_drugs",
        )
    with d2:
        st.plotly_chart(
            charts.bar_horizontal(
                tr,
                "delta",
                "pt",
                "Top 10 reaction quarter-over-quarter increases",
            ),
            width="stretch",
            key="overview_qoq_reactions",
        )

    st.markdown("### Case reports by quarter")
    trend = queries.global_quarterly_trend(quarters, role_filter)
    st.plotly_chart(
        charts.line_chart(trend, "year_q", "n_cases", "Case reports by quarter"),
        width="stretch",
        key="overview_quarterly_trend",
    )

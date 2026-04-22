from __future__ import annotations

import streamlit as st

from dashboard import charts, queries
from dashboard.data_loader import load_manufacturer_lookup
from dashboard.logging_utils import get_logger
from dashboard.manufacturer_normalizer import match_manufacturer_names
from dashboard.ui import (
    format_compact,
    metric_card,
    render_helper_text,
    render_section_intro,
    render_table,
)


logger = get_logger(__name__)


def _empty_state() -> None:
    summary = queries.load_manufacturer_summary().copy()
    if "canonical_mfr" in summary.columns:
        summary = summary.rename(columns={"canonical_mfr": "manufacturer"})
    summary = summary.sort_values("n_cases", ascending=False).reset_index(drop=True)
    render_table(summary.head(50), height=520)


def render(filters: dict) -> None:
    render_section_intro("Manufacturer lookup")
    q = st.text_input("Search manufacturer", placeholder="e.g., Pfizer")
    render_helper_text("Try examples: Pfizer, Moderna, Johnson & Johnson")
    if not q.strip():
        _empty_state()
        return

    logger.info("Manufacturer search submitted: query=%s", q)

    lookup = load_manufacturer_lookup()
    matched = match_manufacturer_names(q, lookup)
    canons = matched["canonical"]
    if not canons:
        logger.info("Manufacturer search no match: query=%s", q)
        st.warning("No matching manufacturer found.")
        return

    bundle = queries.manufacturer_query_bundle(
        tuple(canons),
        filters["top_n"],
        filters["role_filter"],
        tuple(filters["quarters"]),
    )

    logger.info(
        "Manufacturer search matched: query=%s canonical=%s raw_strings=%s",
        q,
        canons,
        len(matched["raw_strings"]),
    )

    kpi = bundle["kpi"]
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Total Cases", format_compact(kpi["cases"]))
    with c2:
        metric_card("Deaths", format_compact(kpi["deaths"]), f"{kpi['death_pct']:.1f}%")
    with c3:
        metric_card("Unique Drugs", format_compact(kpi.get("unique_drugs", 0)))
    with c4:
        metric_card("Countries", format_compact(kpi.get("countries", 0)))

    st.markdown("#### Top drugs")
    st.plotly_chart(
        charts.bar_horizontal(bundle["drug_counts"], "n_cases", "drugname"),
        width="stretch",
        key="mfr_lookup_drug_counts",
    )
    st.markdown("#### Case reports by quarter")
    st.plotly_chart(
        charts.line_chart(
            bundle["quarterly_trend"], "year_q", "n_cases"
        ),
        width="stretch",
        key="mfr_lookup_quarterly_trend",
    )
    st.markdown("#### Top active ingredients")
    st.plotly_chart(
        charts.bar_horizontal(
            bundle["ingredient_counts"],
            "n_cases",
            "ingredient",
        ),
        width="stretch",
        key="mfr_lookup_ingredient_counts",
    )
    st.markdown("#### Outcome distribution")
    st.plotly_chart(
        charts.bar_horizontal(
            bundle["outcome_counts"], "n_cases", "outc_cod"
        ),
        width="stretch",
        key="mfr_lookup_outcome_counts",
    )
    st.caption(
        "DE = Death · LT = Life-Threatening · HO = Hospitalization · "
        "DS = Disability · CA = Congenital Anomaly · RI = Required Intervention · "
        "OT = Other Serious"
    )
    st.markdown("#### Top reporting countries")
    st.plotly_chart(
        charts.bar_horizontal(
            bundle["country_counts"],
            "n_cases",
            "country",
        ),
        width="stretch",
        key="mfr_lookup_country_counts",
    )
    st.markdown("#### Top indications")
    st.plotly_chart(
        charts.bar_horizontal(
            bundle["indication_counts"], "n_cases", "indi_pt"
        ),
        width="stretch",
        key="mfr_lookup_indication_counts",
    )

    render_section_intro("Cases")
    page = st.number_input("Page", min_value=1, value=1, step=1, key="mfr_lookup_page")
    start = (int(page) - 1) * 100
    render_table(bundle["cases"].iloc[start : start + 100], height=430)

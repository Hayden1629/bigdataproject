from __future__ import annotations

import streamlit as st

from dashboard import charts, queries
from dashboard.data_loader import load_manufacturer_lookup
from dashboard.logging_utils import get_logger
from dashboard.manufacturer_normalizer import match_manufacturer_names
from dashboard.ui import metric_card


logger = get_logger(__name__)


def _empty_state() -> None:
    st.info("Try: Pfizer, Moderna, Johnson & Johnson")
    st.markdown("#### Most reported manufacturers")
    summary = queries.load_manufacturer_summary().copy()
    if "canonical_mfr" in summary.columns:
        summary = summary.rename(columns={"canonical_mfr": "manufacturer"})
    summary = summary.sort_values("n_cases", ascending=False).reset_index(drop=True)

    c1, c2 = st.columns([1, 2])
    with c1:
        show_all = st.toggle(
            "Show all manufacturers", value=True, key="mfr_empty_show_all"
        )
    with c2:
        max_rows = st.slider(
            "Rows to display",
            min_value=50,
            max_value=max(50, int(len(summary))),
            value=max(50, int(len(summary)))
            if show_all
            else min(300, max(50, int(len(summary)))),
            step=50,
            key="mfr_empty_rows",
        )

    shown = summary if show_all else summary.head(max_rows)
    st.caption(f"Showing {len(shown):,} of {len(summary):,} manufacturers")
    st.dataframe(shown, width="stretch", hide_index=True)


def render(filters: dict) -> None:
    st.markdown("### Manufacturer lookup")
    q = st.text_input("Search manufacturer", placeholder="e.g., Pfizer")
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

    st.markdown(
        f"**Canonical matches:** {', '.join(canons)}  \\\n+Matched raw manufacturer strings: {len(matched['raw_strings'])}"
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
        metric_card("Total Cases", f"{kpi['cases']:,}")
    with c2:
        metric_card("Deaths", f"{kpi['deaths']:,}", f"{kpi['death_pct']:.1f}%")
    with c3:
        metric_card("Unique Drugs", f"{kpi.get('unique_drugs', 0):,}")
    with c4:
        metric_card("Countries", f"{kpi.get('countries', 0):,}")

    a, b = st.columns(2)
    with a:
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["drug_counts"], "n_cases", "drugname", "Top drugs"
            ),
            width="stretch",
            key="mfr_lookup_drug_counts",
        )
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["outcome_counts"], "n_cases", "outc_cod", "Outcome distribution"
            ),
            width="stretch",
            key="mfr_lookup_outcome_counts",
        )
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["country_counts"],
                "n_cases",
                "country",
                "Top reporting countries",
            ),
            width="stretch",
            key="mfr_lookup_country_counts",
        )
    with b:
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["ingredient_counts"],
                "n_cases",
                "ingredient",
                "Top active ingredients",
            ),
            width="stretch",
            key="mfr_lookup_ingredient_counts",
        )
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["indication_counts"], "n_cases", "indi_pt", "Top indications"
            ),
            width="stretch",
            key="mfr_lookup_indication_counts",
        )

    st.markdown("#### Cases")
    page = st.number_input("Page", min_value=1, value=1, step=1, key="mfr_lookup_page")
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
        key="mfr_lookup_quarterly_trend",
    )

    with st.expander("Matched manufacturer strings"):
        st.dataframe(
            {"mfr_sndr": matched["raw_strings"]},
            width="stretch",
            hide_index=True,
        )

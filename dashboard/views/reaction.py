from __future__ import annotations

import streamlit as st

from dashboard import charts, queries
from dashboard.data_loader import get_all_reaction_terms
from dashboard.logging_utils import get_logger
from dashboard.reaction_search import find_reaction_terms
from dashboard.ui import metric_card


logger = get_logger(__name__)


def _empty_state() -> None:
    st.info("Try symptoms like 'heart attack', 'stroke', 'vomiting', 'rash'.")
    st.markdown("#### Most reported adverse reactions")
    st.dataframe(queries.load_reac_summary().head(20), width="stretch", hide_index=True)


def render(filters: dict) -> None:
    st.markdown("### Reaction Explorer")
    q = st.text_input("Search symptom/reaction", placeholder="e.g., heart attack")
    if not q.strip():
        _empty_state()
        return
    logger.info("Reaction search submitted: query=%s", q)

    all_terms = get_all_reaction_terms()
    matches = find_reaction_terms(q, all_terms, limit=20)
    if not matches:
        logger.info("Reaction search no match: query=%s", q)
        st.warning("No matching MedDRA terms found.")
        return

    scored = matches[:10]
    default_terms = [m["term"] for m in scored[:3]]
    selected = st.multiselect(
        "Select MedDRA PT terms",
        options=[m["term"] for m in matches],
        default=default_terms,
    )
    if not selected:
        st.warning("Select at least one term to continue.")
        return
    logger.info("Reaction terms selected: query=%s terms=%s", q, selected)

    left, right = st.columns([2, 1])
    with right:
        st.markdown("#### Match Scores")
        st.dataframe(scored, width="stretch", hide_index=True)

    terms = tuple(selected)
    quarters = tuple(filters["quarters"])
    role = filters["role_filter"]
    top_n = filters["top_n"]

    kpi = queries.reaction_kpis(terms, quarters, role)
    with left:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            metric_card("Cases Reporting", f"{kpi['cases']:,}")
        with c2:
            metric_card("Deaths", f"{kpi['deaths']:,}", f"{kpi['death_pct']:.1f}%")
        with c3:
            metric_card("Any Serious Outcome", f"{kpi['serious']:,}")
        with c4:
            metric_card("Selected Terms", f"{kpi['n_terms']:,}")

        top_drugs = queries.reaction_top_drugs(terms, top_n, quarters, role)
        outcomes = queries.reaction_outcomes(terms, top_n, quarters, role)
        trend = queries.reaction_trend(terms, quarters, role)

        if not top_drugs.empty:
            lead = top_drugs.iloc[0]
            st.info(
                f"At a glance: top associated drug is **{lead['drugname']}** with **{int(lead['n_cases']):,}** cases."
            )

        a, b = st.columns(2)
        with a:
            st.plotly_chart(
                charts.bar_horizontal(
                    top_drugs, "n_cases", "drugname", "Top associated drugs"
                ),
                width="stretch",
                key="reaction_top_drugs",
            )
        with b:
            st.plotly_chart(
                charts.donut(outcomes, "outc_cod", "n_cases", "Outcome distribution"),
                width="stretch",
                key="reaction_outcomes",
            )

        st.plotly_chart(
            charts.line_chart(trend, "year_q", "n_cases", "Case reports by quarter"),
            width="stretch",
            key="reaction_quarterly_trend",
        )

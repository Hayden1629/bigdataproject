from __future__ import annotations

import streamlit as st

from dashboard import charts, queries
from dashboard.data_loader import get_all_reaction_terms
from dashboard.logging_utils import get_logger
from dashboard.reaction_search import find_reaction_terms
from dashboard.ui import (
    format_compact,
    metric_card,
    render_helper_text,
    render_section_intro,
    render_table,
)


logger = get_logger(__name__)


def _empty_state() -> None:
    render_table(queries.load_reac_summary().head(20), height=420)


def render(filters: dict) -> None:
    render_section_intro("Reaction explorer")
    q = st.text_input("Search symptom/reaction", placeholder="e.g., heart attack")
    render_helper_text("Try symptoms like heart attack, stroke, vomiting, or rash")
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
    default_terms = [m["term"] for m in matches if m["score"] >= 80]
    selected = st.multiselect(
        "Select MedDRA PT terms",
        options=[m["term"] for m in matches],
        default=default_terms if default_terms else [matches[0]["term"]],
    )
    if not selected:
        st.warning("Select at least one term to continue.")
        return
    logger.info("Reaction terms selected: query=%s terms=%s", q, selected)

    terms = tuple(selected)
    quarters = tuple(filters["quarters"])
    role = filters["role_filter"]
    top_n = int(filters["top_n"])

    top_drugs = queries.reaction_top_drugs(terms, min(top_n, 10), quarters, role).head(10)
    outcomes = queries.reaction_outcomes(terms, top_n, quarters, role)
    trend = queries.reaction_trend(terms, quarters, role)
    kpi = queries.reaction_kpis(terms, quarters, role)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Cases Reporting", format_compact(kpi["cases"]))
    with c2:
        metric_card("Deaths", format_compact(kpi["deaths"]), f"{kpi['death_pct']:.1f}%")
    with c3:
        metric_card("Any Serious Outcome", format_compact(kpi["serious"]))
    with c4:
        metric_card("Selected Terms", format_compact(kpi["n_terms"]))

    left, right = st.columns([1, 1])
    with left:
        st.plotly_chart(
            charts.bar_horizontal(top_drugs, "n_cases", "drugname", "Top associated drugs"),
            width="stretch",
            key="reaction_top_drugs",
        )
    with right:
        render_table(scored, height=430)

    st.plotly_chart(
        charts.donut(outcomes, "outc_cod", "n_cases", "Outcome distribution"),
        width="stretch",
        key="reaction_outcomes",
    )
    st.caption(
        "DE = Death · LT = Life-Threatening · HO = Hospitalization · "
        "DS = Disability · CA = Congenital Anomaly · RI = Required Intervention · "
        "OT = Other Serious"
    )
    st.plotly_chart(
        charts.line_chart(trend, "year_q", "n_cases", "Case reports by quarter"),
        width="stretch",
        key="reaction_quarterly_trend",
    )

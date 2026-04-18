from __future__ import annotations

import html

import streamlit as st

from dashboard import charts, queries
from dashboard.logging_utils import get_logger
from dashboard.ui import format_compact, render_section_intro


logger = get_logger(__name__)


def _kpi_strip_html(kpi: dict, quarters: tuple[str, ...]) -> str:
    q_sorted = sorted(quarters) if quarters else []
    if len(q_sorted) >= 2:
        q_span = f"{q_sorted[0]} - {q_sorted[-1]}"
    elif len(q_sorted) == 1:
        q_span = q_sorted[0]
    else:
        q_span = "All quarters"

    nq = len(q_sorted)
    cases = max(int(kpi["cases"]), 1)
    hosp_pct = int(kpi["hospitalisations"]) / cases * 100.0
    lt_pct = int(kpi["life_threatening"]) / cases * 100.0

    parts = [
        (
            "Total cases",
            format_compact(int(kpi["cases"])),
            "faers-kpi-t-blue",
            "faers-kpi-v-blue",
            f"{html.escape(q_span)} | {nq or 'All'} quarter{'s' if nq not in (0, 1) else ''}",
        ),
        (
            "Deaths",
            format_compact(int(kpi["deaths"])),
            "faers-kpi-t-red",
            "faers-kpi-v-red",
            f"{kpi['death_pct']:.1f}% fatality rate",
        ),
        (
            "Hospitalisations",
            format_compact(int(kpi["hospitalisations"])),
            "faers-kpi-t-amber",
            "faers-kpi-v-amber",
            f"{hosp_pct:.1f}% of cases",
        ),
        (
            "Life-threatening",
            format_compact(int(kpi["life_threatening"])),
            "faers-kpi-t-amber",
            "faers-kpi-v-amber",
            f"{lt_pct:.1f}% of cases",
        ),
        (
            "Unique drug entities",
            format_compact(int(kpi["unique_drugs"])),
            "faers-kpi-t-teal",
            "faers-kpi-v-teal",
            "Distinct drug names",
        ),
        (
            "Unique MedDRA PTs",
            format_compact(int(kpi["unique_reactions"])),
            "faers-kpi-t-teal",
            "faers-kpi-v-teal",
            "Preferred terms",
        ),
    ]

    return "".join(
        (
            f'<div class="faers-kpi-card {tone_cls}">'
            f'<div class="faers-kpi-lbl">{html.escape(lbl)}</div>'
            f'<div class="faers-kpi-val {value_cls}">{html.escape(val)}</div>'
            f'<div class="faers-kpi-sub">{html.escape(sub)}</div>'
            "</div>"
        )
        for lbl, val, tone_cls, value_cls, sub in parts
    )


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

    top_drugs = queries.load_drug_summary().head(10)
    top_reac = queries.load_reac_summary().head(10)
    trend = queries.global_quarterly_trend(quarters, role_filter)
    td = queries.trending_drugs(top_n=10)
    tr = queries.trending_reactions(top_n=10)

    render_section_intro("Executive overview")
    st.markdown(
        f'<div class="faers-kpi-strip">{_kpi_strip_html(kpi, quarters)}</div>',
        unsafe_allow_html=True,
    )

    render_section_intro("Top drugs")
    with st.container(border=True):
        st.markdown(
            "<p class='faers-o-card-title'>Top 10 drugs by case reports</p>",
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            charts.bar_horizontal(
                top_drugs,
                "n_cases",
                "drugname",
                "Top 10 drugs by case reports",
                overview_palette="drugs",
            ),
            use_container_width=True,
            key="overview_top_drugs",
        )

    render_section_intro("Top reactions")
    with st.container(border=True):
        st.markdown(
            "<p class='faers-o-card-title'>Top 10 reactions by case reports</p>",
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            charts.bar_horizontal(
                top_reac,
                "n_cases",
                "pt",
                "Top 10 reactions by case reports",
                overview_palette="reactions",
            ),
            use_container_width=True,
            key="overview_top_reactions",
        )

    render_section_intro("Quarter-over-quarter movers")
    d1, d2 = st.columns(2)
    with d1:
        with st.container(border=True):
            st.markdown(
                "<p class='faers-o-card-title'>Drug increases</p>",
                unsafe_allow_html=True,
            )
            st.plotly_chart(
                charts.bar_horizontal(
                    td,
                    "delta",
                    "drugname",
                    "Top 10 drug quarter-over-quarter increases",
                ),
                use_container_width=True,
                key="overview_qoq_drugs",
            )
    with d2:
        with st.container(border=True):
            st.markdown(
                "<p class='faers-o-card-title'>Reaction increases</p>",
                unsafe_allow_html=True,
            )
            st.plotly_chart(
                charts.bar_horizontal(
                    tr,
                    "delta",
                    "pt",
                    "Top 10 reaction quarter-over-quarter increases",
                ),
                use_container_width=True,
                key="overview_qoq_reactions",
            )

    render_section_intro("Case reports by quarter")
    with st.container(border=True):
        st.markdown(
            "<p class='faers-o-card-title'>Quarterly case volume trend</p>",
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            charts.line_chart(
                trend,
                "year_q",
                "n_cases",
                "Case reports by quarter",
                overview_style=True,
            ),
            use_container_width=True,
            key="overview_quarterly_trend",
        )

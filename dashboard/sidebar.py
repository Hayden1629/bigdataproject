from __future__ import annotations

from typing import Any

import streamlit as st

from dashboard import data_loader as dl
from dashboard import queries


def render_sidebar(default_top_n: int = 20) -> dict[str, Any]:
    profile = dl.get_dataset_profile()
    quarters = profile.get("quarters", [])

    with st.sidebar:
        st.markdown("### Filters")

        st.caption("Quarters")
        col_all, col_none = st.columns(2)
        with col_all:
            select_all = st.button("All", use_container_width=True, key="q_all")
        with col_none:
            select_none = st.button("None", use_container_width=True, key="q_none")

        if select_all:
            st.session_state["_q_selection"] = set(quarters)
        elif select_none:
            st.session_state["_q_selection"] = set()

        if "_q_selection" not in st.session_state:
            st.session_state["_q_selection"] = set(quarters)

        with st.container(height=200):
            for q in quarters:
                checked = st.checkbox(
                    q,
                    value=q in st.session_state["_q_selection"],
                    key=f"q_{q}",
                )
                if checked:
                    st.session_state["_q_selection"].add(q)
                else:
                    st.session_state["_q_selection"].discard(q)

        selected_quarters = sorted(st.session_state["_q_selection"])

        role_options = {
            "all": "All",
            "PS": "PS - Primary suspect",
            "SS": "SS - Secondary suspect",
            "C": "C - Concomitant"
        }
        options = list(role_options.values())
        default_index = list(role_options.keys()).index("all")
        
        selected_display = st.selectbox(
            "Drug role",
            options=options,
            index=default_index,
            help="Filter drugs by their suspected role in adverse events.",
        )
        
        # Map display back to code
        role_filter = [k for k, v in role_options.items() if v == selected_display][0]

        top_n = st.slider(
            "Chart depth",
            min_value=5,
            max_value=50,
            value=default_top_n,
            step=1,
            help="Controls how many categories appear in ranking charts.",
        )

        st.divider()
        st.markdown("### Snapshot")
        kpi = queries.global_kpis(tuple(selected_quarters), role_filter)
        st.metric("Case reports", f"{kpi['cases']:,}")
        st.metric("Deaths", f"{kpi['deaths']:,}")
        st.metric("Drugs", f"{kpi['unique_drugs']:,}")
        st.caption(f"Reaction terms: {kpi['unique_reactions']:,}")
        st.caption(f"Mode: {profile.get('mode', 'unknown')}")
        if selected_quarters:
            q_sorted = sorted(selected_quarters)
            coverage_text = f"Coverage: {q_sorted[0]} to {q_sorted[-1]}"
        else:
            coverage_text = f"Coverage: {profile.get('quarter_min', '-')} to {profile.get('quarter_max', '-')}"
        st.caption(coverage_text)

        st.divider()
        st.markdown(
            "<div style='font-size:.68rem;'>"
            "<a href='https://www.fda.gov/drugs/questions-and-answers-fdas-adverse-event-reporting-system-faers/"
            "fda-adverse-event-reporting-system-faers-public-dashboard' "
            "target='_blank'>Official FDA FAERS Dashboard</a>"
            "</div>",
            unsafe_allow_html=True,
        )

    return {
        "quarters": selected_quarters,
        "role_filter": role_filter,
        "top_n": int(top_n),
    }

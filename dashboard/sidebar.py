from __future__ import annotations

from typing import Any

import streamlit as st

from dashboard import data_loader as dl
from dashboard import queries


def render_sidebar(default_top_n: int = 20) -> dict[str, Any]:
    profile = dl.get_dataset_profile()
    quarters = profile.get("quarters", [])

    with st.sidebar:
        st.header("Global Filters")
        selected_quarters = st.multiselect(
            "Quarters",
            options=quarters,
            default=quarters,
            help="Filters all tabs by selected quarter range.",
        )

        role_filter = st.selectbox(
            "Drug role",
            options=["all", "PS", "SS", "C"],
            index=0,
            help="PS=Primary suspect, SS=Secondary suspect, C=Concomitant",
        )

        top_n = st.slider(
            "Top N per chart", min_value=5, max_value=50, value=default_top_n, step=1
        )

        st.divider()
        st.subheader("Dataset Summary")
        kpi = queries.global_kpis(tuple(selected_quarters), role_filter)
        st.caption(f"Mode: {profile.get('mode', 'unknown')}")
        st.write(f"Cases: **{kpi['cases']:,}**")
        st.write(f"Deaths: **{kpi['deaths']:,}**")
        st.write(f"Unique drugs: **{kpi['unique_drugs']:,}**")
        st.write(f"MedDRA PTs: **{kpi['unique_reactions']:,}**")
        st.caption(
            f"Quarter range: {profile.get('quarter_min', '-')} to {profile.get('quarter_max', '-')}"
        )

        st.divider()
        st.subheader("About")
        st.caption(
            "FAERS is a spontaneous reporting system. Signals represent disproportionate reporting, not causality. "
            "Official FDA dashboard: https://www.fda.gov/drugs/fdas-adverse-event-reporting-system-faers"
        )

    return {
        "quarters": selected_quarters,
        "role_filter": role_filter,
        "top_n": top_n,
    }

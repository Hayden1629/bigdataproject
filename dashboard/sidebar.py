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

        selected_quarters = st.multiselect(
            "Quarters",
            options=quarters,
            default=quarters,
            help="Filters all views by the selected quarter range.",
        )

        role_filter = st.selectbox(
            "Drug role",
            options=["all", "PS", "SS", "C"],
            index=0,
            help="PS = Primary suspect, SS = Secondary suspect, C = Concomitant.",
        )

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
        st.caption(
            f"Coverage: {profile.get('quarter_min', '-')} to {profile.get('quarter_max', '-')}"
        )

    return {
        "quarters": selected_quarters,
        "role_filter": role_filter,
        "top_n": int(top_n),
    }

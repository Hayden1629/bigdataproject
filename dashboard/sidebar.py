from __future__ import annotations

import streamlit as st

import data_loader as dl
import queries as qr
import signal_detection as sd
from ui import C
from logger import get_logger

log = get_logger(__name__)


def render_sidebar(all_quarters: list[str]) -> dict[str, str | int | list[str]]:
    with st.sidebar:
        st.markdown(
            f"""
<div style="font-size:.70rem;font-weight:700;color:{C['muted']};
    text-transform:uppercase;letter-spacing:.14em;margin-bottom:12px;">
Global Filters
</div>
""",
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div style="font-size:.72rem;color:{C["muted"]};margin-bottom:6px;">Quarters</div>',
            unsafe_allow_html=True,
        )
        with st.container(height=180, border=True):
            sel_quarters = [q for q in all_quarters if st.checkbox(q, value=True, key=f"q_{q}")]
        q_key = qr._quarters_key(sel_quarters) if sel_quarters else "ALL"

        role_label = st.selectbox(
            "Drug role",
            ["Primary Suspect (PS)", "All roles", "Secondary Suspect (SS)", "Concomitant (C)"],
        )
        role_map = {
            "Primary Suspect (PS)": "PS",
            "All roles": "all",
            "Secondary Suspect (SS)": "SS",
            "Concomitant (C)": "C",
        }
        role_cod = role_map[role_label]
        top_n = st.slider("Top N per chart", 5, 50, 20, step=5)

        st.divider()
        gk = qr.global_kpis()
        sc = sd.signal_counts()
        profile = dl.get_dataset_profile()
        st.markdown(
            f"""
<div style="font-size:.70rem;font-weight:700;color:{C['muted']};
    text-transform:uppercase;letter-spacing:.14em;margin-bottom:8px;">
Dataset
</div>
""",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
| Metric | Value |
|---|---|
| Cases | **{gk['n_cases']:,}** |
| Deaths | **{gk['n_deaths']:,}** |
| Unique drugs | **{gk['n_drugs']:,}** |
| MedDRA PTs | **{gk['n_pts']:,}** |
| Mode | **{profile['mode']}** |
| Quarters | **{profile['quarter_start']} → {profile['quarter_end']}** |
| HIGH signals | **{sc['HIGH']:,}** |
"""
        )
        st.divider()
        st.markdown(
            f"""
<div style="font-size:.70rem;font-weight:700;color:{C['muted']};
    text-transform:uppercase;letter-spacing:.14em;margin-bottom:8px;">
About
</div>
<div style="font-size:.72rem;color:{C['muted']};line-height:1.6;">
FDA FAERS spontaneous adverse event reports, 2023 Q3&ndash;2025 Q2.<br>
Signal detection via PRR/chi&#178; (Evans et al. 2001).<br>
Drug normalization via RxNorm (NLM).
</div>
""",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div style='font-size:.68rem;margin-top:8px;'>"
            "<a href='https://www.fda.gov/drugs/questions-and-answers-fdas-adverse-event-reporting-system-faers/fda-adverse-event-reporting-system-faers-public-dashboard' "
            "style='color:#3b82f6;'>FDA FAERS Dashboard</a>"
            "</div>",
            unsafe_allow_html=True,
        )

    log.info("Sidebar filters: quarters=%s  role=%s  top_n=%d",
             q_key[:60], role_cod, top_n)
    return {
        "selected_quarters": sel_quarters,
        "q_key": q_key,
        "role_cod": role_cod,
        "top_n": top_n,
    }

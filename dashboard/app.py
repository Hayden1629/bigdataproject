"""
FAERS Drug Safety Intelligence Platform
"""

from __future__ import annotations

import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

import data_loader as dl
from sidebar import render_sidebar
from ui import configure_page, inject_css, render_header
from views.comparison import render as render_comparison
from views.drug import render as render_drug
from views.overview import render as render_overview
from views.reaction import render as render_reaction
from views.signals import render as render_signals


configure_page()
inject_css()
render_header()


if not dl._warm_started:
    dl._warm_started = True

    def _bg_warm() -> None:
        try:
            dl.warm_all_tables()
        except Exception:
            pass

    threading.Thread(target=_bg_warm, daemon=True).start()


with st.spinner("Loading FAERS dataset..."):
    tables = dl.load_tables()
    all_pts = dl.get_all_reaction_terms()
    all_q = dl.get_quarters()


filters = render_sidebar(all_q)

tab_ov, tab_drug, tab_cmp, tab_sig, tab_reac = st.tabs(
    ["Overview", "Drug Explorer", "Drug Comparison", "Signal Intelligence", "Reaction Explorer"]
)

with tab_ov:
    render_overview()

with tab_drug:
    render_drug(
        tables=tables,
        q_key=filters["q_key"],
        role_cod=filters["role_cod"],
        top_n=filters["top_n"],
    )

with tab_cmp:
    render_comparison(
        tables=tables,
        role_cod=filters["role_cod"],
        top_n=filters["top_n"],
    )

with tab_sig:
    render_signals()

with tab_reac:
    render_reaction(
        all_pts=all_pts,
        q_key=filters["q_key"],
        role_cod=filters["role_cod"],
        top_n=filters["top_n"],
    )

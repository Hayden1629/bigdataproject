"""
FAERS Drug Safety Intelligence Platform
"""

from __future__ import annotations

import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

from logger import get_logger
import data_loader as dl

log = get_logger(__name__)
from sidebar import render_sidebar
from ui import configure_page, inject_css, render_header
from views.drug import render as render_drug
from views.overview import render as render_overview
from views.reaction import render as render_reaction

configure_page()
inject_css()
render_header()


if not dl._warm_started:
    dl._warm_started = True
    log.info("Starting background cache warm-up thread")

    def _bg_warm() -> None:
        try:
            dl.warm_all_tables()
        except Exception as exc:
            log.error("Background warm-up failed: %s", exc)

    threading.Thread(target=_bg_warm, daemon=True).start()


log.info("App startup: loading tables, reaction terms, and quarters")
with st.spinner("Loading FAERS dataset..."):
    tables = dl.load_tables()
    all_pts = dl.get_all_reaction_terms()
    all_q = dl.get_quarters()
log.info("App startup complete: %d quarters, %d reaction terms", len(all_q), len(all_pts))


filters = render_sidebar(all_q)

tab_ov, tab_drug, tab_reac = st.tabs(
    ["Overview", "Drug Explorer", "Reaction Explorer"]
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

with tab_reac:
    render_reaction(
        all_pts=all_pts,
        q_key=filters["q_key"],
        role_cod=filters["role_cod"],
        top_n=filters["top_n"],
    )

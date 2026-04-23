from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sys
from pathlib import Path
import time

import streamlit as st

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard import data_loader as dl
from dashboard.logging_utils import get_logger, log_timing, setup_logging
from dashboard.sidebar import render_sidebar
from dashboard.ui import configure_page, inject_css, render_header
from dashboard.views import drug, manufacturer, overview, reaction


logger = get_logger(__name__)


def _warm_start() -> None:
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(dl.warm_all_tables)


def main() -> None:
    app_t0 = time.perf_counter()
    setup_logging()
    logger.info("Starting dashboard app")
    configure_page()
    inject_css()
    render_header()

    if "_warmed" not in st.session_state:
        st.session_state["_warmed"] = True
        _warm_start()

    try:
        with log_timing(logger, "Warm resource: drug name lookup"):
            _ = dl.load_drug_name_lookup()
        with log_timing(logger, "Warm resource: reaction terms"):
            _ = dl.get_all_reaction_terms()
        with log_timing(logger, "Warm resource: quarters"):
            _ = dl.get_quarters()
        with log_timing(logger, "Warm resource: manufacturer lookup"):
            _ = dl.load_manufacturer_lookup()
        logger.info("Warm resources loaded")
    except Exception as e:
        logger.warning("Warm resource loading failed, will retry on demand: %s", e)
        st.warning("Dashboard is warming up — some data may load slowly. Please refresh if needed.")

    filters = render_sidebar(default_top_n=20)

    tab_overview, tab_drug, tab_mfr, tab_reac = st.tabs(
        ["Overview", "Drug Explorer", "Manufacturer Lookup", "Reaction Explorer"]
    )

    with tab_overview:
        overview.render(filters)
    with tab_drug:
        drug.render(filters)
    with tab_mfr:
        manufacturer.render(filters)
    with tab_reac:
        reaction.render(filters)
    logger.info(
        "Dashboard render cycle complete in %.3fs", time.perf_counter() - app_t0
    )


if __name__ == "__main__":
    main()

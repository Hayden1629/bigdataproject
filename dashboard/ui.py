from __future__ import annotations

import streamlit as st


def configure_page() -> None:
    st.set_page_config(
        page_title="FAERS Safety Dashboard",
        page_icon=":bar_chart:",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def inject_css() -> None:
    st.markdown(
        """
        <style>
          :root {
            --bg: #f6f6f0;
            --paper: #ffffff;
            --ink: #152222;
            --accent: #006a6a;
            --accent-soft: #d8efeb;
          }
          .stApp {
            background:
              radial-gradient(1200px 500px at 5% -5%, #dff3ee 0%, transparent 60%),
              radial-gradient(900px 400px at 100% 0%, #f3e8d5 0%, transparent 55%),
              var(--bg);
          }
          h1, h2, h3 {
            color: var(--ink);
            letter-spacing: 0.2px;
          }
          .pill {
            display: inline-block;
            padding: 0.15rem 0.5rem;
            margin: 0.1rem 0.25rem 0.1rem 0;
            border-radius: 999px;
            background: var(--accent-soft);
            color: #154847;
            font-size: 0.82rem;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.title("FAERS Safety Intelligence Dashboard")
    st.caption(
        "Explore adverse-event patterns by drug, manufacturer, and reaction term."
    )


def metric_card(label: str, value: str, help_text: str | None = None) -> None:
    with st.container(border=True):
        st.metric(label=label, value=value, help=help_text)

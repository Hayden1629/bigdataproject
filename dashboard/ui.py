from __future__ import annotations

import html

import pandas as pd
import streamlit as st


def configure_page() -> None:
    st.set_page_config(
        page_title="FAERS Safety Dashboard",
        page_icon=":bar_chart:",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def format_compact(value: int | float) -> str:
    n = float(value)
    sign = "-" if n < 0 else ""
    n = abs(n)
    if n >= 1_000_000:
        out = f"{n / 1_000_000:.2f}".rstrip("0").rstrip(".")
        return f"{sign}{out}M"
    if n >= 1_000:
        out = f"{n / 1_000:.1f}".rstrip("0").rstrip(".")
        return f"{sign}{out}K"
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.1f}"


def inject_css() -> None:
    st.markdown(
        """
        <style>
          @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');

          :root {
            --faers-ink: #1d2433;
            --faers-muted: #667085;
            --faers-panel: #ffffff;
            --faers-line: #d7dfeb;
            --faers-navy: #17324d;
            --faers-blue: #2f6fed;
            --faers-blue-soft: #e8f0ff;
            --faers-teal: #148a7b;
            --faers-amber: #c07a20;
            --faers-red: #c44949;
            --faers-sidebar-line: rgba(255, 255, 255, 0.12);
          }

          html, body, .stApp, [data-testid="stAppViewContainer"] {
            font-family: "Manrope", "Segoe UI", sans-serif !important;
            color: var(--faers-ink) !important;
          }

          .stApp,
          [data-testid="stMain"] {
            background:
              radial-gradient(circle at top left, rgba(47, 111, 237, 0.08), transparent 28%),
              radial-gradient(circle at top right, rgba(20, 138, 123, 0.08), transparent 24%),
              linear-gradient(180deg, #f9fbff 0%, #f2f6fb 60%, #eef3f8 100%) !important;
          }

          [data-testid="stMain"] .block-container {
            max-width: none !important;
            padding-top: 0.95rem;
            padding-bottom: 2rem;
            padding-left: 1.25rem;
            padding-right: 1.25rem;
          }

          @media (min-width: 1200px) {
            [data-testid="stMain"] .block-container {
              padding-left: 1.75rem;
              padding-right: 1.75rem;
            }
          }

          [data-testid="stMain"] h1,
          [data-testid="stMain"] h2,
          [data-testid="stMain"] h3,
          [data-testid="stMain"] p,
          [data-testid="stMain"] span,
          [data-testid="stMain"] label {
            color: var(--faers-ink) !important;
          }

          [data-testid="stMain"] [data-testid="stCaptionContainer"] {
            color: var(--faers-muted) !important;
          }

          [data-testid="stMain"] [data-testid="stTabs"] [data-baseweb="tab-list"] {
            background: rgba(255, 255, 255, 0.88) !important;
            border: 1px solid rgba(215, 223, 235, 0.95) !important;
            border-radius: 16px !important;
            padding: 0.35rem !important;
            gap: 0.35rem !important;
            margin-bottom: 1rem !important;
            box-shadow: 0 12px 28px rgba(23, 50, 77, 0.05);
          }

          [data-testid="stMain"] [data-testid="stTabs"] [data-baseweb="tab"] {
            min-height: 42px !important;
            border-radius: 12px !important;
            padding: 0.55rem 1rem !important;
            color: var(--faers-muted) !important;
            font-size: 0.84rem !important;
            font-weight: 700 !important;
          }

          [data-testid="stMain"] [data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
            background: linear-gradient(135deg, rgba(47, 111, 237, 0.12), rgba(20, 138, 123, 0.12)) !important;
            color: var(--faers-navy) !important;
          }

          [data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"],
          [data-testid="stMain"] [data-testid="stPlotlyChart"],
          [data-testid="stMain"] [data-testid="stExpander"] {
            background: var(--faers-panel) !important;
            border: 1px solid rgba(215, 223, 235, 0.95) !important;
            border-radius: 20px !important;
            box-shadow: 0 12px 28px rgba(23, 50, 77, 0.06);
          }

          [data-testid="stMain"] [data-testid="stPlotlyChart"] {
            padding: 0.75rem !important;
            margin-bottom: 0.9rem !important;
          }

          [data-testid="stMain"] [data-testid="stTextInput"] label p,
          [data-testid="stMain"] [data-testid="stNumberInput"] label p,
          [data-testid="stMain"] [data-testid="stMultiSelect"] label p,
          [data-testid="stMain"] [data-testid="stSelectbox"] label p,
          [data-testid="stMain"] [data-testid="stSlider"] label p,
          [data-testid="stMain"] [data-testid="stToggle"] label p {
            color: var(--faers-muted) !important;
            font-size: 0.68rem !important;
            text-transform: uppercase !important;
            letter-spacing: 0.08em !important;
            font-weight: 800 !important;
          }

          [data-testid="stMain"] [data-baseweb="base-input"],
          [data-testid="stMain"] [data-baseweb="input"] input,
          [data-testid="stMain"] [data-baseweb="select"] > div,
          [data-testid="stMain"] [data-baseweb="popover"] [data-baseweb="select"] > div {
            background: #f8fbff !important;
            border: 1px solid var(--faers-line) !important;
            border-radius: 14px !important;
            color: var(--faers-ink) !important;
            box-shadow: none !important;
          }

          [data-testid="stMain"] [data-baseweb="tag"] {
            background: var(--faers-blue) !important;
            color: #ffffff !important;
            border-radius: 999px !important;
          }

          [data-testid="stMain"] [data-testid="stTextInput"] input,
          [data-testid="stMain"] textarea {
            background: #f8fbff !important;
            color: var(--faers-ink) !important;
          }

          [data-testid="stSidebar"] {
            background:
              radial-gradient(circle at top, rgba(47, 111, 237, 0.18), transparent 25%),
              linear-gradient(180deg, #122034 0%, #17283d 100%) !important;
            border-right: 1px solid var(--faers-sidebar-line) !important;
          }

          [data-testid="stSidebar"] .block-container {
            padding-top: 1rem;
          }

          [data-testid="stSidebar"] h1,
          [data-testid="stSidebar"] h2,
          [data-testid="stSidebar"] h3,
          [data-testid="stSidebar"] p,
          [data-testid="stSidebar"] li,
          [data-testid="stSidebar"] span,
          [data-testid="stSidebar"] label {
            color: white !important;
          }

          [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
          [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
            color: #a3b3c8 !important;
          }

          [data-testid="stSidebar"] [data-baseweb="select"] > div,
          [data-testid="stSidebar"] [data-baseweb="input"] input,
          [data-testid="stSidebar"] [data-baseweb="base-input"] {
            background: rgba(255, 255, 255, 0.06) !important;
            border-color: rgba(255, 255, 255, 0.15) !important;
            border-radius: 12px !important;
            color: white !important;
          }

          .faers-hero {
            padding: 1rem 1.25rem;
            border-radius: 22px;
            background: linear-gradient(135deg, #17324d 0%, #23588a 52%, #148a7b 100%);
            color: #ffffff;
            box-shadow: 0 16px 34px rgba(23, 50, 77, 0.16);
            margin-bottom: 0.95rem;
          }

          .faers-hero h1 {
            color: #ffffff !important;
            font-size: 1.85rem !important;
            font-weight: 800 !important;
            margin: 0 !important;
          }

          .faers-section-head {
            margin: 0.45rem 0 1rem 0;
            padding: 0 0.3rem;
          }

          .faers-section-title {
            font-size: 1rem;
            font-weight: 800;
            color: var(--faers-navy);
            margin: 0;
          }

          .faers-kpi-strip {
            display: grid;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            gap: 0.75rem;
            margin-bottom: 1rem;
          }

          @media (max-width: 1200px) {
            .faers-kpi-strip {
              grid-template-columns: repeat(3, minmax(0, 1fr));
            }
          }

          @media (max-width: 720px) {
            .faers-kpi-strip {
              grid-template-columns: repeat(2, minmax(0, 1fr));
            }
          }

          .faers-kpi-card,
          .faers-metric-card,
          .faers-info-card {
            background: #ffffff;
            border: 1px solid rgba(215, 223, 235, 0.95);
            border-radius: 18px;
            padding: 0.95rem 1rem;
            box-shadow: 0 12px 28px rgba(23, 50, 77, 0.06);
            min-height: 116px;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
          }

          .faers-kpi-t-blue, .faers-metric-blue { border-top: 4px solid var(--faers-blue); }
          .faers-kpi-t-red, .faers-metric-red { border-top: 4px solid var(--faers-red); }
          .faers-kpi-t-amber, .faers-metric-amber { border-top: 4px solid var(--faers-amber); }
          .faers-kpi-t-teal, .faers-metric-teal { border-top: 4px solid var(--faers-teal); }

          .faers-kpi-lbl,
          .faers-metric-label,
          .faers-info-label {
            font-size: 0.68rem;
            color: var(--faers-muted);
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-weight: 800;
            margin-bottom: 0.4rem;
          }

          .faers-kpi-val,
          .faers-metric-value,
          .faers-info-value {
            font-size: 1.28rem;
            font-weight: 800;
            line-height: 1.15;
            font-family: "DM Mono", monospace;
            color: var(--faers-ink);
            margin-bottom: 0.2rem;
          }

          .faers-kpi-v-blue { color: var(--faers-blue) !important; }
          .faers-kpi-v-red { color: var(--faers-red) !important; }
          .faers-kpi-v-amber { color: var(--faers-amber) !important; }
          .faers-kpi-v-teal { color: var(--faers-teal) !important; }

          .faers-kpi-sub,
          .faers-metric-sub,
          .faers-info-sub {
            font-size: 0.8rem;
            color: var(--faers-muted);
            margin-top: auto;
            line-height: 1.45;
            min-height: 1.2rem;
          }

          .faers-o-card-title {
            font-size: 0.96rem;
            font-weight: 800;
            color: var(--faers-navy);
            margin: 0 0 0.65rem 0;
          }

          .pill {
            display: inline-block;
            padding: 0.24rem 0.58rem;
            margin: 0.15rem 0.3rem 0.15rem 0;
            border-radius: 999px;
            background: var(--faers-blue-soft);
            color: var(--faers-blue) !important;
            font-size: 0.75rem;
            font-weight: 700;
          }

          .faers-table-wrap {
            background: #ffffff;
            border: 1px solid rgba(215, 223, 235, 0.95);
            border-radius: 20px;
            box-shadow: 0 12px 28px rgba(23, 50, 77, 0.06);
            overflow: auto;
            padding: 0;
            margin-bottom: 0.9rem;
          }

          .faers-table {
            width: 100%;
            border-collapse: collapse;
            background: #ffffff;
            color: var(--faers-ink);
            table-layout: auto;
          }

          .faers-table th {
            position: sticky;
            top: 0;
            background: #eef4ff;
            color: var(--faers-navy);
            text-align: left;
            font-size: 0.82rem;
            font-weight: 800;
            padding: 0.85rem 0.95rem;
            border-bottom: 1px solid var(--faers-line);
            white-space: nowrap;
          }

          .faers-table td {
            background: #ffffff;
            color: var(--faers-ink);
            font-size: 0.9rem;
            padding: 0.78rem 0.95rem;
            border-bottom: 1px solid #e8eef8;
            vertical-align: top;
            white-space: nowrap;
          }

          .faers-table tr:last-child td {
            border-bottom: none;
          }

          .faers-helper {
            margin: 0.4rem 0 1.1rem 0;
            color: #4d6a8a !important;
            font-size: 0.95rem;
            font-weight: 600;
            padding: 0 0.35rem;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown(
        """
        <section class="faers-hero">
          <h1>FAERS Safety Intelligence Dashboard</h1>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_section_intro(title: str, copy: str = "") -> None:
    extra = (
        f'<p style="margin:0.15rem 0 0 0;color:#667085;font-size:0.84rem;">{html.escape(copy)}</p>'
        if copy
        else ""
    )
    st.markdown(
        f"""
        <div class="faers-section-head">
          <div>
            <p class="faers-section-title">{html.escape(title)}</p>
            {extra}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_helper_text(text: str) -> None:
    st.markdown(
        f'<div class="faers-helper">{html.escape(text)}</div>',
        unsafe_allow_html=True,
    )


def render_info_card(label: str, value: str, subtext: str) -> None:
    st.markdown(
        f"""
        <div class="faers-info-card">
          <div class="faers-info-label">{html.escape(label)}</div>
          <div class="faers-info-value">{html.escape(value)}</div>
          <div class="faers-info-sub">{html.escape(subtext)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_note(title: str, body: str) -> None:
    return None


def metric_card(label: str, value: str, help_text: str | None = None) -> None:
    tone = "blue"
    lower = label.lower()
    if "death" in lower:
        tone = "red"
    elif "hospital" in lower or "life" in lower:
        tone = "amber"
    elif "country" in lower or "drug" in lower or "term" in lower:
        tone = "teal"

    subtext = help_text or ""
    st.markdown(
        f"""
        <div class="faers-metric-card faers-metric-{tone}" title="{html.escape(help_text or '')}">
          <div class="faers-metric-label">{html.escape(label)}</div>
          <div class="faers-metric-value">{html.escape(value)}</div>
          <div class="faers-metric-sub">{html.escape(subtext)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_table(df, *, height: int = 360) -> None:
    if isinstance(df, dict):
        df = pd.DataFrame(df)
    elif not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df)

    safe_df = df.copy()
    safe_df.columns = [html.escape(str(col)) for col in safe_df.columns]
    rows = []
    for _, row in safe_df.iterrows():
        cells = "".join(f"<td>{html.escape(str(value))}</td>" for value in row.tolist())
        rows.append(f"<tr>{cells}</tr>")
    header = "".join(f"<th>{col}</th>" for col in safe_df.columns)
    body = "".join(rows) if rows else f"<tr><td colspan='{max(len(safe_df.columns),1)}'>No data</td></tr>"
    st.markdown(
        f"""
        <div class="faers-table-wrap" style="max-height:{int(height)}px;">
          <table class="faers-table">
            <thead><tr>{header}</tr></thead>
            <tbody>{body}</tbody>
          </table>
        </div>
        """,
        unsafe_allow_html=True,
    )

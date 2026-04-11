"""
FAERS Drug Safety Intelligence Platform  v2
FDA Adverse Event Reporting System — Exploratory Dashboard

Run:
    streamlit run claude_test/app.py

Tabs:
    Overview            — global dataset KPIs, top drugs/reactions, country breakdown
    Drug Explorer       — drug search with RxNorm expansion, full adverse event profile
    Signal Intelligence — PRR/chi2 pharmacovigilance signal landscape
    Reaction Explorer   — semantic reaction search mapped to MedDRA PTs
"""

from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

import data_loader as dl
import signal_detection as sd
import queries as qr
from drug_normalizer import rxnorm_lookup, find_faers_names
from reaction_search import search_reactions
from signal_interpreter import interpret_signals

# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FAERS Drug Safety Intelligence",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "FDA FAERS | Team 11, Carlson MSBA 6331"},
)

# ─────────────────────────────────────────────────────────────────────────────
# Design tokens
# ─────────────────────────────────────────────────────────────────────────────
C = {
    "bg":      "#0d1117",
    "surface": "#161b22",
    "border":  "#30363d",
    "text":    "#e6edf3",
    "muted":   "#8b949e",
    "accent":  "#3b82f6",
    "high":    "#f85149",
    "medium":  "#e3b341",
    "low":     "#3fb950",
    "blue":    "#58a6ff",
    "purple":  "#a78bfa",
    "teal":    "#22d3ee",
}

CHART_BASE = dict(
    plot_bgcolor  = C["bg"],
    paper_bgcolor = C["surface"],
    font          = dict(color=C["text"], family="Inter, system-ui, sans-serif", size=12),
    margin        = dict(l=0, r=8, t=28, b=0),
    xaxis         = dict(gridcolor=C["border"], zerolinecolor=C["border"], tickfont=dict(size=11)),
    yaxis         = dict(gridcolor=C["border"], zerolinecolor=C["border"], tickfont=dict(size=11)),
    legend        = dict(bgcolor="rgba(0,0,0,0)", bordercolor=C["border"]),
)

def _theme(fig: go.Figure, h: int = 360) -> go.Figure:
    fig.update_layout(**CHART_BASE, height=h)
    return fig

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html,body,[class*="css"]{{font-family:'Inter',system-ui,sans-serif;}}

/* ── layout ─────────────────────────────────────────────── */
.block-container{{padding-top:0;padding-bottom:2rem;max-width:1440px;}}
[data-testid="stSidebar"]{{
    background:{C['surface']};
    border-right:1px solid {C['border']};
}}

/* ── tabs ────────────────────────────────────────────────── */
.stTabs [role="tablist"]{{
    border-bottom:1px solid {C['border']};
    gap:2px;
    padding:0 2px;
}}
.stTabs [role="tab"]{{
    font-size:0.80rem;
    font-weight:500;
    padding:8px 18px;
    border-radius:6px 6px 0 0;
    color:{C['muted']};
    transition:color .15s, background .15s;
}}
.stTabs [role="tab"][aria-selected="true"]{{
    color:{C['text']};
    background:rgba(59,130,246,.08);
    border-bottom:2px solid {C['accent']};
}}

/* ── header ──────────────────────────────────────────────── */
.dash-header{{
    background:linear-gradient(90deg,{C['surface']} 0%,rgba(22,27,34,.95) 100%);
    border-bottom:1px solid {C['border']};
    padding:14px 28px;
    margin:-1rem -1.5rem 1.5rem -1.5rem;
    display:flex;align-items:center;gap:16px;
}}
.dash-logo{{
    width:30px;height:30px;
    background:linear-gradient(135deg,{C['accent']},{C['purple']});
    border-radius:7px;
    display:flex;align-items:center;justify-content:center;
    font-size:14px;font-weight:800;color:#fff;
    flex-shrink:0;
}}
.dash-wordmark{{font-size:0.97rem;font-weight:700;color:{C['text']};letter-spacing:0.005em;}}
.dash-sep{{color:{C['border']};margin:0 4px;}}
.dash-sub{{font-size:0.73rem;color:{C['muted']};}}
.dash-pill{{
    margin-left:auto;
    background:rgba(63,185,80,.12);
    color:{C['low']};
    border:1px solid rgba(63,185,80,.30);
    border-radius:20px;
    font-size:0.65rem;font-weight:600;
    padding:3px 10px;
    letter-spacing:.05em;
    text-transform:uppercase;
}}

/* ── KPI cards ───────────────────────────────────────────── */
.kpi-row{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:1.25rem;}}
.kpi{{
    background:{C['surface']};
    border:1px solid {C['border']};
    border-radius:10px;
    padding:14px 18px;
    flex:1;min-width:130px;
    transition:border-color .2s;
}}
.kpi:hover{{border-color:{C['accent']};}}
.kpi-label{{font-size:0.62rem;color:{C['muted']};text-transform:uppercase;letter-spacing:.12em;margin-bottom:6px;}}
.kpi-value{{font-size:1.75rem;font-weight:800;color:{C['text']};line-height:1;font-variant-numeric:tabular-nums;}}
.kpi-sub{{font-size:0.68rem;color:{C['muted']};margin-top:4px;}}
.kpi-danger .kpi-value{{color:{C['high']};}}
.kpi-warn   .kpi-value{{color:{C['medium']};}}
.kpi-ok     .kpi-value{{color:{C['low']};}}
.kpi-danger{{border-left:3px solid {C['high']};}}
.kpi-warn{{border-left:3px solid {C['medium']};}}
.kpi-ok{{border-left:3px solid {C['low']};}}

/* ── section labels ──────────────────────────────────────── */
.sec{{
    font-size:0.65rem;font-weight:700;color:{C['muted']};
    text-transform:uppercase;letter-spacing:.15em;
    border-bottom:1px solid {C['border']};
    padding-bottom:6px;margin-bottom:12px;margin-top:8px;
}}

/* ── signal badges ───────────────────────────────────────── */
.badge{{
    display:inline-block;font-size:.60rem;font-weight:700;
    padding:2px 8px;border-radius:4px;
    text-transform:uppercase;letter-spacing:.08em;
}}
.bHIGH  {{background:rgba(248,81,73,.12); color:{C['high']};  border:1px solid rgba(248,81,73,.35);}}
.bMEDIUM{{background:rgba(227,179,65,.12);color:{C['medium']};border:1px solid rgba(227,179,65,.35);}}
.bLOW   {{background:rgba(63,185,80,.12); color:{C['low']};   border:1px solid rgba(63,185,80,.35);}}

/* ── chip strip (RxNorm names) ───────────────────────────── */
.chips{{margin:4px 0 12px;line-height:2.4;}}
.chip{{
    display:inline-block;
    background:rgba(59,130,246,.08);
    color:{C['blue']};
    border:1px solid rgba(59,130,246,.25);
    border-radius:5px;font-size:.67rem;font-weight:500;
    padding:2px 8px;margin:2px 3px;
}}

/* ── note / info box ─────────────────────────────────────── */
.note{{
    background:{C['surface']};border:1px solid {C['border']};
    border-left:3px solid {C['accent']};
    border-radius:0 6px 6px 0;padding:10px 14px;
    font-size:0.74rem;color:{C['muted']};
    line-height:1.6;
    margin:10px 0 14px;
}}

/* ── dataframe ───────────────────────────────────────────── */
.stDataFrame {{border-radius:8px;overflow:hidden;}}

/* ── spinner ─────────────────────────────────────────────── */
[data-testid="stSpinner"] > div {{color:{C['accent']};}}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="dash-header">
  <div class="dash-logo">F</div>
  <span class="dash-wordmark">FAERS Drug Safety Intelligence</span>
  <span class="dash-sep">|</span>
  <span class="dash-sub">FDA Adverse Event Reporting System &nbsp;&middot;&nbsp; 2023 Q3 &ndash; 2025 Q2 &nbsp;&middot;&nbsp; Team 11 &middot; Carlson MSBA 6331</span>
  <span class="dash-pill">Live</span>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Data load (cached — runs once per session, ~15 s first time)
# ─────────────────────────────────────────────────────────────────────────────
with st.spinner("Loading FAERS dataset..."):
    _tables  = dl.load_tables()
    all_pts  = dl.get_all_reaction_terms()
    all_q    = dl.get_quarters()

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
<div style="font-size:.70rem;font-weight:700;color:{C['muted']};
    text-transform:uppercase;letter-spacing:.14em;margin-bottom:12px;">
Global Filters
</div>
""", unsafe_allow_html=True)

    sel_quarters = st.multiselect("Quarters", options=all_q, default=all_q)
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
    st.markdown(f"""
<div style="font-size:.70rem;font-weight:700;color:{C['muted']};
    text-transform:uppercase;letter-spacing:.14em;margin-bottom:8px;">
Dataset
</div>
""", unsafe_allow_html=True)
    st.markdown(f"""
| Metric | Value |
|---|---|
| Cases (dedup) | **{gk['n_cases']:,}** |
| Deaths | **{gk['n_deaths']:,}** |
| Unique drugs | **{gk['n_drugs']:,}** |
| MedDRA PTs | **{gk['n_pts']:,}** |
| Quarters | **{len(all_q)}** |
| HIGH signals | **{sc['HIGH']:,}** |
""")
    st.divider()
    st.markdown(f"""
<div style="font-size:.70rem;font-weight:700;color:{C['muted']};
    text-transform:uppercase;letter-spacing:.14em;margin-bottom:8px;">
About
</div>
<div style="font-size:.72rem;color:{C['muted']};line-height:1.6;">
FDA FAERS spontaneous adverse event reports, 2023 Q3&ndash;2025 Q2.<br>
Signal detection via PRR/chi&#178; (Evans et al. 2001).<br>
Drug normalization via RxNorm (NLM).
</div>
""", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:.68rem;margin-top:8px;'>"
        "<a href='https://www.fda.gov/drugs/questions-and-answers-fdas-adverse-event-reporting-system-faers/fda-adverse-event-reporting-system-faers-public-dashboard' "
        "style='color:#3b82f6;'>FDA FAERS Dashboard</a>"
        "</div>",
        unsafe_allow_html=True,
    )

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def sec(title: str) -> None:
    st.markdown(f'<div class="sec">{title}</div>', unsafe_allow_html=True)

def kpi_card(label: str, value: str, sub: str = "", cls: str = "") -> str:
    return (f'<div class="kpi {cls}">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}</div>'
            + (f'<div class="kpi-sub">{sub}</div>' if sub else "")
            + "</div>")

def badge(level: str) -> str:
    return f'<span class="badge b{level}">{level}</span>'

def empty_fig(msg: str = "No data", h: int = 200) -> go.Figure:
    f = go.Figure()
    f.add_annotation(text=msg, x=.5, y=.5, showarrow=False,
                     font=dict(color=C["muted"], size=13))
    return _theme(f, h)


# ─────────────────────────────────────────────────────────────────────────────
# Shared chart builders
# ─────────────────────────────────────────────────────────────────────────────
def bar_h(df: pd.DataFrame, x: str, y: str, color_scale: list, text_col: str | None = None,
          h: int = 400) -> go.Figure:
    if df.empty:
        return empty_fig(h=h)
    text = df[text_col] if text_col else df[x].apply(lambda v: f"{v:,}")
    fig = go.Figure(go.Bar(
        x=df[x], y=df[y], orientation="h",
        text=text, textposition="outside",
        marker=dict(color=df[x], colorscale=color_scale, showscale=False),
        hovertemplate=f"<b>%{{y}}</b><br>{x}: %{{x:,}}<extra></extra>",
    ))
    fig.update_layout(yaxis=dict(categoryorder="total ascending"), xaxis_title=None, yaxis_title=None)
    return _theme(fig, max(h, len(df) * 22 + 80))


def donut(df: pd.DataFrame, vals: str, names: str, colors: list | None = None,
          h: int = 300) -> go.Figure:
    if df.empty:
        return empty_fig(h=h)
    palette = colors or [C["accent"], C["high"], C["medium"], C["purple"], C["teal"], C["low"], "#f97316"]
    fig = go.Figure(go.Pie(
        labels=df[names], values=df[vals], hole=.48,
        marker=dict(colors=palette[:len(df)], line=dict(color=C["bg"], width=2)),
        textinfo="label+percent", textfont=dict(size=11),
        hovertemplate="<b>%{label}</b><br>%{value:,} (%{percent})<extra></extra>",
    ))
    return _theme(fig, h)


def line_trend(df: pd.DataFrame, x: str, y: str, label: str = "Cases",
               color: str | None = None, h: int = 260) -> go.Figure:
    if df.empty:
        return empty_fig(h=h)
    clr = color or C["accent"]
    fig = go.Figure(go.Scatter(
        x=df[x], y=df[y], mode="lines+markers",
        line=dict(color=clr, width=2.5),
        marker=dict(color=clr, size=7),
        fill="tozeroy", fillcolor=f"rgba({int(clr[1:3],16)},{int(clr[3:5],16)},{int(clr[5:],16)},0.09)",
        hovertemplate=f"<b>%{{x}}</b><br>{label}: %{{y:,}}<extra></extra>",
    ))
    fig.update_layout(xaxis_tickangle=-25, yaxis_title=label, xaxis_title=None)
    return _theme(fig, h)


def multi_line(traces: list[dict], h: int = 280) -> go.Figure:
    """traces = [{"x":..., "y":..., "name":..., "color":...}]"""
    fig = go.Figure()
    for t in traces:
        clr = t.get("color", C["accent"])
        fig.add_trace(go.Scatter(
            x=t["x"], y=t["y"], name=t["name"], mode="lines+markers",
            line=dict(color=clr, width=2.2, dash=t.get("dash", "solid")),
            marker=dict(color=clr, size=6),
            hovertemplate=f"<b>%{{x}}</b><br>{t['name']}: %{{y:,}}<extra></extra>",
        ))
    fig.update_layout(
        xaxis_tickangle=-25, yaxis_title="Cases", xaxis_title=None,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return _theme(fig, h)


def bar_v(df: pd.DataFrame, x: str, y: str, color_scale: list, h: int = 280) -> go.Figure:
    if df.empty:
        return empty_fig(h=h)
    fig = go.Figure(go.Bar(
        x=df[x], y=df[y],
        text=df[y].apply(lambda v: f"{v:,}"),
        textposition="outside",
        marker=dict(color=df[y], colorscale=color_scale, showscale=False),
        hovertemplate="<b>%{x}</b><br>%{y:,}<extra></extra>",
    ))
    fig.update_layout(xaxis_tickangle=-30, yaxis_title=None)
    return _theme(fig, h)


def prr_scatter(df: pd.DataFrame, h: int = 420) -> go.Figure:
    if df.empty:
        return empty_fig(h=h)
    df = df.copy()
    df["log2_prr"] = np.log2(df["PRR"].clip(lower=0.1))
    df["log10_n"]  = np.log10(df["N_DR"].clip(lower=1))
    color_map = {"HIGH": C["high"], "MEDIUM": C["medium"], "LOW": C["low"]}
    fig = go.Figure()
    for level in ["HIGH", "MEDIUM", "LOW"]:
        sub = df[df["signal"] == level]
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub["log10_n"], y=sub["log2_prr"],
            mode="markers", name=level,
            marker=dict(color=color_map[level], size=5, opacity=.7),
            text=sub.apply(lambda r: f"<b>{r['drug']}</b> × {r['pt']}<br>"
                                     f"PRR = {r['PRR']:.1f} &nbsp; N = {r['N_DR']:,}", axis=1),
            hovertemplate="%{text}<extra></extra>",
        ))
    # threshold line at PRR = 2
    fig.add_hline(y=1, line=dict(color=C["medium"], dash="dot", width=1))
    fig.add_annotation(text="PRR = 2", x=df["log10_n"].max() * .98, y=1.15,
                       showarrow=False, font=dict(color=C["medium"], size=10))
    fig.update_layout(
        xaxis_title="log₁₀ co-occurrence count",
        yaxis_title="log₂ PRR",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return _theme(fig, h)


def forest_plot(df: pd.DataFrame, h: int | None = None) -> go.Figure:
    """Forest plot of top PRR signals for a drug."""
    if df.empty:
        return empty_fig(h=300)
    df = df.head(20).copy()
    df = df.sort_values("PRR")
    color_map = {"HIGH": C["high"], "MEDIUM": C["medium"], "LOW": C["low"]}
    colors = [color_map.get(s, C["muted"]) for s in df["signal"]]

    # SE of ln(PRR) for CI bars
    a  = df["N_DR"].to_numpy(dtype=float)
    nd = df["N_D"].to_numpy(dtype=float)
    nr = df["N_R"].to_numpy(dtype=float)
    nt = df["N_total"].to_numpy(dtype=float)
    se = np.sqrt(
        np.where(a > 0, 1/a, 1) +
        np.where(nd - a > 0, 1/(nd - a), 1) +
        np.where(nr - a > 0, 1/(nr - a), 1) +
        np.where(nt - nd - nr + a > 0, 1/(nt - nd - nr + a), 1)
    )
    ln_prr = np.log(df["PRR"].clip(lower=0.01))
    ci_lo  = np.exp(ln_prr - 1.96 * se)
    ci_hi  = np.exp(ln_prr + 1.96 * se)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["PRR"], y=df["pt"],
        mode="markers",
        marker=dict(color=colors, size=9, symbol="diamond"),
        error_x=dict(
            type="data",
            symmetric=False,
            array=ci_hi - df["PRR"].to_numpy(),
            arrayminus=df["PRR"].to_numpy() - ci_lo,
            color=C["muted"], thickness=1.5,
        ),
        hovertemplate="<b>%{y}</b><br>PRR = %{x:.2f}<extra></extra>",
    ))
    fig.add_vline(x=2, line=dict(color=C["medium"], dash="dot", width=1))
    fig.update_layout(xaxis_title="Proportional Reporting Ratio (95% CI)", yaxis_title=None,
                      xaxis_type="log")
    h = h or max(300, len(df) * 24 + 60)
    return _theme(fig, h)


# ─────────────────────────────────────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────────────────────────────────────
tab_ov, tab_drug, tab_cmp, tab_sig, tab_reac = st.tabs(
    ["Overview", "Drug Explorer", "Drug Comparison", "Signal Intelligence", "Reaction Explorer"]
)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 0  ─  Overview
# ═════════════════════════════════════════════════════════════════════════════
with tab_ov:
    # KPI row
    gk = qr.global_kpis()
    death_pct_global = round(gk["n_deaths"] / gk["n_cases"] * 100, 2) if gk["n_cases"] else 0
    kpis_html = "".join([
        kpi_card("Deduplicated Cases",    f"{gk['n_cases']:,}"),
        kpi_card("Deaths Reported",       f"{gk['n_deaths']:,}",
                 f"{death_pct_global}% of cases", "kpi-danger"),
        kpi_card("Hospitalisations",      f"{gk['n_hosp']:,}"),
        kpi_card("Life-threatening",      f"{gk['n_lt']:,}"),
        kpi_card("Unique Drug Entities",  f"{gk['n_drugs']:,}"),
        kpi_card("MedDRA PTs Reported",   f"{gk['n_pts']:,}"),
    ])
    st.markdown(f'<div class="kpi-row">{kpis_html}</div>', unsafe_allow_html=True)

    # Global trend
    sec("Reports Per Quarter")
    global_trend = qr.global_quarterly_trend()
    st.plotly_chart(line_trend(global_trend, "quarter", "case_count", "Cases"), use_container_width=True)

    # Top drugs + top reactions
    col_a, col_b = st.columns(2)
    drug_sum = dl.load_drug_summary()
    reac_sum = dl.load_reac_summary()

    with col_a:
        sec("Top 15 Drugs by Report Volume")
        if drug_sum is not None:
            top15d = drug_sum.head(15)[["drug", "n_cases", "n_deaths"]].copy()
            fig_td = go.Figure(go.Bar(
                x=top15d["n_cases"], y=top15d["drug"], orientation="h",
                marker=dict(color=top15d["n_cases"], colorscale=[[0,"#1d4ed8"],[1,"#60a5fa"]], showscale=False),
                text=top15d["n_cases"].apply(lambda v: f"{v:,}"),
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>Cases: %{x:,}<extra></extra>",
            ))
            fig_td.update_layout(yaxis=dict(categoryorder="total ascending"), xaxis_title=None)
            _theme(fig_td, 420)
            st.plotly_chart(fig_td, use_container_width=True)

    with col_b:
        sec("Top 15 Reactions by Report Volume")
        if reac_sum is not None:
            top15r = reac_sum.head(15)[["pt", "n_cases"]].copy()
            fig_tr = go.Figure(go.Bar(
                x=top15r["n_cases"], y=top15r["pt"], orientation="h",
                marker=dict(color=top15r["n_cases"], colorscale=[[0,"#7c3aed"],[1,"#c4b5fd"]], showscale=False),
                text=top15r["n_cases"].apply(lambda v: f"{v:,}"),
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>Cases: %{x:,}<extra></extra>",
            ))
            fig_tr.update_layout(yaxis=dict(categoryorder="total ascending"), xaxis_title=None)
            _theme(fig_tr, 420)
            st.plotly_chart(fig_tr, use_container_width=True)

    # World map + Reporter type
    sec("Global Report Distribution")
    choropleth_data = qr.global_country_choropleth()
    if not choropleth_data.empty:
        fig_map = go.Figure(go.Choropleth(
            locations=choropleth_data["iso3"],
            z=choropleth_data["count"],
            text=choropleth_data.apply(
                lambda r: f"<b>{r['country']}</b><br>{r['count']:,} reports ({r['pct']}%)", axis=1
            ),
            hovertemplate="%{text}<extra></extra>",
            colorscale=[[0, "#0c1a2e"], [0.2, "#1e3a5f"], [0.5, "#1d4ed8"], [0.8, "#3b82f6"], [1.0, "#93c5fd"]],
            showscale=True,
            colorbar=dict(
                title=dict(text="Reports", font=dict(color=C["muted"], size=11)),
                thickness=12,
                len=0.6,
                bgcolor="rgba(0,0,0,0)",
                bordercolor=C["border"],
                tickfont=dict(color=C["muted"], size=10),
            ),
            marker=dict(line=dict(color=C["border"], width=0.5)),
        ))
        fig_map.update_layout(
            **CHART_BASE,
            height=380,
            geo=dict(
                bgcolor=C["bg"],
                lakecolor=C["bg"],
                landcolor=C["surface"],
                showland=True,
                showlakes=False,
                showcountries=True,
                countrycolor=C["border"],
                showframe=False,
                projection_type="natural earth",
            ),
            margin=dict(l=0, r=0, t=28, b=0),
        )
        st.plotly_chart(fig_map, use_container_width=True)

    col_c, col_d = st.columns([3, 2])
    with col_c:
        sec("Top 20 Countries by Report Volume")
        ctry = qr.global_top_countries(top_n=20)
        fig_ctry = go.Figure(go.Bar(
            x=ctry["country"], y=ctry["count"],
            marker=dict(color=ctry["count"], colorscale=[[0,"#0c4a6e"],[1,"#38bdf8"]], showscale=False),
            text=ctry["pct"].apply(lambda v: f"{v}%"),
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>%{y:,} reports (%{text})<extra></extra>",
        ))
        fig_ctry.update_layout(xaxis_tickangle=-40, yaxis_title="Reports")
        _theme(fig_ctry, 280)
        st.plotly_chart(fig_ctry, use_container_width=True)

    with col_d:
        sec("Reporter Type Distribution")
        rtype = qr.global_reporter_types()
        st.plotly_chart(donut(rtype, "count", "label", h=280), use_container_width=True)

    # Signal summary
    sec("Pharmacovigilance Signal Summary")
    sc = sd.signal_counts()
    sig_html = "".join([
        kpi_card("HIGH Signals",   f"{sc['HIGH']:,}",
                 "PRR \u2265 4, N \u2265 5, \u03c7\u00b2 \u2265 4", "kpi-danger"),
        kpi_card("MEDIUM Signals", f"{sc['MEDIUM']:,}",
                 "PRR \u2265 2, N \u2265 3, \u03c7\u00b2 \u2265 4", "kpi-warn"),
        kpi_card("LOW Signals",    f"{sc['LOW']:,}",
                 "PRR \u2265 1.5, N \u2265 3", "kpi-ok"),
    ])
    st.markdown(f'<div class="kpi-row">{sig_html}</div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="note">Signal detection uses the Proportional Reporting Ratio (PRR) method '
        '(Evans et al. 2001, <i>Pharmacoepidemiol Drug Saf</i>). '
        'A signal is elevated when PRR \u2265 2, chi-squared \u2265 4, and co-occurrences \u2265 3. '
        'FAERS is a spontaneous reporting database; signals do not establish causality.</div>',
        unsafe_allow_html=True,
    )

    # Trending quarter-over-quarter
    sec("Quarter-over-Quarter Trends")
    trend_d = qr.trending_drugs(top_n=10)
    trend_r = qr.trending_reactions(top_n=10)
    t1, t2 = st.columns(2)
    with t1:
        if not trend_d.empty:
            prev_q_lbl = trend_d["prev_q"].iloc[0]
            curr_q_lbl = trend_d["curr_q"].iloc[0]
            st.caption(f"Drugs with largest case increase: {prev_q_lbl} → {curr_q_lbl}")
            fig_td2 = go.Figure(go.Bar(
                x=trend_d["delta"], y=trend_d["drug"], orientation="h",
                text=trend_d.apply(lambda r: f"+{r['delta']:,}  ({r['pct_change']:+.0f}%)", axis=1),
                textposition="outside",
                marker=dict(color=trend_d["delta"], colorscale=[[0,"#164e63"],[1,"#22d3ee"]], showscale=False),
                hovertemplate="<b>%{y}</b><br>+%{x:,} cases<extra></extra>",
            ))
            fig_td2.update_layout(yaxis=dict(categoryorder="total ascending"), xaxis_title="Case increase")
            _theme(fig_td2, 320)
            st.plotly_chart(fig_td2, use_container_width=True)
    with t2:
        if not trend_r.empty:
            prev_q_lbl = trend_r["prev_q"].iloc[0]
            curr_q_lbl = trend_r["curr_q"].iloc[0]
            st.caption(f"Reactions with largest case increase: {prev_q_lbl} → {curr_q_lbl}")
            fig_tr2 = go.Figure(go.Bar(
                x=trend_r["delta"], y=trend_r["reaction"], orientation="h",
                text=trend_r.apply(lambda r: f"+{r['delta']:,}  ({r['pct_change']:+.0f}%)", axis=1),
                textposition="outside",
                marker=dict(color=trend_r["delta"], colorscale=[[0,"#4a1d96"],[1,"#c4b5fd"]], showscale=False),
                hovertemplate="<b>%{y}</b><br>+%{x:,} cases<extra></extra>",
            ))
            fig_tr2.update_layout(yaxis=dict(categoryorder="total ascending"), xaxis_title="Case increase")
            _theme(fig_tr2, 320)
            st.plotly_chart(fig_tr2, use_container_width=True)

    # Top 10 global HIGH signals table
    sec("Top Elevated Signals (HIGH, N \u2265 50)")
    top_sigs = sd.global_top_signals(min_signal="HIGH", min_n_dr=50, top_n=10)
    if not top_sigs.empty:
        disp = top_sigs[["drug", "pt", "N_DR", "PRR", "chi2", "signal"]].copy()
        disp.columns = ["Drug", "Preferred Term", "Co-occurrences", "PRR", "Chi-sq", "Signal"]
        st.dataframe(
            disp, hide_index=True, use_container_width=True,
            column_config={
                "PRR":    st.column_config.NumberColumn("PRR",    format="%.2f"),
                "Chi-sq": st.column_config.NumberColumn("Chi-sq", format="%.1f"),
            },
        )


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1  ─  Drug Explorer
# ═════════════════════════════════════════════════════════════════════════════
with tab_drug:
    drug_query = st.text_input(
        "Drug search",
        placeholder="Brand name, generic name, or active ingredient  —  e.g. naloxone, Mounjaro, dupilumab, warfarin",
        key="drug_input",
        label_visibility="collapsed",
    )

    if not drug_query:
        drug_sum2 = dl.load_drug_summary()
        if drug_sum2 is not None:
            sec("Most Reported Drugs — Full Dataset")
            top20 = drug_sum2.head(20).copy()
            top20.columns = [c.replace("_", " ").title() for c in top20.columns]
            st.dataframe(
                top20.style.format({"N Cases": "{:,}", "N Deaths": "{:,}", "Death Pct": "{:.2f}%"}),
                use_container_width=True, hide_index=True, height=580,
            )
        st.stop()

    # ── Drug normalisation ────────────────────────────────────────────────────
    with st.spinner("Normalising via RxNorm..."):
        rxn      = rxnorm_lookup(drug_query)
        matched  = find_faers_names(drug_query, _tables["drug"])

    if not matched:
        st.error(
            f"No FAERS records found for **{drug_query}**. "
            "Try a different spelling, the generic name, or a brand name."
        )
        st.stop()

    nk = qr._names_key(matched)  # stable cache key

    # ── RxNorm banner ─────────────────────────────────────────────────────────
    canon = rxn.get("canonical") or drug_query.title()
    related = rxn.get("related", [])
    rxcui_tag = f" &nbsp;·&nbsp; RxCUI `{rxn['rxcui']}`" if rxn.get("rxcui") else ""

    st.markdown(f"**{canon}**{rxcui_tag}", unsafe_allow_html=True)
    if related:
        chips_html = " ".join(f'<span class="chip">{n}</span>' for n in sorted(related)[:50])
        st.markdown(f'<div class="chips">{chips_html}</div>', unsafe_allow_html=True)
    st.caption(f"{len(matched)} FAERS drug name strings matched — role filter: {role_cod}")

    # ── KPIs ──────────────────────────────────────────────────────────────────
    kpi = qr.drug_kpis(nk, role_cod, q_key)
    serious_pct = round(kpi["n_serious"] / kpi["n_cases"] * 100, 1) if kpi["n_cases"] else 0
    death_cls   = "kpi-danger" if kpi["death_pct"] > 10 else "kpi-warn" if kpi["death_pct"] > 5 else ""
    k_html = "".join([
        kpi_card("Total Cases",       f"{kpi['n_cases']:,}"),
        kpi_card("Deaths",            f"{kpi['n_deaths']:,}",
                 f"{kpi['death_pct']}% of cases", death_cls),
        kpi_card("Hospitalisations",  f"{kpi['n_hosp']:,}"),
        kpi_card("Life-threatening",  f"{kpi['n_lt']:,}"),
        kpi_card("Any Serious Outcome", f"{kpi['n_serious']:,}", f"{serious_pct}%"),
    ])
    st.markdown(f'<div class="kpi-row">{k_html}</div>', unsafe_allow_html=True)

    # ── Reactions + Outcomes ──────────────────────────────────────────────────
    c_left, c_right = st.columns([3, 2])
    with c_left:
        sec("Top Adverse Reactions (MedDRA PTs)")
        reac_df = qr.drug_top_reactions(nk, role_cod, q_key, top_n)
        st.plotly_chart(
            bar_h(reac_df, "count", "pt",
                  [[0,"#1d4ed8"],[1,"#60a5fa"]],
                  text_col=None, h=max(400, top_n*22+80)),
            use_container_width=True,
        )
    with c_right:
        sec("Outcome Distribution")
        outc_df = qr.drug_outcomes(nk, role_cod, q_key)
        st.plotly_chart(donut(outc_df, "count", "outcome_label", h=340), use_container_width=True)

    # ── Trend ─────────────────────────────────────────────────────────────────
    sec("Quarterly Report Volume")
    trend = qr.drug_trend(nk, role_cod, q_key)
    st.plotly_chart(line_trend(trend, "quarter", "case_count", "Reports"), use_container_width=True)

    # ── Demographics + Country ────────────────────────────────────────────────
    sec("Patient Demographics & Geography")
    d1, d2, d3, d4 = st.columns(4)

    demog = qr.drug_demographics(nk, role_cod, q_key)
    with d1:
        st.markdown('<div style="text-align:center;font-size:.68rem;color:#8b949e;">SEX</div>', unsafe_allow_html=True)
        sex_df = demog["sex"]
        st.plotly_chart(donut(sex_df, "count", "sex_label",
                              [C["accent"], "#ec4899", C["muted"]], h=220), use_container_width=True)
    with d2:
        st.markdown('<div style="text-align:center;font-size:.68rem;color:#8b949e;">AGE GROUP</div>', unsafe_allow_html=True)
        age_df = demog["age_grp"]
        st.plotly_chart(bar_v(age_df, "age_group_label", "count",
                              [[0,"#1e3a5f"],[1,"#3b82f6"]], h=220), use_container_width=True)
    with d3:
        st.markdown('<div style="text-align:center;font-size:.68rem;color:#8b949e;">REPORTER</div>', unsafe_allow_html=True)
        rep_df = demog["reporter"]
        st.plotly_chart(bar_v(rep_df, "reporter", "count",
                              [[0,"#1a3a2a"],[1,"#3fb950"]], h=220), use_container_width=True)
    with d4:
        sec("Top Reporter Countries")
        ctry_df = qr.drug_countries(nk, role_cod, q_key, top_n=10)
        if not ctry_df.empty:
            st.dataframe(
                ctry_df[["country", "count", "pct"]].rename(columns={"count":"Cases","pct":"%"}),
                use_container_width=True, hide_index=True, height=220,
            )

    # ── Drug Indications + Concomitants ───────────────────────────────────────
    sec("Clinical Context")
    ci1, ci2 = st.columns(2)

    with ci1:
        st.markdown('<div style="font-size:.72rem;color:#8b949e;margin-bottom:6px;">PRESCRIBED FOR (Top Indications)</div>', unsafe_allow_html=True)
        indi_df = qr.drug_indications(nk, role_cod, q_key, top_n=12)
        if not indi_df.empty:
            st.plotly_chart(
                bar_h(indi_df, "count", "indication",
                      [[0,"#2d1b69"],[1,"#a78bfa"]], h=max(300, len(indi_df)*22+60)),
                use_container_width=True,
            )
        else:
            st.caption("No indication data found for this drug.")

    with ci2:
        st.markdown('<div style="font-size:.72rem;color:#8b949e;margin-bottom:6px;">COMMONLY CO-REPORTED DRUGS</div>', unsafe_allow_html=True)
        comed_df = qr.drug_concomitants(nk, role_cod, q_key, top_n=12)
        if not comed_df.empty:
            st.plotly_chart(
                bar_h(comed_df, "count", "drug",
                      [[0,"#1a3a3a"],[1,"#22d3ee"]], h=max(300, len(comed_df)*22+60)),
                use_container_width=True,
            )
        else:
            st.caption("No concomitant drug data found.")

    # ── PRR Signals ──────────────────────────────────────────────────────────
    sec("Pharmacovigilance Signals (PRR)")
    sig_df = sd.signals_for_drug(matched, min_signal="LOW", top_n=25, min_n_dr=10)

    if not sig_df.empty:
        cnt_h = int((sig_df["signal"] == "HIGH").sum())
        cnt_m = int((sig_df["signal"] == "MEDIUM").sum())
        cnt_l = int((sig_df["signal"] == "LOW").sum())
        st.markdown(
            f"Showing {len(sig_df)} signals — "
            f"{badge('HIGH')} **{cnt_h}** &nbsp; "
            f"{badge('MEDIUM')} **{cnt_m}** &nbsp; "
            f"{badge('LOW')} **{cnt_l}**",
            unsafe_allow_html=True,
        )
        fp1, fp2 = st.columns([2, 3])
        with fp1:
            sig_disp = sig_df.rename(columns={
                "pt":"Preferred Term","N_DR":"N (D+R)","N_D":"N (Drug)","N_R":"N (Rxn)",
                "PRR":"PRR","chi2":"Chi-sq","signal":"Signal",
            })
            st.dataframe(
                sig_disp[["Signal","Preferred Term","PRR","N (D+R)","Chi-sq"]],
                use_container_width=True, hide_index=True, height=400,
                column_config={
                    "PRR":    st.column_config.NumberColumn("PRR",    format="%.2f"),
                    "Chi-sq": st.column_config.NumberColumn("Chi-sq", format="%.1f"),
                },
            )
        with fp2:
            st.markdown('<div style="font-size:.68rem;color:#8b949e;margin-bottom:4px;">FOREST PLOT — 95% CI on log scale</div>', unsafe_allow_html=True)
            st.plotly_chart(forest_plot(sig_df, h=400), use_container_width=True)
    else:
        st.info("No PRR signals found. Run `python3 claude_test/precompute.py` to generate the signal cache.")

    # ── AI signal interpretation ──────────────────────────────────────────────
    if not sig_df.empty:
        sec("AI Signal Interpretation (Claude Haiku)")
        with st.spinner("Generating signal summary..."):
            signals_csv_str = sig_df[["pt","N_DR","PRR","chi2","signal"]].head(15).to_csv(index=False)
            ai_summary = interpret_signals(
                drug_name=canon,
                signals_csv=signals_csv_str,
                n_cases=kpi["n_cases"],
                n_deaths=kpi["n_deaths"],
            )
        if ai_summary:
            st.markdown(
                f'<div class="note" style="font-size:.80rem;color:{C["text"]};line-height:1.7;">'
                f'{ai_summary}'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption("AI interpretation unavailable — set ANTHROPIC_API_KEY to enable.")

    with st.expander("All matched FAERS drug name strings"):
        st.dataframe(
            pd.DataFrame({"FAERS Drug Name": sorted(matched)}),
            use_container_width=True, hide_index=True,
        )


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2  ─  Signal Intelligence
# ═════════════════════════════════════════════════════════════════════════════
with tab_sig:
    prr_global = dl.load_prr_table()
    if prr_global is None or prr_global.empty:
        st.warning("PRR cache not found. Run `python3 claude_test/precompute.py`.")
        st.stop()

    # ── Filter row ────────────────────────────────────────────────────────────
    fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 2])
    with fc1:
        sig_levels = st.multiselect("Signal level", ["HIGH","MEDIUM","LOW"],
                                    default=["HIGH","MEDIUM"], key="sig_lev")
    with fc2:
        min_n_sig = st.number_input("Min co-occurrences", 1, 5000, 10, step=5)
    with fc3:
        drug_txt = st.text_input("Drug filter", placeholder="e.g. methotrexate", key="sig_d")
    with fc4:
        pt_txt = st.text_input("Reaction filter", placeholder="e.g. hepatitis", key="sig_r")

    mask = prr_global["signal"].isin(sig_levels) & (prr_global["N_DR"] >= min_n_sig)
    if drug_txt:
        mask = mask & prr_global["drug"].str.contains(drug_txt.upper(), na=False, regex=False)
    if pt_txt:
        mask = mask & prr_global["pt"].str.contains(pt_txt, na=False, case=False, regex=False)
    filtered = prr_global[mask].sort_values(["chi2","N_DR"], ascending=[False,False])

    # ── Signal KPIs ───────────────────────────────────────────────────────────
    sc = sd.signal_counts()
    sig_k = "".join([
        kpi_card("HIGH Signals",   f"{sc['HIGH']:,}",   "PRR\u22654, N\u22655, \u03c7\u00b2\u22654", "kpi-danger"),
        kpi_card("MEDIUM Signals", f"{sc['MEDIUM']:,}", "PRR\u22652, N\u22653, \u03c7\u00b2\u22654", "kpi-warn"),
        kpi_card("LOW Signals",    f"{sc['LOW']:,}",    "PRR\u22651.5, N\u22653", "kpi-ok"),
        kpi_card("Drugs Covered",  f"{prr_global['drug'].nunique():,}"),
        kpi_card("Reactions Covered", f"{prr_global['pt'].nunique():,}"),
        kpi_card("Filtered Signals",  f"{len(filtered):,}"),
    ])
    st.markdown(f'<div class="kpi-row">{sig_k}</div>', unsafe_allow_html=True)

    # ── Scatter ───────────────────────────────────────────────────────────────
    sec("Signal Landscape — PRR vs. Report Volume")
    sample = filtered.sample(min(len(filtered), 4000), random_state=42) if len(filtered) > 4000 else filtered
    st.plotly_chart(prr_scatter(sample, h=430), use_container_width=True)
    st.caption(
        f"{len(sample):,} of {len(filtered):,} signals shown. "
        "Dotted line = PRR of 2 (Evans threshold). "
        "X-axis: log₁₀ co-occurrence count. Y-axis: log₂ PRR."
    )

    # ── Table ─────────────────────────────────────────────────────────────────
    sec("Signal Table")
    disp = filtered.head(500).copy()
    disp = disp.rename(columns={
        "drug":"Drug","pt":"Preferred Term",
        "N_DR":"N (D+R)","N_D":"N (Drug)","N_R":"N (Reaction)",
        "PRR":"PRR","ROR":"ROR","chi2":"Chi-sq","signal":"Signal",
    })
    st.dataframe(
        disp[["Signal","Drug","Preferred Term","PRR","N (D+R)","N (Drug)","N (Reaction)","Chi-sq"]],
        use_container_width=True, hide_index=True, height=520,
        column_config={
            "PRR":    st.column_config.NumberColumn("PRR",    format="%.2f"),
            "Chi-sq": st.column_config.NumberColumn("Chi-sq", format="%.1f"),
        },
    )
    st.caption(f"{len(filtered):,} signals match current filters (showing top 500).")

    csv = filtered.head(10000).to_csv(index=False).encode()
    st.download_button("Download filtered signals (CSV)", data=csv,
                       file_name="faers_signals.csv", mime="text/csv")

    st.markdown(
        '<div class="note">'
        '<b>Methodology:</b> PRR = (a/n<sub>exposed</sub>) / (c/n<sub>unexposed</sub>), '
        'where a = cases with both drug and reaction, n<sub>exposed</sub> = all cases with drug, '
        'c = cases with reaction but not drug, n<sub>unexposed</sub> = all cases without drug. '
        'Signal threshold: PRR \u2265 2, chi-squared \u2265 4, N \u2265 3 (Evans et al. 2001). '
        'Computed for top 500 drugs by report volume over 2023 Q3\u20132025 Q2.'
        '</div>',
        unsafe_allow_html=True,
    )


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3  ─  Reaction Explorer
# ═════════════════════════════════════════════════════════════════════════════
with tab_reac:
    reac_query = st.text_input(
        "Reaction search",
        placeholder="Plain English or clinical term  —  e.g. heart attack, hair loss, throwing up, myocardial infarction",
        key="reac_input",
        label_visibility="collapsed",
    )

    if not reac_query:
        reac_sum2 = dl.load_reac_summary()
        if reac_sum2 is not None:
            sec("Most Reported Adverse Reactions")
            top20r = reac_sum2.head(20).copy()
            top20r.columns = [c.replace("_"," ").title() for c in top20r.columns]
            st.dataframe(
                top20r.style.format({"N Cases":"{:,}","N Deaths":"{:,}","Death Pct":"{:.2f}%"}),
                use_container_width=True, hide_index=True, height=580,
            )
        st.stop()

    # ── MedDRA mapping ────────────────────────────────────────────────────────
    with st.spinner("Searching MedDRA vocabulary..."):
        pt_hits = search_reactions(reac_query, all_pts, max_results=25)

    if not pt_hits:
        st.error(f"No MedDRA terms matched **{reac_query}**. Try different phrasing.")
        st.stop()

    col_sel, col_tbl = st.columns([3, 1])
    with col_sel:
        selected_pts = st.multiselect(
            "MedDRA Preferred Terms matched (select to include in analysis):",
            options=[p for p, _ in pt_hits],
            default=[p for p, _ in pt_hits[:3]],
        )
    with col_tbl:
        match_tbl = pd.DataFrame(pt_hits[:12], columns=["Preferred Term", "Score"])
        match_tbl["Score"] = match_tbl["Score"].round(0).astype(int)
        st.dataframe(match_tbl, use_container_width=True, hide_index=True, height=260)

    if not selected_pts:
        st.info("Select at least one Preferred Term.")
        st.stop()

    pk = "|".join(sorted(selected_pts))

    # ── KPIs ─────────────────────────────────────────────────────────────────
    rk = qr.reaction_kpis(pk, q_key)
    death_pct_r = round(rk["n_deaths"] / rk["n_cases"] * 100, 1) if rk["n_cases"] else 0
    rk_html = "".join([
        kpi_card("Cases Reporting Reaction",  f"{rk['n_cases']:,}"),
        kpi_card("Deaths in Those Cases",     f"{rk['n_deaths']:,}",
                 f"{death_pct_r}%", "kpi-danger"),
        kpi_card("Any Serious Outcome",       f"{rk['n_serious']:,}"),
        kpi_card("MedDRA Terms Selected",     str(len(selected_pts))),
    ])
    st.markdown(f'<div class="kpi-row">{rk_html}</div>', unsafe_allow_html=True)

    # ── Charts ────────────────────────────────────────────────────────────────
    cl, cr = st.columns([3, 2])
    with cl:
        sec(f"Top Associated Drugs (role: {role_cod})")
        top_d = qr.reaction_top_drugs(pk, role_cod, q_key, top_n)
        st.plotly_chart(
            bar_h(top_d, "case_count", "drug_label",
                  [[0,"#7c3aed"],[1,"#c4b5fd"]], h=max(400, top_n*22+80)),
            use_container_width=True,
        )
    with cr:
        sec("Outcome Distribution")
        outc_r = qr.reaction_outcomes(pk, q_key)
        st.plotly_chart(donut(outc_r, "count", "outcome_label", h=340), use_container_width=True)

    sec("Quarterly Report Volume")
    tr = qr.reaction_trend(pk, q_key)
    st.plotly_chart(line_trend(tr, "quarter", "case_count", "Reports", color=C["purple"]), use_container_width=True)

    # ── PRR signals for this reaction ─────────────────────────────────────────
    sec("Drug Signals for This Reaction (PRR)")
    reac_sigs = sd.signals_for_reaction(selected_pts, min_signal="MEDIUM", top_n=20)
    if not reac_sigs.empty:
        sr1, sr2 = st.columns([2, 3])
        with sr1:
            sd_disp = reac_sigs.rename(columns={
                "drug":"Drug","N_DR":"N (D+R)","PRR":"PRR","chi2":"Chi-sq","signal":"Signal",
            })
            st.dataframe(
                sd_disp[["Signal","Drug","PRR","N (D+R)","Chi-sq"]],
                use_container_width=True, hide_index=True, height=360,
                column_config={
                    "PRR":    st.column_config.NumberColumn("PRR",    format="%.2f"),
                    "Chi-sq": st.column_config.NumberColumn("Chi-sq", format="%.1f"),
                },
            )
        with sr2:
            # Re-shape the signal dataframe to forest-plot format
            fp_df = reac_sigs.rename(columns={"drug":"pt"})
            # Add dummy columns needed by forest_plot
            fp_df = fp_df.copy()
            if "N_total" not in fp_df.columns:
                fp_df["N_total"] = dl.get_n_total()
            st.markdown('<div style="font-size:.68rem;color:#8b949e;margin-bottom:4px;">FOREST PLOT — drugs with elevated PRR for this reaction</div>', unsafe_allow_html=True)
            st.plotly_chart(forest_plot(fp_df, h=360), use_container_width=True)
    else:
        st.info("No elevated PRR signals found for the selected terms.")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2  ─  Drug Comparison
# ═════════════════════════════════════════════════════════════════════════════
with tab_cmp:
    st.markdown(
        '<div class="note">Enter two drugs to compare their adverse event profiles side-by-side. '
        'Useful for comparing therapeutic alternatives, biosimilars, or competing products in the same class.</div>',
        unsafe_allow_html=True,
    )

    cmp_c1, cmp_c2 = st.columns(2)
    with cmp_c1:
        drug_a_query = st.text_input(
            "Drug A",
            placeholder="e.g. dupilumab, Keytruda, ozempic",
            key="cmp_drug_a",
        )
    with cmp_c2:
        drug_b_query = st.text_input(
            "Drug B",
            placeholder="e.g. tralokinumab, pembrolizumab, tirzepatide",
            key="cmp_drug_b",
        )

    if not drug_a_query or not drug_b_query:
        sec("Suggested Comparison Pairs")
        examples = [
            ("GLP-1 Agonists",      "ozempic",      "mounjaro",      "Semaglutide vs Tirzepatide — GI profile and dosing errors"),
            ("IL-4/IL-13 Inhibitors","dupilumab",   "tralokinumab",  "Dupixent vs Adbry — atopic dermatitis biologics"),
            ("PD-1 Inhibitors",     "keytruda",     "opdivo",        "Pembrolizumab vs Nivolumab — immune checkpoint toxicity"),
            ("Factor Xa Inhibitors","apixaban",     "rivaroxaban",   "Eliquis vs Xarelto — bleeding and renal outcomes"),
            ("TNF Inhibitors",      "adalimumab",   "etanercept",    "Humira vs Enbrel — infection and injection site reactions"),
            ("JAK Inhibitors",      "tofacitinib",  "baricitinib",   "Xeljanz vs Olumiant — cardiovascular and thrombosis"),
        ]
        ex_df = pd.DataFrame(examples, columns=["Drug Class", "Drug A", "Drug B", "Clinical Question"])
        st.dataframe(ex_df, use_container_width=True, hide_index=True)
        st.caption("Type the Drug A and Drug B names above to generate the comparison.")

        st.divider()
        ds = dl.load_drug_summary()
        if ds is not None:
            sec("All Available Drugs (by Report Volume)")
            st.dataframe(
                ds.head(20)[["drug","n_cases","n_deaths","death_pct"]].rename(
                    columns={"drug":"Drug","n_cases":"Cases","n_deaths":"Deaths","death_pct":"Death %"}
                ).style.format({"Cases":"{:,}","Deaths":"{:,}","Death %":"{:.2f}%"}),
                use_container_width=True, hide_index=True, height=440,
            )
        st.stop()

    with st.spinner("Normalising drug names..."):
        rxn_a    = rxnorm_lookup(drug_a_query)
        matched_a = find_faers_names(drug_a_query, _tables["drug"])
        rxn_b    = rxnorm_lookup(drug_b_query)
        matched_b = find_faers_names(drug_b_query, _tables["drug"])

    if not matched_a:
        st.error(f"No FAERS records found for **{drug_a_query}**.")
        st.stop()
    if not matched_b:
        st.error(f"No FAERS records found for **{drug_b_query}**.")
        st.stop()

    nk_a = qr._names_key(matched_a)
    nk_b = qr._names_key(matched_b)
    label_a = (rxn_a.get("canonical") or drug_a_query).title()
    label_b = (rxn_b.get("canonical") or drug_b_query).title()

    if nk_a == nk_b:
        st.warning(
            "Both inputs resolved to the same drug entity. "
            "Enter two distinct drugs to compare."
        )
        st.stop()

    # ── KPI comparison table ──────────────────────────────────────────────────
    sec("Key Metrics Comparison")
    kpi_a, kpi_b = qr.drug_comparison_kpis(nk_a, nk_b, role_cod)

    def _pct(n, d):
        return f"{n/d*100:.1f}%" if d else "—"

    cmp_rows = [
        ("Total Cases",         f"{kpi_a['n_cases']:,}",   f"{kpi_b['n_cases']:,}"),
        ("Deaths",              f"{kpi_a['n_deaths']:,} ({_pct(kpi_a['n_deaths'],kpi_a['n_cases'])})",
                                f"{kpi_b['n_deaths']:,} ({_pct(kpi_b['n_deaths'],kpi_b['n_cases'])})"),
        ("Hospitalisations",    f"{kpi_a['n_hosp']:,} ({_pct(kpi_a['n_hosp'],kpi_a['n_cases'])})",
                                f"{kpi_b['n_hosp']:,} ({_pct(kpi_b['n_hosp'],kpi_b['n_cases'])})"),
        ("Life-threatening",    f"{kpi_a['n_lt']:,} ({_pct(kpi_a['n_lt'],kpi_a['n_cases'])})",
                                f"{kpi_b['n_lt']:,} ({_pct(kpi_b['n_lt'],kpi_b['n_cases'])})"),
        ("Any Serious Outcome", f"{kpi_a['n_serious']:,} ({_pct(kpi_a['n_serious'],kpi_a['n_cases'])})",
                                f"{kpi_b['n_serious']:,} ({_pct(kpi_b['n_serious'],kpi_b['n_cases'])})"),
    ]
    cmp_df = pd.DataFrame(cmp_rows, columns=["Metric", label_a, label_b])
    st.dataframe(cmp_df, use_container_width=True, hide_index=True)

    # ── Quarterly trend overlay ───────────────────────────────────────────────
    sec("Quarterly Report Volume — Overlaid Trend")
    trend_merged = qr.drug_comparison_trend(nk_a, nk_b, role_cod)
    if not trend_merged.empty:
        cols_ab = [c for c in trend_merged.columns if c != "quarter"]
        if len(cols_ab) >= 2:
            traces = [
                {"x": trend_merged["quarter"], "y": trend_merged[cols_ab[0]],
                 "name": label_a, "color": C["accent"]},
                {"x": trend_merged["quarter"], "y": trend_merged[cols_ab[1]],
                 "name": label_b, "color": C["teal"], "dash": "dot"},
            ]
            st.plotly_chart(multi_line(traces, h=300), use_container_width=True)

    # ── Shared reactions grouped bar ──────────────────────────────────────────
    sec(f"Top Shared Adverse Reactions (Reports per 1,000 Cases)")
    shared_rxn = qr.drug_comparison_shared_reactions(nk_a, nk_b, role_cod, top_n=top_n)
    if not shared_rxn.empty:
        shared_rxn_sorted = shared_rxn.sort_values("rate_a", ascending=True)
        fig_shared = go.Figure()
        fig_shared.add_trace(go.Bar(
            y=shared_rxn_sorted["pt"],
            x=shared_rxn_sorted["rate_a"],
            name=label_a, orientation="h",
            marker=dict(color=C["accent"]),
            hovertemplate=f"<b>%{{y}}</b><br>{label_a}: %{{x:.1f}} per 1k<extra></extra>",
        ))
        fig_shared.add_trace(go.Bar(
            y=shared_rxn_sorted["pt"],
            x=shared_rxn_sorted["rate_b"],
            name=label_b, orientation="h",
            marker=dict(color=C["teal"]),
            hovertemplate=f"<b>%{{y}}</b><br>{label_b}: %{{x:.1f}} per 1k<extra></extra>",
        ))
        fig_shared.update_layout(
            barmode="group",
            yaxis=dict(categoryorder="array", categoryarray=shared_rxn_sorted["pt"].tolist()),
            xaxis_title="Reports per 1,000 cases",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(_theme(fig_shared, max(400, len(shared_rxn)*28+80)), use_container_width=True)
        st.caption(
            f"Rate = (reaction reports for drug) / (total drug cases) × 1,000. "
            f"Shows reactions appearing in both {label_a} and {label_b} case sets."
        )
    else:
        st.info("No shared reactions found with sufficient case counts.")

    # ── Top reactions side by side ────────────────────────────────────────────
    sec("Top Reactions — Individual Rankings")
    rxn_a_df, rxn_b_df = qr.drug_comparison_top_reactions(nk_a, nk_b, role_cod, top_n=15)
    ca, cb = st.columns(2)
    with ca:
        st.markdown(f'<div style="font-size:.72rem;color:{C["muted"]};margin-bottom:6px;">{label_a.upper()}</div>', unsafe_allow_html=True)
        st.plotly_chart(
            bar_h(rxn_a_df, "count", "pt", [[0,"#1d4ed8"],[1,"#60a5fa"]], h=max(380, 15*22+80)),
            use_container_width=True,
        )
    with cb:
        st.markdown(f'<div style="font-size:.72rem;color:{C["muted"]};margin-bottom:6px;">{label_b.upper()}</div>', unsafe_allow_html=True)
        st.plotly_chart(
            bar_h(rxn_b_df, "count", "pt", [[0,"#0e7490"],[1,"#22d3ee"]], h=max(380, 15*22+80)),
            use_container_width=True,
        )

    # ── Outcome donuts ────────────────────────────────────────────────────────
    sec("Outcome Distribution")
    outc_a_df, outc_b_df = qr.drug_comparison_outcomes(nk_a, nk_b, role_cod)
    od1, od2 = st.columns(2)
    with od1:
        st.markdown(f'<div style="text-align:center;font-size:.72rem;color:{C["muted"]};">{label_a.upper()}</div>', unsafe_allow_html=True)
        st.plotly_chart(donut(outc_a_df, "count", "outcome_label", h=300), use_container_width=True)
    with od2:
        st.markdown(f'<div style="text-align:center;font-size:.72rem;color:{C["muted"]};">{label_b.upper()}</div>', unsafe_allow_html=True)
        st.plotly_chart(donut(outc_b_df, "count", "outcome_label", h=300), use_container_width=True)

    # ── PRR signal comparison ─────────────────────────────────────────────────
    sec("Pharmacovigilance Signals (HIGH only)")
    sig_a = sd.signals_for_drug(matched_a, min_signal="HIGH", top_n=10, min_n_dr=10)
    sig_b = sd.signals_for_drug(matched_b, min_signal="HIGH", top_n=10, min_n_dr=10)
    ps1, ps2 = st.columns(2)
    with ps1:
        st.markdown(f'<div style="font-size:.72rem;color:{C["muted"]};margin-bottom:6px;">{label_a.upper()} — TOP HIGH SIGNALS</div>', unsafe_allow_html=True)
        if not sig_a.empty:
            st.dataframe(
                sig_a[["pt","N_DR","PRR","chi2","signal"]].rename(
                    columns={"pt":"Preferred Term","N_DR":"N","PRR":"PRR","chi2":"Chi-sq","signal":"Level"}
                ),
                use_container_width=True, hide_index=True, height=320,
                column_config={
                    "PRR": st.column_config.NumberColumn("PRR", format="%.2f"),
                    "Chi-sq": st.column_config.NumberColumn("Chi-sq", format="%.1f"),
                },
            )
        else:
            st.info("No HIGH signals found.")
    with ps2:
        st.markdown(f'<div style="font-size:.72rem;color:{C["muted"]};margin-bottom:6px;">{label_b.upper()} — TOP HIGH SIGNALS</div>', unsafe_allow_html=True)
        if not sig_b.empty:
            st.dataframe(
                sig_b[["pt","N_DR","PRR","chi2","signal"]].rename(
                    columns={"pt":"Preferred Term","N_DR":"N","PRR":"PRR","chi2":"Chi-sq","signal":"Level"}
                ),
                use_container_width=True, hide_index=True, height=320,
                column_config={
                    "PRR": st.column_config.NumberColumn("PRR", format="%.2f"),
                    "Chi-sq": st.column_config.NumberColumn("Chi-sq", format="%.1f"),
                },
            )
        else:
            st.info("No HIGH signals found.")

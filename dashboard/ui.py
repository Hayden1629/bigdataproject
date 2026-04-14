from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


C = {
    "bg": "#FFFFFF",
    "surface": "#EFF6FB",
    "border": "#BDD7EA",
    "text": "#1B2A3B",
    "muted": "#5B616B",
    "accent": "#0071BC",
    "navy": "#112E51",
    "high": "#981B1E",
    "medium": "#D97706",
    "low": "#2E8540",
    "blue": "#205493",
    "teal": "#02BFE7",
    "purple": "#4C2C92",
}

CHART_BASE = dict(
    plot_bgcolor="#FFFFFF",
    paper_bgcolor=C["surface"],
    font=dict(color=C["text"], family="Avenir Next, Segoe UI, Helvetica Neue, Arial, sans-serif", size=12),
    margin=dict(l=0, r=8, t=28, b=0),
    xaxis=dict(gridcolor="#D5E5F0", zerolinecolor="#D5E5F0", tickfont=dict(size=11)),
    yaxis=dict(gridcolor="#D5E5F0", zerolinecolor="#D5E5F0", tickfont=dict(size=11)),
    legend=dict(bgcolor="rgba(255,255,255,0.8)", bordercolor=C["border"]),
)


def configure_page() -> None:
    st.set_page_config(
        page_title="FAERS Drug Safety Intelligence",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={"About": "FDA FAERS | Team 11, Carlson MSBA 6331"},
    )


def theme(fig: go.Figure, h: int = 360) -> go.Figure:
    fig.update_layout(**CHART_BASE, height=h)
    return fig


def inject_css() -> None:
    st.markdown(
        f"""
<style>
html,body,[class*="css"]{{font-family:'Avenir Next','Segoe UI','Helvetica Neue',Arial,sans-serif;background:{C['bg']};color:{C['text']};}}
.block-container{{padding-top:0;padding-bottom:2rem;max-width:1440px;}}
[data-testid="stSidebar"]{{background:{C['surface']};border-right:1px solid {C['border']};}}
.stTabs [role="tablist"]{{border-bottom:2px solid {C['accent']};gap:2px;padding:0 2px;}}
.stTabs [role="tab"]{{font-size:0.80rem;font-weight:500;padding:8px 18px;border-radius:6px 6px 0 0;color:{C['muted']};transition:color .15s,background .15s;}}
.stTabs [role="tab"][aria-selected="true"]{{color:{C['accent']};background:rgba(0,113,188,.08);border-bottom:3px solid {C['accent']};font-weight:700;}}
.dash-header{{background:linear-gradient(90deg,{C['navy']} 0%,{C['blue']} 60%,{C['accent']} 100%);border-bottom:3px solid {C['teal']};padding:14px 28px;margin:-1rem -1.5rem 1.5rem -1.5rem;display:flex;align-items:center;gap:16px;}}
.dash-logo{{width:32px;height:32px;background:#FFFFFF;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:800;color:{C['accent']};flex-shrink:0;}}
.dash-wordmark{{font-size:0.97rem;font-weight:700;color:#FFFFFF;letter-spacing:0.005em;}}
.dash-sep{{color:rgba(255,255,255,.4);margin:0 6px;}}
.dash-sub{{font-size:0.73rem;color:rgba(255,255,255,.75);}}
.dash-pill{{margin-left:auto;background:rgba(255,255,255,.15);color:#FFFFFF;border:1px solid rgba(255,255,255,.35);border-radius:20px;font-size:0.65rem;font-weight:600;padding:3px 10px;letter-spacing:.05em;text-transform:uppercase;}}
.kpi-row{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:1.25rem;}}
.kpi{{background:#FFFFFF;border:1px solid {C['border']};border-radius:8px;padding:14px 18px;flex:1;min-width:130px;box-shadow:0 1px 3px rgba(0,71,188,.06);transition:border-color .2s,box-shadow .2s;}}
.kpi:hover{{border-color:{C['accent']};box-shadow:0 2px 8px rgba(0,113,188,.12);}}
.kpi-label{{font-size:0.62rem;color:{C['muted']};text-transform:uppercase;letter-spacing:.12em;margin-bottom:6px;}}
.kpi-value{{font-size:1.75rem;font-weight:800;color:{C['navy']};line-height:1;font-variant-numeric:tabular-nums;}}
.kpi-sub{{font-size:0.68rem;color:{C['muted']};margin-top:4px;}}
.kpi-danger .kpi-value{{color:{C['high']};}}
.kpi-warn .kpi-value{{color:{C['medium']};}}
.kpi-ok .kpi-value{{color:{C['low']};}}
.kpi-danger{{border-left:3px solid {C['high']};}}
.kpi-warn{{border-left:3px solid {C['medium']};}}
.kpi-ok{{border-left:3px solid {C['low']};}}
.sec{{font-size:0.63rem;font-weight:700;color:{C['blue']};text-transform:uppercase;letter-spacing:.16em;border-bottom:1px solid {C['border']};padding-bottom:5px;margin-bottom:12px;margin-top:8px;}}
.badge{{display:inline-block;font-size:.60rem;font-weight:700;padding:2px 8px;border-radius:4px;text-transform:uppercase;letter-spacing:.08em;}}
.bHIGH{{background:rgba(152,27,30,.09); color:{C['high']}; border:1px solid rgba(152,27,30,.30);}}
.bMEDIUM{{background:rgba(217,119,6,.10); color:{C['medium']}; border:1px solid rgba(217,119,6,.30);}}
.bLOW{{background:rgba(46,133,64,.09); color:{C['low']}; border:1px solid rgba(46,133,64,.30);}}
.chips{{margin:4px 0 12px;line-height:2.4;}}
.chip{{display:inline-block;background:rgba(0,113,188,.07);color:{C['blue']};border:1px solid rgba(0,113,188,.22);border-radius:4px;font-size:.67rem;font-weight:500;padding:2px 8px;margin:2px 3px;}}
.fda-card{{background:#FFFFFF;border:1px solid {C['border']};border-left:4px solid {C['accent']};border-radius:0 8px 8px 0;padding:12px 18px;margin:8px 0 14px;display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px 20px;}}
.fda-label{{font-size:.60rem;color:{C['muted']};text-transform:uppercase;letter-spacing:.10em;margin-bottom:2px;}}
.fda-value{{font-size:.80rem;font-weight:600;color:{C['navy']};}}
.fda-value a{{color:{C['accent']};text-decoration:none;}}
.fda-value a:hover{{text-decoration:underline;}}
.note{{background:{C['surface']};border:1px solid {C['border']};border-left:3px solid {C['accent']};border-radius:0 6px 6px 0;padding:10px 14px;font-size:0.74rem;color:{C['muted']};line-height:1.6;margin:10px 0 14px;}}
.stDataFrame {{border-radius:8px;overflow:hidden;border:1px solid {C['border']};}}
[data-testid="stSpinner"] > div {{color:{C['accent']};}}
</style>
""",
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown(
        """
<div class="dash-header">
  <div class="dash-logo">F</div>
  <span class="dash-wordmark">FAERS Drug Safety Intelligence</span>
  <span class="dash-sep">|</span>
  <span class="dash-sub">FDA Adverse Event Reporting System &nbsp;&middot;&nbsp; 2023 Q3 &ndash; 2025 Q2 &nbsp;&middot;&nbsp; Team 11 &middot; Carlson MSBA 6331</span>
  <span class="dash-pill">Live</span>
</div>
""",
        unsafe_allow_html=True,
    )


def sec(title: str) -> None:
    st.markdown(f'<div class="sec">{title}</div>', unsafe_allow_html=True)


def kpi_card(label: str, value: str, sub: str = "", cls: str = "") -> str:
    return (
        f'<div class="kpi {cls}">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        + (f'<div class="kpi-sub">{sub}</div>' if sub else "")
        + "</div>"
    )


def badge(level: str) -> str:
    return f'<span class="badge b{level}">{level}</span>'


def empty_fig(msg: str = "No data", h: int = 200) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=msg, x=0.5, y=0.5, showarrow=False, font=dict(color=C["muted"], size=13))
    return theme(fig, h)


def summary_note(title: str, items: list[str]) -> None:
    lines = "".join(f"<li>{item}</li>" for item in items if item)
    if not lines:
        return
    st.markdown(
        f'<div class="note"><strong>{title}</strong><ul style="margin:8px 0 0 18px;padding:0;">{lines}</ul></div>',
        unsafe_allow_html=True,
    )


def quarter_delta_text(trend_df: pd.DataFrame) -> str:
    if len(trend_df) < 2:
        return ""
    prev = int(trend_df["case_count"].iloc[-2])
    curr = int(trend_df["case_count"].iloc[-1])
    delta = curr - prev
    pct = (delta / prev * 100) if prev else 0
    return f"{trend_df['quarter'].iloc[-2]} to {trend_df['quarter'].iloc[-1]}: {delta:+,} reports ({pct:+.1f}%)"


def bar_h(df: pd.DataFrame, x: str, y: str, color_scale: list, text_col: str | None = None, h: int = 400) -> go.Figure:
    if df.empty:
        return empty_fig(h=h)
    text = df[text_col] if text_col else df[x].apply(lambda v: f"{v:,}")
    fig = go.Figure(
        go.Bar(
            x=df[x],
            y=df[y],
            orientation="h",
            text=text,
            textposition="inside",
            insidetextanchor="end",
            textfont=dict(color="white", size=11),
            marker=dict(color=df[x], colorscale=color_scale, showscale=False),
            hovertemplate=f"<b>%{{y}}</b><br>{x}: %{{x:,}}<extra></extra>",
        )
    )
    fig.update_layout(yaxis=dict(categoryorder="total ascending"), xaxis_title=None, yaxis_title=None)
    return theme(fig, max(h, len(df) * 22 + 80))


def donut(df: pd.DataFrame, vals: str, names: str, colors: list | None = None, h: int = 300) -> go.Figure:
    if df.empty:
        return empty_fig(h=h)
    palette = colors or [C["accent"], C["high"], C["medium"], C["purple"], C["teal"], C["low"], "#f97316"]
    fig = go.Figure(
        go.Pie(
            labels=df[names],
            values=df[vals],
            hole=0.48,
            marker=dict(colors=palette[: len(df)], line=dict(color=C["bg"], width=2)),
            textinfo="label+percent",
            textfont=dict(size=11),
            hovertemplate="<b>%{label}</b><br>%{value:,} (%{percent})<extra></extra>",
        )
    )
    return theme(fig, h)


def line_trend(df: pd.DataFrame, x: str, y: str, label: str = "Cases", color: str | None = None, h: int = 260) -> go.Figure:
    if df.empty:
        return empty_fig(h=h)
    clr = color or C["accent"]
    fig = go.Figure(
        go.Scatter(
            x=df[x],
            y=df[y],
            mode="lines+markers",
            line=dict(color=clr, width=2.5),
            marker=dict(color=clr, size=7),
            fill="tozeroy",
            fillcolor=f"rgba({int(clr[1:3],16)},{int(clr[3:5],16)},{int(clr[5:],16)},0.09)",
            hovertemplate=f"<b>%{{x}}</b><br>{label}: %{{y:,}}<extra></extra>",
        )
    )
    fig.update_layout(xaxis_tickangle=-25, yaxis_title=label, xaxis_title=None)
    return theme(fig, h)


def multi_line(traces: list[dict], h: int = 280) -> go.Figure:
    fig = go.Figure()
    for trace in traces:
        clr = trace.get("color", C["accent"])
        fig.add_trace(
            go.Scatter(
                x=trace["x"],
                y=trace["y"],
                name=trace["name"],
                mode="lines+markers",
                line=dict(color=clr, width=2.2, dash=trace.get("dash", "solid")),
                marker=dict(color=clr, size=6),
                hovertemplate=f"<b>%{{x}}</b><br>{trace['name']}: %{{y:,}}<extra></extra>",
            )
        )
    fig.update_layout(
        xaxis_tickangle=-25,
        yaxis_title="Cases",
        xaxis_title=None,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return theme(fig, h)


def bar_v(df: pd.DataFrame, x: str, y: str, color_scale: list, h: int = 280) -> go.Figure:
    if df.empty:
        return empty_fig(h=h)
    fig = go.Figure(
        go.Bar(
            x=df[x],
            y=df[y],
            text=df[y].apply(lambda v: f"{v:,}"),
            textposition="inside",
            insidetextanchor="end",
            textfont=dict(color="white", size=11),
            marker=dict(color=df[y], colorscale=color_scale, showscale=False),
            hovertemplate="<b>%{x}</b><br>%{y:,}<extra></extra>",
        )
    )
    fig.update_layout(xaxis_tickangle=-30, yaxis_title=None)
    return theme(fig, h)


def prr_scatter(df: pd.DataFrame, h: int = 420) -> go.Figure:
    if df.empty:
        return empty_fig(h=h)
    df = df.copy()
    df["log2_prr"] = np.log2(df["PRR"].clip(lower=0.1))
    df["log10_n"] = np.log10(df["N_DR"].clip(lower=1))
    color_map = {"HIGH": C["high"], "MEDIUM": C["medium"], "LOW": C["low"]}
    fig = go.Figure()
    for level in ["HIGH", "MEDIUM", "LOW"]:
        sub = df[df["signal"] == level]
        if sub.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=sub["log10_n"],
                y=sub["log2_prr"],
                mode="markers",
                name=level,
                marker=dict(color=color_map[level], size=5, opacity=0.7),
                text=sub.apply(lambda row: f"<b>{row['drug']}</b> × {row['pt']}<br>PRR = {row['PRR']:.1f} &nbsp; N = {row['N_DR']:,}", axis=1),
                hovertemplate="%{text}<extra></extra>",
            )
        )
    fig.add_hline(y=1, line=dict(color=C["medium"], dash="dot", width=1))
    fig.add_annotation(text="PRR = 2", x=df["log10_n"].max() * 0.98, y=1.15, showarrow=False, font=dict(color=C["medium"], size=10))
    fig.update_layout(xaxis_title="log₁₀ co-occurrence count", yaxis_title="log₂ PRR", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return theme(fig, h)


def add_prr_ci(df: pd.DataFrame) -> pd.DataFrame:
    a = df["N_DR"].to_numpy(dtype=float).clip(min=1)
    nd = df["N_D"].to_numpy(dtype=float)
    nr = df["N_R"].to_numpy(dtype=float)
    nt = df["N_total"].to_numpy(dtype=float)
    se = np.sqrt(
        1 / a
        + np.where(nd - a > 0, 1 / np.maximum(nd - a, 1e-10), 0)
        + np.where(nr - a > 0, 1 / np.maximum(nr - a, 1e-10), 0)
        + np.where(nt - nd - nr + a > 0, 1 / np.maximum(nt - nd - nr + a, 1e-10), 0)
    )
    ln_prr = np.log(df["PRR"].clip(lower=0.01))
    out = df.copy()
    out["CI_lower"] = np.exp(ln_prr - 1.96 * se).round(2)
    out["CI_upper"] = np.exp(ln_prr + 1.96 * se).round(2)
    return out


def forest_plot(df: pd.DataFrame, h: int | None = None) -> go.Figure:
    if df.empty:
        return empty_fig(h=300)
    df = df.head(20).copy().sort_values("PRR")
    color_map = {"HIGH": C["high"], "MEDIUM": C["medium"], "LOW": C["low"]}
    colors = [color_map.get(signal, C["muted"]) for signal in df["signal"]]
    a = df["N_DR"].to_numpy(dtype=float)
    nd = df["N_D"].to_numpy(dtype=float)
    nr = df["N_R"].to_numpy(dtype=float)
    nt = df["N_total"].to_numpy(dtype=float)
    se = np.sqrt(
        np.where(a > 0, 1 / a, 1)
        + np.where(nd - a > 0, 1 / (nd - a), 1)
        + np.where(nr - a > 0, 1 / (nr - a), 1)
        + np.where(nt - nd - nr + a > 0, 1 / (nt - nd - nr + a), 1)
    )
    ln_prr = np.log(df["PRR"].clip(lower=0.01))
    ci_lo = np.exp(ln_prr - 1.96 * se)
    ci_hi = np.exp(ln_prr + 1.96 * se)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["PRR"],
            y=df["pt"],
            mode="markers",
            marker=dict(color=colors, size=9, symbol="diamond"),
            error_x=dict(
                type="data",
                symmetric=False,
                array=ci_hi - df["PRR"].to_numpy(),
                arrayminus=df["PRR"].to_numpy() - ci_lo,
                color=C["muted"],
                thickness=1.5,
            ),
            hovertemplate="<b>%{y}</b><br>PRR = %{x:.2f}<extra></extra>",
        )
    )
    fig.add_vline(x=2, line=dict(color=C["medium"], dash="dot", width=1))
    fig.update_layout(xaxis_title="Proportional Reporting Ratio (95% CI)", yaxis_title=None, xaxis_type="log")
    return theme(fig, h or max(300, len(df) * 24 + 60))

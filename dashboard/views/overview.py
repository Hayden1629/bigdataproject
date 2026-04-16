from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

import data_loader as dl
import queries as qr
from ui import kpi_card, line_trend, sec, theme


def render() -> None:
    with st.spinner("Loading overview..."):
        gk = qr.global_kpis()
        global_trend = qr.global_quarterly_trend()
        drug_sum = dl.load_drug_summary()
        reac_sum = dl.load_reac_summary()

    death_pct_global = round(gk["n_deaths"] / gk["n_cases"] * 100, 2) if gk["n_cases"] else 0
    kpis_html = "".join(
        [
            kpi_card("Total Cases", f"{gk['n_cases']:,}"),
            kpi_card("Deaths Reported", f"{gk['n_deaths']:,}", f"{death_pct_global}% of cases", "kpi-danger"),
            kpi_card("Hospitalisations", f"{gk['n_hosp']:,}"),
            kpi_card("Life-threatening", f"{gk['n_lt']:,}"),
            kpi_card("Unique Drug Entities", f"{gk['n_drugs']:,}"),
            kpi_card("Unique Reaction Categories (MedDRA PTs)", f"{gk['n_pts']:,}"),
        ]
    )
    st.markdown(f'<div class="kpi-row">{kpis_html}</div>', unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        sec("Top 15 Drugs by Report Volume")
        if drug_sum is not None:
            top15d = drug_sum.head(15)[["drug", "n_cases", "n_deaths"]].copy()
            fig_td = go.Figure(
                go.Bar(
                    x=top15d["n_cases"],
                    y=top15d["drug"],
                    orientation="h",
                    marker=dict(color=top15d["n_cases"], colorscale=[[0, "#1d4ed8"], [1, "#60a5fa"]], showscale=False),
                    text=top15d["n_cases"].apply(lambda v: f"{v:,}"),
                    textposition="inside",
                    insidetextanchor="end",
                    textfont=dict(color="white", size=11),
                    hovertemplate="<b>%{y}</b><br>Cases: %{x:,}<extra></extra>",
                )
            )
            fig_td.update_layout(yaxis=dict(categoryorder="total ascending"), xaxis_title=None)
            st.plotly_chart(theme(fig_td, 420), width='stretch')

    with col_b:
        sec("Top 15 Reactions by Report Volume")
        if reac_sum is not None:
            top15r = reac_sum.head(15)[["pt", "n_cases"]].copy()
            fig_tr = go.Figure(
                go.Bar(
                    x=top15r["n_cases"],
                    y=top15r["pt"],
                    orientation="h",
                    marker=dict(color=top15r["n_cases"], colorscale=[[0, "#7c3aed"], [1, "#c4b5fd"]], showscale=False),
                    text=top15r["n_cases"].apply(lambda v: f"{v:,}"),
                    textposition="inside",
                    insidetextanchor="end",
                    textfont=dict(color="white", size=11),
                    hovertemplate="<b>%{y}</b><br>Cases: %{x:,}<extra></extra>",
                )
            )
            fig_tr.update_layout(yaxis=dict(categoryorder="total ascending"), xaxis_title=None)
            st.plotly_chart(theme(fig_tr, 420), width='stretch')

    sec("Quarter-over-Quarter Trends")
    trend_d = qr.trending_drugs(top_n=10)
    trend_r = qr.trending_reactions(top_n=10)
    t1, t2 = st.columns(2)
    with t1:
        if not trend_d.empty:
            prev_q_lbl = trend_d["prev_q"].iloc[0]
            curr_q_lbl = trend_d["curr_q"].iloc[0]
            st.caption(f"Drugs with largest case increase: {prev_q_lbl} → {curr_q_lbl}")
            fig_td2 = go.Figure(
                go.Bar(
                    x=trend_d["delta"],
                    y=trend_d["drug"],
                    orientation="h",
                    text=trend_d.apply(lambda r: f"+{r['delta']:,}  ({r['pct_change']:+.0f}%)", axis=1),
                    textposition="inside",
                    insidetextanchor="end",
                    textfont=dict(color="white", size=11),
                    marker=dict(color=trend_d["delta"], colorscale=[[0, "#164e63"], [1, "#22d3ee"]], showscale=False),
                    hovertemplate="<b>%{y}</b><br>+%{x:,} cases<extra></extra>",
                )
            )
            fig_td2.update_layout(yaxis=dict(categoryorder="total ascending"), xaxis_title="Case increase")
            st.plotly_chart(theme(fig_td2, 320), width='stretch')
    with t2:
        if not trend_r.empty:
            prev_q_lbl = trend_r["prev_q"].iloc[0]
            curr_q_lbl = trend_r["curr_q"].iloc[0]
            st.caption(f"Reactions with largest case increase: {prev_q_lbl} → {curr_q_lbl}")
            fig_tr2 = go.Figure(
                go.Bar(
                    x=trend_r["delta"],
                    y=trend_r["reaction"],
                    orientation="h",
                    text=trend_r.apply(lambda r: f"+{r['delta']:,}  ({r['pct_change']:+.0f}%)", axis=1),
                    textposition="inside",
                    insidetextanchor="end",
                    textfont=dict(color="white", size=11),
                    marker=dict(color=trend_r["delta"], colorscale=[[0, "#4a1d96"], [1, "#c4b5fd"]], showscale=False),
                    hovertemplate="<b>%{y}</b><br>+%{x:,} cases<extra></extra>",
                )
            )
            fig_tr2.update_layout(yaxis=dict(categoryorder="total ascending"), xaxis_title="Case increase")
            st.plotly_chart(theme(fig_tr2, 320), width='stretch')

    sec("Reports Per Quarter")
    st.plotly_chart(line_trend(global_trend, "quarter", "case_count", "Cases"), width='stretch')

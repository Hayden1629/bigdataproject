from __future__ import annotations

import pandas as pd
import streamlit as st

import data_loader as dl
import queries as qr
import reaction_search as reaction_search_module
import signal_detection as sd
from ui import C, bar_h, donut, forest_plot, kpi_card, line_trend, quarter_delta_text, sec, summary_note
from logger import get_logger

log = get_logger(__name__)


def render(*, all_pts: list[str], q_key: str, role_cod: str, top_n: int) -> None:
    st.caption("Use plain language if you want. The app maps common phrases to MedDRA terms before analyzing the signal.")
    reac_query = st.text_input(
        "Reaction search",
        placeholder="Plain English or clinical term  —  e.g. heart attack, hair loss, throwing up, myocardial infarction",
        key="reac_input",
        label_visibility="collapsed",
    )

    if reac_query:
        log.info("Reaction Explorer: user searched for %r  (role=%s, q_key=%s)", reac_query, role_cod, q_key[:40])

    if not reac_query:
        st.markdown(
            '<div class="note"><strong>Try one of these:</strong> heart attack, hair loss, throwing up, liver damage, memory loss.</div>',
            unsafe_allow_html=True,
        )
        with st.spinner("Loading reaction data..."):
            reac_sum2 = dl.load_reac_summary()
        if reac_sum2 is not None:
            sec("Most Reported Adverse Reactions")
            top20r = reac_sum2.head(20).copy()
            top20r.columns = [c.replace("_", " ").title() for c in top20r.columns]
            st.dataframe(
                top20r.style.format({"N Cases": "{:,}", "N Deaths": "{:,}", "Death Pct": "{:.2f}%"}),
                width='stretch',
                hide_index=True,
                height=580,
            )
        return

    with st.spinner("Mapping to MedDRA terms..."):
        pt_hits = reaction_search_module.search_reactions(reac_query, all_pts, max_results=25)
    if not pt_hits:
        log.warning("Reaction Explorer: no MedDRA matches for %r", reac_query)
        st.error(f"No MedDRA terms matched **{reac_query}**. Try different phrasing.")
        return
    log.info("Reaction Explorer: %r → %d MedDRA terms  top: %s",
             reac_query, len(pt_hits), [p for p, _ in pt_hits[:3]])

    st.caption(f"{len(pt_hits)} MedDRA terms matched for '{reac_query}'.")
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
        st.dataframe(match_tbl, width='stretch', hide_index=True, height=260)

    if not selected_pts:
        st.info("Select at least one Preferred Term.")
        return

    pk = "|".join(sorted(selected_pts))
    rk = qr.reaction_kpis(pk, q_key)
    death_pct_r = round(rk["n_deaths"] / rk["n_cases"] * 100, 1) if rk["n_cases"] else 0
    rk_html = "".join(
        [
            kpi_card("Cases Reporting Reaction", f"{rk['n_cases']:,}"),
            kpi_card("Deaths in Those Cases", f"{rk['n_deaths']:,}", f"{death_pct_r}%", "kpi-danger"),
            kpi_card("Any Serious Outcome", f"{rk['n_serious']:,}"),
            kpi_card("MedDRA Terms Selected", str(len(selected_pts))),
        ]
    )
    st.markdown(f'<div class="kpi-row">{rk_html}</div>', unsafe_allow_html=True)

    top_d = qr.reaction_top_drugs(pk, role_cod, q_key, top_n)
    outc_r = qr.reaction_outcomes(pk, q_key)
    tr = qr.reaction_trend(pk, q_key)
    reac_sigs = sd.signals_for_reaction(selected_pts, min_signal="MEDIUM", top_n=20)
    top_drug_note = f"Top associated drug: {top_d.iloc[0]['drug_label']} ({int(top_d.iloc[0]['case_count']):,} cases, {top_d.iloc[0]['pct']:.1f}% of matched reaction cases)." if not top_d.empty else ""
    reaction_trend_note = f"Recent volume change: {quarter_delta_text(tr)}." if not tr.empty else ""
    reaction_signal_note = f"Strongest elevated drug signal: {reac_sigs.iloc[0]['drug']} (PRR {reac_sigs.iloc[0]['PRR']:.2f}, N={int(reac_sigs.iloc[0]['N_DR']):,})." if not reac_sigs.empty else ""
    summary_note("At A Glance", [top_drug_note, reaction_trend_note, reaction_signal_note])

    cl, cr = st.columns([3, 2])
    with cl:
        sec(f"Top Associated Drugs (role: {role_cod})")
        st.plotly_chart(bar_h(top_d, "case_count", "drug_label", [[0, "#7c3aed"], [1, "#c4b5fd"]], h=max(400, top_n * 22 + 80)), width='stretch')
    with cr:
        sec("Outcome Distribution")
        st.plotly_chart(donut(outc_r, "count", "outcome_label", h=340), width='stretch')

    sec("Quarterly Report Volume")
    st.plotly_chart(line_trend(tr, "quarter", "case_count", "Reports", color=C["purple"]), width='stretch')

    sec("Drug Signals for This Reaction (PRR)")
    if not reac_sigs.empty:
        sr1, sr2 = st.columns([2, 3])
        with sr1:
            sd_disp = reac_sigs.rename(columns={"drug": "Drug", "N_DR": "N (D+R)", "PRR": "PRR", "chi2": "Chi-sq", "signal": "Signal"})
            st.dataframe(
                sd_disp[["Signal", "Drug", "PRR", "N (D+R)", "Chi-sq"]],
                width='stretch',
                hide_index=True,
                height=360,
                column_config={
                    "PRR": st.column_config.NumberColumn("PRR", format="%.2f"),
                    "Chi-sq": st.column_config.NumberColumn("Chi-sq", format="%.1f"),
                },
            )
        with sr2:
            fp_df = reac_sigs.rename(columns={"drug": "pt"}).copy()
            if "N_total" not in fp_df.columns:
                fp_df["N_total"] = dl.get_n_total()
            st.markdown('<div style="font-size:.68rem;color:#8b949e;margin-bottom:4px;">FOREST PLOT — drugs with elevated PRR for this reaction</div>', unsafe_allow_html=True)
            st.plotly_chart(forest_plot(fp_df, h=360), width='stretch')
    else:
        st.info("No elevated PRR signals found for the selected terms.")

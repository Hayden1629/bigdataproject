from __future__ import annotations

import re
from datetime import datetime

import pandas as pd
import streamlit as st

import data_loader as dl
import drug_normalizer as drug_normalizer
import queries as qr
import research_connector as research_connector
import signal_detection as sd
import signal_interpreter as signal_interpreter
from ui import C, add_prr_ci, badge, bar_h, bar_v, donut, forest_plot, kpi_card, line_trend, sec, summary_note, quarter_delta_text
from logger import get_logger

log = get_logger(__name__)


def render(*, tables: dict[str, pd.DataFrame], q_key: str, role_cod: str, top_n: int) -> None:
    st.caption("Start with a drug name to see the core safety profile first. External research lookups are optional and can be loaded on demand.")
    drug_query = st.text_input(
        "Drug search",
        placeholder="Brand name, generic name, or active ingredient  —  e.g. naloxone, Mounjaro, dupilumab, warfarin",
        key="drug_input",
        label_visibility="collapsed",
    )

    if drug_query:
        log.info("Drug Explorer: user searched for %r  (role=%s, q_key=%s)", drug_query, role_cod, q_key[:40])

    if not drug_query:
        st.markdown(
            '<div class="note"><strong>Try one of these:</strong> ozempic, mounjaro, keytruda, dupilumab, warfarin, naloxone.</div>',
            unsafe_allow_html=True,
        )
        drug_sum2 = dl.load_drug_summary()
        if drug_sum2 is not None:
            sec("Most Reported Drugs — Full Dataset")
            top20 = drug_sum2.head(20).copy()
            top20.columns = [c.replace("_", " ").title() for c in top20.columns]
            st.dataframe(
                top20.style.format({"N Cases": "{:,}", "N Deaths": "{:,}", "Death Pct": "{:.2f}%"}),
                width='stretch',
                hide_index=True,
                height=580,
            )
        return

    # ── 1. Drug lookup ────────────────────────────────────────────────────────
    with st.spinner("Looking up drug names…"):
        rxn = drug_normalizer.rxnorm_lookup(drug_query)
        matched = drug_normalizer.find_faers_names(drug_query, tables["drug"])

    if not matched:
        log.warning("Drug Explorer: no FAERS matches for %r", drug_query)
        st.error(f"No FAERS records found for **{drug_query}**. Try a different spelling, the generic name, or a brand name.")
        return

    log.info("Drug Explorer: %r → %d FAERS names  canon=%r", drug_query, len(matched), rxn.get("canonical"))

    nk = qr._names_key(matched)
    canon = rxn.get("canonical") or drug_query.title()
    related = rxn.get("related", [])
    rxcui_tag = f" &nbsp;·&nbsp; RxCUI `{rxn['rxcui']}`" if rxn.get("rxcui") else ""

    # Drug class + header
    with st.spinner("Loading drug classification…"):
        drug_classes = research_connector.get_drug_class(rxn.get("rxcui", "") or "")

    class_tag = ""
    if drug_classes:
        atc = [c for c in drug_classes if c["source"] == "ATC"]
        va  = [c for c in drug_classes if c["source"] == "VA"]
        primary = (atc or va)[0]["class_name"].title()
        class_tag = f' &nbsp;·&nbsp; <span style="color:{C["muted"]};font-size:.85em;">{primary}</span>'

    st.markdown(f"**{canon}**{rxcui_tag}{class_tag}", unsafe_allow_html=True)
    if related:
        chips_html = " ".join(f'<span class="chip">{n}</span>' for n in sorted(related)[:50])
        st.markdown(f'<div class="chips">{chips_html}</div>', unsafe_allow_html=True)
    st.caption(f"{len(matched)} FAERS drug name strings matched. Current role filter: {role_cod}.")

    # FDA approval card + boxed warning
    with st.spinner("Loading FDA regulatory info…"):
        fda_records = research_connector.get_fda_approval_info(canon)
        label = research_connector.get_drug_label(canon)

    if fda_records:
        fda = fda_records[0]

        def _fda_field(label_text: str, value: str) -> str:
            return f'<div class="fda-field"><div class="fda-label">{label_text}</div><div class="fda-value">{value}</div></div>'

        fields = [
            _fda_field("Application Type", fda["app_type"]),
            _fda_field("Application No.", fda["application_number"]),
            _fda_field("Sponsor", fda["sponsor"]),
            _fda_field("First Approval", fda["first_approval"]),
            _fda_field("Latest Action", fda["latest_action"]),
            _fda_field("Dosage Forms", fda["dosage_forms"] or "—"),
            _fda_field("Route(s)", fda["routes"] or "—"),
            _fda_field("Marketing Status", fda["marketing_status"] or "—"),
            _fda_field("Links", f'<a href="{fda["fda_url"]}" target="_blank">FDA Portal</a> &nbsp;·&nbsp; <a href="{fda["ob_url"]}" target="_blank">Orange Book</a>'),
        ]
        st.markdown(f'<div class="fda-card">{"".join(fields)}</div>', unsafe_allow_html=True)
        if len(fda_records) > 1:
            st.caption(f"{len(fda_records)} FDA applications found — showing primary application ({fda['application_number']})")

    if label.get("boxed_warning"):
        bw_text = label["boxed_warning"][:600]
        if len(label["boxed_warning"]) > 600:
            bw_text += "…"
        st.markdown(
            f'<div style="background:#FFF3F3;border-left:4px solid {C["high"]};border-radius:0 6px 6px 0;padding:10px 16px;margin:6px 0 14px;">'
            f'<div style="font-size:.60rem;font-weight:700;color:{C["high"]};text-transform:uppercase;letter-spacing:.10em;margin-bottom:4px;">Boxed Warning (FDA Label)</div>'
            f'<div style="font-size:.75rem;color:{C["text"]};line-height:1.55;">{bw_text}</div></div>',
            unsafe_allow_html=True,
        )

    # ── 2. KPIs ───────────────────────────────────────────────────────────────
    with st.spinner("Computing case statistics…"):
        kpi = qr.drug_kpis(nk, role_cod, q_key)

    serious_pct = round(kpi["n_serious"] / kpi["n_cases"] * 100, 1) if kpi["n_cases"] else 0
    death_cls = "kpi-danger" if kpi["death_pct"] > 10 else "kpi-warn" if kpi["death_pct"] > 5 else ""
    k_html = "".join([
        kpi_card("Total Cases", f"{kpi['n_cases']:,}"),
        kpi_card("Deaths", f"{kpi['n_deaths']:,}", f"{kpi['death_pct']}% of cases", death_cls),
        kpi_card("Hospitalisations", f"{kpi['n_hosp']:,}"),
        kpi_card("Life-threatening", f"{kpi['n_lt']:,}"),
        kpi_card("Any Serious Outcome", f"{kpi['n_serious']:,}", f"{serious_pct}%"),
    ])
    st.markdown(f'<div class="kpi-row">{k_html}</div>', unsafe_allow_html=True)

    # ── 3. Adverse event profile ──────────────────────────────────────────────
    with st.spinner("Loading adverse event profile…"):
        trend  = qr.drug_trend(nk, role_cod, q_key)
        reac_df = qr.drug_top_reactions(nk, role_cod, q_key, top_n)
        outc_df = qr.drug_outcomes(nk, role_cod, q_key)

    lead_reaction = f"Top reported reaction: {reac_df.iloc[0]['pt']} ({int(reac_df.iloc[0]['count']):,} reports, {reac_df.iloc[0]['pct']:.1f}% of matched cases)." if not reac_df.empty else ""
    recent_change = f"Recent volume change: {quarter_delta_text(trend)}." if not trend.empty else ""

    c_left, c_right = st.columns([3, 2])
    with c_left:
        sec("Top Adverse Reactions (MedDRA PTs)")
        st.plotly_chart(bar_h(reac_df, "count", "pt", [[0, "#1d4ed8"], [1, "#60a5fa"]], h=max(400, top_n * 22 + 80)), width='stretch')
    with c_right:
        sec("Outcome Distribution")
        st.plotly_chart(donut(outc_df, "count", "outcome_label", h=340), width='stretch')

    sec("Quarterly Report Volume")
    trend_fig = line_trend(trend, "quarter", "case_count", "Reports")
    if fda_records and not trend.empty:
        appr_raw = fda_records[0].get("first_approval", "")
        if appr_raw and len(appr_raw) >= 7:
            try:
                dt = datetime.strptime(appr_raw[:10], "%Y-%m-%d")
                appr_q = f"{dt.year}Q{(dt.month - 1) // 3 + 1}"
                quarters_list = trend["quarter"].tolist()
                if appr_q in quarters_list:
                    trend_fig.add_vline(x=quarters_list.index(appr_q), line=dict(color=C["accent"], dash="dash", width=1.5), annotation_text=f"FDA Approved ({appr_q})", annotation_position="top left", annotation_font=dict(size=10, color=C["accent"]))
                elif appr_q < quarters_list[0]:
                    trend_fig.add_annotation(x=quarters_list[0], y=1, xref="x", yref="paper", text=f"FDA Approved {appr_raw[:7]}", showarrow=False, xanchor="left", font=dict(size=9, color=C["muted"]), bgcolor=C["surface"], borderpad=3)
            except Exception:
                pass
    st.plotly_chart(trend_fig, width='stretch')

    # ── 4. Demographics ───────────────────────────────────────────────────────
    with st.spinner("Loading patient demographics…"):
        demog  = qr.drug_demographics(nk, role_cod, q_key)
        ctry_df = qr.drug_countries(nk, role_cod, q_key, top_n=10)

    sec("Patient Demographics & Geography")
    d1, d2, d3, d4 = st.columns(4)
    with d1:
        st.markdown('<div style="text-align:center;font-size:.68rem;color:#8b949e;">SEX</div>', unsafe_allow_html=True)
        st.plotly_chart(donut(demog["sex"], "count", "sex_label", [C["accent"], "#ec4899", C["muted"]], h=220), width='stretch')
    with d2:
        st.markdown('<div style="text-align:center;font-size:.68rem;color:#8b949e;">AGE GROUP</div>', unsafe_allow_html=True)
        st.plotly_chart(bar_v(demog["age_grp"], "age_group_label", "count", [[0, "#1e3a5f"], [1, "#3b82f6"]], h=220), width='stretch')
    with d3:
        st.markdown('<div style="text-align:center;font-size:.68rem;color:#8b949e;">REPORTER</div>', unsafe_allow_html=True)
        st.plotly_chart(bar_v(demog["reporter"], "reporter", "count", [[0, "#1a3a2a"], [1, "#3fb950"]], h=220), width='stretch')
    with d4:
        sec("Top Reporter Countries")
        if not ctry_df.empty:
            st.dataframe(ctry_df[["country", "count", "pct"]].rename(columns={"count": "Cases", "pct": "%"}), width='stretch', hide_index=True, height=220)

    # ── 5. Clinical context ───────────────────────────────────────────────────
    with st.spinner("Loading clinical context…"):
        indi_df  = qr.drug_indications(nk, role_cod, q_key, top_n=12)
        comed_df = qr.drug_concomitants(nk, role_cod, q_key, top_n=12)

    sec("Clinical Context")
    ci1, ci2 = st.columns(2)
    with ci1:
        st.markdown('<div style="font-size:.72rem;color:#8b949e;margin-bottom:6px;">PRESCRIBED FOR (Top Indications)</div>', unsafe_allow_html=True)
        if not indi_df.empty:
            st.plotly_chart(bar_h(indi_df, "count", "indication", [[0, "#2d1b69"], [1, "#a78bfa"]], h=max(300, len(indi_df) * 22 + 60)), width='stretch')
        else:
            st.caption("No indication data found for this drug.")
    with ci2:
        st.markdown('<div style="font-size:.72rem;color:#8b949e;margin-bottom:6px;">COMMONLY CO-REPORTED DRUGS</div>', unsafe_allow_html=True)
        if not comed_df.empty:
            st.plotly_chart(bar_h(comed_df, "count", "drug", [[0, "#1a3a3a"], [1, "#22d3ee"]], h=max(300, len(comed_df) * 22 + 60)), width='stretch')
        else:
            st.caption("No concomitant drug data found.")

    # ── 6. Pharmacovigilance signals ──────────────────────────────────────────
    with st.spinner("Loading pharmacovigilance signals…"):
        sig_df = sd.signals_for_drug(matched, min_signal="LOW", top_n=25, min_n_dr=10)

    # Now that we have all data, render the At A Glance summary
    top_indication = f"Most common linked indication: {indi_df.iloc[0]['indication']}." if not indi_df.empty else ""
    strongest_signal = f"Strongest PRR signal: {sig_df.iloc[0]['pt']} (PRR {sig_df.iloc[0]['PRR']:.2f}, N={int(sig_df.iloc[0]['N_DR']):,}, {sig_df.iloc[0]['signal'].lower()})." if not sig_df.empty else ""
    summary_note("At A Glance", [lead_reaction, recent_change, strongest_signal, top_indication])

    sec("Pharmacovigilance Signals (PRR)")
    if not sig_df.empty:
        cnt_h = int((sig_df["signal"] == "HIGH").sum())
        cnt_m = int((sig_df["signal"] == "MEDIUM").sum())
        cnt_l = int((sig_df["signal"] == "LOW").sum())
        st.markdown(f"Showing {len(sig_df)} signals — {badge('HIGH')} **{cnt_h}** &nbsp; {badge('MEDIUM')} **{cnt_m}** &nbsp; {badge('LOW')} **{cnt_l}**", unsafe_allow_html=True)
        fp1, fp2 = st.columns([2, 3])
        with fp1:
            sig_disp = add_prr_ci(sig_df).rename(columns={"pt": "Preferred Term", "N_DR": "N (D+R)", "N_D": "N (Drug)", "N_R": "N (Rxn)", "PRR": "PRR", "CI_lower": "CI Low", "CI_upper": "CI High", "chi2": "Chi-sq", "signal": "Signal"})
            st.dataframe(
                sig_disp[["Signal", "Preferred Term", "PRR", "CI Low", "CI High", "N (D+R)", "Chi-sq"]],
                width='stretch',
                hide_index=True,
                height=400,
                column_config={
                    "PRR": st.column_config.NumberColumn("PRR", format="%.2f"),
                    "CI Low": st.column_config.NumberColumn("CI Low", format="%.2f"),
                    "CI High": st.column_config.NumberColumn("CI High", format="%.2f"),
                    "Chi-sq": st.column_config.NumberColumn("Chi-sq", format="%.1f"),
                },
            )
        with fp2:
            st.markdown('<div style="font-size:.68rem;color:#8b949e;margin-bottom:4px;">FOREST PLOT — 95% CI on log scale</div>', unsafe_allow_html=True)
            st.plotly_chart(forest_plot(sig_df, h=400), width='stretch')
    else:
        st.info("No PRR signals found. Run `python3 dashboard/precompute.py` to generate the signal cache.")

    # ── 7. Optional external context (on demand) ──────────────────────────────
    with st.expander("Optional External Context", expanded=False):
        load_ai = bool(sig_df is not None and not sig_df.empty) and st.toggle("Generate AI interpretation", value=False, key=f"ai_{canon}", help="Uses an external model only when you turn this on.")
        load_research = st.toggle("Load live research and FDA enforcement context", value=False, key=f"research_{canon}", help="Fetches ClinicalTrials.gov, PubMed, and openFDA enforcement data on demand.")

        if load_ai:
            st.markdown("**AI Signal Interpretation**")
            with st.spinner("Generating signal summary..."):
                signals_csv_str = sig_df[["pt", "N_DR", "PRR", "chi2", "signal"]].head(15).to_csv(index=False)
                ai_summary = signal_interpreter.interpret_signals(drug_name=canon, signals_csv=signals_csv_str, n_cases=kpi["n_cases"], n_deaths=kpi["n_deaths"])
            if ai_summary:
                st.markdown(f'<div class="note" style="font-size:.80rem;color:{C["text"]};line-height:1.7;">{ai_summary}</div>', unsafe_allow_html=True)
            else:
                st.caption("AI interpretation unavailable — set ANTHROPIC_API_KEY or GROQ_API_KEY to enable.")

        if load_research:
            st.markdown("**Research Context**")
            rc_ct, rc_pm, rc_en = st.tabs(["Clinical Trials", "Literature (PubMed)", "Recalls & Enforcement"])
            ingredients = sorted([n for n in related if n.replace(" ", "").isalpha() and 5 <= len(n) <= 25], key=len)
            if ingredients:
                research_name = ingredients[0].title()
            else:
                bracket = re.search(r"\[([^\]]+)\]", canon)
                research_name = bracket.group(1).title() if bracket else drug_query.title()

            with rc_ct:
                with st.spinner(f"Searching ClinicalTrials.gov for {research_name}…"):
                    ct_df, ct_total = research_connector.search_clinical_trials(research_name, max_results=8, search_mode="intervention")
                if ct_df.empty:
                    st.caption(f"No clinical trials found for {research_name} on ClinicalTrials.gov.")
                else:
                    st.caption(f"{ct_total:,} total trials on ClinicalTrials.gov — showing top {len(ct_df)}")
                    header = f"background:{C['surface']};color:{C['muted']};font-size:.65rem;text-transform:uppercase;letter-spacing:.10em;padding:6px 10px;text-align:left;border-bottom:1px solid {C['border']};"
                    status_colors = {"RECRUITING": C["low"], "COMPLETED": C["muted"], "ACTIVE_NOT_RECRUITING": C["medium"], "NOT_YET_RECRUITING": C["blue"], "TERMINATED": C["high"]}
                    rows = ""
                    for _, row in ct_df.iterrows():
                        enroll = f"{int(row['enrollment']):,}" if str(row["enrollment"]).isdigit() else "—"
                        sc = status_colors.get(row["status"], C["muted"])
                        rows += f"<tr><td style='padding:6px 10px;white-space:nowrap;'><a href=\"{row['url']}\" target=\"_blank\" style=\"color:{C['blue']};text-decoration:none;\">{row['nct_id']}</a></td><td style='padding:6px 10px;font-size:.78rem;line-height:1.4;'>{row['title']}</td><td style='padding:6px 10px;white-space:nowrap;font-size:.75rem;color:{sc};'>{row['status']}</td><td style='padding:6px 10px;white-space:nowrap;font-size:.75rem;'>{row['phase']}</td><td style='padding:6px 10px;font-size:.73rem;color:{C['muted']};'>{str(row['sponsor'])[:40]}</td><td style='padding:6px 10px;text-align:right;font-size:.75rem;'>{enroll}</td></tr>"
                    st.markdown(f'<div style="overflow-x:auto;border:1px solid {C["border"]};border-radius:8px;"><table style="width:100%;border-collapse:collapse;font-family:Avenir Next,Segoe UI,Helvetica Neue,Arial,sans-serif;color:{C["text"]};"><thead><tr><th style="{header}">NCT ID</th><th style="{header}">Title</th><th style="{header}">Status</th><th style="{header}">Phase</th><th style="{header}">Sponsor</th><th style="{header};text-align:right;">Enrollment</th></tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)

            with rc_pm:
                pm_query = f"{research_name} adverse events"
                with st.spinner(f"Searching PubMed for '{pm_query}'…"):
                    pm_df, pm_total = research_connector.search_pubmed(pm_query, max_results=8, sort="relevance")
                if pm_df.empty:
                    st.caption(f"No PubMed results for '{pm_query}'.")
                else:
                    st.caption(f"{pm_total:,} total PubMed results — showing top {len(pm_df)}")
                    header = f"background:{C['surface']};color:{C['muted']};font-size:.65rem;text-transform:uppercase;letter-spacing:.10em;padding:6px 10px;text-align:left;border-bottom:1px solid {C['border']};"
                    rows = ""
                    for _, row in pm_df.iterrows():
                        doi_link = f'<a href="https://doi.org/{row["doi"]}" target="_blank" style="color:{C["muted"]};font-size:.70rem;">DOI</a>' if row["doi"] else ""
                        rows += f"<tr><td style='padding:6px 10px;white-space:nowrap;'><a href=\"{row['url']}\" target=\"_blank\" style=\"color:{C['blue']};font-size:.73rem;\">{row['pmid']}</a></td><td style='padding:6px 10px;font-size:.78rem;line-height:1.4;'><a href=\"{row['url']}\" target=\"_blank\" style=\"color:{C['text']};text-decoration:none;\">{row['title']}</a></td><td style='padding:6px 10px;font-size:.72rem;color:{C['muted']};'>{row['authors']}</td><td style='padding:6px 10px;font-size:.71rem;color:{C['muted']};font-style:italic;'>{row['journal']}</td><td style='padding:6px 10px;white-space:nowrap;font-size:.72rem;color:{C['muted']};'>{row['pub_date']}</td><td style='padding:6px 10px;'>{doi_link}</td></tr>"
                    st.markdown(f'<div style="overflow-x:auto;border:1px solid {C["border"]};border-radius:8px;"><table style="width:100%;border-collapse:collapse;font-family:Avenir Next,Segoe UI,Helvetica Neue,Arial,sans-serif;color:{C["text"]};"><thead><tr><th style="{header}">PMID</th><th style="{header}">Title</th><th style="{header}">Authors</th><th style="{header}">Journal</th><th style="{header}">Date</th><th style="{header}">DOI</th></tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)

            with rc_en:
                with st.spinner(f"Searching FDA enforcement for {research_name}…"):
                    en_records = research_connector.get_drug_enforcement(research_name, limit=8)
                if not en_records:
                    st.caption(f"No FDA recalls or enforcement actions found for {research_name}.")
                else:
                    cls_colors = {"Class I": C["high"], "Class II": C["medium"], "Class III": C["low"]}
                    for rec in en_records:
                        cls = rec["classification"]
                        cls_color = cls_colors.get(cls, C["muted"])
                        st.markdown(
                            f'<div style="border:1px solid {C["border"]};border-left:4px solid {cls_color};border-radius:0 8px 8px 0;padding:10px 14px;margin:6px 0;">'
                            f'<div style="display:flex;gap:12px;align-items:center;margin-bottom:4px;">'
                            f'<span style="font-size:.68rem;font-weight:700;color:{cls_color};text-transform:uppercase;">{cls}</span>'
                            f'<span style="font-size:.68rem;color:{C["muted"]};">{rec["recall_initiation_date"]}</span>'
                            f'<span style="font-size:.68rem;color:{C["muted"]};">{rec["status"]}</span>'
                            f'<span style="font-size:.68rem;color:{C["muted"]};">{rec["recalling_firm"]}</span></div>'
                            f'<div style="font-size:.78rem;color:{C["text"]};margin-bottom:2px;">{rec["reason_for_recall"]}</div>'
                            f'<div style="font-size:.70rem;color:{C["muted"]};">{rec["product_description"]}</div></div>',
                            unsafe_allow_html=True,
                        )
                    st.caption("Class I = most serious. Source: openFDA Drug Enforcement.")

    with st.expander("Matched drug name strings"):
        st.dataframe(pd.DataFrame({"FAERS Drug Name": sorted(matched)}), width='stretch', hide_index=True)

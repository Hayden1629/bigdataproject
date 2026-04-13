from __future__ import annotations

import streamlit as st

import data_loader as dl
import signal_detection as sd
from ui import add_prr_ci, kpi_card, prr_scatter, sec
from logger import get_logger

log = get_logger(__name__)


def render() -> None:
    with st.spinner("Loading signal table..."):
        prr_global = dl.load_prr_table()
    if prr_global is None or prr_global.empty:
        st.warning("PRR cache not found. Run `python3 dashboard/precompute.py`.")
        return

    fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 2])
    with fc1:
        sig_levels = st.multiselect("Signal level", ["HIGH", "MEDIUM", "LOW"], default=["HIGH", "MEDIUM"], key="sig_lev")
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
    filtered = prr_global[mask].sort_values(["chi2", "N_DR"], ascending=[False, False])
    log.info("Signal Intelligence: levels=%s  min_n=%d  drug_filter=%r  pt_filter=%r  → %d signals",
             sig_levels, min_n_sig, drug_txt or None, pt_txt or None, len(filtered))

    sc = sd.signal_counts()
    sig_k = "".join(
        [
            kpi_card("HIGH Signals", f"{sc['HIGH']:,}", "PRR≥4, N≥5, χ²≥4", "kpi-danger"),
            kpi_card("MEDIUM Signals", f"{sc['MEDIUM']:,}", "PRR≥2, N≥3, χ²≥4", "kpi-warn"),
            kpi_card("LOW Signals", f"{sc['LOW']:,}", "PRR≥1.5, N≥3", "kpi-ok"),
            kpi_card("Drugs Covered", f"{prr_global['drug'].nunique():,}"),
            kpi_card("Reactions Covered", f"{prr_global['pt'].nunique():,}"),
            kpi_card("Filtered Signals", f"{len(filtered):,}"),
        ]
    )
    st.markdown(f'<div class="kpi-row">{sig_k}</div>', unsafe_allow_html=True)

    sec("Signal Landscape — PRR vs. Report Volume")
    sample = filtered.sample(min(len(filtered), 4000), random_state=42) if len(filtered) > 4000 else filtered
    st.plotly_chart(prr_scatter(sample, h=430), use_container_width=True)
    st.caption(
        f"{len(sample):,} of {len(filtered):,} signals shown. "
        "Dotted line = PRR of 2 (Evans threshold). "
        "X-axis: log₁₀ co-occurrence count. Y-axis: log₂ PRR."
    )

    sec("Signal Table")
    disp = add_prr_ci(filtered.head(500)).rename(
        columns={
            "drug": "Drug",
            "pt": "Preferred Term",
            "N_DR": "N (D+R)",
            "N_D": "N (Drug)",
            "N_R": "N (Reaction)",
            "PRR": "PRR",
            "CI_lower": "CI Low",
            "CI_upper": "CI High",
            "ROR": "ROR",
            "chi2": "Chi-sq",
            "signal": "Signal",
        }
    )
    st.dataframe(
        disp[["Signal", "Drug", "Preferred Term", "PRR", "CI Low", "CI High", "N (D+R)", "N (Drug)", "N (Reaction)", "Chi-sq"]],
        use_container_width=True,
        hide_index=True,
        height=520,
        column_config={
            "PRR": st.column_config.NumberColumn("PRR", format="%.2f"),
            "CI Low": st.column_config.NumberColumn("CI Low", format="%.2f"),
            "CI High": st.column_config.NumberColumn("CI High", format="%.2f"),
            "Chi-sq": st.column_config.NumberColumn("Chi-sq", format="%.1f"),
        },
    )
    st.caption(f"{len(filtered):,} signals match current filters (showing top 500).")

    csv = filtered.head(10000).to_csv(index=False).encode()
    st.download_button("Download filtered signals (CSV)", data=csv, file_name="faers_signals.csv", mime="text/csv")
    st.markdown(
        '<div class="note">'
        '<b>Methodology:</b> PRR = (a/n<sub>exposed</sub>) / (c/n<sub>unexposed</sub>), '
        'where a = cases with both drug and reaction, n<sub>exposed</sub> = all cases with drug, '
        'c = cases with reaction but not drug, n<sub>unexposed</sub> = all cases without drug. '
        'Signal threshold: PRR ≥ 2, chi-squared ≥ 4, N ≥ 3 (Evans et al. 2001). '
        'Computed for top 500 drugs by report volume over 2023 Q3–2025 Q2.'
        '</div>',
        unsafe_allow_html=True,
    )

# commented out this tab for now.

# from __future__ import annotations

# import pandas as pd
# import plotly.graph_objects as go
# import streamlit as st

# import data_loader as dl
# import drug_normalizer as drug_normalizer
# import queries as qr
# import signal_detection as sd
# from ui import C, bar_h, donut, multi_line, sec, theme
# from logger import get_logger

# log = get_logger(__name__)


# def render(*, tables: dict[str, pd.DataFrame], role_cod: str, top_n: int) -> None:
#     st.markdown(
#         '<div class="note">Enter two drugs to compare their adverse event profiles side-by-side. '
#         'Useful for comparing therapeutic alternatives, biosimilars, or competing products in the same class.</div>',
#         unsafe_allow_html=True,
#     )

#     cmp_c1, cmp_c2 = st.columns(2)
#     with cmp_c1:
#         drug_a_query = st.text_input("Drug A", placeholder="e.g. dupilumab, Keytruda, ozempic", key="cmp_drug_a")
#     with cmp_c2:
#         drug_b_query = st.text_input("Drug B", placeholder="e.g. tralokinumab, pembrolizumab, tirzepatide", key="cmp_drug_b")

#     if drug_a_query and drug_b_query:
#         log.info("Drug Comparison: %r vs %r  (role=%s)", drug_a_query, drug_b_query, role_cod)

#     if not drug_a_query or not drug_b_query:
#         sec("Suggested Comparison Pairs")
#         examples = [
#             ("GLP-1 Agonists", "ozempic", "mounjaro", "Semaglutide vs Tirzepatide — GI profile and dosing errors"),
#             ("IL-4/IL-13 Inhibitors", "dupilumab", "tralokinumab", "Dupixent vs Adbry — atopic dermatitis biologics"),
#             ("PD-1 Inhibitors", "keytruda", "opdivo", "Pembrolizumab vs Nivolumab — immune checkpoint toxicity"),
#             ("Factor Xa Inhibitors", "apixaban", "rivaroxaban", "Eliquis vs Xarelto — bleeding and renal outcomes"),
#             ("TNF Inhibitors", "adalimumab", "etanercept", "Humira vs Enbrel — infection and injection site reactions"),
#             ("JAK Inhibitors", "tofacitinib", "baricitinib", "Xeljanz vs Olumiant — cardiovascular and thrombosis"),
#         ]
#         ex_df = pd.DataFrame(examples, columns=["Drug Class", "Drug A", "Drug B", "Clinical Question"])
#         st.dataframe(ex_df, width='stretch', hide_index=True)
#         st.caption("Type the Drug A and Drug B names above to generate the comparison.")
#         st.divider()
#         ds = dl.load_drug_summary()
#         if ds is not None:
#             sec("All Available Drugs (by Report Volume)")
#             st.dataframe(
#                 ds.head(20)[["drug", "n_cases", "n_deaths", "death_pct"]]
#                 .rename(columns={"drug": "Drug", "n_cases": "Cases", "n_deaths": "Deaths", "death_pct": "Death %"})
#                 .style.format({"Cases": "{:,}", "Deaths": "{:,}", "Death %": "{:.2f}%"}),
#                 width='stretch',
#                 hide_index=True,
#                 height=440,
#             )
#         return

#     with st.spinner("Looking up both drugs..."):
#         rxn_a = drug_normalizer.rxnorm_lookup(drug_a_query)
#         matched_a = drug_normalizer.find_faers_names(drug_a_query, tables["drug"])
#         rxn_b = drug_normalizer.rxnorm_lookup(drug_b_query)
#         matched_b = drug_normalizer.find_faers_names(drug_b_query, tables["drug"])

#     if not matched_a:
#         st.error(f"No FAERS records found for **{drug_a_query}**.")
#         return
#     if not matched_b:
#         st.error(f"No FAERS records found for **{drug_b_query}**.")
#         return

#     nk_a = qr._names_key(matched_a)
#     nk_b = qr._names_key(matched_b)
#     label_a = (rxn_a.get("canonical") or drug_a_query).title()
#     label_b = (rxn_b.get("canonical") or drug_b_query).title()
#     st.caption(f"{label_a}: {len(matched_a)} matched FAERS names. {label_b}: {len(matched_b)} matched FAERS names.")

#     if nk_a == nk_b:
#         st.warning("Both inputs resolved to the same drug entity. Enter two distinct drugs to compare.")
#         return

#     sec("Key Metrics Comparison")
#     kpi_a, kpi_b = qr.drug_comparison_kpis(nk_a, nk_b, role_cod)

#     def _pct(n: int, d: int) -> str:
#         return f"{n / d * 100:.1f}%" if d else "—"

#     cmp_rows = [
#         ("Total Cases", f"{kpi_a['n_cases']:,}", f"{kpi_b['n_cases']:,}"),
#         ("Deaths", f"{kpi_a['n_deaths']:,} ({_pct(kpi_a['n_deaths'], kpi_a['n_cases'])})", f"{kpi_b['n_deaths']:,} ({_pct(kpi_b['n_deaths'], kpi_b['n_cases'])})"),
#         ("Hospitalisations", f"{kpi_a['n_hosp']:,} ({_pct(kpi_a['n_hosp'], kpi_a['n_cases'])})", f"{kpi_b['n_hosp']:,} ({_pct(kpi_b['n_hosp'], kpi_b['n_cases'])})"),
#         ("Life-threatening", f"{kpi_a['n_lt']:,} ({_pct(kpi_a['n_lt'], kpi_a['n_cases'])})", f"{kpi_b['n_lt']:,} ({_pct(kpi_b['n_lt'], kpi_b['n_cases'])})"),
#         ("Any Serious Outcome", f"{kpi_a['n_serious']:,} ({_pct(kpi_a['n_serious'], kpi_a['n_cases'])})", f"{kpi_b['n_serious']:,} ({_pct(kpi_b['n_serious'], kpi_b['n_cases'])})"),
#     ]
#     st.dataframe(pd.DataFrame(cmp_rows, columns=["Metric", label_a, label_b]), width='stretch', hide_index=True)

#     sec("Quarterly Report Volume — Overlaid Trend")
#     trend_merged = qr.drug_comparison_trend(nk_a, nk_b, role_cod)
#     if not trend_merged.empty:
#         cols_ab = [c for c in trend_merged.columns if c != "quarter"]
#         if len(cols_ab) >= 2:
#             traces = [
#                 {"x": trend_merged["quarter"], "y": trend_merged[cols_ab[0]], "name": label_a, "color": C["accent"]},
#                 {"x": trend_merged["quarter"], "y": trend_merged[cols_ab[1]], "name": label_b, "color": C["teal"], "dash": "dot"},
#             ]
#             st.plotly_chart(multi_line(traces, h=300), width='stretch')

#     sec("Top Shared Adverse Reactions (Reports per 1,000 Cases)")
#     shared_rxn = qr.drug_comparison_shared_reactions(nk_a, nk_b, role_cod, top_n=top_n)
#     if not shared_rxn.empty:
#         shared_rxn_sorted = shared_rxn.sort_values("rate_a", ascending=True)
#         fig_shared = go.Figure()
#         fig_shared.add_trace(go.Bar(y=shared_rxn_sorted["pt"], x=shared_rxn_sorted["rate_a"], name=label_a, orientation="h", marker=dict(color=C["accent"]), hovertemplate=f"<b>%{{y}}</b><br>{label_a}: %{{x:.1f}} per 1k<extra></extra>"))
#         fig_shared.add_trace(go.Bar(y=shared_rxn_sorted["pt"], x=shared_rxn_sorted["rate_b"], name=label_b, orientation="h", marker=dict(color=C["teal"]), hovertemplate=f"<b>%{{y}}</b><br>{label_b}: %{{x:.1f}} per 1k<extra></extra>"))
#         fig_shared.update_layout(barmode="group", yaxis=dict(categoryorder="array", categoryarray=shared_rxn_sorted["pt"].tolist()), xaxis_title="Reports per 1,000 cases", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
#         st.plotly_chart(theme(fig_shared, max(400, len(shared_rxn) * 28 + 80)), width='stretch')
#         st.caption(f"Rate = (reaction reports for drug) / (total drug cases) × 1,000. Shows reactions appearing in both {label_a} and {label_b} case sets.")
#     else:
#         st.info("No shared reactions found with sufficient case counts.")

#     sec("Top Reactions — Individual Rankings")
#     rxn_a_df, rxn_b_df = qr.drug_comparison_top_reactions(nk_a, nk_b, role_cod, top_n=15)
#     ca, cb = st.columns(2)
#     with ca:
#         st.markdown(f'<div style="font-size:.72rem;color:{C["muted"]};margin-bottom:6px;">{label_a.upper()}</div>', unsafe_allow_html=True)
#         st.plotly_chart(bar_h(rxn_a_df, "count", "pt", [[0, "#1d4ed8"], [1, "#60a5fa"]], h=max(380, 15 * 22 + 80)), width='stretch')
#     with cb:
#         st.markdown(f'<div style="font-size:.72rem;color:{C["muted"]};margin-bottom:6px;">{label_b.upper()}</div>', unsafe_allow_html=True)
#         st.plotly_chart(bar_h(rxn_b_df, "count", "pt", [[0, "#0e7490"], [1, "#22d3ee"]], h=max(380, 15 * 22 + 80)), width='stretch')

#     sec("Outcome Distribution")
#     outc_a_df, outc_b_df = qr.drug_comparison_outcomes(nk_a, nk_b, role_cod)
#     od1, od2 = st.columns(2)
#     with od1:
#         st.markdown(f'<div style="text-align:center;font-size:.72rem;color:{C["muted"]};">{label_a.upper()}</div>', unsafe_allow_html=True)
#         st.plotly_chart(donut(outc_a_df, "count", "outcome_label", h=300), width='stretch')
#     with od2:
#         st.markdown(f'<div style="text-align:center;font-size:.72rem;color:{C["muted"]};">{label_b.upper()}</div>', unsafe_allow_html=True)
#         st.plotly_chart(donut(outc_b_df, "count", "outcome_label", h=300), width='stretch')

#     sec("Pharmacovigilance Signals (HIGH only)")
#     sig_a = sd.signals_for_drug(matched_a, min_signal="HIGH", top_n=10, min_n_dr=10)
#     sig_b = sd.signals_for_drug(matched_b, min_signal="HIGH", top_n=10, min_n_dr=10)
#     ps1, ps2 = st.columns(2)
#     with ps1:
#         st.markdown(f'<div style="font-size:.72rem;color:{C["muted"]};margin-bottom:6px;">{label_a.upper()} — TOP HIGH SIGNALS</div>', unsafe_allow_html=True)
#         if not sig_a.empty:
#             st.dataframe(
#                 sig_a[["pt", "N_DR", "PRR", "chi2", "signal"]].rename(columns={"pt": "Preferred Term", "N_DR": "N", "PRR": "PRR", "chi2": "Chi-sq", "signal": "Level"}),
#                 width='stretch',
#                 hide_index=True,
#                 height=320,
#                 column_config={"PRR": st.column_config.NumberColumn("PRR", format="%.2f"), "Chi-sq": st.column_config.NumberColumn("Chi-sq", format="%.1f")},
#             )
#         else:
#             st.info("No HIGH signals found.")
#     with ps2:
#         st.markdown(f'<div style="font-size:.72rem;color:{C["muted"]};margin-bottom:6px;">{label_b.upper()} — TOP HIGH SIGNALS</div>', unsafe_allow_html=True)
#         if not sig_b.empty:
#             st.dataframe(
#                 sig_b[["pt", "N_DR", "PRR", "chi2", "signal"]].rename(columns={"pt": "Preferred Term", "N_DR": "N", "PRR": "PRR", "chi2": "Chi-sq", "signal": "Level"}),
#                 width='stretch',
#                 hide_index=True,
#                 height=320,
#                 column_config={"PRR": st.column_config.NumberColumn("PRR", format="%.2f"), "Chi-sq": st.column_config.NumberColumn("Chi-sq", format="%.1f")},
#             )
#         else:
#             st.info("No HIGH signals found.")

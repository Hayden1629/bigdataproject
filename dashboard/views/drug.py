from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import re

import pandas as pd
import streamlit as st

from dashboard import charts, queries, research_connector
from dashboard.data_loader import load_drug_name_lookup
from dashboard.drug_normalizer import match_drug_names
from dashboard.logging_utils import get_logger
from dashboard.ui import metric_card
from dashboard.views import drug_manufacturer, drug_provider


logger = get_logger(__name__)


def _clean_display_name(raw_name: str, fallback_query: str) -> str:
    text = (raw_name or "").strip()
    if not text:
        return fallback_query.strip().title()

    brand_match = re.search(r"\[([^\]]+)\]", text)
    brand = brand_match.group(1).strip() if brand_match else ""
    base = re.sub(r"\[[^\]]+\]", "", text).strip()

    base = re.sub(r"\b\d+(\.\d+)?\s*(MG|MCG|G|ML|IU)\b", "", base, flags=re.IGNORECASE)
    base = re.sub(
        r"\b(extended release|oral tablet|tablet|capsule|solution|injection|suspension|powder|release|hour|hr)\b",
        "",
        base,
        flags=re.IGNORECASE,
    )
    base = re.sub(r"\s+/\s+", " / ", base)
    base = re.sub(r"\s+", " ", base).strip(" ,-/")

    if not base:
        base = fallback_query.strip()

    if brand:
        return f"{base.title()} ({brand})"
    return base.title()


def _display_drug_name(query: str, match: dict) -> str:
    q = (query or "").strip().lower()
    canonical = str(match.get("canonical") or "").strip()
    related = [str(x).strip() for x in match.get("related", []) if str(x).strip()]

    for candidate in [canonical] + related:
        c = candidate.lower()
        if c == q:
            return candidate
        if q and q in c and not re.search(r"\d", candidate) and len(candidate) <= 45:
            return candidate

    return _clean_display_name(canonical or query, query)


def _empty_state() -> None:
    st.info("Try examples: metformin, ozempic, acetaminophen, adderall")
    st.markdown("#### Most Reported Drugs - Full Dataset")
    st.dataframe(queries.load_drug_summary().head(20), width="stretch", hide_index=True)


def _render_header(display_name: str, match: dict, role_filter: str) -> None:
    canonical = match.get("canonical") or "(unknown)"
    rxcui = match.get("rxcui") or "-"
    related = match.get("related", [])[:10]
    st.markdown(f"### {display_name}")
    st.caption(
        f"RxCUI: {rxcui} | Matched FAERS strings: {len(match.get('matched_faers_names', []))} | Role filter: {role_filter}"
    )
    if canonical and canonical != display_name:
        st.caption(f"RxNorm canonical name: {canonical}")
    if related:
        chips = "".join([f"<span class='pill'>{r}</span>" for r in related])
        st.markdown(chips, unsafe_allow_html=True)


def _render_default_view(bundle: dict, approval: dict, label: dict) -> None:
    k = bundle["kpi"]
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        metric_card("Total Cases", f"{k['cases']:,}")
    with c2:
        metric_card("Deaths", f"{k['deaths']:,}", f"{k['death_pct']:.1f}%")
    with c3:
        metric_card("Hospitalisations", f"{k['hospitalisations']:,}")
    with c4:
        metric_card("Life-threatening", f"{k['life_threatening']:,}")
    with c5:
        metric_card(
            "Any Serious Outcome", f"{k['serious']:,}", f"{k['serious_pct']:.1f}%"
        )

    if approval:
        with st.container(border=True):
            st.markdown("#### FDA Regulatory Snapshot")
            st.write(
                f"Application number: **{approval.get('application_number', '-') or '-'}**"
            )
            st.write(f"Sponsor: **{approval.get('sponsor', '-') or '-'}**")
            st.write(
                f"First approval date: **{approval.get('first_approval_date', '-') or '-'}**"
            )
            st.write(
                f"Latest action date: **{approval.get('latest_action_date', '-') or '-'}**"
            )
            st.write(f"Dosage form: **{approval.get('dosage_form', '-') or '-'}**")
            st.write(f"Route: **{approval.get('route', '-') or '-'}**")
            st.write(
                f"Marketing status: **{approval.get('marketing_status', '-') or '-'}**"
            )
            st.markdown(
                "[Drugs@FDA](https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm) | [Orange Book](https://www.accessdata.fda.gov/scripts/cder/ob/index.cfm)"
            )

    bw = (label or {}).get("boxed_warning", "")
    if bw:
        snippet = bw[:600] + ("..." if len(bw) > 600 else "")
        st.warning(f"FDA Boxed Warning: {snippet}")

    st.markdown("#### Recent Drug Records")
    recent = bundle.get("recent", pd.DataFrame())
    st.dataframe(recent.head(100), width="stretch", hide_index=True)

    a, b = st.columns(2)
    with a:
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["top_reactions"],
                "n_cases",
                "pt",
                "Top adverse reactions",
            ),
            width="stretch",
            key="drug_default_top_reactions",
        )
    with b:
        st.plotly_chart(
            charts.donut(
                bundle["outcomes"], "outc_cod", "n_cases", "Outcome distribution"
            ),
            width="stretch",
            key="drug_default_outcomes",
        )

    st.plotly_chart(
        charts.line_chart(
            bundle["trend"], "year_q", "n_cases", "Case reports by quarter"
        ),
        width="stretch",
        key="drug_default_quarterly_trend",
    )

    st.markdown("#### Demographics and Geography")
    d1, d2, d3, d4 = st.columns(4)
    with d1:
        st.plotly_chart(
            charts.donut(
                bundle["demographics"]["sex"], "sex", "n_cases", "Sex distribution"
            ),
            width="stretch",
            key="drug_default_demographics_sex",
        )
    with d2:
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["demographics"]["age_group"],
                "n_cases",
                "age_group",
                "Age group distribution",
            ),
            width="stretch",
            key="drug_default_demographics_age",
        )
    with d3:
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["demographics"]["reporter"],
                "n_cases",
                "rpsr_cod",
                "Reporter type distribution",
            ),
            width="stretch",
            key="drug_default_demographics_reporter",
        )
    with d4:
        st.dataframe(bundle["countries"], width="stretch", hide_index=True)

    st.markdown("#### Clinical Context")
    e1, e2 = st.columns(2)
    with e1:
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["indications"],
                "n_cases",
                "indi_pt",
                "Top indications",
            ),
            width="stretch",
            key="drug_default_indications",
        )
    with e2:
        st.plotly_chart(
            charts.bar_horizontal(
                bundle["concomitants"],
                "n_cases",
                "drugname",
                "Top co-reported drugs",
            ),
            width="stretch",
            key="drug_default_concomitants",
        )

    top_reac = bundle["top_reactions"].head(1)
    top_indi = bundle["indications"].head(1)
    trend = bundle["trend"]
    delta = 0
    if len(trend) >= 2:
        delta = int(trend.iloc[-1]["n_cases"] - trend.iloc[-2]["n_cases"])
    bullets = []
    if not top_reac.empty:
        bullets.append(
            f"Most reported reaction: {top_reac.iloc[0]['pt']} ({int(top_reac.iloc[0]['n_cases']):,} cases)"
        )
    bullets.append(f"Recent quarter change: {delta:+,} cases")
    if not top_indi.empty:
        bullets.append(f"Top indication: {top_indi.iloc[0]['indi_pt']}")
    st.markdown("#### At A Glance")
    for b in bullets:
        st.markdown(f"- {b}")

    with st.expander("Optional External Context"):
        t1, t2, t3 = st.tabs(["Clinical Trials", "Literature", "Recalls & Enforcement"])
        with t1:
            trials = research_connector.search_clinical_trials(
                str(st.session_state.get("drug_query", ""))
            )
            st.dataframe(trials, width="stretch", hide_index=True)
        with t2:
            pubs = research_connector.search_pubmed(
                str(st.session_state.get("drug_query", ""))
            )
            st.dataframe(pubs, width="stretch", hide_index=True)
        with t3:
            enf = research_connector.get_drug_enforcement(
                str(st.session_state.get("drug_query", ""))
            )
            st.dataframe(enf, width="stretch", hide_index=True)


def render(filters: dict) -> None:
    st.markdown("### Drug Explorer")
    q = st.text_input("Search a drug", placeholder="e.g., metformin", key="drug_query")
    if not q.strip():
        _empty_state()
        return
    logger.info("Drug search submitted: query=%s", q)

    lookup = load_drug_name_lookup()
    match = match_drug_names(q, lookup)
    if not match["matched_faers_names"]:
        logger.info("Drug search no FAERS match: query=%s", q)
        st.warning("No FAERS drug name match found. Try another spelling or synonym.")
        return
    logger.info(
        "Drug search matched: query=%s canonical=%s matched_names=%s",
        q,
        match.get("canonical"),
        len(match["matched_faers_names"]),
    )

    role_filter = filters["role_filter"]
    quarters = tuple(filters["quarters"])
    top_n = int(filters["top_n"])

    display_name = _display_drug_name(q, match)
    logger.info(
        "Drug display name resolved: canonical=%s display=%s",
        match.get("canonical"),
        display_name,
    )
    _render_header(display_name, match, role_filter)

    with ThreadPoolExecutor(max_workers=6) as pool:
        f_bundle = pool.submit(
            queries.drug_query_bundle,
            tuple(match["matched_faers_names"]),
            top_n,
            role_filter,
            quarters,
        )
        f_provider = None
        f_mfr = None
        f_class = pool.submit(research_connector.get_drug_class, match.get("rxcui"))
        f_approval = pool.submit(
            research_connector.get_fda_approval_info, match.get("canonical") or q
        )
        f_label = pool.submit(
            research_connector.get_drug_label, match.get("canonical") or q
        )

        bundle = f_bundle.result()
        ids = tuple(sorted(bundle.get("primaryids", set())))
        logger.info("Drug bundle ready: query=%s primaryids=%s", q, len(ids))
        f_provider = pool.submit(
            queries.drug_provider_bundle, ids, top_n, role_filter, quarters
        )
        f_mfr = pool.submit(
            queries.drug_manufacturer_bundle, ids, top_n, role_filter, quarters
        )

        provider_bundle = f_provider.result()
        mfr_bundle = f_mfr.result()
        drug_class = f_class.result()
        approval = f_approval.result()
        label = f_label.result()
        logger.info(
            "Drug context loaded: provider_cases=%s manufacturer_cases=%s class=%s",
            len(provider_bundle.get("cases", [])),
            len(mfr_bundle.get("cases", [])),
            bool(drug_class),
        )

    if drug_class:
        st.caption(
            f"Primary class: {drug_class.get('class_name', '-') or '-'} ({drug_class.get('class_type', '-') or '-'})"
        )

    tab_default, tab_provider, tab_mfr = st.tabs(
        ["Default / Full View", "Provider View", "Manufacturer View"]
    )

    with tab_default:
        _render_default_view(bundle, approval, label)
        with st.expander("Matched Drug Name Strings"):
            st.dataframe(
                {"matched_drugname": match["matched_faers_names"]},
                width="stretch",
                hide_index=True,
            )

    with tab_provider:
        drug_provider.render(provider_bundle, top_n)

    with tab_mfr:
        drug_manufacturer.render(mfr_bundle, top_n)

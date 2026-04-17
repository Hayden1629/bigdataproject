from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from dashboard import data_loader as dl
from dashboard.logging_utils import get_logger


ROLE_LABELS = {
    "PS": "Primary suspect",
    "SS": "Secondary suspect",
    "C": "Concomitant",
    "I": "Interacting",
}
OUTCOME_LABELS = {
    "DE": "Death",
    "LT": "Life-threatening",
    "HO": "Hospitalization",
    "DS": "Disability",
    "CA": "Congenital anomaly",
    "RI": "Required intervention",
    "OT": "Other",
}


logger = get_logger(__name__)


def _tables() -> dict[str, pd.DataFrame]:
    return dl.load_runtime_tables()


def _clean_quarters(quarters: list[str] | None) -> list[str]:
    if not quarters:
        return []
    return sorted([str(q) for q in quarters if str(q).strip()])


def _filter_by_quarters(df: pd.DataFrame, quarters: list[str] | None) -> pd.DataFrame:
    q = _clean_quarters(quarters)
    if not q or "year_q" not in df.columns:
        return df
    return df[df["year_q"].astype(str).isin(q)]


def _filter_drug_role(df: pd.DataFrame, role_filter: str) -> pd.DataFrame:
    if role_filter == "all" or "role_cod" not in df.columns:
        return df
    return df[df["role_cod"].astype(str).str.upper() == role_filter.upper()]


def _primaryids_from_filters(quarters: list[str] | None) -> set[str]:
    t = _tables()
    demo = _filter_by_quarters(t["demo_slim"], quarters)
    return set(demo["primaryid"].astype(str).unique().tolist())


def _top_counts(
    df: pd.DataFrame, col: str, top_n: int, label_map: dict[str, str] | None = None
) -> pd.DataFrame:
    if df.empty or col not in df.columns:
        return pd.DataFrame(columns=[col, "n_cases"])
    out = (
        df[["primaryid", col]]
        .dropna()
        .assign(**{col: lambda x: x[col].astype(str).str.strip()})
        .query(f"{col} != ''")
        .groupby(col, as_index=False)["primaryid"]
        .nunique()
        .rename(columns={"primaryid": "n_cases"})
        .sort_values("n_cases", ascending=False)
        .head(top_n)
    )
    if label_map is not None and not out.empty:
        out[col] = out[col].map(lambda v: label_map.get(str(v), str(v)))
    return out


@st.cache_data(show_spinner=False)
def load_drug_summary() -> pd.DataFrame:
    t = _tables()
    if not t["drug_summary"].empty:
        return t["drug_summary"]
    return _top_counts(t["drug_records_slim"], "drugname", 100)


@st.cache_data(show_spinner=False)
def load_reac_summary() -> pd.DataFrame:
    t = _tables()
    if not t["reac_summary"].empty:
        return t["reac_summary"]
    return _top_counts(t["reac_slim"], "pt", 100)


@st.cache_data(show_spinner=False)
def load_manufacturer_summary() -> pd.DataFrame:
    t = _tables()
    if not t["manufacturer_summary"].empty:
        return t["manufacturer_summary"]
    return _top_counts(t["drug_records_slim"], "canonical_mfr", 100)


@st.cache_data(show_spinner=False)
def global_kpis(quarters: tuple[str, ...], role_filter: str) -> dict[str, Any]:
    t = _tables()
    demo = _filter_by_quarters(t["demo_slim"], list(quarters))
    ids = set(demo["primaryid"].astype(str).unique())

    drug = t["drug_records_slim"]
    drug = drug[drug["primaryid"].astype(str).isin(ids)]
    drug = _filter_drug_role(drug, role_filter)

    reac = t["reac_slim"]
    reac = reac[reac["primaryid"].astype(str).isin(ids)]

    outc = t["outc_slim"]
    outc = outc[outc["primaryid"].astype(str).isin(ids)]

    deaths = (
        int(outc[outc["outc_cod"] == "DE"]["primaryid"].nunique())
        if not outc.empty
        else 0
    )
    hosps = (
        int(outc[outc["outc_cod"] == "HO"]["primaryid"].nunique())
        if not outc.empty
        else 0
    )
    life = (
        int(outc[outc["outc_cod"] == "LT"]["primaryid"].nunique())
        if not outc.empty
        else 0
    )
    serious = int(outc["primaryid"].nunique()) if not outc.empty else 0
    cases = int(len(ids))

    return {
        "cases": cases,
        "deaths": deaths,
        "death_pct": (deaths / cases * 100.0) if cases else 0.0,
        "hospitalisations": hosps,
        "life_threatening": life,
        "serious": serious,
        "serious_pct": (serious / cases * 100.0) if cases else 0.0,
        "unique_drugs": int(drug["drugname"].nunique()) if not drug.empty else 0,
        "unique_reactions": int(reac["pt"].nunique()) if not reac.empty else 0,
    }


@st.cache_data(show_spinner=False)
def global_quarterly_trend(quarters: tuple[str, ...], role_filter: str) -> pd.DataFrame:
    t = _tables()
    demo = t["demo_slim"]
    demo = _filter_by_quarters(demo, list(quarters))
    if demo.empty:
        return pd.DataFrame(columns=["year_q", "n_cases"])

    ids = set(demo["primaryid"].astype(str))
    drug = t["drug_records_slim"]
    drug = drug[drug["primaryid"].astype(str).isin(ids)]
    drug = _filter_drug_role(drug, role_filter)

    valid_ids = set(drug["primaryid"].astype(str)) if not drug.empty else ids
    out = (
        demo[demo["primaryid"].astype(str).isin(valid_ids)]
        .groupby("year_q", as_index=False)["primaryid"]
        .nunique()
        .rename(columns={"primaryid": "n_cases"})
        .sort_values("year_q")
    )
    return out


def _trend_delta(fact_df: pd.DataFrame, key_col: str, top_n: int) -> pd.DataFrame:
    if fact_df.empty or key_col not in fact_df.columns:
        return pd.DataFrame(columns=[key_col, "delta"])
    last_two = sorted(fact_df["year_q"].dropna().astype(str).unique().tolist())[-2:]
    if len(last_two) < 2:
        return pd.DataFrame(columns=[key_col, "delta"])
    prev_q, curr_q = last_two[0], last_two[1]
    a = fact_df[fact_df["year_q"] == prev_q].set_index(key_col)["n_cases"]
    b = fact_df[fact_df["year_q"] == curr_q].set_index(key_col)["n_cases"]
    idx = sorted(set(a.index).union(set(b.index)))
    rows = []
    for k in idx:
        rows.append({key_col: k, "delta": int(b.get(k, 0) - a.get(k, 0))})
    out = (
        pd.DataFrame(rows)
        .sort_values("delta", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
    return out


@st.cache_data(show_spinner=False)
def trending_drugs(top_n: int = 10) -> pd.DataFrame:
    t = _tables()
    fact = t["fact_drug_quarter"]
    if fact.empty:
        return pd.DataFrame(columns=["drugname", "delta"])
    return _trend_delta(fact, "drugname", top_n)


@st.cache_data(show_spinner=False)
def trending_reactions(top_n: int = 10) -> pd.DataFrame:
    t = _tables()
    fact = t["fact_reac_quarter"]
    if fact.empty:
        return pd.DataFrame(columns=["pt", "delta"])
    return _trend_delta(fact, "pt", top_n)


def _resolve_drug_primaryids(
    matched_names: list[str], quarters: list[str] | None, role_filter: str
) -> set[str]:
    t = _tables()
    drug = t["drug_records_slim"]
    if matched_names:
        drug = drug[drug["drugname"].astype(str).isin(matched_names)]
    drug = _filter_by_quarters(drug, quarters)
    drug = _filter_drug_role(drug, role_filter)
    return set(drug["primaryid"].astype(str).unique().tolist())


def _kpi_from_ids(ids: set[str]) -> dict[str, Any]:
    t = _tables()
    outc = t["outc_slim"]
    outc = outc[outc["primaryid"].astype(str).isin(ids)]
    cases = len(ids)
    deaths = (
        int(outc[outc["outc_cod"] == "DE"]["primaryid"].nunique())
        if not outc.empty
        else 0
    )
    hosps = (
        int(outc[outc["outc_cod"] == "HO"]["primaryid"].nunique())
        if not outc.empty
        else 0
    )
    life = (
        int(outc[outc["outc_cod"] == "LT"]["primaryid"].nunique())
        if not outc.empty
        else 0
    )
    serious = int(outc["primaryid"].nunique()) if not outc.empty else 0
    return {
        "cases": cases,
        "deaths": deaths,
        "death_pct": (deaths / cases * 100.0) if cases else 0.0,
        "hospitalisations": hosps,
        "life_threatening": life,
        "serious": serious,
        "serious_pct": (serious / cases * 100.0) if cases else 0.0,
    }


@st.cache_data(show_spinner=False)
def drug_query_bundle(
    matched_names: tuple[str, ...],
    top_n: int,
    role_filter: str,
    quarters: tuple[str, ...],
) -> dict[str, Any]:
    t = _tables()
    ids = _resolve_drug_primaryids(list(matched_names), list(quarters), role_filter)
    logger.info(
        "drug_query_bundle: matched_names=%s quarters=%s role=%s top_n=%s ids=%s",
        len(matched_names),
        len(quarters),
        role_filter,
        top_n,
        len(ids),
    )
    if not ids:
        return {
            "primaryids": set(),
            "kpi": _kpi_from_ids(set()),
            "recent": pd.DataFrame(),
            "top_reactions": pd.DataFrame(),
            "outcomes": pd.DataFrame(),
            "trend": pd.DataFrame(),
            "demographics": {},
            "countries": pd.DataFrame(),
            "indications": pd.DataFrame(),
            "concomitants": pd.DataFrame(),
        }

    drug = t["drug_records_slim"]
    drug = drug[drug["primaryid"].astype(str).isin(ids)]

    demo = t["demo_slim"]
    demo = demo[demo["primaryid"].astype(str).isin(ids)]

    reac = t["reac_slim"]
    reac = reac[reac["primaryid"].astype(str).isin(ids)]

    outc = t["outc_slim"]
    outc = outc[outc["primaryid"].astype(str).isin(ids)]

    rpsr = t["rpsr_slim"]
    rpsr = (
        rpsr[rpsr["primaryid"].astype(str).isin(ids)]
        if not t["rpsr_slim"].empty
        else pd.DataFrame(columns=["primaryid", "rpsr_cod"])
    )

    indi = t["indi_slim"]
    indi = indi[indi["primaryid"].astype(str).isin(ids)]

    recent_cols = [
        "primaryid",
        "role_cod",
        "drugname",
        "prod_ai",
        "route",
        "dose_amt",
        "dose_unit",
        "dose_form",
        "dose_freq",
    ]
    recent = (
        drug[recent_cols].copy()
        if set(recent_cols).issubset(drug.columns)
        else drug.copy()
    )
    recent = recent.head(100)

    trend = (
        demo.groupby("year_q", as_index=False)["primaryid"]
        .nunique()
        .rename(columns={"primaryid": "n_cases"})
        .sort_values("year_q")
    )

    sex = (
        demo.groupby("sex", as_index=False)["primaryid"]
        .nunique()
        .rename(columns={"primaryid": "n_cases"})
        .sort_values("n_cases", ascending=False)
    )

    age_group = pd.cut(
        pd.to_numeric(demo["age"], errors="coerce"),
        bins=[-1, 17, 35, 50, 65, 200],
        labels=["0-17", "18-35", "36-50", "51-65", "66+"],
    )
    age_df = (
        pd.DataFrame({"age_group": age_group, "primaryid": demo["primaryid"]})
        .dropna()
        .groupby("age_group", as_index=False)["primaryid"]
        .nunique()
        .rename(columns={"primaryid": "n_cases"})
    )

    reporter = (
        _top_counts(rpsr, "rpsr_cod", top_n)
        if not rpsr.empty
        else pd.DataFrame(columns=["rpsr_cod", "n_cases"])
    )

    countries = _top_counts(demo, "occr_country", top_n)
    top_reactions = _top_counts(reac, "pt", top_n)
    outcomes = _top_counts(outc, "outc_cod", top_n, label_map=OUTCOME_LABELS)
    indications = _top_counts(indi, "indi_pt", top_n)

    concomitants = _top_counts(drug, "drugname", top_n + 5)
    if not concomitants.empty and matched_names:
        concomitants = concomitants[
            ~concomitants["drugname"].isin(list(matched_names))
        ].head(top_n)

    return {
        "primaryids": ids,
        "kpi": _kpi_from_ids(ids),
        "recent": recent,
        "top_reactions": top_reactions,
        "outcomes": outcomes,
        "trend": trend,
        "demographics": {
            "sex": sex,
            "age_group": age_df,
            "reporter": reporter,
        },
        "countries": countries,
        "indications": indications,
        "concomitants": concomitants,
    }


def _build_case_table(ids: set[str], include_lit_ref: bool = False) -> pd.DataFrame:
    t = _tables()
    demo = t["demo_slim"][t["demo_slim"]["primaryid"].astype(str).isin(ids)][
        [
            "primaryid",
            "event_dt",
            "occr_country",
            "mfr_sndr",
            "canonical_mfr",
            "lit_ref",
        ]
    ]
    drug = t["drug_records_slim"][
        t["drug_records_slim"]["primaryid"].astype(str).isin(ids)
    ][
        [
            "primaryid",
            "role_cod",
            "route",
            "dose_amt",
            "dose_unit",
            "dose_form",
            "dose_freq",
            "mfr_sndr",
            "prod_ai",
        ]
    ]
    reac = t["reac_slim"][t["reac_slim"]["primaryid"].astype(str).isin(ids)][
        ["primaryid", "pt"]
    ]
    outc = t["outc_slim"][t["outc_slim"]["primaryid"].astype(str).isin(ids)][
        ["primaryid", "outc_cod"]
    ]
    indi = t["indi_slim"][t["indi_slim"]["primaryid"].astype(str).isin(ids)][
        ["primaryid", "indi_pt"]
    ]

    rows = []
    outcome_map = (
        outc.groupby("primaryid")["outc_cod"]
        .apply(lambda s: ", ".join(sorted(set(s.astype(str)))))
        .to_dict()
        if not outc.empty
        else {}
    )
    top_reac = (
        reac.groupby("primaryid")["pt"].first().to_dict() if not reac.empty else {}
    )
    top_indi = (
        indi.groupby("primaryid")["indi_pt"].first().to_dict() if not indi.empty else {}
    )
    demo_map = (
        demo.drop_duplicates("primaryid", keep="first")
        .set_index("primaryid")
        .to_dict("index")
        if not demo.empty
        else {}
    )

    if drug.empty:
        return pd.DataFrame(columns=["primaryid"])

    for _, r in drug.drop_duplicates("primaryid").iterrows():
        pid = str(r["primaryid"])
        d = demo_map.get(pid, {})
        row = {
            "primaryid": pid,
            "event_dt": d.get("event_dt", ""),
            "country": d.get("occr_country", ""),
            "role": r.get("role_cod", ""),
            "route": r.get("route", ""),
            "dose": f"{r.get('dose_amt', '')} {r.get('dose_unit', '')}".strip(),
            "dose_form": r.get("dose_form", ""),
            "dose_freq": r.get("dose_freq", ""),
            "manufacturer": d.get("mfr_sndr", "") or r.get("mfr_sndr", ""),
            "canonical_mfr": d.get("canonical_mfr", ""),
            "active_ingredient": r.get("prod_ai", ""),
            "top_reaction": top_reac.get(pid, ""),
            "outcomes": outcome_map.get(pid, ""),
            "top_indication": top_indi.get(pid, ""),
            "lit_ref": d.get("lit_ref", ""),
        }
        rows.append(row)

    out = pd.DataFrame(rows)
    if include_lit_ref and "lit_ref" not in out.columns:
        out["lit_ref"] = ""
    return out


@st.cache_data(show_spinner=False)
def drug_provider_bundle(
    primaryids: tuple[str, ...], top_n: int, role_filter: str, quarters: tuple[str, ...]
) -> dict[str, Any]:
    t = _tables()
    ids = set(primaryids)
    if quarters:
        quarter_ids = _primaryids_from_filters(list(quarters))
        ids = ids.intersection(quarter_ids)
    if not ids:
        logger.info("drug_provider_bundle: no ids after filters")
        return {
            "ingredients": pd.DataFrame(),
            "role_counts": pd.DataFrame(),
            "route_counts": pd.DataFrame(),
            "dose_counts": pd.DataFrame(),
            "dose_form_counts": pd.DataFrame(),
            "dose_freq_counts": pd.DataFrame(),
            "reactions": pd.DataFrame(),
            "outcomes": pd.DataFrame(),
            "indications": pd.DataFrame(),
            "cases": pd.DataFrame(),
        }

    drug = t["drug_records_slim"]
    drug = drug[drug["primaryid"].astype(str).isin(ids)]
    drug = _filter_drug_role(drug, role_filter)
    ids2 = set(drug["primaryid"].astype(str))

    reac = t["reac_slim"][t["reac_slim"]["primaryid"].astype(str).isin(ids2)]
    outc = t["outc_slim"][t["outc_slim"]["primaryid"].astype(str).isin(ids2)]
    indi = t["indi_slim"][t["indi_slim"]["primaryid"].astype(str).isin(ids2)]

    tmp = drug.copy()
    tmp["dose_bucket"] = (
        tmp["dose_amt"].astype(str).str.strip().replace("", "Not reported")
        + " "
        + tmp["dose_unit"].astype(str).str.strip().replace("", "")
    ).str.strip()
    tmp["dose_bucket"] = tmp["dose_bucket"].replace("", "Not reported")

    return {
        "ingredients": _top_counts(
            drug.rename(columns={"prod_ai": "ingredient"}), "ingredient", top_n
        ),
        "role_counts": _top_counts(drug, "role_cod", top_n, label_map=ROLE_LABELS),
        "route_counts": _top_counts(drug, "route", top_n),
        "dose_counts": _top_counts(
            tmp.rename(columns={"dose_bucket": "dose"}), "dose", top_n
        ),
        "dose_form_counts": _top_counts(drug, "dose_form", top_n),
        "dose_freq_counts": _top_counts(drug, "dose_freq", top_n),
        "reactions": _top_counts(reac, "pt", top_n),
        "outcomes": _top_counts(outc, "outc_cod", top_n, label_map=OUTCOME_LABELS),
        "indications": _top_counts(indi, "indi_pt", top_n),
        "cases": _build_case_table(ids2, include_lit_ref=True),
    }


@st.cache_data(show_spinner=False)
def drug_manufacturer_bundle(
    primaryids: tuple[str, ...], top_n: int, role_filter: str, quarters: tuple[str, ...]
) -> dict[str, Any]:
    t = _tables()
    ids = set(primaryids)
    if quarters:
        quarter_ids = _primaryids_from_filters(list(quarters))
        ids = ids.intersection(quarter_ids)
    if not ids:
        logger.info("drug_manufacturer_bundle: no ids after filters")
        return {
            "ingredients": pd.DataFrame(),
            "manufacturer_counts": pd.DataFrame(),
            "country_counts": pd.DataFrame(),
            "outcome_counts": pd.DataFrame(),
            "dose_form_counts": pd.DataFrame(),
            "cases": pd.DataFrame(),
            "quarterly_trend": pd.DataFrame(),
        }

    drug = t["drug_records_slim"]
    drug = drug[drug["primaryid"].astype(str).isin(ids)]
    drug = _filter_drug_role(drug, role_filter)
    ids2 = set(drug["primaryid"].astype(str))

    demo = t["demo_slim"][t["demo_slim"]["primaryid"].astype(str).isin(ids2)]
    outc = t["outc_slim"][t["outc_slim"]["primaryid"].astype(str).isin(ids2)]

    trend = (
        demo.groupby("year_q", as_index=False)["primaryid"]
        .nunique()
        .rename(columns={"primaryid": "n_cases"})
        .sort_values("year_q")
    )

    cases = _build_case_table(ids2)
    keep = [
        "event_dt",
        "manufacturer",
        "country",
        "active_ingredient",
        "dose_form",
        "outcomes",
    ]
    if not cases.empty:
        cases = cases[keep].sort_values("event_dt", ascending=False)

    return {
        "ingredients": _top_counts(
            drug.rename(columns={"prod_ai": "ingredient"}), "ingredient", top_n
        ),
        "manufacturer_counts": _top_counts(
            demo.rename(columns={"canonical_mfr": "manufacturer"}),
            "manufacturer",
            top_n,
        ),
        "country_counts": _top_counts(
            demo.rename(columns={"occr_country": "country"}), "country", top_n
        ),
        "outcome_counts": _top_counts(
            outc, "outc_cod", top_n, label_map=OUTCOME_LABELS
        ),
        "dose_form_counts": _top_counts(drug, "dose_form", top_n),
        "cases": cases,
        "quarterly_trend": trend,
    }


@st.cache_data(show_spinner=False)
def manufacturer_query_bundle(
    canonical_names: tuple[str, ...],
    top_n: int,
    role_filter: str,
    quarters: tuple[str, ...],
) -> dict[str, Any]:
    t = _tables()
    if not canonical_names:
        logger.info("manufacturer_query_bundle: empty canonical names")
        return {
            "kpi": _kpi_from_ids(set()),
            "drug_counts": pd.DataFrame(),
            "ingredient_counts": pd.DataFrame(),
            "outcome_counts": pd.DataFrame(),
            "indication_counts": pd.DataFrame(),
            "country_counts": pd.DataFrame(),
            "cases": pd.DataFrame(),
            "quarterly_trend": pd.DataFrame(),
        }

    demo = t["demo_slim"]
    demo = demo[demo["canonical_mfr"].astype(str).isin(list(canonical_names))]
    demo = _filter_by_quarters(demo, list(quarters))
    ids = set(demo["primaryid"].astype(str).unique().tolist())
    logger.info(
        "manufacturer_query_bundle: canonical=%s quarters=%s role=%s ids_pre_role=%s",
        len(canonical_names),
        len(quarters),
        role_filter,
        len(ids),
    )

    drug = t["drug_records_slim"]
    drug = drug[drug["primaryid"].astype(str).isin(ids)]
    drug = _filter_drug_role(drug, role_filter)
    ids = set(drug["primaryid"].astype(str).unique().tolist())
    demo = demo[demo["primaryid"].astype(str).isin(ids)]
    outc = t["outc_slim"][t["outc_slim"]["primaryid"].astype(str).isin(ids)]
    indi = t["indi_slim"][t["indi_slim"]["primaryid"].astype(str).isin(ids)]

    trend = (
        demo.groupby("year_q", as_index=False)["primaryid"]
        .nunique()
        .rename(columns={"primaryid": "n_cases"})
        .sort_values("year_q")
    )

    table = _build_case_table(ids)
    keep = ["active_ingredient", "country", "outcomes", "top_indication"]
    if not table.empty:
        drugname_by_id = drug.groupby("primaryid")["drugname"].first().to_dict()
        table["drug_name"] = table["primaryid"].map(
            lambda x: drugname_by_id.get(str(x), "")
        )
        table = table[["event_dt", "drug_name"] + keep].sort_values(
            "event_dt", ascending=False
        )

    kpi = _kpi_from_ids(ids)
    kpi["unique_drugs"] = int(drug["drugname"].nunique()) if not drug.empty else 0
    kpi["countries"] = int(demo["occr_country"].nunique()) if not demo.empty else 0

    return {
        "kpi": kpi,
        "drug_counts": _top_counts(drug, "drugname", top_n),
        "ingredient_counts": _top_counts(
            drug.rename(columns={"prod_ai": "ingredient"}), "ingredient", top_n
        ),
        "outcome_counts": _top_counts(
            outc, "outc_cod", top_n, label_map=OUTCOME_LABELS
        ),
        "indication_counts": _top_counts(indi, "indi_pt", top_n),
        "country_counts": _top_counts(
            demo.rename(columns={"occr_country": "country"}), "country", top_n
        ),
        "cases": table,
        "quarterly_trend": trend,
    }


@st.cache_data(show_spinner=False)
def reaction_kpis(
    terms: tuple[str, ...], quarters: tuple[str, ...], role_filter: str
) -> dict[str, Any]:
    t = _tables()
    if not terms:
        return {"cases": 0, "deaths": 0, "death_pct": 0.0, "serious": 0, "n_terms": 0}
    reac = t["reac_slim"]
    reac = reac[reac["pt"].astype(str).isin(list(terms))]
    reac = _filter_by_quarters(reac, list(quarters))
    ids = set(reac["primaryid"].astype(str))

    if role_filter != "all":
        drug = _filter_drug_role(t["drug_records_slim"], role_filter)
        ids = ids.intersection(set(drug["primaryid"].astype(str)))

    outc = t["outc_slim"][t["outc_slim"]["primaryid"].astype(str).isin(ids)]
    deaths = (
        int(outc[outc["outc_cod"] == "DE"]["primaryid"].nunique())
        if not outc.empty
        else 0
    )
    serious = int(outc["primaryid"].nunique()) if not outc.empty else 0
    cases = len(ids)
    return {
        "cases": cases,
        "deaths": deaths,
        "death_pct": (deaths / cases * 100.0) if cases else 0.0,
        "serious": serious,
        "n_terms": len(terms),
    }


@st.cache_data(show_spinner=False)
def reaction_top_drugs(
    terms: tuple[str, ...], top_n: int, quarters: tuple[str, ...], role_filter: str
) -> pd.DataFrame:
    t = _tables()
    if not terms:
        return pd.DataFrame(columns=["drugname", "n_cases"])
    reac = t["reac_slim"]
    reac = reac[reac["pt"].astype(str).isin(list(terms))]
    reac = _filter_by_quarters(reac, list(quarters))
    ids = set(reac["primaryid"].astype(str))

    drug = t["drug_records_slim"]
    drug = _filter_drug_role(drug, role_filter)
    drug = drug[drug["primaryid"].astype(str).isin(ids)]
    return _top_counts(drug, "drugname", top_n)


@st.cache_data(show_spinner=False)
def reaction_outcomes(
    terms: tuple[str, ...], top_n: int, quarters: tuple[str, ...], role_filter: str
) -> pd.DataFrame:
    t = _tables()
    if not terms:
        return pd.DataFrame(columns=["outc_cod", "n_cases"])
    reac = t["reac_slim"]
    reac = reac[reac["pt"].astype(str).isin(list(terms))]
    reac = _filter_by_quarters(reac, list(quarters))
    ids = set(reac["primaryid"].astype(str))

    if role_filter != "all":
        drug = _filter_drug_role(t["drug_records_slim"], role_filter)
        ids = ids.intersection(set(drug["primaryid"].astype(str)))

    outc = t["outc_slim"]
    outc = outc[outc["primaryid"].astype(str).isin(ids)]
    return _top_counts(outc, "outc_cod", top_n, label_map=OUTCOME_LABELS)


@st.cache_data(show_spinner=False)
def reaction_trend(
    terms: tuple[str, ...], quarters: tuple[str, ...], role_filter: str
) -> pd.DataFrame:
    t = _tables()
    if not terms:
        return pd.DataFrame(columns=["year_q", "n_cases"])
    reac = t["reac_slim"]
    reac = reac[reac["pt"].astype(str).isin(list(terms))]
    reac = _filter_by_quarters(reac, list(quarters))
    ids = set(reac["primaryid"].astype(str))

    if role_filter != "all":
        drug = _filter_drug_role(t["drug_records_slim"], role_filter)
        ids = ids.intersection(set(drug["primaryid"].astype(str)))

    demo = t["demo_slim"]
    demo = demo[demo["primaryid"].astype(str).isin(ids)]
    return (
        demo.groupby("year_q", as_index=False)["primaryid"]
        .nunique()
        .rename(columns={"primaryid": "n_cases"})
        .sort_values("year_q")
    )

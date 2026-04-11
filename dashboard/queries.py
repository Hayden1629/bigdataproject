"""
queries.py

Cached query functions for the FAERS dashboard.
Uses string/tuple cache keys so Streamlit can hash them efficiently.
Repeated searches of the same drug or reaction return instantly from cache.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

import data_loader as dl
import analytics as ana

# ISO-3166-1 alpha-2 → country name (top FAERS countries)
ISO2_NAMES: dict[str, str] = {
    "US": "United States", "CA": "Canada", "JP": "Japan", "GB": "United Kingdom",
    "FR": "France", "CN": "China", "DE": "Germany", "IT": "Italy", "ES": "Spain",
    "AU": "Australia", "BR": "Brazil", "IN": "India", "CO": "Colombia",
    "NL": "Netherlands", "PL": "Poland", "MX": "Mexico", "SE": "Sweden",
    "KR": "South Korea", "AR": "Argentina", "CH": "Switzerland", "AT": "Austria",
    "BE": "Belgium", "TW": "Taiwan", "PT": "Portugal", "TR": "Turkey",
    "ZA": "South Africa", "RU": "Russia", "SG": "Singapore", "DK": "Denmark",
    "NO": "Norway", "FI": "Finland", "HU": "Hungary", "CZ": "Czechia",
    "RO": "Romania", "GR": "Greece", "IL": "Israel", "PH": "Philippines",
    "ID": "Indonesia", "TH": "Thailand", "MY": "Malaysia", "EG": "Egypt",
    "SA": "Saudi Arabia", "NG": "Nigeria", "PE": "Peru", "CL": "Chile",
    "IE": "Ireland", "NZ": "New Zealand", "HK": "Hong Kong", "PK": "Pakistan",
}

# ISO-3166-1 alpha-2 → alpha-3  (used by Plotly choropleth)
ISO2_TO_ISO3: dict[str, str] = {
    "US": "USA", "CA": "CAN", "JP": "JPN", "GB": "GBR", "FR": "FRA",
    "CN": "CHN", "DE": "DEU", "IT": "ITA", "ES": "ESP", "AU": "AUS",
    "BR": "BRA", "IN": "IND", "CO": "COL", "NL": "NLD", "PL": "POL",
    "MX": "MEX", "SE": "SWE", "KR": "KOR", "AR": "ARG", "CH": "CHE",
    "AT": "AUT", "BE": "BEL", "TW": "TWN", "PT": "PRT", "TR": "TUR",
    "ZA": "ZAF", "RU": "RUS", "SG": "SGP", "DK": "DNK", "NO": "NOR",
    "FI": "FIN", "HU": "HUN", "CZ": "CZE", "RO": "ROU", "GR": "GRC",
    "IL": "ISR", "PH": "PHL", "ID": "IDN", "TH": "THA", "MY": "MYS",
    "EG": "EGY", "SA": "SAU", "NG": "NGA", "PE": "PER", "CL": "CHL",
    "IE": "IRL", "NZ": "NZL", "HK": "HKG", "PK": "PAK", "VN": "VNM",
    "UA": "UKR", "HR": "HRV", "RS": "SRB", "SK": "SVK", "SI": "SVN",
    "LT": "LTU", "LV": "LVA", "EE": "EST", "BG": "BGR", "BA": "BIH",
    "MA": "MAR", "TN": "TUN", "DZ": "DZA", "KE": "KEN", "GH": "GHA",
    "ET": "ETH", "TZ": "TZA", "UG": "UGA", "AO": "AGO", "MZ": "MOZ",
    "SN": "SEN", "CM": "CMR", "CG": "COG", "CI": "CIV", "MR": "MRT",
    "UZ": "UZB", "KZ": "KAZ", "AZ": "AZE", "GE": "GEO", "AM": "ARM",
    "BD": "BGD", "LK": "LKA", "NP": "NPL", "MM": "MMR", "KH": "KHM",
    "QA": "QAT", "AE": "ARE", "KW": "KWT", "OM": "OMN", "JO": "JOR",
    "LB": "LBN", "IQ": "IRQ", "IR": "IRN", "SY": "SYR", "YE": "YEM",
    "EC": "ECU", "BO": "BOL", "PY": "PRY", "UY": "URY", "VE": "VEN",
    "GT": "GTM", "HN": "HND", "SV": "SLV", "NI": "NIC", "CR": "CRI",
    "PA": "PAN", "CU": "CUB", "DO": "DOM", "HT": "HTI", "JM": "JAM",
    "PL": "POL", "LU": "LUX", "MT": "MLT", "CY": "CYP", "IS": "ISL",
    "LI": "LIE", "MC": "MCO", "SM": "SMR", "VA": "VAT", "AD": "AND",
}


def _names_key(matched_names: list[str]) -> str:
    """Stable string key for a list of matched drug names."""
    return "|".join(sorted(matched_names))


def _quarters_key(quarters: list[str] | None) -> str:
    return "|".join(sorted(quarters)) if quarters else "ALL"


# ── Drug queries ──────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def drug_kpis(names_key: str, role: str, quarters_key: str) -> dict:
    tables = dl.load_tables()
    drug   = _filter_quarters(tables["drug"], quarters_key)
    outc   = _filter_quarters_by_demo(tables["outc"], tables["demo"], quarters_key)
    name_set = set(names_key.split("|"))
    return ana.kpis_for_drug(drug, outc, name_set, role=role)


@st.cache_data(show_spinner=False)
def drug_top_reactions(names_key: str, role: str, quarters_key: str, top_n: int) -> pd.DataFrame:
    tables = dl.load_tables()
    drug   = _filter_quarters(tables["drug"], quarters_key)
    reac   = _filter_quarters(tables["reac"], quarters_key)
    name_set = set(names_key.split("|"))
    return ana.top_reactions_for_drug(drug, reac, name_set, role=role, top_n=top_n)


@st.cache_data(show_spinner=False)
def drug_outcomes(names_key: str, role: str, quarters_key: str) -> pd.DataFrame:
    tables = dl.load_tables()
    drug   = _filter_quarters(tables["drug"], quarters_key)
    outc   = _filter_quarters_by_demo(tables["outc"], tables["demo"], quarters_key)
    name_set = set(names_key.split("|"))
    return ana.outcomes_for_drug(drug, outc, name_set, role=role)


@st.cache_data(show_spinner=False)
def drug_trend(names_key: str, role: str, quarters_key: str) -> pd.DataFrame:
    tables = dl.load_tables()
    drug   = _filter_quarters(tables["drug"], quarters_key)
    name_set = set(names_key.split("|"))
    quarter_filter = quarters_key.split("|") if quarters_key != "ALL" else None
    return ana.quarterly_trend_for_drug(name_set, drug, role=role, quarter_filter=quarter_filter)


@st.cache_data(show_spinner=False)
def drug_demographics(names_key: str, role: str, quarters_key: str) -> dict:
    tables = dl.load_tables()
    drug   = _filter_quarters(tables["drug"], quarters_key)
    demo   = _filter_quarters(tables["demo"], quarters_key)
    name_set = set(names_key.split("|"))
    return ana.demographics_for_drug(drug, demo, name_set, role=role)


@st.cache_data(show_spinner=False)
def drug_countries(names_key: str, role: str, quarters_key: str, top_n: int = 20) -> pd.DataFrame:
    """Top reporter countries for a drug's cases."""
    tables   = dl.load_tables()
    drug     = _filter_quarters(tables["drug"], quarters_key)
    demo     = _filter_quarters(tables["demo"], quarters_key)
    name_set = set(names_key.split("|"))

    mask = drug["canon"].isin(name_set)
    if role != "all":
        mask = mask & (drug["role_cod"] == role)
    case_ids = set(drug.loc[mask, "primaryid"].unique())

    sub = demo[demo["primaryid"].isin(case_ids)]
    vc = sub["reporter_country"].value_counts().head(top_n).reset_index()
    vc.columns = ["iso2", "count"]
    vc["country"] = vc["iso2"].map(ISO2_NAMES).fillna(vc["iso2"])
    vc["pct"] = (vc["count"] / vc["count"].sum() * 100).round(1)
    return vc


@st.cache_data(show_spinner=False)
def drug_indications(names_key: str, role: str, quarters_key: str, top_n: int = 15) -> pd.DataFrame:
    """Top indications (what the drug was prescribed for)."""
    tables   = dl.load_tables()
    drug     = _filter_quarters(tables["drug"], quarters_key)
    indi     = _filter_quarters(tables["indi"], quarters_key)
    name_set = set(names_key.split("|"))

    mask = drug["canon"].isin(name_set)
    if role != "all":
        mask = mask & (drug["role_cod"] == role)
    drug_sub = drug.loc[mask, ["primaryid", "drug_seq"]]

    # Join on primaryid + drug_seq to get indications for the specific drug (not concomitants)
    joined = drug_sub.merge(
        indi[["primaryid", "indi_drug_seq", "indi_pt"]],
        left_on=["primaryid", "drug_seq"],
        right_on=["primaryid", "indi_drug_seq"],
        how="inner",
    )
    vc = joined["indi_pt"].value_counts().head(top_n + 1).reset_index()
    vc.columns = ["indication", "count"]
    # Remove the "unknown" placeholder
    vc = vc[~vc["indication"].str.lower().str.contains("unknown", na=False)].head(top_n)
    total = joined["primaryid"].nunique()
    vc["pct"] = (vc["count"] / total * 100).round(1)
    return vc


@st.cache_data(show_spinner=False)
def drug_concomitants(names_key: str, role: str, quarters_key: str, top_n: int = 15) -> pd.DataFrame:
    """Other drugs most commonly reported alongside this drug."""
    tables   = dl.load_tables()
    drug     = _filter_quarters(tables["drug"], quarters_key)
    name_set = set(names_key.split("|"))

    mask = drug["canon"].isin(name_set)
    if role != "all":
        mask = mask & (drug["role_cod"] == role)
    case_ids = set(drug.loc[mask, "primaryid"].unique())

    # All drug records in those cases that are NOT our drug
    other = drug[drug["primaryid"].isin(case_ids) & ~drug["canon"].isin(name_set)]
    vc = other["canon"].value_counts().head(top_n).reset_index()
    vc.columns = ["drug", "count"]
    total = len(case_ids)
    vc["pct"] = (vc["count"] / total * 100).round(1)
    return vc


# ── Reaction queries ──────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def reaction_kpis(pts_key: str, quarters_key: str) -> dict:
    tables = dl.load_tables()
    reac   = _filter_quarters(tables["reac"], quarters_key)
    outc   = _filter_quarters_by_demo(tables["outc"], tables["demo"], quarters_key)
    pt_set = set(pts_key.split("|"))
    return ana.kpis_for_reaction(reac, outc, pt_set)


@st.cache_data(show_spinner=False)
def reaction_top_drugs(pts_key: str, role: str, quarters_key: str, top_n: int) -> pd.DataFrame:
    tables = dl.load_tables()
    drug   = _filter_quarters(tables["drug"], quarters_key)
    reac   = _filter_quarters(tables["reac"], quarters_key)
    pt_set = set(pts_key.split("|"))
    return ana.top_drugs_for_reaction(drug, reac, pt_set, role=role, top_n=top_n)


@st.cache_data(show_spinner=False)
def reaction_outcomes(pts_key: str, quarters_key: str) -> pd.DataFrame:
    tables = dl.load_tables()
    reac   = _filter_quarters(tables["reac"], quarters_key)
    outc   = _filter_quarters_by_demo(tables["outc"], tables["demo"], quarters_key)
    pt_set = set(pts_key.split("|"))
    return ana.outcomes_for_reaction(reac, outc, pt_set)


@st.cache_data(show_spinner=False)
def reaction_trend(pts_key: str, quarters_key: str) -> pd.DataFrame:
    tables = dl.load_tables()
    reac   = _filter_quarters(tables["reac"], quarters_key)
    pt_set = set(pts_key.split("|"))
    quarter_filter = quarters_key.split("|") if quarters_key != "ALL" else None
    return ana.quarterly_trend_for_reaction(pt_set, reac, quarter_filter=quarter_filter)


# ── Global overview queries ───────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def global_kpis() -> dict:
    tables = dl.load_tables()
    demo   = tables["demo"]
    outc   = tables["outc"]
    drug   = tables["drug"]
    reac   = tables["reac"]

    n_cases  = len(demo)
    n_deaths = int((outc["outc_cod"] == "DE").sum())
    n_drugs  = drug["canon"].nunique()
    n_pts    = reac["pt_norm"].nunique()
    hosp     = int((outc["outc_cod"] == "HO").sum())
    lt       = int((outc["outc_cod"] == "LT").sum())

    return {
        "n_cases":  n_cases,
        "n_deaths": n_deaths,
        "n_drugs":  n_drugs,
        "n_pts":    n_pts,
        "n_hosp":   hosp,
        "n_lt":     lt,
    }


@st.cache_data(show_spinner=False)
def global_quarterly_trend() -> pd.DataFrame:
    """Total cases per quarter across all drugs."""
    tables = dl.load_tables()
    demo   = tables["demo"]
    vc = demo["quarter"].value_counts().sort_index().reset_index()
    vc.columns = ["quarter", "case_count"]
    return vc


@st.cache_data(show_spinner=False)
def global_top_countries(top_n: int = 20) -> pd.DataFrame:
    tables = dl.load_tables()
    demo   = tables["demo"]
    vc = demo["reporter_country"].value_counts().head(top_n).reset_index()
    vc.columns = ["iso2", "count"]
    vc["country"] = vc["iso2"].map(ISO2_NAMES).fillna(vc["iso2"])
    vc["pct"] = (vc["count"] / len(demo) * 100).round(1)
    return vc


@st.cache_data(show_spinner=False)
def trending_drugs(top_n: int = 10) -> pd.DataFrame:
    """
    Drugs with the largest absolute increase in case count between the two most recent quarters.
    Returns DataFrame with [drug, prev_q, curr_q, prev_cases, curr_cases, delta, pct_change].
    """
    qd = dl.load_quarterly_drug()
    if qd is None or qd.empty:
        return pd.DataFrame()
    quarters = sorted(qd["quarter"].unique())
    if len(quarters) < 2:
        return pd.DataFrame()
    prev_q, curr_q = quarters[-2], quarters[-1]
    prev = qd[qd["quarter"] == prev_q].set_index("drug")["n_cases"]
    curr = qd[qd["quarter"] == curr_q].set_index("drug")["n_cases"]
    df = pd.DataFrame({"prev_cases": prev, "curr_cases": curr}).fillna(0).astype(int)
    df["delta"] = df["curr_cases"] - df["prev_cases"]
    df["pct_change"] = (df["delta"] / df["prev_cases"].replace(0, 1) * 100).round(1)
    df = df[df["prev_cases"] > 50]  # filter low-volume drugs
    df = df.sort_values("delta", ascending=False).head(top_n).reset_index()
    df.columns = ["drug", "prev_cases", "curr_cases", "delta", "pct_change"]
    df["prev_q"] = prev_q
    df["curr_q"] = curr_q
    return df


@st.cache_data(show_spinner=False)
def trending_reactions(top_n: int = 10) -> pd.DataFrame:
    """Reactions with largest case-count increase between the two most recent quarters."""
    qr_data = dl.load_quarterly_reac()
    if qr_data is None or qr_data.empty:
        return pd.DataFrame()
    quarters = sorted(qr_data["quarter"].unique())
    if len(quarters) < 2:
        return pd.DataFrame()
    prev_q, curr_q = quarters[-2], quarters[-1]
    prev = qr_data[qr_data["quarter"] == prev_q].set_index("pt")["n_cases"]
    curr = qr_data[qr_data["quarter"] == curr_q].set_index("pt")["n_cases"]
    df = pd.DataFrame({"prev_cases": prev, "curr_cases": curr}).fillna(0).astype(int)
    df["delta"] = df["curr_cases"] - df["prev_cases"]
    df["pct_change"] = (df["delta"] / df["prev_cases"].replace(0, 1) * 100).round(1)
    df = df[df["prev_cases"] > 50]
    df = df.sort_values("delta", ascending=False).head(top_n).reset_index()
    df.columns = ["reaction", "prev_cases", "curr_cases", "delta", "pct_change"]
    df["prev_q"] = prev_q
    df["curr_q"] = curr_q
    return df


@st.cache_data(show_spinner=False)
def global_reporter_types() -> pd.DataFrame:
    tables = dl.load_tables()
    demo   = tables["demo"]
    OCCP_LABELS = {
        "MD": "Physician", "PH": "Pharmacist", "RN": "Nurse",
        "OT": "Other HCP", "LW": "Lawyer", "CN": "Consumer", "HP": "Health Professional",
    }
    vc = demo["occp_cod"].value_counts().reset_index()
    vc.columns = ["code", "count"]
    vc["label"] = vc["code"].map(OCCP_LABELS).fillna(vc["code"])
    vc["pct"] = (vc["count"] / len(demo) * 100).round(1)
    return vc


# ── Internal helpers ──────────────────────────────────────────────────────────

def _filter_quarters(df: pd.DataFrame, quarters_key: str) -> pd.DataFrame:
    if quarters_key == "ALL":
        return df
    quarters = set(quarters_key.split("|"))
    return df[df["quarter"].isin(quarters)]


def _filter_quarters_by_demo(outc_df: pd.DataFrame, demo_df: pd.DataFrame, quarters_key: str) -> pd.DataFrame:
    if quarters_key == "ALL":
        return outc_df
    quarters = set(quarters_key.split("|"))
    valid_pids = set(demo_df.loc[demo_df["quarter"].isin(quarters), "primaryid"].unique())
    return outc_df[outc_df["primaryid"].isin(valid_pids)]


# ── World map query ───────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def global_country_choropleth() -> pd.DataFrame:
    """All countries with ISO-3 code and report count for a choropleth map."""
    tables = dl.load_tables()
    demo = tables["demo"]
    vc = demo["reporter_country"].value_counts().reset_index()
    vc.columns = ["iso2", "count"]
    vc["iso3"] = vc["iso2"].map(ISO2_TO_ISO3)
    vc["country"] = vc["iso2"].map(ISO2_NAMES).fillna(vc["iso2"])
    vc["pct"] = (vc["count"] / len(demo) * 100).round(2)
    # drop rows without an iso3 mapping (misc codes, unknowns)
    vc = vc.dropna(subset=["iso3"])
    return vc


# ── Drug comparison queries ───────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def drug_comparison_kpis(names_key_a: str, names_key_b: str, role: str) -> tuple[dict, dict]:
    """Return KPI dicts for two drugs."""
    tables  = dl.load_tables()
    drug    = tables["drug"]
    outc    = tables["outc"]
    set_a   = set(names_key_a.split("|"))
    set_b   = set(names_key_b.split("|"))
    kpi_a   = ana.kpis_for_drug(drug, outc, set_a, role=role)
    kpi_b   = ana.kpis_for_drug(drug, outc, set_b, role=role)
    return kpi_a, kpi_b


@st.cache_data(show_spinner=False)
def drug_comparison_top_reactions(names_key_a: str, names_key_b: str, role: str, top_n: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Top reactions for each drug."""
    tables = dl.load_tables()
    drug   = tables["drug"]
    reac   = tables["reac"]
    set_a  = set(names_key_a.split("|"))
    set_b  = set(names_key_b.split("|"))
    df_a   = ana.top_reactions_for_drug(drug, reac, set_a, role=role, top_n=top_n)
    df_b   = ana.top_reactions_for_drug(drug, reac, set_b, role=role, top_n=top_n)
    return df_a, df_b


@st.cache_data(show_spinner=False)
def drug_comparison_trend(names_key_a: str, names_key_b: str, role: str) -> pd.DataFrame:
    """Quarterly trend for both drugs merged into one DataFrame for multi-line chart."""
    tables = dl.load_tables()
    drug   = tables["drug"]
    set_a  = set(names_key_a.split("|"))
    set_b  = set(names_key_b.split("|"))
    trend_a = ana.quarterly_trend_for_drug(set_a, drug, role=role)
    trend_b = ana.quarterly_trend_for_drug(set_b, drug, role=role)
    label_a = names_key_a.split("|")[0].title()
    label_b = names_key_b.split("|")[0].title()
    merged = trend_a.rename(columns={"case_count": label_a}).merge(
        trend_b.rename(columns={"case_count": label_b}),
        on="quarter", how="outer",
    ).sort_values("quarter").fillna(0)
    merged[label_a] = merged[label_a].astype(int)
    merged[label_b] = merged[label_b].astype(int)
    return merged


@st.cache_data(show_spinner=False)
def drug_comparison_outcomes(names_key_a: str, names_key_b: str, role: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Outcome distributions for each drug."""
    tables = dl.load_tables()
    drug   = tables["drug"]
    outc   = tables["outc"]
    set_a  = set(names_key_a.split("|"))
    set_b  = set(names_key_b.split("|"))
    df_a   = ana.outcomes_for_drug(drug, outc, set_a, role=role)
    df_b   = ana.outcomes_for_drug(drug, outc, set_b, role=role)
    return df_a, df_b


@st.cache_data(show_spinner=False)
def drug_comparison_shared_reactions(names_key_a: str, names_key_b: str, role: str, top_n: int = 20) -> pd.DataFrame:
    """
    Reactions shared between two drugs with normalized report rate per 1000 cases.
    Returns a DataFrame with pt, rate_a, rate_b for a grouped bar comparison.
    """
    tables  = dl.load_tables()
    drug    = tables["drug"]
    reac    = tables["reac"]
    set_a   = set(names_key_a.split("|"))
    set_b   = set(names_key_b.split("|"))

    def _rate_df(name_set: set[str]) -> pd.DataFrame:
        mask = drug["canon"].isin(name_set)
        if role != "all":
            mask = mask & (drug["role_cod"] == role)
        pids = set(drug.loc[mask, "primaryid"].unique())
        n_cases = len(pids)
        r = reac[reac["primaryid"].isin(pids)]["pt_norm"].value_counts().reset_index()
        r.columns = ["pt", "count"]
        r["rate"] = r["count"] / n_cases * 1000  # per 1,000 cases
        return r.set_index("pt")["rate"]

    rate_a = _rate_df(set_a)
    rate_b = _rate_df(set_b)

    shared = set(rate_a.index) & set(rate_b.index)
    if not shared:
        return pd.DataFrame()

    df = pd.DataFrame({
        "pt": list(shared),
        "rate_a": [rate_a[pt] for pt in shared],
        "rate_b": [rate_b[pt] for pt in shared],
    })
    # rank by max rate across both drugs, keep top N
    df["max_rate"] = df[["rate_a", "rate_b"]].max(axis=1)
    df = df.sort_values("max_rate", ascending=False).head(top_n).drop(columns=["max_rate"])
    return df.reset_index(drop=True)

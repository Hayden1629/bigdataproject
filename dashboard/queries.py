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
from logger import get_logger

log = get_logger(__name__)

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


def _primaryids_for_index(indexed_df: pd.DataFrame, keys: list[str] | tuple[str, ...]) -> set[int]:
    if not keys:
        return set()

    found: list[pd.DataFrame] = []
    for key in keys:
        try:
            rows = indexed_df.loc[[key]]
        except KeyError:
            continue
        found.append(rows[["primaryid"]])

    if not found:
        return set()
    primaryids = pd.concat(found, ignore_index=True)["primaryid"].unique()
    return set(primaryids.tolist())


def _quarter_primaryids(quarters_key: str) -> set[int] | None:
    if quarters_key == "ALL":
        return None

    lookups = dl.load_lookup_tables()
    quarters = quarters_key.split("|")
    return _primaryids_for_index(lookups["quarter_cases"], quarters)


def _intersect_quarters(case_ids: set[int], quarters_key: str) -> set[int]:
    quarter_ids = _quarter_primaryids(quarters_key)
    if quarter_ids is None:
        return case_ids
    return case_ids & quarter_ids


def _drug_case_ids(names_key: str, role: str, quarters_key: str) -> set[int]:
    lookups = dl.load_lookup_tables()
    names = names_key.split("|") if names_key else []

    if role == "all":
        case_ids = _primaryids_for_index(lookups["drug_cases"], names)
    else:
        role_keys = [(name, role) for name in names]
        case_ids = _primaryids_for_index(lookups["drug_role_cases"], role_keys)
    return _intersect_quarters(case_ids, quarters_key)


def _reaction_case_ids(pts_key: str, quarters_key: str) -> set[int]:
    lookups = dl.load_lookup_tables()
    pts = pts_key.split("|") if pts_key else []
    case_ids = _primaryids_for_index(lookups["reaction_cases"], pts)
    return _intersect_quarters(case_ids, quarters_key)


# ── Drug queries ──────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def drug_kpis(names_key: str, role: str, quarters_key: str) -> dict:
    log.info("drug_kpis: names=%r  role=%s  quarters=%s", names_key[:60], role, quarters_key[:40])
    tables = dl.load_tables()
    case_ids = _drug_case_ids(names_key, role, quarters_key)
    n_cases = len(case_ids)
    if n_cases == 0:
        log.warning("drug_kpis: 0 cases matched for names=%r", names_key[:60])
        return {"n_cases": 0, "n_deaths": 0, "n_hosp": 0, "n_lt": 0, "n_serious": 0, "death_pct": 0.0}

    outc_sub = tables["outc"][tables["outc"]["primaryid"].isin(case_ids)]
    vc = outc_sub["outc_cod"].value_counts()
    n_deaths = int(vc.get("DE", 0))
    result = {
        "n_cases": n_cases,
        "n_deaths": n_deaths,
        "n_hosp": int(vc.get("HO", 0)),
        "n_lt": int(vc.get("LT", 0)),
        "n_serious": int(outc_sub["primaryid"].nunique()),
        "death_pct": round(n_deaths / n_cases * 100, 2),
    }
    log.info("drug_kpis: %s cases, %s deaths (%.1f%%), %s hosp",
             f"{n_cases:,}", f"{n_deaths:,}", result["death_pct"], f"{result['n_hosp']:,}")
    return result


@st.cache_data(show_spinner=False)
def drug_top_reactions(names_key: str, role: str, quarters_key: str, top_n: int) -> pd.DataFrame:
    tables = dl.load_tables()
    case_ids = _drug_case_ids(names_key, role, quarters_key)
    total = len(case_ids)
    if total == 0:
        return pd.DataFrame(columns=["pt", "count", "pct"])

    sub = tables["reac"][tables["reac"]["primaryid"].isin(case_ids)]
    counts = sub["pt_norm"].value_counts().head(top_n).reset_index()
    counts.columns = ["pt", "count"]
    counts["pct"] = (counts["count"] / total * 100).round(1)
    return counts


@st.cache_data(show_spinner=False)
def drug_outcomes(names_key: str, role: str, quarters_key: str) -> pd.DataFrame:
    tables = dl.load_tables()
    case_ids = _drug_case_ids(names_key, role, quarters_key)
    total = len(case_ids)
    if total == 0:
        return pd.DataFrame(columns=["outcome_label", "count", "pct"])

    outc_sub = tables["outc"][tables["outc"]["primaryid"].isin(case_ids)]
    vc = outc_sub["outc_cod"].value_counts().reset_index()
    vc.columns = ["outc_cod", "count"]
    vc["outcome_label"] = vc["outc_cod"].map(ana.OUTCOME_LABELS).fillna(vc["outc_cod"])
    vc["pct"] = (vc["count"] / total * 100).round(1)
    return vc[["outcome_label", "count", "pct"]].sort_values("count", ascending=False)


@st.cache_data(show_spinner=False)
def drug_trend(names_key: str, role: str, quarters_key: str) -> pd.DataFrame:
    tables = dl.load_tables()
    case_ids = _drug_case_ids(names_key, role, quarters_key)
    if not case_ids:
        return pd.DataFrame(columns=["quarter", "case_count"])

    demo = tables["demo"][tables["demo"]["primaryid"].isin(case_ids)]
    trend = demo.groupby("quarter")["primaryid"].nunique().reset_index()
    trend.columns = ["quarter", "case_count"]
    return trend.sort_values("quarter")


@st.cache_data(show_spinner=False)
def drug_demographics(names_key: str, role: str, quarters_key: str) -> dict:
    tables = dl.load_tables()
    case_ids = _drug_case_ids(names_key, role, quarters_key)
    sub = tables["demo"][tables["demo"]["primaryid"].isin(case_ids)]

    sex = sub["sex"].value_counts().reset_index()
    sex.columns = ["sex_label", "count"]
    sex["sex_label"] = sex["sex_label"].map(ana.SEX_LABELS).fillna(sex["sex_label"])

    age = sub["age_grp"].value_counts().reset_index()
    age.columns = ["age_group_label", "count"]
    age["age_group_label"] = age["age_group_label"].map(ana.AGE_LABELS).fillna(age["age_group_label"])

    rep = sub["occp_cod"].value_counts().reset_index()
    rep.columns = ["reporter", "count"]
    rep["reporter"] = rep["reporter"].map(ana.OCCP_LABELS).fillna(rep["reporter"])

    return {"sex": sex, "age_grp": age, "reporter": rep}


@st.cache_data(show_spinner=False)
def drug_countries(names_key: str, role: str, quarters_key: str, top_n: int = 20) -> pd.DataFrame:
    """Top reporter countries for a drug's cases."""
    tables   = dl.load_tables()
    case_ids = _drug_case_ids(names_key, role, quarters_key)
    sub = tables["demo"][tables["demo"]["primaryid"].isin(case_ids)]
    vc = sub["reporter_country"].value_counts().head(top_n).reset_index()
    vc.columns = ["iso2", "count"]
    vc["country"] = vc["iso2"].map(ISO2_NAMES).fillna(vc["iso2"])
    vc["pct"] = (vc["count"] / vc["count"].sum() * 100).round(1)
    return vc


@st.cache_data(show_spinner=False)
def drug_indications(names_key: str, role: str, quarters_key: str, top_n: int = 15) -> pd.DataFrame:
    """Top indications (what the drug was prescribed for)."""
    tables   = dl.load_tables()
    case_ids = _drug_case_ids(names_key, role, quarters_key)
    if not case_ids:
        return pd.DataFrame(columns=["indication", "count", "pct"])

    name_set = set(names_key.split("|"))
    drug = tables["drug"][tables["drug"]["primaryid"].isin(case_ids)]
    indi = tables["indi"][tables["indi"]["primaryid"].isin(case_ids)]

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
    case_ids = _drug_case_ids(names_key, role, quarters_key)
    name_set = set(names_key.split("|"))

    # All drug records in those cases that are NOT our drug
    other = tables["drug"][tables["drug"]["primaryid"].isin(case_ids) & ~tables["drug"]["canon"].isin(name_set)]
    vc = other["canon"].value_counts().head(top_n).reset_index()
    vc.columns = ["drug", "count"]
    total = len(case_ids)
    vc["pct"] = (vc["count"] / total * 100).round(1)
    return vc


@st.cache_data(show_spinner=False)
def drug_recent_records(names_key: str, role: str, quarters_key: str, limit: int = 100) -> pd.DataFrame:
    """Return recent individual drug records for the matched drug names."""
    tables = dl.load_tables()
    case_ids = _drug_case_ids(names_key, role, quarters_key)
    if not case_ids:
        return pd.DataFrame()

    drug = tables["drug"]
    name_set = set(names_key.split("|"))

    mask = drug["primaryid"].isin(case_ids) & drug["canon"].isin(name_set)
    if role != "all":
        mask = mask & (drug["role_cod"] == role)

    sub = drug[mask].copy()

    _WANT_COLS = ["primaryid", "role_cod", "drugname", "prod_ai", "route",
                  "dose_vbm", "dose_amt", "dose_unit", "dose_form", "dose_freq"]
    sub = sub[[c for c in _WANT_COLS if c in sub.columns]]
    return sub.sort_values("primaryid", ascending=False).head(limit).reset_index(drop=True)


# ── Reaction queries ──────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def reaction_kpis(pts_key: str, quarters_key: str) -> dict:
    log.info("reaction_kpis: pts=%r  quarters=%s", pts_key[:80], quarters_key[:40])
    tables = dl.load_tables()
    case_ids = _reaction_case_ids(pts_key, quarters_key)
    n_cases = len(case_ids)
    if n_cases == 0:
        log.warning("reaction_kpis: 0 cases matched for pts=%r", pts_key[:80])
        return {"n_cases": 0, "n_deaths": 0, "n_serious": 0}

    outc_sub = tables["outc"][tables["outc"]["primaryid"].isin(case_ids)]
    vc = outc_sub["outc_cod"].value_counts()
    result = {
        "n_cases": n_cases,
        "n_deaths": int(vc.get("DE", 0)),
        "n_serious": int(outc_sub["primaryid"].nunique()),
    }
    log.info("reaction_kpis: %s cases, %s deaths", f"{n_cases:,}", f"{result['n_deaths']:,}")
    return result


@st.cache_data(show_spinner=False)
def reaction_top_drugs(pts_key: str, role: str, quarters_key: str, top_n: int) -> pd.DataFrame:
    tables = dl.load_tables()
    case_ids = _reaction_case_ids(pts_key, quarters_key)
    total = len(case_ids)
    if total == 0:
        return pd.DataFrame(columns=["drug_label", "case_count", "pct"])

    drug_sub = tables["drug"][tables["drug"]["primaryid"].isin(case_ids)]
    if role != "all":
        drug_sub = drug_sub[drug_sub["role_cod"] == role]

    counts = (
        drug_sub.groupby("canon")["primaryid"]
        .nunique()
        .sort_values(ascending=False)
        .head(top_n)
        .reset_index()
    )
    counts.columns = ["drug_label", "case_count"]
    counts["pct"] = (counts["case_count"] / total * 100).round(1)
    return counts


@st.cache_data(show_spinner=False)
def reaction_outcomes(pts_key: str, quarters_key: str) -> pd.DataFrame:
    tables = dl.load_tables()
    case_ids = _reaction_case_ids(pts_key, quarters_key)
    total = len(case_ids)
    if total == 0:
        return pd.DataFrame(columns=["outcome_label", "count", "pct"])

    outc_sub = tables["outc"][tables["outc"]["primaryid"].isin(case_ids)]
    vc = outc_sub["outc_cod"].value_counts().reset_index()
    vc.columns = ["outc_cod", "count"]
    vc["outcome_label"] = vc["outc_cod"].map(ana.OUTCOME_LABELS).fillna(vc["outc_cod"])
    vc["pct"] = (vc["count"] / total * 100).round(1)
    return vc[["outcome_label", "count", "pct"]].sort_values("count", ascending=False)


@st.cache_data(show_spinner=False)
def reaction_trend(pts_key: str, quarters_key: str) -> pd.DataFrame:
    tables = dl.load_tables()
    case_ids = _reaction_case_ids(pts_key, quarters_key)
    if not case_ids:
        return pd.DataFrame(columns=["quarter", "case_count"])

    demo = tables["demo"][tables["demo"]["primaryid"].isin(case_ids)]
    trend = demo.groupby("quarter")["primaryid"].nunique().reset_index()
    trend.columns = ["quarter", "case_count"]
    return trend.sort_values("quarter")


# ── Global overview queries ───────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def global_kpis() -> dict:
    log.info("global_kpis: computing...")
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

    result = {
        "n_cases":  n_cases,
        "n_deaths": n_deaths,
        "n_drugs":  n_drugs,
        "n_pts":    n_pts,
        "n_hosp":   hosp,
        "n_lt":     lt,
    }
    log.info("global_kpis: %s cases  %s deaths  %s drugs  %s PTs",
             f"{n_cases:,}", f"{n_deaths:,}", f"{n_drugs:,}", f"{n_pts:,}")
    return result


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
    log.info("drug_comparison_kpis: A=%r  B=%r  role=%s",
             names_key_a[:40], names_key_b[:40], role)
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

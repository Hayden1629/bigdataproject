"""
analytics.py

All query / aggregation logic.
Uses pre-computed cache tables for speed-critical paths;
falls back to live pandas computation when cache is unavailable.
"""

from __future__ import annotations

import pandas as pd
from data_loader import load_quarterly_drug, load_quarterly_reac
from logger import get_logger

log = get_logger(__name__)

OUTCOME_LABELS: dict[str, str] = {
    "DE": "Death",
    "LT": "Life-threatening",
    "HO": "Hospitalisation",
    "DS": "Disability",
    "CA": "Congenital anomaly",
    "RI": "Required intervention",
    "OT": "Other serious",
}

AGE_LABELS: dict[str, str] = {"N": "Neonate", "I": "Infant", "C": "Child", "T": "Teen", "A": "Adult", "E": "Elderly"}
SEX_LABELS: dict[str, str] = {"M": "Male", "F": "Female", "UNK": "Unknown"}
OCCP_LABELS: dict[str, str] = {
    "MD": "Physician", "PH": "Pharmacist", "RN": "Nurse",
    "OT": "Other HCP", "LW": "Lawyer", "CN": "Consumer", "HP": "Health Professional",
}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _drug_case_ids(drug_df: pd.DataFrame, name_set: set[str], role: str) -> set:
    mask = drug_df["canon"].isin(name_set)
    if role != "all":
        mask = mask & (drug_df["role_cod"] == role)
    return set(drug_df.loc[mask, "primaryid"].unique())


def _pt_case_ids(reac_df: pd.DataFrame, pt_set: set[str]) -> set:
    return set(reac_df.loc[reac_df["pt_norm"].isin(pt_set), "primaryid"].unique())


# ── Drug analytics ────────────────────────────────────────────────────────────

def kpis_for_drug(
    drug_df: pd.DataFrame,
    outc_df: pd.DataFrame,
    name_set: set[str],
    role: str = "PS",
) -> dict:
    case_ids = _drug_case_ids(drug_df, name_set, role)
    n = len(case_ids)
    if n == 0:
        return {"n_cases": 0, "n_deaths": 0, "n_hosp": 0, "n_lt": 0, "n_serious": 0, "death_pct": 0.0}

    outc_sub = outc_df[outc_df["primaryid"].isin(case_ids)]
    vc = outc_sub["outc_cod"].value_counts()
    n_deaths = int(vc.get("DE", 0))
    n_hosp   = int(vc.get("HO", 0))
    n_lt     = int(vc.get("LT", 0))
    n_serious = int(outc_sub["primaryid"].nunique())

    return {
        "n_cases":  n,
        "n_deaths": n_deaths,
        "n_hosp":   n_hosp,
        "n_lt":     n_lt,
        "n_serious": n_serious,
        "death_pct": round(n_deaths / n * 100, 2),
    }


def top_reactions_for_drug(
    drug_df: pd.DataFrame,
    reac_df: pd.DataFrame,
    name_set: set[str],
    role: str = "PS",
    top_n: int = 20,
) -> pd.DataFrame:
    case_ids = _drug_case_ids(drug_df, name_set, role)
    total = len(case_ids)
    if total == 0:
        return pd.DataFrame(columns=["pt", "count", "pct"])

    sub = reac_df[reac_df["primaryid"].isin(case_ids)]
    counts = sub["pt_norm"].value_counts().head(top_n).reset_index()
    counts.columns = ["pt", "count"]
    counts["pct"] = (counts["count"] / total * 100).round(1)
    return counts


def outcomes_for_drug(
    drug_df: pd.DataFrame,
    outc_df: pd.DataFrame,
    name_set: set[str],
    role: str = "PS",
) -> pd.DataFrame:
    case_ids = _drug_case_ids(drug_df, name_set, role)
    total = len(case_ids)
    if total == 0:
        return pd.DataFrame(columns=["outcome_label", "count", "pct"])

    outc_sub = outc_df[outc_df["primaryid"].isin(case_ids)]
    vc = outc_sub["outc_cod"].value_counts().reset_index()
    vc.columns = ["outc_cod", "count"]
    vc["outcome_label"] = vc["outc_cod"].map(OUTCOME_LABELS).fillna(vc["outc_cod"])
    vc["pct"] = (vc["count"] / total * 100).round(1)
    return vc[["outcome_label", "count", "pct"]].sort_values("count", ascending=False)


def quarterly_trend_for_drug(
    name_set: set[str],
    drug_df: pd.DataFrame,
    role: str = "PS",
    quarter_filter: list[str] | None = None,
) -> pd.DataFrame:
    """Uses pre-computed quarterly cache if available (much faster)."""
    qd = load_quarterly_drug()
    if qd is not None:
        sub = qd[qd["drug"].isin(name_set)]
        if role != "all":
            # Pre-computed table doesn't carry role_cod; fall back
            log.debug("quarterly_trend_for_drug: role=%r → cache miss, using live fallback", role)
            sub = None
        if sub is not None and not sub.empty:
            log.debug("quarterly_trend_for_drug: cache hit for %s", list(name_set)[:2])
            trend = sub.groupby("quarter")["n_cases"].sum().reset_index()
            trend.columns = ["quarter", "case_count"]
            if quarter_filter:
                trend = trend[trend["quarter"].isin(quarter_filter)]
            return trend.sort_values("quarter")
    else:
        log.debug("quarterly_trend_for_drug: quarterly_drug cache not available, using live fallback")

    # Live fallback
    mask = drug_df["canon"].isin(name_set)
    if role != "all":
        mask = mask & (drug_df["role_cod"] == role)
    sub = drug_df.loc[mask, ["primaryid", "quarter"]].drop_duplicates()
    if quarter_filter:
        sub = sub[sub["quarter"].isin(quarter_filter)]
    trend = sub.groupby("quarter")["primaryid"].nunique().reset_index()
    trend.columns = ["quarter", "case_count"]
    return trend.sort_values("quarter")


def demographics_for_drug(
    drug_df: pd.DataFrame,
    demo_df: pd.DataFrame,
    name_set: set[str],
    role: str = "PS",
) -> dict[str, pd.DataFrame]:
    case_ids = _drug_case_ids(drug_df, name_set, role)
    sub = demo_df[demo_df["primaryid"].isin(case_ids)]

    sex = sub["sex"].value_counts().reset_index()
    sex.columns = ["sex_label", "count"]
    sex["sex_label"] = sex["sex_label"].map(SEX_LABELS).fillna(sex["sex_label"])

    age = sub["age_grp"].value_counts().reset_index()
    age.columns = ["age_group_label", "count"]
    age["age_group_label"] = age["age_group_label"].map(AGE_LABELS).fillna(age["age_group_label"])

    rep = sub["occp_cod"].value_counts().reset_index()
    rep.columns = ["reporter", "count"]
    rep["reporter"] = rep["reporter"].map(OCCP_LABELS).fillna(rep["reporter"])

    return {"sex": sex, "age_grp": age, "reporter": rep}


# ── Reaction analytics ────────────────────────────────────────────────────────

def kpis_for_reaction(
    reac_df: pd.DataFrame,
    outc_df: pd.DataFrame,
    pt_set: set[str],
) -> dict:
    case_ids = _pt_case_ids(reac_df, pt_set)
    n = len(case_ids)
    if n == 0:
        return {"n_cases": 0, "n_deaths": 0, "n_serious": 0}

    outc_sub = outc_df[outc_df["primaryid"].isin(case_ids)]
    vc = outc_sub["outc_cod"].value_counts()
    return {
        "n_cases":  n,
        "n_deaths": int(vc.get("DE", 0)),
        "n_serious": int(outc_sub["primaryid"].nunique()),
    }


def top_drugs_for_reaction(
    drug_df: pd.DataFrame,
    reac_df: pd.DataFrame,
    pt_set: set[str],
    role: str = "PS",
    top_n: int = 20,
) -> pd.DataFrame:
    case_ids = _pt_case_ids(reac_df, pt_set)
    total = len(case_ids)
    if total == 0:
        return pd.DataFrame(columns=["drug_label", "case_count", "pct"])

    drug_sub = drug_df[drug_df["primaryid"].isin(case_ids)]
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


def outcomes_for_reaction(
    reac_df: pd.DataFrame,
    outc_df: pd.DataFrame,
    pt_set: set[str],
) -> pd.DataFrame:
    case_ids = _pt_case_ids(reac_df, pt_set)
    total = len(case_ids)
    if total == 0:
        return pd.DataFrame(columns=["outcome_label", "count", "pct"])

    outc_sub = outc_df[outc_df["primaryid"].isin(case_ids)]
    vc = outc_sub["outc_cod"].value_counts().reset_index()
    vc.columns = ["outc_cod", "count"]
    vc["outcome_label"] = vc["outc_cod"].map(OUTCOME_LABELS).fillna(vc["outc_cod"])
    vc["pct"] = (vc["count"] / total * 100).round(1)
    return vc[["outcome_label", "count", "pct"]].sort_values("count", ascending=False)


def quarterly_trend_for_reaction(
    pt_set: set[str],
    reac_df: pd.DataFrame,
    quarter_filter: list[str] | None = None,
) -> pd.DataFrame:
    """Uses pre-computed quarterly cache if available."""
    qr = load_quarterly_reac()
    if qr is not None:
        sub = qr[qr["pt"].isin(pt_set)]
        if not sub.empty:
            log.debug("quarterly_trend_for_reaction: cache hit for %s", list(pt_set)[:2])
            trend = sub.groupby("quarter")["n_cases"].sum().reset_index()
            trend.columns = ["quarter", "case_count"]
            if quarter_filter:
                trend = trend[trend["quarter"].isin(quarter_filter)]
            return trend.sort_values("quarter")
    else:
        log.debug("quarterly_trend_for_reaction: quarterly_reac cache not available, using live fallback")

    # Live fallback
    mask = reac_df["pt_norm"].isin(pt_set)
    sub = reac_df.loc[mask, ["primaryid", "quarter"]].drop_duplicates()
    if quarter_filter:
        sub = sub[sub["quarter"].isin(quarter_filter)]
    trend = sub.groupby("quarter")["primaryid"].nunique().reset_index()
    trend.columns = ["quarter", "case_count"]
    return trend.sort_values("quarter")


# ── Drug × Reaction co-occurrence ─────────────────────────────────────────────

def cooccurrence_stats(
    drug_df: pd.DataFrame,
    reac_df: pd.DataFrame,
    outc_df: pd.DataFrame,
    name_set: set[str],
    pt_set: set[str],
    role: str = "PS",
    n_total: int = 0,
) -> dict:
    drug_ids = _drug_case_ids(drug_df, name_set, role)
    reac_ids = _pt_case_ids(reac_df, pt_set)
    overlap  = drug_ids & reac_ids

    death_pids = set(outc_df.loc[outc_df["outc_cod"] == "DE", "primaryid"].unique())
    n_deaths_overlap = len(overlap & death_pids)

    prr_val = None
    if n_total and drug_ids and reac_ids:
        a = len(overlap)
        n_d = len(drug_ids)
        n_r = len(reac_ids)
        c = n_r - a
        prr_val = round((a / n_d) / (max(c, 0.5) / max(n_total - n_d, 1)), 3) if n_d else None

    return {
        "drug_cases":    len(drug_ids),
        "reaction_cases": len(reac_ids),
        "overlap_cases": len(overlap),
        "pct_of_drug":   round(len(overlap) / len(drug_ids) * 100, 1) if drug_ids else 0,
        "pct_of_reac":   round(len(overlap) / len(reac_ids) * 100, 1) if reac_ids else 0,
        "deaths_in_overlap": n_deaths_overlap,
        "live_prr":      prr_val,
    }

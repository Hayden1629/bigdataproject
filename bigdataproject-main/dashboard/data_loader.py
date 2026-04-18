from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARQUET_DIR = PROJECT_ROOT / "data" / "parquet_recent"
DEFAULT_CACHE_DIR = PROJECT_ROOT / "dashboard" / "cache_recent"


def parquet_dir() -> Path:
    return Path(os.environ.get("FAERS_PARQUET_DIR", str(DEFAULT_PARQUET_DIR))).resolve()


def cache_dir() -> Path:
    return Path(os.environ.get("FAERS_CACHE_DIR", str(DEFAULT_CACHE_DIR))).resolve()


def _empty(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def _safe_read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _year_q_from_quarter(series: pd.Series) -> pd.Series:
    out = series.astype(str).str.upper().str.replace(" ", "", regex=False)
    return out.where(out.str.contains(r"^\d{4}Q[1-4]$", regex=True), "")


def _parse_listish(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    if value is None:
        return []
    txt = str(value).strip()
    if not txt:
        return []
    if txt.startswith("[") and txt.endswith("]"):
        try:
            parsed = ast.literal_eval(txt)
            if isinstance(parsed, list):
                return [str(v) for v in parsed if str(v).strip()]
        except Exception:
            return []
    return [p.strip() for p in txt.split("|") if p.strip()]


def _normalize_raw_tables(raw: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    demo = raw.get("demo", pd.DataFrame()).copy()
    drug = raw.get("drug", pd.DataFrame()).copy()
    reac = raw.get("reac", pd.DataFrame()).copy()
    outc = raw.get("outc", pd.DataFrame()).copy()
    rpsr = raw.get("rpsr", pd.DataFrame()).copy()
    indi = raw.get("indi", pd.DataFrame()).copy()

    for df in [demo, drug, reac, outc, rpsr, indi]:
        if not df.empty:
            df.columns = [c.strip().lower() for c in df.columns]

    if demo.empty:
        demo_slim = _empty(
            [
                "primaryid",
                "year_q",
                "event_dt",
                "sex",
                "age",
                "occr_country",
                "mfr_sndr",
                "canonical_mfr",
                "lit_ref",
            ]
        )
    else:
        if "quarter" in demo.columns and "year_q" not in demo.columns:
            demo["year_q"] = _year_q_from_quarter(demo["quarter"])
        if "year_q" not in demo.columns:
            demo["year_q"] = ""
        demo_slim = pd.DataFrame(
            {
                "primaryid": demo.get("primaryid", "").astype(str),
                "year_q": demo.get("year_q", "").astype(str),
                "event_dt": demo.get("event_dt", "").astype(str),
                "sex": demo.get("sex", "").astype(str),
                "age": pd.to_numeric(
                    demo.get("age", pd.Series(dtype=float)), errors="coerce"
                ),
                "occr_country": demo.get("occr_country", "").astype(str),
                "mfr_sndr": demo.get("mfr_sndr", "").astype(str),
                "canonical_mfr": demo.get("mfr_sndr", "").map(
                    lambda x: canonicalize_mfr(str(x))
                ),
                "lit_ref": demo.get("lit_ref", "").astype(str),
            }
        ).drop_duplicates()

    if drug.empty:
        drug_records_slim = _empty(
            [
                "primaryid",
                "year_q",
                "role_cod",
                "drugname",
                "drugname_norm",
                "prod_ai",
                "prod_ai_norm",
                "route",
                "dose_amt",
                "dose_unit",
                "dose_form",
                "dose_freq",
                "mfr_sndr",
                "canonical_mfr",
            ]
        )
    else:
        if "quarter" in drug.columns and "year_q" not in drug.columns:
            drug["year_q"] = _year_q_from_quarter(drug["quarter"])
        if "year_q" not in drug.columns:
            drug["year_q"] = ""
        drug_records_slim = pd.DataFrame(
            {
                "primaryid": drug.get("primaryid", "").astype(str),
                "year_q": drug.get("year_q", "").astype(str),
                "role_cod": drug.get("role_cod", "").astype(str).str.upper(),
                "drugname": drug.get("drugname", "").astype(str),
                "drugname_norm": drug.get("drugname", "").map(_normalize_text),
                "prod_ai": drug.get("prod_ai", "").astype(str),
                "prod_ai_norm": drug.get("prod_ai", "").map(_normalize_text),
                "route": drug.get("route", "").astype(str),
                "dose_amt": drug.get("dose_amt", "").astype(str),
                "dose_unit": drug.get("dose_unit", "").astype(str),
                "dose_form": drug.get("dose_form", "").astype(str),
                "dose_freq": drug.get("dose_freq", "").astype(str),
                "mfr_sndr": drug.get("mfr_sndr", "").astype(str),
                "canonical_mfr": drug.get("mfr_sndr", "").map(
                    lambda x: canonicalize_mfr(str(x))
                ),
            }
        ).drop_duplicates()

    if reac.empty:
        reac_slim = _empty(["primaryid", "year_q", "pt", "pt_norm"])
    else:
        if "quarter" in reac.columns and "year_q" not in reac.columns:
            reac["year_q"] = _year_q_from_quarter(reac["quarter"])
        if "year_q" not in reac.columns:
            reac["year_q"] = ""
        reac_slim = pd.DataFrame(
            {
                "primaryid": reac.get("primaryid", "").astype(str),
                "year_q": reac.get("year_q", "").astype(str),
                "pt": reac.get("pt", "").astype(str),
                "pt_norm": reac.get("pt", "").map(_normalize_text),
            }
        ).drop_duplicates()

    if outc.empty:
        outc_slim = _empty(["primaryid", "year_q", "outc_cod"])
    else:
        if "quarter" in outc.columns and "year_q" not in outc.columns:
            outc["year_q"] = _year_q_from_quarter(outc["quarter"])
        if "year_q" not in outc.columns:
            outc["year_q"] = ""
        outc_slim = pd.DataFrame(
            {
                "primaryid": outc.get("primaryid", "").astype(str),
                "year_q": outc.get("year_q", "").astype(str),
                "outc_cod": outc.get("outc_cod", "").astype(str).str.upper(),
            }
        ).drop_duplicates()

    if rpsr.empty:
        rpsr_slim = _empty(["primaryid", "year_q", "rpsr_cod"])
    else:
        if "quarter" in rpsr.columns and "year_q" not in rpsr.columns:
            rpsr["year_q"] = _year_q_from_quarter(rpsr["quarter"])
        if "year_q" not in rpsr.columns:
            rpsr["year_q"] = ""
        rpsr_slim = pd.DataFrame(
            {
                "primaryid": rpsr.get("primaryid", "").astype(str),
                "year_q": rpsr.get("year_q", "").astype(str),
                "rpsr_cod": rpsr.get("rpsr_cod", "").astype(str).str.upper(),
            }
        ).drop_duplicates()

    if indi.empty:
        indi_slim = _empty(["primaryid", "year_q", "indi_pt", "indi_pt_norm"])
    else:
        if "quarter" in indi.columns and "year_q" not in indi.columns:
            indi["year_q"] = _year_q_from_quarter(indi["quarter"])
        if "year_q" not in indi.columns:
            indi["year_q"] = ""
        indi_slim = pd.DataFrame(
            {
                "primaryid": indi.get("primaryid", "").astype(str),
                "year_q": indi.get("year_q", "").astype(str),
                "indi_pt": indi.get("indi_pt", "").astype(str),
                "indi_pt_norm": indi.get("indi_pt", "").map(_normalize_text),
            }
        ).drop_duplicates()

    return {
        "demo_slim": demo_slim,
        "drug_records_slim": drug_records_slim,
        "reac_slim": reac_slim,
        "outc_slim": outc_slim,
        "rpsr_slim": rpsr_slim,
        "indi_slim": indi_slim,
    }


def canonicalize_mfr(text: str) -> str:
    cleaned = "".join(
        ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in text or ""
    )
    tokens = [t for t in cleaned.split() if t]
    suffixes = {
        "inc",
        "incorporated",
        "corp",
        "corporation",
        "company",
        "co",
        "ltd",
        "limited",
        "llc",
        "plc",
        "ag",
        "gmbh",
        "sa",
        "nv",
        "bv",
        "oyj",
        "kk",
    }
    while tokens and tokens[-1] in suffixes:
        tokens.pop()
    return " ".join(tokens).strip()


@st.cache_resource(show_spinner=False)
def load_runtime_tables() -> dict[str, pd.DataFrame]:
    cdir = cache_dir()
    tables = {
        "demo_slim": _safe_read_parquet(cdir / "demo_slim.parquet"),
        "drug_records_slim": _safe_read_parquet(cdir / "drug_records_slim.parquet"),
        "reac_slim": _safe_read_parquet(cdir / "reac_slim.parquet"),
        "outc_slim": _safe_read_parquet(cdir / "outc_slim.parquet"),
        "rpsr_slim": _safe_read_parquet(cdir / "rpsr_slim.parquet"),
        "indi_slim": _safe_read_parquet(cdir / "indi_slim.parquet"),
        "drug_summary": _safe_read_parquet(cdir / "drug_summary.parquet"),
        "reac_summary": _safe_read_parquet(cdir / "reac_summary.parquet"),
        "manufacturer_summary": _safe_read_parquet(
            cdir / "manufacturer_summary.parquet"
        ),
        "fact_drug_quarter": _safe_read_parquet(cdir / "fact_drug_quarter.parquet"),
        "fact_reac_quarter": _safe_read_parquet(cdir / "fact_reac_quarter.parquet"),
        "fact_manufacturer_quarter": _safe_read_parquet(
            cdir / "fact_manufacturer_quarter.parquet"
        ),
        "global_kpis": _safe_read_parquet(cdir / "global_kpis.parquet"),
        "lookup_quarter_cases": _safe_read_parquet(
            cdir / "lookup_quarter_cases.parquet"
        ),
        "lookup_drug_cases": _safe_read_parquet(cdir / "lookup_drug_cases.parquet"),
        "lookup_drug_role_cases": _safe_read_parquet(
            cdir / "lookup_drug_role_cases.parquet"
        ),
        "lookup_reaction_cases": _safe_read_parquet(
            cdir / "lookup_reaction_cases.parquet"
        ),
        "lookup_manufacturer_cases": _safe_read_parquet(
            cdir / "lookup_manufacturer_cases.parquet"
        ),
        "manufacturer_name_lookup": _safe_read_parquet(
            cdir / "manufacturer_name_lookup.parquet"
        ),
        "drug_name_lookup": _safe_read_parquet(cdir / "drug_name_lookup.parquet"),
        "dose_bucket_slim": _safe_read_parquet(cdir / "dose_bucket_slim.parquet"),
    }

    has_cache = any(not df.empty for df in tables.values())
    if has_cache:
        return tables

    pdir = parquet_dir()
    raw = {
        "demo": _safe_read_parquet(pdir / "demo.parquet"),
        "drug": _safe_read_parquet(pdir / "drug.parquet"),
        "reac": _safe_read_parquet(pdir / "reac.parquet"),
        "outc": _safe_read_parquet(pdir / "outc.parquet"),
        "rpsr": _safe_read_parquet(pdir / "rpsr.parquet"),
        "indi": _safe_read_parquet(pdir / "indi.parquet"),
    }
    normalized = _normalize_raw_tables(raw)
    tables.update(normalized)
    return tables


def warm_all_tables() -> None:
    load_runtime_tables()


def get_dataset_profile() -> dict[str, Any]:
    t = load_runtime_tables()
    demo = t["demo_slim"]
    if demo.empty:
        return {
            "mode": "unknown",
            "cases": 0,
            "quarter_min": "-",
            "quarter_max": "-",
            "quarters": [],
        }
    quarters = sorted([q for q in demo["year_q"].dropna().astype(str).unique() if q])
    return {
        "mode": "recent" if "recent" in str(cache_dir()).lower() else "full",
        "cases": int(demo["primaryid"].nunique()),
        "quarter_min": quarters[0] if quarters else "-",
        "quarter_max": quarters[-1] if quarters else "-",
        "quarters": quarters,
    }


def get_quarters() -> list[str]:
    profile = get_dataset_profile()
    return profile["quarters"]


def load_drug_name_lookup() -> pd.DataFrame:
    t = load_runtime_tables()
    lookup = t.get("drug_name_lookup", pd.DataFrame())
    if not lookup.empty:
        return lookup
    drug = t["drug_records_slim"]
    if drug.empty:
        return _empty(["drugname", "drugname_norm", "prod_ai", "prod_ai_norm"])
    return (
        drug[["drugname", "drugname_norm", "prod_ai", "prod_ai_norm"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )


def load_manufacturer_lookup() -> pd.DataFrame:
    t = load_runtime_tables()
    lookup = t.get("manufacturer_name_lookup", pd.DataFrame())
    if not lookup.empty:
        return lookup
    drug = t["drug_records_slim"]
    if drug.empty:
        return _empty(["mfr_sndr", "canonical_mfr", "n_cases"])
    demo = t["demo_slim"]
    out = (
        demo[["mfr_sndr", "canonical_mfr", "primaryid"]]
        .query("canonical_mfr != ''")
        .groupby(["mfr_sndr", "canonical_mfr"], as_index=False)["primaryid"]
        .nunique()
        .rename(columns={"primaryid": "n_cases"})
    )
    return out.sort_values("n_cases", ascending=False)


def get_all_reaction_terms() -> list[str]:
    t = load_runtime_tables()
    reac = t["reac_slim"]
    if reac.empty:
        return []
    return sorted(reac["pt"].dropna().astype(str).unique().tolist())


def parse_primaryid_list_column(series: pd.Series) -> pd.Series:
    return series.map(_parse_listish)

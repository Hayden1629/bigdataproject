from __future__ import annotations

import os
from pathlib import Path
import sys

import pandas as pd

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard.data_loader import canonicalize_mfr


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARQUET_DIR = Path(
    os.environ.get("FAERS_PARQUET_DIR", PROJECT_ROOT / "data" / "parquet_recent")
).resolve()
CACHE_DIR = Path(
    os.environ.get("FAERS_CACHE_DIR", PROJECT_ROOT / "dashboard" / "cache_recent")
).resolve()


def _read(name: str) -> pd.DataFrame:
    path = PARQUET_DIR / f"{name}.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    df.columns = [c.lower().strip() for c in df.columns]
    return df


def _year_q(df: pd.DataFrame) -> pd.Series:
    if "year_q" in df.columns:
        return df["year_q"].astype(str)
    if "quarter" in df.columns:
        return df["quarter"].astype(str).str.upper().str.replace(" ", "", regex=False)
    return pd.Series([""] * len(df))


def _safe_str(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series([""] * len(df))
    return df[col].astype(str)


def _write(df: pd.DataFrame, name: str) -> None:
    path = CACHE_DIR / f"{name}.parquet"
    df.to_parquet(path, index=False)
    print(f"Wrote {name}.parquet ({len(df):,} rows)")


def _listify_lookup(df: pd.DataFrame, key: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[key, "primaryids", "n_cases"])
    out = (
        df.groupby(key, as_index=False)["primaryid"]
        .agg(lambda s: sorted(set(s.astype(str))))
        .rename(columns={"primaryid": "primaryids"})
    )
    out["n_cases"] = out["primaryids"].map(len)
    return out


def main() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    demo = _read("demo")
    drug = _read("drug")
    reac = _read("reac")
    outc = _read("outc")
    rpsr = _read("rpsr")
    indi = _read("indi")

    if demo.empty:
        raise SystemExit(f"No demo.parquet found in {PARQUET_DIR}")

    demo_slim = pd.DataFrame(
        {
            "primaryid": _safe_str(demo, "primaryid"),
            "year_q": _year_q(demo),
            "event_dt": _safe_str(demo, "event_dt"),
            "sex": _safe_str(demo, "sex"),
            "age": pd.to_numeric(demo["age"], errors="coerce")
            if "age" in demo.columns
            else pd.Series([None] * len(demo)),
            "occr_country": _safe_str(demo, "occr_country"),
            "mfr_sndr": _safe_str(demo, "mfr_sndr"),
            "lit_ref": _safe_str(demo, "lit_ref"),
        }
    ).drop_duplicates()
    demo_slim["canonical_mfr"] = demo_slim["mfr_sndr"].map(canonicalize_mfr)

    drug_slim = pd.DataFrame(
        {
            "primaryid": _safe_str(drug, "primaryid"),
            "year_q": _year_q(drug),
            "role_cod": _safe_str(drug, "role_cod").str.upper(),
            "drugname": _safe_str(drug, "drugname"),
            "drugname_norm": _safe_str(drug, "drugname").str.lower().str.strip(),
            "prod_ai": _safe_str(drug, "prod_ai"),
            "prod_ai_norm": _safe_str(drug, "prod_ai").str.lower().str.strip(),
            "route": _safe_str(drug, "route"),
            "dose_amt": _safe_str(drug, "dose_amt"),
            "dose_unit": _safe_str(drug, "dose_unit"),
            "dose_form": _safe_str(drug, "dose_form"),
            "dose_freq": _safe_str(drug, "dose_freq"),
            "mfr_sndr": _safe_str(drug, "mfr_sndr"),
        }
    ).drop_duplicates()
    drug_slim["canonical_mfr"] = drug_slim["mfr_sndr"].map(canonicalize_mfr)

    reac_slim = pd.DataFrame(
        {
            "primaryid": _safe_str(reac, "primaryid"),
            "year_q": _year_q(reac),
            "pt": _safe_str(reac, "pt"),
            "pt_norm": _safe_str(reac, "pt").str.lower().str.strip(),
        }
    ).drop_duplicates()

    outc_slim = pd.DataFrame(
        {
            "primaryid": _safe_str(outc, "primaryid"),
            "year_q": _year_q(outc),
            "outc_cod": _safe_str(outc, "outc_cod").str.upper(),
        }
    ).drop_duplicates()

    rpsr_slim = pd.DataFrame(
        {
            "primaryid": _safe_str(rpsr, "primaryid"),
            "year_q": _year_q(rpsr),
            "rpsr_cod": _safe_str(rpsr, "rpsr_cod").str.upper(),
        }
    ).drop_duplicates()

    indi_slim = pd.DataFrame(
        {
            "primaryid": _safe_str(indi, "primaryid"),
            "year_q": _year_q(indi),
            "indi_pt": _safe_str(indi, "indi_pt"),
            "indi_pt_norm": _safe_str(indi, "indi_pt").str.lower().str.strip(),
        }
    ).drop_duplicates()

    drug_summary = (
        drug_slim.groupby("drugname", as_index=False)["primaryid"]
        .nunique()
        .rename(columns={"primaryid": "n_cases"})
        .sort_values("n_cases", ascending=False)
    )
    reac_summary = (
        reac_slim.groupby("pt", as_index=False)["primaryid"]
        .nunique()
        .rename(columns={"primaryid": "n_cases"})
        .sort_values("n_cases", ascending=False)
    )
    manufacturer_summary = (
        demo_slim[demo_slim["canonical_mfr"] != ""]
        .groupby("canonical_mfr", as_index=False)["primaryid"]
        .nunique()
        .rename(columns={"primaryid": "n_cases"})
        .sort_values("n_cases", ascending=False)
    )

    fact_drug_quarter = (
        drug_slim.groupby(["drugname", "year_q"], as_index=False)["primaryid"]
        .nunique()
        .rename(columns={"primaryid": "n_cases"})
    )
    fact_reac_quarter = (
        reac_slim.groupby(["pt", "year_q"], as_index=False)["primaryid"]
        .nunique()
        .rename(columns={"primaryid": "n_cases"})
    )
    fact_manufacturer_quarter = (
        demo_slim[demo_slim["canonical_mfr"] != ""]
        .groupby(["canonical_mfr", "year_q"], as_index=False)["primaryid"]
        .nunique()
        .rename(columns={"primaryid": "n_cases"})
    )

    lookup_quarter_cases = _listify_lookup(
        demo_slim[["year_q", "primaryid"]].drop_duplicates(), "year_q"
    )
    lookup_drug_cases = _listify_lookup(
        drug_slim[["drugname", "primaryid"]].drop_duplicates(), "drugname"
    )
    lookup_drug_role_cases = _listify_lookup(
        drug_slim.assign(drug_role_key=lambda x: x["drugname"] + "|" + x["role_cod"])[
            ["drug_role_key", "primaryid"]
        ].drop_duplicates(),
        "drug_role_key",
    )
    lookup_reaction_cases = _listify_lookup(
        reac_slim[["pt", "primaryid"]].drop_duplicates(), "pt"
    )
    lookup_manufacturer_cases = _listify_lookup(
        demo_slim[demo_slim["canonical_mfr"] != ""][
            ["canonical_mfr", "primaryid"]
        ].drop_duplicates(),
        "canonical_mfr",
    )

    manufacturer_name_lookup = (
        demo_slim[demo_slim["mfr_sndr"].str.strip() != ""]
        .groupby(["mfr_sndr", "canonical_mfr"], as_index=False)["primaryid"]
        .nunique()
        .rename(columns={"primaryid": "n_cases"})
        .sort_values("n_cases", ascending=False)
    )

    dose_bucket_slim = drug_slim[["primaryid", "dose_amt", "dose_unit"]].copy()
    dose_bucket_slim["dose_amt_bucket"] = (
        dose_bucket_slim["dose_amt"].str.strip().replace("", "Not reported")
    )
    dose_bucket_slim["dose_unit_norm"] = (
        dose_bucket_slim["dose_unit"].str.strip().str.lower()
    )

    global_kpis = pd.DataFrame(
        [
            {
                "cases": int(demo_slim["primaryid"].nunique()),
                "deaths": int(
                    outc_slim[outc_slim["outc_cod"] == "DE"]["primaryid"].nunique()
                ),
                "unique_drugs": int(drug_slim["drugname"].nunique()),
                "unique_reactions": int(reac_slim["pt"].nunique()),
                "quarter_min": str(
                    demo_slim["year_q"].min() if not demo_slim.empty else ""
                ),
                "quarter_max": str(
                    demo_slim["year_q"].max() if not demo_slim.empty else ""
                ),
            }
        ]
    )

    drug_name_lookup = drug_slim[
        ["drugname", "drugname_norm", "prod_ai", "prod_ai_norm"]
    ].drop_duplicates()

    outputs = {
        "demo_slim": demo_slim,
        "drug_records_slim": drug_slim,
        "reac_slim": reac_slim,
        "outc_slim": outc_slim,
        "rpsr_slim": rpsr_slim,
        "indi_slim": indi_slim,
        "drug_summary": drug_summary,
        "reac_summary": reac_summary,
        "manufacturer_summary": manufacturer_summary,
        "fact_drug_quarter": fact_drug_quarter,
        "fact_reac_quarter": fact_reac_quarter,
        "fact_manufacturer_quarter": fact_manufacturer_quarter,
        "lookup_quarter_cases": lookup_quarter_cases,
        "lookup_drug_cases": lookup_drug_cases,
        "lookup_drug_role_cases": lookup_drug_role_cases,
        "lookup_reaction_cases": lookup_reaction_cases,
        "lookup_manufacturer_cases": lookup_manufacturer_cases,
        "manufacturer_name_lookup": manufacturer_name_lookup,
        "dose_bucket_slim": dose_bucket_slim,
        "global_kpis": global_kpis,
        "drug_name_lookup": drug_name_lookup,
    }

    for name, frame in outputs.items():
        _write(frame, name)

    print(f"\nPrecompute complete. Cache directory: {CACHE_DIR}")


if __name__ == "__main__":
    main()

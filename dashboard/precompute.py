"""
precompute.py

One-time pre-computation for the FAERS dashboard.
Run from the project root:
    python3 claude_test/precompute.py

Outputs (saved to claude_test/cache/):
    prr_table.parquet       - PRR signal table for top 500 drugs × all MedDRA PTs
    drug_summary.parquet    - per-drug aggregate stats
    reac_summary.parquet    - per-PT aggregate stats
    quarterly_drug.parquet  - per-drug per-quarter case counts
    quarterly_reac.parquet  - per-PT per-quarter case counts

PRR (Proportional Reporting Ratio) is the standard pharmacovigilance metric for
detecting drug-reaction signals in spontaneous reporting databases.
Reference: Evans et al. (2001), Pharmacoepidemiol Drug Saf.

Signal criteria:
    HIGH   : PRR >= 4  AND N_DR >= 5 AND chi2 >= 4
    MEDIUM : PRR >= 2  AND N_DR >= 3 AND chi2 >= 4
    LOW    : PRR >= 1.5 AND N_DR >= 3 (not chi2-significant but elevated)
"""

import os
import sys
import numpy as np
import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
HERE         = os.path.dirname(os.path.abspath(__file__))


def _default_cache_dir(parquet_dir: str) -> str:
    base = os.path.basename(os.path.normpath(parquet_dir))
    if base == "parquet_recent":
        cache_name = "cache_recent"
    elif base == "parquet":
        cache_name = "cache_full"
    else:
        cache_name = f"cache_{base}"
    return os.path.join(HERE, cache_name)


PARQUET_DIR  = os.environ.get(
    "FAERS_PARQUET_DIR",
    os.path.abspath(os.path.join(HERE, "..", "data", "parquet_recent")),
)
CACHE_DIR    = os.environ.get("FAERS_CACHE_DIR", _default_cache_dir(PARQUET_DIR))
os.makedirs(CACHE_DIR, exist_ok=True)

TOP_DRUGS    = 500   # compute PRR for the N most-reported drugs
MIN_N_DR     = 3     # minimum co-occurrence count to include a pair
MIN_PRR      = 1.5   # minimum PRR to include a pair

# ── Load & deduplicate ────────────────────────────────────────────────────────

def _load_and_dedup():
    print("Loading parquet files...")
    demo = pd.read_parquet(os.path.join(PARQUET_DIR, "demo.parquet"))
    drug = pd.read_parquet(os.path.join(PARQUET_DIR, "drug.parquet"))
    reac = pd.read_parquet(os.path.join(PARQUET_DIR, "reac.parquet"))
    outc = pd.read_parquet(os.path.join(PARQUET_DIR, "outc.parquet"))

    # Deduplicate demo: keep latest caseversion per caseid
    print("Deduplicating cases...")
    demo["caseversion"] = pd.to_numeric(demo["caseversion"], errors="coerce").fillna(0).astype(int)
    demo = demo.sort_values("caseversion").drop_duplicates("caseid", keep="last")

    valid_pids = set(demo["primaryid"].unique())
    print(f"  Deduplicated cases: {len(valid_pids):,}")

    # Filter all tables to deduplicated cases
    drug = drug[drug["primaryid"].isin(valid_pids)].copy()
    reac = reac[reac["primaryid"].isin(valid_pids)].copy()
    outc = outc[outc["primaryid"].isin(valid_pids)].copy()

    # Normalise names
    drug["prod_ai_norm"] = drug["prod_ai"].str.upper().str.strip()
    drug["drugname_norm"] = drug["drugname"].str.upper().str.strip()
    reac["pt_norm"] = reac["pt"].str.strip().str.title()

    return demo, drug, reac, outc, len(valid_pids)


# ── Drug summary ──────────────────────────────────────────────────────────────

def build_drug_summary(drug_df, outc_df, n_total):
    print("Building drug summary...")
    # Use prod_ai_norm as canonical drug identifier; fall back to drugname_norm
    drug_df = drug_df.copy()
    drug_df["canon"] = drug_df["prod_ai_norm"].fillna(drug_df["drugname_norm"])

    # Count unique cases per drug
    grp = drug_df.groupby("canon")["primaryid"].nunique().reset_index()
    grp.columns = ["drug", "n_cases"]

    # Death count per drug
    death_pids = set(outc_df.loc[outc_df["outc_cod"] == "DE", "primaryid"].unique())
    drug_death = drug_df[drug_df["primaryid"].isin(death_pids)]
    death_grp = drug_death.groupby("canon")["primaryid"].nunique().reset_index()
    death_grp.columns = ["drug", "n_deaths"]

    summary = grp.merge(death_grp, on="drug", how="left").fillna(0)
    summary["n_deaths"] = summary["n_deaths"].astype(int)
    summary["death_pct"] = (summary["n_deaths"] / summary["n_cases"] * 100).round(2)
    summary = summary.sort_values("n_cases", ascending=False).reset_index(drop=True)

    path = os.path.join(CACHE_DIR, "drug_summary.parquet")
    summary.to_parquet(path, index=False)
    print(f"  Saved {len(summary):,} drugs -> {path}")
    return summary


# ── Reaction summary ──────────────────────────────────────────────────────────

def build_reac_summary(reac_df, outc_df):
    print("Building reaction summary...")
    grp = reac_df.groupby("pt_norm")["primaryid"].nunique().reset_index()
    grp.columns = ["pt", "n_cases"]

    death_pids = set(outc_df.loc[outc_df["outc_cod"] == "DE", "primaryid"].unique())
    reac_death = reac_df[reac_df["primaryid"].isin(death_pids)]
    d_grp = reac_death.groupby("pt_norm")["primaryid"].nunique().reset_index()
    d_grp.columns = ["pt", "n_deaths"]

    summary = grp.merge(d_grp, on="pt", how="left").fillna(0)
    summary["n_deaths"] = summary["n_deaths"].astype(int)
    summary["death_pct"] = (summary["n_deaths"] / summary["n_cases"] * 100).round(2)
    summary = summary.sort_values("n_cases", ascending=False).reset_index(drop=True)

    path = os.path.join(CACHE_DIR, "reac_summary.parquet")
    summary.to_parquet(path, index=False)
    print(f"  Saved {len(summary):,} PTs -> {path}")
    return summary


# ── Quarterly trends ──────────────────────────────────────────────────────────

def build_quarterly_trends(drug_df, reac_df):
    print("Building quarterly drug trends...")
    drug_df = drug_df.copy()
    drug_df["canon"] = drug_df["prod_ai_norm"].fillna(drug_df["drugname_norm"])

    qd = (
        drug_df.drop_duplicates(["canon", "primaryid"])
        .groupby(["canon", "quarter"])["primaryid"]
        .nunique()
        .reset_index()
    )
    qd.columns = ["drug", "quarter", "n_cases"]
    path = os.path.join(CACHE_DIR, "quarterly_drug.parquet")
    qd.to_parquet(path, index=False)
    print(f"  Saved {len(qd):,} rows -> {path}")

    print("Building quarterly reaction trends...")
    qr = (
        reac_df.drop_duplicates(["pt_norm", "primaryid"])
        .groupby(["pt_norm", "quarter"])["primaryid"]
        .nunique()
        .reset_index()
    )
    qr.columns = ["pt", "quarter", "n_cases"]
    path = os.path.join(CACHE_DIR, "quarterly_reac.parquet")
    qr.to_parquet(path, index=False)
    print(f"  Saved {len(qr):,} rows -> {path}")


# ── PRR computation ───────────────────────────────────────────────────────────

def build_prr_table(drug_df, reac_df, n_total, top_n=TOP_DRUGS):
    print(f"Building PRR table (top {top_n} drugs)...")

    drug_df = drug_df.copy()
    drug_df["canon"] = drug_df["prod_ai_norm"].fillna(drug_df["drugname_norm"])

    # N_D: unique cases per drug
    n_d_series = (
        drug_df.drop_duplicates(["canon", "primaryid"])
        .groupby("canon")["primaryid"]
        .nunique()
    )
    top_drug_names = n_d_series.nlargest(top_n).index.tolist()

    # Restrict to top drugs for the join (performance)
    drug_sub = drug_df[drug_df["canon"].isin(top_drug_names)][["canon", "primaryid"]].drop_duplicates()
    print(f"  Drug sub rows: {len(drug_sub):,}")

    # N_R: unique cases per PT
    n_r_series = (
        reac_df.drop_duplicates(["pt_norm", "primaryid"])
        .groupby("pt_norm")["primaryid"]
        .nunique()
    )

    # Co-occurrence: join on primaryid
    print("  Computing co-occurrences (inner join)...")
    reac_sub = reac_df[["pt_norm", "primaryid"]].drop_duplicates()
    cooc = drug_sub.merge(reac_sub, on="primaryid")
    print(f"  Co-occurrence rows: {len(cooc):,}")

    # N_DR: unique cases per (drug, PT)
    n_dr = cooc.groupby(["canon", "pt_norm"])["primaryid"].nunique().reset_index()
    n_dr.columns = ["drug", "pt", "N_DR"]

    # Filter early
    n_dr = n_dr[n_dr["N_DR"] >= MIN_N_DR].copy()
    print(f"  Pairs with N_DR >= {MIN_N_DR}: {len(n_dr):,}")

    # Attach N_D and N_R
    n_dr["N_D"] = n_dr["drug"].map(n_d_series)
    n_dr["N_R"] = n_dr["pt"].map(n_r_series)
    n_dr["N_total"] = n_total

    # Compute PRR
    # a = N_DR, b = N_D - N_DR, c = N_R - N_DR, d = N_total - N_D - N_R + N_DR
    a = n_dr["N_DR"].to_numpy(dtype=float)
    b = (n_dr["N_D"] - n_dr["N_DR"]).to_numpy(dtype=float)
    c = (n_dr["N_R"] - n_dr["N_DR"]).to_numpy(dtype=float)
    d = (n_total - n_dr["N_D"] - n_dr["N_R"] + n_dr["N_DR"]).to_numpy(dtype=float)

    # Guard against division by zero
    c = np.where(c <= 0, 0.5, c)
    b = np.where(b <= 0, 0.5, b)

    n_exposed   = a + b  # N_D
    n_unexposed = c + d  # N_total - N_D

    prr = (a / n_exposed) / (c / n_unexposed)

    # ROR for cross-validation
    ror = (a * d) / (b * c)

    # Chi-squared (Yates corrected)
    n_arr = a + b + c + d
    chi2 = n_arr * (np.abs(a * d - b * c) - 0.5 * n_arr) ** 2 / (
        (a + b) * (c + d) * (a + c) * (b + d) + 1e-10
    )

    n_dr["PRR"]  = np.round(prr, 3)
    n_dr["ROR"]  = np.round(ror, 3)
    n_dr["chi2"] = np.round(chi2, 2)

    # Filter
    n_dr = n_dr[n_dr["PRR"] >= MIN_PRR].copy()

    # Signal level
    def _signal(row):
        if row["PRR"] >= 4 and row["N_DR"] >= 5 and row["chi2"] >= 4:
            return "HIGH"
        elif row["PRR"] >= 2 and row["N_DR"] >= 3 and row["chi2"] >= 4:
            return "MEDIUM"
        elif row["PRR"] >= 1.5 and row["N_DR"] >= 3:
            return "LOW"
        return "NONE"

    print("  Assigning signal levels...")
    n_dr["signal"] = n_dr.apply(_signal, axis=1)
    n_dr = n_dr[n_dr["signal"] != "NONE"].copy()

    n_dr = n_dr.sort_values(["PRR", "N_DR"], ascending=[False, False]).reset_index(drop=True)
    print(f"  Signals: {len(n_dr):,}  (HIGH={n_dr[n_dr['signal']=='HIGH'].shape[0]:,}, "
          f"MEDIUM={n_dr[n_dr['signal']=='MEDIUM'].shape[0]:,}, "
          f"LOW={n_dr[n_dr['signal']=='LOW'].shape[0]:,})")

    path = os.path.join(CACHE_DIR, "prr_table.parquet")
    n_dr.to_parquet(path, index=False)
    print(f"  Saved -> {path}")
    return n_dr


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    demo, drug, reac, outc, n_total = _load_and_dedup()
    build_drug_summary(drug, outc, n_total)
    build_reac_summary(reac, outc)
    build_quarterly_trends(drug, reac)
    build_prr_table(drug, reac, n_total, top_n=TOP_DRUGS)
    print("\nPrecomputation complete. Cache files saved to claude_test/cache/")

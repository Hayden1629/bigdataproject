"""
generate_fixtures.py

Builds synthetic FAERS-like parquet fixtures and pre-computed cache files
used by the test suite.  Run once before running tests (or let conftest.py
call it automatically).

Usage:
    python dashboard/tests/generate_fixtures.py

Output:
    dashboard/tests/fixtures/          — 7 FAERS source tables
    dashboard/tests/fixtures/cache/    — 5 pre-computed cache tables
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

import numpy as np
import pandas as pd

FIXTURE_DIR = Path(__file__).parent / "fixtures"
CACHE_DIR   = FIXTURE_DIR / "cache"

# ── Deterministic test corpus ─────────────────────────────────────────────────
RNG = np.random.default_rng(42)

DRUGS = ["ASPIRIN", "WARFARIN", "METFORMIN", "LISINOPRIL", "ATORVASTATIN",
         "DUPILUMAB", "OZEMPIC"]
REACTIONS = [
    "Nausea", "Headache", "Dizziness", "Fatigue", "Rash",
    "Bleeding", "Myocardial Infarction", "Nausea And Vomiting",
    "Thrombosis", "Liver Injury",
]
QUARTERS = ["2023Q3", "2023Q4", "2024Q1", "2024Q2"]
N_CASES = 600   # small enough to be fast, large enough to produce real PRR signals


def _make_demo(n: int) -> pd.DataFrame:
    primaryids = list(range(1, n + 1))
    # Introduce 20 duplicate caseid pairs to test dedup logic:
    #   rows  0-19: primaryid 1-20,  caseid 1-20, caseversion=2 (kept)
    #   rows 20-39: primaryid 21-40, caseid 1-20, caseversion=1 (dropped)
    caseids = list(range(1, n + 1))
    for i in range(20):
        caseids[20 + i] = i + 1                # rows 20-39 share caseids 1-20
    caseversions = [1] * n
    for i in range(20):
        caseversions[i] = 2                    # higher version — should win

    return pd.DataFrame({
        "primaryid":   primaryids,
        "caseid":      caseids,
        "caseversion": caseversions,
        "quarter":     RNG.choice(QUARTERS, n).tolist(),
        "age":         RNG.integers(18, 85, n).tolist(),
        "sex":         RNG.choice(["M", "F", "UNK"], n, p=[.45, .45, .10]).tolist(),
        "occr_country": RNG.choice(["US", "CA", "GB", "DE", "FR"], n,
                                    p=[.60, .10, .10, .10, .10]).tolist(),
        "reporter_type": RNG.choice(["HP", "CS", "OT"], n, p=[.50, .35, .15]).tolist(),
    })


def _make_drug(demo: pd.DataFrame) -> pd.DataFrame:
    """Each case gets 1–3 drugs; ASPIRIN and WARFARIN are over-represented
    to ensure they generate HIGH PRR signals for specific reactions."""
    rows: list[dict] = []
    for pid in demo["primaryid"]:
        n_drugs = RNG.integers(1, 4)
        chosen = RNG.choice(DRUGS, n_drugs, replace=False).tolist()
        # Bias first 200 cases toward ASPIRIN + Bleeding and WARFARIN + Bleeding
        if pid <= 120:
            if "ASPIRIN" not in chosen:
                chosen[0] = "ASPIRIN"
        elif pid <= 200:
            if "WARFARIN" not in chosen:
                chosen[0] = "WARFARIN"
        for seq, drug in enumerate(chosen, start=1):
            rows.append({
                "primaryid":  pid,
                "drug_seq":   seq,
                "drugname":   drug,
                "prod_ai":    drug,
                "role_cod":   RNG.choice(["PS", "SS", "C"], p=[.60, .25, .15]),
            })
    return pd.DataFrame(rows)


def _make_reac(demo: pd.DataFrame, drug: pd.DataFrame) -> pd.DataFrame:
    """Bias ASPIRIN cases toward Bleeding and Myocardial Infarction for strong PRR."""
    rows: list[dict] = []
    aspirin_pids = set(drug[drug["drugname"] == "ASPIRIN"]["primaryid"].unique())
    warfarin_pids = set(drug[drug["drugname"] == "WARFARIN"]["primaryid"].unique())

    for pid in demo["primaryid"]:
        n_reac = RNG.integers(1, 4)
        if pid in aspirin_pids and pid <= 120:
            # Strongly associate ASPIRIN with Bleeding
            chosen = ["Bleeding"] + RNG.choice(REACTIONS[:-4], max(0, n_reac - 1),
                                                replace=False).tolist()
        elif pid in warfarin_pids and pid <= 200:
            chosen = ["Bleeding", "Thrombosis"] + RNG.choice(
                REACTIONS[:5], max(0, n_reac - 2), replace=False).tolist()
        else:
            chosen = RNG.choice(REACTIONS, n_reac, replace=False).tolist()
        for pt in dict.fromkeys(chosen):          # deduplicate while preserving order
            rows.append({"primaryid": pid, "pt": pt})
    return pd.DataFrame(rows)


def _make_outc(demo: pd.DataFrame) -> pd.DataFrame:
    codes = ["DE", "HO", "LT", "DS", "CA", "OT"]
    pids  = RNG.choice(demo["primaryid"], int(len(demo) * 0.60), replace=False)
    return pd.DataFrame({
        "primaryid": pids,
        "outc_cod":  RNG.choice(codes, len(pids), p=[.08, .35, .15, .10, .07, .25]),
    })


def _make_indi(demo: pd.DataFrame) -> pd.DataFrame:
    indications = ["Pain", "Hypertension", "Diabetes", "Atrial Fibrillation",
                   "Hyperlipidemia", "Infection"]
    pids = RNG.choice(demo["primaryid"], int(len(demo) * 0.70), replace=False)
    return pd.DataFrame({
        "primaryid":    pids,
        "indi_drug_seq": 1,   # matches drug_seq=1 (primary drug for each case)
        "indi_pt":      RNG.choice(indications, len(pids)),
    })


def _make_ther(demo: pd.DataFrame) -> pd.DataFrame:
    pids = RNG.choice(demo["primaryid"], int(len(demo) * 0.50), replace=False)
    return pd.DataFrame({
        "primaryid": pids,
        "start_dt":  ["20230101"] * len(pids),
        "end_dt":    ["20231231"] * len(pids),
    })


def _make_rpsr(demo: pd.DataFrame) -> pd.DataFrame:
    pids = RNG.choice(demo["primaryid"], int(len(demo) * 0.40), replace=False)
    return pd.DataFrame({
        "primaryid": pids,
        "rpsr_cod":  RNG.choice(["HP", "CS", "OT"], len(pids)),
    })


# ── PRR computation (mirrors precompute.py logic) ─────────────────────────────

def _compute_prr(drug: pd.DataFrame, reac: pd.DataFrame, demo: pd.DataFrame) -> pd.DataFrame:
    """Compute PRR/ROR/chi² for all drug-reaction pairs with N_DR >= 3."""
    drug_norm = drug.copy()
    drug_norm["canon"] = drug_norm["prod_ai"].str.upper().str.strip()
    reac_norm = reac.copy()
    reac_norm["pt_norm"] = reac_norm["pt"].str.strip().str.title()

    # Deduplicate demo (keep highest caseversion per caseid)
    demo_dedup = demo.sort_values("caseversion").drop_duplicates("caseid", keep="last")
    valid_pids  = set(demo_dedup["primaryid"].unique())
    drug_norm   = drug_norm[drug_norm["primaryid"].isin(valid_pids)]
    reac_norm   = reac_norm[reac_norm["primaryid"].isin(valid_pids)]

    n_total = len(valid_pids)

    # Per-drug and per-reaction case sets
    drug_cases = (
        drug_norm.groupby("canon")["primaryid"]
        .apply(set).reset_index()
        .rename(columns={"primaryid": "drug_pids", "canon": "drug"})
    )
    reac_cases = (
        reac_norm.groupby("pt_norm")["primaryid"]
        .apply(set).reset_index()
        .rename(columns={"primaryid": "reac_pids", "pt_norm": "pt"})
    )

    rows: list[dict] = []
    for _, dr in drug_cases.iterrows():
        for _, rr in reac_cases.iterrows():
            a  = len(dr.drug_pids & rr.reac_pids)  # N_DR
            if a < 3:
                continue
            n_d = len(dr.drug_pids)   # N_D
            n_r = len(rr.reac_pids)   # N_R
            b   = n_d - a
            c   = n_r - a
            d   = n_total - n_d - n_r + a

            if n_d == 0 or (n_total - n_d) == 0 or c <= 0:
                continue

            prr  = (a / n_d) / (c / (n_total - n_d))
            ror  = (a * d) / (b * c) if (b * c) > 0 else float("nan")
            # Yates-corrected chi-squared
            exp  = (a + b) * (a + c) / n_total
            chi2 = ((abs(a - exp) - 0.5) ** 2) / exp if exp > 0 else 0.0

            if prr >= 4 and a >= 5 and chi2 >= 4:
                signal = "HIGH"
            elif prr >= 2 and a >= 3 and chi2 >= 4:
                signal = "MEDIUM"
            elif prr >= 1.5 and a >= 3:
                signal = "LOW"
            else:
                continue

            rows.append({
                "drug":    dr.drug,
                "pt":      rr.pt,
                "N_DR":    int(a),
                "N_D":     int(n_d),
                "N_R":     int(n_r),
                "N_total": int(n_total),
                "PRR":     round(prr, 4),
                "ROR":     round(ror, 4),
                "chi2":    round(chi2, 4),
                "signal":  signal,
            })

    return pd.DataFrame(rows)


def _compute_drug_summary(drug: pd.DataFrame, outc: pd.DataFrame,
                           demo: pd.DataFrame) -> pd.DataFrame:
    drug_norm = drug.copy()
    drug_norm["canon"] = drug_norm["prod_ai"].str.upper().str.strip()
    demo_dedup = demo.sort_values("caseversion").drop_duplicates("caseid", keep="last")
    valid = set(demo_dedup["primaryid"].unique())
    drug_filt = drug_norm[drug_norm["primaryid"].isin(valid)]
    death_pids = set(outc[outc["outc_cod"] == "DE"]["primaryid"].unique())

    rows = []
    for canon, grp in drug_filt.groupby("canon"):
        pids = set(grp["primaryid"].unique())
        n_deaths = len(pids & death_pids)
        rows.append({
            "drug":      canon,
            "n_cases":   len(pids),
            "n_deaths":  n_deaths,
            "death_pct": round(n_deaths / len(pids) * 100, 2) if pids else 0.0,
        })
    return pd.DataFrame(rows).sort_values("n_cases", ascending=False).reset_index(drop=True)


def _compute_reac_summary(reac: pd.DataFrame, outc: pd.DataFrame,
                           demo: pd.DataFrame) -> pd.DataFrame:
    reac_norm = reac.copy()
    reac_norm["pt_norm"] = reac_norm["pt"].str.strip().str.title()
    demo_dedup = demo.sort_values("caseversion").drop_duplicates("caseid", keep="last")
    valid = set(demo_dedup["primaryid"].unique())
    reac_filt = reac_norm[reac_norm["primaryid"].isin(valid)]
    death_pids = set(outc[outc["outc_cod"] == "DE"]["primaryid"].unique())

    rows = []
    for pt, grp in reac_filt.groupby("pt_norm"):
        pids = set(grp["primaryid"].unique())
        n_deaths = len(pids & death_pids)
        rows.append({
            "pt":        pt,
            "n_cases":   len(pids),
            "n_deaths":  n_deaths,
            "death_pct": round(n_deaths / len(pids) * 100, 2) if pids else 0.0,
        })
    return pd.DataFrame(rows).sort_values("n_cases", ascending=False).reset_index(drop=True)


def _compute_quarterly_drug(drug: pd.DataFrame, demo: pd.DataFrame) -> pd.DataFrame:
    drug_norm = drug.copy()
    drug_norm["canon"] = drug_norm["prod_ai"].str.upper().str.strip()
    merged = drug_norm.merge(demo[["primaryid", "quarter"]], on="primaryid")
    return (
        merged.groupby(["canon", "quarter"])["primaryid"]
        .nunique().reset_index()
        .rename(columns={"canon": "drug", "primaryid": "n_cases"})
    )


def _compute_quarterly_reac(reac: pd.DataFrame, demo: pd.DataFrame) -> pd.DataFrame:
    reac_norm = reac.copy()
    reac_norm["pt_norm"] = reac_norm["pt"].str.strip().str.title()
    merged = reac_norm.merge(demo[["primaryid", "quarter"]], on="primaryid")
    return (
        merged.groupby(["pt_norm", "quarter"])["primaryid"]
        .nunique().reset_index()
        .rename(columns={"pt_norm": "pt", "primaryid": "n_cases"})
    )


# ── Main entry point ──────────────────────────────────────────────────────────

def generate(fixture_dir: Path = FIXTURE_DIR, cache_dir: Path = CACHE_DIR,
             force: bool = False) -> None:
    """Generate all fixture files.  Skips if already present unless force=True."""
    fixture_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    source_marker = fixture_dir / "demo.parquet"
    cache_marker  = cache_dir  / "prr_table.parquet"

    if not force and source_marker.exists() and cache_marker.exists():
        return   # already generated

    print(f"Generating test fixtures in {fixture_dir} …")

    demo  = _make_demo(N_CASES)
    drug  = _make_drug(demo)
    reac  = _make_reac(demo, drug)
    outc  = _make_outc(demo)
    indi  = _make_indi(demo)
    ther  = _make_ther(demo)
    rpsr  = _make_rpsr(demo)

    demo.to_parquet(fixture_dir / "demo.parquet",  index=False)
    drug.to_parquet(fixture_dir / "drug.parquet",  index=False)
    reac.to_parquet(fixture_dir / "reac.parquet",  index=False)
    outc.to_parquet(fixture_dir / "outc.parquet",  index=False)
    indi.to_parquet(fixture_dir / "indi.parquet",  index=False)
    ther.to_parquet(fixture_dir / "ther.parquet",  index=False)
    rpsr.to_parquet(fixture_dir / "rpsr.parquet",  index=False)

    print("  Source tables written.")

    prr = _compute_prr(drug, reac, demo)
    prr.to_parquet(cache_dir / "prr_table.parquet", index=False)

    _compute_drug_summary(drug, outc, demo).to_parquet(
        cache_dir / "drug_summary.parquet", index=False)
    _compute_reac_summary(reac, outc, demo).to_parquet(
        cache_dir / "reac_summary.parquet", index=False)
    _compute_quarterly_drug(drug, demo).to_parquet(
        cache_dir / "quarterly_drug.parquet", index=False)
    _compute_quarterly_reac(reac, demo).to_parquet(
        cache_dir / "quarterly_reac.parquet", index=False)

    print(f"  Cache files written ({len(prr)} PRR signals).")
    print("Done.")


if __name__ == "__main__":
    force = "--force" in sys.argv
    generate(force=force)

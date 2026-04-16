from __future__ import annotations

import pandas as pd

import queries as qr


def test_drug_query_bundle_matches_manual_kpis_and_recent_records(tables: dict[str, pd.DataFrame]) -> None:
    names_key = qr._names_key(["ASPIRIN"])
    role = "PS"
    quarters_key = "ALL"

    bundle = qr.drug_query_bundle(
        names_key,
        role,
        quarters_key,
        top_n_reactions=5,
        top_n_countries=5,
        top_n_indications=5,
        top_n_concomitants=5,
        recent_limit=10,
    )

    case_ids = qr._drug_case_ids(names_key, role, quarters_key)
    outc_sub = tables["outc"][tables["outc"]["primaryid"].isin(case_ids)]
    outc_vc = outc_sub["outc_cod"].value_counts()
    expected_kpi = {
        "n_cases": len(case_ids),
        "n_deaths": int(outc_vc.get("DE", 0)),
        "n_hosp": int(outc_vc.get("HO", 0)),
        "n_lt": int(outc_vc.get("LT", 0)),
        "n_serious": int(outc_sub["primaryid"].nunique()),
        "death_pct": round(int(outc_vc.get("DE", 0)) / len(case_ids) * 100, 2) if case_ids else 0.0,
    }
    assert bundle["kpi"] == expected_kpi

    drug_sub = tables["drug"]
    name_set = set(names_key.split("|"))
    expected_recent = drug_sub[drug_sub["primaryid"].isin(case_ids) & drug_sub["canon"].isin(name_set)]
    expected_recent = expected_recent[expected_recent["role_cod"] == role].copy()
    want_cols = ["primaryid", "role_cod", "drugname", "prod_ai", "route", "dose_vbm", "dose_amt", "dose_unit", "dose_form", "dose_freq"]
    expected_recent = expected_recent[[c for c in want_cols if c in expected_recent.columns]]
    expected_recent = expected_recent.sort_values("primaryid", ascending=False).head(10).reset_index(drop=True)
    pd.testing.assert_frame_equal(bundle["recent_records"].reset_index(drop=True), expected_recent)


def test_drug_query_bundle_matches_manual_reactions_and_trend(tables: dict[str, pd.DataFrame]) -> None:
    names_key = qr._names_key(["WARFARIN"])
    role = "all"
    quarters_key = "ALL"

    bundle = qr.drug_query_bundle(
        names_key,
        role,
        quarters_key,
        top_n_reactions=3,
        top_n_countries=5,
        top_n_indications=5,
        top_n_concomitants=5,
        recent_limit=10,
    )

    case_ids = qr._drug_case_ids(names_key, role, quarters_key)

    reac_sub = tables["reac"][tables["reac"]["primaryid"].isin(case_ids)]
    expected_reac = reac_sub["pt_norm"].value_counts().head(3).reset_index()
    expected_reac.columns = ["pt", "count"]
    expected_reac["pct"] = (expected_reac["count"] / len(case_ids) * 100).round(1)
    pd.testing.assert_frame_equal(bundle["top_reactions"].reset_index(drop=True), expected_reac.reset_index(drop=True))

    demo_sub = tables["demo"][tables["demo"]["primaryid"].isin(case_ids)]
    expected_trend = demo_sub.groupby("quarter")["primaryid"].nunique().reset_index()
    expected_trend.columns = ["quarter", "case_count"]
    expected_trend = expected_trend.sort_values("quarter").reset_index(drop=True)
    pd.testing.assert_frame_equal(bundle["trend"].reset_index(drop=True), expected_trend)

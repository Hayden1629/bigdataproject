from __future__ import annotations

import math
from typing import Any

import pandas as pd
import requests
from rapidfuzz import fuzz, process


def _norm(text: Any) -> str:
    if text is None:
        return ""
    if isinstance(text, float) and math.isnan(text):
        return ""
    return str(text).strip().lower()


def rxnorm_lookup(name: str, timeout: int = 8) -> dict[str, Any]:
    q = (name or "").strip()
    if not q:
        return {"rxcui": None, "canonical": None, "related": []}
    try:
        url = "https://rxnav.nlm.nih.gov/REST/drugs.json"
        resp = requests.get(url, params={"name": q}, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
        groups = payload.get("drugGroup", {}).get("conceptGroup", [])
        for group in groups:
            concepts = group.get("conceptProperties", []) or []
            if concepts:
                c = concepts[0]
                rxcui = c.get("rxcui")
                canonical = c.get("name")
                related = [x.get("name") for x in concepts[:12] if x.get("name")]
                return {"rxcui": rxcui, "canonical": canonical, "related": related}
    except Exception:
        pass
    return {"rxcui": None, "canonical": None, "related": []}


def llm_normalize(_query: str) -> str | None:
    return None


def match_drug_names(
    query: str, lookup_df: pd.DataFrame, fuzzy_threshold: int = 86
) -> dict[str, Any]:
    q = _norm(query)
    if not q or lookup_df.empty:
        return {
            "matched_faers_names": [],
            "canonical": None,
            "rxcui": None,
            "related": [],
        }

    local = lookup_df.copy()
    for col in ["drugname", "drugname_norm", "prod_ai", "prod_ai_norm"]:
        if col not in local.columns:
            local[col] = ""
    local["drugname_norm"] = local["drugname_norm"].map(_norm)
    local["prod_ai_norm"] = local["prod_ai_norm"].map(_norm)

    rx = rxnorm_lookup(query)
    rx_tokens = {
        _norm(t)
        for t in [query, rx.get("canonical", "")] + list(rx.get("related", []))
        if _norm(t)
    }

    direct = local[
        local["drugname_norm"].str.contains(q, na=False)
        | local["prod_ai_norm"].str.contains(q, na=False)
    ]

    bridge = pd.DataFrame()
    if rx_tokens:
        mask = False
        for tok in rx_tokens:
            tok_mask = local["drugname_norm"].str.contains(tok, na=False) | local[
                "prod_ai_norm"
            ].str.contains(tok, na=False)
            mask = tok_mask if isinstance(mask, bool) else (mask | tok_mask)
        if not isinstance(mask, bool):
            bridge = local[mask]

    combined = pd.concat([direct, bridge], ignore_index=True).drop_duplicates()

    if combined.empty:
        choices = sorted(
            set(local["drugname_norm"].tolist() + local["prod_ai_norm"].tolist())
        )
        fuzzy = process.extract(q, choices, scorer=fuzz.token_set_ratio, limit=12)
        keep = [name for name, score, _ in fuzzy if score >= fuzzy_threshold]
        if keep:
            combined = local[
                local["drugname_norm"].isin(keep) | local["prod_ai_norm"].isin(keep)
            ]

    if combined.empty:
        fallback = llm_normalize(query)
        if fallback:
            fq = _norm(fallback)
            combined = local[
                local["drugname_norm"].str.contains(fq, na=False)
                | local["prod_ai_norm"].str.contains(fq, na=False)
            ]

    if combined.empty:
        return {
            "matched_faers_names": [],
            "canonical": rx.get("canonical") or query.strip(),
            "rxcui": rx.get("rxcui"),
            "related": rx.get("related", []),
        }

    names = sorted(set(combined["drugname"].dropna().astype(str).tolist()))
    return {
        "matched_faers_names": names,
        "canonical": rx.get("canonical") or query.strip(),
        "rxcui": rx.get("rxcui"),
        "related": rx.get("related", []),
    }

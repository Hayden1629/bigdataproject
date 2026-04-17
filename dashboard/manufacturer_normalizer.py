from __future__ import annotations

from typing import Any

import pandas as pd
from rapidfuzz import fuzz, process

from dashboard.data_loader import canonicalize_mfr


def match_manufacturer_names(
    query: str,
    lookup_df: pd.DataFrame,
    fuzzy_threshold: int = 85,
) -> dict[str, Any]:
    q = canonicalize_mfr(query)
    if not q or lookup_df.empty:
        return {"canonical": [], "raw_strings": []}

    cols = {c.lower(): c for c in lookup_df.columns}
    raw_col = cols.get("mfr_sndr") or cols.get("raw_mfr") or "mfr_sndr"
    canon_col = cols.get("canonical_mfr") or "canonical_mfr"

    local = lookup_df.copy()
    if canon_col not in local.columns:
        local[canon_col] = local[raw_col].map(canonicalize_mfr)

    exact = local[local[canon_col] == q]
    if not exact.empty:
        canons = sorted(exact[canon_col].dropna().astype(str).unique().tolist())
        raws = sorted(exact[raw_col].dropna().astype(str).unique().tolist())
        return {"canonical": canons, "raw_strings": raws}

    sub = local[local[canon_col].astype(str).str.contains(q, na=False)]
    if sub.empty:
        sub = local[local[canon_col].map(lambda v: q in str(v))]
    if not sub.empty:
        canons = sorted(sub[canon_col].dropna().astype(str).unique().tolist())
        raws = sorted(sub[raw_col].dropna().astype(str).unique().tolist())
        return {"canonical": canons[:10], "raw_strings": raws[:200]}

    choices = sorted(local[canon_col].dropna().astype(str).unique().tolist())
    if not choices:
        return {"canonical": [], "raw_strings": []}
    fuzzy = process.extract(q, choices, scorer=fuzz.token_set_ratio, limit=10)
    matched = [name for name, score, _ in fuzzy if score >= fuzzy_threshold]
    if not matched:
        return {"canonical": [], "raw_strings": []}

    filt = local[local[canon_col].isin(matched)]
    raws = sorted(filt[raw_col].dropna().astype(str).unique().tolist())
    return {"canonical": matched, "raw_strings": raws[:200]}

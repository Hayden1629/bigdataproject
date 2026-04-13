"""
signal_detection.py

Query interface for the pre-computed PRR signal table.
Provides drug-specific signal lookups and global signal rankings.
"""

from __future__ import annotations

import pandas as pd
from data_loader import load_prr_table
from logger import get_logger

log = get_logger(__name__)

SIGNAL_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def signals_for_drug(
    matched_names: list[str],
    min_signal: str = "LOW",
    top_n: int = 30,
    min_n_dr: int = 5,
) -> pd.DataFrame:
    """
    Return PRR signals for a given drug (matched name set).

    Sorted by chi-squared descending (balances frequency and magnitude)
    rather than raw PRR, which can be inflated by very small counts.
    """
    prr = load_prr_table()
    if prr is None or prr.empty:
        log.warning("signals_for_drug: PRR table unavailable")
        return pd.DataFrame()

    name_set = {n.upper().strip() for n in matched_names}
    mask = prr["drug"].isin(name_set) & (prr["N_DR"] >= min_n_dr)
    sub = prr[mask].copy()
    if sub.empty:
        log.info("signals_for_drug: no signals found for %s (min_signal=%s, min_n_dr=%d)",
                 matched_names[:3], min_signal, min_n_dr)
        return sub

    allowed = {k for k, v in SIGNAL_ORDER.items() if v <= SIGNAL_ORDER[min_signal]}
    sub = sub[sub["signal"].isin(allowed)]
    sub = sub.sort_values(["chi2", "PRR"], ascending=[False, False])
    sub = sub.drop_duplicates(subset=["pt"], keep="first")
    sub = sub.head(top_n)
    counts = sub["signal"].value_counts().to_dict()
    log.info("signals_for_drug: %d signals for %s  %s", len(sub), matched_names[:2], counts)
    return sub[["pt", "N_DR", "N_D", "N_R", "N_total", "PRR", "ROR", "chi2", "signal"]].reset_index(drop=True)


def global_top_signals(
    min_signal: str = "MEDIUM",
    min_n_dr: int = 5,
    top_n: int = 200,
) -> pd.DataFrame:
    """Return the globally highest PRR signals across all drugs."""
    prr = load_prr_table()
    if prr is None or prr.empty:
        log.warning("global_top_signals: PRR table unavailable")
        return pd.DataFrame()

    allowed = {k for k, v in SIGNAL_ORDER.items() if v <= SIGNAL_ORDER[min_signal]}
    mask = prr["signal"].isin(allowed) & (prr["N_DR"] >= min_n_dr)
    sub = prr[mask].copy()
    sub = sub.sort_values(["PRR", "N_DR"], ascending=[False, False]).head(top_n)
    log.debug("global_top_signals: returning %d rows (min_signal=%s)", len(sub), min_signal)
    return sub.reset_index(drop=True)


def signals_for_reaction(
    pt_list: list[str],
    min_signal: str = "LOW",
    top_n: int = 30,
    min_n_dr: int = 5,
) -> pd.DataFrame:
    """Return drugs that have elevated PRR for the given reaction(s)."""
    prr = load_prr_table()
    if prr is None or prr.empty:
        log.warning("signals_for_reaction: PRR table unavailable")
        return pd.DataFrame()

    pt_set = set(pt_list)
    mask = prr["pt"].isin(pt_set) & (prr["N_DR"] >= min_n_dr)
    sub = prr[mask].copy()
    if sub.empty:
        log.info("signals_for_reaction: no signals found for PTs=%s", pt_list[:3])
        return sub

    allowed = {k for k, v in SIGNAL_ORDER.items() if v <= SIGNAL_ORDER[min_signal]}
    sub = sub[sub["signal"].isin(allowed)]
    sub = sub.sort_values(["chi2", "PRR"], ascending=[False, False]).head(top_n)
    log.info("signals_for_reaction: %d signals for PTs=%s", len(sub), pt_list[:3])
    return sub[["drug", "N_DR", "N_D", "N_R", "N_total", "PRR", "ROR", "chi2", "signal"]].reset_index(drop=True)


def signal_counts() -> dict[str, int]:
    """Return {HIGH: n, MEDIUM: n, LOW: n} across the full PRR table."""
    prr = load_prr_table()
    if prr is None or prr.empty:
        return {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    vc = prr["signal"].value_counts()
    counts = {
        "HIGH":   int(vc.get("HIGH",   0)),
        "MEDIUM": int(vc.get("MEDIUM", 0)),
        "LOW":    int(vc.get("LOW",    0)),
    }
    log.debug("signal_counts: %s", counts)
    return counts

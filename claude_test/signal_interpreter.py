"""
signal_interpreter.py

Uses Claude Haiku to generate a plain-English pharmacovigilance signal summary
for a given drug and its top PRR signals.

This satisfies the LLM-powered summarization requirement in the MSBA 6331
Big Data project (Team 11).  Uses claude-haiku-4-5 for low latency and cost.
"""

from __future__ import annotations

import os
import streamlit as st
import pandas as pd


@st.cache_data(ttl=3600, show_spinner=False)
def interpret_signals(
    drug_name: str,
    signals_csv: str,      # CSV string of top signals (pt, PRR, chi2, signal, N_DR)
    n_cases: int,
    n_deaths: int,
) -> str:
    """
    Ask Claude Haiku to summarise the pharmacovigilance signal profile for a drug.

    Parameters
    ----------
    drug_name   : canonical name of the drug
    signals_csv : top PRR signals as a compact CSV string (already rendered)
    n_cases     : total FAERS case count for this drug
    n_deaths    : deaths reported for this drug

    Returns
    -------
    A 3-5 sentence plain-English summary suitable for a clinical analyst.
    Returns an empty string if the API key is missing or the call fails.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            f"You are a pharmacovigilance analyst summarising FDA FAERS adverse event signals.\n\n"
            f"Drug: {drug_name}\n"
            f"Total FAERS cases: {n_cases:,}  |  Deaths: {n_deaths:,}\n\n"
            f"Top disproportionality signals (PRR analysis):\n"
            f"{signals_csv}\n\n"
            f"Write a concise 3-5 sentence clinical interpretation for a drug safety analyst. "
            f"Cover: (1) the most prominent signal clusters, (2) their clinical plausibility, "
            f"(3) any unexpected or noteworthy findings. "
            f"Be specific and factual. Do not use emojis, markdown headers, or bullet points. "
            f"Remind the reader that FAERS is a spontaneous reporting system and does not "
            f"establish causality."
        )
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception:
        return ""

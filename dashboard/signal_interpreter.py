"""
signal_interpreter.py

Generates a plain-English pharmacovigilance signal summary for a given drug
and its top PRR signals.

Provider priority (uses first available key):
  1. Anthropic Claude Haiku  — set ANTHROPIC_API_KEY
  2. Groq Llama 3            — set GROQ_API_KEY  (free tier: 14,400 req/day)

If neither key is present the function returns an empty string and the UI
shows a soft "unavailable" message.
"""

from __future__ import annotations

import os
import streamlit as st
import pandas as pd

_PROMPT_TEMPLATE = (
    "You are a pharmacovigilance analyst summarising FDA FAERS adverse event signals.\n\n"
    "Drug: {drug_name}\n"
    "Total FAERS cases: {n_cases:,}  |  Deaths: {n_deaths:,}\n\n"
    "Top disproportionality signals (PRR analysis):\n"
    "{signals_csv}\n\n"
    "Write a concise 3-5 sentence clinical interpretation for a drug safety analyst. "
    "Cover: (1) the most prominent signal clusters, (2) their clinical plausibility, "
    "(3) any unexpected or noteworthy findings. "
    "Be specific and factual. Do not use emojis, markdown headers, or bullet points. "
    "Remind the reader that FAERS is a spontaneous reporting system and does not "
    "establish causality."
)


@st.cache_data(ttl=3600, show_spinner=False)
def interpret_signals(
    drug_name: str,
    signals_csv: str,
    n_cases: int,
    n_deaths: int,
) -> str:
    """
    Summarise a drug's pharmacovigilance signal profile using an LLM.

    Returns a 3-5 sentence plain-English summary, or an empty string if no
    API key is configured.
    """
    prompt = _PROMPT_TEMPLATE.format(
        drug_name=drug_name,
        n_cases=n_cases,
        n_deaths=n_deaths,
        signals_csv=signals_csv,
    )

    # ── 1. Try Anthropic ──────────────────────────────────────────────────────
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text.strip()
        except Exception:
            pass

    # ── 2. Try Groq (free tier — llama-3.1-8b-instant) ───────────────────────
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)
            resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            pass

    return ""

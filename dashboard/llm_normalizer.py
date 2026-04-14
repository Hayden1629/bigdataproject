"""
llm_normalizer.py

LLM-based drug name normalization layer.


PURPOSE
-------
This module serves as a fallback in the drug normalization pipeline.
It is invoked only when both RxNorm API lookup and RapidFuzz fuzzy matching
fail to find a match in the FAERS database.

Cases handled that RxNorm and fuzzy matching cannot resolve:

    Input               Output
    -----------------   ----------------
    MTX                 Methotrexate        (abbreviation)
    blood thinner       Warfarin            (lay term)
    acetaminophn        Acetaminophen       (misspelling)
    TYLENOL             Acetaminophen       (brand to generic)
    heprin              Heparin             (misspelling)


LLM PROVIDER PRIORITY
----------------------
  1. Databricks built-in LLM  -- free, no external key required,
                                  token retrieved automatically inside Databricks
  2. Anthropic Claude Haiku   -- set ANTHROPIC_API_KEY environment variable
  3. Groq Llama 3             -- set GROQ_API_KEY environment variable
                                  free tier: 14,400 requests per day
  4. Original name returned   -- if all providers are unavailable

CACHING
-------
Results are cached at two levels to avoid redundant API calls:
  - In-session memory : @st.cache_data (Streamlit, 24-hour TTL)
  - On-disk           : @disk_cache (survives server restarts, 24-hour TTL)

The same drug name string will never trigger more than one LLM API call.
"""

from __future__ import annotations

import os
import time

try:
    import streamlit as st
except ImportError:
    from types import SimpleNamespace

    def _noop(*args, **kwargs):
        return args[0] if args and callable(args[0]) else (lambda f: f)
    st = SimpleNamespace(cache_resource=_noop, cache_data=_noop)

from api_cache import disk_cache
from logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DATABRICKS_HOST = os.environ.get(
    "DATABRICKS_HOST",
    "https://dbc-28c879c7-9abd.cloud.databricks.com",
)

_DATABRICKS_MODEL = "databricks-meta-llama-3-3-70b-instruct"

# Prompt is intentionally concise to elicit a single-word or short response.
# temperature=0 is set at call time for deterministic output.
_PROMPT_TEMPLATE = (
    "You are a clinical pharmacology expert. "
    "Convert the following drug name to its standard INN generic name. "
    "Reply with ONLY the generic name -- no punctuation, no explanation, "
    "no alternatives. "
    "If it is already a generic name, return it cleaned up. "
    "If you cannot identify it, return the original input exactly.\n\n"
    "Drug name: {drug_name}"
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@st.cache_data(ttl=86400, show_spinner=False)
@disk_cache(ttl=86400)
def llm_normalize(drug_name: str) -> str:
    """
    Convert a raw drug name string to its standard INN generic name.

    This function is a pipeline fallback. It should be called only after
    RxNorm API lookup and fuzzy matching have both returned no results.
    Results are cached for 24 hours so repeated calls for the same input
    incur no additional API cost.

    Parameters
    ----------
    drug_name : str
        Raw drug name from FAERS data or user search input.

    Returns
    -------
    str
        Standard generic name if an LLM provider is available and confident,
        otherwise the original drug_name string unchanged.
    """
    t0 = time.perf_counter()
    log.info("llm_normalize: called for %r", drug_name)

    prompt = _PROMPT_TEMPLATE.format(drug_name=drug_name)

    # Provider 1: Databricks built-in LLM
    databricks_token = _get_databricks_token()
    if databricks_token:
        result = _call_databricks(drug_name, prompt, databricks_token, t0)
        if result:
            return result

    # Provider 2: Anthropic Claude Haiku
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        result = _call_anthropic(drug_name, prompt, anthropic_key, t0)
        if result:
            return result

    # Provider 3: Groq Llama 3
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        result = _call_groq(drug_name, prompt, groq_key, t0)
        if result:
            return result

    # All providers unavailable -- return original input unchanged
    log.warning(
        "llm_normalize: no LLM provider available for %r -- returning original"
        "  (%.2fs)",
        drug_name,
        time.perf_counter() - t0,
    )
    return drug_name


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _get_databricks_token() -> str:
    """
    Retrieve a Databricks personal access token.

    Attempts notebook context first (works inside Databricks automatically),
    then falls back to the DATABRICKS_TOKEN environment variable.
    """
    try:
        return (
            dbutils.notebook.entry_point          # noqa: F821
            .getDbutils()
            .notebook()
            .getContext()
            .apiToken()
            .get()
        )
    except Exception:
        pass
    return os.environ.get("DATABRICKS_TOKEN", "")


def _call_databricks(
    drug_name: str, prompt: str, token: str, t0: float
) -> str | None:
    """
    Call the Databricks-hosted foundation model endpoint.
    Returns the normalized name string, or None if the call fails.
    """
    log.info("llm_normalize: trying Databricks for %r", drug_name)
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=token,
            base_url=f"{_DATABRICKS_HOST}/serving-endpoints",
        )
        resp = client.chat.completions.create(
            model=_DATABRICKS_MODEL,
            max_tokens=20,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        result = resp.choices[0].message.content.strip()
        log.info(
            "llm_normalize: Databricks %r -> %r  (%.2fs)",
            drug_name, result, time.perf_counter() - t0,
        )
        return result
    except Exception as exc:
        log.warning(
            "llm_normalize: Databricks failed for %r: %s", drug_name, exc
        )
        return None


def _call_anthropic(
    drug_name: str, prompt: str, api_key: str, t0: float
) -> str | None:
    """
    Call Anthropic Claude Haiku.
    Returns the normalized name string, or None if the call fails.
    """
    log.info("llm_normalize: trying Anthropic for %r", drug_name)
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=20,
            messages=[{"role": "user", "content": prompt}],
        )
        result = resp.content[0].text.strip()
        log.info(
            "llm_normalize: Anthropic %r -> %r  (%.2fs)",
            drug_name, result, time.perf_counter() - t0,
        )
        return result
    except Exception as exc:
        log.warning(
            "llm_normalize: Anthropic failed for %r: %s", drug_name, exc
        )
        return None


def _call_groq(
    drug_name: str, prompt: str, api_key: str, t0: float
) -> str | None:
    """
    Call Groq Llama 3 (free tier).
    Returns the normalized name string, or None if the call fails.
    """
    log.info("llm_normalize: trying Groq for %r", drug_name)
    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            max_tokens=20,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        result = resp.choices[0].message.content.strip()
        log.info(
            "llm_normalize: Groq %r -> %r  (%.2fs)",
            drug_name, result, time.perf_counter() - t0,
        )
        return result
    except Exception as exc:
        log.warning(
            "llm_normalize: Groq failed for %r: %s", drug_name, exc
        )
        return None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def run_tests() -> None:
    """
    Validate LLM normalization against known ground-truth cases.

    Run this in a Databricks notebook to confirm the integration is working:

        from llm_normalizer import run_tests
        run_tests()

    Expected output:
        Input                Output               Expected             Pass
        -------------------------------------------------------------------
        MTX                  Methotrexate         Methotrexate         PASS
        blood thinner        Warfarin             Warfarin             PASS
        acetaminophn         Acetaminophen        Acetaminophen        PASS
        TYLENOL              Acetaminophen        Acetaminophen        PASS
        heprin               Heparin              Heparin              PASS
        APAP                 Acetaminophen        Acetaminophen        PASS
    """
    test_cases = [
        ("MTX",           "Methotrexate"),
        ("blood thinner", "Warfarin"),
        ("acetaminophn",  "Acetaminophen"),
        ("TYLENOL",       "Acetaminophen"),
        ("heprin",        "Heparin"),
        ("APAP",          "Acetaminophen"),
    ]

    separator = "-" * 70
    header = f"{'Input':<20} {'Output':<20} {'Expected':<20} {'Pass'}"
    print(separator)
    print(header)
    print(separator)

    correct = 0
    for drug_name, expected in test_cases:
        result = llm_normalize(drug_name)
        passed = result.lower() == expected.lower()
        if passed:
            correct += 1
        print(
            f"{drug_name:<20} {result:<20} {expected:<20}"
            f" {'PASS' if passed else 'FAIL'}"
        )

    print(separator)
    print(f"Result: {correct}/{len(test_cases)} passed")


if __name__ == "__main__":
    run_tests()

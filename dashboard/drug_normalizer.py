"""
drug_normalizer.py

Maps a user-supplied drug name to a canonical set of names found in FAERS,
using the RxNorm public API (no auth required) + fuzzy fallback.

Flow:
  1. Call RxNorm /drugs endpoint to get the RxCUI for the search term.
  2. Fetch all related concept names (brand names, ingredients, clinical drugs).
  3. Fuzzy-match the resulting names against FAERS drugname/prod_ai columns.
  4. Return the set of FAERS drug name strings that correspond to this drug.
"""

import re
import time
import requests
from api_cache import disk_cache
#add on
from llm_normalizer import llm_normalize

try:
    import streamlit as st
except ImportError:
    from types import SimpleNamespace
    def _noop(*args, **kwargs):
        return args[0] if args and callable(args[0]) else (lambda f: f)
    st = SimpleNamespace(cache_resource=_noop, cache_data=_noop)

from rapidfuzz import process, fuzz
from logger import get_logger

log = get_logger(__name__)

RXNORM_BASE = "https://rxnav.nlm.nih.gov/REST"
_SESSION = requests.Session()
_SESSION.headers.update({"Accept": "application/json"})


# ── RxNorm helpers ────────────────────────────────────────────────────────────

def _rxnorm_get(path: str, params: dict | None = None) -> dict:
    url = f"{RXNORM_BASE}/{path}"
    resp = _SESSION.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=3600, show_spinner=False)
@disk_cache(ttl=86400)
def rxnorm_lookup(drug_name: str) -> dict:
    """
    Return a dict with:
      rxcui       - best RxCUI for the search term (or None)
      canonical   - canonical RxNorm name for the RxCUI
      related     - list of related names (brands, generics, ingredients)
    """
    t0 = time.perf_counter()
    log.info("RxNorm lookup: %r", drug_name)
    result = {"rxcui": None, "canonical": None, "related": []}

    # Preferred term type order: simple names first, complex product strings last
    _TTY_PRIORITY = {"IN": 1, "PIN": 2, "MIN": 3, "BN": 4, "SCDF": 5, "SCD": 6,
                     "SBD": 7, "BPCK": 8, "GPCK": 9}

    # Step 1: find RxCUI
    try:
        data = _rxnorm_get("drugs.json", params={"name": drug_name})
        concept_group = (
            data.get("drugGroup", {})
                .get("conceptGroup", [])
        )
        names_by_tty: dict[str, list[tuple[str, str]]] = {}
        for group in concept_group:
            tty = group.get("tty", "")
            for prop in group.get("conceptProperties", []):
                if prop.get("rxcui"):
                    names_by_tty.setdefault(tty, []).append(
                        (prop["rxcui"], prop.get("name", ""))
                    )
        if not names_by_tty:
            log.warning("RxNorm: no RxCUI found for %r", drug_name)
            return result

        # Build a human-friendly canonical: "Brand (ingredient)" when available,
        # otherwise the best single name we can find.
        in_names = names_by_tty.get("IN", []) or names_by_tty.get("PIN", []) or names_by_tty.get("MIN", [])
        bn_names = names_by_tty.get("BN", [])

        if in_names and bn_names:
            rxcui = in_names[0][0]
            brand = bn_names[0][1].title()
            ingredient = in_names[0][1].lower()
            canonical = f"{brand} ({ingredient})"
        elif in_names:
            rxcui, name = in_names[0]
            canonical = name.title()
        elif bn_names:
            rxcui, name = bn_names[0]
            canonical = name.title()
        else:
            # Fall back to the highest-priority tty available
            best_tty = min(names_by_tty.keys(), key=lambda t: _TTY_PRIORITY.get(t, 99))
            rxcui, name = names_by_tty[best_tty][0]
            # SBD/BPCK product strings often embed the brand in brackets, e.g.
            # "10 Ml Drug-Name Dosage [Brand]" — extract it for a cleaner label.
            bracket = re.search(r'\[([^\[\]]+)\]', name)
            canonical = bracket.group(1).strip().title() if bracket else name.title()

        result["rxcui"] = rxcui
        result["canonical"] = canonical
        log.debug("RxNorm step1: %r → RxCUI=%s tentative_canonical=%r", drug_name, rxcui, canonical)
    except Exception as exc:
        log.warning("RxNorm lookup failed for %r: %s", drug_name, exc)
        return result

    # Step 2: fetch all related concepts via allRelatedInfo (works for every RxCUI type,
    # unlike related.json which requires TTY params that can 400 on some concept types).
    try:
        time.sleep(0.1)  # be polite to the API
        rel = _rxnorm_get(f"rxcui/{rxcui}/allRelatedInfo.json")
        related_names: list[str] = []
        names_by_tty_rel: dict[str, list[str]] = {}
        for group in rel.get("allRelatedGroup", {}).get("conceptGroup", []):
            tty = group.get("tty", "")
            for prop in group.get("conceptProperties", []):
                name = prop.get("name", "")
                if name:
                    related_names.append(name.upper().strip())
                    names_by_tty_rel.setdefault(tty, []).append(name)
        result["related"] = list(set(related_names))

        # Refine canonical: prefer "Brand (ingredient)" when both are present
        in_rel = (names_by_tty_rel.get("IN", []) or
                  names_by_tty_rel.get("PIN", []) or
                  names_by_tty_rel.get("MIN", []))
        bn_rel = names_by_tty_rel.get("BN", [])
        if in_rel and bn_rel:
            result["canonical"] = f"{bn_rel[0].title()} ({in_rel[0].lower()})"
        elif in_rel:
            result["canonical"] = in_rel[0].title()
        elif bn_rel:
            result["canonical"] = bn_rel[0].title()
        # else: keep the bracket-extracted name from Step 1

        log.debug("RxNorm step2: %r → %d related names canonical=%r  (%.2fs)",
                  drug_name, len(result["related"]), result["canonical"], time.perf_counter() - t0)
    except Exception as exc:
        log.warning("RxNorm related lookup failed for RxCUI=%s: %s", rxcui, exc)

    return result


# ── Fuzzy matching against FAERS names ───────────────────────────────────────

def _tokenise(name: str) -> str:
    """Keep only alphanumeric chars + spaces, collapsed."""
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9 ]", " ", name)).strip().upper()


@st.cache_data(show_spinner=False)
def _get_faers_name_universe(drug_df_hash: int) -> list[str]:  # noqa: ARG001
    """
    We hash the drug df to use as cache key; caller passes hash.
    Returns unique list of all uppercase FAERS drug/prod_ai names.
    """
    from data_loader import load_tables
    drug = load_tables()["drug"]
    names = set()
    names.update(drug["drugname_norm"].dropna().unique())
    names.update(drug["prod_ai_norm"].dropna().unique())
    return sorted(names)


def _is_valid_drug_name(name: str) -> bool:
    """Filter out garbage strings: must be ≥4 chars and contain at least 3 ASCII letters."""
    if len(name) < 4:
        return False
    ascii_alpha = sum(1 for c in name if c.isalpha() and ord(c) < 128)
    return ascii_alpha >= 3


def find_faers_names(
    search_term: str,
    drug_df,
    *,
    fuzzy_threshold: int = 82,
    max_fuzzy_results: int = 50,
) -> list[str]:
    """
    Given a user search term, return every FAERS drug name string that
    corresponds to the same drug.

    Strategy:
      1. RxNorm lookup → collect all related uppercase names
      2. Exact / substring match those against FAERS names
      3. Fuzzy fallback for the original search term
    """
    import time
    t0 = time.perf_counter()
    log.info("find_faers_names: searching for %r", search_term)
    search_up = search_term.upper().strip()

    # All unique FAERS drug name strings — filtered to valid names only
    faers_names_drug = set(drug_df["drugname_norm"].dropna().unique())
    faers_names_prod = set(drug_df["prod_ai_norm"].dropna().unique())
    all_faers = {n for n in (faers_names_drug | faers_names_prod) if _is_valid_drug_name(n)}
    log.debug("FAERS name universe: %d unique names", len(all_faers))

    matched: set[str] = set()

    # 1. Direct substring match on the search term itself
    for n in all_faers:
        if search_up in n or n in search_up:
            matched.add(n)
    log.debug("Substring match: %d hits for %r", len(matched), search_up)

    # 2. RxNorm related names
    rxn = rxnorm_lookup(search_term)
    rxnorm_names = {search_up, rxn.get("canonical", "") or ""}
    rxnorm_names.update(rxn.get("related", []))
    rxnorm_names = {_tokenise(n) for n in rxnorm_names if n}

    before_rxn = len(matched)
    for faers_name in all_faers:
        faers_tok = _tokenise(faers_name)
        for rxn_name in rxnorm_names:
            if rxn_name and (rxn_name in faers_tok or faers_tok in rxn_name):
                matched.add(faers_name)
    log.debug("RxNorm match: +%d hits (%d RxNorm names checked)", len(matched) - before_rxn, len(rxnorm_names))

    # 3. Fuzzy fallback on search term (catches misspellings)
    if not matched:
        log.debug("No exact/RxNorm matches — falling back to fuzzy matching (threshold=%d)", fuzzy_threshold)
        hits = process.extract(
            search_up,
            list(all_faers),
            scorer=fuzz.token_set_ratio,
            limit=max_fuzzy_results,
            score_cutoff=fuzzy_threshold,
        )
        matched.update(name for name, _, _ in hits)
        log.debug("Fuzzy fallback: %d hits", len(matched))
        
        # add: 4. LLM fallback
        if not matched:
            llm_name = llm_normalize(search_term)
            llm_up = _tokenise(llm_name)
            if llm_up and llm_up != search_up:
                for faers_name in all_faers:
                    faers_tok = _tokenise(faers_name)
                    if llm_up in faers_tok or faers_tok in llm_up:
                        matched.add(faers_name)

  
    # 5. Canon expansion: for every matched name, add the corresponding prod_ai_norm
    #    (the canon key used by the lookup tables). This ensures that when a brand
    #    name like "SKYRIZI" is matched via drugname_norm, we also include
    #    "RISANKIZUMAB" (the prod_ai_norm / canon), so the indexed lookups work.
    #    This is critical when RxNorm step 2 fails and can't bridge brand→ingredient.
    if matched and "canon" in drug_df.columns:
        rows = drug_df[drug_df["drugname_norm"].isin(matched) | drug_df["prod_ai_norm"].isin(matched)]
        canon_vals = {n for n in rows["canon"].dropna().unique() if _is_valid_drug_name(n)}
        extra = canon_vals - matched
        if extra:
            log.debug("Canon expansion: +%d names from prod_ai cross-reference  e.g. %s",
                      len(extra), sorted(extra)[:3])
            matched.update(extra)

    result = sorted(matched)
    if result:
        log.info("find_faers_names: %r → %d FAERS names  (%.2fs)  e.g. %s",
                 search_term, len(result), time.perf_counter() - t0, result[:3])
    else:
        log.warning("find_faers_names: no FAERS matches for %r  (%.2fs)", search_term, time.perf_counter() - t0)
    return result


def filter_drug_df(drug_df, matched_names: list[str]):
    """Return rows whose drugname_norm or prod_ai_norm is in matched_names."""
    name_set = set(matched_names)
    mask = (
        drug_df["drugname_norm"].isin(name_set) |
        drug_df["prod_ai_norm"].isin(name_set)
    )
    return drug_df[mask]

"""
research_connector.py

Live connectors for external research databases:
  - ClinicalTrials.gov v2 API  (https://clinicaltrials.gov/api/v2/studies)
  - NCBI PubMed eutils          (https://eutils.ncbi.nlm.nih.gov/entrez/eutils/)
  - openFDA Drugs@FDA           (https://api.fda.gov/drug/drugsfda.json)
  - NLM RxClass API             (https://rxnav.nlm.nih.gov/REST/rxclass/)
  - openFDA Drug Label API      (https://api.fda.gov/drug/label.json)
  - openFDA Drug Enforcement    (https://api.fda.gov/drug/enforcement.json)

All endpoints are public and require no API key.
Results are cached via Streamlit's @st.cache_data (TTL: 1 hour).
"""

from __future__ import annotations

import time
import streamlit as st
import requests
import pandas as pd
from logger import get_logger
from api_cache import disk_cache

log = get_logger(__name__)

CTGOV_BASE       = "https://clinicaltrials.gov/api/v2/studies"
PUBMED_SEARCH    = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_SUMMARY   = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
OPENFDA_DRUGSFDA = "https://api.fda.gov/drug/drugsfda.json"
OPENFDA_LABEL    = "https://api.fda.gov/drug/label.json"
OPENFDA_ENFORCE  = "https://api.fda.gov/drug/enforcement.json"
RXCLASS_BASE     = "https://rxnav.nlm.nih.gov/REST/rxclass"

_REQUEST_TIMEOUT = 12


# ─────────────────────────────────────────────────────────────────────────────
# ClinicalTrials.gov
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
@disk_cache(ttl=3600)
def search_clinical_trials(
    query: str,
    max_results: int = 25,
    status_filter: str | None = None,
    search_mode: str = "condition",
) -> tuple[pd.DataFrame, int]:
    """
    Search ClinicalTrials.gov v2 for trials related to a condition or drug.

    Parameters
    ----------
    query        : free-text condition / symptom / drug name
    max_results  : number of records to return (max 200)
    status_filter: one of RECRUITING, COMPLETED, ACTIVE_NOT_RECRUITING, or None (all)
    search_mode  : "condition" to search by disease/symptom, "intervention" for drug

    Returns
    -------
    (DataFrame, total_count) — DataFrame columns:
        nct_id, title, status, phase, study_type, sponsor,
        enrollment, start_date, completion_date, interventions, conditions, url
    """
    params: dict = {
        "pageSize": min(max_results, 200),
        "format": "json",
        "countTotal": "true",
    }
    if search_mode == "intervention":
        params["query.intr"] = query
    else:
        params["query.cond"] = query

    if status_filter:
        params["filter.overallStatus"] = status_filter

    log.info("ClinicalTrials search: %r  mode=%s  status=%s", query, search_mode, status_filter)
    t0 = time.perf_counter()
    try:
        resp = requests.get(CTGOV_BASE, params=params, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        log.debug("ClinicalTrials response: %.2fs  status=%d", time.perf_counter() - t0, resp.status_code)
    except Exception as exc:
        log.warning("ClinicalTrials request failed for %r: %s", query, exc)
        return pd.DataFrame(), 0

    total = data.get("totalCount", 0)
    studies = data.get("studies", [])

    rows = []
    for study in studies:
        proto = study.get("protocolSection", {})
        ident  = proto.get("identificationModule", {})
        status = proto.get("statusModule", {})
        design = proto.get("designModule", {})
        arms   = proto.get("armsInterventionsModule", {})
        spon   = proto.get("sponsorCollaboratorsModule", {})
        conds  = proto.get("conditionsModule", {})

        nct = ident.get("nctId", "")
        phases = design.get("phases", [])
        intrvs = arms.get("interventions", [])
        conditions_list = conds.get("conditions", [])

        rows.append({
            "nct_id":          nct,
            "title":           ident.get("briefTitle", ""),
            "status":          status.get("overallStatus", ""),
            "phase":           ", ".join(phases) if phases else "N/A",
            "study_type":      design.get("studyType", ""),
            "sponsor":         spon.get("leadSponsor", {}).get("name", ""),
            "enrollment":      design.get("enrollmentInfo", {}).get("count", ""),
            "start_date":      status.get("startDateStruct", {}).get("date", ""),
            "completion_date": status.get("completionDateStruct", {}).get("date", ""),
            "interventions":   "; ".join(i.get("name", "") for i in intrvs[:4]),
            "conditions":      "; ".join(conditions_list[:3]),
            "url":             f"https://clinicaltrials.gov/study/{nct}",
        })

    log.info("ClinicalTrials: %r → %d/%d trials returned", query, len(rows), total)
    return pd.DataFrame(rows), int(total)


# ─────────────────────────────────────────────────────────────────────────────
# PubMed
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
@disk_cache(ttl=3600)
def search_pubmed(
    query: str,
    max_results: int = 20,
    sort: str = "relevance",
    date_filter: str | None = None,
) -> tuple[pd.DataFrame, int]:
    """
    Search PubMed via NCBI eutils for articles on a drug or symptom.

    Parameters
    ----------
    query        : free-text drug name, symptom, or structured PubMed query
    max_results  : number of records to retrieve
    sort         : "relevance" | "pub_date" | "author" | "journal"
    date_filter  : optional year range, e.g. "2020:2025[pdat]"

    Returns
    -------
    (DataFrame, total_count) — DataFrame columns:
        pmid, title, authors, journal, pub_date, pub_type, doi, url
    """
    log.info("PubMed search: %r  sort=%s  date_filter=%s", query, sort, date_filter)
    t0 = time.perf_counter()
    term = query
    if date_filter:
        term = f"({query}) AND {date_filter}"

    # Step 1 — esearch: retrieve PMIDs
    search_params = {
        "db":       "pubmed",
        "term":     term,
        "retmax":   max_results,
        "sort":     sort,
        "retmode":  "json",
    }
    try:
        sr = requests.get(PUBMED_SEARCH, params=search_params, timeout=_REQUEST_TIMEOUT)
        sr.raise_for_status()
        sr_data = sr.json()
    except Exception:
        return pd.DataFrame(), 0

    esr = sr_data.get("esearchresult", {})
    pmids = esr.get("idlist", [])
    total = int(esr.get("count", 0))

    if not pmids:
        return pd.DataFrame(), total

    # Step 2 — esummary: retrieve article metadata
    sum_params = {
        "db":      "pubmed",
        "id":      ",".join(pmids),
        "retmode": "json",
    }
    try:
        sumr = requests.get(PUBMED_SUMMARY, params=sum_params, timeout=_REQUEST_TIMEOUT)
        sumr.raise_for_status()
        sum_data = sumr.json()
    except Exception as exc:
        log.warning("PubMed esummary failed for %r: %s", query, exc)
        return pd.DataFrame(), total

    result = sum_data.get("result", {})
    uids   = result.get("uids", [])

    rows = []
    for uid in uids:
        art = result.get(uid, {})
        if not art:
            continue

        authors = art.get("authors", [])
        author_str = ", ".join(a.get("name", "") for a in authors[:3])
        if len(authors) > 3:
            author_str += " et al."

        # Extract DOI from articleids list
        doi = ""
        for aid in art.get("articleids", []):
            if aid.get("idtype") == "doi":
                doi = aid.get("value", "")
                break

        rows.append({
            "pmid":     uid,
            "title":    art.get("title", "").rstrip("."),
            "authors":  author_str,
            "journal":  art.get("fulljournalname", art.get("source", "")),
            "pub_date": art.get("pubdate", ""),
            "pub_type": ", ".join(art.get("pubtype", [])[:2]),
            "doi":      doi,
            "url":      f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
        })

    log.info("PubMed: %r → %d/%d articles  (%.2fs)", query, len(rows), total, time.perf_counter() - t0)
    return pd.DataFrame(rows), total


# ─────────────────────────────────────────────────────────────────────────────
# openFDA — Drug approval & regulatory info
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
@disk_cache(ttl=86400)
def get_fda_approval_info(drug_name: str) -> list[dict]:
    """
    Query openFDA Drugs@FDA for regulatory approval information.

    Returns a list of matching application records, each containing:
        application_number, app_type, sponsor, brand_names, generic_names,
        dosage_forms, routes, marketing_status, first_approval_date,
        latest_action_date, ob_url (Orange Book link)

    Results are cached for 24 hours (regulatory data changes infrequently).
    Returns an empty list on error or no match.
    """
    log.info("FDA approval lookup: %r", drug_name)
    t0 = time.perf_counter()
    for field in ("openfda.brand_name", "openfda.generic_name", "openfda.substance_name"):
        try:
            resp = requests.get(
                OPENFDA_DRUGSFDA,
                params={"search": f'{field}:"{drug_name}"', "limit": 5},
                timeout=_REQUEST_TIMEOUT,
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                if results:
                    log.info("FDA approval: %r → %d records via %s  (%.2fs)",
                             drug_name, len(results), field, time.perf_counter() - t0)
                    return [_parse_fda_result(r) for r in results]
        except Exception as exc:
            log.warning("FDA approval request failed for %r (field=%s): %s", drug_name, field, exc)
    log.info("FDA approval: no records found for %r  (%.2fs)", drug_name, time.perf_counter() - t0)
    return []


def _parse_fda_result(r: dict) -> dict:
    """Extract key fields from a single openFDA drugsfda result."""
    openfda = r.get("openfda", {})
    submissions = r.get("submissions", [])
    products = r.get("products", [])

    # First approval: earliest ORIG submission with status AP
    orig_dates = [
        s["submission_status_date"]
        for s in submissions
        if s.get("submission_type") == "ORIG" and s.get("submission_status") == "AP"
        and s.get("submission_status_date")
    ]
    first_approval = min(orig_dates) if orig_dates else None

    # Latest action across all submissions
    all_dates = [s["submission_status_date"] for s in submissions if s.get("submission_status_date")]
    latest_action = max(all_dates) if all_dates else None

    def fmt_date(d: str | None) -> str:
        if not d or len(d) < 8:
            return "—"
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}"

    app_num = r.get("application_number", "")
    app_type = "NDA (Brand)" if app_num.startswith("NDA") else \
               "BLA (Biologic)" if app_num.startswith("BLA") else \
               "ANDA (Generic)" if app_num.startswith("ANDA") else app_num[:4]

    dosage_forms = sorted({p.get("dosage_form", "") for p in products if p.get("dosage_form")})
    routes = sorted({p.get("route", "") for p in products if p.get("route")})
    mkt_statuses = sorted({p.get("marketing_status", "") for p in products if p.get("marketing_status")})

    return {
        "application_number": app_num,
        "app_type":           app_type,
        "sponsor":            r.get("sponsor_name", "—"),
        "brand_names":        ", ".join(openfda.get("brand_name", [])[:3]),
        "generic_names":      ", ".join(openfda.get("generic_name", [])[:2]),
        "dosage_forms":       ", ".join(dosage_forms[:4]),
        "routes":             ", ".join(routes[:3]),
        "marketing_status":   ", ".join(mkt_statuses[:2]),
        "first_approval":     fmt_date(first_approval),
        "latest_action":      fmt_date(latest_action),
        # Direct link to the Orange Book entry for this application
        "ob_url": f"https://www.accessdata.fda.gov/scripts/cder/ob/results_product.cfm"
                  f"?Appl_Type={app_num[:3]}&Appl_No={app_num[3:].lstrip('0')}",
        "fda_url": f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm"
                   f"?event=overview.process&ApplNo={app_num[3:].lstrip('0')}",
    }


# ─────────────────────────────────────────────────────────────────────────────
# NLM RxClass — therapeutic drug classification (ATC, VA, MeSH)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
@disk_cache(ttl=86400)
def get_drug_class(rxcui: str) -> list[dict]:
    """
    Fetch therapeutic classifications for a drug via the NLM RxClass API.

    Uses ATC (WHO Anatomical Therapeutic Chemical) and VA (Veterans Affairs)
    class systems.  Returns a list of dicts, each with:
        class_id, class_name, class_type, source

    Results are cached for 24 hours (class mappings rarely change).
    Returns an empty list on error or unknown RxCUI.
    """
    if not rxcui:
        return []

    log.info("RxClass lookup: rxcui=%s", rxcui)
    t0 = time.perf_counter()
    results: list[dict] = []
    for source in ("ATC", "VA"):
        try:
            resp = requests.get(
                f"{RXCLASS_BASE}/class/byRxcui.json",
                params={"rxcui": rxcui, "relaSource": source},
                timeout=_REQUEST_TIMEOUT,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            classes = (
                data.get("rxclassDrugInfoList", {})
                    .get("rxclassDrugInfo", [])
            )
            for c in classes:
                info = c.get("rxclassMinConceptItem", {})
                results.append({
                    "class_id":   info.get("classId", ""),
                    "class_name": info.get("className", ""),
                    "class_type": info.get("classType", ""),
                    "source":     source,
                })
        except Exception as exc:
            log.warning("RxClass request failed for rxcui=%s source=%s: %s", rxcui, source, exc)
            continue

    # Deduplicate by class_name
    seen: set[str] = set()
    unique: list[dict] = []
    for r in results:
        if r["class_name"] not in seen:
            seen.add(r["class_name"])
            unique.append(r)
    log.info("RxClass: rxcui=%s → %d classes  (%.2fs)", rxcui, len(unique), time.perf_counter() - t0)
    return unique


# ─────────────────────────────────────────────────────────────────────────────
# openFDA Drug Label — boxed warnings and key safety sections
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
@disk_cache(ttl=86400)
def get_drug_label(drug_name: str) -> dict:
    """
    Fetch structured product label data from openFDA for a drug.

    Returns a dict with keys (all may be empty strings):
        boxed_warning, warnings, indications, contraindications,
        brand_name, generic_name, manufacturer

    Tries brand name then generic name search.
    Results are cached for 24 hours. Returns empty dict on error.
    """
    empty: dict = {
        "boxed_warning": "", "warnings": "", "indications": "",
        "contraindications": "", "brand_name": "", "generic_name": "",
        "manufacturer": "",
    }

    def _first(lst: list) -> str:
        return lst[0].strip() if lst else ""

    log.info("FDA label lookup: %r", drug_name)
    t0 = time.perf_counter()
    for field in ("openfda.brand_name", "openfda.generic_name", "openfda.substance_name"):
        try:
            resp = requests.get(
                OPENFDA_LABEL,
                params={"search": f'{field}:"{drug_name}"', "limit": 1},
                timeout=_REQUEST_TIMEOUT,
            )
            if resp.status_code != 200:
                continue
            results = resp.json().get("results", [])
            if not results:
                continue
            r = results[0]
            openfda = r.get("openfda", {})
            has_boxed = bool(r.get("boxed_warning"))
            log.info("FDA label: %r found via %s  boxed_warning=%s  (%.2fs)",
                     drug_name, field, has_boxed, time.perf_counter() - t0)
            return {
                "boxed_warning":   _first(r.get("boxed_warning", [])),
                "warnings":        _first(r.get("warnings", [])),
                "indications":     _first(r.get("indications_and_usage", [])),
                "contraindications": _first(r.get("contraindications", [])),
                "brand_name":      _first(openfda.get("brand_name", [])),
                "generic_name":    _first(openfda.get("generic_name", [])),
                "manufacturer":    _first(openfda.get("manufacturer_name", [])),
            }
        except Exception as exc:
            log.warning("FDA label request failed for %r (field=%s): %s", drug_name, field, exc)
            continue
    log.info("FDA label: no label found for %r  (%.2fs)", drug_name, time.perf_counter() - t0)
    return empty


# ─────────────────────────────────────────────────────────────────────────────
# openFDA Drug Enforcement — recalls and enforcement actions
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
@disk_cache(ttl=3600)
def get_drug_enforcement(drug_name: str, limit: int = 5) -> list[dict]:
    """
    Search openFDA Drug Enforcement database for recall/enforcement actions.

    Returns a list of dicts, each with:
        recall_number, status, recalling_firm, reason_for_recall,
        product_description, classification, recall_initiation_date, termination_date

    Classification: Class I (most serious) → Class III (least serious).
    Results are cached for 1 hour. Returns empty list on error.
    """
    log.info("FDA enforcement lookup: %r", drug_name)
    t0 = time.perf_counter()
    try:
        resp = requests.get(
            OPENFDA_ENFORCE,
            params={
                "search": f'product_description:"{drug_name}"',
                "limit":  limit,
                "sort":   "recall_initiation_date:desc",
            },
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            log.info("FDA enforcement: no records for %r (status=%d)  (%.2fs)",
                     drug_name, resp.status_code, time.perf_counter() - t0)
            return []
        results = resp.json().get("results", [])
        log.info("FDA enforcement: %r → %d recall records  (%.2fs)",
                 drug_name, len(results), time.perf_counter() - t0)
        return [
            {
                "recall_number":         r.get("recall_number", ""),
                "status":                r.get("status", ""),
                "recalling_firm":        r.get("recalling_firm", ""),
                "reason_for_recall":     r.get("reason_for_recall", "")[:200],
                "product_description":   r.get("product_description", "")[:120],
                "classification":        r.get("classification", ""),
                "recall_initiation_date":r.get("recall_initiation_date", ""),
                "termination_date":      r.get("termination_date", ""),
            }
            for r in results
        ]
    except Exception as exc:
        log.warning("FDA enforcement request failed for %r: %s", drug_name, exc)
        return []

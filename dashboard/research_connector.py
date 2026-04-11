"""
research_connector.py

Live connectors for external research databases:
  - ClinicalTrials.gov v2 API  (https://clinicaltrials.gov/api/v2/studies)
  - NCBI PubMed eutils          (https://eutils.ncbi.nlm.nih.gov/entrez/eutils/)
  - openFDA Drugs@FDA           (https://api.fda.gov/drug/drugsfda.json)

All endpoints are public and require no API key.
Results are cached via Streamlit's @st.cache_data (TTL: 1 hour).
"""

from __future__ import annotations

import streamlit as st
import requests
import pandas as pd

CTGOV_BASE    = "https://clinicaltrials.gov/api/v2/studies"
PUBMED_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_SUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
OPENFDA_DRUGSFDA = "https://api.fda.gov/drug/drugsfda.json"

_REQUEST_TIMEOUT = 12


# ─────────────────────────────────────────────────────────────────────────────
# ClinicalTrials.gov
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
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

    try:
        resp = requests.get(CTGOV_BASE, params=params, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
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

    return pd.DataFrame(rows), int(total)


# ─────────────────────────────────────────────────────────────────────────────
# PubMed
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
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
    except Exception:
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

    return pd.DataFrame(rows), total


# ─────────────────────────────────────────────────────────────────────────────
# openFDA — Drug approval & regulatory info
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
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
    # Try brand name first, fall back to generic name
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
                    return [_parse_fda_result(r) for r in results]
        except Exception:
            pass
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

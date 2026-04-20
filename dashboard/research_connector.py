from __future__ import annotations

from typing import Any

import requests


def get_drug_class(rxcui: str | None) -> dict[str, Any]:
    if not rxcui:
        return {}
    try:
        url = f"https://rxnav.nlm.nih.gov/REST/rxclass/class/byRxcui.json?rxcui={rxcui}"
        data = requests.get(url, timeout=8).json()
        classes = data.get("rxclassDrugInfoList", {}).get("rxclassDrugInfo", [])
        if not classes:
            return {}
        best = classes[0].get("rxclassMinConceptItem", {})
        return {
            "class_name": best.get("className", ""),
            "class_type": best.get("classType", ""),
        }
    except Exception:
        return {}


def get_fda_approval_info(drug_name: str) -> dict[str, Any]:
    q = (drug_name or "").strip()
    if not q:
        return {}
    try:
        url = "https://api.fda.gov/drug/drugsfda.json"
        params = {"search": f"openfda.brand_name:{q}", "limit": 1}
        payload = requests.get(url, params=params, timeout=8).json()
        results = payload.get("results", [])
        if not results:
            return {}
        r = results[0]
        products = r.get("products", [])
        app = r.get("application_number", "")
        sponsor = r.get("sponsor_name", "")
        product = products[0] if products else {}
        return {
            "application_number": app,
            "sponsor": sponsor,
            "dosage_form": product.get("dosage_form", ""),
            "route": product.get("route", ""),
            "marketing_status": str(product.get("marketing_status", "")),
            "first_approval_date": r.get("submissions", [{}])[-1].get(
                "submission_status_date", ""
            )
            if r.get("submissions")
            else "",
            "latest_action_date": r.get("submissions", [{}])[0].get(
                "submission_status_date", ""
            )
            if r.get("submissions")
            else "",
        }
    except Exception:
        return {}


def get_drug_label(drug_name: str) -> dict[str, Any]:
    q = (drug_name or "").strip()
    if not q:
        return {}
    try:
        url = "https://api.fda.gov/drug/label.json"
        params = {"search": f"openfda.brand_name:{q}", "limit": 1}
        payload = requests.get(url, params=params, timeout=8).json()
        results = payload.get("results", [])
        if not results:
            return {}
        bw = results[0].get("boxed_warning", [])
        txt = bw[0] if bw else ""
        return {"boxed_warning": txt}
    except Exception:
        return {}


def get_drug_enforcement(drug_name: str) -> list[dict[str, Any]]:
    q = (drug_name or "").strip()
    if not q:
        return []
    try:
        url = "https://api.fda.gov/drug/enforcement.json"
        params = {"search": f"product_description:{q}", "limit": 5}
        payload = requests.get(url, params=params, timeout=8).json()
        out = []
        for row in payload.get("results", []):
            out.append(
                {
                    "recall_number": row.get("recall_number", ""),
                    "classification": row.get("classification", ""),
                    "reason": row.get("reason_for_recall", ""),
                    "report_date": row.get("report_date", ""),
                }
            )
        return out
    except Exception:
        return []


def search_clinical_trials(drug_name: str) -> list[dict[str, str]]:
    q = (drug_name or "").strip()
    if not q:
        return []
    try:
        url = "https://clinicaltrials.gov/api/v2/studies"
        params = {"query.term": q, "pageSize": 10}
        payload = requests.get(url, params=params, timeout=10).json()
        out = []
        for s in payload.get("studies", [])[:10]:
            proto = s.get("protocolSection", {})
            ident = proto.get("identificationModule", {})
            status = proto.get("statusModule", {})
            nct_id = ident.get("nctId", "")
            out.append(
                {
                    "nct_id": nct_id,
                    "title": ident.get("briefTitle", ""),
                    "status": status.get("overallStatus", ""),
                    "link": f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else "",
                }
            )
        return out
    except Exception:
        return []


def search_pubmed(query: str) -> list[dict[str, str]]:
    q = (query or "").strip()
    if not q:
        return []
    try:
        base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        esearch = requests.get(
            f"{base}/esearch.fcgi",
            params={"db": "pubmed", "retmode": "json", "term": q, "retmax": 10},
            timeout=10,
        ).json()
        ids = esearch.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        esummary = requests.get(
            f"{base}/esummary.fcgi",
            params={"db": "pubmed", "retmode": "json", "id": ",".join(ids)},
            timeout=10,
        ).json()
        out = []
        for pid in ids:
            rec = esummary.get("result", {}).get(pid, {})
            out.append({
                "pmid": pid,
                "title": rec.get("title", ""),
                "link": f"https://pubmed.ncbi.nlm.nih.gov/{pid}/",
            })
        return out
    except Exception:
        return []

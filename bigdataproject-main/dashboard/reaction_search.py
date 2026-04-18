from __future__ import annotations

from typing import Any

from rapidfuzz import fuzz, process


LAY_SYNONYMS = {
    "heart attack": ["myocardial infarction", "acute myocardial infarction"],
    "stroke": ["cerebrovascular accident", "ischemic stroke", "hemorrhagic stroke"],
    "throwing up": ["vomiting", "nausea"],
    "kidney failure": ["acute kidney injury", "renal failure"],
    "liver injury": ["hepatic failure", "drug induced liver injury"],
    "rash": ["rash", "urticaria", "erythema"],
}


def find_reaction_terms(
    query: str, all_terms: list[str], limit: int = 20
) -> list[dict[str, Any]]:
    q = (query or "").strip().lower()
    if not q or not all_terms:
        return []

    terms_norm = [(t, t.lower()) for t in all_terms]
    candidates: list[tuple[str, float]] = []

    for syn in LAY_SYNONYMS.get(q, []):
        for term, norm in terms_norm:
            if syn in norm:
                candidates.append((term, 98.0))

    for term, norm in terms_norm:
        if q == norm:
            candidates.append((term, 100.0))
        elif q in norm:
            score = 90.0 - min(20.0, float(len(norm) - len(q)) * 0.3)
            candidates.append((term, max(70.0, score)))

    if len(candidates) < limit:
        fuzzy = process.extract(q, all_terms, scorer=fuzz.token_set_ratio, limit=limit)
        candidates.extend([(name, float(score)) for name, score, _ in fuzzy])

    best: dict[str, float] = {}
    for name, score in candidates:
        if name not in best or score > best[name]:
            best[name] = score

    ranked = sorted(best.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [{"term": name, "score": round(score, 1)} for name, score in ranked]

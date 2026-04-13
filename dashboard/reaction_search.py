"""
reaction_search.py

Maps plain-English user queries to MedDRA Preferred Terms (PTs) present in FAERS.

Approach:
  1. A curated synonym dictionary covering the most-searched lay terms → MedDRA PTs.
  2. Fuzzy matching (token_set_ratio) against the full PT vocabulary as a fallback.
  3. Results ranked by match score.

Why not a full MedDRA hierarchy lookup?
  MedDRA requires a paid license. The PTs already in FAERS are the ground truth;
  we just need to help users find them with plain language.
"""

from rapidfuzz import process, fuzz
from logger import get_logger

log = get_logger(__name__)

# ── Lay-term → MedDRA PT synonym map ─────────────────────────────────────────
# Keys are lowercase plain English; values are MedDRA PTs (title case).
# This covers common consumer search terms. Extend freely.

LAY_SYNONYMS: dict[str, list[str]] = {
    # gastrointestinal
    "nausea": ["Nausea"],
    "nauseous": ["Nausea"],
    "sick to stomach": ["Nausea"],
    "throwing up": ["Vomiting"],
    "vomiting": ["Vomiting"],
    "puking": ["Vomiting"],
    "diarrhea": ["Diarrhoea"],
    "diarrhoea": ["Diarrhoea"],
    "loose stool": ["Diarrhoea"],
    "constipation": ["Constipation"],
    "stomach pain": ["Abdominal Pain", "Abdominal Pain Upper"],
    "belly pain": ["Abdominal Pain"],
    "heartburn": ["Dyspepsia", "Gastrooesophageal Reflux Disease"],
    "acid reflux": ["Gastrooesophageal Reflux Disease"],
    "gerd": ["Gastrooesophageal Reflux Disease"],
    "bloating": ["Abdominal Distension", "Flatulence"],
    "gas": ["Flatulence"],
    "bleeding": ["Haemorrhage", "Gastrointestinal Haemorrhage"],
    "bloody stool": ["Haematochezia", "Rectal Haemorrhage"],
    "black stool": ["Melaena"],

    # cardiac
    "heart attack": ["Acute Myocardial Infarction", "Myocardial Infarction"],
    "heart failure": ["Cardiac Failure", "Cardiac Failure Congestive"],
    "chest pain": ["Chest Pain", "Chest Discomfort"],
    "palpitations": ["Palpitations"],
    "fast heartbeat": ["Tachycardia", "Heart Rate Increased"],
    "slow heartbeat": ["Bradycardia"],
    "irregular heartbeat": ["Atrial Fibrillation", "Arrhythmia"],
    "high blood pressure": ["Hypertension"],
    "low blood pressure": ["Hypotension"],

    # neurological
    "headache": ["Headache"],
    "migraine": ["Migraine"],
    "dizziness": ["Dizziness"],
    "dizzy": ["Dizziness"],
    "lightheaded": ["Dizziness", "Presyncope"],
    "fainting": ["Syncope"],
    "seizure": ["Seizure", "Epilepsy"],
    "stroke": ["Cerebrovascular Accident", "Basal Ganglia Stroke", "Cerebellar Stroke"],
    "memory loss": ["Memory Impairment", "Amnesia"],
    "confusion": ["Confusional State"],
    "tremor": ["Tremor"],
    "numbness": ["Hypoaesthesia", "Paraesthesia"],
    "tingling": ["Paraesthesia"],

    # respiratory
    "shortness of breath": ["Dyspnoea"],
    "trouble breathing": ["Dyspnoea"],
    "cough": ["Cough"],
    "wheezing": ["Wheezing"],
    "pneumonia": ["Pneumonia"],

    # musculoskeletal
    "joint pain": ["Arthralgia"],
    "muscle pain": ["Myalgia"],
    "muscle weakness": ["Muscular Weakness"],
    "back pain": ["Back Pain"],

    # skin
    "rash": ["Rash", "Rash Maculo-Papular"],
    "itching": ["Pruritus"],
    "itchy": ["Pruritus"],
    "hives": ["Urticaria"],
    "swelling": ["Oedema", "Oedema Peripheral", "Face Oedema"],
    "bruising": ["Ecchymosis", "Contusion"],
    "hair loss": ["Alopecia"],

    # general / systemic
    "fatigue": ["Fatigue"],
    "tired": ["Fatigue", "Asthenia"],
    "weakness": ["Asthenia", "Fatigue"],
    "fever": ["Pyrexia"],
    "chills": ["Chills"],
    "weight gain": ["Weight Increased", "Abnormal Weight Gain"],
    "weight loss": ["Weight Decreased", "Abnormal Loss Of Weight"],
    "appetite loss": ["Decreased Appetite", "Appetite Disorder"],
    "death": ["Death"],
    "died": ["Death"],
    "infection": ["Infection"],
    "swollen lymph nodes": ["Lymphadenopathy"],

    # psychiatric
    "anxiety": ["Anxiety"],
    "depression": ["Depression"],
    "insomnia": ["Insomnia"],
    "sleep problems": ["Insomnia", "Sleep Disorder"],
    "hallucinations": ["Hallucination"],
    "suicidal thoughts": ["Suicidal Ideation"],

    # urinary / renal
    "kidney failure": ["Acute Kidney Injury", "Chronic Kidney Disease", "Renal Impairment"],
    "frequent urination": ["Pollakiuria"],
    "painful urination": ["Dysuria"],
    "blood in urine": ["Haematuria"],

    # liver
    "liver damage": ["Hepatotoxicity", "Hepatic Function Abnormal"],
    "jaundice": ["Jaundice"],
    "yellow skin": ["Jaundice"],

    # allergy / anaphylaxis
    "allergic reaction": ["Hypersensitivity", "Drug Hypersensitivity"],
    "anaphylaxis": ["Anaphylactic Reaction", "Anaphylactic Shock"],
    "anaphylactic shock": ["Anaphylactic Shock"],
}


# ── Main search function ──────────────────────────────────────────────────────

def search_reactions(
    query: str,
    all_pts: list[str],
    *,
    fuzzy_threshold: int = 60,
    max_results: int = 20,
) -> list[tuple[str, float]]:
    """
    Map a plain-English query to a ranked list of (MedDRA PT, score) tuples.

    Args:
        query:           User input string.
        all_pts:         Full list of unique MedDRA PTs present in FAERS.
        fuzzy_threshold: Minimum fuzzy score to include a PT (0-100).
        max_results:     Maximum number of results to return.

    Returns:
        List of (pt, score) sorted by score descending.
    """
    import time
    t0 = time.perf_counter()
    log.info("Reaction search: %r  (%d PTs in vocabulary)", query, len(all_pts))

    query_lower = query.lower().strip()
    query_title = query.title()
    results: dict[str, float] = {}

    # 1. Synonym dictionary hit (score = 100)
    for lay_term, pts in LAY_SYNONYMS.items():
        if lay_term in query_lower or query_lower in lay_term:
            for pt in pts:
                if pt in all_pts:
                    results[pt] = 100.0
    if results:
        log.debug("Synonym dict hit for %r: %s", query, list(results.keys()))

    # 2. Substring match in the PT vocabulary — tiered scoring
    #    98: exact match  |  95: PT contains query  |  90: query contains PT (partial)
    query_up = query.upper()
    before_substr = len(results)
    for pt in all_pts:
        pt_up = pt.upper()
        existing = results.get(pt, 0)
        if pt_up == query_up:
            results[pt] = max(existing, 98.0)
        elif existing == 0:
            if query_up in pt_up:
                results[pt] = 95.0
            elif pt_up in query_up:
                results[pt] = 90.0
    log.debug("Substring match added %d PTs for %r", len(results) - before_substr, query)

    # 3. Fuzzy fallback — use WRatio for better whole-phrase matching,
    #    avoiding false positives from shared single words (e.g. "attack")
    before_fuzzy = len(results)
    hits = process.extract(
        query_title,
        all_pts,
        scorer=fuzz.WRatio,
        limit=max_results * 2,
        score_cutoff=max(fuzzy_threshold, 87),  # 85.5 = single-shared-word artefact; 87+ are real matches
    )
    for pt, score, _ in hits:
        if pt not in results:
            results[pt] = float(score)
    log.debug("Fuzzy match added %d PTs for %r", len(results) - before_fuzzy, query)

    sorted_results = sorted(results.items(), key=lambda x: -x[1])
    final = sorted_results[:max_results]

    if final:
        log.info("Reaction search %r → %d results  top: %s  (%.2fs)",
                 query, len(final), [pt for pt, _ in final[:3]], time.perf_counter() - t0)
    else:
        log.warning("Reaction search %r → no results  (%.2fs)", query, time.perf_counter() - t0)
    return final

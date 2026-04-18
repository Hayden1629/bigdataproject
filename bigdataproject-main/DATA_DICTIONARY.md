# FAERS Data Dictionary

FDA Adverse Event Reporting System (FAERS) — ASCII quarterly extract format.

---

## Table Relationships

```
Therapy  ──┐
           ├──► Drug ──────────────► Demographic ◄──── Reaction
Indication─┘                              │
                                          ├──────────► Outcome
                                          └──────────► Report_Sources
```

**Central key: `primaryid`** — every table links back to `demo` through this field. It uniquely identifies a case-version (one report at one point in time).

**`caseid`** is the base case identifier. A case can be updated multiple times; each update gets a new `primaryid` but the same `caseid`. When deduplicating across quarters, keep the row with the highest `caseversion` for each `caseid`.

**Drug-level join key: `drug_seq` / `dsg_drug_seq` / `indi_drug_seq`** — `ther` and `indi` link to specific drugs within a case via this sequence number. To join therapy dates or indications to a drug, match on both `primaryid` AND `drug_seq`.

---

## Tables

### `demo` — Demographic (1 row per case)

The central table. One row per reported adverse event case version.

| Column               | Description                                                                                                                                                                                               |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `primaryid`        | Primary key. Unique case-version identifier. Composite of `caseid` + `caseversion`.                                                                                                                   |
| `caseid`           | Base case ID. Stays the same across follow-up reports for the same event.                                                                                                                                 |
| `caseversion`      | Version number. Higher = more recent update. Use `MAX(caseversion)` per `caseid` to get the latest.                                                                                                   |
| `i_f_code`         | Initial or follow-up report.`I` = initial submission, `F` = follow-up/amendment.                                                                                                                      |
| `event_dt`         | Date the adverse event occurred (YYYYMMDD, may be partial e.g. YYYYMM or YYYY).                                                                                                                           |
| `mfr_dt`           | Date the manufacturer received the report.                                                                                                                                                                |
| `init_fda_dt`      | Date FDA first received any version of this case.                                                                                                                                                         |
| `fda_dt`           | Date FDA received this specific version.                                                                                                                                                                  |
| `rept_cod`         | Report type.`EXP` = 15-day expedited (serious/unexpected), `PER` = periodic, `DIR` = direct.                                                                                                        |
| `auth_num`         | Authorization/NDA number associated with the report.                                                                                                                                                      |
| `mfr_num`          | Manufacturer's internal report number.                                                                                                                                                                    |
| `mfr_sndr`         | Name of the manufacturer who submitted the report.                                                                                                                                                        |
| `lit_ref`          | Literature reference if the case originated from a published paper.                                                                                                                                       |
| `age`              | Patient age (numeric, use `age_cod` for units).                                                                                                                                                         |
| `age_cod`          | Age unit.`YR` = years, `MON` = months, `WK` = weeks, `DY` = days, `HR` = hours, `DEC` = decades.                                                                                              |
| `age_grp`          | Age group bucket.`N` = neonate, `I` = infant, `C` = child, `T` = teenager, `A` = adult, `E` = elderly.                                                                                        |
| `sex`              | Patient sex.`M` = male, `F` = female, `UNK` = unknown.                                                                                                                                              |
| `e_sub`            | Electronic submission flag.`Y` = submitted electronically.                                                                                                                                              |
| `wt`               | Patient weight (numeric, use `wt_cod` for units).                                                                                                                                                       |
| `wt_cod`           | Weight unit.`KG` = kilograms, `LBS` = pounds, ``GMS`` Grams.                                                                                                                                          |
| `rept_dt`          | Date the report was submitted to FDA.                                                                                                                                                                     |
| `to_mfr`           | Whether FDA forwarded the report to the manufacturer.`Y` / `N`.                                                                                                                                       |
| `occp_cod`         | Occupation of the reporter.`MD` = physician, `PH` = pharmacist, `RN` = nurse, `OT` = other health professional, `LW` = lawyer, `CN` = consumer, `HP` = health professional (general).       |
| `reporter_country` | Country of the person who filed the report (ISO country code). Link to country code:<br />https://www.fda.gov/industry/structured-product-labeling-resources/geopolitical-entities-names-and-codes-genc  |
| `occr_country`     | Country where the adverse event occurred (ISO country code).                                                                                                                                              |

---

### `drug` — Drug Information (1+ rows per case)

One row per drug reported in the case. A single case typically has multiple drugs (the suspect drug plus concomitant medications).

| Column            | Description                                                                                                                                   |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `primaryid`     | Foreign key to `demo`.                                                                                                                      |
| `caseid`        | Base case ID.                                                                                                                                 |
| `drug_seq`      | Drug sequence number within the case. Used to join to `ther` and `indi`.                                                                  |
| `role_cod`      | Role of the drug in the event.`PS` = primary suspect, `SS` = secondary suspect, `C` = concomitant (not suspected), `I` = interacting. |
| `drugname`      | Drug name as reported (free text — messy, not standardized).                                                                                 |
| `prod_ai`       | Active ingredient(s) of the product. More standardized than `drugname`.                                                                     |
| `val_vbm`       | Validation flag indicating whether the drug was validated against an FDA reference.`1` = validated.                                         |
| `route`         | Route of administration (e.g.,`oral`, `intravenous`, `topical`).                                                                        |
| `dose_vbm`      | Dose as verbatim reported by the submitter (free text).                                                                                       |
| `cum_dose_chr`  | Cumulative dose characterization (numeric string).                                                                                            |
| `cum_dose_unit` | Unit for cumulative dose (e.g.,`mg`, `g`).                                                                                                |
| `dechal`        | Dechallenge result — did the event improve after stopping the drug?`Y` = yes, `N` = no, `U` = unknown, `D` = drug not stopped.       |
| `rechal`        | Rechallenge result — did the event recur after restarting the drug?`Y` = yes, `N` = no, `U` = unknown, `D` = not rechallenged.       |
| `lot_num`       | Drug lot/batch number.                                                                                                                        |
| `exp_dt`        | Drug expiration date.                                                                                                                         |
| `nda_num`       | NDA (New Drug Application) or BLA number — links to FDA approval database.                                                                   |
| `dose_amt`      | Dose amount (numeric).                                                                                                                        |
| `dose_unit`     | Dose unit (e.g.,`mg`, `mcg`, `mg/kg`).                                                                                                  |
| `dose_form`     | Dosage form (e.g.,`tablet`, `capsule`, `solution`).                                                                                     |
| `dose_freq`     | Dose frequency (e.g.,`QD` = once daily, `BID` = twice daily).                                                                             |

---

### `reac` — Reactions (1+ rows per case)

One row per adverse reaction reported for the case. Terms are coded in MedDRA Preferred Terms (PTs).

| Column           | Description                                                                                                                                      |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `primaryid`    | Foreign key to `demo`.                                                                                                                         |
| `caseid`       | Base case ID.                                                                                                                                    |
| `pt`           | MedDRA Preferred Term describing the adverse event (e.g.,`nausea`, `myocardial infarction`). This is the primary field for signal detection. |
| `drug_rec_act` | Action taken with the drug in response to the reaction (e.g.,`drug withdrawn`, `dose reduced`, `dose not changed`).                        |

---

### `outc` — Outcomes (0+ rows per case)

One row per serious outcome associated with the case. A case with no serious outcome will have no rows here.

| Column        | Description                                                                                                                                                                                                                                        |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `primaryid` | Foreign key to `demo`.                                                                                                                                                                                                                           |
| `caseid`    | Base case ID.                                                                                                                                                                                                                                      |
| `outc_cod`  | Outcome code.`DE` = death, `LT` = life-threatening, `HO` = hospitalization (initial or prolonged), `DS` = disability, `CA` = congenital anomaly, `RI` = required intervention to prevent permanent impairment, `OT` = other serious. |

---

### `rpsr` — Report Sources (0+ rows per case)

One row per source through which the report was received. A case can have multiple sources.

| Column        | Description                                                                                                                                                                                                                                                                                                 |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `primaryid` | Foreign key to `demo`.                                                                                                                                                                                                                                                                                    |
| `caseid`    | Base case ID.                                                                                                                                                                                                                                                                                               |
| `rpsr_cod`  | Source code.`FGN` = foreign regulatory authority, `SDY` = study, `LIT` = literature, `CSM` = consumer/non-health professional, `HP` = health professional, `UF` = user facility, `CR` = compounding pharmacy, `DT` = distributor, `MFR` = manufacturer, `MDC` = medical device company. |

---

### `ther` — Therapy Dates (0+ rows per drug per case)

One row per drug therapy period. Links to a specific drug in `drug` via `primaryid` + `dsg_drug_seq`.

| Column           | Description                                                                                                       |
| ---------------- | ----------------------------------------------------------------------------------------------------------------- |
| `primaryid`    | Foreign key to `demo` and `drug`.                                                                             |
| `caseid`       | Base case ID.                                                                                                     |
| `dsg_drug_seq` | Drug sequence number — matches `drug.drug_seq` to identify which drug this therapy record belongs to.          |
| `start_dt`     | Therapy start date (YYYYMMDD, may be partial).                                                                    |
| `end_dt`       | Therapy end date (YYYYMMDD, may be partial).                                                                      |
| `dur`          | Duration of therapy (numeric).                                                                                    |
| `dur_cod`      | Duration unit.`YR` = years, `MON` = months, `WK` = weeks, `DY` = days, `HR` = hours, `MIN` = minutes. |

---

### `indi` — Indications (0+ rows per drug per case)

One row per indication (reason the drug was prescribed) per drug. Links to a specific drug via `primaryid` + `indi_drug_seq`.

| Column            | Description                                                                                                                                  |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `primaryid`     | Foreign key to `demo` and `drug`.                                                                                                        |
| `caseid`        | Base case ID.                                                                                                                                |
| `indi_drug_seq` | Drug sequence number — matches `drug.drug_seq` to identify which drug this indication belongs to.                                         |
| `indi_pt`       | MedDRA Preferred Term for the indication (i.e., what the drug was being used to treat, e.g.,`hypertension`, `type 2 diabetes mellitus`). |

---

## Common Join Patterns

```python
# Who is getting which reactions?
demo.merge(reac[["primaryid", "pt"]], on="primaryid")

# Which drugs are associated with which reactions?
drug.merge(reac, on="primaryid")

# Primary suspect drugs only, with reactions
suspects = drug[drug["role_cod"] == "PS"]
suspects.merge(reac, on="primaryid")

# Drug + what it was prescribed for
drug.merge(indi, left_on=["primaryid", "drug_seq"],
                 right_on=["primaryid", "indi_drug_seq"])

# Drug + therapy duration
drug.merge(ther, left_on=["primaryid", "drug_seq"],
                 right_on=["primaryid", "dsg_drug_seq"])

# Cases that resulted in death
fatal_ids = outc[outc["outc_cod"] == "DE"]["primaryid"]
demo[demo["primaryid"].isin(fatal_ids)]

# Deduplicate cases across quarters (keep latest version per caseid)
demo = demo.sort_values("caseversion").drop_duplicates("caseid", keep="last")
```

---

## Key Caveats

- **`drugname` is free text.** The same drug appears under hundreds of spellings. Use `prod_ai` for analysis or normalize against an external drug dictionary (RxNorm, DrugBank).
- **Dates are often partial.** `event_dt = "201803"` means March 2018 with no day. Parse carefully.
- **Duplicate cases across quarters.** The same adverse event can be re-submitted in a later quarter with a new `primaryid` but the same `caseid`. Always deduplicate on `caseid` + `caseversion` before counting cases.
- **FAERS is not a random sample.** Reporting is voluntary and biased toward serious events, new drugs, and drugs under scrutiny. Raw counts cannot be used as incidence rates without a denominator.
- **MedDRA hierarchy.** `pt` (Preferred Term) sits within Higher Level Terms (HLT), High Level Group Terms (HLGT), and System Organ Classes (SOC). For broader signal searches, group PTs into SOCs.

# BDA Trends Dashboard: QA Feedback & Questions

**Source:** Teammate review notes, April 19, 2026
**Scope:** Usability issues, layout change requests, bugs, and open questions across dashboard tabs

---

## Context for reader

This document is feedback from a reviewer walking through a pharmacovigilance dashboard ("BDA Trends"). The dashboard appears to surface FAERS-style adverse event data with drug role codes (PS = primary suspect, SS = secondary suspect, C = concomitant), MedDRA Preferred Terms (PT), and related regulatory/clinical context. Items below are mixed: some are bugs, some are layout requests, some are open design questions for discussion.

---

## 1. Side Panel (global filters)

### 1.1 Drug Role Filter
- **Bug:** Changing the Drug Role Filter does not update the `role_cod` field shown on the Default / Full View of the Drug Explorer tab. Filter selection and displayed role code are out of sync.

### 1.2 Display / layout
- **Bug:** Numeric values for "Deaths" and "Drugs" are being cut off (likely a column width or container sizing issue).

---

## 2. Drug Explorer Tab

### 2.1 Default / Full View

- **Remove:** "Reporter Type Distribution" can likely be removed from this view.
- **Suggestion:** Add a title to the `occr_country` table.
- **Layout:** Items currently hidden under the "Optional External Context" dropdown should be promoted to standalone tables. The information feels relevant enough that hiding it behind a dropdown is the wrong default.
  - Sub-item: **Recalls & Enforcement** can return reports dated outside the currently filtered quarter range. Either scope these to the active filter, or make it explicit that they are unscoped.
- **Question:** Can we list more than 5 Clinical Trials and Literature results? (Proposal: 10 items, or make the list scrollable.)

### 2.2 Provider View

#### 2.2.1 Ingredient (larger design discussion)
The Ingredient section is compiling information in a way that confuses end users. Concrete reproduction:

1. Enter **"Dupixent"** as the drug filter.
2. Result shows **"Dupilumab"** (correct, it's the active ingredient of Dupixent), **but also** shows active ingredients from other drugs that happen to appear on the same reaction report under role codes SS or C.
3. Apply **Drug Role = SS (secondary suspect)**: Dupixent now appears as SS, while other drugs appear as PS (primary suspect). This is inconsistent with step 2's framing.
4. Apply **Drug Role = PS**: no other drugs show up as SS.

The filter behavior across role codes is not symmetric and the table conflates "active ingredient of the queried drug" with "active ingredients of co-reported drugs." Needs a design conversation before implementation.

#### 2.2.2 Other Provider View items
- **Rename:** "Dose Distribution" → "Dose Amount".
- **Bug:** Filter button on the "Cases" table does not work.
- **Remove (conditional):** Can be removed if the Literature Reference is available on the other tab. *(Reviewer did not specify which element "this" refers to in the original; confirm target.)*
- **Reorder:** Move "Top Reactions" table to the top of the tab.
- **Bug:** The table at the bottom of the tab shows Event Dates outside the selected range. May be safe to remove this table entirely.

### 2.3 Manufacturer View

- **Bug (shared):** The Ingredient table has the same issues as the Ingredient section under Provider View (see 2.2.1).
- **Reorder:** Move "Case Reports by Quarter" to sit directly below "Top Manufacturers".
- **Reorder:** Move "Dosage Form Distribution" to sit directly below "Case Reports by Quarter".

### 2.4 Manufacturer Lookup

- **Reorder:** Move "Case Reports by Quarter" to sit directly below "Top Drugs".

---

## 3. Reaction Explorer

- **Question:** Can all associated PT (Preferred Term) values appear in the results, or is the current output restricted to terms with a match score of 100?
- **Example illustrating the concern:** Searching "dizziness" returns some PT terms that contain the full word "dizziness," but these are not scored 100 and do not appear in the calculation for Selected Terms. The reviewer wants to understand whether this is by design (strict scoring threshold) or a gap (partial matches dropped unintentionally).

---

## Summary by action type

**Bugs to fix**
- Drug Role Filter does not update `role_cod` on Drug Explorer Default View (1.1)
- Deaths / Drugs numbers truncated in side panel (1.2)
- Recalls & Enforcement shows out-of-range reports (2.1)
- Ingredient table logic across role codes (2.2.1, and same issue in 2.3)
- Cases filter button non-functional (2.2.2)
- Bottom table on Provider View shows out-of-range Event Dates (2.2.2)

**Layout / reorder**
- Promote items out of "Optional External Context" dropdown (2.1)
- Top Reactions → top of Provider View (2.2.2)
- Case Reports by Quarter → under Top Manufacturers on Manufacturer View (2.3)
- Dosage Form Distribution → under Case Reports by Quarter (2.3)
- Case Reports by Quarter → under Top Drugs on Manufacturer Lookup (2.4)

**Copy / labeling**
- Add title to `occr_country` table (2.1)
- Rename "Dose Distribution" → "Dose Amount" (2.2.2)

**Open questions for discussion**
- Expand Clinical Trials and Literature lists beyond 5? (2.1)
- Broader Ingredient table redesign (2.2.1)
- PT term scoring threshold in Reaction Explorer (3)

**Candidates for removal**
- Reporter Type Distribution on Drug Explorer Default (2.1)
- Bottom out-of-range table on Provider View (2.2.2)
- Literature Reference duplicate (pending confirmation) (2.2.2)

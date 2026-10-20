# GitHub Issues — Thesis Remaining Work

These are the open issues to track before thesis submission.
Copy each block into a GitHub issue or use as a checklist.

---

## Issue #1 — Write Methodology Chapter
**Label:** `thesis-writing` `high-priority`

**Description:**
Write `bachelor_thesis/chapters/methodology.tex` covering the full 4-stage pipeline.

**Must cover:**
- [ ] Research design: observational, repository-mining study
- [ ] Corpus construction criteria (Stage 1): date window, star/commit/fork/size filters, language detection
- [ ] Ecosystem classification: lockfile-based package manager detection
- [ ] Owner location inference (Stage 2): two-pass design, 7 signals, Wilson CI, limitations of 56.1% unresolved
- [ ] AI detection pipeline (Stage 3): tiered signal hierarchy (STRONG/MEDIUM/WEAK), all 4 passes, classify() rule
- [ ] Detection signals catalogue: all signal families with examples
- [ ] Reclassification pass (Stage 3d): two-phase design, why Phase 1 upgrades all Pass 2 ai_assisted
- [ ] Geographic analysis (Stage 4): country join, MIN_REPOS=30 threshold
- [ ] Statistical methods: Wilson CI, one-sample binomial, McNemar, chi-squared, Fisher exact, Benjamini-Hochberg FDR
- [ ] Validity threats: unlocated owners bias, template copying, config file abandonment, corpus filters

---

## Issue #2 — Write Introduction Chapter
**Label:** `thesis-writing` `high-priority`

**Description:**
Write `bachelor_thesis/chapters/intro.tex`.

**Must cover:**
- [ ] Motivation: why AI coding agents matter in 2025–2026
- [ ] Problem statement: we don't know adoption rates in JS/TS/npm specifically, or how geography shapes adoption
- [ ] Research questions (RQ1, RQ2, RQ3) — stated formally
- [ ] Scope: JS/TS/npm ecosystem, GitHub, Feb 2025–Oct 2026
- [ ] Contributions: 60k-repo corpus, multi-signal pipeline, country ranking of 65 countries
- [ ] Thesis structure overview (one paragraph)

---

## Issue #3 — Write Discussion Chapter
**Label:** `thesis-writing` `high-priority`

**Description:**
Write `bachelor_thesis/chapters/discussion.tex` interpreting the results against the literature.

**Must cover:**
- [ ] RQ1 interpretation: 73% vs Robbes et al. 71–76% for new repos — why they converge
- [ ] RQ2 interpretation: 31.41 pp gap — what it means for prior work that used single-signal
- [ ] RQ3 interpretation: high-income vs low-income divide — link to Wachs et al. GDP finding and Daniotti et al. Python results
- [ ] Claude Code dominance (44.7%): why terminal-first CLI fits npm toolchain
- [ ] TypeScript vs JavaScript gap (77.1% vs 60.5%): typed code + AI performance
- [ ] Size stratum pattern (91.7% large): two hypotheses — activity exposure vs serious developer profile
- [ ] Limitations: 56.1% unlocated, repo ≠ developer, quality filters, template copying noise
- [ ] Implications for practitioners and future tooling

---

## Issue #4 — Write Conclusion Chapter
**Label:** `thesis-writing` `medium-priority`

**Description:**
Write `bachelor_thesis/chapters/conclusion.tex`.

**Must cover:**
- [ ] Summary of findings (one paragraph per RQ)
- [ ] Main contribution stated concisely
- [ ] Limitations in one paragraph
- [ ] Future work: temporal analysis (when was AI first adopted?), developer-level analysis, other ecosystems (Python, Rust), causal modelling

---

## Issue #5 — Verify Literature Review with Supervisor
**Label:** `review` `high-priority`

**Description:**
Present `bachelor_thesis/chapters/litrev.tex` to supervisor for feedback.

**Checklist:**
- [ ] Confirm all 30 papers have: who, did what, approach, results, pros, cons, counter-argument
- [ ] Confirm section structure (6 thematic sections) matches thesis scope
- [ ] Confirm research gaps section (Gap 1, Gap 2, Gap 3) is correctly framed
- [ ] Apply any feedback from supervisor

---

## Issue #6 — Verify Results Summary with Supervisor
**Label:** `review` `high-priority`

**Description:**
Present `bachelor_thesis/results_summary.tex` (2-page PDF) to supervisor.

**Checklist:**
- [ ] Compile PDF: `pdflatex bachelor_thesis/results_summary.tex`
- [ ] Confirm RQ formulations match supervisor expectations
- [ ] Confirm statistical tests used are appropriate
- [ ] Confirm country ranking methodology is acceptable
- [ ] Apply any feedback

---

## Issue #7 — Write Abstract
**Label:** `thesis-writing` `medium-priority`

**Description:**
Write a 250-word abstract for the thesis covering:
- [ ] Context (JS/TS/npm ecosystem, agentic era)
- [ ] Objective (measure adoption rates + geographic variation)
- [ ] Method (60k-repo corpus, 4-pass multi-signal pipeline)
- [ ] Key results (73.0%, +31.41 pp undercounting, Belgium 89.9% – Rwanda 22.4%)
- [ ] Conclusion (majority practice, geography significant, multi-signal necessary)

---

## Issue #8 — Final Thesis Compilation and Formatting
**Label:** `technical` `medium-priority`

**Description:**
Final check before submission.

**Checklist:**
- [ ] All chapters compile without LaTeX errors
- [ ] All `\ref{}` and `\cite{}` resolve correctly
- [ ] All tables fit within page margins
- [ ] All `[pending]` markers removed
- [ ] Bibliography (`references.bib`) has all 30 papers with correct keys
- [ ] Page count within submission limits
- [ ] Front matter complete (title page, abstract, table of contents)
- [ ] Check figure/table numbering is sequential

---

## Issue #9 — Validate Detection Pipeline on Known Repos
**Label:** `validation` `low-priority`

**Description:**
Manually spot-check 10–15 repos from the corpus across different adoption labels
to verify the detection pipeline is classifying correctly.

**Checklist:**
- [ ] Pick 5 repos labelled `agentic` — confirm signal is real
- [ ] Pick 5 repos labelled `ai_assisted` — confirm borderline signal
- [ ] Pick 5 repos labelled `none` — confirm no AI evidence
- [ ] Document any misclassifications found

---

## Issue #10 — Archive Supplementary Scripts
**Label:** `technical` `low-priority`

**Description:**
The `scripts/supplementary/` folder contains Stage 5/6 scripts written for the
old Egyptian corpus methodology. They are no longer part of the main pipeline.

**Checklist:**
- [ ] Confirm none of the supplementary scripts are referenced in the thesis methodology
- [ ] Add a `README.md` inside `scripts/supplementary/` explaining they are archived
- [ ] Confirm `scripts/stage4/stage4a/b/c` cover all analyses needed

---

## Summary Table

| # | Issue | Priority | Status |
|---|-------|----------|--------|
| 1 | Write Methodology chapter | High | ⏳ Pending |
| 2 | Write Introduction chapter | High | ⏳ Pending |
| 3 | Write Discussion chapter | High | ⏳ Pending |
| 4 | Write Conclusion chapter | Medium | ⏳ Pending |
| 5 | Verify litrev with supervisor | High | ⏳ Pending |
| 6 | Verify results summary with supervisor | High | ⏳ Pending |
| 7 | Write Abstract | Medium | ⏳ Pending |
| 8 | Final compilation + formatting | Medium | ⏳ Pending |
| 9 | Validate detection on known repos | Low | ⏳ Pending |
| 10 | Archive supplementary scripts | Low | ⏳ Pending |

# Thesis Observations & Draft Notes
**Topic 2 — JavaScript / TypeScript / npm**  
**Student:** Manuel Youssef Haik Kevorkian  

This file collects observations, findings, and draft passages worth considering for the thesis. Entries are added as they arise during data collection and analysis.

---

## OBS-001 — Egyptian Developer Repos Are Overwhelmingly Small-Scale
**Stage:** 2c output  
**Date added:** 2026-09-26  

The Egypt corpus (Stage 2c) produced 72,946 JS/TS repositories from 21,223 Egyptian developer accounts. The stratum breakdown was strikingly skewed:

- **Small (0–50 stars): 72,835 repos (99.8%)**
- Medium (51–500 stars): 88 repos (0.1%)
- Large (>500 stars): 23 repos (0.03%)

This contrasts sharply with the base corpus (Stage 1), which used star-band queries to ensure balanced coverage across strata. The finding suggests that Egyptian JS/TS developers predominantly work on personal, academic, or local-scale projects rather than widely-adopted open source software. This has implications for RQ2: if the Egypt corpus is almost entirely small repos, and agent adoption rates differ by stratum, the Egyptian sub-sample may not be directly comparable to the global sample on a stratum-by-stratum basis. This should be acknowledged in the methodology and discussed in the results section.

**Draft thesis sentence:** *"The Egyptian developer sub-corpus exhibited a pronounced skew toward low-visibility repositories (99.8% with ≤50 stars), reflecting the predominance of personal and academic projects among Egyptian GitHub contributors, and suggesting that direct stratum-level comparison with the globally-sampled base corpus requires careful interpretation."*

---

## OBS-002 — Snowball Expansion Showed No Early Convergence
**Stage:** 2b output  
**Date added:** 2026-09-26  

The snowball expansion ran all 3 rounds without converging early:
- Round 1: 5,267 new accounts
- Round 2: 8,653 new accounts  
- Round 3: 5,427 new accounts

Round 2 actually discovered *more* accounts than Round 1, which is unusual — typically snowball expansion decelerates as the network saturates. The acceleration in Round 2 suggests the Egyptian developer network on GitHub has a densely connected core that was not fully reachable from the initial seeds. The fact that Round 3 still added 5,427 accounts (63% of Round 1's yield) indicates the network was not yet exhausted at the 3-round limit. This is worth noting as a limitation: a 4th round may have discovered additional accounts.

**Draft thesis sentence:** *"The snowball expansion did not converge within the three-round limit, with rounds 1–3 yielding 5,267, 8,653, and 5,427 new accounts respectively. The acceleration in round 2 suggests a densely connected sub-network not reachable from the initial seed set, and the non-zero yield in round 3 indicates that additional rounds could expand the corpus further — a known boundary of the current methodology."*

---

## OBS-003 — Arabic Location Terms Are Essential for Egyptian Developer Discovery
**Stage:** 2a design  
**Date added:** 2026-09-26  

During the exploratory phase, it was noted that a significant portion of Egyptian developers on GitHub use Arabic-script location strings (`مصر`, `القاهرة`, `الإسكندرية`, `الجيزة`) rather than English equivalents. Studies that use only English location terms will systematically undercount Egyptian developers. This is a methodological contribution worth highlighting — it is not standard practice in GitHub mining studies and directly improves the recall of the Egyptian developer identification pipeline.

**Draft thesis sentence:** *"Unlike prior GitHub mining studies that rely exclusively on English location strings, this study incorporates Arabic-script equivalents for all Egyptian city names. Omitting Arabic terms would exclude a non-trivial portion of the Egyptian developer population whose GitHub profiles are written in Arabic."*

---

## OBS-004 — Stars Are a Visibility Proxy, Not a Size Proxy
**Stage:** Methodology design  
**Date added:** 2026-09-26  

The thesis uses star count for size stratification (small/medium/large), following the convention established in the reference papers. However, stars measure community visibility and social endorsement, not actual project size. A single-file npm utility can accumulate thousands of stars; a large enterprise codebase may have zero. The strata are better described as "low-visibility", "medium-visibility", and "high-visibility" projects. This distinction matters when interpreting results: if adoption rates differ across strata, the explanation may be social (visible projects face more community pressure to adopt popular tools) rather than structural (large codebases need more automation).

**Draft thesis sentence:** *"Although the strata are labelled small, medium, and large for consistency with prior work, star count is more precisely a measure of project visibility than project size. Differences in adoption rates across strata should therefore be interpreted in terms of community exposure rather than codebase complexity."*

---

## OBS-005 — Near-Zero Overlap Between Global and Egyptian Corpora
**Stage:** 3 output  
**Date added:** 2026-09-26  

After merging the base corpus (4,372 repos from Stage 1 global search) with the Egypt corpus (72,946 repos from Stage 2c), only **3 repos appeared in both**. This means Egyptian JS/TS developers are working on an almost entirely separate set of repositories from the globally-popular JS/TS repos that the star-sorted search discovers.

This is a substantive finding: Egyptian developers are not the primary contributors to high-visibility open source JS/TS projects. Their GitHub activity lives in a different part of the ecosystem — personal projects, course assignments, work-internal tools, and small-scale utilities that do not accumulate stars globally.

For the thesis this means:
- The `corpus_source = "both"` category has only 3 repos and cannot support any statistical comparison on its own — acknowledge this explicitly.
- The Egypt vs global comparison in RQ2 is essentially comparing two non-overlapping populations, which strengthens the validity of the comparison (no double-counting) but also means any difference found reflects genuine population-level differences, not sampling noise.

**Draft thesis sentence:** *"Of the 77,315 unique repositories in the unified corpus, only 3 appeared in both the globally-sampled base corpus and the Egyptian developer sub-corpus, confirming that Egyptian GitHub developers operate in a largely distinct segment of the JS/TS ecosystem — one characterised by low-visibility personal and small-scale projects rather than widely-adopted open source libraries."*

---

## OBS-006 — Unified Corpus Size and Language Distribution
**Stage:** 3 output  
**Date added:** 2026-09-26  

The unified corpus contains **77,315 unique repositories**: 4,369 base-only, 72,943 Egypt-only, and 3 in both. Language breakdown: JavaScript 46,973 (60.8%), TypeScript 30,342 (39.2%). The JavaScript dominance is consistent with npm ecosystem data where JavaScript remains the majority language despite TypeScript's growth. The 60/40 split provides sufficient coverage of both languages to enable language-level subgroup analysis in Stage 7 if needed.

Stratum breakdown of the unified corpus: small 74,162 (95.9%), medium 1,522 (2.0%), large 1,631 (2.1%). The small-stratum dominance is driven entirely by the Egypt corpus. The base corpus alone has a more balanced distribution across strata — this should be reported separately in the thesis rather than only showing the unified totals, which are dominated by the Egypt corpus's skew.

**Draft thesis sentence:** *"The unified corpus comprised 77,315 repositories (JavaScript: 60.8%, TypeScript: 39.2%). Stratum coverage was balanced in the globally-sampled base corpus but heavily skewed toward low-visibility projects in the Egyptian sub-corpus, reflecting structural differences between the two sampling strategies."*

---


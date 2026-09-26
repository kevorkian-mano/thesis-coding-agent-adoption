# Thesis Observations & Draft Notes
**Topic 2 — JavaScript / TypeScript / npm**  
**Student:** Manuel Youssef Haik Kevorkian  

This file collects observations, findings, and draft passages worth considering for the thesis. Entries are added as they arise during data collection and analysis.

---

## OBS-008 — SEART GHS as a Potential Enrichment Source
**Stage:** Post Stage 3 / pre Stage 4  
**Date added:** 2026-09-26  

SEART GHS (https://seart-ghs.si.usi.ch/) is a GitHub repository search tool maintained by USI that provides pre-computed repository metadata including commit count and contributor count — the two fields skipped in the Stage 1 GraphQL pipeline for performance reasons.

**Potential use:** Cross-reference `unified_corpus.csv` against a SEART export filtered to JavaScript/TypeScript to fill in `total_commits` and `contributor_count` for base-corpus repos. This would strengthen the methodology by restoring the I-4 and I-5 checks that were approximated or skipped.

**Limitations of SEART for this study:** No `package.json` presence check, no language byte-share data, snapshot date not fully controllable, and it cannot support the Egyptian developer corpus (no location/user filtering).

**Decision:** Not used for corpus construction (Stage 1 already complete). Worth considering for metadata enrichment before Stage 5 metrics computation if commit count is needed as a covariate.

---

## OBS-009 — The Study Targets Egyptian Developers, Not Egyptian-Themed Repos
**Stage:** Methodology design  
**Date added:** 2026-09-26  

A critical distinction that must be stated explicitly in the thesis: the Egyptian sub-corpus is built around **developer nationality**, not **repository subject matter**. The unit of analysis is the person, not the topic of their work.

This means:
- A repo named `react-todo-app` owned by an Egyptian developer → **included**
- A repo named `egypt-tourism-api` owned by a German developer → **excluded**

This is directly supported by RQ2 in the methodology: *"How does coding agent adoption among **Egyptian JavaScript/TypeScript developers** compare to the general JS/TS GitHub population?"* — the comparison is between developer communities, not between repos about different countries.

The practical implication is that keyword-based repo search (e.g. searching for "egypt" in repo names on SEART or GitHub) would be the wrong approach — it would find repos *about* Egypt regardless of developer origin, producing a fundamentally different and incorrect population.

The people-first pipeline (Stage 2a location search → Stage 2b snowball expansion → Stage 2c repo pull) is the correct operationalisation of this research question because it identifies Egyptian developers first, then collects their work.

**Draft thesis sentence:** *"The unit of analysis in the Egyptian sub-corpus is the developer, not the repository subject matter. A repository is included in the Egyptian sub-corpus if and only if its owner is identified as an Egyptian developer through location self-reporting or social network proximity — regardless of the repository's topic, name, or content. This people-first sampling strategy directly operationalises RQ2, which compares developer communities rather than repository topics."*

---

## OBS-007 — Location-Based Sampling Cannot Capture All Egyptian Developers
**Stage:** Methodology design  
**Date added:** 2026-09-26  

GitHub's location field is optional and free-text. A meaningful portion of Egyptian developers either leave it blank or use formats not matched by the search terms (e.g. "EG", "Arab Republic of Egypt", city names without country). This creates a systematic under-coverage problem for any location-based sampling approach.

**What the current pipeline does to address this:**
The two-layer approach partially compensates. Stage 2a captures developers who explicitly self-report an Egyptian location (1,876 seeds). Stage 2b then expands through follower/following social networks for 3 rounds, discovering 19,347 additional accounts regardless of whether those accounts have a location set. Any Egyptian developer socially connected to a location-tagged Egyptian developer is captured even with a blank location field.

**What remains uncaptured:**
Developers who are Egyptian but have (a) no location set, (b) no social connection to any of the 21,223 discovered accounts, and (c) no other discoverable signal. This is a genuinely hard-to-reach population that no passive API-based approach can fully recover without, for example, scraping commit email domains for `.eg` TLDs or cross-referencing with Egyptian university alumni databases — both out of scope for this study.

**Additional signals that could partially extend coverage (future work):**
- Arabic script in `bio` field (Unicode range `\u0600–\u06FF`)
- Egyptian institution names in `company` or `bio` (Cairo University, AUC, GUC, Ain Shams, etc.)
- `.eg` TLD in public email or company domain
- None of these require re-running the current pipeline — they would extend Stage 2a's seed discovery in a future iteration

**Correct scoping for the thesis:**
The study population is "Egyptian JS/TS developers discoverable on GitHub through location self-reporting or social network proximity to location-tagged Egyptian developers." This is a defensible and clearly bounded population — not all Egyptian developers on GitHub, but a well-defined and reproducible subset.

**Draft thesis sentence:** *"The Egyptian developer identification pipeline operates on two complementary signals: explicit location self-reporting (Stage 2a) and social network proximity to confirmed Egyptian accounts (Stage 2b snowball expansion). Developers who neither set an Egyptian location nor maintain social connections to discovered accounts fall outside the study's sampling frame — a known limitation shared by all geography-based GitHub mining studies."*

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

## OBS-010 — Gathered Literature Validates and Directly Shapes the Detection Methodology
**Stage:** Stage 4 design / literature review
**Date added:** 2026-09-26

A review of all 17 gathered papers confirms that none require changes to Stages 1–3 (corpus construction, Egyptian developer discovery, or merge). All papers address detection methodology, code quality after adoption, or contextual ecosystem findings — areas that are either already handled or will be handled in Stages 4–7.

The two papers with the most direct impact on `stage4_detection.py` are:

- **Khosravani & Mockus (Paper 9)** — their 4-Type taxonomy (Bot accounts / Commit trailers / Author name suffixes / Config files) is the exact architecture of Stage 4's Pass 1 (config file check) and Pass 2 (commit + PR scan). Crucially, they prove that single-signal bot lookups miss **up to 30×** of actual Claude Code commits. This is the entire justification for the `agent_adopted_single` vs `agent_adopted_multi` split in the output schema, and for the RQ1 sub-question about the undercounting gap.

- **Robbes et al. — Heuristics (Paper 16)** — their empirical catalog of agent traces documented 2.7 million commits with `noreply@anthropic.com` as the author email, and 2.1 million branches with the `codex/` prefix. The `codex/` branch pattern was already in `stage4_detection.py`. The `noreply@anthropic.com` email check was missing and has been added as a new `author_email` signal type.

**Signal types in `stage4_detection.py` after update:**

| Signal type | Source paper(s) | Notes |
|---|---|---|
| `config_file` | Galster et al. (Papers 1, 8), Chatlatanagulchai (Paper 3) | CLAUDE.md, .cursorrules, etc. — Pass 1 only |
| `commit_trailer` | Robbes et al. (Papers 4, 5), Khosravani (Paper 9) | Co-authored-by: patterns — single-signal baseline |
| `bot_author` | Khosravani (Paper 9) Type A | GitHub bot account logins |
| `author_email` | Robbes et al. (Paper 16) | noreply@anthropic.com — **added in this session** |
| `pr_body` | Robbes et al. (Paper 16) | Generated with Claude Code marker |
| `pr_branch` | Robbes et al. (Paper 16) | codex/, copilot/, cursor/ prefixes |
| `pr_label` | Robbes et al. (Paper 16) | copilot, codex labels |
| `npm_dependency` | Topic 2 specific | @anthropic-ai/sdk, openai, etc. |

**Papers for Results/Discussion (no script impact):**
Papers 2, 6, 7, 10, 12, 13, 14, 15, 17 all belong in Chapters 3–4 and provide benchmarks to compare against: adoption rates (22.20%–28.66% from Paper 4/5), PR acceptance rates (83.8% agentic vs 91.0% human from Paper 15), revert rates (Copilot 7.6%, Claude Code 7.2% vs human 4.7% from Paper 17), and code survival statistics (Paper 14). None touch the data collection pipeline.

**Draft thesis sentence:** *"The detection taxonomy implemented in Stage 4 directly operationalises the multi-method framework validated by Khosravani and Mockus (2026), whose census of 180 million repositories demonstrated that single-signal bot detection undercounts Claude Code commits by a factor of up to 30. The four signal types — config file presence, commit trailers, bot account authorship, and author email matching — correspond to their Type D, Type B, Type A, and Type B/C categories respectively, extended with a fifth npm-dependency signal specific to the JavaScript/TypeScript ecosystem."*

---

## OBS-011 — Three Additional Papers Added to Fill Methodology Gaps
**Stage:** Literature review expansion
**Date added:** 2026-09-26

After mapping the original 17 papers to specific thesis claims, three targeted gaps were identified and filled (total now 20 papers):

- **Paper 18 — Dabić et al. (2021), "Sampling Projects in GitHub for MSR Studies" (MSR '21 Data Showcase):** The foundational sampling methodology paper behind the SEART GHS tool. Robbes et al. (Papers 4 & 5) explicitly cite this as their sampling infrastructure. Without this citation, the Stage 1 corpus construction methodology floats — it uses a well-established approach that exists in the literature but was uncited. Cite in Chapter 2 when introducing Stage 1: *"Following Dabić et al. (2021), repositories were sampled using the GitHub Search API filtered by language, push recency, and fork status."*

- **Paper 19 — Wachs et al. (2022), "The Geography of Open Source Software: Evidence from GitHub" (Technological Forecasting and Social Change, Vol. 176):** The closest prior work to the Stage 2 Egyptian developer identification pipeline. Establishes that GitHub profile location self-reporting is a valid (if noisy) basis for geographic developer attribution, and documents the systematic undercounting of blank-location developers — the exact limitation the snowball expansion addresses. Positions the thesis methodology as extending rather than inventing from scratch. Cite in Chapter 2 when introducing Stage 2.

- **Paper 20 — GitHub Octoverse 2025 (industry report, GitHub Blog):** Documents TypeScript overtaking Python and JavaScript as the #1 language on GitHub in August 2025, with 2,636,006 monthly contributors (+66.6% YoY). The report explicitly attributes this rise to AI coding agent adoption and TypeScript's compatibility with AI tools. One citation, one sentence in Chapter 1 Background to justify the ecosystem choice. Non-academic source but the official GitHub measurement — acceptable for factual ecosystem statistics.

**Decision:** Stop at 20. Adding more papers beyond this would require supervisor direction. The current set provides: core detection methodology (6), configuration & ecosystem (4), PR dynamics (5), specialized (3), infrastructure & context (3) — complete coverage of all thesis chapters.

---


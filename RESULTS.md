# Results
## Coding Agent Adoption in JavaScript/TypeScript/npm Repositories on GitHub

**Student:** Manuel Youssef Haik Kevorkian
**Date:** October 2026
**Status:** Stage 5 complete — based on corrected Egyptian corpus (created ≥ 2025-02-24)

---

## Overview

| Corpus | Repos | Multi-signal Adoption | Single-signal Adoption | Delta |
|---|---|---|---|---|
| Global (random sample) | 4,500 | **67.5%** | 48.1% | 19.5 pp |
| Egyptian v2 — corrected (created ≥ 2025-02-24) | 83 | **41.0%** | 25.3% | 15.7 pp |
| Egyptian v1 — old (pushed ≥ 2025-01-01) | 136 | 17.6% | 11.8% | 5.9 pp |
| **Gap v2 vs global (RQ3 — valid)** | — | **−26.5 pp** | −22.8 pp | — |
| Gap v1 vs global (invalid — pre-AI repos included) | — | −49.9 pp | −36.3 pp | — |

**All analysis uses the corrected corpus (v2).** The old corpus (v1) is documented here as a methodological finding. See Section 3.0 for the full explanation.

---

## 1. RQ1 — Scope of Adoption

### 1.1 Adoption by Ecosystem (Global)

| Ecosystem | Repos | Multi-signal % | Single-signal % | Agentic % |
|---|---|---|---|---|
| pnpm | 909 | **74.5%** | 51.5% | 70.4% |
| npm_no_lock | 656 | 73.0% | 49.5% | 68.9% |
| npm | 1,891 | 70.0% | 50.8% | 63.6% |
| yarn | 194 | 61.3% | 44.8% | 56.2% |
| bun | 61 | 59.0% | 39.3% | 57.4% |
| vanilla | 789 | **51.2%** | 37.9% | 44.4% |

**Key finding:** pnpm developers have the highest adoption (74.5%). pnpm is a modern, performance-focused package manager — developers who chose it are already toolchain-aware and likely to adopt new tools early. Vanilla repos have the lowest adoption (51.2%), yet 51% is still remarkably high, showing AI tools have reached even casual JS/TS developers.

**npm_no_lock (73%):** Repos with package.json but no lockfile tend to be newer and more experimental. These developers may be less concerned with conventions and more open to new tooling.

### 1.2 Adoption by Language (Global + Egyptian)

| Language | Corpus | Repos | Multi-signal % | Single-signal % | Agentic % |
|---|---|---|---|---|---|
| TypeScript | Global | 3,217 | **71.4%** | 50.6% | 66.3% |
| JavaScript | Global | 1,283 | 57.9% | 41.7% | 51.1% |
| TypeScript | Egyptian | 63 | **46.0%** | 28.6% | 39.7% |
| JavaScript | Egyptian | 20 | **25.0%** | 15.0% | 20.0% |

**Key finding:** TypeScript developers adopt AI significantly more than JavaScript developers in both corpora. Globally the gap is 13.5 pp (71.4% vs 57.9%). In Egypt the gap is 21.0 pp (46.0% vs 25.0%). TypeScript's strict typing helps AI tools generate more accurate code — developers notice better results and continue using the tool.

**Egyptian JavaScript (25.0%)** is notably lower than Egyptian TypeScript (46.0%), consistent with the global language pattern but at a lower baseline across both languages.

### 1.3 Adoption by Size Stratum (Global + Egyptian)

| Size | Corpus | Repos | Multi-signal % | Single-signal % | Agentic % |
|---|---|---|---|---|---|
| Large (>500 stars) | Global | 391 | **85.7%** | 68.5% | 78.3% |
| Medium (51–500) | Global | 789 | 75.0% | 52.0% | 68.2% |
| Small (≤50 stars) | Global | 3,320 | 63.6% | 44.7% | 58.6% |
| Large (>500 stars) | Egyptian | 3 | 66.7% | 66.7% | 33.3% |
| Medium (51–500) | Egyptian | 7 | 85.7% | 28.6% | 71.4% |
| Small (≤50 stars) | Egyptian | 73 | **35.6%** | 23.3% | 31.5% |

**Key finding:** Globally, larger repositories adopt AI more (85.7% large vs 63.6% small). In Egypt, the small repo group (n=73) is the only statistically meaningful size group. At 35.6%, Egyptian small repos are well below the global small repo rate (63.6%).

*Note: Egyptian large (n=3) and medium (n=7) groups are too small for reliable conclusions.*

### 1.4 Cross-tabulation: Ecosystem × Language (Global)

Multi-signal adoption rate (%) by ecosystem and primary language:

| Ecosystem | JavaScript % | TypeScript % | Total repos |
|---|---|---|---|
| pnpm | 69.2% | **75.3%** | 909 |
| npm | 66.2% | 71.5% | 1,891 |
| npm_no_lock | 61.0% | **78.3%** | 656 |
| bun | 57.1% | 59.3% | 61 |
| yarn | 49.0% | 65.7% | 194 |
| vanilla | 43.0% | 59.1% | 789 |

**Key finding:** TypeScript outperforms JavaScript in every ecosystem without exception. The highest combination is **npm_no_lock + TypeScript (78.3%)**. The lowest is **vanilla + JavaScript (43.0%)**.

---

## 2. RQ2 — Signal Undercounting

### 2.1 Undercounting Delta

| Corpus | Single-signal % | Multi-signal % | Delta |
|---|---|---|---|
| Global | 48.1% | 67.5% | **+19.5 pp** |
| Egyptian | 25.3% | 41.0% | **+15.7 pp** |

**Key finding:** Globally, 19.5 percentage points of adopters would be completely invisible if only commit trailers were checked. The Egyptian delta (15.7 pp) is now close to the global delta, which is consistent with both corpora covering the same time window. Egyptian developers who use AI tools rely on a similar mix of signal types as global developers.

### 2.2 Signal Type Breakdown (Global)

| Signal type | Instances | % of total |
|---|---|---|
| Commit trailers | 121,148 | 89.0% |
| PR branch patterns | 11,896 | 8.7% |
| Author email | 5,947 | 4.4% |
| Config files | 3,030 | 2.2% |
| PR labels | 1,193 | 0.9% |
| PR body patterns | 647 | 0.5% |
| Bot author | 291 | 0.2% |
| npm dependencies | 190 | 0.1% |

### 2.3 Agent Breakdown (Global)

| Agent | Repos | % of all repos |
|---|---|---|
| Claude Code | 2,852 | **63.4%** |
| OpenAI | 909 | 20.2% |
| Copilot | 633 | 14.1% |
| Cursor | 605 | 13.4% |
| Gemini | 68 | 1.5% |
| Devin | 54 | 1.2% |
| Cline | 16 | 0.4% |
| Windsurf | 10 | 0.2% |

**Claude Code dominance:** Claude Code appears in 63.4% of all repos. Its terminal-first CLI design fits naturally with the npm developer workflow, and it adds a commit trailer by default that most developers do not disable. This likely overstates its true market share relative to Cursor and Copilot, which leave fewer automatic traces.

---

## 3. RQ3 — Egyptian vs Global Comparison

### 3.0 Corpus Version Comparison (Finding)

Two versions of the Egyptian corpus were built during this study. The table below compares them side by side.

| Metric | Version 1 (old) | Version 2 (corrected) |
|---|---|---|
| Creation date filter | pushed ≥ 2025-01-01 | **created ≥ 2025-02-24** |
| Corpus size | 136 repos | **83 repos** |
| Multi-signal adoption | 17.6% (24/136) | **41.0% (34/83)** |
| Single-signal adoption | 11.8% (16/136) | 25.3% (21/83) |
| Undercounting delta | 5.9 pp | 15.7 pp |
| Gap vs global (67.5%) | −49.9 pp | **−26.5 pp** |

#### Version 1 — Old Egyptian Corpus (136 repos, pushed ≥ 2025-01-01)

The first corpus was built using a last-push date filter. A repository created in 2019 and simply pushed to in 2025 would pass this filter despite predating AI coding tools entirely. Stage 4 was run on this corpus and produced the following results:

**Overall:** 17.6% multi-signal adoption, 11.8% single-signal adoption, 5.9 pp undercounting delta.

The 5.9 pp undercounting delta in Version 1 (vs 15.7 pp in Version 2) is itself a side effect of the bad filter. Older repos generate fewer signals of any kind, compressing both the single and multi numbers toward zero, so the gap between them shrinks too.

**Gap vs global:** −49.9 pp (Egyptian 17.6% vs global 67.5%).

#### Version 2 — Corrected Egyptian Corpus (83 repos, created ≥ 2025-02-24)

After identifying the filter inconsistency, the corpus was rebuilt requiring `created ≥ 2025-02-24` — the same condition as the global corpus. All final analysis and all results elsewhere in this document use Version 2.

#### Why the adoption rate jumped from 17.6% to 41.0%

The jump is not real adoption growth — it is the removal of pre-AI-era repos. Version 1 included repos created as far back as 2018–2024 that were simply pushed to recently. Those older repos were built before AI coding agents existed, so naturally very few show AI adoption signals. Version 2 contains only repos started on or after 2025-02-24, matching the global corpus exactly.

**This comparison is itself a finding.** A researcher using the Version 1 approach would have reported a 50 pp gap between Egypt and the global average. The correct gap after fixing the filter is 26.5 pp — still large and meaningful, but not nearly as extreme. This illustrates why creation date filtering is essential when comparing adoption across corpora, and why methodology transparency matters in empirical software engineering research.

### 3.1 Headline Comparison (Corrected Corpus)

| Metric | Global (n=4,500) | Egyptian (n=83) | Gap |
|---|---|---|---|
| Multi-signal adoption | 67.5% | 41.0% | **−26.5 pp** |
| Single-signal adoption | 48.1% | 25.3% | −22.8 pp |
| Agentic level | 61.9% | 34.9% | **−27.0 pp** |
| AI-assisted level | 5.6% | 6.0% | +0.4 pp |
| None | 32.4% | 59.0% | +26.6 pp |
| Undercounting delta | 19.5 pp | 15.7 pp | — |

Egyptian JS/TS developers adopt AI coding agents at a notably lower rate than the global average. The gap of 26.5 pp will be formally tested using Fisher's exact test in the final statistical analysis.

### 3.2 Adoption by Language — Egyptian

| Language | Egyptian repos | Multi-signal % | Agentic % |
|---|---|---|---|
| TypeScript | 63 | **46.0%** | 39.7% |
| JavaScript | 20 | 25.0% | 20.0% |

The language gap within Egypt (21.0 pp) is slightly larger than the global language gap (13.5 pp).

### 3.3 Agent Breakdown — Egyptian vs Global

| Agent | Global repos % | Egyptian repos % | Difference |
|---|---|---|---|
| Claude Code | 63.4% | **63.9%** | +0.5 pp |
| Copilot | 14.1% | **24.1%** | +10.0 pp |
| Cursor | 13.4% | 15.7% | +2.3 pp |
| OpenAI | 20.2% | 10.8% | −9.4 pp |

**Key finding:** Among Egyptian adopters, the tool distribution is notably different from the global picture. Claude Code maintains a similar share (63.9% vs 63.4%), but Copilot is proportionally much stronger in Egypt (24.1% vs 14.1% globally, +10 pp). OpenAI is weaker in Egypt (10.8% vs 20.2% globally, −9.4 pp). Copilot's stronger relative showing in Egypt may be explained by GitHub Education's free Copilot access for verified students, which reduces the cost barrier. This is a hypothesis and cannot be confirmed from repository data alone.

### 3.4 Tool Loyalty — Egyptian vs Global

| | Global adopters | Egyptian adopters |
|---|---|---|
| Only Claude Code | 47.5% | **45.9%** |
| Any single tool | 63.1% | **73.0%** |
| Multiple tools | 36.9% | **27.0%** |

Egyptian adopters are more likely to stick to a single tool (73.0% vs 63.1%). Those who do adopt in Egypt tend to be single-tool users rather than developers who experiment with multiple AI tools simultaneously.

---

## 4. Temporal Analysis

### 4.1 Time from Repo Creation to First AI Signal

| Metric | Global | Egyptian |
|---|---|---|
| Repos with timing data | 2,529 | 24 |
| Median days to first signal | **20 days** | **30 days** |
| Mean days to first signal | 78 days | 63 days |
| Within 7 days | 1,011 (40.0%) | 10 (41.7%) |
| Within 30 days | 1,418 (56.1%) | 12 (50.0%) |
| Within 90 days | 1,807 (71.5%) | 16 (66.7%) |

**Key finding:** The median global adopter adds their first AI signal just 20 days after creating the repo. Egyptian adopters take slightly longer (30 days median) but the within-7-days rate is nearly identical (41.7% vs 40.0%). The "born agentic" behaviour — starting with AI from the very beginning — is present in both communities at similar rates.

### 4.2 Adoption Timing Breakdown

| Timing | Global | Egyptian |
|---|---|---|
| Within 1 week | 33.3% | 29.4% |
| Within 1 month | 13.4% | 5.9% |
| 1–3 months | 12.8% | 11.8% |
| 3–6 months | 9.6% | 11.8% |
| 6+ months | 14.2% | 11.8% |
| Unknown | 16.8% | 29.4% |

One third of global adopters were born agentic (AI within first week). Egyptian adopters show a similar proportion (29.4%), though the high unknown rate (29.4%) in the Egyptian corpus limits this conclusion.

### 4.3 Adoption Rate by Creation Month (Global)

| Month | Repos | Adoption % |
|---|---|---|
| Feb 2025 | 23 | 34.8% |
| Mar 2025 | 171 | 42.7% |
| May 2025 | 142 | 53.5% |
| Aug 2025 | 171 | 60.2% |
| Dec 2025 | 207 | 68.1% |
| Feb 2026 | 352 | 76.7% |
| Mar 2026 | 420 | 79.8% |
| Apr 2026 | 331 | **81.3%** |
| Sep 2026 | 174 | 63.2% |

**Key finding:** Adoption has grown from 34.8% (Feb 2025) to 81.3% (Apr 2026). The overall 67.5% average understates the current rate because it averages early-2025 repos together with late-2026 repos. Repos created in mid-2026 are at ~80% adoption.

*Note: September 2026 dip (63.2%) likely reflects incomplete data for very recently created repos.*

### 4.4 Adoption Rate by Creation Month (Egyptian)

| Month | Repos | Adoption % |
|---|---|---|
| Mar 2025 | 4 | 50.0% |
| Jun 2025 | 5 | 20.0% |
| Nov 2025 | 4 | 100.0% |
| Feb 2026 | 10 | 80.0% |
| Mar 2026 | 5 | 40.0% |
| Aug 2026 | 3 | 100.0% |

*Note: Egyptian monthly groups are very small (3–10 repos each), so individual month percentages are not reliable. The overall trend directionally matches the global trend.*

### 4.5 Born Agentic

| | Global | Egyptian |
|---|---|---|
| Born-agentic repos | 1,011 | 10 |
| % of all adopters | **33.3%** | **29.4%** |
| % of all repos | 22.5% | 12.0% |

Born-agentic behaviour is present in both corpora at similar rates among adopters (~30–33%). As a share of all repos, it is lower in Egypt (12.0% vs 22.5%), reflecting the lower overall adoption rate.

---

## 5. Co-adoption Analysis

### 5.1 Number of Tools per Repo

| Tools used | Global adopters | Egyptian adopters |
|---|---|---|
| 1 tool only | 63.1% | **73.0%** |
| 2 tools | 27.3% | 20.3% |
| 3 tools | 8.1% | 2.7% |
| 4+ tools | 1.5% | 4.1% |

Most adopters use only one AI tool. Egyptian adopters are even more single-tool focused (73.0% vs 63.1%).

### 5.2 Most Common Tool Pairs (Global)

| Tool A | Tool B | Repos |
|---|---|---|
| Claude Code | OpenAI | 682 |
| Claude Code | Cursor | 424 |
| Claude Code | Copilot | 362 |
| Cursor | OpenAI | 185 |
| Copilot | OpenAI | 128 |
| Copilot | Cursor | 103 |

Claude Code is the hub in almost every multi-tool combination. Claude Code + OpenAI (682 repos) is the most common pair globally.

### 5.3 Most Common Tool Pairs (Egyptian)

| Tool A | Tool B | Repos |
|---|---|---|
| Claude Code | Cursor | 8 |
| Claude Code | OpenAI | 6 |
| Claude Code | Copilot | 6 |
| Claude Code | Gemini | 5 |
| Copilot | Cursor | 4 |

Claude Code is also the hub in Egypt. In Egypt, Cursor pairs with Claude Code most frequently (8 repos), unlike globally where OpenAI is the top pair partner. Copilot also features more prominently in Egyptian pairs, consistent with its stronger overall showing in Egypt.

### 5.4 Tool Loyalty

| | Global | Egyptian |
|---|---|---|
| Only Claude Code | 47.5% | 45.9% |
| Only one tool (any) | 63.1% | 73.0% |

Nearly half of all adopters in both corpora use only Claude Code and nothing else. This proportion is nearly identical (47.5% vs 45.9%), suggesting that among those who do adopt, single-tool commitment to Claude Code is equally common in both communities.

---

## 6. Egyptian Owner Profile Analysis

*Based on GitHub profile data for 75 unique owners of the 83 Egyptian repos.*

### 6.1 Adoption by Follower Count

| Followers | Repos | Adoption % |
|---|---|---|
| 0 | 37 | 43.2% |
| 1–10 | 8 | 25.0% |
| 11–50 | 18 | 33.3% |
| **51–200** | **14** | **64.3%** |
| 200+ | 6 | 16.7% |

Mid-tier connected developers (51–200 followers) have the highest adoption at 64.3%. The drop at 200+ (16.7%) may reflect older, more established developers with set workflows who are slower to adopt new tools.

### 6.2 Adoption by Account Age

| Joined GitHub | Repos | Adoption % |
|---|---|---|
| Before 2019 | 7 | 57.1% |
| 2019–2020 | 7 | 28.6% |
| 2021–2022 | 20 | 35.0% |
| **2023 or later** | **12** | **41.7%** |
| Unknown | 37 | 43.2% |

No strong linear trend — the before-2019 group (57.1%) is surprisingly high, possibly because long-established developers who are still actively creating new repos in 2025 are early adopters by nature.

### 6.3 Adoption by Public Repo Count

| Public repos | Repos | Adoption % |
|---|---|---|
| 1–5 | 41 | 39.0% |
| 6–20 | 12 | 41.7% |
| 21–50 | 13 | 38.5% |
| **50+** | **17** | **47.1%** |

More prolific developers (50+ public repos) adopt slightly more (47.1%), but the differences across groups are modest. GitHub activity level is a weak predictor of adoption in the Egyptian corpus.

### 6.4 Adoption by Company Affiliation

| | Repos | Adoption % |
|---|---|---|
| Company-affiliated | 17 | 29.4% |
| Individual (no company) | 66 | 43.9% |

Individuals adopt more than company-affiliated developers in Egypt. This is the opposite of what one might expect and may reflect that company-affiliated developers work in constrained environments, while independent developers are freer to experiment.

### 6.5 Profile of the Egyptian AI Adopter

Combining all dimensions, the Egyptian developer most likely to adopt AI coding tools is:
- **Mid-tier connected** — 51–200 followers (64.3% adoption)
- **Works in TypeScript** — 46.0% vs 25.0% for JavaScript
- **Prolific GitHub user** — 50+ public repos (47.1% adoption)
- **Individual developer** — not company-affiliated (43.9% adoption)

---

## 7. Summary of Key Findings

| # | Finding | Value |
|---|---|---|
| F1 | Global multi-signal adoption rate | **67.5%** |
| F2 | Egyptian multi-signal adoption rate (corrected) | **41.0%** |
| F3 | Egypt vs global gap (corrected) | **−26.5 pp** |
| F4 | Egypt vs global gap (old corpus, pre-fix) | −49.9 pp |
| F5 | Undercounting delta (global) | **+19.5 pp** |
| F6 | Undercounting delta (Egyptian) | **+15.7 pp** |
| F7 | Highest adoption ecosystem | **pnpm (74.5%)** |
| F8 | Lowest adoption ecosystem | **vanilla (51.2%)** |
| F9 | TypeScript vs JavaScript gap (global) | **+13.5 pp** |
| F10 | Egyptian TypeScript adoption | **46.0%** |
| F11 | Egyptian JavaScript adoption | **25.0%** |
| F12 | Born agentic (AI within first week) | **33.3% of global adopters** |
| F13 | Adoption growth: Feb 2025 → Apr 2026 | **34.8% → 81.3%** |
| F14 | Single-tool loyalty (global adopters) | **63.1%** |
| F15 | Single-tool loyalty (Egyptian adopters) | **73.0%** |
| F16 | Claude Code repo coverage (global) | **63.4% of all repos** |
| F17 | Copilot strength in Egypt vs global | **+10.0 pp** (stronger in Egypt) |
| F18 | Egyptian adopters: 51–200 followers | **64.3%** |
| F19 | Filter correction impact on adoption | **17.6% → 41.0%** (same corpus, different filter) |
| F20 | Egyptian repos out of 26,475 accounts | **83** (only repos created in AI era) |

# Results
## Coding Agent Adoption in JavaScript/TypeScript/npm Repositories on GitHub

**Student:** Manuel Youssef Haik Kevorkian
**Date:** October 2026
**Status:** Draft — Stage 5 analysis complete

---

## Overview

| Corpus | Repos | Multi-signal Adoption | Single-signal Adoption | Delta |
|---|---|---|---|---|
| Global (random sample) | 4,500 | **67.5%** | 48.1% | 19.5 pp |
| Egyptian (targeted) | 136 | **17.6%** | 11.8% | 5.9 pp |
| **Gap (RQ3)** | — | **−49.9 pp** | −36.3 pp | — |

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

**Key finding:** pnpm developers have the highest adoption rate (74.5%). pnpm is a modern, performance-focused package manager — developers who chose it are already toolchain-aware and more likely to adopt new tools early. Vanilla repos (no package manager) have the lowest adoption (51.2%), consistent with them being simpler or less actively maintained projects. Even so, 51% is remarkably high, showing AI tools have reached even the most casual JS/TS developers.

**npm_no_lock surprisingly high (73%):** Repos with package.json but no lockfile tend to be newer, more experimental projects. These developers are less concerned with reproducibility conventions and may be more open to new tooling overall.

### 1.2 Adoption by Language (Global + Egyptian)

| Language | Corpus | Repos | Multi-signal % | Single-signal % | Agentic % |
|---|---|---|---|---|---|
| TypeScript | Global | 3,217 | **71.4%** | 50.6% | 66.3% |
| JavaScript | Global | 1,283 | 57.9% | 41.7% | 51.1% |
| TypeScript | Egyptian | 77 | **27.3%** | 18.2% | 18.2% |
| JavaScript | Egyptian | 59 | **5.1%** | 3.4% | 1.7% |

**Key finding:** TypeScript developers adopt AI significantly more than JavaScript developers in both corpora. Globally the gap is 13.5 pp (71.4% vs 57.9%). In Egypt the gap is enormous: 22.2 pp (27.3% vs 5.1%).

**Egyptian JavaScript (5.1%) is the most striking number in the dataset.** Only approximately 3 out of 59 Egyptian JavaScript repos show any AI signal at all. Egyptian JavaScript developers are essentially not using AI coding tools. This likely reflects that Egyptian JS developers skew toward beginners and students using simpler projects where AI tooling has not penetrated.

TypeScript's advantage is likely structural: its strict typing system helps AI tools generate more accurate code with fewer errors. Developers notice better results and keep using the tool.

### 1.3 Adoption by Size Stratum (Global + Egyptian)

| Size | Corpus | Repos | Multi-signal % | Single-signal % | Agentic % |
|---|---|---|---|---|---|
| Large (>500 stars) | Global | 391 | **85.7%** | 68.5% | 78.3% |
| Medium (51–500) | Global | 789 | 75.0% | 52.0% | 68.2% |
| Small (≤50 stars) | Global | 3,320 | 63.6% | 44.7% | 58.6% |
| Large (>500 stars) | Egyptian | 8 | 50.0% | 37.5% | 25.0% |
| Medium (51–500) | Egyptian | 18 | 22.2% | 11.1% | 11.1% |
| Small (≤50 stars) | Egyptian | 110 | **14.5%** | 10.0% | 10.0% |

**Key finding:** Globally, larger repositories adopt AI more (85.7% large vs 63.6% small). High-visibility projects are built by larger teams with more resources and greater awareness of new tools. However, the 63.6% adoption in small repos shows AI has reached casual individual developers, not just professional teams.

**Egyptian size pattern:** The same direction holds but at much lower levels across all strata. Even Egyptian large repos (50%) fall below the global small repo rate (63.6%). The Egyptian small repos (110 repos, 14.5%) are the most statistically reliable Egyptian size group and show how far adoption lags behind the global baseline.

*Note: Egyptian large repo count (n=8) is too small for reliable conclusions.*

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

**Key finding:** TypeScript outperforms JavaScript in every single ecosystem without exception. The highest adoption combination is **npm_no_lock + TypeScript (78.3%)** — experimental TypeScript projects with package.json but no lockfile. The lowest is **vanilla + JavaScript (43.0%)** — plain JavaScript with no package manager.

---

## 2. RQ2 — Signal Undercounting

### 2.1 Undercounting Delta

| Corpus | Single-signal % | Multi-signal % | Delta |
|---|---|---|---|
| Global | 48.1% | 67.5% | **+19.5 pp** |
| Egyptian | 11.8% | 17.6% | **+5.9 pp** |

**Key finding:** Globally, 19.5 percentage points of adopters — nearly one in five — would be completely invisible if only commit trailers were checked (the method used by most studies before 2025). This confirms that single-signal detection significantly undercounts real adoption.

The smaller Egyptian delta (5.9 pp) makes sense: Egyptian developers who do adopt AI tend to use it less intensively and are less likely to set up project-level configuration files or leave traces across multiple signal types. Their usage is shallower, so the gap between single-signal and multi-signal is smaller.

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

Commit trailers dominate at 89% of all instances, which explains why single-signal detection (trailers only) captures a large share but still misses 19.5 pp of multi-signal adopters. The 19.5 pp gap comes from repos where config files, PR patterns, or npm dependencies are present but no commit trailer was found.

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

**Claude Code dominance:** Claude Code appears in 63.4% of all repos scanned — the most detectable agent by far. Two factors explain this: (1) it adds a `Co-authored-by: Claude` trailer to every commit by default, which most developers do not disable; (2) its terminal-first CLI design fits naturally with the npm developer workflow. This likely overstates Claude Code's true market share — Cursor and Copilot are widely used but leave fewer automatic traces.

---

## 3. RQ3 — Egyptian vs Global Comparison

### 3.1 Headline Comparison

| Metric | Global (n=4,500) | Egyptian (n=136) | Gap |
|---|---|---|---|
| Multi-signal adoption | 67.5% | 17.6% | **−49.9 pp** |
| Single-signal adoption | 48.1% | 11.8% | −36.3 pp |
| Agentic level | 61.9% | 11.0% | **−50.9 pp** |
| AI-assisted level | 5.6% | 6.6% | +1.0 pp |
| None | 32.4% | 82.4% | +50.0 pp |
| Undercounting delta | 19.5 pp | 5.9 pp | — |

Egyptian JS/TS developers adopt AI coding agents at roughly one quarter the global rate. The gap will be formally tested in Stage 5 using Fisher's exact test. Given the magnitude (~50 pp), statistical significance at p < 0.0001 is expected.

### 3.2 Adoption by Language — Egyptian

| Language | Egyptian repos | Multi-signal % |
|---|---|---|
| TypeScript | 77 | 27.3% |
| JavaScript | 59 | **5.1%** |

The language gap within Egypt (22.2 pp) is sharper than the global language gap (13.5 pp). Egyptian JavaScript developers almost entirely do not use AI tools.

### 3.3 Agent Breakdown — Egyptian vs Global

| Agent | Global repos % | Egyptian repos % | Difference |
|---|---|---|---|
| Claude Code | 63.4% | 27.9% | −35.5 pp |
| OpenAI | 20.2% | 4.4% | −15.8 pp |
| Copilot | 14.1% | **12.5%** | **−1.6 pp** |
| Cursor | 13.4% | 5.9% | −7.5 pp |

**Copilot's relative resilience in Egypt** is notable. Every other tool collapses significantly when comparing Egyptian to global adoption. Copilot drops only 1.6 pp. A plausible explanation is GitHub Education's free Copilot access for verified students, which reduces the cost barrier for Egyptian university students. However, this cannot be confirmed from repository data alone and should be stated as a hypothesis in the thesis.

### 3.4 Tool Loyalty — Egyptian vs Global

| | Global adopters | Egyptian adopters |
|---|---|---|
| Only Claude Code | 47.5% | 47.3% |
| Any single tool | 63.1% | **76.4%** |
| Multiple tools | 36.9% | **23.6%** |

Egyptian adopters are significantly more likely to stick to a single tool (76.4% vs 63.1%). Those who do adopt in Egypt are more likely to be occasional or single-tool users rather than developers who experiment with multiple AI tools at once. This is consistent with lower overall adoption intensity in the Egyptian corpus.

---

## 4. Temporal Analysis (Global)

### 4.1 Time from Repo Creation to First AI Signal

| Metric | Value |
|---|---|
| Repos with timing data | 2,529 |
| Median days to first signal | **20 days** |
| Mean days to first signal | 78 days |
| Min | 0 days |
| Max | 576 days |
| Within 7 days | 1,011 repos (40.0%) |
| Within 30 days | 1,418 repos (56.1%) |
| Within 90 days | 1,807 repos (71.5%) |

**Key finding:** The median adopter adds their first AI signal just 20 days after creating the repo. 40% of adopters show AI signals within the first week — meaning they started using AI tools almost immediately after creating the project. This is "born agentic" behaviour.

### 4.2 Adoption Timing Breakdown (Global adopters)

| Timing | Repos | % of adopters |
|---|---|---|
| Within 1 week | 1,011 | 33.3% |
| Within 1 month | 407 | 13.4% |
| 1–3 months | 389 | 12.8% |
| 3–6 months | 291 | 9.6% |
| 6+ months | 431 | 14.2% |
| Unknown | 510 | 16.8% |

One third of all adopters were "born agentic" — they used AI from the very first week of the project. AI is not being bolted on to existing projects after the fact; it is being built in from day one.

### 4.3 Adoption Rate by Creation Month (Global)

| Month | Repos | Adoption % |
|---|---|---|
| Feb 2025 | 23 | 34.8% |
| Mar 2025 | 171 | 42.7% |
| Apr 2025 | 140 | 50.7% |
| Jul 2025 | 185 | 57.8% |
| Oct 2025 | 182 | 62.1% |
| Dec 2025 | 207 | 68.1% |
| Jan 2026 | 287 | 72.8% |
| Feb 2026 | 352 | 76.7% |
| Mar 2026 | 420 | 79.8% |
| Apr 2026 | 331 | **81.3%** |
| Sep 2026 | 174 | 63.2% |

**Key finding:** Adoption has grown dramatically over the study window — from 34.8% in February 2025 to 81.3% in April 2026. The overall 67.5% average understates the current adoption rate because it averages early-2025 repos (when tools were newer) together with late-2026 repos. Repos created today are approaching 80%+ adoption.

*Note: September 2026 dip (63.2%) may reflect incomplete data for very recently created repos whose AI signals have not yet appeared.*

*Note: Egyptian temporal data was unavailable — the `created_at` field was not populated in the Egyptian corpus CSV.*

---

## 5. Co-adoption Analysis

### 5.1 Number of Tools per Repo

| Tools used | Global adopters | Egyptian adopters |
|---|---|---|
| 1 tool only | 63.1% | **76.4%** |
| 2 tools | 27.3% | 18.2% |
| 3 tools | 8.1% | 1.8% |
| 4+ tools | 1.5% | 3.6% |

Most adopters globally use only one AI tool (63.1%). In Egypt this is even more pronounced at 76.4%. Multi-tool usage is a minority behaviour globally (36.9%) and even rarer in Egypt (23.6%).

### 5.2 Most Common Tool Pairs (Global)

| Tool A | Tool B | Repos |
|---|---|---|
| Claude Code | OpenAI | 682 |
| Claude Code | Cursor | 424 |
| Claude Code | Copilot | 362 |
| Cursor | OpenAI | 185 |
| Copilot | OpenAI | 128 |
| Copilot | Cursor | 103 |

**Key finding:** Claude Code is the hub in almost every multi-tool combination. Developers who use multiple tools almost always include Claude Code. Claude Code + OpenAI (682 repos) is the most common pair globally, suggesting developers use Claude Code for agentic work and OpenAI's API or ChatGPT for other tasks.

### 5.3 Most Common Tool Pairs (Egyptian)

| Tool A | Tool B | Repos |
|---|---|---|
| Claude Code | Cursor | 6 |
| Claude Code | Copilot | 4 |
| Claude Code | OpenAI | 3 |
| Copilot | Cursor | 3 |

Small numbers but the same pattern holds — Claude Code is the hub. In Egypt, Cursor and Copilot pair with Claude Code more than OpenAI, which is the reverse of the global pattern. This is consistent with Copilot's stronger relative showing in Egypt (possibly due to free student access).

### 5.4 Tool Loyalty

| | Global | Egyptian |
|---|---|---|
| Only Claude Code | 47.5% | 47.3% |
| Only one tool (any) | 63.1% | 76.4% |

Exactly half of all adopters in both corpora use only Claude Code and nothing else. This proportion is nearly identical globally and in Egypt (47.5% vs 47.3%), suggesting that among those who do adopt, the choice to commit to Claude Code alone is consistent across both communities.

---

## 6. Egyptian Owner Profile Analysis

*Based on GitHub profile data for 119 unique owners of the 136 Egyptian repos.*

### 6.1 Adoption by Follower Count

| Followers | Repos | Adoption % |
|---|---|---|
| 1–10 | 13 | 7.7% |
| 11–50 | 57 | 14.0% |
| **51–200** | **41** | **29.3%** |
| 200+ | 25 | 12.0% |

Mid-tier connected developers (51–200 followers) have the highest adoption at 29.3%. The drop at 200+ (12%) may reflect older, more established developers with set workflows who are slower to adopt new tools.

### 6.2 Adoption by Account Age

| Joined GitHub | Repos | Adoption % |
|---|---|---|
| Before 2019 | 51 | 17.6% |
| 2019–2020 | 25 | 8.0% |
| 2021–2022 | 40 | 20.0% |
| **2023 or later** | **20** | **25.0%** |

Newer accounts adopt more. Developers who joined GitHub in 2023 or later arrived during the AI tool era and show 25% adoption. The 2019–2020 cohort (8%) is the lowest — they built their habits before AI tools existed and have been the slowest to change.

### 6.3 Adoption by Public Repo Count

| Public repos | Repos | Adoption % |
|---|---|---|
| 1–5 | 8 | 0.0% |
| 6–20 | 32 | 21.9% |
| 21–50 | 53 | 9.4% |
| **50+** | **43** | **27.9%** |

The most prolific developers (50+ public repos) adopt the most at 27.9%. Developers with almost no public repos show 0% adoption. Higher GitHub activity strongly correlates with AI tool adoption.

### 6.4 Adoption by Company Affiliation

| | Repos | Adoption % |
|---|---|---|
| Company-affiliated | 61 | 19.7% |
| Individual (no company) | 75 | 16.0% |

Only a 3.7 pp difference. Company affiliation has minimal effect on Egyptian AI adoption. The barrier to adoption in Egypt appears to be primarily individual (cost, awareness, habit) rather than organisational.

### 6.5 Profile of the Egyptian AI Adopter

Combining all dimensions, the Egyptian developer most likely to adopt AI coding tools is:

- **Active on GitHub** — 50+ public repos (27.9% adoption)
- **Mid-tier connected** — 51–200 followers (29.3% adoption)
- **Joined recently** — 2023 or later (25.0% adoption)
- **Works in TypeScript** — 27.3% vs 5.1% for JavaScript
- **Company affiliation helps slightly** but is not decisive

The Egyptian developer least likely to adopt:
- Few followers, very few repos, joined 2019–2020
- Works primarily in JavaScript

---

## 7. Summary of Key Findings

| # | Finding | Value |
|---|---|---|
| F1 | Global multi-signal adoption rate | **67.5%** |
| F2 | Egyptian multi-signal adoption rate | **17.6%** |
| F3 | Egypt vs global gap | **−49.9 pp** |
| F4 | Undercounting delta (global) | **+19.5 pp** |
| F5 | Highest adoption ecosystem | **pnpm (74.5%)** |
| F6 | Lowest adoption ecosystem | **vanilla (51.2%)** |
| F7 | TypeScript vs JavaScript gap (global) | **+13.5 pp** |
| F8 | Egyptian JavaScript adoption | **5.1%** |
| F9 | Born agentic (AI within first week) | **33.3% of adopters** |
| F10 | Adoption growth: Feb 2025 → Apr 2026 | **34.8% → 81.3%** |
| F11 | Single-tool loyalty (global adopters) | **63.1%** |
| F12 | Claude Code repo coverage (global) | **63.4% of all repos** |
| F13 | Copilot drop Egypt vs global | **−1.6 pp** (all others −7 to −35 pp) |
| F14 | Egyptian adopters: 50+ repo owners | **27.9%** |
| F15 | Egyptian adopters: joined 2023+ | **25.0%** |

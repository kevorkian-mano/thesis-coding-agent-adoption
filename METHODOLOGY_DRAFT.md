# Methodology Draft
## Coding Agent Adoption in JavaScript/TypeScript/npm Repositories on GitHub

**Student:** Manuel Youssef Haik Kevorkian  
**Date:** October 2026  
**Status:** Draft for supervisor review

---

## 1. Research Questions

This thesis investigates three research questions:

| # | Research Question |
|---|---|
| **RQ1** | What percentage of active JavaScript/TypeScript repositories on GitHub show evidence of AI coding agent adoption? |
| **RQ2** | How much does single-signal detection (commit trailers only) undercount AI adoption compared to multi-signal detection? |
| **RQ3** | Do Egyptian developers adopt AI coding agents at a different rate than the global average? |

RQ1 and RQ2 address the global landscape of AI agent adoption. RQ3 introduces a comparative dimension by examining whether developer location (specifically Egypt) correlates with different adoption behavior.

---

## 2. Pipeline Overview

The study is organized into five sequential stages. Stages 1–4 are complete or near-complete. Stage 5 (statistical analysis) is next.

```
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 1 — Global JS/TS Corpus                                  │
│  60,129 repos collected → 4,500 stratified random sample        │
└────────────────────────┬────────────────────────────────────────┘
                         │
           ┌─────────────┴──────────────┐
           │                            │
           ▼                            ▼
┌──────────────────────┐    ┌───────────────────────────────────┐
│  STAGE 2             │    │  STAGE 4 (Global)                 │
│  Owner Identity      │    │  AI Detection on 4,500 repos      │
│  9 signals applied   │    │  → Adoption rate + delta          │
│  → 10 Egyptian repos │    │  → Answers RQ1 and RQ2            │
│    found in sample   │    └───────────────────────────────────┘
└──────────────────────┘
                                        ▲
┌──────────────────────┐                │
│  STAGE 3             │                │
│  Egyptian Targeted   │────────────────┘
│  Corpus              │  (Stage 4 also runs on this corpus)
│  6,642 repos         │
└──────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 5 — Statistical Analysis                                 │
│  RQ1: Global adoption rate                                      │
│  RQ2: Undercounting delta                                       │
│  RQ3: Egypt vs global comparison                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Stage 1 — Global Corpus Construction

### 3.1 Motivation

To measure AI coding agent adoption rates, a representative corpus of active JavaScript/TypeScript repositories is required. The corpus must be:
- **Globally representative** — not biased toward any geography, ecosystem, or size category
- **Active** — repositories with meaningful development history, not toy or abandoned projects
- **Scoped to the AI agent era** — only repositories created after AI coding agents became widely available (February 2025 onward)

### 3.2 Collection (Stage 1a)

Repositories were collected using the GitHub GraphQL Search API in two separate passes — one for JavaScript and one for TypeScript — to work around a known GitHub API limitation where OR-combined language filters return zero results.

**Date windows:** 5-day rolling windows from 2025-02-24 to October 2026, with recursive halving for windows that exceeded GitHub's 1,000-result cap per query.

**Inclusion criteria applied during collection:**

| Filter | Value | Rationale |
|---|---|---|
| Language | JavaScript or TypeScript | Thesis scope |
| Created on or after | 2025-02-24 | Start of mature AI agent era |
| Stars | ≥ 4 | Excludes toy and abandoned projects |
| Commits | ≥ 50 | Ensures meaningful development history |
| Fork | No | Excludes derivative projects |
| JS + TS combined bytes | ≥ 175,000 (175 KB) | Ensures JS/TS is the primary language, not incidental |

**Result:** 60,129 repositories collected.

### 3.3 Ecosystem Categorization (Stage 1b)

Every repository was classified by its package manager ecosystem. For each repo, 7 files at the root were checked via GitHub GraphQL:

`package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `bun.lockb`, `deno.json`, `deno.jsonc`

**Classification priority (applied in order):**

```
1. deno.json or deno.jsonc present  →  deno
2. package.json present:
     + package-lock.json            →  npm
     + yarn.lock                    →  yarn
     + pnpm-lock.yaml               →  pnpm
     + bun.lockb                    →  bun
     (no lockfile)                  →  npm_no_lock
3. None of the above               →  vanilla
```

**Result — full ecosystem breakdown:**

| Ecosystem | Count | % | Description |
|---|---|---|---|
| npm | 28,248 | 47.0% | package.json + package-lock.json |
| pnpm | 12,229 | 20.3% | package.json + pnpm-lock.yaml |
| vanilla | 10,177 | 16.9% | JS/TS with no package manager |
| npm_no_lock | 7,979 | 13.3% | package.json but no lockfile |
| yarn | 1,091 | 1.8% | package.json + yarn.lock |
| deno | 250 | 0.4% | Deno runtime |
| bun | 107 | 0.2% | package.json + bun.lockb |
| unknown | 48 | 0.1% | Data quality issue (NaN rows) |
| **Total** | **60,129** | **100%** | |

### 3.4 Stratified Random Sampling (Stage 1c)

Running AI detection on all 60,129 repositories would require millions of API calls. A stratified random sample of 4,500 repositories provides statistically reliable estimates for every subgroup while remaining computationally feasible.

**Ecosystem groups:**

| Group | Ecosystems included | Role in analysis |
|---|---|---|
| Thesis targets | npm, pnpm, yarn, bun, npm_no_lock | Primary analysis (RQ1, RQ2, RQ3) |
| Comparison group | vanilla | Secondary baseline — no package manager |
| Excluded | deno, unknown | Out of scope / data quality |

**Deno** is excluded because it uses a fundamentally different runtime and package system (URL imports, jsr.io) — outside the npm scope of the thesis title. **Unknown** rows (48 repos, 0.1%) are excluded due to a data quality issue in collection.

**Vanilla** is intentionally included as a comparison group. Dropping it would create selection bias — the adoption rate would reflect "npm developers" rather than "JS/TS developers." Vanilla repos also provide a natural baseline: if AI adoption is lower in vanilla repos (which lack npm tooling), that is itself a meaningful finding.

**Stratification variables:**
- Ecosystem (6 values: npm, pnpm, yarn, bun, npm_no_lock, vanilla)
- Primary language (2 values: JavaScript, TypeScript)
- Size stratum (3 values: small ≤50 stars, medium 51–500, large >500)

This produces 36 possible strata. 35 strata were found in the corpus (`bun__JavaScript__large` does not exist). Minimum 30 repos per stratum; otherwise proportional allocation. Random seed = 42 for reproducibility.

**Result — 4,500 repos sampled:**

| Ecosystem | Available | Sampled | % sampled |
|---|---|---|---|
| npm | 28,248 | 1,891 | 6.7% |
| pnpm | 12,229 | 909 | 7.4% |
| npm_no_lock | 7,979 | 656 | 8.2% |
| vanilla | 10,177 | 789 | 7.8% |
| yarn | 1,091 | 194 | 17.8% |
| bun | 107 | 61 | 57.0% |
| **Total** | **59,831** | **4,500** | **7.5%** |

Yarn and bun are oversampled relative to their corpus proportion because proportional allocation would yield too few samples for reliable stratum-level estimates (yarn has only 1,091 total; bun only 107). This is a standard technique in stratified sampling.

---

## 4. Stage 2 — Owner Identity Identification

### 4.1 Motivation

RQ3 requires comparing Egyptian developer adoption rates to the global average. To do this, we must identify which repositories in the global sample are owned by Egyptian developers.

This is non-trivial: **60.5% of GitHub users leave their location field blank.** A naive approach (filter by `location = "Egypt"`) would miss the majority of Egyptian developers. Stage 2 addresses this by applying a cascade of 9 signals that infer nationality from multiple independent sources.

### 4.2 Why a Score-Based Approach

Rather than binary classification (Egyptian / not Egyptian), each signal contributes points to a cumulative score. This design has several advantages:
- **Graceful degradation:** A developer with no location but Arabic bio text and Egyptian colleagues still accumulates evidence
- **Calibrated confidence:** High scores indicate certainty; low scores indicate uncertainty that is reported explicitly
- **Auditability:** Every classification decision has a traceable evidence record in `evidence_json`

### 4.3 The Nine Signals

Signals are grouped by data source and applied in increasing order of API cost.

**Group A — Profile signals (Stage 2a, S1–S4)**  
Fetched in a single GraphQL batch: 50 owners per request, ~90 total requests.

| Signal | Source field | What triggers it | Points |
|---|---|---|---|
| S1 | `user.location` | Contains Egypt / Cairo / مصر / Alexandria / etc. | **10** |
| S2 | `user.bio` | Contains Arabic text OR Egyptian keywords | **5** |
| S3 | `user.company` | Contains Egyptian org names or `.eg` domain | **5** |
| S4 | `user.email` | Has `.eg` TLD or Egyptian university domain | **8** |

S1 also acts as a **hard negative**: if the location field explicitly names a non-Egyptian country, the owner is immediately classified as `not_egyptian` and no further signals are applied.

**Group B — Social signals (Stage 2b, S5–S6)**  
Applied only to owners with `total_score < 10` after Stage 2a (2,649 owners). Batch size: 4 users per GraphQL request (each user fetches 10 orgs + 50 followers + 50 following = ~110 nodes).

| Signal | Source | What triggers it | Points |
|---|---|---|---|
| S5 | `user.organizations[].location` | Any organization the user belongs to has an Egyptian location | **7** |
| S6 | `user.followers` + `user.following` | ≥40% of connections with disclosed location are Egyptian AND ≥3 connections have a location | **5** |

**Group C — Repository signals (Stage 2c, S7–S9)**  
Applied only to owners still unclassified after Stage 2b (2,648 owners). Uses both REST (contributor lists) and GraphQL (README content).

| Signal | Source | What triggers it | Points |
|---|---|---|---|
| S7 | `GET /repos/{owner}/{repo}/contributors` | ≥40% of top-20 contributors with disclosed location are Egyptian AND ≥3 have location | **7** |
| S8 | `README.md`, `CONTRIBUTING.md` | Arabic Unicode characters (U+0600–U+06FF) make up >10% of all alphabetic characters | **3** |
| S9 | `README.md`, `CONTRIBUTING.md` | Contains Egyptian phone prefixes (010/011/012/015), country code +20, currency EGP, or 14-digit National ID | **4** |

### 4.4 Classification Thresholds

After all 9 signals have been applied, each owner is assigned a final label:

| Total score | Signals fired | Label | Included in Egypt corpus? |
|---|---|---|---|
| ≥ 10 | any | `egyptian_confirmed` | ✅ Yes — high confidence |
| 5–9 | any | `egyptian_probable` | ✅ Yes — medium confidence |
| 1–4 | ≥ 2 signals | `egyptian_probable` | ✅ Yes — two independent signals |
| 1–4 | 1 signal only | `unconfirmed` | ❌ No — single weak signal |
| 0 | 0 | `unclassified` | ❌ No — no evidence found |
| S1 hard negative | — | `not_egyptian` | ❌ No — explicit non-Egyptian location |

`unconfirmed` and `unclassified` owners are excluded from the Egyptian corpus and reported as **undercoverage** in the thesis methodology. They represent developers whose location is genuinely unknown after exhausting all available signals — an honest limitation of any GitHub-based study.

### 4.5 Results

Stage 2 processed 4,374 unique owners from the 4,500-repo sample.

**Final owner classification:**

| Label | Count | % | Meaning |
|---|---|---|---|
| not_egyptian | 1,720 | 39.3% | Explicit non-Egyptian location (S1 hard negative) |
| unclassified | 2,626 | 60.0% | No location evidence found across all 9 signals |
| unconfirmed | 18 | 0.4% | Weak single signal — insufficient evidence |
| egyptian_confirmed | 6 | 0.1% | Score ≥ 10 — high confidence |
| egyptian_probable | 4 | 0.1% | Score 5–9 or 2+ signals |
| **Total** | **4,374** | **100%** | |

**Egyptian corpus from global sample:** 10 repos (0.2% of 4,500)

**How Egyptian owners were identified (location source):**

| Source | Owners | % of Egyptian owners |
|---|---|---|
| Direct (S1 — profile location field) | 5 | 50% |
| Social (S5/S6 — orgs or network) | 2 | 20% |
| Repository (S7/S8/S9 — contributors, README) | 2 | 20% |
| Profile fields (S2/S3/S4 — bio, company, email) | 1 | 10% |

**Key finding from Stage 2:** Egyptian developers represent approximately 0.2% of active JS/TS repositories on GitHub. This natural frequency — consistent with Egypt's share of the global developer population — is itself a reportable finding. It also directly motivates the need for Stage 3: with only 10 Egyptian repos in the global sample, meaningful statistical comparison for RQ3 is not possible from the global sample alone.

---

## 5. Stage 3 — Egyptian Targeted Corpus

### 5.1 Motivation

The global random sample yields only 10 Egyptian-owned repositories. This is statistically correct (it accurately reflects natural frequency), but it is insufficient for RQ3. To perform a meaningful Egypt-vs-global comparison, a minimum of ~100–300 Egyptian repositories with AI detection results is required.

A supplementary **targeted Egyptian corpus** is therefore constructed. This corpus is used **exclusively for RQ3** — it does not affect the global adoption rate calculations in RQ1 and RQ2, which use only the global random sample.

This approach is methodologically standard in comparative studies where the minority group is rare in a random sample. The methodology chapter discloses this explicitly.

### 5.2 Construction

The targeted Egyptian corpus was built in two phases:

**Phase 1 — Account discovery (Stage 3a)**

```
Step 1 — Seed discovery:
  Search GitHub REST API for users with Egyptian location terms
  (Egypt, Cairo, Alexandria, Giza, مصر, القاهرة, الإسكندرية, الجيزة, ...)
  Apply activity filter: ≥10 followers OR ≥5 public repositories
  → Initial seed list of Egyptian developer accounts

Step 2 — Snowball expansion (up to 3 rounds):
  For each seed account: fetch followers + following (top 30 each)
  Any connection with an Egyptian location → add to account list
  Repeat until no new accounts found (convergence)
  → Expanded account list covering developers who follow Egyptians
    but may not have set their own location field
```

**Rationale for snowball expansion:** Egyptian developers who collaborate with or follow other Egyptians are likely Egyptian themselves, even if they have not set a location. This is the network-level equivalent of signal S6 in Stage 2.

**Phase 2 — Corpus pull and quality filter (Stage 3b)**

```
For each discovered account:
  Fetch public non-fork repositories via GraphQL
  Apply Stage 1-equivalent inclusion filters:
    - primary language = JavaScript or TypeScript
    - JS + TS bytes ≥ 50% of total language bytes
    - has package.json (verified via GraphQL)
    - not archived, not tutorial/auto-gen name pattern

Quality filter (matching Stage 1 thresholds exactly):
  - stars ≥ 4
  - commits ≥ 50  ← added to match Stage 1a filter
  - last push ≥ 2025-01-01
  - deduplicate by full_name
```

Applying identical inclusion and quality filters to both corpora ensures that any adoption rate difference in RQ3 cannot be explained by differences in repository quality or selection criteria. The commits ≥ 50 filter was specifically added after Stage 4 had already run on a preliminary 420-repo version of the corpus (which lacked this filter), to ensure the Egyptian corpus is built on the same activity threshold as the global sample.

### 5.3 Results

| Step | Count | Removed |
|---|---|---|
| Repos pulled from Egyptian accounts (raw) | 6,642 | — |
| After stars ≥ 4 | 819 | −5,823 |
| After commits ≥ 50 + pushed ≥ 2025-01-01 | **136** | −683 |

**By ecosystem:** npm only (136)  
**By language:** TypeScript 77 (56.6%) · JavaScript 59 (43.4%)

The large drop at the stars filter (6,642 → 819) reflects that Egyptian developer accounts contain many personal, learning, and small-scale projects with 0–3 stars. These are excluded by the same quality bar applied to the global corpus. The 136 remaining repositories represent the subset of Egyptian-owned JS/TS projects that meet the same activity and quality criteria as the global sample — the appropriate comparison group for RQ3.

---

## 6. Stage 4 — AI Coding Agent Detection

### 6.1 Detection Approach

AI coding agent adoption is detected through four independent signal types, applied in two passes:

**Pass 1 — Configuration file check (GraphQL, all repos)**

Checks the root directory tree of every repository for known agent configuration files:

| File | Agent |
|---|---|
| `CLAUDE.md`, `AGENTS.md` | Claude Code (Anthropic) |
| `.cursorrules`, `.cursorignore` | Cursor |
| `.aider.conf.yml` | Aider |
| `.roomodes`, `.windsurfrules` | Roo Code, Windsurf |
| `GEMINI.md` | Gemini CLI |
| `.github/copilot-instructions.md` | GitHub Copilot |
| `.continue/`, `.codeium/` | Continue, Codeium |

**Pass 2 — Deep scan (REST, all repos)**

Three sub-checks per repository (up to 300 commits and 200 PRs per repo, since 2025-01-01):

| Sub-check | What it detects |
|---|---|
| Commit message trailers | `Co-authored-by: Claude`, `Co-authored-by: GitHub Copilot`, etc. |
| Bot author emails | Emails matching known AI agent service accounts |
| PR body / branch / label patterns | Agent attribution in pull request metadata |
| npm dependency check | AI agent packages in `package.json` (e.g., `@anthropic-ai/claude-code`) |

### 6.2 Adoption Level Classification

Each repository is assigned an adoption level based on the strength of evidence:

| Level | Condition | Meaning |
|---|---|---|
| **agentic** | Config file present, OR ≥2 distinct signal types, OR ≥3 total signals | Active, deliberate agent use |
| **ai_assisted** | Any signal found but none of the agentic conditions | Occasional or incidental use |
| **none** | 0 signals detected | No evidence of agent use |

### 6.3 Single vs Multi-Signal Detection (RQ2)

Two adoption flags are computed per repository:
- `agent_adopted_single` — True if any **commit trailer** signal found (the method used by most prior studies)
- `agent_adopted_multi` — True if **any** signal type found (this study's multi-signal approach)

The difference between these two rates is the **undercounting delta**: the percentage points of adoption that commit-trailer-only detection fails to capture.

### 6.4 Results — Global Corpus (4,500 repos)

**Headline adoption rates:**

| Metric | Value |
|---|---|
| Total repos scanned | 4,500 |
| Multi-signal adoption rate (RQ1) | **67.5%** (3,039 repos) |
| Single-signal adoption rate | **48.1%** (2,163 repos) |
| **Undercounting delta (RQ2)** | **+19.5 percentage points** |

**Adoption level breakdown:**

| Level | Count | % |
|---|---|---|
| agentic | 2,788 | 61.9% |
| ai_assisted | 251 | 5.6% |
| none | 1,461 | 32.4% |

**Signal type breakdown (total signal instances detected):**

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

**Agent breakdown (top 10 by signal count):**

| Agent | Signal instances | % of total |
|---|---|---|
| Claude Code (Anthropic) | 119,995 | 88.1% |
| OpenAI (ChatGPT / Codex) | 9,913 | 7.3% |
| Cursor | 8,318 | 6.1% |
| GitHub Copilot | 5,016 | 3.7% |
| Devin (Cognition) | 935 | 0.7% |
| Aider | 70 | 0.1% |
| Gemini | 68 | 0.1% |
| Cline | 16 | <0.1% |
| Windsurf | 10 | <0.1% |
| Roo Code | 1 | <0.1% |

### 6.5 Interpretation

**RQ1:** 67.5% of active 2025 JS/TS repositories show evidence of AI coding agent adoption. This figure specifically applies to repositories created after February 2025 — the period when AI coding agents reached mainstream use. It should not be extrapolated to the full historical GitHub corpus.

**RQ2:** Single-signal detection (commit trailers only, as used in most prior work) captures only 48.1% — missing 19.5 percentage points of adoption. This confirms the study's core methodological claim: multi-signal detection substantially outperforms single-signal approaches in capturing real-world AI agent usage.

**Claude Code dominance:** 88.1% of signal instances are attributable to Claude Code. This likely reflects the strong community adoption of Claude Code's `Co-authored-by: Claude` trailer convention combined with the corpus's 2025 timeframe. This finding will be discussed in the results chapter.

### 6.6 Results — Egyptian Corpus (136 repos) ✅

**Headline adoption rates:**

| Metric | Value |
|---|---|
| Total repos scanned | 136 |
| Multi-signal adoption rate | **17.6%** (24 repos) |
| Single-signal adoption rate | **11.8%** (16 repos) |
| Undercounting delta | **+5.9 percentage points** |

**Adoption level breakdown:**

| Level | Count | % |
|---|---|---|
| agentic | 15 | 11.0% |
| ai_assisted | 9 | 6.6% |
| none | 112 | 82.4% |

**Signal type breakdown:**

| Signal type | Instances |
|---|---|
| Commit trailers | 323 |
| Config files | 48 |
| PR branch patterns | 29 |
| PR labels | 21 |
| Author email | 4 |
| npm dependency | 2 |
| PR body patterns | 1 |

**Agent breakdown:**

| Agent | Signal instances |
|---|---|
| Claude Code | 339 |
| OpenAI | 44 |
| Copilot | 26 |
| Cursor | 14 |
| Cline | 2 |
| Continue | 1 |
| Windsurf | 1 |
| Gemini | 1 |

### 6.7 RQ3 Comparison — Egypt vs Global

| Metric | Global (n=4,500) | Egyptian (n=136) | Gap |
|---|---|---|---|
| Multi-signal adoption | 67.5% | 17.6% | **−49.9 pp** |
| Single-signal adoption | 48.1% | 11.8% | **−36.3 pp** |
| Agentic level | 61.9% | 11.0% | **−50.9 pp** |
| Undercounting delta | 19.5 pp | 5.9 pp | — |

**Preliminary RQ3 answer:** Egyptian JS/TS developers adopt AI coding agents at dramatically lower rates than the global average (17.6% vs 67.5%, a gap of ~50 percentage points). This difference will be formally tested in Stage 5 using Fisher's exact test. Given the magnitude of the gap, statistical significance at p < 0.0001 is expected.

**Note on undercounting delta:** The smaller delta in the Egyptian corpus (5.9 pp vs 19.5 pp globally) suggests Egyptian developers who do use AI tools rely slightly more on commit trailers relative to other signal types — possibly because they are less likely to configure project-level agent settings (config files).

---

## 6.8 Discussion of Key Findings

### What does 67.5% global adoption actually mean?

67.5% means that out of every 10 active JS/TS repositories created in 2025, about 7 show at least one sign that an AI coding agent was used. This sounds very high, but it makes sense for two reasons.

First, the corpus only includes repositories created after February 2025 — projects born during the period when AI tools were already widely available. Developers who started a new project in 2025 were already surrounded by these tools and very likely tried them.

Second, the threshold is "any sign at all." Even one commit with a Claude trailer counts. A repository does not need to be heavily AI-generated to be classified as adopted — just touched by an AI tool once. So 67.5% does not mean AI wrote most of the code. It means at least something AI-related happened in this repository.

### Agentic vs AI-assisted: most users are fully committed

| Level | Global | Egyptian |
|---|---|---|
| Agentic | 61.9% | 11.0% |
| AI-assisted | 5.6% | 6.6% |
| None | 32.4% | 82.4% |

Globally, almost everyone who uses AI at all uses it in an agentic, integrated way (61.9%) rather than occasionally (5.6%). This suggests that once developers adopt an AI coding tool, they tend to keep using it deeply — not just experiment once and stop.

In Egypt the balance is different. Agentic (11%) and AI-assisted (6.6%) are much closer together, suggesting Egyptian developers who do use AI are more likely to be in the "tried it occasionally" stage rather than the "fully integrated into workflow" stage.

### Why is the Egypt gap so large?

Egyptian developers adopt AI coding agents at roughly one quarter the global rate (17.6% vs 67.5%). Several factors likely contribute:

- **Cost and access.** Claude Code, Cursor, and Copilot are paid tools. A $20/month subscription is a much bigger barrier for a developer in Egypt than for one in Germany or the United States. This is the most likely explanation.

- **Awareness and exposure.** These tools spread heavily through Twitter/X, YouTube, and tech communities that are more active in North America and Europe. Egyptian developers may have less exposure to them.

- **Project type.** The Egyptian corpus skews toward personal and academic projects. Developers working on homework assignments or small personal tools are less likely to invest in AI tooling than someone building a commercial product.

- **Cultural norms around automation.** Some developer communities have a stronger preference for writing code manually. Using AI assistance may carry different connotations in different contexts.

The thesis does not need to prove which of these is the cause. It documents that the gap exists and proposes these as plausible explanations in the discussion chapter.

### Why does Claude Code dominate 88% of signals?

| Tool | Global signals | % |
|---|---|---|
| Claude Code | 119,995 | 88.1% |
| OpenAI | 9,913 | 7.3% |
| Cursor | 8,318 | 6.1% |
| Copilot | 5,016 | 3.7% |

Two reasons explain this dominance:

**It leaves a trailer by default.** Every commit Claude Code makes automatically adds `Co-authored-by: Claude <noreply@anthropic.com>`. Most developers do not turn this off. Cursor and Copilot do not do this by default — they leave fewer visible traces in commit history.

**It fits the JS/TS developer profile.** Claude Code is a terminal-based tool built for developers who work from the command line. JS/TS npm developers are exactly that kind of developer. The tool matches the community.

This also means the 88% figure likely overstates Claude Code's true market share. Cursor and Copilot are widely used but leave fewer automatic traces, so they appear undercounted in repository mining studies. This limitation should be acknowledged in the thesis.

### What does the undercounting delta tell us?

| | Global | Egyptian |
|---|---|---|
| Single-signal (trailers only) | 48.1% | 11.8% |
| Multi-signal (all signals) | 67.5% | 17.6% |
| Delta | **19.5 pp** | **5.9 pp** |

Globally, 19.5 percentage points of adopters — nearly one in five — would be completely invisible if only commit trailers were checked. This is the answer to RQ2 and directly confirms what prior literature suspected: single-signal detection significantly undercounts real adoption.

The smaller Egyptian delta (5.9 pp) makes sense. Egyptian developers who do use AI tend to use it less intensively and are less likely to have set up project-level configuration files or left traces in pull requests. Their usage is shallower, so fewer signal types appear, and the gap between single-signal and multi-signal detection is smaller.

### Summary

Most active JS/TS projects started in 2025 show signs of AI tool use (67.5%), and most of that use is serious and deliberate rather than occasional. Claude Code dominates the signals because it is the best-fitting tool for this ecosystem and leaves automatic commit traces. Egyptian developers adopt these tools at a much lower rate (17.6%), likely due to cost, access, and the nature of their projects. Studying only commit trailers would have missed about 20% of global adopters, confirming that multi-signal detection is necessary for accurate measurement.

---

## 7. Pending Work

| Step | What | Status |
|---|---|---|
| Stage 3b (filter) | Filter 6,642 Egyptian repos → 136 repos | ✅ Done |
| Stage 4 (Egyptian) | Run AI detection on 136 Egyptian repos | ✅ Done — 17.6% adoption |
| Stage 5 | Statistical analysis — all three RQs | ⏳ Scripts to write |

**Stage 5 plan:**

- **RQ1:** Report global multi-signal adoption rate (67.5%), broken down by ecosystem, primary language, and size stratum. Report vanilla separately as comparison group.
- **RQ2:** Report undercounting delta (19.5 pp), broken down by signal type contribution.
- **RQ3:** Apply Fisher's exact test and Mann-Whitney U to compare Egyptian adoption rate against global. Apply Benjamini-Hochberg correction for multiple comparisons. Perform sensitivity check: confirmed-only Egyptian owners vs confirmed + probable.

---

## 8. Data Produced

| File | Location | Contents |
|---|---|---|
| `global_corpus.csv` | `data/stage1/` | All 60,129 collected repos |
| `ecosystem_audit.csv` | `data/stage1/` | Ecosystem breakdown table |
| `sample_corpus.csv` | `data/stage1/` | 4,500 stratified random sample |
| `strata_audit.csv` | `data/stage1/` | Per-stratum breakdown |
| `owner_signals.csv` | `data/stage2/` | S1–S6 scores for all 4,374 owners |
| `owner_signals_full.csv` | `data/stage2/` | All 9 signal scores |
| `owners_final.csv` | `data/stage2/` | Final owner classifications |
| `egypt_corpus.csv` | `data/stage2/` | 10 Egyptian repos from global sample |
| `coverage_stats.csv` | `data/stage2/` | Signal contribution breakdown |
| `egyptian_corpus_raw.csv` | `data/stage3/` | 6,642 targeted Egyptian repos (raw) |
| `egypt_corpus_input.csv` | `data/stage3/` | 136 quality-filtered Egyptian repos ✅ |
| `sample_corpus_detected.csv` | `data/stage4/` | AI detection results — global corpus ✅ |
| `signals_global.csv` | `data/stage4/` | Per-signal instances — global corpus ✅ |
| `egypt_corpus_input_detected.csv` | `data/stage4/` | AI detection results — Egyptian ✅ |
| `signals_egypt_corpus_input.csv` | `data/stage4/` | Per-signal instances — Egyptian ✅ |

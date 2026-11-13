# Thesis Continuation Instructions
**Thesis:** Coding Agent Adoption in JavaScript/TypeScript/npm Repositories on GitHub  
**Author:** Manuel Youssef Haik Kevorkian — German International University (GIU)  
**Last updated:** November 2026

---

## 1. Current State

| Chapter | File | Status |
|---------|------|--------|
| Ch.1 Introduction | `chapters/intro.tex` | ✅ Complete |
| Ch.2 Literature Review | `chapters/litrev.tex` | ✅ Complete |
| Ch.3 Methodology | `chapters/methodology.tex` | ❌ File does not exist yet — must be created |
| Ch.4 Results | `chapters/results.tex` | ❌ File does not exist yet — must be created |
| Ch.5 Discussion | `chapters/discussion.tex` | ❌ File does not exist yet — must be created |
| Ch.6 Conclusion | `chapters/conclusion.tex` | ❌ File does not exist yet — must be created |

**Abstract and Acknowledgments** in `main.tex` are also still `% TODO`.

When a chapter is written, **uncomment its `\input{}` line in `main.tex`** (lines 283, 290, 297, 304).

---

## 2. Thesis Overview

**Research Questions:**
- **RQ1 (Scope):** What proportion of active JS/TS/npm repos on GitHub created since Feb 2025 show AI coding agent use?
- **RQ2 (Undercounting):** To what extent does single-signal detection underestimate adoption vs. a multi-signal approach?
- **RQ3 (Geography):** Do adoption rates differ significantly across countries within JS/TS/npm?

**Corpus criteria:** Created ≥ 24 Feb 2025, ≥ 4 stars, ≥ 50 commits, not a fork, ≥ 175,000 bytes JS/TS code, `package.json` + lockfile present.

**Detection pipeline (3 passes):**
- Pass 3a — config files (CLAUDE.md, AGENTS.md, .cursorrules, etc.) — batch GraphQL
- Pass 3b — commit trailers + PR branch prefixes — REST API
- Pass 3c — PR body text, PR labels, npm SDK dependency declarations — deep scan

**Labels:**
- `agentic` = 3+ signals OR signals from 2+ distinct agents
- `ai_assisted` = 1–2 signals from a single agent
- `none` = no signals detected

---

## 3. All Results (from `results_summary.tex`)

### Stage 1 — Corpus
- **Total repos:** 60,129
- Ecosystem split: npm 47.0%, pnpm 20.3%, vanilla 16.9%, npm_no_lock 13.3%, yarn 1.8%, deno 0.4%, bun 0.2%
- Language: TypeScript 75.4% (45,314), JavaScript 24.6% (14,815)

### Stage 2 — Owner Location
- Unique owners: 50,002
- Located: 28,279 (56.6%) across 4 passes
- Top countries: China 5,829 (20.6%), US 3,981 (14.1%), India 3,945 (14.0%)

### Stage 3 — Detection
- Pass 3a (config): 28,397 agentic (47.2% of 60,129)
- Pass 3b (trailers): 11,937 agentic (37.6% of remaining 31,732)
- Pass 3c (deep): 70 agentic (from remaining 19,795)
- **Final: Agentic 40,364 (67.1%), AI-assisted 4,397 (7.3%), None 15,368 (25.6%)**
- **Total adopted: 44,761 (74.4%)** — Wilson 95% CI: [74.09%, 74.79%]
- Breakdown: TypeScript 78.5%, JavaScript 62.0%; pnpm 84.0%, npm 75.3%, vanilla 58.9%
- Tool loyalty: 66.3% single-tool; Claude Code only: 34.4% of adopters
- Pass 3a top agents: Claude Code 18,313 (64.5%), Generic 17,015 (59.9%), Cursor 2,247 (7.9%), GitHub Copilot 1,798 (6.3%)

### Stage 4 — Geography (66 countries, ≥30 repos each)
- Located corpus: 33,848 repos (56.3%)
- **Global adoption: 74.4%** — Wilson CI: [74.09%, 74.79%]
- **Top 5:** Saudi Arabia 90.9%, Belgium 90.4%, UAE 87.4%, South Korea 86.9%, Taiwan 85.0%
- **Bottom 5:** Nepal 35.2%, Sri Lanka 34.6%, Rwanda 27.5% (lowest)
- **Income groups:**
  - High Income: 15,020 repos, 81.3% adoption, paid tool 72.6%, free 11.4%
  - Upper-Middle: 10,534 repos, 74.6% adoption, paid 64.0%, free 11.0%
  - Lower-Middle: 7,697 repos, 52.4% adoption, paid 60.8%, free 24.3%
  - Low Income: 51 repos, 27.5% adoption
- **World regions:** North America 76.1%, Western Europe 72.8%, East Asia 69.8%, South Asia 44.3%, Sub-Saharan Africa 36.4%
- **MENA (1,587 repos, 65.9% overall):** Gulf 87.9%, Levant 81.9%, Turkey 72.1%, North Africa 50.8%, Iran 47.1%
- Statistical tests: chi-squared for overall country difference; pairwise Fisher's exact with FDR correction; all * in tables = p < 0.05

### Stage 4 — Size Analysis
- Monotonic pattern across all 3 operationalisations:
  - Stars (≤50/51–500/>500): 72.1% → 83.7% → 92.2% (+20.1 pp)
  - Commits (≤114/115–286/>286): 66.9% → 75.0% → 81.3% (+14.4 pp)
  - Code volume (≤0.50MB/0.50–1.45MB/>1.45MB): 61.6% → 74.8% → 86.6% (+25.0 pp)

### Stage 5 — Extended Analysis
- **Time series (Feb 2025 – Sep 2026):** Adoption rose from 50.5% (Feb 2025) → peak 84.3% (Mar 2026). Sharpest growth: Dec 2025 → Feb 2026 (+11 pp in 2 months). Plateau ~82–84% from Feb–May 2026.
- **Tool diversity:** 65.1% single-agent; 28.2% dual; 5.0% 3 tools; 34.9% multi-agent total
- **Commit density (11,937 trailer repos):** Experimental <1%: 20.4%; Limited 1–5%: 28.8%; Consistent 5–20%: 23.8%; Pervasive >20%: 27.0%. Median density: Claude Code 0.101, Aider 0.113, Replit 0.157, Cursor 0.026
- **Adoption timing (44,761 agentic repos):** Immediate ≤7 days: 55.9% (21,828); Early 8–30 days: 12.4%; Late >30 days: 31.7%. Median 3.0 days to first AI signal.
- **TypeScript in JS repos (14,815 JS-primary repos):** Agentic 15.7% adopt tsconfig.json vs non-agentic 7.7% (2.03× ratio). Of those, 25.9% bootstrapped TS on same day as first AI signal; 46.2% on or after AI signal.
- **China (6,764 repos — #1 country, more than US):** 69.2% use Western tools only; Claude Code in 53.3% of Chinese agentic repos (vs 65.5% globally). Chinese domestic tools: Trae/MarsCode 167 repos, Qwen Code 54, Kimi Code 11 — total 2.3% of Chinese agentic.
- **Frameworks (top 5 by adoption):** Astro 83.5%, Hono 82.1%, TanStack Start 79.4%, VitePress 77.8%, Solid 77.8%. Lowest: Express 57.8%, NestJS 62.0%. React (30,614 repos): 65.2%.

---

## 4. Chapter Writing Guide

### Chapter 3 — Methodology (`chapters/methodology.tex`)

**Label:** `\label{chap:methodology}`  
**Sections to cover:**

1. **Research Design** — observational, computational pipeline study; not experimental; no causal claims
2. **Phase 1 — Corpus Construction**
   - GitHub Search API with date-window partitioning
   - Filter criteria (date ≥ 24 Feb 2025, ≥4 stars, ≥50 commits, no forks, ≥175KB JS/TS)
   - Ecosystem membership: `package.json` + lockfile (npm, Yarn, pnpm, Bun, Deno, vanilla)
   - Deduplication and validity checks
   - Cite: `dabic2021` (SEART GHS), `kalliamvakou2016` (filtering rationale)
3. **Phase 2 — Owner Geographic Inference**
   - 4-pass pipeline: location field → bio/TLD/network → Nominatim+TZ+script → company ROR/org
   - 56.6% located (28,279 of 50,002 unique owners)
   - Cite: `wachs2022` (validation of self-reporting)
4. **Phase 3 — AI Signal Detection**
   - 3-pass pipeline ordered by cost (GraphQL → REST → deep scan)
   - Signal families: config files, commit trailers, PR branch prefixes, PR body/labels, npm SDK deps
   - Labelling thresholds (agentic / ai_assisted / none)
   - Cite: `robbesHeuristics2026`, `ghaleb2026`, `khosravani2026`, `galsterConfig2026`
5. **Phase 4 — Statistical Analysis**
   - Wilson 95% CI for adoption rates
   - Chi-squared test for overall country difference (RQ3)
   - Pairwise Fisher's exact tests with Benjamini-Hochberg FDR correction
   - Kruskal-Wallis + Mann-Whitney U for size comparisons
   - Countries with <30 repos excluded from geographic ranking
6. **Reproducibility** — scripts archived, Python 3.x, GitHub REST v3 / GraphQL v4 APIs

### Chapter 4 — Results (`chapters/results.tex`)

**Label:** `\label{chap:results}`  
Structure answers to the 3 RQs directly. Each RQ gets its own section.

**Section 4.1 — RQ1: Scope of Adoption**
- Overall: 74.4% adopted (44,761 / 60,129); Wilson CI [74.09%, 74.79%]
- Agentic 67.1%, AI-assisted 7.3%, None 25.6%
- By language: TypeScript 78.5%, JavaScript 62.0%
- By ecosystem: pnpm 84.0%, npm 75.3%, vanilla 58.9%, yarn 57.2%
- Tool landscape: Claude Code dominant (64.5% of config-detected), Generic second (59.9%)
- Time series: 50.5% at start (Feb 2025) → 84.3% peak (Mar 2026)
- Adoption timing: 55.9% immediate (≤7 days)

**Section 4.2 — RQ2: Signal Undercounting**
- Compare Pass 3a only (config files = 28,397) vs full 3-pass (40,364 agentic)
- Single-signal detection (config only) finds 28,397 → misses 11,967 additional agentic repos
- Delta: 11,967 / 40,364 = 29.6% of true agentic count missed
- In percentage points: config-only = 47.2% adoption; full = 67.1% → +19.9 pp gap
- Cite `khosravani2026` (30× undercounting factor) and `robbesAgenticMuch2026` (6.46 pp gap in cross-language study) as comparators

**Section 4.3 — RQ3: Geographic Ranking**
- 66 countries eligible (≥30 repos), 33,848 located repos
- Chi-squared confirms global country difference is significant
- Top 10 / Bottom 10 from results_summary.tex (table above)
- Income group breakdown (HIC 81.3% → LIC 27.5%)
- World regions breakdown (North America 76.1% → Sub-Saharan Africa 36.4%)
- MENA detail (Gulf 87.9% → Iran 47.1%)
- Pricing analysis: in lower-income countries, free tools dominate (LMIC: free 24.3% vs HIC: free 11.4%)
- China analysis (largest country, VPN paradox, 2.3% Chinese domestic tools)

**Additional subsections (Extended):**
- Repository size and adoption (monotonic, all 3 operationalisations)
- Framework breakdown (Astro, Hono highest; Express, NestJS lowest)
- Tool diversity (65.1% single-agent)
- Commit density distribution
- TypeScript adoption in JS repos (2× rate in agentic repos)

### Chapter 5 — Discussion (`chapters/discussion.tex`)

**Label:** `\label{chap:discussion}`  
**Sections:**

1. **Interpretation of RQ1** — 74.4% is well above the 71–76% reported by `robbesAgenticVery2026` for new repos generally; confirms npm/JS/TS is a high-adoption ecosystem
2. **Interpretation of RQ2** — 29.6% miss rate with single-signal; worse than the 6.46 pp gap in `robbesAgenticMuch2026` because config-only detection is narrower than a narrow heuristic set
3. **Interpretation of RQ3** — Gradient follows income/GDP but with notable outliers (South Korea, Taiwan outperform income prediction; Gulf states highest despite smaller developer communities)
4. **Pricing and Access** — Free-tool share rises as income falls; supports `daniotti2025` finding that adoption gap may widen
5. **Threats to Validity**
   - Internal: labelling thresholds are arbitrary; 43.4% owners not geolocated
   - External: GitHub ≠ all software development; npm ≠ all JS/TS
   - Construct: "adoption" ≠ "quality use"; co-authored commits ≠ agent-driven commit
6. **Implications** — For tool vendors (Claude Code terminal-first fits npm workflow), educators, open-source foundations, policy (pricing barriers in lower-income regions)

### Chapter 6 — Conclusion (`chapters/conclusion.tex`)

**Label:** `\label{chap:conclusion}`  
- Summarise contributions (3 from intro.tex Section 1.6)
- Answer each RQ in 2–3 sentences
- Limitations (2–3 key ones)
- Future work: (a) extend to other ecosystems, (b) longitudinal re-measurement, (c) causal study of pricing barriers, (d) qualitative interviews with developers

### Abstract (`main.tex` lines 237–241)
~250 words. Cover: context (AI agents on GitHub), gap (no npm-specific study), method (60,129 repos, 3-pass detection), key results (74.4%, 29.6% undercounting gap, country ranking 90.9%→27.5%), contribution.

---

## 5. Writing Rules (MANDATORY)

### The Doctor's Prescribed Format
Every paper in the literature review follows this structure — maintain it if adding any new citations:
1. **Who** — Author(s)~\cite{key} [past-tense verb] [what they studied]
2. **Approach** — "Their approach..."
3. **Findings** — key numbers/results
4. **Strength** — "The study's strength is..."
5. **Limitation** — "A limitation is..."
6. **Counter-argument** — "A counter-argument is..."

### AI Red Flags to AVOID
Do not use any of the following phrases or patterns:
- "It is important to note that" / "It is worth noting"
- "Furthermore" / "Moreover" / "Additionally" (as sentence openers)
- "In conclusion" / "In summary" / "Overall"
- "Notably" / "Interestingly" / "Significantly" (as adverbs to open a sentence)
- "plays a crucial role" / "plays a key role"
- "leverage" (as a verb — use "use" or "apply" instead)
- "utilize" (use "use")
- "delve into" / "dive into"
- "pivotal" / "paramount" / "imperative"
- "It is essential to" / "It should be noted"
- "In order to" (use "To")
- Consecutive sentences all starting with "The"
- Identical sentence structure repeated more than twice in a paragraph
- Overly symmetrical bullet lists where every item has the same length

### Style
- Academic British English (organise, analyse, colour, behaviour, characterise)
- Specific numbers over vague claims ("74.4%" not "a high proportion")
- Varied sentence length — mix short punchy sentences with longer analytical ones
- Do not start consecutive paragraphs with the same word
- No inline comments in LaTeX about what you're writing

---

## 6. The 31 Bibliography Keys

```
robbesAgenticMuch2026    robbesAgenticVery2026    khosravani2026
robbesHeuristics2026     ghaleb2026               galsterConfig2026
galsterExploratory2026   raida2026                chatlatanagulchai2025
ogenrwot2026             mazloomzadeh2026          popescu2026
watanabe2025             oukhay2026               horaRobbes2026
cynthia2026              dabic2021                wachs2022
octoverse2024            octoverse2025            daniotti2025
felder2026               chen2021codex            dey2020biman
agarwal2026              kalliamvakou2016         barke2023
ziegler2022              chatzidimitriou2018      dakhel2023
denisovBlanch2026
```

Do not cite any other papers. Do not add new bib entries without user approval.

---

## 7. Key File Locations

| Resource | Path |
|----------|------|
| Main LaTeX file | `bachelor_thesis/main.tex` |
| Bibliography | `bachelor_thesis/references.bib` |
| Intro (Ch.1) | `bachelor_thesis/chapters/intro.tex` |
| Lit Rev (Ch.2) | `bachelor_thesis/chapters/litrev.tex` |
| Full results data | `bachelor_thesis/results_summary.tex` |
| Statistical tests | `data/stage4/statistical_tests.txt` |
| Figures | `bachelor_thesis/figures/` |
| JS/TS corpus CSV | `data/stage3/corpus_detected_full.csv` |
| Country timeline | `data/stage5/country_timeline.csv` |

---

## 8. Before Starting — Read First

1. Read `chapters/intro.tex` — contains the exact RQ wording, scope statements, and contribution framing to stay consistent with
2. Read `chapters/litrev.tex` — do not contradict anything stated there; cite the same papers when referencing the same findings
3. Read `results_summary.tex` — this is the authoritative source for all numbers; never invent or approximate figures
4. Read `data/stage4/statistical_tests.txt` — for exact p-values and test statistics to report in Results

Then proceed chapter by chapter: Methodology → Results → Discussion → Conclusion → Abstract.

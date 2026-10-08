# Chapter 1 — Introduction

## 1.1 Background and Motivation

Software development is undergoing one of its most significant productivity transformations in decades. Since the public release of GitHub Copilot in October 2021, AI-powered tools have progressed rapidly from inline autocomplete assistants to fully autonomous coding agents capable of planning multi-step tasks, writing and executing code, running test suites, and opening pull requests without continuous human supervision. Tools such as Anthropic's Claude Code, Cursor, Windsurf, OpenAI Codex CLI, and Amazon Q Developer now occupy production workflows across a wide spectrum of open-source and commercial projects.

The pace of this adoption is remarkable. GitHub's Octoverse 2025 report recorded TypeScript as the most-used language on the platform for the first time, with the JavaScript and TypeScript ecosystem collectively representing the single largest segment of public activity [octoverse2025]. This makes the **npm** ecosystem — the package registry that underpins both languages — a natural and practically important lens through which to study AI-driven development patterns. Repositories that depend on npm packages leave observable, structured artefacts: lockfiles, dependency declarations, configuration files, and commit histories that can be analysed at scale.

Despite the velocity of tool adoption, the empirical picture of *how much* and *among whom* AI coding agents are actually being used in open-source development remains incomplete. Robbes and colleagues produced the first large-scale estimates — 22–28% adoption globally in established projects, rising to 71–76% in newly created repositories [robbesAgenticMuch2026, robbesAgenticVery2026] — but their studies span all GitHub languages and do not isolate the JS/TS/npm ecosystem. Similarly, Khosravani and Mockus [khosravani2026] identify a potential 30-fold undercounting in earlier single-signal studies but do not disaggregate by language or registry. No prior work focuses specifically on the npm ecosystem as a unit of analysis, despite it being the world's largest package registry with more than two million packages and tens of billions of weekly downloads [chatzidimitriou2018].

A second gap concerns the geographic distribution of AI coding agent adoption. Prior work has documented substantial cross-national variation in open-source participation [wachs2022], yet no study has compared AI adoption rates between developer communities in the Global North and the Global South. Egypt represents a particularly interesting case: it hosts one of the fastest-growing developer communities on GitHub in the Middle East and Africa region, yet its developers face different infrastructure constraints, different access conditions to premium AI tools, and different cultural norms around automation than developers in, say, the United States or Germany. Whether these structural differences translate into lower AI coding agent adoption — and by how much — is an open empirical question.

---

## 1.2 Research Questions

This thesis is structured around three research questions (RQs):

**RQ1 — Scope of adoption.**
What proportion of active JavaScript, TypeScript, and npm repositories on GitHub created since February 2025 show evidence of AI coding agent use, and how does this vary by package manager ecosystem (npm, Yarn, pnpm, Bun), primary language, and repository size?

**RQ2 — Signal undercounting.**
To what extent does relying on a single detection signal underestimate AI coding agent adoption compared with a multi-signal approach, and which signal types contribute most to detection coverage in the JS/TS/npm ecosystem?

**RQ3 — Community comparison.**
Do repositories with Egyptian-affiliated contributors show significantly different AI coding agent adoption rates than the global JS/TS/npm baseline, and what factors — tool accessibility, repository size, community type — correlate with any observed difference?

These three questions address, respectively, the scope, the measurement reliability, and the geographic dimension of AI coding agent adoption — the three gaps identified in the literature review (Chapter 2).

---

## 1.3 Scope and Delimitations

The study targets **public** GitHub repositories that satisfy all of the following criteria:

| Filter | Value | Reason |
|---|---|---|
| Created on or after | 2025-02-24 | Start of the high-growth agentic era |
| Stars | ≥ 4 | Excludes toy repositories |
| Commits | ≥ 50 | Ensures meaningful development history |
| Fork | No | Excludes derivative projects |
| JS+TS language bytes | ≥ 175,000 | Ensures genuine JS/TS project |

**Ecosystem** is operationalised via the lockfile present at the repository root:

| Lockfile | Ecosystem |
|---|---|
| `package-lock.json` | npm |
| `yarn.lock` | Yarn |
| `pnpm-lock.yaml` | pnpm |
| `bun.lockb` | Bun |
| `package.json` (no lockfile) | npm_no_lock |
| `deno.json` / `deno.jsonc` | deno |
| None of the above | vanilla |

The thesis focuses on the four lockfile-confirmed ecosystems and `npm_no_lock`, which together represent the canonical npm dependency surface.

**AI coding agent adoption** is detected via four families of signals:

1. **Configuration files** — `CLAUDE.md`, `.cursorrules`, `AGENTS.md`, etc.
2. **Commit message patterns** — `Co-authored-by: Claude`, `Generated with Claude Code`, etc.
3. **Pull request body patterns** — markers left by Copilot, Devin, Codex in PR descriptions
4. **AI-specific npm dependency declarations** — e.g., `@anthropic-ai/claude-code`, `@cursor/agent`

Repositories are classified as:
- **Agentic** — at least two distinct signal types present
- **AI-assisted** — exactly one signal type present
- **None** — no signals detected

The Egyptian corpus is constructed by mapping contributor GitHub profiles to Egypt using location fields, biography text, and organisational affiliations. The comparison is observational; no causal claims are made.

---

## 1.4 Methodology Overview

The study follows a seven-stage pipeline:

1. **Global corpus collection** (Stage 1a): collect all JS/TS repositories on GitHub that satisfy the inclusion criteria using the GitHub GraphQL Search API with date-windowed pagination to respect the 1,000-result-per-query cap.

2. **Ecosystem categorisation** (Stage 1b): classify each repository by its package manager via root-level lockfile detection.

3. **Stratified sampling** (Stage 1c): draw a stratified random sample proportional to ecosystem × language × size stratum, targeting approximately 3,500–5,000 repositories for Stage 4 analysis.

4. **Egyptian corpus construction** (Stage 2): identify the subset of repositories whose contributors include at least one developer with a verifiable Egyptian affiliation, using an eight-signal location inference pipeline.

5. **Signal detection** (Stage 4): scan each sampled repository for the four families of AI coding agent signals; output per-repository signal vectors and adoption-level classifications.

6. **Statistical comparison** (Stage 5): compare global and Egyptian adoption rates using Fisher's exact test; compare repository characteristics (stars, commits, age) using Mann-Whitney U tests; apply Benjamini-Hochberg correction for multiple comparisons.

7. **Synthesis** (Stage 6): interpret quantitative results in the context of the literature; surface qualitative patterns by inspecting configuration file content and commit message phrasing.

The pipeline is implemented entirely in Python 3.11, using the GitHub GraphQL and REST APIs.

---

## 1.5 Contributions

This thesis makes three contributions to the empirical software engineering literature:

1. **First ecosystem-scoped adoption estimate.** By restricting the corpus to the JS/TS/npm ecosystem and classifying repositories by package manager, this study provides adoption estimates that practitioners and tool vendors can map directly to a specific technical community, rather than averaging across all GitHub languages.

2. **Multi-signal undercounting quantification.** By comparing single-signal and four-signal detection on the same corpus, the study provides a concrete estimate of the coverage gap that afflicts studies relying on a single heuristic — directly addressing the measurement concern raised by Khosravani and Mockus [khosravani2026].

3. **Cross-community comparison.** The Egyptian-versus-global comparison provides the first empirical data point on AI coding agent adoption in a Middle Eastern/African developer community, contributing evidence relevant to questions about equitable access to AI development tools across the Global South.

---

## 1.6 Thesis Structure

| Chapter | Content |
|---|---|
| Chapter 2 — Literature Review | AI coding agent definitions, empirical adoption studies, detection methodology, developer interaction research, the JS/TS/npm ecosystem, geographic dimensions |
| Chapter 3 — Methodology | Data collection pipeline, corpus construction, signal detection algorithm, statistical analysis plan |
| Chapter 4 — Results | Quantitative findings for each of the three research questions |
| Chapter 5 — Discussion | Interpretation of findings, threats to validity, implications for tool developers and researchers |
| Chapter 6 — Conclusion | Summary of contributions and directions for future work |

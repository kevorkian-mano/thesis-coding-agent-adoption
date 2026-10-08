# Chapter 2 — Literature Review

This chapter surveys the body of work that contextualises, motivates, and directly informs the present study. The review is organised into six thematic sections: the emergence and definition of AI coding agents (§2.1); empirical studies of adoption rates and trends on GitHub (§2.2); detection methodology and the multi-signal challenge (§2.3); how developers interact with and adopt AI tools (§2.4); the JavaScript, TypeScript, and npm ecosystem as a research subject (§2.5); and geographic dimensions of open-source software development (§2.6). The chapter concludes by synthesising the identified research gaps that this thesis addresses (§2.7).

---

## 2.1 AI Coding Agents: Emergence and Definitions

The term *coding agent* refers to an AI system embedded in an autonomous loop that plans a sub-task, executes an action (writing or modifying code, running tests, reading documentation), observes the result, and iterates until a goal is reached [robbesAgenticMuch2026]. This distinguishes agents from earlier AI coding *assistants*, which provide suggestions inline but require the human to accept each change individually. The distinction is operationally significant: an assistant leaves a trace only when the developer accepts a suggestion, whereas an agent may author entire functions, write tests, and open pull requests autonomously, leaving a richer and more diverse set of observable artefacts.

The practical frontier between assistants and agents is blurred by how tools are configured. GitHub Copilot, for example, operates as an autocomplete assistant in its default IDE mode but transitions to an agentic mode when given access to a terminal or a repository via Copilot Workspace. Similarly, Cursor and Windsurf expose both completion and multi-step agentic modes within the same interface. Chatlatanagulchai et al. [chatlatanagulchai2025] document the growth of *context files* — configuration artefacts such as `CLAUDE.md`, `.cursorrules`, and `AGENTS.md` — which signal that a developer has configured an agent to operate with project-level instructions rather than just accepting inline suggestions. The presence of such files is the most reliable publicly observable signal that agentic (as opposed to merely AI-assisted) development is taking place.

**Key AI coding tools and their approximate launch dates:**

| Tool | Vendor | Mode | Launch |
|---|---|---|---|
| GitHub Copilot | GitHub/Microsoft | Assistant + Agent | Jun 2021 |
| Cursor | Anysphere | Assistant + Agent | 2023 |
| Aider | Paul Gauthier | Agent (CLI) | 2023 |
| Devin | Cognition AI | Agent (full) | Mar 2024 |
| Claude Code | Anthropic | Agent (CLI) | Mar 2025 |
| Windsurf | Codeium | Assistant + Agent | Nov 2024 |
| Gemini Code Assist | Google | Assistant + Agent | 2024 |

The most consequential tool for the npm ecosystem is Claude Code (launched March 2025), which targets command-line-first developers and stamps every commit it authors with a `Co-Authored-By: Claude <noreply@anthropic.com>` trailer by default [robbesHeuristics2026]. This default behaviour makes Claude Code the most detectable agent in repository mining studies.

Galster et al. [galsterConfig2026] conducted a large-scale empirical analysis of configuration artefacts across 4,738 repositories, finding 148,519 AI-co-authored commits and 15,591 configuration artefact files. TypeScript was the most represented primary language (24.5% of repos in their sample), providing early evidence that the npm ecosystem is a particularly active site of AI agent adoption. A companion study [galsterHarness2026] characterised the structure of agent harness files, finding that 85.5% of skill definitions lack dynamic scripts, revealing that much agentic configuration is declarative rather than programmatic.

---

## 2.2 Empirical Studies of Coding Agent Adoption

The two most comprehensive empirical studies of coding agent adoption on GitHub are the *Agentic Much?* [robbesAgenticMuch2026] and *Agentic Very Much!* [robbesAgenticVery2026] papers by Robbes et al., which together establish the baseline adoption rates against which this thesis measures the JavaScript/TypeScript ecosystem specifically.

### 2.2.1 Adoption in Established Repositories

Robbes et al. [robbesAgenticMuch2026] studied **128,018 GitHub repositories** across all languages using a snapshot dated 21 February 2026. Applying a taxonomy of 196 heuristics covering 63 agents, they found an overall adoption rate of **22.20%–28.66%**, depending on which heuristic set is used. The 6.46 percentage-point gap between these bounds represents repositories that are missed when a narrower signal set is applied — the *undercounting delta* that this thesis explicitly quantifies for the JS/TS ecosystem.

Key patterns from Robbes et al. that motivate this thesis's design:

- Adoption is **positively correlated with repository size, activity, and star count** → justifies size-stratified sampling in Stage 1
- AI-generated commits are **3× larger** than human commits (median 31 vs. 11 added lines)
- Most common task type: **feature work (35.7%)**, followed by bug fixing (29.9%)
- Rapid acceleration of adoption from mid-2025, coinciding with Claude Code release and agentic Cursor/Copilot modes

A crucial limitation: the cross-language aggregation conceals ecosystem-specific patterns. The 22–28% figure pools together low-adoption ecosystems (e.g. legacy C repositories) with potentially high-adoption ecosystems such as npm. This aggregation gap is the primary scope motivation for the present thesis.

### 2.2.2 Adoption in New Repositories

A companion study [robbesAgenticVery2026] restricted analysis to **12,794 repositories *created* after 29 August 2025** — paralleling this thesis's `created:>=2025-02-24` filter.

Results in new repositories:

| Metric | New repos | Established repos |
|---|---|---|
| Adoption rate | **71.83%–76.15%** | 22.20%–28.66% |
| Median commit agent ratio | ~30% | ~10% |
| "Pervasive" adoption (>50% commits by agent) | 41.2% | 21.1% |

Claude Code accounts for approximately **3× more signals** than Copilot in new repositories, consistent with its more aggressive default attribution behaviour and CLI-first design.

These findings motivate the creation date filter applied in Stage 1: repositories created before the agentic era were built without agents from day one; including them conflates non-adoption with *pre-adoption*, inflating the apparent non-adoption rate.

### 2.2.3 A Census-Scale Study

Khosravani and Mockus [khosravani2026] surveyed over **180 million GitHub repositories** using four signal types: bot account authorship (Type A), commit message trailers (Type B), author email patterns (Type C), and configuration file presence (Type D). Their central finding: single-signal bot-account detection misses **up to 30×** the volume of Claude Code commits detected by the full multi-signal approach — the strongest empirical evidence for why any single-signal methodology produces a severe lower bound. The study also documents 320,000+ AI-authored commits per month as of early 2026.

---

## 2.3 Detection Methodology and the Multi-Signal Challenge

Translating "does this repository use AI coding agents?" into an operational answer requires observable signals. The literature converges on four families [robbesHeuristics2026, galsterConfig2026, khosravani2026]:

**1. Configuration artefacts**
Files at the repository root that configure an agent's behaviour — `CLAUDE.md`, `AGENTS.md`, `.cursorrules`, `.aider.conf.yml`, `.roomodes`, and others. Galster et al. [galsterConfig2026] catalogue 15,591 such files across their corpus. These signals have **high precision** (a `CLAUDE.md` file is nearly unambiguous evidence of intentional Claude Code use) but **limited recall** (many teams use agents without creating configuration files).

**2. Commit message trailers**
The `Co-Authored-By:` trailer is injected by several agents by default, most notably Claude Code (`noreply@anthropic.com`). Robbes et al. [robbesHeuristics2026] document 2.7 million commits carrying this email address and catalogue the full set of trailer patterns used by 63 agents. Trailer-based detection has **high precision** but is easily suppressed by developers who clean their commit history.

**3. Pull request markers**
Agents that operate in PR-creation mode (Copilot, Devin, Codex) leave markers in PR bodies, branch names (`copilot/fix-*`, `codex/*`), and PR labels. Robbes et al. [robbesHeuristics2026] document 2.1 million branches with the `codex/` prefix. These signals are **PR-scope only** and miss commit-level agent usage.

**4. Bot account authorship**
Some agents operate as registered GitHub apps (e.g. `github-copilot[bot]`, `devin-ai-integration[bot]`), making their commits attributable directly via the author login. This is the **highest-precision signal** but covers only a minority of agent types.

Ghaleb [ghaleb2026] trained an XGBoost/Random Forest classifier on 33,580 pull requests with **97.2% F1-score**. The classifier's key features include: multiline commit density (Codex: 67.5%), PR description length (Copilot: 38.4%), bullet-point formatting (Cursor: 17.2%), and conditional statement density (Claude Code: 27.2%). While achieving high accuracy, this approach requires labelled training data and is therefore complementary rather than a direct substitute for heuristic-based detection.

Mao et al. [mao2026] demonstrate that restricting detection to a single signal type systematically undercounts adoption. The present thesis operationalises this insight by reporting both a *single-signal* rate (commit trailers only, for comparability with prior work) and a *multi-signal* rate (all signal types), treating the gap between them as an estimate of the undercounting delta.

The study also distinguishes between two adoption levels:
- **AI-assisted** — sparse, isolated signals (a single commit trailer, no configuration file); tool used occasionally without workflow integration
- **Agentic** — configuration file present, or multiple signal types co-occur, or signals appear with high frequency; systematic integration of the agent into the development process

---

## 2.4 Developer Interaction with AI Coding Tools

Understanding why some repositories produce observable agent signals while others do not requires insight into how developers interact with these tools in practice.

### 2.4.1 Bimodal Interaction Patterns

Barke et al. [barke2023] conducted a grounded theory study of 20 programmers using GitHub Copilot, identifying a stable **bimodal interaction pattern**:

| Mode | Trigger | Code prompts | Comment prompts | Time |
|---|---|---|---|---|
| **Acceleration** | Developer knows what to write | 71.4% | — | ~105 min |
| **Exploration** | Developer is uncertain | — | 57.2% | ~249 min |

The dominant determinant of mode: **task familiarity**. Familiar logic drives acceleration, unfamiliar APIs drive exploration.

Implications for this thesis:
1. Exploration-mode interactions (natural-language comments, large generated blocks) are **more likely to leave detectable traces** in commits and PRs
2. Developer communities who work predominantly in unfamiliar territory (students, developers new to an ecosystem) may produce **richer agent traces** than experienced developers in acceleration mode

### 2.4.2 Productivity and Acceptance Rates

Ziegler et al. [ziegler2022] studied 2,631 GitHub Copilot users matched to four weeks of IDE telemetry:

- Overall acceptance rate: **27%**, with users accepting >31 suggestions/day on average
- Acceptance rate was the strongest predictor of self-reported productivity (*r* = 0.24, *p* < 0.0001)
- JavaScript acceptance rate: **30.8%** vs. TypeScript: **26.3%** — consistent with JS's looser type system reducing suggestion rejections

Subsequent work extended the evidence to PR level:

- AI-assisted PRs accepted at **83.8%** vs. human PRs at **91.0%** [ogenrwot2026]
- AI-authored commits reverted more frequently: Copilot 7.6%, Claude Code 7.2% vs. human 4.7% [oukhay2026]
- AI assistance increases code review comment volume without proportionally increasing review quality [watanabe2025]

---

## 2.5 The JavaScript, TypeScript, and npm Ecosystem

The selection of the JS/TS/npm ecosystem as the unit of analysis is motivated by three converging lines of evidence: ecosystem scale, tool affinity, and research gap.

### 2.5.1 Ecosystem Scale and Growth

GitHub Octoverse 2025 [octoverse2025] documents:
- TypeScript overtook Python as the most widely used language on GitHub in August 2025
- **2,636,006 monthly TypeScript contributors** — year-on-year increase of 66.6%
- The report explicitly attributes this growth to AI coding agent adoption: TypeScript's strict typing and comprehensive IDE tooling make it well-suited for agentic code generation

The npm registry is the world's largest software package registry. Chatzidimitriou et al. [chatzidimitriou2018] characterised it through the npm-miner infrastructure:
- 598,862 packages analysed
- Mean package: **4.01 direct dependencies**, **1,577 lines of code**
- Quality metrics follow heavily skewed power-law distributions

These characteristics motivate the lockfile filter in this thesis: a repository containing `package.json` alongside a lockfile demonstrates active npm dependency management, distinguishing it from repositories where npm is incidental.

### 2.5.2 Ecosystem Affinity with AI Coding Agents

Evidence from configuration artefact studies confirms npm's disproportionate affinity with AI coding agents:

- TypeScript is the most common primary language (24.5%) in repositories containing agent configuration files [galsterConfig2026]
- TypeScript is the top language (27.8%) in repositories with agent skill definitions [galsterHarness2026]
- Claude Code is dominant in new-project repositories by **3× over Copilot** — its CLI-first design integrates naturally with the npm toolchain [robbesAgenticVery2026]

Marková [markova2025] documents a migration trend from JavaScript to TypeScript driven partly by the desire to improve AI coding tool performance: typed codebases produce fewer incorrect suggestions and require less correction.

### 2.5.3 GitHub as a Data Source

Kalliamvakou et al. [kalliamvakou2016] analysed 6.8 million public GitHub repositories and found:

- 67% have only a single committer
- Median project lifespan: 9.9 days
- Only 12.5% were active in the preceding month
- Only 63.4% of random-sample projects were genuine software development efforts

These findings directly inform this thesis's corpus construction:

| Filter | Addresses |
|---|---|
| Stars ≥ 4 | Excludes invisible/abandoned projects |
| Commits ≥ 50 | Excludes trivial or one-off projects |
| Created ≥ 2025-02-24 | Ensures access to mature agentic tools throughout project lifetime |
| Fork = false | Excludes derivative repositories |

Dabić et al. [dabic2021] provide additional methodological grounding: star-based stratification produces corpora with stable cross-study comparability properties.

---

## 2.6 Geographic Dimensions of Open-Source Software Development

The geographic comparison between Egyptian and global JS/TS developers constitutes the second research question of this thesis.

### 2.6.1 Geographic Distribution of OSS Contribution

Wachs et al. [wachs2022] conducted the most comprehensive empirical study of geographic patterns in open-source software on GitHub, finding:

- OSS contribution is strongly concentrated in North America and Western Europe
- Measurable correlation between a country's GDP per capita and the visibility of its developers' OSS contributions
- GitHub profile location self-reporting is a practical (if imperfect) basis for geographic attribution
- The blank-location population introduces systematic undercoverage of lower-income-country developers

This last limitation motivates the snowball expansion component of Stage 2 of this thesis, which recovers Egyptian developers who are socially connected to location-tagged Egyptian accounts but do not themselves report a location.

### 2.6.2 The Egyptian Developer Community

Egypt is the most populous Arabic-speaking country with a rapidly growing technology sector (Cairo University, AUC, GIU, and others producing large annual cohorts of software engineering graduates). Egyptian developers are a particularly interesting case because they combine:

- **(a)** A predominantly **English-language professional coding environment** (reducing language-barrier confounds)
- **(b)** An **active GitHub presence** — Stage 2a identified 1,876 seed accounts through self-reported Egyptian location strings in both English (*Egypt*, *Cairo*, *Alexandria*, *Giza*) and Arabic (*مصر*, *القاهرة*, *الإسكندرية*, *الجيزة*)
- **(c)** A development context characterised predominantly by **personal, academic, and small-scale commercial projects** (strong skew toward low-star repositories — OBS-001)

No prior study has examined AI coding agent adoption specifically within the Egyptian or MENA developer community. This thesis is therefore the first to test whether the 22–76% adoption range documented globally holds within a specific national developer community.

---

## 2.7 Research Gaps

The foregoing review identifies three research gaps that the present thesis directly addresses.

**Gap 1 — The Ecosystem Scope Gap.**
All major empirical studies of coding agent adoption report cross-language aggregate rates [robbesAgenticMuch2026, robbesAgenticVery2026, khosravani2026]. No study has measured adoption specifically within the JavaScript/TypeScript/npm ecosystem, despite this ecosystem being the most active site of agent adoption according to configuration artefact evidence [galsterConfig2026, octoverse2025]. The aggregate rates therefore provide a lower bound for what should be expected within npm, but cannot answer whether JS/TS developers adopt more, less, or differently than the general GitHub population.

**Gap 2 — The Undercounting Gap.**
The 6.46 percentage-point gap between the narrow and broad heuristic sets in Robbes et al. [robbesAgenticMuch2026], and the 30× undercounting factor in Khosravani and Mockus [khosravani2026], establish that single-signal detection severely misrepresents true adoption. However, no study has quantified this undercounting delta specifically for the JavaScript/TypeScript ecosystem, where the npm package dependency infrastructure provides a fifth signal type not applicable to other ecosystems.

**Gap 3 — The Community Comparison Gap.**
Prior adoption studies report blended figures that obscure community-level variation. The geography of OSS contribution is well-documented [wachs2022], but the intersection of geographic community membership and AI coding agent adoption has not been studied. In particular, no prior work has investigated whether an adoption gap between high-income and lower-income developer communities — predicted by the Wachs et al. framework and motivated by the cost and discoverability of agentic tools — is observable in repository-level adoption signals.

---

**Together, these three gaps frame the contributions of the present thesis:**
- Gap 1 → RQ1: quantify adoption within the JS/TS/npm ecosystem by package manager, language, and size
- Gap 2 → RQ2: report both single-signal and multi-signal rates to estimate the undercounting delta
- Gap 3 → RQ3: compare Egyptian and global adoption rates stratified by repository size

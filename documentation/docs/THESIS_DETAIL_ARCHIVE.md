# Thesis Detail Archive

Detailed passages removed from the thesis for conciseness but preserved here
for reuse in the methodology chapter, appendix, or discussion chapter.

---

## intro.tex — Section 1.4 Scope and Delimitations (original full text)

```latex
The study targets \emph{public} GitHub repositories that meet all of the
following criteria: created on or after 24 February 2025 (the start of the
high-growth agentic era); at least four stars (to exclude toy repositories
and forks of popular projects); at least fifty commits (to ensure a meaningful
development history); not themselves forks; and with at least 175\,000 bytes
of combined JavaScript and TypeScript source code (to confirm that JS/TS is
the primary language of the project).

\emph{Ecosystem} is determined by the lockfile present at the repository
root: \texttt{package-lock.json} (npm), \texttt{yarn.lock} (Yarn),
\texttt{pnpm-lock.yaml} (pnpm), \texttt{bun.lockb} (Bun). Repositories with
\texttt{package.json} but no lockfile are classified as \texttt{npm\_no\_lock};
repositories with \texttt{deno.json} are classified as \texttt{deno};
repositories with neither are classified as \texttt{vanilla}. The thesis
focuses on the four lockfile-confirmed ecosystems and \texttt{npm\_no\_lock},
which together represent the main npm dependency surface.

\emph{AI coding agent adoption} is detected using four families of signals
adapted from Robbes et al.~\cite{robbesHeuristics2026} and Galster et al.\
\cite{galsterConfig2026}: (1) configuration files (\texttt{CLAUDE.md},
\texttt{.cursorrules}, \texttt{AGENTS.md}, etc.); (2) commit message patterns
left by agents (\texttt{Co-authored-by: Claude},
\texttt{Generated with Claude Code}, etc.); (3) pull request body patterns;
and (4) AI-specific npm dependency declarations (e.g.\
\texttt{@anthropic-ai/claude-code}, \texttt{@cursor/agent}). Repositories
are classified as \emph{agentic} if they show at least two distinct signal
types, \emph{AI-assisted} if they show exactly one type, and \emph{none}
otherwise.

The Egyptian corpus is built by matching contributor GitHub profiles to
Egypt using location fields, biography text, and organisational affiliations.
The comparison is observational; no causal claims are made.
```

**Where to reuse:** The lockfile classification detail belongs in
`methodology.tex` Section on corpus construction. The signal family detail
(CLAUDE.md, .cursorrules, exact trailer strings) belongs in `methodology.tex`
Section on detection algorithm. The Egyptian identity inference detail belongs
in `methodology.tex` Section on the Egyptian corpus.

---

## Why commit size was not used as a detection signal

**Short answer:** Commit size is an indirect statistical indicator, not direct evidence. It requires machine learning and labeled training data to use correctly, neither of which is available for the JS/TS ecosystem.

**The distinction:**
- Our signals (Co-Authored-By trailer, CLAUDE.md, .cursorrules, copilot/ branch names) are **direct evidence** — they literally say an agent was present.
- Commit size is **indirect evidence** — AI commits tend to be larger on average, but so do human refactors and bulk edits. On its own it produces too many false positives.

**Why Ghaleb's ML approach uses it but we do not:**
Ghaleb trains an XGBoost/Random Forest classifier on 33,580 labeled pull requests. Commit size is one of ~30 features; the model learns the correct weight for it in combination with the others. Without a labeled dataset of AI vs. human commits specifically for JS/TS repos, there is no way to calibrate the threshold. Using a raw "large commit = AI" heuristic would flag every human refactor as AI adoption and inflate the rate.

**Additional problem:** A developer who squashes commits or writes small focused commits with Claude Code would look "human-sized" and be missed. Commit size is not a robust standalone signal.

**Where to mention in the thesis:** In `methodology.tex`, in the section justifying the choice of detection signals, add a sentence explaining that behavioral/statistical signals (commit size, PR description length) were excluded because they require labeled training data and produce false positives without a calibrated model. Cite Ghaleb~\cite{ghaleb2026} as evidence that the approach works when labels are available, but note labels do not exist for the JS/TS ecosystem specifically.

---

## litrev.tex — Section 2.6.2 The Egyptian Developer Community (original full text)

Archived for later discussion with supervisor before finalising.

```latex
Egypt is the most populous Arabic-speaking country and has a rapidly growing
technology sector. Several universities, including Cairo University, the
American University in Cairo, and the German University in Cairo, produce
large annual cohorts of software engineering graduates. Egyptian developers are a useful group for AI adoption studies for several
reasons. They largely write code and documentation in English, which avoids
the language-related complications that arise when studying developer
communities where the primary language is not English. They also have a
visible presence on GitHub: a location-based search for Egyptian developer
accounts identified over 1,800 accounts directly using Egyptian city and
country names in both English and Arabic, and a further network expansion
step raised this to over 26,000 accounts. In addition, Egyptian developers
tend to work on personal, academic, and small-scale commercial projects
rather than large open-source libraries, which means the Egyptian corpus
in this study skews toward lower-star repositories, reflecting a different
type of development activity than the global sample.

No prior study has examined AI coding agent adoption within the Egyptian or
MENA developer community. The closest work is Wachs et al.~\cite{wachs2022},
which documents the geographic distribution of OSS contribution but does not
address tool adoption. This thesis is therefore the first to test whether the
22--76\% adoption range documented globally also holds within a specific
national developer community, and to investigate what mechanisms, including
team composition and international collaboration, might explain differences.
```

**Questions to discuss with supervisor:**
- How much detail about Egypt's developer community is appropriate in a litrev section vs. methodology/results?
- Is it appropriate to describe corpus construction details (1,800 accounts, 26,000 via expansion) in the litrev, or should that stay in methodology?
- The claim that Egyptian developers tend toward personal/academic projects rather than large OSS libraries — is this supported by a citation or is it an observation from the corpus? If the latter, it belongs in results/discussion, not litrev.
- The "no prior study" claim needs to be verified before final submission.

---

## Bimodal interaction patterns (Barke et al.) — can we study this on our corpus?

**Short answer:** Not directly. Barke et al. used lab-based IDE telemetry (screen recordings, prompt logs, task timings). That data does not exist in GitHub repositories. We only have commits, PR content, file names, and timestamps.

**However, our corpus contains proxies that connect to the same framework:**

| Barke et al. concept | Our corpus proxy |
|---|---|
| Acceleration mode (AI used for speed, routine tasks) | Single commit-trailer signal only, no config file; short time-to-first-signal |
| Exploration mode (AI used to discover APIs, unfamiliar territory) | Config file present (deliberate setup); multi-signal repos; born-agentic pattern |
| Task familiarity drives the mode | Language proxy: JS (looser types, more uncertainty) vs TS (tighter, more acceleration) |
| Exploration interactions take 2x longer | Late adopters (signal weeks/months after creation) vs born-agentic (signal within first week) |

**Key discussion point:**
Born-agentic repos (~33% of global adopters, ~29% Egyptian) reflect developers who planned AI use from the first commit — consistent with acceleration mode built into their workflow from the start. Late adopters who add AI signals weeks after creation more likely represent exploration mode: bringing AI in to solve a specific unfamiliar problem. The lower born-agentic share in Egypt (29% vs 33%) may suggest slightly more exploration-driven adoption in that community, though the sample size limits this inference.

**Where to use in the thesis:** `discussion.tex` — connect the born-agentic rate and single-signal vs. multi-signal split back to the Barke et al. framework. This shows the discussion is grounded in prior interaction research, not just descriptive numbers. Also note the limitation: without IDE telemetry, mode classification from repository data alone is an approximation.

---

## Ziegler et al. JS vs TS acceptance rates — can we study this on our corpus?

**Short answer:** Not directly. Ziegler et al. used IDE telemetry from 2,631 Copilot users tracking every suggestion accepted or rejected. We only see accepted suggestions that reached commits — rejected suggestions are invisible in repository data.

**What we cannot study:**
- Acceptance rate (we never see rejections, only what made it into the codebase)
- Working hours vs. weekend difference at the session level

**What we CAN study (partial proxies):**

| Ziegler et al. finding | Our corpus equivalent |
|---|---|
| JS higher acceptance rate than TS (30.8% vs 26.3%) | JS adoption rate vs TS adoption rate |
| Weekend vs. weekday timing | Commit timestamps on AI-signal commits — could cluster by day of week |

**Key tension worth raising in the discussion chapter:**
Ziegler found JS developers accept *more* individual suggestions per session (30.8% vs 26.3%), yet our corpus shows TS developers adopt AI tools at a *higher overall rate* (71.4% vs 57.9% globally; 46.0% vs 25.0% in Egypt). These are not contradictory findings — they measure different things. Individual acceptance rate measures how often a developer clicks "accept" in a session. Adoption rate measures whether a developer integrates AI into their regular workflow at all. The likely reconciliation: TypeScript's strict typing helps AI tools generate more *correct* code overall, so TS developers find the tools more useful in the long run and are more likely to keep using them, even if each individual suggestion is accepted less often because the bar for correctness is higher.

This reconciliation is a strong paragraph for `discussion.tex` — it shows your findings are consistent with prior work at a deeper level, not just surface agreement or disagreement.

**Where to use in the thesis:** `discussion.tex`, in the section interpreting the JS vs TS adoption gap. Cite both Ziegler~\cite{ziegler2022} and the language breakdown from RQ1. Note the limitation that IDE telemetry data is not available for this study.

---

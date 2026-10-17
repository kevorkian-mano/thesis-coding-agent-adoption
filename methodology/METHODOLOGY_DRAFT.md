# Methodology Draft (Revised)
## Coding Agent Adoption in JavaScript/TypeScript/npm Repositories on GitHub

**Student:** Manuel Youssef Haik Kevorkian
**Date:** October 2026
**Status:** Active draft — reflects supervisor feedback received October 2026

> **Note:** The previous methodology (Egypt-focused, 4,500-repo sample) is archived in
> `METHODOLOGY_DRAFT_OLD.md`. The Egyptian corpus work (83 repos, 41.0% adoption) is
> preserved as supplementary/additional work, not the main study.

---

## 1. What Changed and Why

The supervisor feedback introduced two key changes:

**Change 1 — From Egypt-specific to geographic.**
The thesis no longer focuses specifically on Egyptian developers as the comparison group.
Instead, the main study measures AI coding agent adoption across all countries present
in the corpus and ranks them from highest to lowest. Egypt becomes one data point in
that ranking rather than the focus of a dedicated comparison.

**Change 2 — No pre-sampling.**
The previous methodology sampled 4,500 repos from 60,129 before geographic labeling.
The supervisor flagged this as methodologically weak: a random sample drawn before
country is known cannot guarantee representative coverage of any specific country.
The new methodology removes sampling as a core step. Instead, a layered detection
approach processes the full 60,129-repo corpus cost-efficiently, applying cheap signals
first and expensive signals only where needed. This eliminates sampling bias entirely.

---

## 2. Revised Research Questions

| # | Research Question |
|---|---|
| **RQ1** | What is the overall AI coding agent adoption rate in the JavaScript, TypeScript, and npm ecosystem on GitHub among repositories created since February 2025? |
| **RQ2** | How much does relying on a single detection signal undercount AI coding agent adoption compared to a multi-signal approach, and which signal types contribute most to detection coverage? |
| **RQ3** | How does AI coding agent adoption vary geographically across developer communities? Which countries show the highest and lowest adoption rates, and what repository or ecosystem characteristics correlate with geographic differences? |

RQ3 replaces the previous Egypt-vs-global binary comparison with a full geographic
ranking. Egypt will appear as one country in the RQ3 results.

---

## 3. New Pipeline Overview

```
Stage 1 — Repo Collection (COMPLETE, fully reusable)
  60,129 JS/TS repos collected with quality filters
  Ecosystem categorised by lockfile type
  ↓
Stage 2 — Owner Location Detection (NEW)
  Phase 1: Fast pass — location field for all 60,129 owners
  Phase 2: Deep inference — bio/company/email/network for unresolved owners
  Output: every repo labelled with inferred country (or not_specified)
  ↓
Stage 3 — Layered Agentic Signal Detection (REDESIGNED)
  Pass 1: Config file check (GraphQL) — label agentic immediately if found
  Pass 2: Commit trailer scan (REST) — on unclassified repos only
  Pass 3: Deep scan (REST, full) — on still-unclassified repos only
  Output: every repo labelled with adoption level
  ↓
Stage 4 — Geographic Analysis
  Join repo adoption labels with owner country labels
  Compute adoption rate per country
  Rank countries descending by adoption rate
  Statistical tests for geographic variation (RQ3)
  ↓
Stage 5 — Reporting
  RQ1: Overall adoption rate
  RQ2: Undercounting delta
  RQ3: Country-level ranking and correlates
```

No sampling step. The layered detection makes full-corpus processing feasible.

---

## 4. Stage 1 — Repo Collection (Complete, No Changes)

Stage 1 is fully reusable. Nothing changes here.

**What was done:**
- 60,129 repositories collected via GitHub GraphQL Search API
- Filters: created >= 2025-02-24, stars >= 4, commits >= 50, not fork, JS+TS bytes >= 175,000
- Ecosystem categorised by lockfile: npm, pnpm, yarn, bun, npm_no_lock, vanilla

**Scripts: keep as-is**
- `scripts/stage1/stage1a_collect_repos.py` → keep
- `scripts/stage1/stage1b_categorize_ecosystem.py` → keep
- `scripts/stage1/stage1c_sample.py` → **archive** (sampling no longer core methodology)

**Data files: keep**
- `data/stage1/global_corpus.csv` (60,129 repos) → keep — this is the base of everything
- `data/stage1/ecosystem_audit.csv` → keep
- `data/stage1/sample_corpus.csv` → **archive** (the old 4,500 sample is no longer the main corpus)
- `data/stage1/strata_audit.csv` → **archive**

---

## 5. Stage 2 — Owner Location Detection (New)

### 5.1 Goal

Every repository in the 60,129-repo corpus needs a country label. The country is inferred
from the GitHub profile of the repository owner. This replaces the old Stage 2
(which classified owners as Egyptian/not) and old Stage 3 (targeted Egyptian corpus).

The output of this stage is a file where every repo has:
- `owner_login`
- `inferred_country` (e.g., "Egypt", "United States", "Germany") or `not_specified`
- `location_confidence` (high / medium / low)
- `location_source` (which signal provided the country)

### 5.2 Phase 1 — Fast Location Pass (Script 2a)

**Input:** owner login list from global_corpus.csv (unique owners, ~40,000-50,000 unique)

**Method:** Batch GraphQL queries, 50 owners per request. For each owner, read only
the `location` field. Parse the location string against a lookup of country names,
major cities, and country codes in both English and common local spellings.

**Outcome per owner:**
- Location field contains a recognisable country → label with that country, confidence = high
- Location field is present but unrecognisable (e.g. "Earth", "Remote") → `not_specified`
- Location field is empty → `not_specified`

**Cost:** ~1,000 GraphQL requests for all unique owners. Fast — can run in under an hour.

**Expected result:** Based on prior Stage 2 experience, roughly 40% of owners will
have a parseable location field. The remaining ~60% pass to Phase 2.

### 5.3 Phase 2 — Deep Location Inference (Script 2b)

**Input:** All owners labelled `not_specified` after Phase 1.

**Method:** Apply deeper signals in order of API cost, same cascade logic as the old
Stage 2 but now outputting a country rather than a binary Egyptian flag:

| Signal | Source | What it detects | Cost |
|---|---|---|---|
| Bio text | `user.bio` | Country keywords, Arabic/regional text patterns | Low (profile already fetched) |
| Company field | `user.company` | Company name → known country, `.eg` / `.de` / `.uk` domains | Low |
| Email domain | `user.email` | Country-code TLDs (.eg, .de, .fr, .jp etc.) | Low |
| Organisation location | `user.organizations[].location` | Org has a parseable country location | Medium |
| Follower/following network | followers + following | Majority of located connections are from same country | Medium-High |

**Outcome per owner:**
- Enough signals converge on one country → label with that country, confidence = medium or low depending on signal strength
- Signals conflict or insufficient → `not_specified` (reported as a limitation)

**Important:** The goal is not to force a label on every owner. Owners that genuinely
cannot be located after all signals are reported as `not_specified` and are excluded
from the geographic analysis. This is methodologically honest.

### 5.4 Output

After both phases:
- `data/stage2/owner_locations.csv` — one row per unique owner, with country and confidence
- `data/stage2/repo_labelled.csv` — the full 60,129-repo corpus with country field joined in

### 5.5 Old Stage 2 and Stage 3 — Archive

All scripts and data from the old Egypt-specific work are archived, not deleted.
The Egyptian targeted corpus (83 repos, 41.0%) is preserved as supplementary work.

**Scripts to archive:**
- `scripts/stage2/stage2a_owner_profiles.py`
- `scripts/stage2/stage2b_social_signals.py`
- `scripts/stage2/stage2c_repo_signals.py`
- `scripts/stage2/stage2d_finalize.py`
- `scripts/stage3/stage3a_egypt_discovery.py`
- `scripts/stage3/stage3b_egypt_corpus.py`

**Data to archive:**
- `data/stage2/owner_signals.csv`
- `data/stage2/owner_signals_full.csv`
- `data/stage2/owners_final.csv`
- `data/stage2/egypt_corpus.csv`
- `data/stage2/coverage_stats.csv`
- `data/stage3/` (entire folder — Egyptian targeted corpus)

---

## 6. Stage 3 — Layered Agentic Signal Detection (Redesigned)

### 6.1 Why Layered

Running a full deep scan (300 commits + 200 PRs) on all 60,129 repos would require
millions of API calls and many days of compute time. The layered approach applies
cheap signals first. A repo that is labelled in Pass 1 never reaches Pass 2 or 3.
This makes full-corpus detection feasible without sampling.

### 6.2 Pass 1 — Configuration File Check (Script 3a)

**Input:** All 60,129 repos.

**Method:** Single GraphQL query per repo checks for the existence of known agent
configuration files at the repository root:

| File | Agent |
|---|---|
| `CLAUDE.md`, `AGENTS.md` | Claude Code |
| `.cursorrules`, `.cursorignore` | Cursor |
| `.aider.conf.yml` | Aider |
| `.roomodes`, `.windsurfrules` | Roo Code, Windsurf |
| `GEMINI.md` | Gemini CLI |
| `.github/copilot-instructions.md` | GitHub Copilot |

**Outcome:** If any file found → label repo **agentic** immediately. No further
processing. Config files are hard positives — nobody accidentally creates a `CLAUDE.md`.

**Cost:** GraphQL can batch multiple repos per request. Very fast across 60,129 repos.

**Expected yield:** Based on prior work, ~46% of repos have a config file. So roughly
28,000 repos are classified here, leaving ~32,000 for Pass 2.

### 6.3 Pass 2 — Commit Trailer Scan (Script 3b)

**Input:** Repos not classified in Pass 1 (~32,000 estimated).

**Method:** Fetch the most recent 100 commits per repo via GitHub REST API. Scan
commit messages for known agent trailer patterns:
- `Co-authored-by: Claude <noreply@anthropic.com>`
- `Co-authored-by: GitHub Copilot`
- `Co-authored-by: Devin`
- Branch name patterns: `copilot/`, `codex/`

**Outcome:**
- Trailer found → label **agentic** or **ai_assisted** depending on frequency
- No trailer found → pass to Pass 3

**Cost:** 1 REST call per repo (fetch commits endpoint). Medium cost — manageable
across ~32,000 repos with standard rate limiting.

### 6.4 Pass 3 — Deep Scan (Script 3c)

**Input:** Repos not classified in Pass 1 or 2. Expected to be a smaller subset.

**Method:** Full scan — up to 300 commits, PR bodies, PR branch names, PR labels,
author email patterns, npm dependency declarations. Same comprehensive detection as
the old Stage 4 script.

**Outcome:** Final adoption label for every remaining repo. Repos with no signal
after all three passes are labelled **none**.

### 6.5 Old Stage 4 — Archive

The old `scripts/stage4/stage4_detection.py` ran full deep scans on the 4,500-repo
sample. It is archived since the new pipeline replaces it with the three-pass approach
on the full corpus.

**Scripts to archive:**
- `scripts/stage4/stage4_detection.py`

**Data to archive:**
- `data/stage4/sample_corpus_detected.csv`
- `data/stage4/egypt_corpus_input_detected.csv`
- `data/stage4/signals_global.csv`
- `data/stage4/signals_egypt_corpus_input.csv`

---

## 7. Stage 4 — Geographic Analysis (New)

### 7.1 Join

Merge `repo_labelled.csv` (with country) and the detection output (with adoption level)
on `full_name`. Every repo now has: ecosystem, language, size, country, adoption level.

### 7.2 Analysis

**For RQ3:**
- Count repos per country, compute adoption rate per country
- Require minimum threshold (e.g. >= 10 repos) to report a country — below this the
  rate is too noisy to be meaningful
- Sort countries descending by multi-signal adoption rate
- For countries with enough repos, compute confidence intervals (Wilson)
- Identify top and bottom countries, note any patterns (region, income level, language)

**For RQ1:**
- Overall adoption rate across all 60,129 repos (or all that were detectable)
- Broken down by ecosystem, language, size — same dimensions as before

**For RQ2:**
- Single-signal vs multi-signal undercounting delta
- Which signal types contribute most to coverage

### 7.3 Statistical Tests

- RQ3: Kruskal-Wallis test across country groups (non-parametric, multiple groups)
  followed by pairwise Mann-Whitney U for significant pairs with BH correction
- Correlation between country-level adoption rate and external indicators if available
  (e.g. internet infrastructure index, developer population size)

---

## 8. Egypt as Supplementary Work

The Egyptian targeted corpus (83 repos, 41.0% adoption, corrected filter) is preserved
and can be reported in the thesis as:

1. A **validation check**: Egypt's adoption rate from the targeted corpus (41.0%) can
   be compared to Egypt's rate from the full geographic analysis. If they are consistent,
   this validates both methods.
2. A **methodological finding**: The filter correction (17.6% old vs 41.0% corrected)
   remains a finding about corpus construction methodology.
3. A **supplementary case study**: The detailed Egyptian owner profile analysis, tool
   loyalty, and Copilot-vs-OpenAI breakdown can be reported as additional depth on one
   specific community.

---

## 9. Script and Data File Structure Going Forward

### Scripts

```
scripts/
  stage1/
    stage1a_collect_repos.py          ✅ keep — repo collection
    stage1b_categorize_ecosystem.py   ✅ keep — ecosystem classification
    archived/
      stage1c_sample.py               📦 archived — sampling no longer core

  stage2/  (new purpose: owner location detection)
    stage2a_location_fast.py          🆕 to build — Phase 1 fast location pass
    stage2b_location_deep.py          🆕 to build — Phase 2 deep inference
    archived/
      stage2a_owner_profiles.py       📦 archived
      stage2b_social_signals.py       📦 archived
      stage2c_repo_signals.py         📦 archived
      stage2d_finalize.py             📦 archived

  stage3/  (new purpose: layered detection)
    stage3a_config_files.py           🆕 to build — Pass 1 config file check
    stage3b_commit_trailers.py        🆕 to build — Pass 2 commit trailer scan
    stage3c_deep_scan.py              🆕 to build — Pass 3 full deep scan
    archived/
      stage3a_egypt_discovery.py      📦 archived
      stage3b_egypt_corpus.py         📦 archived

  stage4/  (new purpose: geographic analysis + stats)
    stage4a_geographic_analysis.py    🆕 to build — join + country ranking
    stage4b_statistical_tests.py      🆕 to build — RQ1/RQ2/RQ3 formal tests
    archived/
      stage4_detection.py             📦 archived

  supplementary/  (Egyptian corpus work, preserved)
    egypt_stage4_results/             📦 keep for reference
    egypt_stage5_results/             📦 keep for reference
```

### Data Files

```
data/
  stage1/
    global_corpus.csv                 ✅ keep — 60,129 repos, base of everything
    ecosystem_audit.csv               ✅ keep
    archived/
      sample_corpus.csv               📦 archived — old 4,500 sample
      strata_audit.csv                📦 archived

  stage2/  (new outputs)
    owner_locations.csv               🆕 to produce — owner → country mapping
    repo_labelled.csv                 🆕 to produce — 60,129 repos with country field
    archived/
      owner_signals.csv               📦 archived
      owner_signals_full.csv          📦 archived
      owners_final.csv                📦 archived
      egypt_corpus.csv                📦 archived
      coverage_stats.csv              📦 archived

  stage3/  (new outputs — layered detection)
    pass1_results.csv                 🆕 to produce — config file classifications
    pass2_results.csv                 🆕 to produce — trailer classifications
    pass3_results.csv                 🆕 to produce — deep scan classifications
    corpus_detected_full.csv          🆕 to produce — all 60,129 with adoption label
    archived/
      (old stage3 Egyptian corpus files)

  stage4/  (new outputs — geographic analysis)
    country_adoption_rates.csv        🆕 to produce — per-country adoption rates
    country_ranking.csv               🆕 to produce — sorted descending
    rq1_results.json                  🆕 to produce
    rq2_results.json                  🆕 to produce
    rq3_results.json                  🆕 to produce
    archived/
      (old stage4 detection outputs on sample)

  supplementary/
    egypt_corpus_input_detected.csv   📦 keep — 83-repo Egyptian corpus results
    egypt_stage5_outputs/             📦 keep — breakdowns, profiles, temporal
    egypt_stage6_outputs/             📦 keep — statistical tests on Egyptian corpus
```

---

## 10. What We Know Already (Reusable Findings)

From the old methodology, these numbers remain valid and will feed into the new analysis:

| Finding | Value | Status in new thesis |
|---|---|---|
| Total JS/TS repos collected | 60,129 | Core — unchanged |
| Ecosystem distribution | npm 47%, pnpm 20.3%, vanilla 16.9% | Core — unchanged |
| Global adoption rate (4,500 sample) | 67.5% multi-signal | Preliminary estimate — will be updated with full corpus |
| Undercounting delta (sample) | 19.5 pp | Preliminary — will be recalculated on full corpus |
| Config file signal yield | ~46% of repos | Informs Pass 1 expected yield |
| Egyptian corpus adoption (targeted, 83 repos) | 41.0% | Supplementary |
| Filter correction finding | 17.6% vs 41.0% | Supplementary / methodological |

---

## 11. Pending Work (in order)

| # | Task | Depends on |
|---|---|---|
| 1 | Archive old scripts and data per Section 9 above | Nothing — do now |
| 2 | Build `stage2a_location_fast.py` | Stage 1 data (ready) |
| 3 | Run Stage 2a on all 60,129 owner logins | Script 2a |
| 4 | Build `stage2b_location_deep.py` | Stage 2a results |
| 5 | Run Stage 2b on not_specified owners | Script 2b |
| 6 | Build `stage3a_config_files.py` (Pass 1) | Stage 1 data (ready) |
| 7 | Run Pass 1 on all 60,129 repos | Script 3a |
| 8 | Build `stage3b_commit_trailers.py` (Pass 2) | Pass 1 results |
| 9 | Run Pass 2 on unclassified repos | Script 3b |
| 10 | Build `stage3c_deep_scan.py` (Pass 3) | Pass 2 results |
| 11 | Run Pass 3 on remaining unclassified repos | Script 3c |
| 12 | Build `stage4a_geographic_analysis.py` | Stage 2 + Stage 3 outputs |
| 13 | Run geographic analysis and produce country ranking | Script 4a |
| 14 | Run statistical tests (RQ1, RQ2, RQ3) | Stage 4a output |
| 15 | Update thesis chapters with new findings | All above |

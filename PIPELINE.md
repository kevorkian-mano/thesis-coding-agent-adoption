# Complete Research Pipeline

**Thesis:** Coding Agent Adoption in JavaScript/TypeScript/npm Repositories on GitHub  
**Student:** Manuel Youssef Haik Kevorkian  
**Last updated:** 2026-10-08

---

## Overview

```
STAGE 1 — Build the global JS/TS corpus
    ↓
STAGE 2 — Owner identity: profile & network signals (S1–S6)
    ↓
STAGE 3 — Owner identity: repo signals + Egyptian corpus finalization (S7–S9)
    ↓                 (runs in parallel with Stage 4)
STAGE 4 — AI coding agent signal detection
    ↓
STAGE 5 — Statistical analysis & comparison
```

Stage 2, Stage 3, and Stage 4 all read from `sample_corpus.csv`.  
Stage 2 and Stage 3 are sequential (Stage 3 needs Stage 2 output).  
Stage 4 is fully independent and can run in parallel with Stage 2/3.

---

## STAGE 1 — Corpus Collection & Sampling ✅

### Stage 1a — Global Corpus Collection
**Script:** `scripts/stage1/stage1a_collect_repos.py`  
**Status:** Complete

```
GitHub GraphQL Search API
        ↓
  Two passes (JavaScript, TypeScript)
  Date windows: 2025-02-24 → today
  Filters: stars≥4, commits≥50, lang_bytes≥175KB, fork=false
        ↓
  data/stage1/global_corpus_raw.csv  (archived)
```

**Result:** 60,129 repositories

---

### Stage 1b — Ecosystem Categorization
**Script:** `scripts/stage1/stage1b_categorize_ecosystem.py`  
**Status:** Complete

```
global_corpus_raw.csv
        ↓
  GraphQL: check 7 files per repo (package.json, lockfiles, deno.json)
  Classify: npm / pnpm / yarn / bun / npm_no_lock / vanilla / deno / unknown
        ↓
  data/stage1/global_corpus.csv      ← MASTER CORPUS
  data/stage1/ecosystem_audit.csv    ← breakdown table
```

**Result:**

| Ecosystem | Count | % |
|---|---|---|
| npm | 28,248 | 47.0% |
| pnpm | 12,229 | 20.3% |
| vanilla | 10,177 | 16.9% |
| npm_no_lock | 7,979 | 13.3% |
| yarn | 1,091 | 1.8% |
| deno | 250 | 0.4% |
| bun | 107 | 0.2% |
| unknown | 48 | 0.1% |

---

### Stage 1c — Stratified Random Sampling
**Script:** `scripts/stage1/stage1c_sample.py`  
**Status:** Complete

```
global_corpus.csv (60,129 repos)
        ↓
  Include: npm, pnpm, yarn, bun, npm_no_lock (thesis targets)
           vanilla (comparison group)
  Exclude: deno (different runtime), unknown (data quality)
        ↓
  Stratify: ecosystem × primary_language × size_stratum → 35 strata
  Allocate: proportional with minimum 30 per stratum
  Sample:   4,500 repos (random_seed=42)
        ↓
  data/stage1/sample_corpus.csv      ← INPUT FOR ALL DOWNSTREAM STAGES
  data/stage1/strata_audit.csv       ← per-stratum breakdown
```

**Result:** 4,500 repos — npm: 1,891 | pnpm: 909 | npm_no_lock: 656 | vanilla: 789 | yarn: 194 | bun: 61

---

## STAGE 2 — Owner Identity: Profile & Network Signals

**Goal:** For every repo in `sample_corpus.csv`, fetch the owner's GitHub profile and apply the first 6 location signals. Every owner accumulates a score — the higher the score the more confident the Egyptian classification.

**Scripts location:** `scripts/stage2/`

### Signal scoring system

| Signal | What it checks | Points |
|---|---|---|
| S1 | Profile location field = Egypt/Cairo/مصر/etc. | **10** |
| S2 | Bio has Arabic text or Egyptian keywords | **5** |
| S3 | Company field has Egyptian org names / .eg domain | **5** |
| S4 | Email has .eg TLD or Egyptian university domain | **8** |
| S5 | Member of a GitHub org with Egyptian location | **7** |
| S6 | ≥40% of followers/following are confirmed Egyptian | **5** |

**Hard negative:** S1 fires with an explicit non-Egyptian country → mark `not_egyptian`, skip remaining signals.

**Classification thresholds (applied in Stage 3b):**

| Score | Signals fired | Label | In Egypt corpus? |
|---|---|---|---|
| ≥ 10 | any | `egyptian_confirmed` | ✅ Yes |
| 5–9 | any | `egyptian_probable` | ✅ Yes (flagged) |
| 1–4 | ≥ 2 signals | `egyptian_probable` | ✅ Yes (flagged) |
| 1–4 | 1 signal only | `unconfirmed` | ❌ No — weak single signal |
| 0 | 0 | `unclassified` | ❌ No — no evidence found |
| S1 hard negative | — | `not_egyptian` | ❌ No — explicit non-Egyptian location |

**`unconfirmed`** = all 9 signals ran, only one weak signal fired — not enough evidence.  
**`unclassified`** = all 9 signals ran, zero evidence found — location genuinely unknown.  
Both are excluded from the Egyptian corpus and reported as undercoverage in coverage_stats.csv.

---

### Stage 2a — Owner Profile Fetch (S1–S4)
**Script:** `scripts/stage2/stage2a_owner_profiles.py` *(to be written)*

```
sample_corpus.csv
        ↓
  Extract unique owner_logins (~4,000–4,500 unique owners)
  Batch-fetch GitHub profiles via GraphQL (50 owners/request)
  Apply: S1 (location), S2 (bio), S3 (company), S4 (email)
        ↓
  data/stage2/owner_signals.csv
    columns: login, location_raw, bio, company, email,
             s1_score, s2_score, s3_score, s4_score,
             total_score, classification, evidence_json
```

**Cost:** ~90 GraphQL requests. Runs in minutes.  
**Expected:** ~35–45% of owners classifiable at this stage.

---

### Stage 2b — Social Signals (S5–S6)
**Script:** `scripts/stage2/stage2b_social_signals.py` *(to be written)*

```
owner_signals.csv  (only rows where total_score < 10)
        ↓
  For each unconfirmed owner:
    S5: fetch user.organizations → check org location fields
    S6: fetch followers + following (top 50 each)
        count Egyptian-confirmed connections
        if ≥40% → infer Egyptian (+5 points)
        ↓
  data/stage2/owner_signals.csv  (updated with s5_score, s6_score)
```

**Cost:** ~2–3 API calls per unconfirmed owner. Runs in 1–2 hours.

---

## STAGE 3 — Owner Identity: Repo Signals + Egyptian Corpus

**Goal:** For owners still unclassified after Stage 2, apply repo-level evidence (contributor locations, README language, dummy data patterns). Then finalize all scores, apply thresholds, and produce the Egyptian corpus.

**Scripts location:** `scripts/stage3/`

### Additional signals used in Stage 3

| Signal | What it checks | Points |
|---|---|---|
| S7 | ≥40% of repo contributors have confirmed Egyptian location | **7** |
| S8 | README/CONTRIBUTING has >10% Arabic characters | **3** |
| S9 | Code/fixtures contain Egyptian patterns (+20 phone, Cairo address, EGP, NID) | **4** |

---

### Stage 3a — Repo-Level Signals (S7–S9)
**Script:** `scripts/stage3/stage3a_repo_signals.py` *(to be written)*

```
owner_signals.csv  (only rows where total_score < 10)
sample_corpus.csv  (to get repos belonging to each owner)
        ↓
  For each unconfirmed owner's repos:

    S7 — Contributor consensus:
      GET /repos/{owner}/{repo}/contributors (top 20)
      Batch-fetch contributor profiles
      If ≥40% contributors are confirmed Egyptian → +7 points

    S8 — Arabic README:
      Fetch README.md content via GraphQL
      Count Arabic Unicode chars (U+0600–U+06FF)
      If Arabic ratio >10% → +3 points

    S9 — Egyptian dummy data:
      Scan README + test fixture files for:
        Egyptian mobile prefixes: 010, 011, 012, 015
        Country code: +20
        Currency: EGP, Egyptian Pound
        National ID: 14-digit starting with 2 or 3
      → +4 points (capped at 4 total for S9)
        ↓
  data/stage3/owner_signals_full.csv  (all 9 signals populated)
```

**Cost:** ~3–5 API calls per unconfirmed owner. Runs in 2–4 hours.

---

### Stage 3b — Finalize & Build Egyptian Corpus
**Script:** `scripts/stage3/stage3b_finalize.py` *(to be written)*

```
owner_signals_full.csv
sample_corpus.csv
        ↓
  Sum all signal scores per owner
  Apply classification thresholds
  Join owner classification back to sample_corpus.csv
  Compute OBS-016 location coverage statistics
        ↓
  data/stage3/owners_final.csv
    all owners: total_score, classification, confidence,
                evidence_json, location_source

  data/stage3/egypt_corpus.csv
    repos where owner is egyptian_confirmed or egyptian_probable

  data/stage3/coverage_stats.csv
    % owners with explicit location (S1)
    % inferred via signals S2–S9
    % still unknown
    breakdown by ecosystem and size_stratum
```

**No API calls. Runs in seconds.**

---

## STAGE 4 — AI Signal Detection ⏳

**Script:** `scripts/stage4/stage4_detection.py` *(updated, ready to run)*  
**Runs independently — does not depend on Stage 2 or Stage 3.**

```
sample_corpus.csv (~4,500 repos)
        ↓
  Pass 1 — Config file check (GraphQL, all 4,500 repos)
    Checks root tree for: CLAUDE.md, AGENTS.md, .cursorrules,
                          .aider.conf.yml, .roomodes, .windsurfrules,
                          GEMINI.md, .continue, .codeium, etc.
    Also checks: .github/copilot-instructions.md

  Pass 2 — Deep scan (REST, all 4,500 repos)
    a) Commit scan — trailers, bot authors, author email
       (up to 300 commits per repo, since 2025-01-01)
    b) PR scan — body patterns, branch names, labels
       (up to 200 PRs per repo)
    c) npm dependency check — AI agent packages in package.json
       (skipped gracefully for vanilla repos)
        ↓
  data/stage4/signals_global.csv
    one row per detected signal instance

  data/stage4/sample_corpus_detected.csv
    one row per repo with aggregated detection columns:
      agent_adopted_single / agent_adopted_multi / adoption_level
      signal_count / signal_occurrences / agent_name / first_detected_at
```

**Adoption level classification:**
- **agentic** — config file present, OR ≥2 distinct signal types, OR ≥3 total signals
- **ai_assisted** — any signals but none of the agentic conditions
- **none** — 0 signals

---

## STAGE 5 — Statistical Analysis ⏳

**Scripts location:** `scripts/stage5/` *(to be written)*

```
owners_final.csv      (Stage 3b output)
sample_corpus_detected.csv  (Stage 4 output)
        ↓
  Join on full_name / owner_login
        ↓
  RQ1 — Global JS/TS/npm adoption rate
    Headline rate: npm + pnpm + yarn + bun + npm_no_lock
    Breakdown: by ecosystem, language, size_stratum
    Vanilla shown as comparison footnote

  RQ2 — Undercounting delta
    single-signal rate (commit trailers only)
    multi-signal rate (all 4 signal types)
    delta = multi − single
    per-signal-type contribution to coverage

  RQ3 — Egypt vs global comparison
    Fisher's exact test on adoption_level proportions
    Mann-Whitney U on stars, commits, repo age
    Benjamini-Hochberg correction for multiple comparisons
    Sensitivity check: confirmed-only vs confirmed+probable Egyptians
```

---

## Data flow summary

```
GitHub API
    │
    ▼
stage1a → global_corpus_raw.csv (archived)
    │
    ▼
stage1b → global_corpus.csv ─────────────────── ecosystem_audit.csv
    │
    ▼
stage1c → sample_corpus.csv ◄─────────────────────────────────────┐
    │                                                               │
    ├──────────────────────────┐                                    │
    │                          │                                    │
    ▼                          ▼                                    │
STAGE 2                    STAGE 4                                  │
stage2a → owner_signals    stage4 → signals_global.csv             │
stage2b → owner_signals              sample_corpus_detected.csv    │
    │                          │                                    │
    ▼                          │                                    │
STAGE 3                        │                                    │
stage3a → owner_signals_full   │                                    │
stage3b → owners_final.csv ────┤                                    │
          egypt_corpus.csv     │                                    │
          coverage_stats.csv   │                                    │
    │                          │                                    │
    └──────────┬───────────────┘                                    │
               ▼                                                    │
          STAGE 5                                                   │
     statistical analysis                                           │
               │                                                    │
               ▼                                                    │
         thesis results                                             │
```

---

## Script inventory

| Script | Location | Status |
|---|---|---|
| `stage1a_collect_repos.py` | `scripts/stage1/` | ✅ Done |
| `stage1b_categorize_ecosystem.py` | `scripts/stage1/` | ✅ Done |
| `stage1c_sample.py` | `scripts/stage1/` | ✅ Done |
| `stage2a_owner_profiles.py` | `scripts/stage2/` | ⏳ To be written |
| `stage2b_social_signals.py` | `scripts/stage2/` | ⏳ To be written |
| `stage3a_repo_signals.py` | `scripts/stage3/` | ⏳ To be written |
| `stage3b_finalize.py` | `scripts/stage3/` | ⏳ To be written |
| `stage4_detection.py` | `scripts/stage4/` | 🔄 Updated, ready to run |
| Stage 5 scripts | `scripts/stage5/` | ⏳ To be written |

---

## Data file locations

| File | Location | Created by |
|---|---|---|
| `global_corpus.csv` | `data/stage1/` | Stage 1b |
| `ecosystem_audit.csv` | `data/stage1/` | Stage 1b |
| `sample_corpus.csv` | `data/stage1/` | Stage 1c |
| `strata_audit.csv` | `data/stage1/` | Stage 1c |
| `owner_signals.csv` | `data/stage2/` | Stage 2a–2b |
| `owner_signals_full.csv` | `data/stage3/` | Stage 3a |
| `owners_final.csv` | `data/stage3/` | Stage 3b |
| `egypt_corpus.csv` | `data/stage3/` | Stage 3b |
| `coverage_stats.csv` | `data/stage3/` | Stage 3b |
| `signals_global.csv` | `data/stage4/` | Stage 4 |
| `sample_corpus_detected.csv` | `data/stage4/` | Stage 4 |

---

## Current status

| Stage | Status |
|---|---|
| Stage 1a | ✅ Complete — 60,129 repos collected |
| Stage 1b | ✅ Complete — all 60,129 repos categorized |
| Stage 1c | ✅ Complete — 4,500 repos sampled |
| Stage 2a | ⏳ Script to be written |
| Stage 2b | ⏳ Script to be written |
| Stage 3a | ⏳ Script to be written |
| Stage 3b | ⏳ Script to be written |
| Stage 4 | 🔄 Script updated — ready to run |
| Stage 5 | ⏳ Not started |

# Complete Research Pipeline

**Thesis:** Coding Agent Adoption in JavaScript/TypeScript/npm Repositories on GitHub  
**Student:** Manuel Youssef Haik Kevorkian  
**Last updated:** 2026-10-09

---

## Overview

```
STAGE 1 — Build the global JS/TS corpus
    ↓
STAGE 2 — Owner identity: all 9 signals + final classification
    ↓                 (runs in parallel with Stage 4)
STAGE 3 — Egyptian targeted corpus construction
    ↓
STAGE 4 — AI coding agent signal detection (global + Egyptian)
    ↓
STAGE 5 — Statistical analysis & comparison
```

- Stage 2 reads from `sample_corpus.csv` and produces the owner classification.
- Stage 3 builds the supplementary Egyptian corpus independently (no dependency on Stage 2).
- Stage 4 runs on **both** corpora: `sample_corpus.csv` (global) and `egypt_corpus_input.csv` (Egyptian).
- Stage 5 joins the Stage 2 and Stage 4 outputs for all three research questions.

---

## STAGE 1 — Corpus Collection & Sampling ✅

### Stage 1a — Global Corpus Collection
**Script:** `scripts/stage1/stage1a_collect_repos.py`  
**Status:** ✅ Complete

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
**Status:** ✅ Complete

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
**Status:** ✅ Complete

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
  data/stage1/sample_corpus.csv      ← INPUT FOR STAGES 2 AND 4
  data/stage1/strata_audit.csv       ← per-stratum breakdown
```

**Result:** 4,500 repos — npm: 1,891 | pnpm: 909 | npm_no_lock: 656 | vanilla: 789 | yarn: 194 | bun: 61

---

## STAGE 2 — Owner Identity: All 9 Signals + Final Classification ✅

**Goal:** For every repo in `sample_corpus.csv`, identify the owner's nationality by applying 9 location signals in order of cost. Produce a final classification for all 4,374 unique owners.

**Scripts location:** `scripts/stage2/`

### Signal scoring system

| Signal | What it checks | Points | Script |
|---|---|---|---|
| S1 | Profile location field = Egypt/Cairo/مصر/etc. | **10** | 2a |
| S2 | Bio has Arabic text or Egyptian keywords | **5** | 2a |
| S3 | Company field has Egyptian org names / .eg domain | **5** | 2a |
| S4 | Email has .eg TLD or Egyptian university domain | **8** | 2a |
| S5 | Member of a GitHub org with Egyptian location | **7** | 2b |
| S6 | ≥40% of followers/following are confirmed Egyptian | **5** | 2b |
| S7 | ≥40% of repo contributors have confirmed Egyptian location | **7** | 2c |
| S8 | README/CONTRIBUTING has >10% Arabic characters | **3** | 2c |
| S9 | Code/fixtures contain Egyptian patterns (phone, EGP, NID) | **4** | 2c |

**Hard negative:** S1 fires with an explicit non-Egyptian country → mark `not_egyptian`, skip all remaining signals.

### Classification thresholds (applied in Stage 2d)

| Score | Signals fired | Label | In Egypt corpus? |
|---|---|---|---|
| ≥ 10 | any | `egyptian_confirmed` | ✅ Yes |
| 5–9 | any | `egyptian_probable` | ✅ Yes (flagged) |
| 1–4 | ≥ 2 signals | `egyptian_probable` | ✅ Yes (flagged) |
| 1–4 | 1 signal only | `unconfirmed` | ❌ No — weak single signal |
| 0 | 0 | `unclassified` | ❌ No — no evidence found |
| S1 hard negative | — | `not_egyptian` | ❌ No — explicit non-Egyptian location |

**`unconfirmed`** = all 9 signals ran, only one weak signal fired — insufficient evidence.  
**`unclassified`** = all 9 signals ran, zero evidence found — location genuinely unknown.  
Both are excluded from the Egyptian corpus and reported as undercoverage in `coverage_stats.csv`.

---

### Stage 2a — Owner Profile Fetch (S1–S4)
**Script:** `scripts/stage2/stage2a_owner_profiles.py`  
**Status:** ✅ Complete

```
sample_corpus.csv
        ↓
  Extract 4,374 unique owner_logins
  Batch-fetch GitHub profiles via GraphQL (50 owners/request, ~90 requests)
  Apply: S1 (location), S2 (bio), S3 (company), S4 (email)
  S1 hard negative → mark not_egyptian immediately
        ↓
  data/stage2/owner_signals.csv
```

**Result:** 4,374 owners — not_egyptian: 1,720 (39.3%) | unclassified: 2,648 (60.5%) | confirmed/probable: 6 (0.1%)

---

### Stage 2b — Social Signals (S5–S6)
**Script:** `scripts/stage2/stage2b_social_signals.py`  
**Status:** ✅ Complete

```
owner_signals.csv  (needs_more = True rows only: 2,649 owners)
        ↓
  S5: fetch user.organizations → check org location fields
  S6: fetch followers + following (top 50 each)
      if ≥40% of located connections are Egyptian → +5 points
  Batch size: 4 users per GraphQL request (110 nodes each)
        ↓
  data/stage2/owner_signals.csv  (updated with s5_score, s6_score)
```

**Result:** S5 fired: 1 | S6 fired: 2 | New Egyptian owners found: 3

---

### Stage 2c — Repo-Level Signals (S7–S9)
**Script:** `scripts/stage2/stage2c_repo_signals.py`  
**Status:** ✅ Complete

```
owner_signals.csv  (needs_more = True rows only: 2,648 owners)
sample_corpus.csv  (to get repos belonging to each owner)
        ↓
  S7: REST GET /repos/{owner}/{repo}/contributors (top 20)
      Batch-fetch contributor locations via GraphQL
      If ≥40% of located contributors are Egyptian → +7 points

  S8: GraphQL fetch README.md + CONTRIBUTING.md
      Count Arabic Unicode chars (U+0600–U+06FF)
      If Arabic ratio >10% → +3 points

  S9: Scan README + CONTRIBUTING for Egyptian patterns:
        Mobile prefixes: 010, 011, 012, 015
        Country code: +20 | Currency: EGP | NID: 14-digit starting 2 or 3
      → +4 points if any pattern found
        ↓
  data/stage2/owner_signals_full.csv  (all 9 signals populated)
```

**Result:** S7 fired: 2 | S8 fired: 5 | S9 fired: 13

---

### Stage 2d — Finalize & Build Owner Classification
**Script:** `scripts/stage2/stage2d_finalize.py`  
**Status:** ✅ Complete

```
owner_signals_full.csv
sample_corpus.csv
        ↓
  Sum all 9 signal scores per owner
  Apply final classification thresholds
  Add confidence + location_source columns
  Join classification back to sample_corpus.csv
        ↓
  data/stage2/owners_final.csv        ← all 4,374 owners, final label
  data/stage2/egypt_corpus.csv        ← 10 repos from global sample (Egyptian owners)
  data/stage2/coverage_stats.csv      ← signal contribution breakdown (thesis table)
```

**Result:**

| Label | Owners | % | In Egypt corpus? |
|---|---|---|---|
| not_egyptian | 1,720 | 39.3% | No |
| unclassified | 2,626 | 60.0% | No |
| unconfirmed | 18 | 0.4% | No |
| egyptian_confirmed | 6 | 0.1% | Yes |
| egyptian_probable | 4 | 0.1% | Yes |

Egyptian owners identified via: direct location (50%) | social signals (20%) | repo signals (20%) | profile fields (10%)

**No API calls. Runs in seconds.**

---

## STAGE 3 — Egyptian Targeted Corpus Construction ⏳

**Goal:** Build a supplementary Egyptian corpus of ~3,000–5,000 repos for RQ3 statistical comparison. The global random sample contains only 10 Egyptian repos — insufficient for meaningful analysis. This stage directly searches GitHub for Egyptian developers and collects their JS/TS repositories.

**Why a separate stage?** Stage 2 identifies Egyptian owners *within* the global random sample. That sample has only ~0.2% Egyptian repos by design (Egypt = ~0.1% of global GitHub). Stage 3 builds a targeted corpus used exclusively for RQ3 — it does not affect the global adoption rate estimates in RQ1 and RQ2.

**Scripts location:** `scripts/stage3/`

---

### Stage 3a — Egyptian Developer Account Discovery
**Script:** `scripts/stage3/stage3a_egypt_discovery.py`  
**Status:** ⏳ Already ran (data exists) — re-run only if refreshing the account list

```
GitHub REST Search API
        ↓
  Phase 1 — Seed discovery:
    Search users by location: Egypt, Cairo, Alexandria, Giza, مصر, etc.
    Apply activity filter: ≥10 followers OR ≥5 public repos
    → seed list of Egyptian developer accounts

  Phase 2 — Snowball expansion (up to 3 rounds):
    Fetch followers + following of each seed account
    Any connection with Egyptian location → add to list
    Stop when no new accounts found (convergence)
        ↓
  data/stage3/egypt_accounts.csv      ← combined deduplicated account list
```

---

### Stage 3b — Egyptian Corpus Pull & Quality Filter
**Script:** `scripts/stage3/stage3b_egypt_corpus.py`  
**Status:** ⏳ Ready to run (Phase 1 skipped — raw corpus already in data/stage3/)

```
egypt_accounts.csv  (Phase 1 — skipped if egyptian_corpus_raw.csv exists)
        ↓
  For each account: fetch public non-fork JS/TS repos via GraphQL
  Apply same inclusion filters as Stage 1:
    - not archived, not tutorial/auto-gen name
    - primary language = JavaScript or TypeScript
    - JS+TS bytes ≥ 50% of total language bytes
    - has package.json (verified via GraphQL)

  Phase 1.5 — Commit count enrichment:
    Fetch commit count for repos that passed Phase 1.
    Drop repos with commits < 50.

  Phase 2 — Quality filter (always runs):
    stars ≥ 4  |  created ≥ 2025-02-24  |  commits ≥ 50  |  deduplicate
        ↓
  data/stage3/egyptian_corpus_raw.csv   ← all repos pulled before quality filter
  data/stage3/egypt_corpus_input.csv    ← filtered, ready for Stage 4
```

**Run:**
```bash
export GITHUB_TOKEN=your_token_here
python3 scripts/stage3/stage3b_egypt_corpus.py
```

---

## STAGE 4 — AI Coding Agent Signal Detection ⏳

**Script:** `scripts/stage4/stage4_detection.py`  
**Runs on both corpora independently.**

### Detection signals

| Signal type | What it detects | Pass |
|---|---|---|
| Config files | CLAUDE.md, AGENTS.md, .cursorrules, .aider.conf.yml, .roomodes, .windsurfrules, GEMINI.md, copilot-instructions.md | 1 (GraphQL) |
| Commit trailers | `Co-authored-by: Claude`, `Co-authored-by: GitHub Copilot`, bot author emails | 2 (REST) |
| PR body markers | Agent attribution patterns in PR descriptions and labels | 2 (REST) |
| npm dependencies | AI agent packages in package.json | 2 (REST) |

### Adoption level classification

- **agentic** — config file present, OR ≥2 distinct signal types, OR ≥3 total signals
- **ai_assisted** — any signals but none of the agentic conditions
- **none** — 0 signals

### Run on global corpus (for RQ1 + RQ2)
```bash
export GITHUB_TOKEN=your_token_here
python3 scripts/stage4/stage4_detection.py
# reads:  data/stage1/sample_corpus.csv
# writes: data/stage4/sample_corpus_detected.csv
#         data/stage4/signals_global.csv
```

### Run on Egyptian corpus (for RQ3)
```bash
python3 scripts/stage4/stage4_detection.py --corpus data/stage3/egypt_corpus_input.csv
# reads:  data/stage3/egypt_corpus_input.csv
# writes: data/stage4/egypt_corpus_input_detected.csv
#         data/stage4/signals_egypt_corpus_input.csv
```

---

## STAGE 5 — Statistical Analysis ⏳

**Scripts location:** `scripts/stage5/` *(to be written)*

```
data/stage2/owners_final.csv              (Stage 2d output)
data/stage4/sample_corpus_detected.csv   (Stage 4 global output)
data/stage4/egypt_corpus_input_detected.csv  (Stage 4 Egyptian output)
        ↓
  RQ1 — Global JS/TS/npm adoption rate
    Headline rate: npm + pnpm + yarn + bun + npm_no_lock repos
    Breakdown: by ecosystem, primary language, size_stratum
    Vanilla shown as comparison footnote

  RQ2 — Undercounting delta
    single-signal rate (commit trailers only)
    multi-signal rate (all 4 signal types combined)
    delta = multi − single
    per-signal-type contribution to coverage

  RQ3 — Egypt vs global comparison
    Fisher's exact test on adoption_level proportions
    Mann-Whitney U on stars, commits, repo age
    Benjamini-Hochberg correction for multiple comparisons
    Sensitivity check: confirmed-only vs confirmed+probable Egyptians
    Note: Egyptian corpus = targeted sample (Stage 3), used for RQ3 only
```

---

## Data flow summary

```
GitHub API
    │
    ▼
stage1a → global_corpus_raw.csv
    │
    ▼
stage1b → global_corpus.csv ──────────────── ecosystem_audit.csv
    │
    ▼
stage1c → sample_corpus.csv
    │
    ├─────────────────────────────┐
    │                             │
    ▼                             ▼
STAGE 2                       STAGE 4 (global)
stage2a → owner_signals       stage4 → sample_corpus_detected.csv
stage2b → owner_signals                signals_global.csv
stage2c → owner_signals_full
stage2d → owners_final.csv
          egypt_corpus.csv (10 repos)
          coverage_stats.csv
                                  STAGE 3
                                  stage3a → egypt_accounts.csv
                                  stage3b → egypt_corpus_input.csv
                                      │
                                      ▼
                                  STAGE 4 (Egyptian)
                                  stage4 → egypt_corpus_input_detected.csv
    │                                 │
    └──────────────┬───────────────────┘
                   ▼
             STAGE 5
        statistical analysis
               │
               ▼
         thesis results
```

---

## Script inventory

| Script | Location | Status |
|---|---|---|
| `stage1a_collect_repos.py` | `scripts/stage1/` | ✅ Done |
| `stage1b_categorize_ecosystem.py` | `scripts/stage1/` | ✅ Done |
| `stage1c_sample.py` | `scripts/stage1/` | ✅ Done |
| `stage2a_owner_profiles.py` | `scripts/stage2/` | ✅ Done |
| `stage2b_social_signals.py` | `scripts/stage2/` | ✅ Done |
| `stage2c_repo_signals.py` | `scripts/stage2/` | ✅ Done |
| `stage2d_finalize.py` | `scripts/stage2/` | ✅ Done |
| `stage3a_egypt_discovery.py` | `scripts/stage3/` | ✅ Done (data exists) |
| `stage3b_egypt_corpus.py` | `scripts/stage3/` | ⏳ Run Phase 2 (filter) |
| `stage4_detection.py` | `scripts/stage4/` | 🔄 Running (global corpus) |
| Stage 5 scripts | `scripts/stage5/` | ⏳ Not started |

---

## Data file locations

| File | Location | Created by | Description |
|---|---|---|---|
| `global_corpus.csv` | `data/stage1/` | Stage 1b | All 60,129 repos |
| `ecosystem_audit.csv` | `data/stage1/` | Stage 1b | Ecosystem breakdown |
| `sample_corpus.csv` | `data/stage1/` | Stage 1c | 4,500 sampled repos |
| `strata_audit.csv` | `data/stage1/` | Stage 1c | Per-stratum breakdown |
| `owner_signals.csv` | `data/stage2/` | Stage 2a–2b | S1–S6 scores per owner |
| `owner_signals_full.csv` | `data/stage2/` | Stage 2c | All 9 signals per owner |
| `owners_final.csv` | `data/stage2/` | Stage 2d | Final owner classifications |
| `egypt_corpus.csv` | `data/stage2/` | Stage 2d | 10 Egyptian repos from global sample |
| `coverage_stats.csv` | `data/stage2/` | Stage 2d | Signal contribution breakdown |
| `egypt_accounts.csv` | `data/stage3/` | Stage 3a | Egyptian developer accounts |
| `egyptian_corpus_raw.csv` | `data/stage3/` | Stage 3b | 6,642 raw Egyptian repos |
| `egypt_corpus_input.csv` | `data/stage3/` | Stage 3b | Filtered Egyptian corpus for Stage 4 |
| `signals_global.csv` | `data/stage4/` | Stage 4 | Per-signal instances (global) |
| `sample_corpus_detected.csv` | `data/stage4/` | Stage 4 | Per-repo detection (global) |
| `signals_egypt_corpus_input.csv` | `data/stage4/` | Stage 4 | Per-signal instances (Egyptian) |
| `egypt_corpus_input_detected.csv` | `data/stage4/` | Stage 4 | Per-repo detection (Egyptian) |

---

## Current status

| Stage | Status |
|---|---|
| Stage 1a | ✅ Complete — 60,129 repos collected |
| Stage 1b | ✅ Complete — all 60,129 repos categorized |
| Stage 1c | ✅ Complete — 4,500 repos sampled |
| Stage 2a | ✅ Complete — 4,374 owners, S1–S4 applied |
| Stage 2b | ✅ Complete — S5–S6 applied |
| Stage 2c | ✅ Complete — S7–S9 applied |
| Stage 2d | ✅ Complete — 10 Egyptian repos in global sample |
| Stage 3a | ✅ Complete — Egyptian accounts discovered |
| Stage 3b | ⏳ Run Phase 2 to produce egypt_corpus_input.csv |
| Stage 4 (global) | 🔄 Running on sample_corpus.csv |
| Stage 4 (Egyptian) | ⏳ Run after Stage 3b completes |
| Stage 5 | ⏳ Not started |

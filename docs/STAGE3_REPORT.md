# Stage 3 — Egyptian Targeted Corpus Construction

**Goal:** Build a dedicated Egyptian repository corpus large enough for statistical comparison with the global sample (RQ3). Stage 2 found only 10 Egyptian repos inside the global random sample — far too few for any statistical test. Stage 3 solves this by directly targeting Egyptian developers.

---

## Why a separate stage was needed

The global random sample (4,500 repos) naturally contains ~0.2% Egyptian repos because Egypt represents a tiny fraction of global GitHub activity. Stage 2 confirmed this: after running 9 identification signals on all 4,374 owners, only 10 Egyptian repos were found.

To answer RQ3 ("do Egyptian developers adopt AI tools at a different rate?") you need enough Egyptian repos to run Fisher's exact test and Mann-Whitney U. That requires a targeted corpus — which is what Stage 3 builds.

**Important:** The Stage 3 corpus is used exclusively for RQ3. It does not affect the global adoption rate estimates in RQ1 or RQ2. The two corpora are built with identical quality filters so any adoption rate difference reflects developer behaviour, not selection bias.

---

## Where the input came from — the 3 old scripts

Before Stage 3 existed in the current pipeline, three scripts were written (now archived in `scripts/stage2/old/`) to collect Egyptian developer accounts:

### Script 1 — `stage2a_egypt_seed_discovery_v2.py`
**What it does:** Searches GitHub's REST User Search API for accounts whose location field contains Egyptian city/country names (both English and Arabic).

Search terms used:
- English: Egypt, Cairo, Alexandria, Giza
- Arabic: مصر, القاهرة, الإسكندرية, الجيزة

Activity filter applied: account must have ≥10 followers OR ≥5 public repos (to exclude inactive/abandoned accounts).

**Output:** `egypt_seed_candidates.csv` — **2,434 accounts**

---

### Script 2 — `Stage2b_snowball_expansion.py`
**What it does:** Takes every seed account from Script 1 and fetches their followers and following (up to 30 connections each) via GraphQL. Any connection whose location field also contains an Egyptian term is added to the list. This runs for up to 3 rounds until no new accounts are found (convergence).

**Why snowball?** Many Egyptian developers do not fill in their location field. But they follow and are followed by Egyptian developers who do. The snowball step discovers the "invisible" Egyptian developers through their social network.

**Output:** `egypt_snowball_candidates.csv` — **24,041 accounts**

---

### Script 3 — `combine_accounts.py`
**What it does:** Merges the seed list and the snowball list, deduplicates by login, and adds a `source` column (`seed` or `snowball`) to trace where each account was found.

**Output:** `egypt_combined_accounts.csv` — **26,475 unique accounts**

This file was copied to `data/stage3/egypt_accounts.csv` and is the input to Stage 3b.

---

## The input to Stage 3b

**`data/stage3/egypt_accounts.csv` — 26,475 accounts**

This is the merged file containing:
- 2,434 directly discovered seed accounts (location search)
- ~24,041 snowball-discovered accounts (found through social networks)

Stage 3b uses ALL 26,475 accounts — not just the directly found seeds.

---

## Stage 3a — `stage3a_egypt_discovery.py`

This script is the current-pipeline equivalent of the three old scripts above. It is already complete — its output is `egypt_accounts.csv` in `data/stage3/`. It does not need to be re-run unless you want to refresh the account list.

What it does (same logic as the old scripts, in one script):
- Phase 1: GitHub REST search by Egyptian location terms → seed accounts
- Phase 2: Snowball expansion through follower/following networks
- Output: `data/stage3/egypt_accounts.csv`

---

## Stage 3b — `stage3b_egypt_corpus.py`

This is the main script. It takes the 26,475 Egyptian developer accounts and builds the filtered corpus that goes into Stage 4.

### Phase 1 — Repo pull (from 26,475 accounts)
For each account, fetch all public non-fork repositories via GraphQL and apply inclusion filters:

| Filter | Value | Reason |
|--------|-------|--------|
| Primary language | JavaScript or TypeScript | Thesis scope |
| JS+TS language bytes | ≥ 50% of total | Ensure it's genuinely a JS/TS project |
| Has package.json | Yes | npm ecosystem scope |
| Is fork | No | Only original repos |
| Is archived | No | Only active repos |
| Tutorial/auto-gen name | No | Filter boilerplate repos |
| created_at | ≥ 2025-02-24 | AI agent era only |

Repos that fail these filters are recorded in the audit log but dropped.

**Output:** `data/stage3/egyptian_corpus_raw.csv` — all repos that passed Phase 1

---

### Phase 1.5 — Commit count enrichment
For every repo that passed Phase 1, fetch its total commit count via GraphQL.

Filter: commits ≥ 50

**Why 50 commits?** Same threshold used in Stage 1 for the global corpus. Repos with fewer commits have too little development history to be meaningful for the study. Applying the same filter ensures the two corpora are comparable.

---

### Phase 2 — Quality filtering
Takes the raw corpus and applies final quality thresholds:

| Filter | Value |
|--------|-------|
| Stars | ≥ 4 |
| Created at | ≥ 2025-02-24 |
| Commits | ≥ 50 |
| Duplicate repos | Deduplicate by full_name |

**Output:** `data/stage3/egypt_corpus_input.csv` — the final Egyptian corpus, ready for Stage 4

---

## Numbers (current corpus — old run, pre creation-date fix)

| Step | Repos |
|------|-------|
| Accounts processed | 26,475 |
| Passed Phase 1 inclusion filters | ~820 |
| After commits ≥ 50 (Phase 1.5) | ~136 |
| After stars ≥ 4 and deduplication | **136** |

> **Note:** The corpus is currently being re-run with the creation date filter (`created >= 2025-02-24`) applied from Phase 1. The old run used `pushed >= 2025-01-01` which allowed repos created before the AI agent era. The new run will produce a corrected and smaller corpus.

---

## Filter consistency with global corpus

Every filter applied in Stage 3b matches Stage 1:

| Filter | Stage 1 (global) | Stage 3b (Egyptian) |
|--------|-----------------|---------------------|
| Language | JS or TS | JS or TS ✅ |
| Language bytes | ≥ 175KB | ≥ 50% JS+TS ✅ |
| package.json | ✅ | ✅ |
| Not fork | ✅ | ✅ |
| Stars | ≥ 4 | ≥ 4 ✅ |
| Created at | ≥ 2025-02-24 | ≥ 2025-02-24 ✅ |
| Commits | ≥ 50 | ≥ 50 ✅ |

This consistency is essential. If the two corpora were filtered differently, any adoption rate gap between global and Egyptian repos could be explained by the different selection criteria rather than by developer nationality.

---

## Outputs

| File | Location | Description |
|------|----------|-------------|
| `egypt_accounts.csv` | `data/stage3/` | 26,475 Egyptian developer accounts (input) |
| `egyptian_corpus_raw.csv` | `data/stage3/` | All repos pulled before quality filter |
| `egypt_corpus_input.csv` | `data/stage3/` | Final filtered corpus → input for Stage 4 |

---

## What Stage 3 feeds into

- **Stage 4** reads `egypt_corpus_input.csv` and runs the same AI adoption detection on it
- **Stage 5 (RQ3)** compares the Egyptian adoption rate against the global rate from Stage 4

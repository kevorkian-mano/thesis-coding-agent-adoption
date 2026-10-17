# Stage 1 Summary — Corpus Collection & Ecosystem Categorization

**Thesis:** Coding Agent Adoption in JavaScript/TypeScript/npm Repositories on GitHub  
**Student:** Manuel Youssef Haik Kevorkian  
**Last updated:** 2026-10-08

---

## What Stage 1 Did

Stage 1 built the global corpus of JavaScript/TypeScript repositories from GitHub.  
It ran in three sub-stages: collection (1a), categorization (1b), and sampling (1c).

---

## Stage 1a — Global Corpus Collection

**Script:** `scripts/stage1/stage1a_collect_repos.py`  
**Output:** `data/stage1/global_corpus_raw.csv` (archived — superseded by global_corpus.csv)

### What it did
Searched GitHub via the GraphQL Search API for all public JS/TS repositories that met the professor's inclusion criteria. Ran two separate passes — one for JavaScript, one for TypeScript — to avoid a known GitHub API bug where `language:JavaScript OR language:TypeScript` returns 0 results.

Used 5-day date windows from 2025-02-24 to today, with recursive halving for windows that exceeded GitHub's 1,000-result cap.

### Inclusion criteria applied
| Filter | Value | Reason |
|---|---|---|
| Language | JavaScript or TypeScript | Thesis scope |
| Created on or after | 2025-02-24 | Start of mature AI agent era |
| Stars | ≥ 4 | Excludes toy/abandoned repos |
| Commits | ≥ 50 | Ensures meaningful development history |
| Fork | No | Excludes derivative projects |
| JS+TS combined bytes | ≥ 175,000 (175 KB) | Ensures JS/TS is the primary language, not incidental |

### Result
**60,129 repositories** collected.

---

## Stage 1b — Ecosystem Categorization

**Script:** `scripts/stage1/stage1b_categorize_ecosystem.py`  
**Output:** `data/stage1/global_corpus.csv`, `data/stage1/ecosystem_audit.csv`

### What it did
Checked 7 files at the root of every repo via GitHub GraphQL to classify each repo by its package manager ecosystem. No repos were dropped — every repo got a category label.

### Files checked per repo
`package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `bun.lockb`, `deno.json`, `deno.jsonc`

### Classification priority
1. If `deno.json` or `deno.jsonc` exists → **deno**
2. If `package.json` exists:
   - + `package-lock.json` → **npm**
   - + `yarn.lock` → **yarn**
   - + `pnpm-lock.yaml` → **pnpm**
   - + `bun.lockb` → **bun**
   - (no lockfile) → **npm_no_lock**
3. None of the above → **vanilla**

### Results — full ecosystem breakdown

| Category | Count | % | Description |
|---|---|---|---|
| npm | 28,248 | 47.0% | package.json + package-lock.json |
| pnpm | 12,229 | 20.3% | package.json + pnpm-lock.yaml |
| vanilla | 10,177 | 16.9% | JS/TS code, no package manager at all |
| npm_no_lock | 7,979 | 13.3% | package.json but no lockfile |
| yarn | 1,091 | 1.8% | package.json + yarn.lock |
| deno | 250 | 0.4% | Deno runtime (not npm) |
| bun | 107 | 0.2% | package.json + bun.lockb |
| unknown | 48 | 0.1% | NaN rows (data quality issue) |
| **Total** | **60,129** | **100%** | |

---

## Stage 1c — Stratified Random Sampling (TO BE RE-RUN)

**Script:** `scripts/stage1/stage1c_sample.py`  
**Output:** `data/stage1/sample_corpus.csv`, `data/stage1/strata_audit.csv`

### Why we need to sample
Running Stage 4 (AI signal detection) on all 60,129 repos would require millions of GitHub API calls and take weeks. A well-designed stratified sample of ~4,500 repos produces statistically reliable estimates for every subgroup while staying within a feasible runtime (~2–4 hours for Stage 4).

---

## Open Question: Which ecosystems to include in the sample?

### The original approach (now revised)
The first run of Stage 1c included only: `npm, pnpm, yarn, bun, npm_no_lock` — dropping vanilla, deno, and unknown.

### Why vanilla should be kept (not dropped)

**Vanilla repos = 10,177 repos (16.9%)** — JS/TS repositories with no package manager.

Dropping them has two problems:

1. **Selection bias:** If you only sample npm-managed repos, your adoption rate reflects "npm developers" not "JS/TS developers on GitHub." A reviewer can legitimately challenge this.

2. **Lost comparison group:** If vanilla repos show a different adoption rate than npm repos, that is a finding. AI coding agents may be more common in well-structured, dependency-managed projects — or less common, because vanilla repos are often smaller. You cannot know unless you sample them.

3 out of 4 detection signals still work on vanilla repos:
- ✅ Config files (CLAUDE.md, .cursorrules, etc.)
- ✅ Commit message trailers (Co-authored-by: Claude)
- ✅ PR body markers
- ❌ npm dependency declarations (not applicable — no package.json)

**Recommendation:** Keep vanilla in the sample as a **comparison group**, clearly separated from the npm thesis targets in the analysis. Report adoption rates for npm targets separately, with vanilla as a baseline footnote.

### What about deno? (Drop it)

Deno is a completely different JavaScript runtime created as an alternative to Node.js. It does not use npm — packages are imported directly from URLs or `jsr.io`. With only 250 repos (0.4%), it is:
- Outside the "npm repositories" scope of the thesis title
- Too small for meaningful statistical analysis

**Decision: Drop deno.** Mention it in a single sentence in the methodology as an excluded category.

### What about unknown? (Drop it)

48 repos (0.1%) where owner_login or repo_name was NaN due to a data quality issue in Stage 1a. Not recoverable.

**Decision: Drop unknown.**

### Ecosystem groups used

| Group | Ecosystems | Purpose |
|---|---|---|
| **Thesis targets** | npm, pnpm, yarn, bun, npm_no_lock | Primary analysis (RQ1, RQ2, RQ3) |
| **Comparison group** | vanilla | Secondary baseline — no package manager |
| **Excluded** | deno, unknown | Out of scope / data quality |

---

## Stage 1c Results — Completed ✅

**Script:** `scripts/stage1/stage1c_sample.py`  
**Output:** `data/stage1/sample_corpus.csv`, `data/stage1/strata_audit.csv`  
**Random seed:** 42 (reproducible)

### Configuration
- Target sample: 4,500 repos
- Minimum per stratum: 30
- Strata found: 35 (out of 36 possible — `bun__JavaScript__large` does not exist in the corpus, meaning there are zero large Bun JavaScript repos)

### Results by ecosystem

| Ecosystem | Available | Sampled | % sampled | Role |
|---|---|---|---|---|
| npm | 28,248 | 1,891 | 6.7% | Primary thesis target |
| pnpm | 12,229 | 909 | 7.4% | Primary thesis target |
| npm_no_lock | 7,979 | 656 | 8.2% | Primary thesis target |
| vanilla | 10,177 | 789 | 7.8% | Comparison group |
| yarn | 1,091 | 194 | 17.8% | Primary thesis target (oversampled for coverage) |
| bun | 107 | 61 | 57.0% | Primary thesis target (oversampled — too small) |
| **Total** | **59,831** | **4,500** | **7.5%** | |

Excluded from pool: deno (250) + unknown (48) = 298 repos.

### Full stratum breakdown

| Stratum | Available | Sampled | % |
|---|---|---|---|
| bun__JavaScript__medium | 1 | 1 | 100% |
| bun__JavaScript__small | 6 | 6 | 100% |
| bun__TypeScript__large | 3 | 3 | 100% |
| bun__TypeScript__medium | 18 | 18 | 100% |
| bun__TypeScript__small | 79 | 33 | 41.8% |
| npm__JavaScript__large | 219 | 42 | 19.2% |
| npm__JavaScript__medium | 922 | 84 | 9.1% |
| npm__JavaScript__small | 5,956 | 391 | 6.6% |
| npm__TypeScript__large | 679 | 70 | 10.3% |
| npm__TypeScript__medium | 2,896 | 205 | 7.1% |
| npm__TypeScript__small | 17,576 | 1,099 | 6.3% |
| npm_no_lock__JavaScript__large | 56 | 32 | 57.1% |
| npm_no_lock__JavaScript__medium | 253 | 44 | 17.4% |
| npm_no_lock__JavaScript__small | 1,571 | 124 | 7.9% |
| npm_no_lock__TypeScript__large | 294 | 46 | 15.6% |
| npm_no_lock__TypeScript__medium | 985 | 88 | 8.9% |
| npm_no_lock__TypeScript__small | 4,820 | 322 | 6.7% |
| pnpm__JavaScript__large | 25 | 25 | 100% |
| pnpm__JavaScript__medium | 100 | 34 | 34% |
| pnpm__JavaScript__small | 546 | 61 | 11.2% |
| pnpm__TypeScript__large | 579 | 63 | 10.9% |
| pnpm__TypeScript__medium | 1,863 | 142 | 7.6% |
| pnpm__TypeScript__small | 9,116 | 584 | 6.4% |
| vanilla__JavaScript__large | 128 | 36 | 28.1% |
| vanilla__JavaScript__medium | 576 | 63 | 10.9% |
| vanilla__JavaScript__small | 4,287 | 289 | 6.7% |
| vanilla__TypeScript__large | 159 | 38 | 23.9% |
| vanilla__TypeScript__medium | 601 | 65 | 10.8% |
| vanilla__TypeScript__small | 4,426 | 298 | 6.7% |
| yarn__JavaScript__large | 6 | 6 | 100% |
| yarn__JavaScript__medium | 10 | 10 | 100% |
| yarn__JavaScript__small | 112 | 35 | 31.2% |
| yarn__TypeScript__large | 32 | 30 | 93.8% |
| yarn__TypeScript__medium | 119 | 35 | 29.4% |
| yarn__TypeScript__small | 812 | 78 | 9.6% |

### Why this does not bias the Egyptian corpus

The Egyptian sub-corpus (Stage 2) is built by looking at the **owners** of the sampled repos and identifying which are Egyptian. Stratification variables (ecosystem, language, size) are independent of owner nationality — an Egyptian developer is equally likely to own a small TypeScript npm repo as any other developer.

The only potential correlation is if Egyptian developers systematically prefer one ecosystem. This is precisely what RQ3 will measure. Proportional sampling ensures Egyptian owners have equal representation across all subgroups.

---

## Files currently in data/stage1/

| File | Description | Status |
|---|---|---|
| `global_corpus.csv` | All 60,129 repos with ecosystem_type | ✅ Active — master corpus |
| `ecosystem_audit.csv` | Full ecosystem breakdown | ✅ Active — thesis table |
| `sample_corpus.csv` | 4,500 sampled repos for analysis | ✅ Active — input for Stage 2 & 4 |
| `strata_audit.csv` | Per-stratum breakdown | ✅ Active — methodology appendix |
| `old/` | Archived intermediate files | 📦 Archived |

---

## Next steps

Stage 1 is complete. See PIPELINE.md for the full pipeline.

```
Stage 2 (owner identity) — ✅ Complete
  stage2a → stage2b → stage2c → stage2d

Stage 3 (Egyptian targeted corpus) — ⏳ Run stage3b to filter
  stage3a (discovery) → stage3b (corpus pull + filter)

Stage 4 (AI detection) — 🔄 Running
  python3 scripts/stage4/stage4_detection.py                                   # global
  python3 scripts/stage4/stage4_detection.py --corpus data/stage3/egypt_corpus_input.csv  # Egyptian

Stage 5 (analysis) — ⏳ Not started
```

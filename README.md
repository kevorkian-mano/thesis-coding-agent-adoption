# AI Coding Agent Adoption in JavaScript / TypeScript / npm
### Bachelor's Thesis — Empirical Software Engineering
**Student:** Manuel Youssef Haik Kevorkian · October 2026

---

## What This Thesis Is About

This thesis measures how widely AI coding agents (Claude Code, GitHub Copilot,
Cursor, OpenAI Codex, Devin, Aider, etc.) have been adopted in active
JavaScript and TypeScript repositories on GitHub, and whether adoption rates
differ significantly across countries.

**Three research questions:**

| RQ | Question | Answer |
|----|----------|--------|
| RQ1 | What proportion of active JS/TS/npm repos created since Feb 2025 show AI agent use? | **73.0%** [72.65%, 73.35%] |
| RQ2 | How much does single-signal detection undercount adoption vs multi-signal? | **+31.41 pp** (41.6% → 73.0%) |
| RQ3 | Do adoption rates differ significantly across countries? | **Yes** — Belgium 89.9% to Rwanda 22.4%, 41/65 countries significant |

---

## Pipeline

```
Stage 1  →  Stage 2  →  Stage 3a/b/c/d  →  Stage 4a/b/c
Corpus      Location     AI Detection        Geographic Analysis
60,129      Inference    4 passes            + Statistical Tests
repos       43.9%        73.0% adopted       + Breakdowns
            located
```

### Stage Status

| Stage | Script(s) | What it does | Status |
|-------|-----------|-------------|--------|
| Stage 1a | `stage1a_collect_repos.py` | Collect JS/TS repos via GitHub GraphQL (rolling 5-day windows) | ✅ Done |
| Stage 1b | `stage1b_categorize_ecosystem.py` | Classify repos by package manager (npm/pnpm/yarn/bun/deno/vanilla) | ✅ Done |
| Stage 2a | `stage2a_location_fast.py` | Batch location inference from profile field (50 owners/request) | ✅ Done |
| Stage 2b | `stage2b_location_deep.py` | Deep location inference (bio, company, TLD, network) for unresolved owners | ✅ Done |
| Stage 3a | `stage3a_config_files.py` | Pass 1: config file detection (CLAUDE.md, AGENTS.md, .cursorrules, etc.) | ✅ Done |
| Stage 3b | `stage3b_commit_trailers.py` | Pass 2: commit trailer + PR branch scan | ✅ Done |
| Stage 3c | `stage3c_deep_scan.py` | Pass 3: GraphQL batched deep scan (commits, PRs, .gitignore, CI, topics) | ✅ Done |
| Stage 3d | `stage3d_reclassify.py` | Pass 4: reclassify ai_assisted under tiered signal rule | ✅ Done |
| Stage 4a | `stage4a_geographic_analysis.py` | Join detection corpus with location data; build country ranking | ✅ Done |
| Stage 4b | `stage4b_statistical_tests.py` | RQ1 binomial, RQ2 McNemar, RQ3 chi-squared + Fisher + BH FDR | ✅ Done |
| Stage 4c | `stage4c_breakdowns.py` | Adoption by ecosystem, language, size; co-adoption analysis | ✅ Done |

---

## Key Numbers

### Corpus (Stage 1)
| Metric | Value |
|--------|-------|
| Total repositories | 60,129 |
| Creation window | 24 Feb 2025 – Oct 2026 |
| Filters | ≥4 stars, ≥50 commits, not a fork, JS+TS bytes ≥175k |
| TypeScript | 45,314 (75.4%) |
| JavaScript | 14,815 (24.6%) |

### Location Inference (Stage 2)
| Metric | Value |
|--------|-------|
| Unique owners | 50,002 |
| Located (country known) | 21,948 (43.9%) |
| Not specified | 28,054 (56.1%) |
| Countries with ≥30 repos | 65 |

### AI Detection (Stage 3)
| Pass | Input | Agentic found |
|------|-------|---------------|
| Pass 1 — config files | 60,129 | 25,010 (41.6%) |
| Pass 2 — commit trailers | 35,119 | 9,618 (27.4%) |
| Pass 3 — deep scan | 21,655 | 764 (3.5%) |
| Stage 3d — reclassification | 8,503 ai_assisted | 4,104 upgraded |

**Final classification:**
| Label | Repos | % |
|-------|-------|---|
| Agentic | 39,496 | 65.7% |
| AI-assisted | 4,399 | 7.3% |
| None | 16,234 | 27.0% |
| **Total adopted** | **43,895** | **73.0%** |

### Geographic Analysis (Stage 4)
| Metric | Value |
|--------|-------|
| Countries ranked | 65 |
| Highest adoption | Belgium 89.9% |
| Lowest adoption | Rwanda 22.4% |
| Significant countries (BH) | 41 / 65 |
| Chi-squared (RQ3) | χ²=2234.55, df=64, p≈0 |

---

## Project Structure

```
├── scripts/
│   ├── stage1/               — corpus collection & ecosystem classification
│   ├── stage2/               — owner location inference (fast + deep passes)
│   ├── stage3/               — AI adoption detection (4 passes)
│   │   ├── stage3a_config_files.py
│   │   ├── stage3b_commit_trailers.py
│   │   ├── stage3c_deep_scan.py
│   │   └── stage3d_reclassify.py
│   ├── stage4/               — geographic analysis & statistical tests
│   │   ├── stage4a_geographic_analysis.py
│   │   ├── stage4b_statistical_tests.py
│   │   └── stage4c_breakdowns.py
│   └── supplementary/        — archived scripts from earlier methodology
│
├── data/
│   ├── stage1/               — global_corpus.csv
│   ├── stage2/               — owner_locations_all.csv
│   ├── stage3/               — pass1/2/3 results, corpus_detected_full_v2.csv
│   └── stage4/               — country_adoption.csv, corpus_with_country.csv,
│                               statistical_tests.txt, breakdown CSVs
│
└── bachelor_thesis/
    ├── main.tex              — thesis entry point
    ├── chapters/
    │   ├── intro.tex
    │   ├── litrev.tex        — 30 papers, 6 thematic sections ✅
    │   ├── methodology.tex   — ⏳ pending
    │   ├── results.tex       — Phases 1–4 complete ✅
    │   ├── discussion.tex    — ⏳ pending
    │   └── conclusion.tex    — ⏳ pending
    └── results_summary.tex   — 2-page supervisor summary ✅
```

---

## Detection Signal Hierarchy

The pipeline uses a tiered signal classification:

| Tier | Signal families | Classification |
|------|----------------|---------------|
| **STRONG** | bot_author, ci_workflow, pr_branch, agent_attribution | Any 1 STRONG → **agentic** |
| **MEDIUM** | config_file, pr_label, tool_configuration | ≥2 MEDIUM families → **agentic** |
| **WEAK** | pr_body, gitignore_mixed | MEDIUM or WEAK only → **ai_assisted** |

---

## Requirements

```bash
pip install requests pandas numpy scipy
export GITHUB_TOKEN=ghp_...
```

Run order:
```bash
python3 scripts/stage1/stage1a_collect_repos.py
python3 scripts/stage1/stage1b_categorize_ecosystem.py
python3 scripts/stage2/stage2a_location_fast.py
python3 scripts/stage2/stage2b_location_deep.py
python3 scripts/stage3/stage3a_config_files.py
python3 scripts/stage3/stage3b_commit_trailers.py
python3 scripts/stage3/stage3c_deep_scan.py
python3 scripts/stage3/stage3d_reclassify.py
python3 scripts/stage4/stage4a_geographic_analysis.py
python3 scripts/stage4/stage4b_statistical_tests.py
python3 scripts/stage4/stage4c_breakdowns.py
```

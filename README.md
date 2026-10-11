# Coding Agent Adoption in JavaScript / TypeScript / npm
### Bachelor's Thesis — Topic 2
**Student:** Manuel Youssef Haik Kevorkian

---

## What This Thesis Is About

This thesis measures how widely AI coding agents (GitHub Copilot, Cursor, Claude Code, Aider, etc.) have been adopted in active JavaScript and TypeScript repositories on GitHub, with a focused comparison on Egyptian developers.

Three research questions:
- **RQ1** — What proportion of active JS/TS/npm repositories show evidence of AI coding agent adoption? How does it vary by ecosystem, language, and repo size?
- **RQ2** — How much does single-signal detection (commit trailers only) undercount adoption compared to multi-signal detection?
- **RQ3** — Do Egyptian developers adopt AI coding agents at a different rate than the global average?

---

## Pipeline Status

| Stage | What it does | Status |
|-------|-------------|--------|
| Stage 1 | Build global JS/TS corpus (60,129 repos → 4,500 sampled) | ✅ Done |
| Stage 2 | Identify Egyptian owners within the global sample | ✅ Done |
| Stage 3 | Build targeted Egyptian corpus from 26,475 accounts | 🔄 Re-running |
| Stage 4 | Detect AI adoption signals (global + Egyptian) | ✅ Done (global), ⏳ Egyptian pending |
| Stage 5 | Statistical analysis & comparisons | ✅ Done (will re-run after Stage 3) |

---

## Key Numbers So Far

| Metric | Value |
|--------|-------|
| Global corpus collected | 60,129 repos |
| Global sample (stratified) | 4,500 repos |
| Egyptian developer accounts | 26,475 |
| Egyptian repos (current corpus) | ~136 (being re-pulled) |
| Egyptian owners found in global sample (Stage 2) | 10 repos |
| Global AI adoption rate (multi-signal) | ~46% |
| Egyptian AI adoption rate (multi-signal) | ~17.6% (will update) |

---

## Project Structure

```
├── scripts/
│   ├── stage1/          — global corpus collection & sampling
│   ├── stage2/          — owner identity: 9 signals to find Egyptian owners
│   ├── stage3/          — Egyptian targeted corpus construction
│   ├── stage4/          — AI adoption signal detection
│   └── stage5/          — statistical analysis & breakdowns
│
├── data/
│   ├── stage1/          — global_corpus.csv, sample_corpus.csv
│   ├── stage2/          — owner_signals, owners_final, egypt_corpus (10 repos)
│   ├── stage3/          — egypt_accounts.csv, egypt_corpus_input.csv
│   ├── stage4/          — detected CSVs + signals CSVs
│   └── stage5/          — breakdown, temporal, coadoption, owner profile CSVs
│
├── docs/
│   ├── STAGE2_REPORT.md           — detailed Stage 2 documentation
│   ├── STAGE3_REPORT.md           — detailed Stage 3 documentation
│   ├── METHODOLOGY.md             — shared cluster methodology
│   └── SCRIPTS_REFERENCE.md      — per-script reference
│
├── PIPELINE.md                    — full pipeline with all steps and numbers
├── METHODOLOGY_DRAFT.md           — thesis methodology write-up draft
└── RESULTS.md                     — all Stage 5 analysis results
```

---

## Requirements

```bash
pip install requests pandas numpy scipy
export GITHUB_TOKEN=your_token_here
```

---

## Documentation

- Full pipeline details → `PIPELINE.md`
- Stage 2 explained → `docs/STAGE2_REPORT.md`
- Stage 3 explained → `docs/STAGE3_REPORT.md`
- Analysis results → `RESULTS.md`
- Methodology draft → `METHODOLOGY_DRAFT.md`

#!/usr/bin/env python3
"""
Update GitHub Issues — migrate from old methodology to new.

Closes issues #1–10 (old Egyptian-corpus methodology) with an explanation,
then creates 10 new issues matching the current pipeline.

Usage:
  export GITHUB_TOKEN=ghp_...
  python3 scripts/update_github_issues.py
"""

import os
import time
import requests

TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    raise SystemExit("Set GITHUB_TOKEN before running.")

REPO    = "kevorkian-mano/thesis-coding-agent-adoption"
BASE    = "https://api.github.com"
HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept":        "application/vnd.github+json",
}

# ── Close old issues #1–10 ────────────────────────────────────────────────────

CLOSE_COMMENT = (
    "**Closing — methodology has changed.**\n\n"
    "The thesis pivoted from an Egyptian-corpus comparison study to a "
    "global JS/TS/npm adoption study covering 60,129 repositories and "
    "65 countries. This issue was written for the old pipeline and is no "
    "longer applicable. New issues reflecting the current methodology have "
    "been created to replace it."
)

def close_issue(number: int):
    url = f"{BASE}/repos/{REPO}/issues/{number}"
    # Post closing comment
    requests.post(f"{url}/comments", json={"body": CLOSE_COMMENT}, headers=HEADERS)
    # Close the issue
    r = requests.patch(url, json={"state": "closed"}, headers=HEADERS)
    if r.status_code == 200:
        print(f"  Closed #{number}")
    else:
        print(f"  Failed to close #{number}: {r.status_code} {r.text[:80]}")
    time.sleep(0.5)

print("Closing old issues #1–10 ...")
for n in range(1, 11):
    close_issue(n)

# ── Create new issues ─────────────────────────────────────────────────────────

NEW_ISSUES = [
    {
        "title": "Write Methodology chapter",
        "labels": ["thesis-writing", "high-priority"],
        "body": """## Write `bachelor_thesis/chapters/methodology.tex`

Covers the full 4-stage pipeline as implemented.

### Checklist
- [ ] Research design: observational, repository-mining study
- [ ] Stage 1 — Corpus construction: date window (24 Feb 2025), filters (≥4 stars, ≥50 commits, not fork, JS+TS bytes ≥175k)
- [ ] Stage 1 — Ecosystem classification: lockfile-based package manager detection (npm/pnpm/yarn/bun/deno/vanilla)
- [ ] Stage 2 — Owner location inference: two-pass design, 7 signals, 43.9% located, limitations of 56.1% unresolved
- [ ] Stage 3 — Tiered signal hierarchy: STRONG / MEDIUM / WEAK families, classify() rule
- [ ] Stage 3 — All 4 passes: config files, commit trailers, deep GraphQL scan, reclassification
- [ ] Stage 3 — Detection signals catalogue with examples per family
- [ ] Stage 3d — Reclassification design: Phase 1 (no API) + Phase 2 (deep checks)
- [ ] Stage 4 — Geographic join: country ranking, MIN_REPOS=30 threshold
- [ ] Stage 4 — Statistical methods: Wilson CI, binomial test, McNemar, chi-squared, Fisher exact, Benjamini-Hochberg FDR
- [ ] Validity threats: unlocated owner bias, template copying, config file abandonment, quality filter effects
""",
    },
    {
        "title": "Write Introduction chapter",
        "labels": ["thesis-writing", "high-priority"],
        "body": """## Write `bachelor_thesis/chapters/intro.tex`

### Checklist
- [ ] Motivation: AI coding agents as a majority practice in 2025–2026
- [ ] Problem statement: unknown adoption rates in JS/TS/npm specifically; unknown geographic variation
- [ ] Formal statement of RQ1, RQ2, RQ3
- [ ] Scope: JS/TS/npm ecosystem, GitHub, Feb 2025 – Oct 2026, 60,129 repos
- [ ] Contributions: corpus, multi-signal pipeline, 65-country ranking, statistical tests
- [ ] Thesis structure overview paragraph
""",
    },
    {
        "title": "Write Discussion chapter",
        "labels": ["thesis-writing", "high-priority"],
        "body": """## Write `bachelor_thesis/chapters/discussion.tex`

Interpret results against the literature.

### Checklist
- [ ] RQ1: 73% vs Robbes et al. 71–76% convergence — why it validates the pipeline
- [ ] RQ2: 31.41 pp undercounting gap — implications for prior work that used single-signal
- [ ] RQ3: high-income vs low-income divide — link to Wachs et al. GDP and Daniotti et al. Python findings
- [ ] Claude Code dominance (44.7%, 59.2% loyalty): terminal-first CLI fits npm workflow
- [ ] TypeScript vs JavaScript gap (77.1% vs 60.5%): typed code + AI suggestion quality
- [ ] Size stratum pattern (large 91.7%): activity exposure vs serious developer profile
- [ ] Limitations: 56.1% unlocated, repo ≠ developer, quality filter bias, template copying noise
- [ ] Implications for practitioners and future research
""",
    },
    {
        "title": "Write Conclusion chapter",
        "labels": ["thesis-writing", "medium-priority"],
        "body": """## Write `bachelor_thesis/chapters/conclusion.tex`

### Checklist
- [ ] Summary of findings — one paragraph per RQ
- [ ] Main contribution stated concisely
- [ ] Limitations paragraph
- [ ] Future work: temporal analysis, developer-level analysis, other ecosystems (Python/Rust), causal modelling
""",
    },
    {
        "title": "Write Abstract",
        "labels": ["thesis-writing", "medium-priority"],
        "body": """## Write 250-word abstract

### Must include
- [ ] Context: JS/TS/npm ecosystem, agentic era, Feb 2025 onwards
- [ ] Objective: measure AI coding agent adoption rates and geographic variation
- [ ] Method: 60,129-repo corpus, 4-pass multi-signal detection pipeline
- [ ] Key results: 73.0% adoption, +31.41 pp undercounting delta, Belgium 89.9% – Rwanda 22.4%, 41/65 countries significant
- [ ] Conclusion: majority practice, geography matters significantly, multi-signal detection is necessary
""",
    },
    {
        "title": "Verify Literature Review with supervisor",
        "labels": ["review", "high-priority"],
        "body": """## Present `bachelor_thesis/chapters/litrev.tex` to supervisor

30 papers across 6 thematic sections.

### Checklist
- [ ] Compile PDF and share with supervisor
- [ ] Confirm all 30 papers have: who, did what, approach, results, pros, cons, counter-argument
- [ ] Confirm 6-section structure matches thesis scope
- [ ] Confirm research gaps section (Gap 1 ecosystem scope, Gap 2 undercounting, Gap 3 geographic) is correctly framed
- [ ] Apply any feedback from supervisor
""",
    },
    {
        "title": "Verify Results Summary with supervisor",
        "labels": ["review", "high-priority"],
        "body": """## Present `bachelor_thesis/results_summary.tex` (2-page PDF) to supervisor

### Checklist
- [ ] Compile: `pdflatex bachelor_thesis/results_summary.tex`
- [ ] Confirm RQ formulations match supervisor expectations
- [ ] Confirm statistical tests are appropriate (binomial, McNemar, chi-squared + BH)
- [ ] Confirm country ranking methodology and MIN_REPOS=30 threshold is acceptable
- [ ] Apply any feedback
""",
    },
    {
        "title": "Final thesis compilation and formatting check",
        "labels": ["technical", "medium-priority"],
        "body": """## Final check before submission

### Checklist
- [ ] All chapters compile without LaTeX errors or warnings
- [ ] All `\\ref{}` and `\\cite{}` resolve correctly (no undefined references)
- [ ] All tables fit within page margins
- [ ] No `[pending]` markers remaining in any chapter
- [ ] `references.bib` has all 30 papers with correct cite keys
- [ ] Page count within submission limit
- [ ] Front matter complete: title page, abstract, table of contents, list of tables
- [ ] Figure and table numbering is sequential
- [ ] Consistent terminology throughout (agentic / AI-assisted / none)
""",
    },
    {
        "title": "Validate detection pipeline on known repos (spot-check)",
        "labels": ["validation", "low-priority"],
        "body": """## Manually verify detection labels on a sample of repos

### Checklist
- [ ] Pick 5 repos labelled `agentic` — open on GitHub and confirm the signal is real
- [ ] Pick 5 repos labelled `ai_assisted` — confirm the signal is genuinely borderline
- [ ] Pick 5 repos labelled `none` — confirm no AI evidence exists
- [ ] Document any misclassifications in a `data/validation/spot_check.csv`
- [ ] If systematic misclassification found, open a sub-issue to fix the relevant script
""",
    },
    {
        "title": "Archive supplementary scripts and add internal README",
        "labels": ["technical", "low-priority"],
        "body": """## Clean up `scripts/supplementary/`

The `scripts/supplementary/` folder contains Stage 5/6 scripts written for the old Egyptian-corpus methodology (stage5a_breakdowns, stage5b_owner_profiles, stage5c_temporal, stage5d_coadoption, stage6_statistical_tests). They are superseded by `stage4b_statistical_tests.py` and `stage4c_breakdowns.py`.

### Checklist
- [ ] Add `scripts/supplementary/README.md` explaining these scripts are archived from the old methodology
- [ ] Confirm none of the supplementary scripts are referenced in the thesis methodology chapter
- [ ] Confirm `scripts/stage4/stage4a/b/c` cover all analyses described in the thesis
""",
    },
]


def create_issue(issue: dict) -> int:
    r = requests.post(
        f"{BASE}/repos/{REPO}/issues",
        json={
            "title":  issue["title"],
            "body":   issue["body"],
            "labels": issue.get("labels", []),
        },
        headers=HEADERS,
    )
    if r.status_code == 201:
        number = r.json()["number"]
        print(f"  Created #{number}: {issue['title']}")
        return number
    else:
        print(f"  Failed: {r.status_code} {r.text[:120]}")
        return -1


print("\nCreating new issues ...")

# Ensure labels exist first
needed_labels = {
    "thesis-writing": ("0075ca", "Thesis chapter writing task"),
    "high-priority":  ("e11d48", "Must be done before submission"),
    "medium-priority":("f59e0b", "Important but not blocking"),
    "low-priority":   ("84cc16", "Nice to have"),
    "review":         ("7c3aed", "Needs supervisor review"),
    "technical":      ("0ea5e9", "Code or compilation task"),
    "validation":     ("10b981", "Data validation task"),
}

for name, (color, desc) in needed_labels.items():
    r = requests.post(
        f"{BASE}/repos/{REPO}/labels",
        json={"name": name, "color": color, "description": desc},
        headers=HEADERS,
    )
    if r.status_code in (201, 422):  # 422 = already exists
        pass
    time.sleep(0.3)

for issue in NEW_ISSUES:
    create_issue(issue)
    time.sleep(0.6)

print("\nDone. All old issues closed, 10 new issues created.")

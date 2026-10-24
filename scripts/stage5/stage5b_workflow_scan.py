#!/usr/bin/env python3
"""
Stage 5b -- AI Workflow YAML Content Scan
==========================================
Scans repos still labelled none or ai_assisted after Stage 5a for
.github/workflows/*.yml files whose *contents* reference known AI
coding-agent GitHub Actions.

A workflow that merely *reviews* code (e.g. coderabbitai PR review
action) is NOT counted -- only actions that actively write/generate
code or open PRs autonomously are counted.

New STRONG signal family added: ci_ai_action

AI Actions checked (owner/repo@<any-tag>):
  anthropic/claude-code-action       Claude Code GitHub Action
  sweep-ai/sweep                     Sweep AI auto-PR action
  All-Hands-AI/OpenHands             OpenHands autonomous agent
  codegen-sh/codegen                 Codegen (Automorphic)
  devin-ai-integration/devin         Devin AI action
  junie-jetbrains/junie              JetBrains Junie action
  amazonwebservices/amazon-q-developer-action  Amazon Q Developer
  greptileai/greptile-action         Greptile action
  ellipsis-dev/ellipsis-action       Ellipsis code action
  factory-ai/factory-action          Factory AI action
  github/copilot-autofix-action      GitHub Copilot Autofix

Input
-----
  data/stage5/stage5a_unclassified.csv   (full_name, new_label)

Output
------
  data/stage5/stage5b_results.csv        -- all scanned repos with label
  data/stage5/stage5b_unclassified.csv   -- repos still none/ai_assisted → 5c

Usage
-----
  export GITHUB_TOKEN=ghp_...
  python3 scripts/stage5/stage5b_workflow_scan.py
"""

import os
import re
import time
import base64
import requests
import pandas as pd
from pathlib import Path

ROOT        = Path(__file__).resolve().parents[2]
IN_FILE     = ROOT / "data" / "stage5" / "stage5a_unclassified.csv"
STAGE3_CSV  = ROOT / "data" / "stage3" / "corpus_detected_full_v2.csv"
OUT_DIR     = ROOT / "data" / "stage5"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_RESULTS = OUT_DIR / "stage5b_results.csv"
OUT_UNREC   = OUT_DIR / "stage5b_unclassified.csv"

TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    raise SystemExit("Set GITHUB_TOKEN before running.")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept":        "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# ── AI actions whose presence in a workflow YAML = STRONG agentic signal ──────
# Patterns matched against the raw YAML text (case-insensitive).
# Each entry is a substring that must appear after "uses:" in the file.
AI_ACTION_PATTERNS = [
    "anthropic/claude-code-action",
    "sweep-ai/sweep",
    "All-Hands-AI/OpenHands",
    "codegen-sh/codegen",
    "devin-ai-integration/devin",
    "junie-jetbrains/junie",
    "amazonwebservices/amazon-q-developer-action",
    "greptileai/greptile-action",
    "ellipsis-dev/ellipsis-action",
    "factory-ai/factory-action",
    "github/copilot-autofix-action",
]

# Compiled regex: matches "uses: <owner/repo>@..." (any tag/sha)
_ACTION_RE = re.compile(
    r"uses\s*:\s*(" + "|".join(re.escape(p) for p in AI_ACTION_PATTERNS) + r")[@\s]",
    re.IGNORECASE,
)

ACTION_TO_TOOL = {
    "anthropic/claude-code-action":               "Claude Code",
    "sweep-ai/sweep":                             "Sweep AI",
    "All-Hands-AI/OpenHands":                     "OpenHands",
    "codegen-sh/codegen":                         "Codegen",
    "devin-ai-integration/devin":                 "Devin",
    "junie-jetbrains/junie":                      "Junie",
    "amazonwebservices/amazon-q-developer-action": "Amazon Q",
    "greptileai/greptile-action":                 "Greptile",
    "ellipsis-dev/ellipsis-action":               "Ellipsis",
    "factory-ai/factory-action":                  "Factory AI",
    "github/copilot-autofix-action":              "GitHub Copilot",
}


# ── GitHub REST helpers ────────────────────────────────────────────────────────
def get_workflow_files(owner: str, repo: str) -> list[dict]:
    """Return list of file metadata objects under .github/workflows/."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/.github/workflows"
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.json() if isinstance(r.json(), list) else []
            if r.status_code == 404:
                return []
            if r.status_code in (403, 429):
                reset = int(r.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait  = max(reset - int(time.time()), 1)
                time.sleep(min(wait, 120))
            elif r.status_code in (502, 503):
                time.sleep(5 * (attempt + 1))
        except requests.RequestException:
            time.sleep(5 * (attempt + 1))
    return []


def get_file_content(download_url: str) -> str:
    """Fetch raw file content from a download URL."""
    for attempt in range(3):
        try:
            r = requests.get(download_url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.text
            if r.status_code in (502, 503):
                time.sleep(5 * (attempt + 1))
        except requests.RequestException:
            time.sleep(5 * (attempt + 1))
    return ""


def scan_workflows(owner: str, repo: str) -> set[str]:
    """
    Scan all .yml/.yaml files under .github/workflows/.
    Returns set of matched AI_ACTION_PATTERNS (lower-case owner/repo portion).
    """
    files = get_workflow_files(owner, repo)
    matched = set()
    for f in files:
        fname = f.get("name", "")
        if not (fname.endswith(".yml") or fname.endswith(".yaml")):
            continue
        url = f.get("download_url") or f.get("url")
        if not url:
            continue
        content = get_file_content(url)
        if not content:
            continue
        for m in _ACTION_RE.finditer(content):
            action_path = m.group(1).lower()
            # Find the canonical key
            for pat in AI_ACTION_PATTERNS:
                if pat.lower() in action_path:
                    matched.add(pat)
                    break
    return matched


# ── Signal helpers (same logic as Stage 3 / Stage 5a) ────────────────────────
def combine_families(existing, new_family: str) -> list[str]:
    if pd.isna(existing) or existing == "":
        return [new_family]
    existing_list = [f.strip() for f in str(existing).split("|") if f.strip()]
    if new_family not in existing_list:
        existing_list.append(new_family)
    return existing_list


def classify(strong_fams: list, medium_fams: list, weak_fams: list,
             attr_count: int) -> str:
    if strong_fams:
        return "agentic"
    if len(set(medium_fams)) >= 2:
        return "agentic"
    if medium_fams and attr_count >= 1:
        return "agentic"
    if medium_fams or weak_fams:
        return "ai_assisted"
    return "none"


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    print("Stage 5b -- AI Workflow YAML Content Scan")
    print("=" * 60)

    if not IN_FILE.exists():
        raise SystemExit(f"Input file not found: {IN_FILE}\nRun stage5a first.")

    unclassified = pd.read_csv(IN_FILE)
    corpus       = pd.read_csv(STAGE3_CSV, low_memory=False)
    # Build lookup: full_name → Stage-3 row
    corpus_idx = corpus.set_index("full_name")

    repos  = unclassified["full_name"].tolist()
    total  = len(repos)
    print(f"Repos to scan : {total:,}\n")

    results     = []
    new_agentic = 0

    for idx, full_name in enumerate(repos, 1):
        owner, repo = full_name.split("/", 1)
        matched_actions = scan_workflows(owner, repo)

        # Pull original Stage-3 row for signal families
        if full_name in corpus_idx.index:
            orig = corpus_idx.loc[full_name]
        else:
            orig = {}

        def _get(col, default=""):
            if isinstance(orig, dict):
                return orig.get(col, default)
            val = orig.get(col, default) if hasattr(orig, "get") else getattr(orig, col, default)
            return val if not pd.isna(val) else default

        if matched_actions:
            tools  = sorted({ACTION_TO_TOOL.get(a, a) for a in matched_actions})
            strong = combine_families(_get("strong_families"), "ci_ai_action")
            medium = [f.strip() for f in str(_get("medium_families") or "").split("|") if f.strip()]
            weak   = [f.strip() for f in str(_get("weak_families")   or "").split("|") if f.strip()]
            attr   = int(_get("agent_attributed_count", 0) or 0)
            label  = classify(strong, medium, weak, attr)
            new_agentic += 1
        else:
            tools  = []
            # Keep existing label from Stage 5a input
            prev   = unclassified[unclassified["full_name"] == full_name]["new_label"].iloc[0]
            label  = prev
            strong = str(_get("strong_families") or "")
            medium = str(_get("medium_families") or "")
            weak   = str(_get("weak_families")   or "")
            attr   = _get("agent_attributed_count", 0)

        results.append({
            "full_name":              full_name,
            "prev_label":             unclassified[unclassified["full_name"] == full_name]["new_label"].iloc[0],
            "new_label":              label,
            "upgraded":               label == "agentic",
            "actions_found":          "|".join(sorted(matched_actions)),
            "tools_found":            "|".join(tools),
            "strong_families_final":  "|".join(strong) if isinstance(strong, list) else (strong or ""),
            "medium_families_final":  "|".join(medium) if isinstance(medium, list) else (medium or ""),
            "weak_families_final":    "|".join(weak)   if isinstance(weak, list)   else (weak   or ""),
            "agent_attributed_count": attr,
        })

        if idx % 500 == 0:
            print(f"  [{idx:>6}/{total}]  new agentic so far: {new_agentic:,}")

        # Polite rate limiting: ~50 req/s max (2 API calls per repo on average)
        time.sleep(0.05)

    results_df   = pd.DataFrame(results)
    results_df.to_csv(OUT_RESULTS, index=False)

    still_unclassified = results_df[results_df["new_label"].isin(["none", "ai_assisted"])][
        ["full_name", "new_label"]
    ]
    still_unclassified.to_csv(OUT_UNREC, index=False)

    print(f"\n{'=' * 60}")
    print(f"New agentic upgrades : {results_df['upgraded'].sum():,}")
    print(f"Remaining unclassified: {len(still_unclassified):,}  → input for Stage 5c")
    print(f"Saved: {OUT_RESULTS.name}  ({len(results_df):,} rows)")
    print(f"Saved: {OUT_UNREC.name}  ({len(still_unclassified):,} rows)")
    print("\nStage 5b complete.")


if __name__ == "__main__":
    main()

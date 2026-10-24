#!/usr/bin/env python3
"""
Stage 5c -- Extended Config File Detection
==========================================
Scans repos still labelled none or ai_assisted after Stage 5b for the
presence of config files / directories that were NOT included in the
Stage 3 config_file signal set.

New config paths checked
------------------------
Tool                  Paths / filenames checked
----                  -------------------------
Amazon Q Developer    .amazonq/           (directory)
Continue              .continue/          (directory)
                      .continuerc.json
Codeium / Windsurf    .codeium/           (directory)
Sweep AI              sweep.yaml
                      sweep.toml
CodeRabbit            coderabbit.yaml
                      .coderabbit.yaml
                      .coderabbit/        (directory)
Mentat                .mentat/            (directory)
Graphite              .graphite/          (directory, AI review)
Ellipsis              .ellipsis.yaml
                      .ellipsis/          (directory)
Sourcegraph Cody      .sourcegraph/       (directory)
Tabnine               .tabnine/           (directory)
Cursor                .cursorrules        (file -- project-level AI rules)
                      .cursor/            (directory)

Signal family : config_file  (MEDIUM)
Classification: depends on how many MEDIUM signals exist and attr_count.

Input
-----
  data/stage5/stage5b_unclassified.csv   (full_name, new_label)

Output
------
  data/stage5/stage5c_results.csv        -- all scanned repos with label
  data/stage5/stage5c_unclassified.csv   -- repos still none/ai_assisted
                                            (feed into Stage 5 merge / Stage 5d)

Usage
-----
  export GITHUB_TOKEN=ghp_...
  python3 scripts/stage5/stage5c_extended_configs.py
"""

import os
import re
import time
import requests
import pandas as pd
from pathlib import Path

ROOT       = Path(__file__).resolve().parents[2]
IN_FILE    = ROOT / "data" / "stage5" / "stage5b_unclassified.csv"
STAGE3_CSV = ROOT / "data" / "stage3" / "corpus_detected_full_v2.csv"
OUT_DIR    = ROOT / "data" / "stage5"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_RESULTS = OUT_DIR / "stage5c_results.csv"
OUT_UNREC   = OUT_DIR / "stage5c_unclassified.csv"

TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    raise SystemExit("Set GITHUB_TOKEN before running.")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept":        "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# ── Config paths to check ─────────────────────────────────────────────────────
# Each entry: (path_to_check, tool_name, is_directory)
# For directories we check for their existence via the contents API.
# For files we use HEAD on the raw content URL (faster, no body download).
CONFIG_ENTRIES: list[tuple[str, str, bool]] = [
    # Amazon Q
    (".amazonq",            "Amazon Q",     True),
    # Continue
    (".continue",           "Continue",     True),
    (".continuerc.json",    "Continue",     False),
    # Codeium / Windsurf
    (".codeium",            "Codeium",      True),
    # Sweep AI
    ("sweep.yaml",          "Sweep AI",     False),
    ("sweep.toml",          "Sweep AI",     False),
    # CodeRabbit
    ("coderabbit.yaml",     "CodeRabbit",   False),
    (".coderabbit.yaml",    "CodeRabbit",   False),
    (".coderabbit",         "CodeRabbit",   True),
    # Mentat
    (".mentat",             "Mentat",       True),
    # Graphite
    (".graphite",           "Graphite",     True),
    # Ellipsis
    (".ellipsis.yaml",      "Ellipsis",     False),
    (".ellipsis",           "Ellipsis",     True),
    # Sourcegraph Cody
    (".sourcegraph",        "Sourcegraph Cody", True),
    # Tabnine
    (".tabnine",            "Tabnine",      True),
    # Cursor
    (".cursorrules",        "Cursor",       False),
    (".cursor",             "Cursor",       True),
]

BATCH_SIZE = 10   # repos per GraphQL batch for existence checks


# ── GitHub REST helpers ────────────────────────────────────────────────────────
def _get_json(url: str, params: dict | None = None) -> tuple[int, object]:
    """GET with rate-limit handling. Returns (status_code, json_body)."""
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=20)
            if r.status_code == 200:
                return 200, r.json()
            if r.status_code == 404:
                return 404, None
            if r.status_code in (403, 429):
                reset = int(r.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait  = max(reset - int(time.time()), 1)
                time.sleep(min(wait, 120))
            elif r.status_code in (502, 503):
                time.sleep(5 * (attempt + 1))
        except requests.RequestException:
            time.sleep(5 * (attempt + 1))
    return -1, None


def path_exists(owner: str, repo: str, path: str, is_dir: bool) -> bool:
    """
    Returns True if the given path exists in the repo's default branch.
    For directories: calls the contents API and checks for a non-empty list.
    For files: calls the contents API and checks for a file object.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    status, body = _get_json(url)
    if status != 200 or body is None:
        return False
    if is_dir:
        return isinstance(body, list) and len(body) > 0
    else:
        return isinstance(body, dict) and body.get("type") == "file"


def scan_repo_configs(owner: str, repo: str) -> dict[str, set[str]]:
    """
    Check all CONFIG_ENTRIES for the given repo.
    Returns dict: {path: {tool_name, ...}} for every found path.
    """
    found: dict[str, set[str]] = {}
    for path, tool, is_dir in CONFIG_ENTRIES:
        if path_exists(owner, repo, path, is_dir):
            found.setdefault(path, set()).add(tool)
        time.sleep(0.04)   # ~25 req/s to stay well under rate limit
    return found


# ── Signal helpers ────────────────────────────────────────────────────────────
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
    print("Stage 5c -- Extended Config File Detection")
    print("=" * 60)

    if not IN_FILE.exists():
        raise SystemExit(f"Input file not found: {IN_FILE}\nRun stage5b first.")

    unclassified = pd.read_csv(IN_FILE)
    corpus       = pd.read_csv(STAGE3_CSV, low_memory=False)
    corpus_idx   = corpus.set_index("full_name")

    repos = unclassified["full_name"].tolist()
    total = len(repos)
    print(f"Repos to scan : {total:,}\n")

    results          = []
    new_agentic      = 0
    new_ai_assisted  = 0

    for idx, full_name in enumerate(repos, 1):
        owner, repo = full_name.split("/", 1)
        found_paths = scan_repo_configs(owner, repo)

        # Gather tools detected
        detected_tools: set[str] = set()
        for paths_tools in found_paths.values():
            detected_tools |= paths_tools

        # Pull original Stage-3 row
        if full_name in corpus_idx.index:
            orig = corpus_idx.loc[full_name]
        else:
            orig = {}

        def _get(col, default=""):
            try:
                val = orig[col]
                return val if not pd.isna(val) else default
            except (KeyError, TypeError):
                return default

        prev_label = unclassified[unclassified["full_name"] == full_name]["new_label"].iloc[0]

        if detected_tools:
            # MEDIUM signal: config_file
            strong = [f.strip() for f in str(_get("strong_families") or "").split("|") if f.strip()]
            medium = combine_families(_get("medium_families"), "config_file")
            weak   = [f.strip() for f in str(_get("weak_families")   or "").split("|") if f.strip()]
            attr   = int(_get("agent_attributed_count", 0) or 0)
            label  = classify(strong, medium, weak, attr)
            configs_str = "|".join(sorted(found_paths.keys()))
            tools_str   = "|".join(sorted(detected_tools))
            if label == "agentic":
                new_agentic += 1
            elif label == "ai_assisted" and prev_label != "ai_assisted":
                new_ai_assisted += 1
        else:
            label       = prev_label
            strong      = str(_get("strong_families") or "")
            medium      = str(_get("medium_families") or "")
            weak        = str(_get("weak_families")   or "")
            attr        = _get("agent_attributed_count", 0)
            configs_str = ""
            tools_str   = ""

        results.append({
            "full_name":              full_name,
            "prev_label":             prev_label,
            "new_label":              label,
            "upgraded":               label != prev_label,
            "configs_found":          configs_str,
            "tools_found":            tools_str,
            "strong_families_final":  "|".join(strong) if isinstance(strong, list) else (strong or ""),
            "medium_families_final":  "|".join(medium) if isinstance(medium, list) else (medium or ""),
            "weak_families_final":    "|".join(weak)   if isinstance(weak, list)   else (weak   or ""),
            "agent_attributed_count": attr,
        })

        if idx % 200 == 0:
            print(f"  [{idx:>6}/{total}]  new agentic: {new_agentic:,}  "
                  f"new ai_assisted: {new_ai_assisted:,}")

    results_df = pd.DataFrame(results)
    results_df.to_csv(OUT_RESULTS, index=False)

    still_unclassified = results_df[results_df["new_label"].isin(["none", "ai_assisted"])][
        ["full_name", "new_label"]
    ]
    still_unclassified.to_csv(OUT_UNREC, index=False)

    print(f"\n{'=' * 60}")
    print(f"New agentic upgrades   : {results_df[results_df['new_label'] == 'agentic'].shape[0]:,}")
    print(f"New ai_assisted labels : {results_df[(results_df['new_label'] == 'ai_assisted') & (results_df['prev_label'] == 'none')].shape[0]:,}")
    print(f"Remaining unclassified : {len(still_unclassified):,}")
    print(f"Saved: {OUT_RESULTS.name}  ({len(results_df):,} rows)")
    print(f"Saved: {OUT_UNREC.name}  ({len(still_unclassified):,} rows)")
    print("\nStage 5c complete.")


if __name__ == "__main__":
    main()

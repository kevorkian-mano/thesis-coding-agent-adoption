#!/usr/bin/env python3
"""
Stage 5a -- Extended Bot Author Detection
==========================================
Scans the 20,633 repos still labelled none or ai_assisted in
corpus_detected_full_v2.csv for commits and pull requests authored
by AI agent bot accounts that were not included in the Stage 3 detection set.

New bot accounts checked (in addition to Stage 3 set):
  sweep-ai[bot]              Sweep AI  -- autonomous PR-opening agent
  openhands-agent[bot]       OpenHands (All-Hands AI)
  codegen-sh[bot]            Codegen (Automorphic)
  amazon-q-developer[bot]    Amazon Q Developer
  coderabbitai[bot]          CodeRabbit AI reviewer
  junie[bot]                 JetBrains Junie
  factory-bot[bot]           Factory AI
  github-copilot[bot]        GitHub Copilot Autofix / Coding Agent
  devin-ai-integration[bot]  Devin (alternate account name)
  jules-google[bot]          Jules (alternate account name)
  ellipsis-dev[bot]          Ellipsis code review bot
  greptileai[bot]            Greptile AI reviewer

Signal family : bot_author  (STRONG)
Classification: any confirmed bot author commit or PR → agentic immediately

Input
-----
  data/stage3/corpus_detected_full_v2.csv   (labels: none + ai_assisted)

Output
------
  data/stage5/stage5a_results.csv           -- all target repos with new label
  data/stage5/stage5a_unclassified.csv      -- repos still none/ai_assisted → input for 5b

Usage
-----
  export GITHUB_TOKEN=ghp_...
  python3 scripts/stage5/stage5a_extended_bots.py
"""

import os
import re
import time
import requests
import pandas as pd
from pathlib import Path

ROOT       = Path(__file__).resolve().parents[2]
CORPUS_V2  = ROOT / "data" / "stage3" / "corpus_detected_full_v2.csv"
OUT_DIR    = ROOT / "data" / "stage5"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_RESULTS = OUT_DIR / "stage5a_results.csv"
OUT_UNREC   = OUT_DIR / "stage5a_unclassified.csv"

TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    raise SystemExit("Set GITHUB_TOKEN before running.")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type":  "application/json",
}

# ── new bot accounts not in Stage 3 set ───────────────────────────────────────
NEW_BOT_ACCOUNTS = {
    "sweep-ai[bot]",
    "openhands-agent[bot]",
    "codegen-sh[bot]",
    "amazon-q-developer[bot]",
    "coderabbitai[bot]",
    "junie[bot]",
    "factory-bot[bot]",
    "github-copilot[bot]",
    "devin-ai-integration[bot]",
    "jules-google[bot]",
    "ellipsis-dev[bot]",
    "greptileai[bot]",
}

# Map bot account → tool name for reporting
BOT_TO_TOOL = {
    "sweep-ai[bot]":             "Sweep AI",
    "openhands-agent[bot]":      "OpenHands",
    "codegen-sh[bot]":           "Codegen",
    "amazon-q-developer[bot]":   "Amazon Q",
    "coderabbitai[bot]":         "CodeRabbit",
    "junie[bot]":                "Junie",
    "factory-bot[bot]":          "Factory AI",
    "github-copilot[bot]":       "GitHub Copilot",
    "devin-ai-integration[bot]": "Devin",
    "jules-google[bot]":         "Jules",
    "ellipsis-dev[bot]":         "Ellipsis",
    "greptileai[bot]":           "Greptile",
}

BATCH_SIZE = 5
COMMIT_DEPTH = 200
PR_DEPTH = 50

# ── GraphQL query ─────────────────────────────────────────────────────────────
def build_query(repos: list[tuple[str, str]]) -> str:
    """
    repos: list of (alias, owner/name) tuples
    Fetches last COMMIT_DEPTH commits + COMMIT_DEPTH PR authors per repo.
    """
    fragments = []
    for alias, full_name in repos:
        owner, name = full_name.split("/", 1)
        fragments.append(f"""
  {alias}: repository(owner: "{owner}", name: "{name}") {{
    commits: defaultBranchRef {{
      target {{
        ... on Commit {{
          history(first: {COMMIT_DEPTH}) {{
            nodes {{
              author {{ user {{ login }} }}
              committer {{ user {{ login }} }}
            }}
          }}
        }}
      }}
    }}
    pullRequests(first: {PR_DEPTH}, states: [OPEN, CLOSED, MERGED]) {{
      nodes {{
        author {{ login }}
        headRefName
      }}
    }}
  }}
""")
    return "{ " + "\n".join(fragments) + " }"


def safe_login(obj) -> str:
    if obj and isinstance(obj, dict):
        return (obj.get("login") or "").lower()
    return ""


def run_query(query: str) -> dict:
    for attempt in range(3):
        try:
            r = requests.post(
                "https://api.github.com/graphql",
                json={"query": query},
                headers=HEADERS,
                timeout=30,
            )
            if r.status_code == 200:
                data = r.json()
                # GitHub GraphQL returns partial results even with errors
                # (e.g. one deleted/private repo in a batch). Keep the data.
                return data.get("data", {})
            if r.status_code in (502, 503):
                time.sleep(5 * (attempt + 1))
        except requests.RequestException:
            time.sleep(5 * (attempt + 1))
    return {}


# ── classify (same rule as Stage 3) ─────────────────────────────────────────
def combine_families(existing: str | float, new_family: str) -> list[str]:
    """Merge existing signal families string with a new family."""
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
    print("Stage 5a -- Extended Bot Author Detection")
    print("=" * 60)

    corpus = pd.read_csv(CORPUS_V2, low_memory=False)
    target = corpus[corpus["adoption_label"].isin(["none", "ai_assisted"])].copy()
    print(f"Target repos : {len(target):,}  (none: {(target.adoption_label=='none').sum():,}  "
          f"ai_assisted: {(target.adoption_label=='ai_assisted').sum():,})")

    repos = target["full_name"].tolist()
    results = []
    new_agentic = 0

    batches = [repos[i:i+BATCH_SIZE] for i in range(0, len(repos), BATCH_SIZE)]
    print(f"Batches      : {len(batches):,}  (size {BATCH_SIZE})\n")

    for batch_idx, batch in enumerate(batches):
        aliases = [(f"r{i}", rn) for i, rn in enumerate(batch)]
        query   = build_query(aliases)
        data    = run_query(query)

        for alias, full_name in aliases:
            repo_data = data.get(alias) or {}
            orig_row  = target[target["full_name"] == full_name].iloc[0]

            detected_bots  = set()
            detected_tools = set()

            # Commit authors
            commits_obj = repo_data.get("commits") or {}
            target_obj  = (commits_obj.get("target") or {})
            history     = (target_obj.get("history") or {}).get("nodes", [])
            for node in (history or []):
                for role in ("author", "committer"):
                    login = safe_login((node.get(role) or {}).get("user"))
                    # normalise [bot] suffix for matching
                    for bot in NEW_BOT_ACCOUNTS:
                        if bot.replace("[bot]", "").lower() in login:
                            detected_bots.add(bot)
                            detected_tools.add(BOT_TO_TOOL.get(bot, bot))

            # PR authors and branch names
            prs = (repo_data.get("pullRequests") or {}).get("nodes", [])
            for pr in (prs or []):
                login = safe_login(pr.get("author"))
                for bot in NEW_BOT_ACCOUNTS:
                    if bot.replace("[bot]", "").lower() in login:
                        detected_bots.add(bot)
                        detected_tools.add(BOT_TO_TOOL.get(bot, bot))

            if detected_bots:
                # STRONG signal → agentic
                strong = combine_families(orig_row.get("strong_families"), "bot_author")
                medium = [f.strip() for f in str(orig_row.get("medium_families", "") or "").split("|") if f.strip()]
                weak   = [f.strip() for f in str(orig_row.get("weak_families",   "") or "").split("|") if f.strip()]
                attr   = int(orig_row.get("agent_attributed_count", 0) or 0)
                label  = classify(strong, medium, weak, attr)
                agents = "|".join(sorted(detected_tools))
                new_agentic += 1
            else:
                label  = orig_row["adoption_label"]
                strong = orig_row.get("strong_families", "")
                medium = orig_row.get("medium_families", "")
                weak   = orig_row.get("weak_families",   "")
                attr   = orig_row.get("agent_attributed_count", 0)
                agents = orig_row.get("agents_found", "")

            results.append({
                "full_name":              full_name,
                "prev_label":             orig_row["adoption_label"],
                "new_label":              label,
                "upgraded":               label == "agentic" and orig_row["adoption_label"] != "agentic",
                "bots_found":             "|".join(sorted(detected_bots)),
                "tools_found":            agents,
                "strong_families_final":  "|".join(strong) if isinstance(strong, list) else (strong or ""),
                "medium_families_final":  "|".join(medium) if isinstance(medium, list) else (medium or ""),
                "weak_families_final":    "|".join(weak)   if isinstance(weak, list)   else (weak   or ""),
                "agent_attributed_count": attr,
            })

        if (batch_idx + 1) % 100 == 0:
            print(f"  [{batch_idx+1:>5}/{len(batches)}]  new agentic so far: {new_agentic:,}")

        time.sleep(0.25)

    results_df = pd.DataFrame(results)
    results_df.to_csv(OUT_RESULTS, index=False)

    unclassified = results_df[results_df["new_label"].isin(["none", "ai_assisted"])][["full_name", "new_label"]]
    unclassified.to_csv(OUT_UNREC, index=False)

    print(f"\n{'=' * 60}")
    print(f"New agentic upgrades : {results_df['upgraded'].sum():,}")
    print(f"Remaining unclassified: {len(unclassified):,}  → input for Stage 5b")
    print(f"Saved: {OUT_RESULTS.name}  ({len(results_df):,} rows)")
    print(f"Saved: {OUT_UNREC.name}  ({len(unclassified):,} rows)")
    print("\nStage 5a complete.")


if __name__ == "__main__":
    main()

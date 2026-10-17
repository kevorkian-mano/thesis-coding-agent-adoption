#!/usr/bin/env python3
"""
Stage 3a -- Pass 1: Configuration File Check
=============================================
Checks every repo in global_corpus.csv for the presence of known AI agent
configuration files at the repository root. Uses a single GraphQL query per
repo (batched). If any config file is found the repo is immediately labelled
agentic and never touched again by Pass 2 or 3.

This is the cheapest possible signal -- file existence, no content reading.
Config files are hard positives: nobody accidentally creates a CLAUDE.md.

Output
------
data/stage3/pass1_results.csv
  full_name, config_file_found, agent_detected, adoption_label, signal_source

data/stage3/pass1_unclassified.csv
  full_name  (repos with no config file -- input for stage3b)

Usage
-----
  export GITHUB_TOKEN=ghp_...
  python3 scripts/stage3/stage3a_config_files.py
"""

import os
import time
import requests
import pandas as pd
from pathlib import Path

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).resolve().parents[2]
CORPUS    = ROOT / "data" / "stage1" / "global_corpus.csv"
OUT_DIR   = ROOT / "data" / "stage3"
OUT_PASS1 = OUT_DIR / "pass1_results.csv"
OUT_UNRES = OUT_DIR / "pass1_unclassified.csv"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    raise SystemExit("Set GITHUB_TOKEN environment variable before running.")

HEADERS     = {"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"}
GRAPHQL_URL = "https://api.github.com/graphql"
BATCH_SIZE  = 10     # repos per GraphQL request
SLEEP_OK    = 0.8
SLEEP_RETRY = 60
SAVE_EVERY  = 500    # save to disk every N repos

# ── known agent config files ──────────────────────────────────────────────────
CONFIG_FILES = {
    "CLAUDE.md":                          "Claude Code",
    "AGENTS.md":                          "Claude Code / Generic",
    ".cursorrules":                       "Cursor",
    ".cursorignore":                      "Cursor",
    ".aider.conf.yml":                    "Aider",
    ".roomodes":                          "Roo Code",
    ".windsurfrules":                     "Windsurf",
    "GEMINI.md":                          "Gemini CLI",
    ".github/copilot-instructions.md":    "GitHub Copilot",
    ".continue/config.json":              "Continue",
    ".codeium/config.json":               "Codeium",
    "AGENTS.json":                        "OpenAI Codex",
}

def build_query(repos: list[tuple[str, str]]) -> str:
    """Build a GraphQL query to check config files for a batch of repos."""
    parts = []
    for i, (owner, name) in enumerate(repos):
        file_checks = "\n".join(
            f'      f{j}: object(expression: "HEAD:{fname}") {{ __typename }}'
            for j, fname in enumerate(CONFIG_FILES.keys())
        )
        parts.append(f"""
  r{i}: repository(owner: "{owner}", name: "{name}") {{
    nameWithOwner
{file_checks}
  }}""")
    return "{ " + "\n".join(parts) + " }"

def parse_result(repo_data: dict) -> tuple[bool, str, str]:
    """
    Returns (found, agent_name, file_found).
    """
    filenames = list(CONFIG_FILES.keys())
    for j, fname in enumerate(filenames):
        node = repo_data.get(f"f{j}")
        if node and node.get("__typename"):
            return True, CONFIG_FILES[fname], fname
    return False, "", ""

def fetch_batch(repos: list[tuple[str, str]]) -> dict:
    """Returns {full_name: repo_data_dict}"""
    query = build_query(repos)
    for attempt in range(5):
        try:
            resp = requests.post(GRAPHQL_URL, json={"query": query}, headers=HEADERS, timeout=30)
        except Exception as e:
            wait = 10 * (attempt + 1)
            print(f"  Network error ({e.__class__.__name__}), retry {attempt+1}/5 in {wait}s ...")
            time.sleep(wait)
            continue
        if resp.status_code == 200:
            data = resp.json().get("data") or {}
            result = {}
            for i, (owner, name) in enumerate(repos):
                full_name = f"{owner}/{name}"
                result[full_name] = data.get(f"r{i}") or {}
            return result
        elif resp.status_code in (403, 429):
            print(f"  Rate limited. Sleeping {SLEEP_RETRY}s ...")
            time.sleep(SLEEP_RETRY)
        else:
            print(f"  HTTP {resp.status_code} attempt {attempt+1}")
            time.sleep(5)
    return {f"{o}/{n}": {} for o, n in repos}

# ── main ──────────────────────────────────────────────────────────────────────
def main():
    print("Stage 3a -- Pass 1: Configuration File Check")
    print("=" * 55)

    df = pd.read_csv(CORPUS, low_memory=False)
    all_repos = list(zip(df["owner_login"], df["repo_name"]))
    full_names = [f"{o}/{n}" for o, n in all_repos]
    print(f"Total repos: {len(full_names):,}")

    # Resume support
    if OUT_PASS1.exists():
        done = set(pd.read_csv(OUT_PASS1)["full_name"].tolist())
        pairs = [(o, n) for o, n in all_repos if f"{o}/{n}" not in done]
        print(f"Resuming: {len(pairs):,} repos remaining")
    else:
        pairs = all_repos

    results  = []
    total    = len(pairs)
    agentic  = 0

    for start in range(0, total, BATCH_SIZE):
        batch   = pairs[start:start + BATCH_SIZE]
        fetched = fetch_batch(batch)

        for owner, name in batch:
            full_name = f"{owner}/{name}"
            repo_data = fetched.get(full_name, {})
            found, agent, fname = parse_result(repo_data)

            if found:
                label = "agentic"
                agentic += 1
            else:
                label = "unclassified"

            results.append({
                "full_name":         full_name,
                "config_file_found": fname if found else "",
                "agent_detected":    agent if found else "",
                "adoption_label":    label,
                "signal_source":     "config_file" if found else "",
            })

        done_count = start + len(batch)
        if done_count % SAVE_EVERY == 0 or done_count == total:
            pct = done_count / total * 100
            print(f"  {done_count:>6,}/{total:,} ({pct:.1f}%)  agentic so far: {agentic:,}")
            # incremental save
            chunk = pd.DataFrame(results)
            if OUT_PASS1.exists():
                existing = pd.read_csv(OUT_PASS1)
                chunk = pd.concat([existing, chunk], ignore_index=True)
            chunk.to_csv(OUT_PASS1, index=False)
            results = []  # clear buffer after saving

        time.sleep(SLEEP_OK)

    # Final save of any remaining buffer
    if results:
        chunk = pd.DataFrame(results)
        if OUT_PASS1.exists():
            existing = pd.read_csv(OUT_PASS1)
            chunk = pd.concat([existing, chunk], ignore_index=True)
        chunk.to_csv(OUT_PASS1, index=False)

    new_df = pd.read_csv(OUT_PASS1)

    # Save unclassified for Pass 2
    unclassified = new_df[new_df["adoption_label"] == "unclassified"][["full_name"]]
    unclassified.to_csv(OUT_UNRES, index=False)

    # Summary
    total_proc   = len(new_df)
    n_agentic    = (new_df["adoption_label"] == "agentic").sum()
    n_unclassified = (new_df["adoption_label"] == "unclassified").sum()

    print()
    print("=" * 55)
    print(f"Total processed   : {total_proc:,}")
    print(f"Agentic (Pass 1)  : {n_agentic:,}  ({n_agentic/total_proc*100:.1f}%)")
    print(f"Unclassified      : {n_unclassified:,}  ({n_unclassified/total_proc*100:.1f}%)  -> pass to stage3b")
    print()
    print("Top agents detected:")
    top = new_df[new_df["agent_detected"] != ""].groupby("agent_detected").size().sort_values(ascending=False)
    for agent, count in top.items():
        print(f"  {agent:<35} {count:>6,}")
    print()
    print(f"Saved: {OUT_PASS1}")
    print(f"Saved: {OUT_UNRES}")

if __name__ == "__main__":
    main()

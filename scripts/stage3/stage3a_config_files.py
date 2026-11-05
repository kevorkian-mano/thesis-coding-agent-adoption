#!/usr/bin/env python3
"""
Stage 3a -- Pass A: Configuration File Check
=============================================
Checks every repo in global_corpus.csv for the presence of known AI agent
configuration files at the repository root. Uses a single GraphQL query per
batch of repos (BATCH_SIZE = 10).

ALL matching config files are recorded per repo (not just the first one).
This means a repo with both CLAUDE.md and .junie/ will show both agents in
agents_found.

Any config file hit -> labelled agentic immediately and skipped by Pass B/C.
Repos with no hit -> written to pass1_unclassified.csv for Pass B.

Config files are hard positives: nobody accidentally creates a CLAUDE.md or
a .pr_agent.toml. These are deliberate, dedicated agent configuration files.

Output
------
data/stage3/pass1_results.csv
  full_name, config_files_found, agents_found, adoption_label, signal_source

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
BATCH_SIZE  = 5      # repos per GraphQL request (lower = fewer 5xx timeouts)
SLEEP_OK    = 0.8
SLEEP_RETRY = 60
SAVE_EVERY  = 500    # save to disk every N repos

# ── known agent config files / directories ────────────────────────────────────
# Key   : path relative to repo root (directories have trailing / stripped for
#         GraphQL but are detected as Tree objects just like files)
# Value : human-readable agent name
#
# Ordering: more specific paths first so that the alias comment stays clear.
# All entries here are hard positives -- deliberate, dedicated agent configs.
CONFIG_FILES = {
    # ── Claude Code (Anthropic) ───────────────────────────────────────────────
    "CLAUDE.md":                            "Claude Code",
    ".claude":                              "Claude Code",        # settings/commands dir
    "AGENTS.md":                            "Generic",            # shared by Codex/Jules/Cursor/Aider
    # ── OpenAI Codex ─────────────────────────────────────────────────────────
    "AGENTS.json":                          "OpenAI Codex",
    # ── Cursor ───────────────────────────────────────────────────────────────
    ".cursorrules":                         "Cursor",
    ".cursorignore":                        "Cursor",
    ".cursor/rules":                        "Cursor",             # nested rules dir (agentic use)
    # ── Aider ────────────────────────────────────────────────────────────────
    ".aider.conf.yml":                      "Aider",
    ".aiderignore":                         "Aider",
    # ── Cline ────────────────────────────────────────────────────────────────
    ".clinerules":                          "Cline / Roo Code",   # shared — Cline invented, Roo forked
    ".cline":                               "Cline",              # Cline-specific dir
    # ── Roo Code ─────────────────────────────────────────────────────────────
    ".roomodes":                            "Roo Code",
    ".roo":                                 "Roo Code",
    ".roosettings":                         "Roo Code",
    # ── Windsurf (Codeium) ───────────────────────────────────────────────────
    ".windsurfrules":                       "Windsurf",
    # ── Gemini CLI ───────────────────────────────────────────────────────────
    "GEMINI.md":                            "Gemini CLI",
    # ── GitHub Copilot ───────────────────────────────────────────────────────
    ".github/copilot-instructions.md":      "GitHub Copilot",
    # ── Continue ─────────────────────────────────────────────────────────────
    ".continue/config.json":               "Continue",
    # ── Codeium ──────────────────────────────────────────────────────────────
    ".codeium/config.json":                "Codeium",
    # ── Replit ───────────────────────────────────────────────────────────────
    ".replit":                              "Replit",
    # ── DeepSource ───────────────────────────────────────────────────────────
    ".deepsource.toml":                     "DeepSource",
    # ── PR-Agent / CodiumAI ──────────────────────────────────────────────────
    ".pr_agent.toml":                       "PR-Agent",
    # ── Junie (JetBrains) ────────────────────────────────────────────────────
    ".junie":                               "Junie",
    # ── Sourcery ─────────────────────────────────────────────────────────────
    ".sourcery.yaml":                       "Sourcery",
    # ── Kiro (Amazon) ────────────────────────────────────────────────────────
    ".kiro":                                "Kiro",
    # ── OpenCode ─────────────────────────────────────────────────────────────
    ".opencode":                            "OpenCode",
    # ── CodeRabbit ───────────────────────────────────────────────────────────
    "coderabbit.yaml":                      "CodeRabbit",
    ".coderabbit.yaml":                     "CodeRabbit",
    ".coderabbit":                          "CodeRabbit",         # config dir
    # ── Sweep AI ─────────────────────────────────────────────────────────────
    "sweep.yaml":                           "Sweep",
    ".sweep":                               "Sweep",              # config dir
    # ── Ellipsis ─────────────────────────────────────────────────────────────
    ".ellipsis.yaml":                       "Ellipsis",
    # ── Devin (Cognition) ────────────────────────────────────────────────────
    ".devin":                               "Devin",
    # ── Amp (Sourcegraph) ────────────────────────────────────────────────────
    "AGENT.md":                             "Amp",                # Amp-specific guidance file
    # ── Amazon Q Developer ───────────────────────────────────────────────────
    ".amazonq":                             "Amazon Q",
    # ── Codegen ──────────────────────────────────────────────────────────────
    ".codegen":                             "Codegen",
    # ── Goose (Block) ────────────────────────────────────────────────────────
    ".goose":                               "Goose",
    # ── Trae / MarsCode (ByteDance) ──────────────────────────────────────────
    ".marscode":                            "Trae / MarsCode",
    ".trae":                                "Trae / MarsCode",
    # ── SpecKit ──────────────────────────────────────────────────────────────
    ".speckit":                             "SpecKit",
    # ── Serena ───────────────────────────────────────────────────────────────
    ".serena":                              "Serena",
    # ── Mistral Vibe ─────────────────────────────────────────────────────────
    ".mistral":                             "Mistral Vibe",
    # ── Letta Code ───────────────────────────────────────────────────────────
    ".letta":                               "Letta Code",
    # ── Abacus AI ────────────────────────────────────────────────────────────
    ".abacus":                              "Abacus AI",
    # ── Paperclip ────────────────────────────────────────────────────────────
    ".paperclip":                           "Paperclip",
    # ── Kimi Code (Moonshot AI) ──────────────────────────────────────────────
    ".kimi":                                "Kimi Code",
    # ── Atlassian Rovodev ────────────────────────────────────────────────────
    ".rovodev":                             "Atlassian Rovodev",
    # ── SpecStory ────────────────────────────────────────────────────────────
    ".specstory":                           "SpecStory",
    # ── Augment Code ─────────────────────────────────────────────────────────
    ".augment":                             "Augment Code",
    # ── Gru ──────────────────────────────────────────────────────────────────
    ".gru":                                 "Gru",
    # ── Pi ───────────────────────────────────────────────────────────────────
    ".pi":                                  "Pi",
    # ── Qwen Code (Alibaba) ──────────────────────────────────────────────────
    ".qwen":                                "Qwen Code",
    # ── Plandex ──────────────────────────────────────────────────────────────
    ".plandex":                             "Plandex",
}


def build_query(repos: list[tuple[str, str]]) -> str:
    """Build a GraphQL query to check ALL config files for a batch of repos."""
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


def parse_result(repo_data: dict) -> tuple[list[str], list[str]]:
    """
    Scan ALL config file positions and return:
      (files_found_list, agents_found_list)
    Both lists may contain duplicates (e.g. two CodeRabbit files) -- deduplication
    is applied before writing to CSV.
    """
    filenames = list(CONFIG_FILES.keys())
    agents    = {}   # agent -> True  (ordered dict for determinism, dedup)
    files     = []

    for j, fname in enumerate(filenames):
        node = repo_data.get(f"f{j}")
        if node and node.get("__typename"):
            files.append(fname)
            agents[CONFIG_FILES[fname]] = True

    return files, list(agents.keys())


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
            time.sleep(20)
    return {f"{o}/{n}": {} for o, n in repos}


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    print("Stage 3a -- Pass A: Configuration File Check")
    print("=" * 55)
    print(f"Config files checked per repo: {len(CONFIG_FILES)}")

    df = pd.read_csv(CORPUS, low_memory=False)
    all_repos = list(zip(df["owner_login"], df["repo_name"]))
    full_names = [f"{o}/{n}" for o, n in all_repos]
    print(f"Total repos: {len(full_names):,}")

    # Resume support -- detect stale files from old schema and discard them
    if OUT_PASS1.exists():
        existing = pd.read_csv(OUT_PASS1)
        if "agents_found" not in existing.columns:
            print("  Old-format pass1_results.csv detected -- discarding and restarting.")
            OUT_PASS1.unlink()
            pairs = all_repos
        else:
            done = set(existing["full_name"].tolist())
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
            files_found, agents_found = parse_result(repo_data)

            if files_found:
                label = "agentic"
                agentic += 1
            else:
                label = "unclassified"

            results.append({
                "full_name":          full_name,
                "config_files_found": "|".join(files_found),
                "agents_found":       "|".join(agents_found),
                "adoption_label":     label,
                "signal_source":      "config_file" if files_found else "",
            })

        done_count = start + len(batch)
        if done_count % SAVE_EVERY == 0 or done_count == total:
            pct = done_count / total * 100
            print(f"  {done_count:>6,}/{total:,} ({pct:.1f}%)  agentic so far: {agentic:,}")
            chunk = pd.DataFrame(results)
            if OUT_PASS1.exists():
                existing = pd.read_csv(OUT_PASS1)
                chunk = pd.concat([existing, chunk], ignore_index=True)
            chunk.to_csv(OUT_PASS1, index=False)
            results = []

        time.sleep(SLEEP_OK)

    # Final save of any remaining buffer
    if results:
        chunk = pd.DataFrame(results)
        if OUT_PASS1.exists():
            existing = pd.read_csv(OUT_PASS1)
            chunk = pd.concat([existing, chunk], ignore_index=True)
        chunk.to_csv(OUT_PASS1, index=False)

    new_df = pd.read_csv(OUT_PASS1)

    # Save unclassified for Pass B
    unclassified = new_df[new_df["adoption_label"] == "unclassified"][["full_name"]]
    unclassified.to_csv(OUT_UNRES, index=False)

    # Summary
    total_proc     = len(new_df)
    n_agentic      = (new_df["adoption_label"] == "agentic").sum()
    n_unclassified = (new_df["adoption_label"] == "unclassified").sum()

    print()
    print("=" * 55)
    print(f"Total processed   : {total_proc:,}")
    print(f"Agentic (Pass A)  : {n_agentic:,}  ({n_agentic/total_proc*100:.1f}%)")
    print(f"Unclassified      : {n_unclassified:,}  ({n_unclassified/total_proc*100:.1f}%)  -> pass to stage3b")
    print()
    print("Top agents detected:")
    # Expand pipe-separated agents_found for counting
    agent_series = (
        new_df[new_df["agents_found"] != ""]["agents_found"]
        .str.split("|")
        .explode()
    )
    top = agent_series.value_counts()
    for agent, count in top.items():
        print(f"  {agent:<40} {count:>6,}")
    print()
    print(f"Saved: {OUT_PASS1}")
    print(f"Saved: {OUT_UNRES}")


if __name__ == "__main__":
    main()

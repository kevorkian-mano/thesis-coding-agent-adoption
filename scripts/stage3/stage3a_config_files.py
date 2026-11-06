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
BATCH_SIZE  = 10     # repos per GraphQL request
SLEEP_OK    = 0.5
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
    # ── Qwen Code (Alibaba) ──────────────────────────────────────────────────
    ".qwen":                                "Qwen Code",
    # ── Plandex ──────────────────────────────────────────────────────────────
    ".plandex":                             "Plandex",
}


# ── split config files into root-level vs nested paths ───────────────────────
# Root-level: checked via repo root tree (one lightweight query for all names)
# Nested    : checked via individual object queries (only 4 paths)
_ROOT_CONFIGS   = {k: v for k, v in CONFIG_FILES.items() if "/" not in k}
_NESTED_CONFIGS = {k: v for k, v in CONFIG_FILES.items() if "/" in k}
_NESTED_KEYS    = list(_NESTED_CONFIGS.keys())


def _build_tree_query(repos: list[tuple[str, str]]) -> str:
    """Fetch root directory tree entries for every repo — one lightweight query."""
    parts = []
    for i, (owner, name) in enumerate(repos):
        parts.append(f"""
  r{i}: repository(owner: "{owner}", name: "{name}") {{
    nameWithOwner
    object(expression: "HEAD:") {{
      ... on Tree {{
        entries {{ name type }}
      }}
    }}
  }}""")
    return "{ " + "\n".join(parts) + " }"


def _build_nested_query(repos: list[tuple[str, str]]) -> str:
    """Check the small set of nested config paths (e.g. .github/copilot-instructions.md)."""
    parts = []
    for i, (owner, name) in enumerate(repos):
        checks = "\n".join(
            f'      n{j}: object(expression: "HEAD:{fname}") {{ __typename }}'
            for j, fname in enumerate(_NESTED_KEYS)
        )
        parts.append(f"""
  r{i}: repository(owner: "{owner}", name: "{name}") {{
{checks}
  }}""")
    return "{ " + "\n".join(parts) + " }"


def parse_result(repo_data: dict) -> tuple[list[str], list[str]]:
    """Return (files_found, agents_found) from merged tree + nested query data."""
    agents = {}
    files  = []

    # Root-level: check tree entries by name
    entries    = ((repo_data.get("object") or {}).get("entries")) or []
    root_names = {e["name"] for e in entries}
    for fname, agent in _ROOT_CONFIGS.items():
        if fname in root_names:
            files.append(fname)
            agents[agent] = True

    # Nested paths: individual object lookups
    for j, (fname, agent) in enumerate(_NESTED_CONFIGS.items()):
        node = repo_data.get(f"n{j}")
        if node and node.get("__typename"):
            files.append(fname)
            agents[agent] = True

    return files, list(agents.keys())


def _run_query(query: str) -> dict:
    """Execute one GraphQL query with retry. Returns the data dict."""
    for attempt in range(5):
        try:
            resp = requests.post(GRAPHQL_URL, json={"query": query}, headers=HEADERS, timeout=30)
        except Exception as e:
            wait = 10 * (attempt + 1)
            print(f"  Network error ({e.__class__.__name__}), retry {attempt+1}/5 in {wait}s ...")
            time.sleep(wait)
            continue
        if resp.status_code == 200:
            try:
                return resp.json().get("data") or {}
            except Exception:
                print(f"  Empty/invalid JSON on attempt {attempt+1}/5, retrying in 10s ...")
                time.sleep(10)
                continue
        elif resp.status_code in (403, 429):
            print(f"  Rate limited. Sleeping {SLEEP_RETRY}s ...")
            time.sleep(SLEEP_RETRY)
        else:
            print(f"  HTTP {resp.status_code} attempt {attempt+1}")
            time.sleep(20)
    return {}


def fetch_batch(repos: list[tuple[str, str]]) -> dict:
    """Two lightweight queries per batch: (1) root tree, (2) nested paths."""
    # Query 1: root tree — returns all root filenames, we filter locally
    tree_data   = _run_query(_build_tree_query(repos))
    time.sleep(SLEEP_OK)
    # Query 2: nested paths — only 4 files, very small query
    nested_data = _run_query(_build_nested_query(repos))
    time.sleep(SLEEP_OK)

    merged = {}
    for i, (owner, name) in enumerate(repos):
        full_name       = f"{owner}/{name}"
        repo_tree       = tree_data.get(f"r{i}")   or {}
        repo_nested     = nested_data.get(f"r{i}") or {}
        merged[full_name] = {**repo_tree, **repo_nested}

    return merged


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

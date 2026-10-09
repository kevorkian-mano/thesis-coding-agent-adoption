#!/usr/bin/env python3
"""
Stage 5d — Co-adoption Analysis
==================================
Analyses which AI coding tools appear together in the same repository.

Questions answered:
  - Are developers loyal to one tool or do they use multiple?
  - Which tool combinations appear most often?
  - Do multi-tool repos have more signals (more intensive AI use)?
  - Does co-adoption differ between global and Egyptian corpora?

INPUTS
------
  data/stage4/signals_global.csv               — per-signal rows, global corpus
  data/stage4/signals_egypt_corpus_input.csv   — per-signal rows, Egyptian corpus
  data/stage4/sample_corpus_detected.csv       — global detected (for repo count)
  data/stage4/egypt_corpus_input_detected.csv  — Egyptian detected (for repo count)

OUTPUTS
-------
  data/stage5/coadoption_pairs.csv             — pairwise co-occurrence counts
  data/stage5/coadoption_repo_summary.csv      — per-repo tool count distribution

USAGE
-----
  python3 scripts/stage5/stage5d_coadoption.py
"""

import pandas as pd
from itertools import combinations
from pathlib import Path
from collections import Counter

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR        = Path(__file__).parent
DATA_DIR          = SCRIPT_DIR / "../../data"
SIGNALS_GLOBAL    = DATA_DIR / "stage4/signals_global.csv"
SIGNALS_EGYPT     = DATA_DIR / "stage4/signals_egypt_corpus_input.csv"
GLOBAL_DETECTED   = DATA_DIR / "stage4/sample_corpus_detected.csv"
EGYPT_DETECTED    = DATA_DIR / "stage4/egypt_corpus_input_detected.csv"
OUT_DIR           = DATA_DIR / "stage5"

OUT_DIR.mkdir(parents=True, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_signals(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["agent_name"] = df["agent_name"].fillna("unknown").str.strip().str.lower()
    return df


def agents_per_repo(signals_df: pd.DataFrame) -> pd.DataFrame:
    """Return one row per repo with the set of unique agents used."""
    return (
        signals_df.groupby("full_name")["agent_name"]
        .apply(lambda x: frozenset(x.unique()))
        .reset_index()
        .rename(columns={"agent_name": "agents"})
    )


def tool_count_label(n: int) -> str:
    if n == 1: return "1 tool"
    if n == 2: return "2 tools"
    if n == 3: return "3 tools"
    return "4+ tools"


def print_section(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    sig_global = load_signals(SIGNALS_GLOBAL)
    sig_egypt  = load_signals(SIGNALS_EGYPT)

    global_detected = pd.read_csv(GLOBAL_DETECTED)
    egypt_detected  = pd.read_csv(EGYPT_DETECTED)

    total_global = len(global_detected)
    total_egypt  = len(egypt_detected)

    # ── Per-repo agent sets ───────────────────────────────────────────────────
    repo_agents_global = agents_per_repo(sig_global)
    repo_agents_egypt  = agents_per_repo(sig_egypt)

    # ── Tool count distribution ───────────────────────────────────────────────
    print_section("Number of distinct tools per repo (adopted repos only)")

    summary_rows = []
    for label, repo_df, total in [
        ("Global",   repo_agents_global, total_global),
        ("Egyptian", repo_agents_egypt,  total_egypt),
    ]:
        repo_df = repo_df.copy()
        repo_df["n_tools"] = repo_df["agents"].map(len)
        dist = repo_df["n_tools"].value_counts().sort_index()
        print(f"\n  {label} (adopted repos = {len(repo_df)}, all repos = {total}):")
        for n_tools, count in dist.items():
            pct_of_adopted = count / len(repo_df) * 100
            pct_of_all     = count / total * 100
            label_str = tool_count_label(n_tools)
            print(f"    {label_str:<12} {count:>5} repos  "
                  f"({pct_of_adopted:.1f}% of adopters, "
                  f"{pct_of_all:.1f}% of all)")
            summary_rows.append({
                "corpus":      label,
                "n_tools":     n_tools,
                "n_repos":     count,
                "pct_adopters": round(pct_of_adopted, 1),
                "pct_all":     round(pct_of_all, 1),
            })

    pd.DataFrame(summary_rows).to_csv(
        OUT_DIR / "coadoption_repo_summary.csv", index=False
    )

    # ── Most used single tools ────────────────────────────────────────────────
    print_section("Most used tools — global (by repo count, not signal count)")
    tool_counts = Counter()
    for agents in repo_agents_global["agents"]:
        for a in agents:
            tool_counts[a] += 1
    for tool, count in tool_counts.most_common(10):
        pct = count / total_global * 100
        print(f"  {tool:<25} {count:>5} repos  ({pct:.1f}% of all)")

    print_section("Most used tools — Egyptian")
    tool_counts_eg = Counter()
    for agents in repo_agents_egypt["agents"]:
        for a in agents:
            tool_counts_eg[a] += 1
    for tool, count in tool_counts_eg.most_common(10):
        pct = count / total_egypt * 100
        print(f"  {tool:<25} {count:>5} repos  ({pct:.1f}% of all)")

    # ── Pairwise co-occurrence (global) ───────────────────────────────────────
    print_section("Tool pair co-occurrence — global (repos using both tools)")
    pair_counts = Counter()
    for agents in repo_agents_global["agents"]:
        if len(agents) >= 2:
            for pair in combinations(sorted(agents), 2):
                pair_counts[pair] += 1

    pair_rows = []
    print(f"\n  {'Tool A':<25} {'Tool B':<25} {'Repos':>6}")
    for (a, b), count in pair_counts.most_common(15):
        print(f"  {a:<25} {b:<25} {count:>6}")
        pair_rows.append({"tool_a": a, "tool_b": b,
                          "co_occurrence_repos": count, "corpus": "global"})

    # ── Pairwise co-occurrence (Egyptian) ─────────────────────────────────────
    print_section("Tool pair co-occurrence — Egyptian")
    pair_counts_eg = Counter()
    for agents in repo_agents_egypt["agents"]:
        if len(agents) >= 2:
            for pair in combinations(sorted(agents), 2):
                pair_counts_eg[pair] += 1

    if pair_counts_eg:
        print(f"\n  {'Tool A':<25} {'Tool B':<25} {'Repos':>6}")
        for (a, b), count in pair_counts_eg.most_common(10):
            print(f"  {a:<25} {b:<25} {count:>6}")
            pair_rows.append({"tool_a": a, "tool_b": b,
                              "co_occurrence_repos": count, "corpus": "egyptian"})
    else:
        print("  No co-adoption found in Egyptian corpus.")

    pd.DataFrame(pair_rows).to_csv(OUT_DIR / "coadoption_pairs.csv", index=False)

    # ── Tool loyalty: what % of adopters use ONLY Claude Code? ───────────────
    print_section("Tool loyalty — what % of adopters use only one tool?")
    for label, repo_df, total in [
        ("Global",   repo_agents_global, total_global),
        ("Egyptian", repo_agents_egypt,  total_egypt),
    ]:
        only_claude = repo_df[repo_df["agents"] == frozenset(["claude_code"])]
        single_tool = repo_df[repo_df["agents"].map(len) == 1]
        print(f"\n  {label}:")
        print(f"    Only Claude Code   : {len(only_claude)} repos "
              f"({len(only_claude)/len(repo_df)*100:.1f}% of adopters)")
        print(f"    Any single tool    : {len(single_tool)} repos "
              f"({len(single_tool)/len(repo_df)*100:.1f}% of adopters)")
        print(f"    Multiple tools     : {len(repo_df)-len(single_tool)} repos "
              f"({(len(repo_df)-len(single_tool))/len(repo_df)*100:.1f}% of adopters)")

    print(f"\nOutputs saved to {OUT_DIR}/")


if __name__ == "__main__":
    main()

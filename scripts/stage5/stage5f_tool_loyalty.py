#!/usr/bin/env python3
"""
Stage 5f -- Repo-Level Agent Diversity
=======================================
Measures how many distinct AI agents are detected per agentic repository.

Terminology
-----------
  Single-agent repo : exactly 1 agent detected in agents_found
  Multi-agent repo  : 2+ agents detected in agents_found

NOTE ON INTERPRETATION
  This is a repo-level metric, not an individual-developer metric.
  A multi-agent repo may reflect:
    (a) one developer genuinely using multiple tools in parallel, OR
    (b) different contributors each using their preferred tool, OR
    (c) a tool migration where traces of the old tool still remain.
  Results should be reported as "repo-level agent diversity", not as
  individual developer tool loyalty or single/multi-homing behaviour.

Two figures produced
---------------------
A) Stacked bar  (fig_tool_loyalty_bar)
   Shows % of agentic repos with 1 / 2 / 3+ agents detected.
   Primary finding: single-agent rate vs. multi-agent rate.

B) Co-occurrence heatmap  (fig_tool_loyalty_heatmap)
   Top N_HEATMAP_AGENTS x Top N_HEATMAP_AGENTS grid.
   Cell [i, j] = number of repos that detected both agent i and agent j.
   Diagonal = total repos where that agent was detected (useful reference).
   Only plotted if multi-agent rate > MULTI_AGENT_THRESHOLD (default 5%).

Input
-----
  data/stage4/corpus_with_country.csv
    Required columns: adoption_label, agents_found (pipe-separated agent names)

Output
------
  data/stage5/tool_loyalty.csv           per-repo agent diversity summary
  figures/stage5/fig_tool_loyalty_bar.png
  figures/stage5/fig_tool_loyalty_heatmap.png  (if multi-agent rate > threshold)

Usage
-----
  python3 scripts/stage5/stage5f_tool_loyalty.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from itertools import combinations
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
CORPUS  = ROOT / "data" / "stage4" / "corpus_with_country.csv"
OUT_DIR = ROOT / "data"  / "stage5"
FIG_DIR = ROOT / "figures" / "stage5"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

# ── configuration ─────────────────────────────────────────────────────────────
N_HEATMAP_AGENTS     = 12   # top N agents to include in co-occurrence heatmap
MULTI_AGENT_THRESHOLD = 5.0  # % multi-agent above which heatmap is generated
TOP_PAIRS_REPORT     = 5    # number of top pairs to print in summary


def load_agentic(corpus: Path) -> pd.DataFrame:
    df = pd.read_csv(corpus, low_memory=False)
    df = df[df["adoption_label"] == "agentic"].copy()
    df["agents_found"] = df["agents_found"].fillna("").astype(str)
    df["agent_list"] = df["agents_found"].apply(
        lambda s: [a.strip() for a in s.split("|") if a.strip()]
    )
    df["agent_count"] = df["agent_list"].apply(len)
    return df


def bucket(n: int) -> str:
    if n == 1:
        return "1 agent"
    elif n == 2:
        return "2 agents"
    else:
        return "3+ agents"


def plot_bar(df: pd.DataFrame) -> float:
    """Plot stacked bar of single- vs multi-agent repos. Returns multi-agent rate."""
    counts = df["agent_count"].apply(bucket).value_counts()
    order  = ["1 agent", "2 agents", "3+ agents"]
    counts = counts.reindex(order, fill_value=0)
    total  = counts.sum()
    pcts   = counts / total * 100

    multi_rate = pcts.get("2 agents", 0) + pcts.get("3+ agents", 0)

    colors = ["#4C72B0", "#DD8452", "#55A868"]
    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(order, pcts.values, color=colors, edgecolor="white", linewidth=0.8)

    for bar, pct, cnt in zip(bars, pcts.values, counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                f"{pct:.1f}%\n({cnt:,})",
                ha="center", va="bottom", fontsize=9)

    ax.set_ylabel("% of agentic repos", fontsize=10)
    ax.set_title("Repo-Level Agent Diversity\n(single-agent vs. multi-agent repos)",
                 fontsize=12, fontweight="bold")
    ax.set_ylim(0, max(pcts.values) * 1.25)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.set_xlabel(f"Total agentic repos: {total:,}  |  Note: multi-agent may reflect team diversity, not individual tool switching",
                  fontsize=7.5)

    plt.tight_layout()
    out = FIG_DIR / "fig_tool_loyalty_bar.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")
    return multi_rate


def plot_heatmap(df: pd.DataFrame) -> None:
    """Co-occurrence heatmap for top N_HEATMAP_AGENTS agents."""
    # Build agent frequency table (across all agentic repos)
    from collections import Counter
    all_agents = Counter(a for agents in df["agent_list"] for a in agents)
    top_agents = [a for a, _ in all_agents.most_common(N_HEATMAP_AGENTS)]
    n = len(top_agents)

    # Build co-occurrence matrix
    matrix = np.zeros((n, n), dtype=int)
    agent_idx = {a: i for i, a in enumerate(top_agents)}

    for agents in df["agent_list"]:
        relevant = [a for a in agents if a in agent_idx]
        # Diagonal: single presence
        for a in relevant:
            matrix[agent_idx[a], agent_idx[a]] += 1
        # Off-diagonal: co-occurrence
        for a, b in combinations(relevant, 2):
            i, j = agent_idx[a], agent_idx[b]
            matrix[i, j] += 1
            matrix[j, i] += 1

    fig, ax = plt.subplots(figsize=(9, 8))
    # Mask zero off-diagonal cells
    masked = np.ma.masked_where((matrix == 0) & (np.eye(n) == 0), matrix)
    im = ax.imshow(masked, cmap="Blues", aspect="auto")

    ax.set_xticks(range(n))
    ax.set_xticklabels(top_agents, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(n))
    ax.set_yticklabels(top_agents, fontsize=8)

    # Annotate non-zero cells
    for i in range(n):
        for j in range(n):
            val = matrix[i, j]
            if val > 0:
                text_color = "white" if val > matrix.max() * 0.6 else "black"
                ax.text(j, i, f"{val:,}", ha="center", va="center",
                        fontsize=7, color=text_color)

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Repo count (diagonal = total; off-diagonal = co-occurrence)", fontsize=8)
    ax.set_title("Agent Co-occurrence in Multi-Agent Repos\n(repo-level; may reflect team diversity)",
                 fontsize=12, fontweight="bold")

    plt.tight_layout()
    out = FIG_DIR / "fig_tool_loyalty_heatmap.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


def top_pairs(df: pd.DataFrame, k: int = TOP_PAIRS_REPORT) -> list[tuple]:
    """Return top-k agent pairs by co-occurrence count."""
    from collections import Counter
    pair_counts: Counter = Counter()
    for agents in df["agent_list"]:
        for a, b in combinations(sorted(agents), 2):
            pair_counts[(a, b)] += 1
    return pair_counts.most_common(k)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("Stage 5f -- Repo-Level Agent Diversity")
    print("=" * 55)

    if not CORPUS.exists():
        raise SystemExit(f"Missing: {CORPUS}\nRun stage4a first.")

    df = load_agentic(CORPUS)
    print(f"Agentic repos loaded : {len(df):,}")

    # Save per-repo summary
    summary = df[["agents_found", "agent_count"]].copy()
    summary["agent_diversity"] = summary["agent_count"].apply(
        lambda n: "single-agent" if n == 1 else ("multi-agent" if n >= 2 else "none")
    )
    out_csv = OUT_DIR / "tool_loyalty.csv"
    summary.to_csv(out_csv, index=False)
    print(f"  Saved: {out_csv.name}")

    print()
    print("Generating figures ...")
    multi_rate = plot_bar(df)
    print(f"  Multi-agent repos : {multi_rate:.1f}%")
    print(f"  (Note: multi-agent may reflect team diversity, not individual tool switching)")

    if multi_rate > MULTI_AGENT_THRESHOLD:
        plot_heatmap(df)
        pairs = top_pairs(df)
        print()
        print(f"Top {TOP_PAIRS_REPORT} agent pairs (multi-agent repos):")
        for (a, b), cnt in pairs:
            print(f"  {a} + {b:<30} {cnt:>5,} repos")
    else:
        print(f"  Multi-agent rate {multi_rate:.1f}% < {MULTI_AGENT_THRESHOLD}% threshold "
              f"-- co-occurrence heatmap skipped (not meaningful).")

    # Summary table
    total = len(df)
    for label, mask in [
        ("Single-agent repos (1 agent)",   df["agent_count"] == 1),
        ("Multi-agent repos  (2 agents)",  df["agent_count"] == 2),
        ("Multi-agent repos  (3+ agents)", df["agent_count"] >= 3),
    ]:
        cnt = mask.sum()
        print(f"  {label:<35} {cnt:>6,}  ({cnt/total*100:.1f}%)")

    print()
    print("Done.")


if __name__ == "__main__":
    main()

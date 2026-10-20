#!/usr/bin/env python3
"""
Stage 4c -- Adoption Breakdowns and Co-adoption Analysis
==========================================================
Produces descriptive breakdowns of AI coding agent adoption across the corpus
dimensions that are specific to the JS/TS/npm ecosystem, and analyses which
tools appear together in the same repository.

All analyses use corpus_with_country.csv (produced by stage4a) and require
no additional API calls.

Analyses
--------
  1. Adoption by ecosystem      (npm / pnpm / yarn / bun / vanilla / etc.)
  2. Adoption by language        (JavaScript vs TypeScript)
  3. Adoption by size stratum    (small <= 50 stars / medium 51-500 / large > 500)
  4. Co-adoption                 which tools appear together, tool loyalty,
                                 pairwise co-occurrence, Claude Code dominance

Output
------
  data/stage4/breakdown_ecosystem.csv
  data/stage4/breakdown_language.csv
  data/stage4/breakdown_size.csv
  data/stage4/coadoption_tool_counts.csv   -- repos per tool
  data/stage4/coadoption_tool_pairs.csv    -- pairwise co-occurrence counts
  data/stage4/coadoption_per_repo.csv      -- n_tools per adopted repo

Usage
-----
  python3 scripts/stage4/stage4c_breakdowns.py
"""

import math
import pandas as pd
from collections import Counter
from itertools import combinations
from pathlib import Path

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parents[2]
CORPUS_FILE = ROOT / "data" / "stage4" / "corpus_with_country.csv"
OUT_DIR     = ROOT / "data" / "stage4"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ── helpers ───────────────────────────────────────────────────────────────────

def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denom  = 1 + z ** 2 / n
    centre = (p + z ** 2 / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def adoption_breakdown(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """
    For each value of group_col compute adoption counts, rates, and Wilson CIs.
    Returns a DataFrame sorted by adoption_rate descending.
    """
    rows = []
    for val, grp in df.groupby(group_col):
        n       = len(grp)
        n_ag    = (grp["adoption_label"] == "agentic").sum()
        n_ai    = (grp["adoption_label"] == "ai_assisted").sum()
        n_adpt  = n_ag + n_ai
        n_none  = (grp["adoption_label"] == "none").sum()
        rate    = n_adpt / n
        ag_rate = n_ag   / n
        ci_lo, ci_hi = wilson_ci(n_adpt, n)
        rows.append({
            group_col:         val,
            "total_repos":     n,
            "agentic":         int(n_ag),
            "ai_assisted":     int(n_ai),
            "adopted":         int(n_adpt),
            "none":            int(n_none),
            "adoption_rate":   round(rate * 100, 2),
            "agentic_rate":    round(ag_rate * 100, 2),
            "ci_lower":        round(ci_lo * 100, 2),
            "ci_upper":        round(ci_hi * 100, 2),
        })
    return (
        pd.DataFrame(rows)
        .sort_values("adoption_rate", ascending=False)
        .reset_index(drop=True)
    )


def print_breakdown(df: pd.DataFrame, title: str, group_col: str):
    print(f"\n{'─' * 65}")
    print(f"  {title}")
    print(f"{'─' * 65}")
    hdr = (f"  {'Group':<22} {'Repos':>6} {'Adopted':>8} "
           f"{'Rate%':>7} {'95% CI':>15} {'Agentic%':>9}")
    print(hdr)
    print(f"  {'-' * 70}")
    for _, row in df.iterrows():
        ci_str = f"[{row['ci_lower']:.1f},{row['ci_upper']:.1f}]"
        print(f"  {str(row[group_col]):<22} {row['total_repos']:>6,} "
              f"{row['adopted']:>8,} {row['adoption_rate']:>7.1f}% "
              f"{ci_str:>15} {row['agentic_rate']:>9.1f}%")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("Stage 4c -- Adoption Breakdowns and Co-adoption Analysis")
    print("=" * 65)

    if not CORPUS_FILE.exists():
        raise SystemExit(f"Missing: {CORPUS_FILE}\nRun stage4a first.")

    corpus = pd.read_csv(CORPUS_FILE, low_memory=False)
    print(f"Corpus loaded : {len(corpus):,} repos")

    # ── Analysis 1: Ecosystem ─────────────────────────────────────────────────
    eco_df = adoption_breakdown(corpus, "ecosystem_type")
    print_breakdown(eco_df, "Analysis 1 -- Adoption by Ecosystem", "ecosystem_type")
    eco_df.to_csv(OUT_DIR / "breakdown_ecosystem.csv", index=False)
    print(f"\n  Saved: breakdown_ecosystem.csv")

    # ── Analysis 2: Primary language ─────────────────────────────────────────
    lang_df = adoption_breakdown(corpus, "primary_language")
    print_breakdown(lang_df, "Analysis 2 -- Adoption by Language (JS vs TS)", "primary_language")
    lang_df.to_csv(OUT_DIR / "breakdown_language.csv", index=False)
    print(f"\n  Saved: breakdown_language.csv")

    # ── Analysis 3: Size stratum ──────────────────────────────────────────────
    size_df = adoption_breakdown(corpus, "size_stratum")
    # ensure logical order: small → medium → large
    size_order = {"small": 0, "medium": 1, "large": 2}
    size_df["_ord"] = size_df["size_stratum"].map(size_order).fillna(99)
    size_df = size_df.sort_values("_ord").drop(columns="_ord").reset_index(drop=True)
    print_breakdown(size_df, "Analysis 3 -- Adoption by Size Stratum", "size_stratum")
    size_df.to_csv(OUT_DIR / "breakdown_size.csv", index=False)
    print(f"\n  Saved: breakdown_size.csv")

    # ── Analysis 4: Co-adoption ───────────────────────────────────────────────
    print(f"\n{'─' * 65}")
    print("  Analysis 4 -- Co-adoption")
    print(f"{'─' * 65}")

    # Work only with adopted repos that have agent names recorded
    adopted = corpus[
        corpus["adoption_label"].isin(["agentic", "ai_assisted"]) &
        corpus["agents_found"].notna() &
        (corpus["agents_found"] != "")
    ].copy()

    n_adopted = corpus["adoption_label"].isin(["agentic", "ai_assisted"]).sum()
    n_total   = len(corpus)

    print(f"\n  Adopted repos with agent signal: {len(adopted):,} "
          f"/ {n_adopted:,} total adopted")

    # Parse pipe-separated agents_found into a set per repo
    adopted["agent_set"] = adopted["agents_found"].apply(
        lambda x: frozenset(a.strip() for a in str(x).split("|") if a.strip())
    )

    # ── 4a: repos per tool ────────────────────────────────────────────────────
    tool_counter = Counter()
    for agent_set in adopted["agent_set"]:
        for agent in agent_set:
            tool_counter[agent] += 1

    print(f"\n  Tool usage (repos using each tool, % of full corpus):")
    tool_rows = []
    for tool, count in tool_counter.most_common():
        pct = count / n_total * 100
        print(f"    {tool:<30} {count:>6,}  ({pct:.1f}% of all repos)")
        tool_rows.append({
            "tool":            tool,
            "repos":           count,
            "pct_of_corpus":   round(pct, 2),
            "pct_of_adopted":  round(count / n_adopted * 100, 2),
        })
    tool_df = pd.DataFrame(tool_rows)
    tool_df.to_csv(OUT_DIR / "coadoption_tool_counts.csv", index=False)
    print(f"\n  Saved: coadoption_tool_counts.csv")

    # ── 4b: number of distinct tools per repo ─────────────────────────────────
    adopted["n_tools"] = adopted["agent_set"].map(len)
    dist = adopted["n_tools"].value_counts().sort_index()

    print(f"\n  Number of distinct tools per adopted repo:")
    per_repo_rows = []
    for n_tools, count in dist.items():
        pct_of_adopted = count / len(adopted) * 100
        pct_of_all     = count / n_total * 100
        label = f"{n_tools} tool{'s' if n_tools > 1 else ''}"
        print(f"    {label:<12} {count:>6,}  "
              f"({pct_of_adopted:.1f}% of adopters, "
              f"{pct_of_all:.1f}% of all repos)")
        per_repo_rows.append({
            "n_tools":         int(n_tools),
            "repos":           int(count),
            "pct_of_adopters": round(pct_of_adopted, 2),
            "pct_of_corpus":   round(pct_of_all, 2),
        })
    pd.DataFrame(per_repo_rows).to_csv(OUT_DIR / "coadoption_per_repo.csv", index=False)
    print(f"\n  Saved: coadoption_per_repo.csv")

    # ── 4c: tool loyalty ──────────────────────────────────────────────────────
    print(f"\n  Tool loyalty:")
    single_tool    = adopted[adopted["n_tools"] == 1]
    multi_tool     = adopted[adopted["n_tools"] >  1]
    only_claude    = adopted[adopted["agent_set"] == frozenset(["Claude Code"])]
    only_copilot   = adopted[adopted["agent_set"] == frozenset(["GitHub Copilot"])]

    def pct(n): return f"{n:,}  ({n / len(adopted) * 100:.1f}% of adopters)"
    print(f"    Single-tool repos    : {pct(len(single_tool))}")
    print(f"    Multi-tool repos     : {pct(len(multi_tool))}")
    print(f"    Claude Code only     : {pct(len(only_claude))}")
    print(f"    GitHub Copilot only  : {pct(len(only_copilot))}")

    # ── 4d: pairwise co-occurrence ────────────────────────────────────────────
    pair_counter = Counter()
    for agent_set in adopted["agent_set"]:
        if len(agent_set) >= 2:
            for pair in combinations(sorted(agent_set), 2):
                pair_counter[pair] += 1

    print(f"\n  Top tool pair co-occurrences (repos using both tools):")
    pair_rows = []
    if pair_counter:
        for (tool_a, tool_b), count in pair_counter.most_common(15):
            pct_corpus = count / n_total * 100
            print(f"    {tool_a:<28} + {tool_b:<28} {count:>5,}  ({pct_corpus:.2f}%)")
            pair_rows.append({
                "tool_a":          tool_a,
                "tool_b":          tool_b,
                "repos":           count,
                "pct_of_corpus":   round(pct_corpus, 3),
                "pct_of_adopted":  round(count / n_adopted * 100, 3),
            })
    else:
        print("    No co-adoption found.")
    pd.DataFrame(pair_rows).to_csv(OUT_DIR / "coadoption_tool_pairs.csv", index=False)
    print(f"\n  Saved: coadoption_tool_pairs.csv")

    print()
    print("Stage 4c complete.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Stage 1c — Stratified Random Sampling
======================================
Takes the full categorised corpus (60,129 repos) and draws a stratified
random sample of ~4,000 repos for Stage 4 signal detection.

Why sample?
  Running Stage 4 (GitHub API commit + file scans) on 60k repos would take
  weeks of API calls. A well-designed stratified sample of 4,000 repos gives
  statistically reliable estimates for every subgroup we care about while
  staying within a feasible runtime.

Stratification dimensions
  ecosystem_type   : npm | pnpm | yarn | bun | npm_no_lock
  primary_language : JavaScript | TypeScript
  size_stratum     : small (≤50 stars) | medium (51–500) | large (>500)

  → 5 × 2 × 3 = 30 possible strata.

Allocation strategy (two-phase):
  Phase 1 — assign MIN_PER_STRATUM (30) to every stratum that has at least
             30 repos available (otherwise take all available).
  Phase 2 — distribute the remaining budget proportionally across all strata,
             capped by how many repos are still available in each.

  This guarantees every subgroup has enough observations for Fisher's exact
  test and Mann-Whitney U while still reflecting the true ecosystem distribution
  for the headline adoption rate.

Special cases:
  bun  (107 total) — taken entirely in Phase 1 (all 107 fit within 30-minimum
                     across its 6 strata).
  yarn (1,091 total) — partially sampled; still well-represented.

INPUTS
------
  data/stage1/global_corpus.csv     — Stage 1b output (60,129 repos with
                                      ecosystem_type column)

OUTPUTS
-------
  data/stage1/sample_corpus.csv     — ~4,000 sampled repos with all original
                                      columns + stratum key
  data/stage1/strata_audit.csv      — per-stratum n_available / n_sampled / %

USAGE
-----
  python3 stage1c_sample.py
  (no API calls, no token needed)
"""

import sys
import pandas as pd
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────
TARGET_N          = 4_500   # desired total sample size
MIN_PER_STRATUM   = 30      # minimum repos per stratum (for statistical tests)
RANDOM_SEED       = 42      # reproducibility

# npm/pnpm/yarn/bun/npm_no_lock = thesis targets (primary analysis)
# vanilla = comparison group (no package manager, included as baseline)
# deno + unknown = excluded (different runtime / data quality)
TARGET_ECOSYSTEMS = ["npm", "pnpm", "yarn", "bun", "npm_no_lock", "vanilla"]

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR       = Path(__file__).parent
DATA_DIR         = SCRIPT_DIR / "../../data/stage1"

CORPUS_IN        = DATA_DIR / "global_corpus.csv"
SAMPLE_OUT       = DATA_DIR / "sample_corpus.csv"
STRATA_AUDIT_OUT = DATA_DIR / "strata_audit.csv"


# ── Allocation helpers ────────────────────────────────────────────────────────

def allocate(stratum_counts: dict, target: int, minimum: int) -> dict:
    """
    Two-phase allocation:
      Phase 1 — give every stratum its minimum (or all if < minimum).
      Phase 2 — distribute remaining budget proportionally.

    Returns dict {stratum: n_to_sample}.
    """
    # Phase 1: minimums
    alloc = {s: min(minimum, n) for s, n in stratum_counts.items()}
    budget_used = sum(alloc.values())
    remaining_budget = target - budget_used

    if remaining_budget <= 0:
        return alloc

    # Phase 2: remaining capacity per stratum after Phase 1
    remaining_capacity = {s: stratum_counts[s] - alloc[s] for s in alloc}
    total_remaining_capacity = sum(remaining_capacity.values())

    if total_remaining_capacity == 0:
        return alloc

    # Proportional distribution of the remaining budget
    for stratum, capacity in remaining_capacity.items():
        if capacity <= 0:
            continue
        extra = round(remaining_budget * capacity / total_remaining_capacity)
        extra = min(extra, capacity)   # cannot exceed available
        alloc[stratum] += extra

    # Fix rounding: total may be slightly off from TARGET_N — adjust largest strata
    total = sum(alloc.values())
    diff  = target - total

    if diff != 0:
        # Sort by current allocation descending; add/remove from largest first
        for stratum in sorted(alloc, key=alloc.get, reverse=(diff > 0)):
            if diff == 0:
                break
            if diff > 0 and alloc[stratum] < stratum_counts[stratum]:
                alloc[stratum] += 1
                diff -= 1
            elif diff < 0 and alloc[stratum] > minimum:
                alloc[stratum] -= 1
                diff += 1

    return alloc


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not CORPUS_IN.exists():
        sys.exit(f"ERROR: {CORPUS_IN} not found. Run stage1b_categorize_ecosystem.py first.")

    df = pd.read_csv(CORPUS_IN)
    print(f"Loaded {len(df):,} repos from Stage 1b corpus.\n")

    # ── Filter to target ecosystems ───────────────────────────────────────────
    target_df = df[df["ecosystem_type"].isin(TARGET_ECOSYSTEMS)].copy()
    excluded  = df[~df["ecosystem_type"].isin(TARGET_ECOSYSTEMS)]

    print(f"Target ecosystems ({', '.join(TARGET_ECOSYSTEMS)}): {len(target_df):,} repos")
    print(f"Excluded (vanilla, deno, unknown):                  {len(excluded):,} repos\n")

    # ── Build stratum key ─────────────────────────────────────────────────────
    # Normalise: fill any missing primary_language or size_stratum
    target_df["primary_language"] = target_df["primary_language"].fillna("Unknown")
    target_df["size_stratum"]     = target_df["size_stratum"].fillna("small")

    target_df["stratum"] = (
        target_df["ecosystem_type"]   + "__" +
        target_df["primary_language"] + "__" +
        target_df["size_stratum"]
    )

    # ── Compute stratum sizes ─────────────────────────────────────────────────
    stratum_counts = target_df["stratum"].value_counts().to_dict()

    print(f"Strata found: {len(stratum_counts)}")
    print(f"Allocating ~{TARGET_N:,} repos with minimum {MIN_PER_STRATUM} per stratum...\n")

    # ── Allocate ──────────────────────────────────────────────────────────────
    allocations = allocate(stratum_counts, TARGET_N, MIN_PER_STRATUM)

    # ── Sample each stratum ───────────────────────────────────────────────────
    samples    = []
    audit_rows = []

    for stratum, n_to_sample in sorted(allocations.items()):
        stratum_df = target_df[target_df["stratum"] == stratum]
        n_available = len(stratum_df)
        n_actual    = min(n_to_sample, n_available)

        sampled = stratum_df.sample(n=n_actual, random_state=RANDOM_SEED)
        samples.append(sampled)

        eco, lang, size = stratum.split("__")
        audit_rows.append({
            "stratum":          stratum,
            "ecosystem_type":   eco,
            "primary_language": lang,
            "size_stratum":     size,
            "n_available":      n_available,
            "n_sampled":        n_actual,
            "pct_sampled":      round(n_actual / n_available * 100, 1),
        })

    sample_df = (
        pd.concat(samples)
        .drop(columns=["stratum"])
        .reset_index(drop=True)
    )

    audit_df = (
        pd.DataFrame(audit_rows)
        .sort_values(["ecosystem_type", "primary_language", "size_stratum"])
        .reset_index(drop=True)
    )

    # ── Save ──────────────────────────────────────────────────────────────────
    sample_df.to_csv(SAMPLE_OUT,       index=False)
    audit_df.to_csv(STRATA_AUDIT_OUT,  index=False)

    # ── Summary ───────────────────────────────────────────────────────────────
    total_sampled = len(sample_df)

    print(f"─── Stage 1c Summary ─────────────────────────────────────────────")
    print(f"Source pool    : {len(target_df):,} repos")
    print(f"Target sample  : {TARGET_N:,}")
    print(f"Actual sample  : {total_sampled:,}")
    print(f"Random seed    : {RANDOM_SEED}")
    print()
    print(f"  {'Stratum':<45} {'Avail':>7}  {'Sampled':>8}  {'%':>6}")
    print(f"  {'-'*72}")
    for _, row in audit_df.iterrows():
        print(f"  {row['stratum']:<45} {row['n_available']:>7}  "
              f"{row['n_sampled']:>8}  {row['pct_sampled']:>5}%")

    print()
    print(f"Ecosystem totals:")
    eco_summary = (
        audit_df.groupby("ecosystem_type")
        .agg(n_available=("n_available","sum"), n_sampled=("n_sampled","sum"))
        .assign(pct=lambda x: (x["n_sampled"]/x["n_available"]*100).round(1))
    )
    for eco, row in eco_summary.iterrows():
        print(f"  {eco:<15} {row['n_available']:>7} available  → "
              f"{row['n_sampled']:>5} sampled  ({row['pct']}%)")

    print()
    print(f"Saved: {SAMPLE_OUT}")
    print(f"       {STRATA_AUDIT_OUT}")
    print(f"\nNext steps:")
    print(f"  1. Run stage2a_collect_owners.py  — extract unique owners from sample")
    print(f"  2. Run stage2b_fetch_locations.py — fetch GitHub profile location for each owner")
    print(f"  3. Run stage4_detection.py        — AI signal detection on sample_corpus.csv")


if __name__ == "__main__":
    main()

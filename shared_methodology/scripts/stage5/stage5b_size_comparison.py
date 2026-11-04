#!/usr/bin/env python3
"""
Stage 5b -- Repo Size: Human vs AI-Assisted vs Agentic  (Point 2)
==================================================================
Compares repository size across the three adoption groups using:
  commits, lang_bytes (KB), stars, forks

Statistical tests: Kruskal-Wallis (3-way) + Mann-Whitney U (Agentic vs None)
Visualisation: violin plots (capped at 99th percentile for readability)

Input
-----
  data/stage4/corpus_with_country.csv

Output
------
  data/stage5/size_by_adoption.csv        -- summary stats per group
  data/stage5/size_statistical_tests.csv  -- test results
  figures/stage5/fig_size_comparison.pdf/.png
"""
# ══════════════════════════════════════════════════════════════════════════════
# TEAM CONFIGURATION — edit the variables in this block before running
# ══════════════════════════════════════════════════════════════════════════════
#
# INPUT_CSV  : path to your Stage 1 corpus CSV
#              Required columns: full_name, owner_login, stars, commits,
#                                lang_bytes, created_at, primary_language
#              (replace with the equivalent columns in your stack's corpus)
#
# GITHUB_TOKEN: set via environment variable before running:
#   export GITHUB_TOKEN=ghp_...
#
# Outputs will be written to:  shared_methodology/data/stage5/
# ══════════════════════════════════════════════════════════════════════════════



import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from scipy.stats import mannwhitneyu, kruskal
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
CORPUS  = ROOT / "data" / "stage4" / "corpus_with_country.csv"
OUT_DIR = ROOT / "data"  / "stage5"
FIG_DIR = ROOT / "figures" / "stage5"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

GROUP_ORDER  = ["No AI", "AI-Assisted", "Agentic"]
GROUP_LABELS = {"none": "No AI", "ai_assisted": "AI-Assisted", "agentic": "Agentic"}
GROUP_COLOURS = {"No AI": "#d9d9d9", "AI-Assisted": "#74add1", "Agentic": "#2166ac"}

METRICS = [
    ("commits",    "Commit Count",         None,           False),
    ("lang_bytes", "Source Code Size (KB)", lambda x: x/1024, False),
    ("stars",      "Stars",                 None,           False),
    ("forks",      "Forks",                 None,           False),
]


OUTPUTS = [
    OUT_DIR / "size_by_adoption.csv",
    OUT_DIR / "size_statistical_tests.csv",
    FIG_DIR / "fig_size_comparison.pdf",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="Rerun even if output files already exist")
    args = parser.parse_args()

    print("Stage 5e -- Repo Size by Adoption Category")
    print("=" * 60)

    if not args.force and all(p.exists() for p in OUTPUTS):
        print("All outputs already exist. Skipping.")
        print("Use --force to regenerate.")
        return

    df = pd.read_csv(CORPUS, low_memory=False)
    df["group"] = df["adoption_label"].map(GROUP_LABELS)
    df = df[df["group"].notna()].copy()

    groups = {g: df[df["group"] == g] for g in GROUP_ORDER}
    for g, gdf in groups.items():
        print(f"  {g}: {len(gdf):,} repos")

    # ── Summary statistics ────────────────────────────────────────────────────
    stat_rows = []
    for col, name, transform, _ in METRICS:
        for g, gdf in groups.items():
            vals = gdf[col].dropna()
            if transform:
                vals = transform(vals)
            stat_rows.append({
                "group":  g,
                "metric": name,
                "n":      len(vals),
                "median": round(vals.median(), 1),
                "mean":   round(vals.mean(), 1),
                "p25":    round(vals.quantile(0.25), 1),
                "p75":    round(vals.quantile(0.75), 1),
                "max":    round(vals.max(), 1),
            })

    stats_df = pd.DataFrame(stat_rows)
    stats_df.to_csv(OUT_DIR / "size_by_adoption.csv", index=False)

    print(f"\n{'Metric':<25} {'Group':<14} {'Median':>10} {'Mean':>10} "
          f"{'P25':>8} {'P75':>10}")
    print("-" * 75)
    for _, r in stats_df.iterrows():
        print(f"{r['metric']:<25} {r['group']:<14} {r['median']:>10,.1f} "
              f"{r['mean']:>10,.1f} {r['p25']:>8,.1f} {r['p75']:>10,.1f}")

    # ── Statistical tests ─────────────────────────────────────────────────────
    test_rows = []
    print(f"\n{'─'*70}")
    print("Statistical tests:")
    for col, name, transform, _ in METRICS:
        vals_by_group = {}
        for g, gdf in groups.items():
            v = gdf[col].dropna()
            vals_by_group[g] = transform(v) if transform else v

        kw_stat, kw_p = kruskal(*vals_by_group.values())
        mw_stat, mw_p = mannwhitneyu(
            vals_by_group["Agentic"], vals_by_group["No AI"],
            alternative="two-sided",
        )
        # Effect size (rank-biserial correlation)
        n1, n2 = len(vals_by_group["Agentic"]), len(vals_by_group["No AI"])
        r_rb = 1 - (2 * mw_stat) / (n1 * n2)

        print(f"\n  {name}")
        print(f"    Kruskal-Wallis:            H = {kw_stat:,.1f},  p = {kw_p:.2e}")
        print(f"    Mann-Whitney (Ag vs None): U = {mw_stat:,.0f},  p = {mw_p:.2e},  "
              f"r_rb = {r_rb:.3f}")

        test_rows.append({
            "metric":       name,
            "kw_H":         round(kw_stat, 2),
            "kw_p":         round(kw_p, 6),
            "mw_U":         round(mw_stat, 0),
            "mw_p":         round(mw_p, 6),
            "effect_r_rb":  round(r_rb, 3),
            "median_agentic": round(vals_by_group["Agentic"].median(), 1),
            "median_none":    round(vals_by_group["No AI"].median(), 1),
        })

    pd.DataFrame(test_rows).to_csv(OUT_DIR / "size_statistical_tests.csv", index=False)

    # ── Violin plot ───────────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 4, figsize=(16, 5.5))
    positions = [1, 2, 3]

    for ax, (col, name, transform, _) in zip(axes, METRICS):
        data = []
        for g in GROUP_ORDER:
            gdf = groups[g]
            v = gdf[col].dropna()
            if transform:
                v = transform(v)
            cap = v.quantile(0.99)
            data.append(v[v <= cap].values)

        vp = ax.violinplot(data, positions=positions,
                           showmedians=True, showextrema=False, widths=0.65)
        for i, body in enumerate(vp["bodies"]):
            body.set_facecolor(GROUP_COLOURS[GROUP_ORDER[i]])
            body.set_edgecolor("white")
            body.set_alpha(0.85)
        vp["cmedians"].set_color("black")
        vp["cmedians"].set_linewidth(2.2)

        # Add median labels
        for i, g in enumerate(GROUP_ORDER):
            v = groups[g][col].dropna()
            if transform:
                v = transform(v)
            med = v.median()
            ax.text(positions[i], med, f"{med:,.0f}",
                    ha="center", va="bottom", fontsize=7.5,
                    fontweight="bold", color="white",
                    bbox=dict(boxstyle="round,pad=0.15", fc="#333333", alpha=0.6))

        ax.set_xticks(positions)
        ax.set_xticklabels(GROUP_ORDER, fontsize=9)
        ax.set_title(name, fontsize=10, fontweight="bold")
        ax.grid(axis="y", alpha=0.3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig.suptitle(
        "Repository Size by AI Adoption Category\n"
        "(violin capped at 99th percentile; median shown)",
        fontsize=12, fontweight="bold",
    )
    plt.tight_layout()
    for ext in ("pdf", "png"):
        plt.savefig(FIG_DIR / f"fig_size_comparison.{ext}",
                    bbox_inches="tight", dpi=150)
    plt.close()
    print(f"\nSaved: fig_size_comparison.pdf / .png")
    print("Stage 5b complete.")


if __name__ == "__main__":
    main()

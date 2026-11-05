#!/usr/bin/env python3
"""
Stage 5h -- AI Commit Density
==============================
Measures what fraction of commits in each agentic repo were made by an AI
agent (i.e. carried a detectable commit trailer).

  ai_density = trailer_count / total_commits   (range 0–1)

Three figures produced
-----------------------
A) Histogram  (fig_commit_density_hist)
   Distribution of AI commit density across agentic repos that have at least
   one trailer commit.  Bin width = 5 %.

B) Median density by agent  (fig_commit_density_by_agent)
   Horizontal bar chart: median AI commit density for the top N_AGENTS agents
   (ranked by number of repos with trailer data).  Error bars = IQR.

C) Adoption intensity buckets  (fig_commit_density_buckets)
   All agentic repos split into four bands:
     config-only  : adoption_label == agentic, trailer_count == 0 or NaN
                    (detected via config file, no measured trailer commits)
     low          : 0 < density <= 25 %
     medium       : 25 % < density <= 75 %
     high         : 75 % < density < 100 %
     full         : density == 100 %  (every commit carries an agent trailer)

Input
-----
  data/stage4/corpus_with_country.csv
    Required columns: adoption_label, trailer_count, commits, agents_found

Output
------
  data/stage5/commit_density.csv              per-repo density values
  figures/stage5/fig_commit_density_hist.png
  figures/stage5/fig_commit_density_by_agent.png
  figures/stage5/fig_commit_density_buckets.png

Usage
-----
  python3 scripts/stage5/stage5h_commit_density.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
CORPUS  = ROOT / "data" / "stage4" / "corpus_with_country.csv"
OUT_DIR = ROOT / "data"  / "stage5"
FIG_DIR = ROOT / "figures" / "stage5"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

# ── configuration ─────────────────────────────────────────────────────────────
N_AGENTS      = 15    # top N agents shown in the by-agent chart
MIN_REPOS     = 5     # minimum repos with trailer data to include an agent


def load(corpus: Path) -> pd.DataFrame:
    df = pd.read_csv(corpus, low_memory=False)
    df = df[df["adoption_label"] == "agentic"].copy()

    df["trailer_count"] = pd.to_numeric(df["trailer_count"], errors="coerce").fillna(0)
    df["commits"]       = pd.to_numeric(df["commits"],       errors="coerce")
    df["agents_found"]  = df["agents_found"].fillna("").astype(str)

    # Density only defined when total commits is known and positive
    mask = df["commits"] > 0
    df.loc[mask,  "ai_density"] = df.loc[mask, "trailer_count"] / df.loc[mask, "commits"]
    df.loc[~mask, "ai_density"] = np.nan

    # Clamp to [0, 1] — rounding errors in source data
    df["ai_density"] = df["ai_density"].clip(0.0, 1.0)

    return df


def bucket_label(density: float | None) -> str:
    if pd.isna(density) or density == 0:
        return "config-only"
    elif density <= 0.25:
        return "low (1–25%)"
    elif density <= 0.75:
        return "medium (26–75%)"
    elif density < 1.0:
        return "high (76–99%)"
    else:
        return "full (100%)"


def plot_histogram(df: pd.DataFrame) -> None:
    has_trailer = df[df["trailer_count"] > 0].copy()
    densities   = has_trailer["ai_density"].dropna() * 100  # → percent

    fig, ax = plt.subplots(figsize=(8, 4))
    bins = np.arange(0, 105, 5)
    ax.hist(densities, bins=bins, color="#4C72B0", edgecolor="white", linewidth=0.5)

    median_val = densities.median()
    ax.axvline(median_val, color="#DD8452", linewidth=1.5, linestyle="--",
               label=f"Median = {median_val:.1f}%")

    ax.set_xlabel("AI commit density (% of commits with agent trailer)", fontsize=10)
    ax.set_ylabel("Number of repos", fontsize=10)
    ax.set_title("Distribution of AI Commit Density\n(agentic repos with ≥1 trailer commit)",
                 fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    ax.set_xlim(0, 100)
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    ax.text(0.98, 0.95,
            f"n = {len(densities):,} repos",
            transform=ax.transAxes, ha="right", va="top", fontsize=9)

    plt.tight_layout()
    out = FIG_DIR / "fig_commit_density_hist.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


def plot_by_agent(df: pd.DataFrame) -> None:
    has_trailer = df[df["trailer_count"] > 0].copy()

    # Explode pipe-separated agents
    rows = []
    for _, row in has_trailer.iterrows():
        agents = [a.strip() for a in row["agents_found"].split("|") if a.strip()]
        for agent in agents:
            rows.append({"agent": agent, "ai_density": row["ai_density"]})

    agent_df = pd.DataFrame(rows).dropna(subset=["ai_density"])

    # Filter to agents with enough data, rank by sample size
    counts  = agent_df["agent"].value_counts()
    top_agents = counts[counts >= MIN_REPOS].head(N_AGENTS).index.tolist()
    agent_df = agent_df[agent_df["agent"].isin(top_agents)]

    stats = (agent_df.groupby("agent")["ai_density"]
             .agg(median="median", q25=lambda x: x.quantile(0.25),
                  q75=lambda x: x.quantile(0.75), n="count")
             .reindex(top_agents)
             .sort_values("median", ascending=True))

    fig, ax = plt.subplots(figsize=(8, max(4, len(stats) * 0.45)))
    y = np.arange(len(stats))

    xerr_lo = (stats["median"] - stats["q25"]).clip(lower=0).values
    xerr_hi = (stats["q75"]    - stats["median"]).clip(lower=0).values

    ax.barh(y, stats["median"] * 100, color="#4C72B0", edgecolor="white",
            linewidth=0.5, xerr=[xerr_lo * 100, xerr_hi * 100],
            error_kw={"elinewidth": 1, "ecolor": "#555", "capsize": 2})

    ax.set_yticks(y)
    ax.set_yticklabels(
        [f"{a}  (n={int(stats.loc[a,'n']):,})" for a in stats.index],
        fontsize=8)
    ax.set_xlabel("Median AI commit density (%)  [error bars = IQR]", fontsize=10)
    ax.set_title("Median AI Commit Density by Agent\n(agentic repos with ≥1 trailer commit)",
                 fontsize=12, fontweight="bold")
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(xmax=100))
    ax.set_xlim(0, 100)
    ax.grid(axis="x", linestyle="--", alpha=0.4)

    plt.tight_layout()
    out = FIG_DIR / "fig_commit_density_by_agent.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


def plot_buckets(df: pd.DataFrame) -> None:
    df = df.copy()
    df["bucket"] = df["ai_density"].apply(bucket_label)

    order  = ["config-only", "low (1–25%)", "medium (26–75%)", "high (76–99%)", "full (100%)"]
    colors = ["#aec7e8", "#6baed6", "#3182bd", "#08519c", "#08306b"]

    counts = df["bucket"].value_counts().reindex(order, fill_value=0)
    total  = counts.sum()
    pcts   = counts / total * 100

    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar(order, pcts.values, color=colors, edgecolor="white", linewidth=0.8)

    for bar, pct, cnt in zip(bars, pcts.values, counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.4,
                f"{pct:.1f}%\n({cnt:,})",
                ha="center", va="bottom", fontsize=8)

    ax.set_ylabel("% of agentic repos", fontsize=10)
    ax.set_title("AI Commit Intensity Buckets\n(all agentic repos)",
                 fontsize=12, fontweight="bold")
    ax.set_ylim(0, max(pcts.values) * 1.3)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.set_xlabel(f"Total agentic repos: {total:,}", fontsize=9)
    plt.xticks(fontsize=8)

    plt.tight_layout()
    out = FIG_DIR / "fig_commit_density_buckets.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    print("Stage 5h -- AI Commit Density")
    print("=" * 55)

    if not CORPUS.exists():
        raise SystemExit(f"Missing: {CORPUS}\nRun stage4a first.")

    df = load(CORPUS)
    total_agentic   = len(df)
    with_trailers   = (df["trailer_count"] > 0).sum()
    config_only     = (df["trailer_count"] == 0).sum()
    fully_agentic   = (df["ai_density"] == 1.0).sum()

    print(f"Agentic repos total  : {total_agentic:,}")
    print(f"  With trailer data  : {with_trailers:,}  ({with_trailers/total_agentic*100:.1f}%)")
    print(f"  Config-only        : {config_only:,}  ({config_only/total_agentic*100:.1f}%)")
    print(f"  Fully agentic (100%): {fully_agentic:,}  ({fully_agentic/total_agentic*100:.1f}%)")

    has_density = df[df["trailer_count"] > 0]["ai_density"].dropna()
    print(f"  Median AI density  : {has_density.median()*100:.1f}%  (among trailer repos)")
    print(f"  Mean   AI density  : {has_density.mean()*100:.1f}%")

    # Save per-repo CSV
    out_csv = OUT_DIR / "commit_density.csv"
    df[["full_name", "commits", "trailer_count", "ai_density",
        "agents_found", "adoption_label", "primary_language", "country"]].to_csv(
        out_csv, index=False)
    print(f"\n  Saved: {out_csv.name}")

    print("\nGenerating figures ...")
    plot_histogram(df)
    plot_by_agent(df)
    plot_buckets(df)

    print()
    print("Done.")


if __name__ == "__main__":
    main()

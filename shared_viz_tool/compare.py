#!/usr/bin/env python3
"""
compare.py  —  Static matplotlib figures (no browser needed)
=============================================================
Generates PNG/PDF figures to shared_viz_tool/figures/.
Run this if you don't want to install Streamlit.

Usage:
    python3 shared_viz_tool/compare.py
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from pathlib import Path
from collections import Counter
from statsmodels.stats.proportion import proportion_confint

DATA_DIR    = Path(__file__).parent / "data"
FIGURES_DIR = Path(__file__).parent / "figures"
FIGURES_DIR.mkdir(exist_ok=True)

STACK_COLORS = {
    "TypeScript/JavaScript": "#F0A500",
    "Python":                "#3776AB",
    "Java":                  "#ED8B00",
    "Rust":                  "#CE422B",
    "C#":                    "#178600",
    "C++":                   "#00599C",
}

def stack_color(name): return STACK_COLORS.get(name, "#888888")

def wilson_ci(k, n):
    if n == 0: return 0.0, 0.0
    lo, hi = proportion_confint(k, n, alpha=0.05, method="wilson")
    return lo * 100, hi * 100

def parse_agents(s):
    if pd.isna(s) or str(s).strip() == "": return []
    return [a.strip() for a in str(s).split("|") if a.strip()]

def is_adopted(label): return label in ("agentic", "ai_assisted")

def save(fig, name):
    for ext in ("png", "pdf"):
        path = FIGURES_DIR / f"{name}.{ext}"
        fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: figures/{name}.png")


def load_data():
    frames = []
    for f in sorted(DATA_DIR.glob("*.csv")):
        try: df = pd.read_csv(f, low_memory=False)
        except Exception: continue
        if "stack" not in df.columns or "adoption_label" not in df.columns: continue
        if "inferred_country" in df.columns and "country" not in df.columns:
            df = df.rename(columns={"inferred_country": "country"})
        frames.append(df)
    if not frames: return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def plot_adoption_rates(df):
    rows = []
    for stack, grp in df.groupby("stack"):
        n = len(grp)
        adopted = grp["adoption_label"].apply(is_adopted).sum()
        rate = adopted / n * 100 if n > 0 else 0.0
        ci_lo, ci_hi = wilson_ci(adopted, n)
        rows.append({"stack": stack, "rate": rate, "ci_lo": ci_lo, "ci_hi": ci_hi})
    sdf    = pd.DataFrame(rows).sort_values("rate", ascending=False)
    fig, ax = plt.subplots(figsize=(max(5, len(sdf) * 1.4), 5))
    stacks = sdf["stack"].tolist()
    rates  = sdf["rate"].tolist()
    err_lo = [r - lo for r, lo in zip(rates, sdf["ci_lo"].tolist())]
    err_hi = [hi - r  for r, hi in zip(rates, sdf["ci_hi"].tolist())]
    colors = [stack_color(s) for s in stacks]
    bars   = ax.bar(stacks, rates, color=colors, edgecolor="white", linewidth=0.8, zorder=3)
    ax.errorbar(stacks, rates, yerr=[err_lo, err_hi],
                fmt="none", color="#333333", capsize=6, linewidth=1.8, zorder=4)
    for bar, rate in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.8,
                f"{rate:.1f}%", ha="center", va="bottom", fontsize=11, fontweight="bold")
    ax.axhline(50, color="gray", linestyle="--", linewidth=0.9, alpha=0.5)
    ax.set_ylabel("Adoption Rate (%)", fontsize=11)
    ax.set_title("AI Coding Agent Adoption by Language Stack\n(95% Wilson CI)", fontsize=13, fontweight="bold")
    ax.set_ylim(0, 105)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    save(fig, "fig1_adoption_rates")


def plot_top_agents(df, top_n=8):
    stacks = sorted(df["stack"].unique())
    fig, axes = plt.subplots(1, len(stacks), figsize=(5 * len(stacks), 5), squeeze=False)
    for i, stack in enumerate(stacks):
        ax  = axes[0][i]
        grp = df[df["stack"] == stack]
        counts = Counter()
        for agents in grp["agents_found"].dropna():
            for a in parse_agents(agents): counts[a] += 1
        items  = counts.most_common(top_n)
        if not items:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            continue
        agents = [a for a, _ in reversed(items)]
        vals   = [c for _, c in reversed(items)]
        ax.barh(agents, vals, color=stack_color(stack), edgecolor="white")
        max_v = max(vals)
        for j, (a, v) in enumerate(zip(agents, vals)):
            ax.text(v + max_v * 0.02, j, f"{v:,}", va="center", fontsize=8)
        ax.set_title(stack, fontsize=10, fontweight="bold")
        ax.set_xlabel("Repositories", fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x", linestyle="--", alpha=0.35)
        ax.set_xlim(0, max_v * 1.18)
    fig.suptitle(f"Top {top_n} Detected Agents per Stack", fontsize=13, fontweight="bold")
    plt.tight_layout()
    save(fig, "fig2_top_agents")


def plot_countries(df, top_n=10, min_repos=10):
    if "country" not in df.columns: return
    stacks = sorted(df["stack"].unique())
    fig, axes = plt.subplots(1, len(stacks), figsize=(5 * len(stacks), 6), squeeze=False)
    for i, stack in enumerate(stacks):
        ax  = axes[0][i]
        grp = df[df["stack"] == stack]
        rows = []
        for country, cgrp in grp.groupby("country"):
            if pd.isna(country) or str(country).lower() in ("not_specified", "unknown", "", "nan"): continue
            n = len(cgrp)
            if n < min_repos: continue
            adopted = cgrp["adoption_label"].apply(is_adopted).sum()
            rate = adopted / n * 100
            ci_lo, ci_hi = wilson_ci(adopted, n)
            rows.append({"country": country, "rate": rate, "ci_lo": ci_lo, "ci_hi": ci_hi})
        if not rows:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            continue
        cdf  = pd.DataFrame(rows).sort_values("rate", ascending=False).head(top_n)
        ctry = cdf["country"].tolist()[::-1]
        rate = cdf["rate"].tolist()[::-1]
        err_lo = [r - lo for r, lo in zip(rate, cdf["ci_lo"].tolist()[::-1])]
        err_hi = [hi - r  for r, hi in zip(rate, cdf["ci_hi"].tolist()[::-1])]
        ax.barh(ctry, rate, color=stack_color(stack), edgecolor="white", zorder=3)
        ax.errorbar(rate, ctry, xerr=[err_lo, err_hi],
                    fmt="none", color="#333333", capsize=3, linewidth=1, zorder=4)
        ax.set_title(stack, fontsize=10, fontweight="bold")
        ax.set_xlabel("Adoption Rate (%)", fontsize=9)
        ax.set_xlim(0, 110)
        ax.xaxis.set_major_formatter(mtick.PercentFormatter())
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x", linestyle="--", alpha=0.35)
    fig.suptitle(f"Top {top_n} Countries by Adoption Rate", fontsize=13, fontweight="bold")
    plt.tight_layout()
    save(fig, "fig3_countries")


def plot_agent_diversity(df):
    agentic = df[df["adoption_label"] == "agentic"]
    if agentic.empty: return
    rows = []
    for stack, grp in agentic.groupby("stack"):
        counts = grp["agents_found"].apply(lambda x: len(parse_agents(x)))
        n = len(grp)
        rows.append({"stack": stack,
                     "Single": (counts == 1).sum() / n * 100,
                     "Multi":  (counts  > 1).sum() / n * 100})
    rdf = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(max(5, len(rdf) * 1.4), 5))
    x = np.arange(len(rdf))
    ax.bar(x, rdf["Single"], label="Single-agent", color="#4C72B0", zorder=3)
    ax.bar(x, rdf["Multi"], bottom=rdf["Single"], label="Multi-agent", color="#DD8452", zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels(rdf["stack"].tolist(), fontsize=10)
    ax.set_ylabel("% of Agentic Repos", fontsize=11)
    ax.set_title("Agent Diversity — Single vs Multi-Agent Repos", fontsize=13, fontweight="bold")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_ylim(0, 105)
    ax.legend(fontsize=9)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    save(fig, "fig4_agent_diversity")


def main():
    print("Static Comparison Charts")
    print("=" * 40)
    df = load_data()
    if df.empty:
        print("No data found in shared_viz_tool/data/. Run prepare_submission.py first.")
        return
    stacks = df["stack"].unique().tolist()
    print(f"Stacks loaded: {stacks}")
    print(f"Total repos  : {len(df):,}\n")
    plot_adoption_rates(df)
    plot_top_agents(df)
    plot_countries(df)
    plot_agent_diversity(df)
    print(f"\nAll figures saved to: shared_viz_tool/figures/")


if __name__ == "__main__":
    main()

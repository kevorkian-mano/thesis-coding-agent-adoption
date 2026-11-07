#!/usr/bin/env python3
"""
Stage 5k -- True Adoption Timeline
=====================================
Merges the config-file timestamps (stage5i) and trailer timestamps (stage5j)
to build a unified first_ai_date for every adopted repo, then answers three
research questions:

  RQ-T1  True adoption timeline
         Monthly volume of repos grouped by first_ai_date vs. created_at.
         Shows whether "creation surge" is due to new repos or new adopters.

  RQ-T2  Time-to-adoption distribution
         days_to_adoption = first_ai_date − created_at
         Histogram + percentiles.  Was AI adopted on day 1, or added later?

  RQ-T3  AI-native vs retrofit breakdown
         ai_native  : first_ai_date within DAY1_DAYS of created_at
         early      : DAY1_DAYS < days <= EARLY_DAYS
         late       : days > EARLY_DAYS
         Stacked bar by month of repo creation.

Input
-----
  data/stage5/config_timestamps.csv   (from stage5i)
  data/stage5/trailer_timestamps.csv  (from stage5j)
  data/stage4/corpus_with_country.csv (created_at, adoption_label, …)

Output
------
  data/stage5/adoption_timeline.csv        per-repo merged result
  figures/stage5/fig_true_timeline.png/.pdf
  figures/stage5/fig_time_to_adoption.png/.pdf
  figures/stage5/fig_ai_native_stacked.png/.pdf
  figures/stage5/fig_adoption_category_pie.png/.pdf

Usage
-----
  python3 scripts/stage5/stage5k_adoption_timeline.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from pathlib import Path

ROOT        = Path(__file__).resolve().parents[2]
CONFIG_TS   = ROOT / "data" / "stage5" / "config_timestamps.csv"
TRAILER_TS  = ROOT / "data" / "stage5" / "trailer_timestamps.csv"
CORPUS      = ROOT / "data" / "stage4" / "corpus_with_country.csv"
OUT_DIR     = ROOT / "data"  / "stage5"
FIG_DIR     = ROOT / "figures" / "stage5"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Adoption thresholds (days from repo creation to first AI signal)
DAY1_DAYS   =  7
EARLY_DAYS  = 30

START_MONTH = "2025-02"   # Feb 2025 — Claude Code public release


# ── 1. Load & merge ───────────────────────────────────────────────────────────

def load_data() -> pd.DataFrame:
    if not CORPUS.exists():
        raise SystemExit(f"Missing: {CORPUS}")

    corpus = pd.read_csv(CORPUS, low_memory=False)
    corpus["created_at"] = pd.to_datetime(corpus["created_at"], errors="coerce")
    corpus = corpus.dropna(subset=["created_at"])

    # Only adopted repos
    corpus = corpus[corpus["adoption_label"].isin(["agentic", "ai_assisted"])].copy()

    # Load timestamp files if present
    has_config   = CONFIG_TS.exists()
    has_trailer  = TRAILER_TS.exists()

    if not has_config and not has_trailer:
        raise SystemExit(
            "Neither config_timestamps.csv nor trailer_timestamps.csv found.\n"
            "Run stage5i and/or stage5j first."
        )

    # Merge config timestamps
    if has_config:
        cfg = pd.read_csv(CONFIG_TS)
        cfg = cfg[cfg["api_status"] == "ok"][["full_name", "first_ai_date"]].copy()
        cfg.rename(columns={"first_ai_date": "config_first_date"}, inplace=True)
        cfg["config_first_date"] = pd.to_datetime(cfg["config_first_date"], errors="coerce")
        corpus = corpus.merge(cfg, on="full_name", how="left")
    else:
        corpus["config_first_date"] = pd.NaT

    # Merge trailer timestamps
    if has_trailer:
        trl = pd.read_csv(TRAILER_TS)
        trl = trl[trl["api_status"] == "ok"][["full_name", "first_ai_date",
                                              "first_trailer_agent"]].copy()
        trl.rename(columns={"first_ai_date": "trailer_first_date"}, inplace=True)
        trl["trailer_first_date"] = pd.to_datetime(trl["trailer_first_date"], errors="coerce")
        corpus = corpus.merge(trl, on="full_name", how="left")
    else:
        corpus["trailer_first_date"]  = pd.NaT
        corpus["first_trailer_agent"] = None

    # first_ai_date = earliest of config and trailer dates
    corpus["first_ai_date"] = corpus[["config_first_date",
                                       "trailer_first_date"]].min(axis=1)

    # days_to_adoption (can be 0 for repos where AI was used on day 1)
    corpus["days_to_adoption"] = (
        corpus["first_ai_date"] - corpus["created_at"]
    ).dt.days

    # Clamp negative values to 0 (clocks off, force-pushes, etc.)
    corpus["days_to_adoption"] = corpus["days_to_adoption"].clip(lower=0)

    # Adoption category
    def categorize(row):
        d = row["days_to_adoption"]
        if pd.isna(d):
            return "unknown"
        if d <= DAY1_DAYS:
            return "ai_native"
        if d <= EARLY_DAYS:
            return "early"
        return "late"

    corpus["adoption_category"] = corpus.apply(categorize, axis=1)

    # Month columns
    corpus["created_month"]  = corpus["created_at"].dt.to_period("M")
    corpus["ai_month"]       = corpus["first_ai_date"].dt.to_period("M")

    return corpus


# ── 2. Save merged CSV ────────────────────────────────────────────────────────

def save_csv(df: pd.DataFrame) -> None:
    cols = ["full_name", "created_at", "first_ai_date",
            "days_to_adoption", "adoption_category",
            "adoption_label", "country"]
    # keep only columns that exist
    cols = [c for c in cols if c in df.columns]
    out  = OUT_DIR / "adoption_timeline.csv"
    df[cols].to_csv(out, index=False)
    print(f"  Saved: {out.name}")


# ── 3. RQ-T1  True adoption timeline ─────────────────────────────────────────

def fig_true_timeline(df: pd.DataFrame) -> None:
    # Restrict to months since launch
    sub = df[df["created_month"] >= START_MONTH].copy()
    has_ai_date = sub.dropna(subset=["first_ai_date"])

    # Repos created per month
    created_monthly = sub.groupby("created_month").size().rename("created")
    # Repos where AI was first adopted per month (grouped by first_ai_date month)
    ai_monthly = (
        has_ai_date[has_ai_date["ai_month"] >= START_MONTH]
        .groupby("ai_month")
        .size()
        .rename("first_adoption")
    )

    all_months = sorted(set(created_monthly.index) | set(ai_monthly.index))
    months_str = [str(m) for m in all_months]

    created_vals    = [created_monthly.get(m, 0) for m in all_months]
    ai_vals         = [ai_monthly.get(m, 0)      for m in all_months]

    x = np.arange(len(months_str))
    width = 0.4

    fig, ax = plt.subplots(figsize=(max(10, len(months_str) * 0.55), 5))
    ax.bar(x - width/2, created_vals, width, label="Repos created",    color="#4c72b0", alpha=0.85)
    ax.bar(x + width/2, ai_vals,      width, label="First AI adoption", color="#dd8452", alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(months_str, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Repository count", fontsize=9)
    ax.set_title("True AI Adoption Timeline vs. Repo Creation Date", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    plt.tight_layout()
    out = FIG_DIR / "fig_true_timeline"
    fig.savefig(out.with_suffix(".png"), dpi=150, bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}.png")


# ── 4. RQ-T2  Time-to-adoption distribution ───────────────────────────────────

def fig_time_to_adoption(df: pd.DataFrame) -> None:
    known = df.dropna(subset=["days_to_adoption"])
    days  = known["days_to_adoption"].values

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Left: histogram (capped at 365 days for readability)
    cap = 365
    clipped = np.clip(days, 0, cap)
    ax = axes[0]
    ax.hist(clipped, bins=50, color="#4c72b0", edgecolor="white", linewidth=0.3)
    ax.set_xlabel("Days from repo creation to first AI signal", fontsize=9)
    ax.set_ylabel("Repos", fontsize=9)
    ax.set_title(f"Time-to-Adoption (capped at {cap} days)", fontsize=11, fontweight="bold")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))

    # Annotate percentiles
    pcts = [25, 50, 75, 90]
    colors_p = ["#2ca02c", "#ff7f0e", "#d62728", "#9467bd"]
    for pct, col in zip(pcts, colors_p):
        val = np.percentile(days, pct)
        ax.axvline(val, color=col, linestyle="--", linewidth=1.2,
                   label=f"p{pct}={val:.0f}d")
    ax.legend(fontsize=8)

    # Right: CDF
    ax2 = axes[1]
    sorted_days = np.sort(days)
    cdf = np.arange(1, len(sorted_days) + 1) / len(sorted_days)
    ax2.plot(np.minimum(sorted_days, cap), cdf, color="#4c72b0", linewidth=1.5)
    ax2.set_xlabel("Days from repo creation to first AI signal", fontsize=9)
    ax2.set_ylabel("Cumulative fraction", fontsize=9)
    ax2.set_title("CDF of Time-to-Adoption", fontsize=11, fontweight="bold")
    ax2.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1))
    ax2.set_xlim(0, cap)

    # Reference lines
    for thresh, label, col in [(7, "7d", "#ff7f0e"), (30, "30d", "#d62728")]:
        frac = (days <= thresh).mean()
        ax2.axvline(thresh, color=col, linestyle="--", linewidth=1.2,
                    label=f"{label}: {frac:.1%}")
    ax2.legend(fontsize=8)

    ax2.grid(axis="both", linestyle="--", alpha=0.4)

    plt.suptitle("Time-to-Adoption Distribution", fontsize=12, fontweight="bold", y=1.01)
    plt.tight_layout()
    out = FIG_DIR / "fig_time_to_adoption"
    fig.savefig(out.with_suffix(".png"), dpi=150, bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}.png")


# ── 5. RQ-T3  AI-native vs retrofit ──────────────────────────────────────────

def fig_ai_native_stacked(df: pd.DataFrame) -> None:
    sub = df[df["created_month"] >= START_MONTH].copy()
    sub = sub[sub["adoption_category"] != "unknown"]
    sub["created_month_str"] = sub["created_month"].astype(str)

    order  = sorted(sub["created_month_str"].unique())
    cats   = ["ai_native", "early", "late"]
    labels = ["AI-native (≤7d)", "Early adopter (8–30d)", "Late adopter (>30d)"]
    colors = ["#2ca02c", "#ff7f0e", "#9467bd"]

    pivot = (
        sub.groupby(["created_month_str", "adoption_category"])
        .size()
        .unstack(fill_value=0)
        .reindex(order)
        .reindex(columns=cats, fill_value=0)
    )

    fig, ax = plt.subplots(figsize=(max(10, len(order) * 0.6), 5))
    bottom = np.zeros(len(order))
    x = np.arange(len(order))

    for cat, label, color in zip(cats, labels, colors):
        vals = pivot[cat].values
        ax.bar(x, vals, bottom=bottom, label=label, color=color, alpha=0.85)
        bottom += vals

    ax.set_xticks(x)
    ax.set_xticklabels(order, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Adopted repos", fontsize=9)
    ax.set_title("AI-Native vs. Early vs. Late Adopter\n(grouped by repo creation month)",
                 fontsize=11, fontweight="bold")
    ax.legend(fontsize=9, loc="upper left")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    plt.tight_layout()
    out = FIG_DIR / "fig_ai_native_stacked"
    fig.savefig(out.with_suffix(".png"), dpi=150, bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}.png")


def fig_category_pie(df: pd.DataFrame) -> None:
    counts = df[df["adoption_category"] != "unknown"]["adoption_category"].value_counts()
    cats   = ["ai_native", "early", "late"]
    labels = ["AI-native (≤7d)", "Early (8–30d)", "Late (>30d)"]
    colors = ["#2ca02c", "#ff7f0e", "#9467bd"]

    vals = [counts.get(c, 0) for c in cats]

    fig, ax = plt.subplots(figsize=(6, 6))
    wedges, texts, autotexts = ax.pie(
        vals, labels=labels, colors=colors,
        autopct=lambda p: f"{p:.1f}%\n({int(round(p * sum(vals) / 100)):,})",
        startangle=90, pctdistance=0.75
    )
    for t in autotexts:
        t.set_fontsize(9)
    ax.set_title("Adoption Timing Distribution", fontsize=12, fontweight="bold")

    plt.tight_layout()
    out = FIG_DIR / "fig_adoption_category_pie"
    fig.savefig(out.with_suffix(".png"), dpi=150, bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}.png")


# ── 6. Print summary stats ────────────────────────────────────────────────────

def print_summary(df: pd.DataFrame) -> None:
    total_adopted = len(df)
    with_date     = df["first_ai_date"].notna().sum()
    known_days    = df.dropna(subset=["days_to_adoption"])

    print()
    print("── Summary ──────────────────────────────────────────────────")
    print(f"  Adopted repos total       : {total_adopted:>8,}")
    print(f"  With first_ai_date        : {with_date:>8,}  ({with_date/total_adopted:.1%})")
    print(f"  With days_to_adoption     : {len(known_days):>8,}")
    if len(known_days):
        days = known_days["days_to_adoption"]
        print(f"  Median days-to-adoption   : {days.median():>8.1f}")
        print(f"  Mean  days-to-adoption    : {days.mean():>8.1f}")
        print(f"  p25 / p75                 : {days.quantile(0.25):.0f}d / {days.quantile(0.75):.0f}d")
        for lbl, thresh in [("AI-native (≤7d)", 7), ("Early (8-30d)", 30)]:
            n = (days <= thresh).sum()
            print(f"  {lbl:<26}: {n:>7,}  ({n/len(days):.1%})")
    print()
    cats = df["adoption_category"].value_counts()
    print("  Adoption category breakdown:")
    for cat, n in cats.items():
        print(f"    {cat:<15} {n:>7,}  ({n/total_adopted:.1%})")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Stage 5k -- True Adoption Timeline")
    print("=" * 55)

    df = load_data()

    print(f"Adopted repos loaded      : {len(df):,}")
    print(f"With first_ai_date        : {df['first_ai_date'].notna().sum():,}")
    print()

    save_csv(df)
    print_summary(df)

    print("Generating figures …")
    fig_true_timeline(df)
    fig_time_to_adoption(df)
    fig_ai_native_stacked(df)
    fig_category_pie(df)

    print()
    print("Done.")


if __name__ == "__main__":
    main()

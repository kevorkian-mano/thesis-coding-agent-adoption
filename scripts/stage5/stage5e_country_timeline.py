#!/usr/bin/env python3
"""
Stage 5e -- Country Adoption Timeline
======================================
Tracks AI coding agent adoption across the top countries month by month,
from Feb 2025 to the latest repo creation date in the corpus.

Three complementary visualisations
------------------------------------
A) Heatmap  (fig_country_heatmap)
   Country x month grid.  Cell colour = adoption rate (%) that month.
   Only months where the country has >= MIN_MONTHLY_REPOS repos shown.
   Reveals which countries adopted early vs late and which are consistent.

B) Bump chart  (fig_country_bump)
   Same data as the heatmap but plotted as rank lines (rank 1 = highest
   adoption rate that month among eligible countries).
   Shows countries rising / falling in relative position over time.

C) Cumulative agentic repos  (fig_country_cumulative)
   Running sum of agentic repos per country, month by month.
   Shows raw volume growth; complements the rate-based heatmap.

Country eligibility
--------------------
  - >= MIN_TOTAL_REPOS total repos across the entire period
  - Top N_COUNTRIES by total repo count among eligible countries

Month eligibility (heatmap / bump only)
-----------------------------------------
  - A country x month cell is only included if that country has
    >= MIN_MONTHLY_REPOS repos in that month (avoids noisy single-repo rates).

Input
-----
  data/stage4/corpus_with_country.csv
    Required columns: created_at, country, adoption_label

Output
------
  data/stage5/country_timeline.csv        monthly rates per country
  figures/stage5/fig_country_heatmap.png
  figures/stage5/fig_country_bump.png
  figures/stage5/fig_country_cumulative.png

Usage
-----
  python3 scripts/stage5/stage5e_country_timeline.py
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
CORPUS  = ROOT / "data" / "stage4" / "corpus_with_country.csv"
OUT_DIR = ROOT / "data"  / "stage5"
FIG_DIR = ROOT / "figures" / "stage5"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

# ── configuration ─────────────────────────────────────────────────────────────
N_COUNTRIES      = 15    # top N countries by total repo count
MIN_TOTAL_REPOS  = 30    # minimum total repos across all months (same as stage4)
MIN_MONTHLY_REPOS = 5    # minimum repos in a month for a cell to be shown
START_MONTH      = "2025-02"   # Feb 2025 = Claude Code public release


def load_and_prepare() -> pd.DataFrame:
    df = pd.read_csv(CORPUS, low_memory=False)
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df = df.dropna(subset=["created_at"])
    df["month"] = df["created_at"].dt.to_period("M")
    df = df[df["month"] >= START_MONTH]
    df = df[df["country"] != "not_specified"]
    df["adopted"] = df["adoption_label"].isin(["agentic", "ai_assisted"])
    return df


def build_monthly_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a DataFrame with one row per (country, month) with:
      total_repos, adopted, adoption_rate
    Only countries with >= MIN_TOTAL_REPOS total repos included.
    """
    # Country totals for eligibility filter
    country_totals = df.groupby("country").size()
    eligible = country_totals[country_totals >= MIN_TOTAL_REPOS].index

    df = df[df["country"].isin(eligible)]

    grouped = (
        df.groupby(["country", "month"])
        .agg(total_repos=("adoption_label", "count"),
             adopted=("adopted", "sum"))
        .reset_index()
    )
    grouped["adoption_rate"] = grouped["adopted"] / grouped["total_repos"] * 100
    grouped["month_str"] = grouped["month"].astype(str)
    return grouped


def select_top_countries(monthly: pd.DataFrame) -> list[str]:
    """Pick top N_COUNTRIES by total repos across all months."""
    totals = monthly.groupby("country")["total_repos"].sum().sort_values(ascending=False)
    return totals.head(N_COUNTRIES).index.tolist()


# ── A: Heatmap ────────────────────────────────────────────────────────────────

def plot_heatmap(monthly: pd.DataFrame, countries: list[str]) -> None:
    sub = monthly[monthly["country"].isin(countries)].copy()

    # Mask cells with too few repos
    sub.loc[sub["total_repos"] < MIN_MONTHLY_REPOS, "adoption_rate"] = np.nan

    pivot = sub.pivot_table(
        index="country", columns="month_str", values="adoption_rate"
    )
    # Sort countries by mean adoption rate
    pivot = pivot.loc[pivot.mean(axis=1).sort_values(ascending=False).index]

    fig, ax = plt.subplots(figsize=(max(12, len(pivot.columns) * 0.7), 7))
    im = ax.imshow(pivot.values, aspect="auto", cmap="YlOrRd", vmin=0, vmax=100)

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=9)

    # Annotate cells with the rate value
    for r, country in enumerate(pivot.index):
        for c, month in enumerate(pivot.columns):
            val = pivot.loc[country, month]
            if not np.isnan(val):
                ax.text(c, r, f"{val:.0f}%", ha="center", va="center",
                        fontsize=7, color="black" if val < 60 else "white")

    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Adoption rate (%)", fontsize=9)
    ax.set_title("Monthly AI Adoption Rate by Country", fontsize=12, fontweight="bold")
    ax.set_xlabel("Month", fontsize=9)
    ax.set_ylabel("Country", fontsize=9)

    plt.tight_layout()
    out = FIG_DIR / "fig_country_heatmap.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── B: Bump chart ─────────────────────────────────────────────────────────────

def plot_bump(monthly: pd.DataFrame, countries: list[str]) -> None:
    sub = monthly[monthly["country"].isin(countries)].copy()
    sub = sub[sub["total_repos"] >= MIN_MONTHLY_REPOS]

    # Rank per month (rank 1 = highest adoption rate)
    sub["rank"] = sub.groupby("month_str")["adoption_rate"].rank(
        ascending=False, method="min"
    )

    months = sorted(sub["month_str"].unique())
    cmap   = plt.get_cmap("tab20")
    colors = {c: cmap(i / len(countries)) for i, c in enumerate(countries)}

    fig, ax = plt.subplots(figsize=(max(12, len(months) * 0.7), 7))

    for country in countries:
        cdata = sub[sub["country"] == country].sort_values("month_str")
        if cdata.empty:
            continue
        x = [months.index(m) for m in cdata["month_str"]]
        y = cdata["rank"].tolist()
        ax.plot(x, y, marker="o", markersize=5, linewidth=1.8,
                color=colors[country], label=country, alpha=0.85)
        # Label at last visible point
        ax.annotate(country, xy=(x[-1], y[-1]),
                    xytext=(5, 0), textcoords="offset points",
                    fontsize=7, color=colors[country], va="center")

    ax.set_xticks(range(len(months)))
    ax.set_xticklabels(months, rotation=45, ha="right", fontsize=8)
    ax.invert_yaxis()   # rank 1 at top
    ax.set_ylabel("Rank (1 = highest adoption rate)", fontsize=9)
    ax.set_xlabel("Month", fontsize=9)
    ax.set_title("Country Adoption Rank Over Time", fontsize=12, fontweight="bold")
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    plt.tight_layout()
    out = FIG_DIR / "fig_country_bump.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── C: Cumulative agentic repos ───────────────────────────────────────────────

def plot_cumulative(monthly: pd.DataFrame, countries: list[str]) -> None:
    sub    = monthly[monthly["country"].isin(countries)].copy()
    months = sorted(sub["month_str"].unique())
    cmap   = plt.get_cmap("tab20")
    colors = {c: cmap(i / len(countries)) for i, c in enumerate(countries)}

    fig, ax = plt.subplots(figsize=(max(12, len(months) * 0.7), 6))

    for country in countries:
        cdata = (
            sub[sub["country"] == country]
            .sort_values("month_str")
            .assign(month_str=lambda d: d["month_str"].astype(str))
            .set_index("month_str")
            [["adopted"]]
            .reindex(months, fill_value=0)
        )
        cumulative = cdata["adopted"].cumsum()
        x = range(len(months))
        ax.plot(x, cumulative.values, marker="o", markersize=4, linewidth=1.8,
                color=colors[country], label=country, alpha=0.85)

    ax.set_xticks(range(len(months)))
    ax.set_xticklabels(months, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Cumulative agentic repos", fontsize=9)
    ax.set_xlabel("Month", fontsize=9)
    ax.set_title("Cumulative Agentic Repo Growth by Country", fontsize=12, fontweight="bold")
    ax.legend(fontsize=7, ncol=2, loc="upper left")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x):,}"))

    plt.tight_layout()
    out = FIG_DIR / "fig_country_cumulative.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("Stage 5e -- Country Adoption Timeline")
    print("=" * 55)

    if not CORPUS.exists():
        raise SystemExit(f"Missing: {CORPUS}\nRun stage4a first.")

    df      = load_and_prepare()
    monthly = build_monthly_table(df)
    top_countries = select_top_countries(monthly)

    print(f"Months covered    : {monthly['month_str'].min()} to {monthly['month_str'].max()}")
    print(f"Countries shown   : {len(top_countries)}  (top {N_COUNTRIES} by repo count)")
    print(f"Top countries     : {', '.join(top_countries[:5])} ...")
    print()

    # Save monthly table
    out_csv = OUT_DIR / "country_timeline.csv"
    monthly.to_csv(out_csv, index=False)
    print(f"  Saved: {out_csv.name}")

    print("Generating figures ...")
    plot_heatmap(monthly, top_countries)
    plot_bump(monthly, top_countries)
    plot_cumulative(monthly, top_countries)

    # Print summary table
    print()
    print(f"{'Country':<25} {'Total':>6} {'Adopted':>8} {'Rate%':>7} {'Peak month':<10} {'Peak%':>6}")
    print("-" * 68)
    for country in top_countries:
        cdata = monthly[monthly["country"] == country]
        total   = cdata["total_repos"].sum()
        adopted = cdata["adopted"].sum()
        rate    = adopted / total * 100 if total else 0
        peak_row = cdata.loc[cdata["adoption_rate"].idxmax()]
        print(f"{country:<25} {total:>6,} {int(adopted):>8,} {rate:>7.1f}%"
              f"  {peak_row['month_str']:<10} {peak_row['adoption_rate']:>5.1f}%")

    print()
    print("Done.")


if __name__ == "__main__":
    main()

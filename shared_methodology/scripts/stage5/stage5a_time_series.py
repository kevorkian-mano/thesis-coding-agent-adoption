#!/usr/bin/env python3
"""
Stage 5a -- Time Series: Adoption Trend (Point 1) + Agent Market Share (Point 4)
=================================================================================
Point 1: Monthly adoption rate from Feb 2025 to Sep 2026 — stacked area chart
          showing the growth of agentic / AI-assisted / no-AI repos over time,
          annotated with major tool release dates.

Point 4: Monthly agent market share — which agents dominated early vs late,
          using repo creation date + agents_found as the signal.

Input
-----
  data/stage4/corpus_with_country.csv

Output
------
  data/stage5/monthly_adoption.csv
  data/stage5/monthly_agent_share.csv
  figures/stage5/fig_adoption_time_series.pdf/.png
  figures/stage5/fig_agent_market_share.pdf/.png
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



import re
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import matplotlib.dates as mdates
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
CORPUS  = ROOT / "data" / "stage4" / "corpus_with_country.csv"
OUT_DIR = ROOT / "data"  / "stage5"
FIG_DIR = ROOT / "figures" / "stage5"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

# ── Major tool release dates ───────────────────────────────────────────────────
RELEASES = {
    "Claude Code\n(Feb 2025)":     "2025-02-24",
    "OpenAI Codex CLI\n(Apr 2025)": "2025-04-16",
    "Gemini CLI\n(Jun 2025)":       "2025-06-25",
}

# ── Agent name normalisation ───────────────────────────────────────────────────
def normalise_agent(raw: str) -> str | None:
    n = raw.strip().lower()
    if "claude" in n:         return "Claude Code"
    if "copilot" in n:        return "GitHub Copilot"
    if "cursor" in n:         return "Cursor"
    if "codex" in n:          return "OpenAI Codex"
    if "gemini" in n:         return "Gemini CLI"
    if "devin" in n:          return "Devin"
    if "aider" in n:          return "Aider"
    if "windsurf" in n:       return "Windsurf"
    return None

TOP_AGENTS = ["Claude Code", "GitHub Copilot", "Cursor",
              "OpenAI Codex", "Gemini CLI", "Devin", "Aider", "Windsurf"]
AGENT_COLOURS = {
    "Claude Code":     "#2166ac",
    "GitHub Copilot":  "#4dac26",
    "Cursor":          "#d01c8b",
    "OpenAI Codex":    "#f1a340",
    "Gemini CLI":      "#e66101",
    "Devin":           "#762a83",
    "Aider":           "#1b9e77",
    "Windsurf":        "#a6761d",
}


OUTPUTS = [
    OUT_DIR / "monthly_adoption.csv",
    OUT_DIR / "monthly_agent_share.csv",
    FIG_DIR / "fig_adoption_time_series.pdf",
    FIG_DIR / "fig_agent_market_share.pdf",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="Rerun even if output files already exist")
    args = parser.parse_args()

    print("Stage 5d -- Time Series & Agent Market Share")
    print("=" * 60)

    if not args.force and all(p.exists() for p in OUTPUTS):
        print("All outputs already exist. Skipping.")
        print("Use --force to regenerate.")
        return

    df = pd.read_csv(CORPUS, low_memory=False)
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["month"]      = df["created_at"].dt.to_period("M")

    # Drop the last (incomplete) month
    last_month = df["month"].max()
    df = df[df["month"] < last_month].copy()

    months_all = sorted(df["month"].unique())
    print(f"Date range : {months_all[0]}  →  {months_all[-1]}  ({len(months_all)} months)")
    print(f"Total repos: {len(df):,}")

    # ── Point 1: Monthly adoption rate ────────────────────────────────────────
    monthly = (
        df.groupby("month")
        .apply(lambda g: pd.Series({
            "total":        len(g),
            "agentic":      (g["adoption_label"] == "agentic").sum(),
            "ai_assisted":  (g["adoption_label"] == "ai_assisted").sum(),
            "none":         (g["adoption_label"] == "none").sum(),
        }))
        .reset_index()
    )
    monthly["adopted"]        = monthly["agentic"] + monthly["ai_assisted"]
    monthly["adoption_rate"]  = monthly["adopted"]      / monthly["total"] * 100
    monthly["agentic_pct"]    = monthly["agentic"]      / monthly["total"] * 100
    monthly["ai_assisted_pct"]= monthly["ai_assisted"]  / monthly["total"] * 100
    monthly["none_pct"]       = monthly["none"]          / monthly["total"] * 100
    monthly["month_dt"]       = monthly["month"].dt.to_timestamp()
    monthly.to_csv(OUT_DIR / "monthly_adoption.csv", index=False)

    # Print summary
    print(f"\n{'Month':<10} {'Repos':>6}  {'Adoption%':>10}  {'Agentic%':>9}")
    print("-" * 42)
    for _, r in monthly.iterrows():
        print(f"{str(r['month']):<10} {int(r['total']):>6}  "
              f"{r['adoption_rate']:>9.1f}%  {r['agentic_pct']:>8.1f}%")

    # ── Figure 1: Stacked area — adoption over time ────────────────────────
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.stackplot(
        monthly["month_dt"],
        monthly["agentic_pct"],
        monthly["ai_assisted_pct"],
        monthly["none_pct"],
        labels=["Agentic", "AI-Assisted", "No AI detected"],
        colors=["#2166ac", "#74add1", "#d9d9d9"],
        alpha=0.88,
    )
    # Annotate release dates
    for label, date in RELEASES.items():
        dt = pd.Timestamp(date)
        ax.axvline(dt, color="#d62728", lw=1.3, ls="--", alpha=0.75)
        ax.text(dt, 103, label, ha="center", va="bottom",
                fontsize=7.5, color="#d62728")

    ax.set_xlabel("Month of Repository Creation", fontsize=11)
    ax.set_ylabel("Share of Repositories (%)", fontsize=11)
    ax.set_title(
        "AI Coding Agent Adoption Over Time\n"
        "JS/TS/npm corpus · Feb 2025 – Sep 2026",
        fontsize=12, fontweight="bold",
    )
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax.set_ylim(0, 118)
    ax.legend(loc="lower left", fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    for ext in ("pdf", "png"):
        plt.savefig(FIG_DIR / f"fig_adoption_time_series.{ext}",
                    bbox_inches="tight", dpi=150)
    plt.close()
    print("\nSaved: fig_adoption_time_series.pdf / .png")

    # ── Point 4: Agent market share per month ─────────────────────────────────
    agentic = df[df["adoption_label"] == "agentic"].copy()
    rows = []
    for _, row in agentic.iterrows():
        raw = row["agents_found"]
        if pd.isna(raw):
            continue
        seen = set()
        for tok in str(raw).split("|"):
            label = normalise_agent(tok)
            if label and label not in seen:
                seen.add(label)
                rows.append({"month": row["month"], "agent": label})

    agent_df = pd.DataFrame(rows)
    if agent_df.empty:
        print("No agent data found — skipping market share plot.")
        return

    pivot = (
        agent_df.groupby(["month", "agent"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=TOP_AGENTS, fill_value=0)
    )
    # % share of all agent detections that month
    pivot_pct = pivot.div(pivot.sum(axis=1), axis=0) * 100
    pivot_pct["month_dt"] = pivot_pct.index.to_timestamp()
    pivot_pct.to_csv(OUT_DIR / "monthly_agent_share.csv")

    fig, ax = plt.subplots(figsize=(12, 5))
    for agent in TOP_AGENTS:
        if agent not in pivot_pct.columns:
            continue
        ax.plot(
            pivot_pct["month_dt"], pivot_pct[agent],
            label=agent, color=AGENT_COLOURS[agent],
            lw=2, marker="o", markersize=4,
        )
    for label, date in RELEASES.items():
        ax.axvline(pd.Timestamp(date), color="gray", lw=1, ls=":", alpha=0.6)

    ax.set_xlabel("Month of Repository Creation", fontsize=11)
    ax.set_ylabel("Share of Agent Detections (%)", fontsize=11)
    ax.set_title(
        "Agent Market Share Over Time\n"
        "Among agentic repos by creation month",
        fontsize=12, fontweight="bold",
    )
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax.legend(fontsize=9, loc="upper left", ncol=2)
    ax.grid(alpha=0.3)
    plt.tight_layout()
    for ext in ("pdf", "png"):
        plt.savefig(FIG_DIR / f"fig_agent_market_share.{ext}",
                    bbox_inches="tight", dpi=150)
    plt.close()
    print("Saved: fig_agent_market_share.pdf / .png")
    print("\nStage 5a complete.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Figures for Stage 5l — TypeScript Adoption Timing
Two figures saved to bachelor_thesis/figures/stage5/
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
DATA    = ROOT / "data" / "stage5"
OUT_DIR = ROOT / "bachelor_thesis" / "figures" / "stage5"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BLUE   = "#1f77b4"
ORANGE = "#ff7f0e"
GREEN  = "#2ca02c"
RED    = "#d62728"
GRAY   = "#aaaaaa"
PURPLE = "#9467bd"

df = pd.read_csv(DATA / "ts_adoption_timing.csv")

agentic  = df[df["adoption_label"] == "agentic"]
none_df  = df[df["adoption_label"] == "none"]

# ── Figure 1: TypeScript adoption rate — agentic vs non-agentic ───────────────
# "agentic repos are 2x more likely to have TypeScript"

agentic_ts  = (agentic["timing_category"] != "no_tsconfig").sum()
agentic_no  = (agentic["timing_category"] == "no_tsconfig").sum()
none_ts     = (none_df["timing_category"] == "ts_present").sum()
none_no     = (none_df["timing_category"] == "ts_absent").sum()

n_agentic   = agentic_ts + agentic_no
n_none      = none_ts + none_no

rate_agentic = agentic_ts / n_agentic * 100
rate_none    = none_ts / n_none * 100

fig, ax = plt.subplots(figsize=(7, 4.5))

bars = ax.bar(
    ["Agentic\n(n={:,})".format(n_agentic),
     "Non-agentic\n(n={:,})".format(n_none)],
    [rate_agentic, rate_none],
    color=[BLUE, GRAY],
    width=0.45,
    edgecolor="white"
)

for bar, rate, n_ts in zip(bars, [rate_agentic, rate_none], [agentic_ts, none_ts]):
    ax.text(bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.4,
            f"{rate:.1f}%\n({n_ts:,} repos)",
            ha="center", va="bottom", fontsize=11, fontweight="bold")

ax.set_ylabel("Repos with tsconfig.json (%)", fontsize=11)
ax.set_title("TypeScript Adoption Rate — Agentic vs Non-Agentic\n(JavaScript-primary repos only)",
             fontsize=12, fontweight="bold")
ax.set_ylim(0, max(rate_agentic, rate_none) * 1.35)
ax.spines[["top", "right"]].set_visible(False)
ax.axhline(rate_none, color=GRAY, linestyle="--", linewidth=0.9, alpha=0.6)
ax.text(1.42, rate_none + 0.3, f"baseline {rate_none:.1f}%",
        fontsize=8.5, color=GRAY, va="bottom")

plt.tight_layout()
fig.savefig(OUT_DIR / "fig_5l_ts_adoption_rate.png", dpi=300, bbox_inches="tight")
fig.savefig(OUT_DIR / "fig_5l_ts_adoption_rate.pdf", bbox_inches="tight")
plt.close()
print("Saved fig_5l_ts_adoption_rate")

# ── Figure 2: Timing breakdown — among agentic repos WITH tsconfig ────────────
# "when did TypeScript arrive relative to first AI signal?"

has_ts = agentic[agentic["timing_category"].isin(
    ["ts_before_ai", "ts_same_day", "ts_after_ai"]
)].copy()

n_has_ts  = len(has_ts)
before    = (has_ts["timing_category"] == "ts_before_ai").sum()
same      = (has_ts["timing_category"] == "ts_same_day").sum()
after     = (has_ts["timing_category"] == "ts_after_ai").sum()

labels  = ["Before AI signal\n(already had TS)",
           "Same day as\nfirst AI signal",
           "After AI signal\n(agent-era adoption)"]
counts  = [before, same, after]
colors  = [GRAY, ORANGE, GREEN]
pcts    = [v / n_has_ts * 100 for v in counts]

fig, ax = plt.subplots(figsize=(8, 4.5))
bars = ax.bar(labels, counts, color=colors, width=0.5, edgecolor="white")

for bar, n, pct in zip(bars, counts, pcts):
    ax.text(bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 8,
            f"{n:,}\n({pct:.1f}%)",
            ha="center", va="bottom", fontsize=11, fontweight="bold")

ax.set_ylabel("Number of agentic JS repositories", fontsize=11)
ax.set_title(
    f"TypeScript Adoption Timing Relative to First AI Signal\n"
    f"(Agentic JS repos with tsconfig.json, n={n_has_ts:,} of 8,158 total)",
    fontsize=12, fontweight="bold"
)
ax.set_ylim(0, max(counts) * 1.28)
ax.spines[["top", "right"]].set_visible(False)

# annotation: combined "on or after" percentage
on_or_after = same + after
pct_on_or_after = on_or_after / n_has_ts * 100
ax.text(0.98, 0.97,
        f"{on_or_after:,} repos ({pct_on_or_after:.1f}%) adopted TypeScript\n"
        f"on or after their first AI signal",
        transform=ax.transAxes, ha="right", va="top",
        fontsize=9, color="#444444",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#fff9e6", edgecolor="#cccccc"))

plt.tight_layout()
fig.savefig(OUT_DIR / "fig_5l_ts_timing.png", dpi=300, bbox_inches="tight")
fig.savefig(OUT_DIR / "fig_5l_ts_timing.pdf", bbox_inches="tight")
plt.close()
print("Saved fig_5l_ts_timing")

print(f"\nAll figures saved to: {OUT_DIR}")
print(f"\nKey numbers:")
print(f"  Agentic TS rate  : {rate_agentic:.1f}%  ({agentic_ts:,}/{n_agentic:,})")
print(f"  Non-agentic rate : {rate_none:.1f}%  ({none_ts:,}/{n_none:,})")
print(f"  Ratio            : {rate_agentic/rate_none:.2f}x")
print(f"\nAmong {n_has_ts:,} agentic JS repos with tsconfig:")
print(f"  Before AI : {before:,}  ({before/n_has_ts*100:.1f}%)")
print(f"  Same day  : {same:,}  ({same/n_has_ts*100:.1f}%)")
print(f"  After AI  : {after:,}  ({after/n_has_ts*100:.1f}%)")

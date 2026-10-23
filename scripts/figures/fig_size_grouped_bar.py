#!/usr/bin/env python3
"""
Figure: Repository Size vs Adoption — Three Operationalisations
================================================================
Grouped bar chart: 3 strata (small/medium/large) × 3 approaches.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd
import numpy as np
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "bachelor_thesis" / "figures"
DATA    = ROOT / "data" / "stage4" / "size_comparison.csv"

df = pd.read_csv(DATA)

# Pivot to wide
pivot = df.pivot_table(index="approach", columns="stratum",
                       values=["adoption_rate", "ci_lower", "ci_upper"])

APPROACHES = {
    "A_stars":     "A: Stars\n(≤50 / 51–500 / >500)",
    "B_commits":   "B: Commits\n(tertiles P33/P66)",
    "C_langbytes": "C: Code volume\n(tertiles P33/P66)",
}
STRATA  = ["small", "medium", "large"]
COLORS  = ["#93C5FD", "#2563EB", "#1E3A5F"]
x       = np.arange(len(APPROACHES))
width   = 0.24

fig, ax = plt.subplots(figsize=(10, 5.5))
fig.patch.set_facecolor("white")

for i, (stratum, color) in enumerate(zip(STRATA, COLORS)):
    rates  = [pivot.loc[app, ("adoption_rate", stratum)]
              for app in APPROACHES]
    ci_lo  = [pivot.loc[app, ("adoption_rate", stratum)] -
              pivot.loc[app, ("ci_lower", stratum)]
              for app in APPROACHES]
    ci_hi  = [pivot.loc[app, ("ci_upper", stratum)] -
              pivot.loc[app, ("adoption_rate", stratum)]
              for app in APPROACHES]

    offset = (i - 1) * width
    bars   = ax.bar(x + offset, rates, width, label=stratum.capitalize(),
                    color=color, edgecolor="white", linewidth=0.8,
                    zorder=3)
    ax.errorbar(x + offset, rates, yerr=[ci_lo, ci_hi],
                fmt="none", color="#374151", capsize=3, linewidth=1.1,
                capthick=1.1, zorder=4)
    for bar, rate in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(ci_hi) + 0.8,
                f"{rate:.1f}%", ha="center", fontsize=7.5,
                color="#374151")

ax.set_xticks(x)
ax.set_xticklabels([APPROACHES[a] for a in APPROACHES],
                   fontsize=9.5, linespacing=1.3)
ax.set_ylabel("Adoption rate (%)", fontsize=11)
ax.set_ylim(50, 100)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)
ax.legend(title="Stratum", fontsize=9.5, title_fontsize=9.5,
          loc="upper left", framealpha=0.9)

ax.set_title("Adoption Rate by Repository Size — Three Operationalisations",
             fontsize=12, fontweight="bold", pad=10)

plt.tight_layout()
plt.savefig(OUT_DIR / "fig_size_grouped_bar.pdf", bbox_inches="tight", dpi=150)
plt.savefig(OUT_DIR / "fig_size_grouped_bar.png", bbox_inches="tight", dpi=180)
print("Saved: fig_size_grouped_bar")

#!/usr/bin/env python3
"""
Figure: MENA Country Adoption Rates with 95% CI
=================================================
Horizontal bar chart of 9 eligible MENA countries.
Vertical lines for MENA mean and global mean.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "bachelor_thesis" / "figures"
DATA    = ROOT / "data" / "stage4" / "mena" / "mena_country_ranking.csv"

df   = pd.read_csv(DATA)
elig = df[df["eligible"] == True].sort_values("adoption_rate").copy().reset_index(drop=True)

MENA_MEAN = 65.1
GLOBAL    = 73.0

colors = ["#EF4444" if r < MENA_MEAN else "#2563EB"
          for r in elig["adoption_rate"]]

# Taller figure with more bar spacing to eliminate overlap
fig, ax = plt.subplots(figsize=(11, 6.5))
fig.patch.set_facecolor("white")

y       = np.arange(len(elig))
xerr_lo = elig["adoption_rate"] - elig["ci_lower"]
xerr_hi = elig["ci_upper"]      - elig["adoption_rate"]

bars = ax.barh(y, elig["adoption_rate"], color=colors, alpha=0.87,
               edgecolor="white", height=0.50, zorder=3)
ax.errorbar(elig["adoption_rate"], y,
            xerr=[xerr_lo.values, xerr_hi.values],
            fmt="none", color="#111827", capsize=4,
            linewidth=1.3, capthick=1.3, zorder=4)

# Reference lines
ax.axvline(MENA_MEAN, color="#D97706", linestyle="--", linewidth=1.6,
           zorder=5, label=f"MENA average ({MENA_MEAN}%)")
ax.axvline(GLOBAL, color="#6B7280", linestyle=":", linewidth=1.6,
           zorder=5, label=f"Global average ({GLOBAL}%)")

# Rate + n label: placed clearly to the right of the CI bar
for i, (_, row) in enumerate(elig.iterrows()):
    right_edge = row["ci_upper"]
    ax.text(right_edge + 1.5, i,
            f"{row['adoption_rate']:.1f}%  (n = {int(row['total_repos'])})",
            va="center", fontsize=9, color="#111827")

# Sub-region label: placed to the LEFT of the y-axis labels
subregion_colors = {
    "Gulf":         "#1E3A5F",
    "Levant":       "#1D4ED8",
    "Turkey":       "#2563EB",
    "North Africa": "#D97706",
    "Iran":         "#EF4444",
}
for i, (_, row) in enumerate(elig.iterrows()):
    sc = subregion_colors.get(row["subregion"], "#374151")
    ax.text(-2, i, f"[{row['subregion']}]",
            va="center", ha="right", fontsize=7.5, color=sc, style="italic")

ax.set_yticks(y)
ax.set_yticklabels(elig["country"], fontsize=10)
ax.set_xlabel("Adoption rate (%)", fontsize=11)
ax.set_xlim(0, 115)   # extra room on right for rate labels
ax.set_ylim(-0.7, len(elig) - 0.3)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="x", linestyle="--", alpha=0.35, zorder=0)
ax.legend(fontsize=9, loc="lower right", framealpha=0.88)

ax.set_title("MENA Region: AI Coding Agent Adoption Rate (95% Wilson CI)\n"
             "9 eligible countries (≥ 30 repositories)",
             fontsize=11, fontweight="bold", pad=10)

plt.tight_layout()
plt.savefig(OUT_DIR / "fig_mena_bar.pdf", bbox_inches="tight", dpi=150)
plt.savefig(OUT_DIR / "fig_mena_bar.png", bbox_inches="tight", dpi=180)
print("Saved: fig_mena_bar")

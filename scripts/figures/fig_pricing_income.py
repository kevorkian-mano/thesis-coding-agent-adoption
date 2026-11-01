#!/usr/bin/env python3
"""
fig_pricing_income.py
Bar chart: AI adoption rate + paid vs free tool share by World Bank income group.
Output: bachelor_thesis/figures/fig_pricing_income.png
"""
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
FIG_DIR = ROOT / "bachelor_thesis" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Data from results_summary.tex
GROUPS     = ["High Income", "Upper-Middle", "Lower-Middle", "Low Income"]
ADOPTION   = [80.0,  72.4, 50.6, 23.5]
PAID_PCT   = [91.3,  91.7, 78.8, 60.0]
FREE_PCT   = [ 8.6,   8.3, 20.9, 40.0]
REPOS      = [15020, 10534, 7697, 51]

x = np.arange(len(GROUPS))
width = 0.28

fig, ax1 = plt.subplots(figsize=(10, 5.5))
ax2 = ax1.twinx()

# Adoption rate bars (left axis)
bars1 = ax1.bar(x - width, ADOPTION, width,
                color=["#2166ac", "#74add1", "#f4a582", "#d6604d"],
                edgecolor="white", label="Adoption rate %")

# Paid tool % bars (right axis)
bars2 = ax2.bar(x,        PAID_PCT, width, color="#4dac26", alpha=0.75,
                edgecolor="white", label="Paid tool %")
bars3 = ax2.bar(x + width, FREE_PCT, width, color="#b2abd2", alpha=0.75,
                edgecolor="white", label="Free tool %")

ax1.set_xticks(x)
ax1.set_xticklabels(GROUPS, fontsize=10)
ax1.set_ylabel("AI Adoption Rate (%)", fontsize=10, color="#2166ac")
ax2.set_ylabel("Tool type share among agentic repos (%)", fontsize=10)
ax1.set_ylim(0, 105)
ax2.set_ylim(0, 105)
ax1.yaxis.set_major_formatter(mtick.PercentFormatter())
ax2.yaxis.set_major_formatter(mtick.PercentFormatter())

# Value labels for adoption bars
for bar, val in zip(bars1, ADOPTION):
    ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
             f"{val:.1f}%", ha="center", va="bottom", fontsize=9,
             color="#2166ac", fontweight="bold")

ax1.set_title(
    "AI Adoption Rate and Tool Pricing by World Bank Income Group\n"
    "Paid = requires subscription; Free = free tier / OSS available",
    fontsize=11, fontweight="bold"
)

lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right", fontsize=9)
ax1.grid(axis="y", alpha=0.3)
ax1.spines["top"].set_visible(False)
fig.tight_layout()
plt.savefig(FIG_DIR / "fig_pricing_income.png", dpi=150, bbox_inches="tight")
plt.close()
print(f"Saved: {FIG_DIR / 'fig_pricing_income.png'}")

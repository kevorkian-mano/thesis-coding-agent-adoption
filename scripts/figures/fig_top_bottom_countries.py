#!/usr/bin/env python3
"""
Figure: Top 10 and Bottom 10 Countries — Adoption Rate with 95% CI
====================================================================
Side-by-side horizontal bar charts. Carefully spaced to prevent overlap.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "bachelor_thesis" / "figures"
DATA    = ROOT / "data" / "stage4" / "country_adoption.csv"

df = pd.read_csv(DATA)
df = df.sort_values("adoption_rate", ascending=False).reset_index(drop=True)

top10    = df.head(10).copy().reset_index(drop=True)
bottom10 = df.tail(10).copy().reset_index(drop=True)

GLOBAL   = 73.0
C_TOP    = "#2563EB"
C_BOTTOM = "#EF4444"

def plot_panel(ax, data, color, title):
    data = data.sort_values("adoption_rate").reset_index(drop=True)
    y    = np.arange(len(data))

    xerr_lo = (data["adoption_rate"] - data["ci_lower"]).values
    xerr_hi = (data["ci_upper"] - data["adoption_rate"]).values

    ax.barh(y, data["adoption_rate"], color=color, alpha=0.82,
            edgecolor="white", height=0.55, zorder=3)
    ax.errorbar(data["adoption_rate"], y,
                xerr=[xerr_lo, xerr_hi],
                fmt="none", color="#111827", capsize=3.5,
                linewidth=1.2, capthick=1.2, zorder=4)

    # Rate label: right of CI bar
    for i, (_, row) in enumerate(data.iterrows()):
        ax.text(row["ci_upper"] + 1.2, i,
                f"{row['adoption_rate']:.1f}%",
                va="center", fontsize=8.5, color="#111827")

    # Repo count: placed inside the bar (or just left of it for small bars)
    for i, (_, row) in enumerate(data.iterrows()):
        if row["adoption_rate"] > 20:
            ax.text(1.5, i, f"n={int(row['total_repos']):,}",
                    va="center", ha="left", fontsize=7.2,
                    color="white", alpha=0.85)

    # Global line
    ax.axvline(GLOBAL, color="#6B7280", linestyle="--",
               linewidth=1.4, zorder=5, label=f"Global avg ({GLOBAL}%)")
    ax.legend(fontsize=8, loc="lower right", framealpha=0.85)

    ax.set_yticks(y)
    ax.set_yticklabels(data["country"], fontsize=9.5)
    ax.set_xlabel("Adoption rate (%)", fontsize=10)
    ax.set_xlim(0, 108)
    ax.set_ylim(-0.7, len(data) - 0.3)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", linestyle="--", alpha=0.35, zorder=0)
    ax.set_title(title, fontsize=11, fontweight="bold", pad=8)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 6),
                                gridspec_kw={"wspace": 0.45})
fig.patch.set_facecolor("white")

plot_panel(ax1, top10,    C_TOP,    "Top 10 Countries")
plot_panel(ax2, bottom10, C_BOTTOM, "Bottom 10 Countries")

fig.suptitle("AI Coding Agent Adoption Rate by Country (95% Wilson CI)",
             fontsize=13, fontweight="bold", y=1.01)

plt.tight_layout()
plt.savefig(OUT_DIR / "fig_top_bottom_countries.pdf", bbox_inches="tight", dpi=150)
plt.savefig(OUT_DIR / "fig_top_bottom_countries.png", bbox_inches="tight", dpi=180)
print("Saved: fig_top_bottom_countries")

#!/usr/bin/env python3
"""
Figure: Country Bubble Chart — Repo Count vs Adoption Rate
============================================================
Each bubble = one country. x = log(repos), y = adoption rate.
Bubble size proportional to repo count. Key countries labelled.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import pandas as pd
import numpy as np
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "bachelor_thesis" / "figures"
DATA    = ROOT / "data" / "stage4" / "country_adoption.csv"

df = pd.read_csv(DATA)

GLOBAL = 73.0

# Colour by adoption rate
norm   = mcolors.Normalize(vmin=20, vmax=92)
cmap   = plt.cm.RdYlBu
colors = [cmap(norm(r)) for r in df["adoption_rate"]]

# Bubble size
sizes = (df["total_repos"] / df["total_repos"].max() * 1800 + 60).clip(60, 1800)

fig, ax = plt.subplots(figsize=(11, 6.5))
fig.patch.set_facecolor("white")

sc = ax.scatter(np.log10(df["total_repos"]), df["adoption_rate"],
                s=sizes, c=df["adoption_rate"], cmap="RdYlBu",
                vmin=20, vmax=92, alpha=0.82, edgecolors="#374151",
                linewidths=0.6, zorder=3)

# Global average line
ax.axhline(GLOBAL, color="#6B7280", linestyle="--", linewidth=1.3,
           zorder=2, label=f"Global average ({GLOBAL}%)")

# Label notable countries
LABEL = ["United States", "China", "India", "Germany", "Brazil",
         "Belgium", "Rwanda", "South Korea", "Japan", "United Kingdom",
         "France", "Russia", "Bangladesh", "Pakistan", "Iran",
         "Israel", "Turkey", "Egypt", "Morocco"]

for _, row in df[df["country"].isin(LABEL)].iterrows():
    x = np.log10(row["total_repos"])
    y = row["adoption_rate"]
    offset = (0.06, 3) if row["adoption_rate"] > GLOBAL else (0.06, -4)
    ax.annotate(row["country"], (x, y),
                xytext=(x + offset[0], y + offset[1]),
                fontsize=7.5, color="#111827",
                arrowprops=dict(arrowstyle="-", color="#9CA3AF",
                                lw=0.6, shrinkA=4, shrinkB=2))

# Colorbar
cb = plt.colorbar(sc, ax=ax, pad=0.01, fraction=0.03)
cb.set_label("Adoption rate (%)", fontsize=10)

# x-axis ticks back to real values
xticks = [1, 2, 3, 4]
ax.set_xticks(xticks)
ax.set_xticklabels([f"{10**t:,.0f}" for t in xticks])
ax.set_xlabel("Number of repositories (log scale)", fontsize=11)
ax.set_ylabel("Adoption rate (%)", fontsize=11)
ax.set_ylim(15, 97)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(linestyle="--", alpha=0.3, zorder=0)
ax.legend(fontsize=9.5, loc="lower right", framealpha=0.85)

ax.set_title("Repository Count vs Adoption Rate by Country\n"
             "(bubble size ∝ number of repositories; n = 65 countries)",
             fontsize=12, fontweight="bold", pad=10)

plt.tight_layout()
plt.savefig(OUT_DIR / "fig_country_bubble.pdf", bbox_inches="tight", dpi=150)
plt.savefig(OUT_DIR / "fig_country_bubble.png", bbox_inches="tight", dpi=180)
print("Saved: fig_country_bubble")

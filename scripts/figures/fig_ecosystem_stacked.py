#!/usr/bin/env python3
"""
Figure: Adoption Rate by Ecosystem (Stacked Bar)
==================================================
Stacked bar showing agentic / ai-assisted / none per ecosystem.
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
DATA    = ROOT / "data" / "stage4" / "breakdown_ecosystem.csv"

df = pd.read_csv(DATA)
# Exclude tiny / unknown
df = df[~df["ecosystem_type"].isin(["unknown"])]
df = df.sort_values("adoption_rate", ascending=False).reset_index(drop=True)

# Compute percentages
df["pct_agentic"]     = df["agentic"]     / df["total_repos"] * 100
df["pct_ai_assisted"] = df["ai_assisted"] / df["total_repos"] * 100
df["pct_none"]        = df["none"]        / df["total_repos"] * 100

ecosystems = df["ecosystem_type"].tolist()
x = np.arange(len(ecosystems))
width = 0.55

C_AG  = "#1E3A5F"
C_AI  = "#F59E0B"
C_NON = "#E5E7EB"

fig, ax = plt.subplots(figsize=(10, 5.5))
fig.patch.set_facecolor("white")

b1 = ax.bar(x, df["pct_agentic"],     width, label="Agentic",      color=C_AG,  zorder=3)
b2 = ax.bar(x, df["pct_ai_assisted"], width, bottom=df["pct_agentic"],
            label="AI-assisted", color=C_AI, zorder=3)
b3 = ax.bar(x, df["pct_none"],        width,
            bottom=df["pct_agentic"] + df["pct_ai_assisted"],
            label="None", color=C_NON, edgecolor="#9CA3AF", linewidth=0.5, zorder=3)

# Adoption rate label on top
for i, (_, row) in enumerate(df.iterrows()):
    ax.text(i, row["pct_agentic"] + row["pct_ai_assisted"] + 1.5,
            f"{row['adoption_rate']:.1f}%",
            ha="center", fontsize=9, fontweight="bold", color="#111827")

# Repo count below x-axis
for i, (_, row) in enumerate(df.iterrows()):
    ax.text(i, -4, f"n={int(row['total_repos']):,}",
            ha="center", fontsize=7.8, color="#6B7280")

ax.set_xticks(x)
ax.set_xticklabels(ecosystems, fontsize=10)
ax.set_ylabel("Share of repositories (%)", fontsize=11)
ax.set_ylim(-7, 108)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)
ax.legend(loc="upper right", fontsize=9.5, framealpha=0.9)

ax.set_title("AI Coding Agent Adoption by Package Ecosystem",
             fontsize=12, fontweight="bold", pad=10)

plt.tight_layout()
plt.savefig(OUT_DIR / "fig_ecosystem_stacked.pdf", bbox_inches="tight", dpi=150)
plt.savefig(OUT_DIR / "fig_ecosystem_stacked.png", bbox_inches="tight", dpi=180)
print("Saved: fig_ecosystem_stacked")

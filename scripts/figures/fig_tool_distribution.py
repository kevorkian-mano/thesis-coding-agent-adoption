#!/usr/bin/env python3
"""
Figure: AI Coding Tool Distribution
=====================================
Horizontal bar chart of tool usage among adopters.
Shows top tools; merges tiny ones into "Other".
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "bachelor_thesis" / "figures"
DATA    = ROOT / "data" / "stage4" / "coadoption_tool_counts.csv"

df = pd.read_csv(DATA)

# Merge Claude Code + claude-code (same tool, different detection signal)
df.loc[df.tool == "claude-code", "tool"] = "Claude Code"
df = df.groupby("tool", as_index=False).sum()
df = df.sort_values("repos", ascending=False)

# Keep top 10, group rest as Other
TOP_N = 10
top    = df.head(TOP_N).copy()
others = df.iloc[TOP_N:]
other_row = pd.DataFrame([{
    "tool": "Other tools",
    "repos": others["repos"].sum(),
    "pct_of_corpus": others["pct_of_corpus"].sum(),
    "pct_of_adopted": others["pct_of_adopted"].sum(),
}])
top = pd.concat([top, other_row], ignore_index=True)
top = top.sort_values("repos")   # ascending so largest is at top of hbar

COLORS = ["#CBD5E1"] + ["#93C5FD"] * (TOP_N - 4) + \
         ["#3B82F6", "#2563EB", "#1D4ED8", "#1E3A5F"]
COLORS = COLORS[-len(top):]

fig, ax = plt.subplots(figsize=(9, 5.5))
fig.patch.set_facecolor("white")

bars = ax.barh(top["tool"], top["repos"], color=COLORS,
               edgecolor="white", linewidth=0.8, height=0.65, zorder=3)

for bar, (_, row) in zip(bars, top.iterrows()):
    w = bar.get_width()
    ax.text(w + 130, bar.get_y() + bar.get_height() / 2,
            f"{int(w):,}  ({row['pct_of_adopted']:.1f}% of adopters)",
            va="center", fontsize=8.5, color="#374151")

ax.set_xlabel("Repositories", fontsize=11)
ax.set_xlim(0, top["repos"].max() * 1.52)
ax.spines[["top", "right"]].set_visible(False)
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x):,}"))
ax.grid(axis="x", linestyle="--", alpha=0.35, zorder=0)

ax.set_title("AI Coding Tool Usage Among Adopters",
             fontsize=12, fontweight="bold", pad=10)

plt.tight_layout()
plt.savefig(OUT_DIR / "fig_tool_distribution.pdf", bbox_inches="tight", dpi=150)
plt.savefig(OUT_DIR / "fig_tool_distribution.png", bbox_inches="tight", dpi=180)
print("Saved: fig_tool_distribution")

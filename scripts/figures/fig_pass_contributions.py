#!/usr/bin/env python3
"""
Figure: Per-Pass Contribution to Final Agentic Count
======================================================
Horizontal stacked bar showing how many repos each pass added.
Stage 3d is now called Pass 4 (Phase 1 + Phase 2).
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[2] / "bachelor_thesis" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

passes = [
    "Pass 1\nConfig files",
    "Pass 2\nCommit trailers",
    "Pass 3\nDeep scan",
    "Pass 4 – Phase 1\nReclassify (no API)",
    "Pass 4 – Phase 2\nReclassify (deep API)",
]
counts   = [25010, 9618, 764, 3846, 258]
total_ag = 39496

COLORS = ["#1E3A5F", "#2563EB", "#3B82F6", "#7C3AED", "#A78BFA"]

fig, ax = plt.subplots(figsize=(11, 4.2))
fig.patch.set_facecolor("white")

cum = 0
for label, count, color in zip(passes, counts, COLORS):
    ax.barh(0, count, left=cum, color=color, edgecolor="white",
            linewidth=1.5, height=0.55, zorder=3)
    pct = count / total_ag * 100
    cx  = cum + count / 2
    if count > 500:
        ax.text(cx, 0, f"{count:,}\n({pct:.1f}%)",
                ha="center", va="center", fontsize=8.5,
                color="white", fontweight="bold", zorder=4)
    cum += count

ax.set_xlim(0, total_ag * 1.04)
ax.set_ylim(-0.6, 1.35)
ax.set_xlabel("Repositories classified as agentic", fontsize=11)
ax.set_yticks([])
ax.spines[["top", "right", "left"]].set_visible(False)
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x):,}"))
ax.grid(axis="x", linestyle="--", alpha=0.4, zorder=0)

patches = [mpatches.Patch(color=c, label=l.replace("\n", " "))
           for c, l in zip(COLORS, passes)]
ax.legend(handles=patches, loc="upper right", fontsize=8.5,
          framealpha=0.9, ncol=2)

ax.set_title(
    f"Contribution of Each Detection Pass to Final Agentic Count (n = {total_ag:,})",
    fontsize=12, fontweight="bold", pad=10)

plt.tight_layout()
plt.savefig(OUT_DIR / "fig_pass_contributions.pdf", bbox_inches="tight", dpi=150)
plt.savefig(OUT_DIR / "fig_pass_contributions.png", bbox_inches="tight", dpi=180)
print("Saved: fig_pass_contributions")

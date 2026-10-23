#!/usr/bin/env python3
"""
Figure: Tool Loyalty — Number of Tools per Adopter Repo
=========================================================
Left: donut chart for 1 / 2 / 3+ tools.
Right: horizontal bar for top tool pairs.
Carefully spaced to prevent any overlap.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "bachelor_thesis" / "figures"

loyalty = {1: 40532, 2: 1715, 3: 176}
total   = sum(loyalty.values())

labels_raw = ["1 tool", "2 tools", "3+ tools"]
pcts       = [loyalty[k] / total * 100 for k in [1, 2, 3]]
labels     = [f"{l}\n{p:.1f}%" for l, p in zip(labels_raw, pcts)]
sizes      = [loyalty[k] for k in [1, 2, 3]]
colors     = ["#1E3A5F", "#3B82F6", "#93C5FD"]
explode    = [0.04, 0.04, 0.04]

pairs = [
    ("Claude Code + Cursor",         628),
    ("Claude Code + GitHub Copilot", 439),
    ("Claude Code + OpenAI Codex",   276),
    ("Claude Code + MCP",            145),
    ("Aider + Claude Code",           78),
]

fig = plt.figure(figsize=(12, 5))
fig.patch.set_facecolor("white")
gs  = gridspec.GridSpec(1, 2, width_ratios=[1, 1.2], wspace=0.42,
                        left=0.04, right=0.97, top=0.88, bottom=0.10)

# ── donut ─────────────────────────────────────────────────────────────────────
ax1 = fig.add_subplot(gs[0])
wedges, texts = ax1.pie(
    sizes,
    labels=None,          # labels placed manually below to avoid overlap
    colors=colors,
    explode=explode,
    startangle=90,
    counterclock=False,
    wedgeprops=dict(width=0.52, edgecolor="white", linewidth=2.5),
)

# Centre text
ax1.text(0, 0, f"{total:,}\nadopters", ha="center", va="center",
         fontsize=9.5, fontweight="bold", color="#111827")

# Manual legend instead of pie labels (avoids overlap)
from matplotlib.patches import Patch
legend_handles = [Patch(facecolor=c, label=l)
                  for c, l in zip(colors, labels)]
ax1.legend(handles=legend_handles, loc="lower center",
           bbox_to_anchor=(0.5, -0.18), ncol=3,
           fontsize=9, framealpha=0.9, handlelength=1.2)

ax1.set_title("Tool Loyalty", fontsize=11, fontweight="bold", pad=8)

# ── top pairs bar ─────────────────────────────────────────────────────────────
ax2 = fig.add_subplot(gs[1])
pair_labels = [p[0] for p in reversed(pairs)]
pair_vals   = [p[1] for p in reversed(pairs)]

bars = ax2.barh(range(len(pairs)), pair_vals,
                color="#2563EB", edgecolor="white",
                height=0.52, zorder=3)

for i, (bar, val) in enumerate(zip(bars, pair_vals)):
    ax2.text(bar.get_width() + 9, i,
             f"{val:,}", va="center", fontsize=9, color="#374151")

ax2.set_yticks(range(len(pairs)))
ax2.set_yticklabels(pair_labels, fontsize=8.8)
ax2.set_xlabel("Repositories", fontsize=10)
ax2.set_xlim(0, max(pair_vals) * 1.28)
ax2.set_ylim(-0.6, len(pairs) - 0.4)
ax2.spines[["top", "right"]].set_visible(False)
ax2.grid(axis="x", linestyle="--", alpha=0.35, zorder=0)
ax2.set_title("Top Tool Pairs (multi-tool repos)", fontsize=11,
              fontweight="bold", pad=8)

fig.suptitle("Tool Loyalty Among AI Coding Agent Adopters",
             fontsize=12, fontweight="bold", y=0.98)

plt.savefig(OUT_DIR / "fig_tool_loyalty.pdf", bbox_inches="tight", dpi=150)
plt.savefig(OUT_DIR / "fig_tool_loyalty.png", bbox_inches="tight", dpi=180)
print("Saved: fig_tool_loyalty")

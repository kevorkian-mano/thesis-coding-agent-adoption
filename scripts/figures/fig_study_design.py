#!/usr/bin/env python3
"""
Figure: Study Design Overview (Methodology)
=============================================
4-stage pipeline architecture diagram:
  Stage 1 → Stage 2 → Stage 3 → Stage 4
Each stage box shows: name, method, input/output counts.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[2] / "bachelor_thesis" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

STAGE_DATA = [
    {
        "title":   "Stage 1",
        "name":    "Corpus Construction",
        "color":   "#1E3A5F",
        "lines": [
            "GitHub GraphQL Search API",
            "Rolling 5-day date windows",
            "JS + TS repositories",
            "After 24 Feb 2025",
            "",
            "Filters: ≥4 stars, ≥50 commits,",
            "not a fork, JS+TS ≥ 175 KB",
            "",
            "Output: 60,129 repositories",
        ],
    },
    {
        "title":   "Stage 2",
        "name":    "Owner Location\nInference",
        "color":   "#1D4ED8",
        "lines": [
            "GitHub REST API (user profiles)",
            "Two-pass inference:",
            "  Pass 1: location field",
            "  Pass 2: bio, TLD, network",
            "",
            "7 inference signals",
            "50,002 unique owners",
            "",
            "Located: 21,948 (43.9%)",
        ],
    },
    {
        "title":   "Stage 3",
        "name":    "AI Adoption\nDetection",
        "color":   "#2563EB",
        "lines": [
            "4-pass tiered pipeline:",
            "  P1: config files (CLAUDE.md…)",
            "  P2: commit trailers",
            "  P3: deep GraphQL scan",
            "  3d: reclassification",
            "",
            "STRONG / MEDIUM / WEAK signals",
            "",
            "Output: 39,496 agentic (65.7%)",
            "        4,399 ai-assisted (7.3%)",
        ],
    },
    {
        "title":   "Stage 4",
        "name":    "Geographic &\nStatistical Analysis",
        "color":   "#7C3AED",
        "lines": [
            "Join corpus ↔ located owners",
            "65 countries (≥30 repos)",
            "",
            "Tests: Fisher exact, χ², McNemar,",
            "       Wilson CI, BH FDR",
            "",
            "Sub-analyses:",
            "  • Country ranking",
            "  • MENA deep-dive",
            "  • Repo-size analysis",
        ],
    },
]

fig, ax = plt.subplots(figsize=(14, 5.5))
fig.patch.set_facecolor("white")
ax.set_xlim(0, 14)
ax.set_ylim(0, 5.5)
ax.axis("off")

BOX_W = 3.0
BOX_H = 4.6
GAP   = 0.55
STARTS = [0.2 + i * (BOX_W + GAP) for i in range(4)]

for i, (stage, sx) in enumerate(zip(STAGE_DATA, STARTS)):
    # Shadow
    shadow = FancyBboxPatch((sx + 0.07, 0.27), BOX_W, BOX_H,
                            boxstyle="round,pad=0.12",
                            facecolor="#D1D5DB", edgecolor="none",
                            zorder=1)
    ax.add_patch(shadow)

    # Main box
    box = FancyBboxPatch((sx, 0.3), BOX_W, BOX_H,
                         boxstyle="round,pad=0.12",
                         facecolor=stage["color"], edgecolor="white",
                         linewidth=1.5, zorder=2)
    ax.add_patch(box)

    # Header band
    hdr = FancyBboxPatch((sx, 0.3 + BOX_H - 0.82), BOX_W, 0.82,
                         boxstyle="round,pad=0.12",
                         facecolor="#111827", edgecolor="none",
                         zorder=3)
    ax.add_patch(hdr)

    cx = sx + BOX_W / 2
    # Title
    ax.text(cx, 0.3 + BOX_H - 0.36, stage["title"],
            ha="center", va="center", fontsize=11, fontweight="bold",
            color="white", zorder=4)
    ax.text(cx, 0.3 + BOX_H - 0.65, stage["name"],
            ha="center", va="center", fontsize=8, color="#D1D5DB", zorder=4)

    # Body lines
    y_start = 0.3 + BOX_H - 1.05
    for line in stage["lines"]:
        ax.text(sx + 0.18, y_start, line,
                ha="left", va="top", fontsize=7.8,
                color="white" if line else "white",
                alpha=0.92, zorder=4)
        y_start -= 0.35

    # Arrow to next box
    if i < 3:
        ax.annotate("",
                    xy=(STARTS[i+1] - 0.02, 0.3 + BOX_H / 2),
                    xytext=(sx + BOX_W + 0.02, 0.3 + BOX_H / 2),
                    arrowprops=dict(
                        arrowstyle="-|>",
                        color="#374151",
                        lw=2,
                        mutation_scale=16,
                    ), zorder=5)

ax.set_title("Study Design Overview: Four-Stage Research Pipeline",
             fontsize=13, fontweight="bold", y=0.97)

plt.tight_layout(pad=0.4)
plt.savefig(OUT_DIR / "fig_study_design.pdf", bbox_inches="tight", dpi=150)
plt.savefig(OUT_DIR / "fig_study_design.png", bbox_inches="tight", dpi=180)
print("Saved: fig_study_design")

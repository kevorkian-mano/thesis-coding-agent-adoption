#!/usr/bin/env python3
"""
Figure: Detection Pipeline Flow Diagram
========================================
Produces a flow diagram showing how the 60,129 repos are processed
through the 4 passes of Stage 3, with counts at each step.

Output
------
  bachelor_thesis/figures/fig_pipeline_flow.pdf
  bachelor_thesis/figures/fig_pipeline_flow.png

Usage
-----
  python3 scripts/figures/fig_pipeline_flow.py
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "bachelor_thesis" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── colour palette ─────────────────────────────────────────────────────────────
C_PASS   = "#2563EB"   # blue  – pass boxes
C_AG     = "#16A34A"   # green – agentic output
C_AI     = "#D97706"   # amber – ai_assisted output
C_NONE   = "#6B7280"   # grey  – none output
C_ARROW  = "#374151"
C_BG     = "#F9FAFB"
C_LABEL  = "white"

fig, ax = plt.subplots(figsize=(10, 13))
ax.set_xlim(0, 10)
ax.set_ylim(0, 14)
ax.axis("off")
fig.patch.set_facecolor(C_BG)
ax.set_facecolor(C_BG)

# ── helper functions ───────────────────────────────────────────────────────────

def box(ax, x, y, w, h, text, subtext="", color=C_PASS, textsize=11, subtextsize=9):
    rect = FancyBboxPatch((x - w/2, y - h/2), w, h,
                          boxstyle="round,pad=0.1",
                          facecolor=color, edgecolor="white",
                          linewidth=1.5, zorder=3)
    ax.add_patch(rect)
    ty = y + (0.18 if subtext else 0)
    ax.text(x, ty, text, ha="center", va="center",
            fontsize=textsize, fontweight="bold", color=C_LABEL, zorder=4)
    if subtext:
        ax.text(x, y - 0.22, subtext, ha="center", va="center",
                fontsize=subtextsize, color=C_LABEL, alpha=0.9, zorder=4)


def arrow_down(ax, x, y_start, y_end, label="", color=C_ARROW):
    ax.annotate("", xy=(x, y_end + 0.04), xytext=(x, y_start - 0.04),
                arrowprops=dict(arrowstyle="-|>", color=color,
                                lw=1.8, mutation_scale=14), zorder=2)
    if label:
        ax.text(x + 0.18, (y_start + y_end) / 2, label,
                ha="left", va="center", fontsize=8.5, color=color)


def side_box(ax, x, y, w, h, text, subtext="", color=C_AG):
    rect = FancyBboxPatch((x, y - h/2), w, h,
                          boxstyle="round,pad=0.08",
                          facecolor=color, edgecolor="white",
                          linewidth=1.2, zorder=3, alpha=0.92)
    ax.add_patch(rect)
    ty = y + (0.15 if subtext else 0)
    ax.text(x + w/2, ty, text, ha="center", va="center",
            fontsize=9, fontweight="bold", color="white", zorder=4)
    if subtext:
        ax.text(x + w/2, y - 0.18, subtext, ha="center", va="center",
                fontsize=8, color="white", alpha=0.9, zorder=4)


def side_arrow(ax, from_x, from_y, to_x, label="", color=C_AG):
    ax.annotate("", xy=(to_x, from_y), xytext=(from_x, from_y),
                arrowprops=dict(arrowstyle="-|>", color=color,
                                lw=1.5, mutation_scale=12), zorder=2)
    if label:
        mid = (from_x + to_x) / 2
        ax.text(mid, from_y + 0.13, label, ha="center", va="bottom",
                fontsize=8, color=color)


# ── layout constants ───────────────────────────────────────────────────────────
CX    = 5.0   # centre x of main pipeline
BW    = 3.4   # box width
BH    = 0.72  # box height
SBW   = 2.6   # side box width
SBH   = 0.60  # side box height
SX    = 6.95  # side box left edge

# y positions (top → bottom)
Y_INPUT = 13.0
Y_P1    = 11.6
Y_P1OUT = 10.95
Y_P2    = 9.8
Y_P2OUT = 9.1
Y_P3    = 8.0
Y_P3OUT = 7.3
Y_3D    = 6.0
Y_3DA   = 5.25
Y_FINAL = 3.8
Y_FIN_L = 3.1

# ── draw ───────────────────────────────────────────────────────────────────────

# Input corpus
box(ax, CX, Y_INPUT, BW, BH,
    "60,129 repositories", "corpus after Stage 1 & 2 filtering",
    color="#1E3A5F", textsize=12)

# Pass 1
arrow_down(ax, CX, Y_INPUT - BH/2, Y_P1 + BH/2,
           label="all repos")
box(ax, CX, Y_P1, BW, BH,
    "Pass 1 — Config Files",
    "check for CLAUDE.md, AGENTS.md, .cursorrules, …",
    color=C_PASS)

# Pass 1 output → side
side_arrow(ax, CX + BW/2, Y_P1OUT, SX, color=C_AG)
side_box(ax, SX, Y_P1OUT, SBW, SBH,
         "25,010 agentic",
         "config file found (MEDIUM signal)",
         color=C_AG)

# Pass 2
arrow_down(ax, CX, Y_P1 - BH/2, Y_P2 + BH/2,
           label="35,119 unclassified")
box(ax, CX, Y_P2, BW, BH,
    "Pass 2 — Commit Trailers",
    "scan last 100 commits + PR branch names",
    color=C_PASS)

# Pass 2 output → side (split)
side_arrow(ax, CX + BW/2, Y_P2OUT, SX, color=C_AG)
side_box(ax, SX, Y_P2OUT + 0.35, SBW, SBH * 0.85,
         "9,618 agentic",
         "≥3 AI commits / 2+ agents",
         color=C_AG)
side_box(ax, SX, Y_P2OUT - 0.35, SBW, SBH * 0.85,
         "3,846 ai-assisted",
         "1–2 AI commits, 1 agent",
         color=C_AI)

# Pass 3
arrow_down(ax, CX, Y_P2 - BH/2, Y_P3 + BH/2,
           label="21,655 unclassified")
box(ax, CX, Y_P3, BW, BH,
    "Pass 3 — Deep Scan",
    "150 commits + 50 PRs, STRONG/MEDIUM/WEAK tiers",
    color=C_PASS)

# Pass 3 output → side (split)
side_arrow(ax, CX + BW/2, Y_P3OUT, SX, color=C_AG)
side_box(ax, SX, Y_P3OUT + 0.35, SBW, SBH * 0.85,
         "764 agentic",
         "≥1 STRONG or ≥2 MEDIUM signals",
         color=C_AG)
side_box(ax, SX, Y_P3OUT - 0.35, SBW, SBH * 0.85,
         "4,657 ai-assisted",
         "1 MEDIUM / WEAK only",
         color=C_AI)

# 16,234 none continues down
arrow_down(ax, CX, Y_P3 - BH/2, Y_3D + BH/2,
           label="8,503 ai-assisted  +  16,234 none")

# Stage 3d
box(ax, CX, Y_3D, BW, BH,
    "Stage 3d — Reclassification",
    "Phase 1 (no API) + Phase 2 (deep API checks)",
    color="#7C3AED")

# 3d output
side_arrow(ax, CX + BW/2, Y_3DA, SX, color=C_AG)
side_box(ax, SX, Y_3DA + 0.35, SBW, SBH * 0.85,
         "3,846 upgraded",
         "Phase 1: trailer = STRONG → agentic",
         color=C_AG)
side_box(ax, SX, Y_3DA - 0.35, SBW, SBH * 0.85,
         "258 upgraded",
         "Phase 2: extended CI/bot/config checks",
         color=C_AG)

# 16,234 none stays
ax.text(CX + 0.15, (Y_3D - BH/2 + Y_FINAL + BH/2) / 2,
        "16,234 none  +  4,399 ai-assisted remain",
        ha="left", va="center", fontsize=8, color=C_NONE, style="italic")

# Final summary box
arrow_down(ax, CX, Y_3D - BH/2, Y_FINAL + BH/2)
rect_final = FancyBboxPatch((CX - BW/2 - 0.2, Y_FINAL - 0.52),
                            BW + 0.4, 1.04,
                            boxstyle="round,pad=0.12",
                            facecolor="#111827", edgecolor="white",
                            linewidth=2, zorder=3)
ax.add_patch(rect_final)
ax.text(CX, Y_FINAL + 0.22, "Final Classification", ha="center", va="center",
        fontsize=11, fontweight="bold", color="white", zorder=4)
ax.text(CX, Y_FINAL - 0.17,
        "39,496 agentic (65.7%)   |   4,399 ai-assisted (7.3%)   |   16,234 none (27.0%)",
        ha="center", va="center", fontsize=8.5, color="#D1FAE5", zorder=4)

# ── adoption rate callout ──────────────────────────────────────────────────────
ax.text(CX, Y_FINAL - 0.58,
        "Total adopted: 43,895  (73.0%)",
        ha="center", va="center", fontsize=9.5, fontweight="bold",
        color="#34D399", zorder=4)

# ── title ─────────────────────────────────────────────────────────────────────
ax.text(CX, 13.75, "Stage 3 Detection Pipeline",
        ha="center", va="center", fontsize=14, fontweight="bold",
        color="#111827")

plt.tight_layout(pad=0.3)
plt.savefig(OUT_DIR / "fig_pipeline_flow.pdf", bbox_inches="tight", dpi=150)
plt.savefig(OUT_DIR / "fig_pipeline_flow.png", bbox_inches="tight", dpi=180)
print("Saved: fig_pipeline_flow.pdf / .png")

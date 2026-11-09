#!/usr/bin/env python3
"""
Figures for Stage 5i / 5j / 5k summary section in results_summary.tex
Generates 3 figures saved to bachelor_thesis/figures/stage5/
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
DATA    = ROOT / "data" / "stage5"
OUT_DIR = ROOT / "bachelor_thesis" / "figures" / "stage5"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BLUE   = "#1f77b4"
ORANGE = "#ff7f0e"
GREEN  = "#2ca02c"
GRAY   = "#aaaaaa"

# ── Load data ─────────────────────────────────────────────────────────────────
cfg = pd.read_csv(DATA / "config_timestamps.csv")
tr  = pd.read_csv(DATA / "trailer_timestamps.csv")
at  = pd.read_csv(DATA / "adoption_timeline.csv")

# ── Figure 1: Adoption Timing Breakdown (5k) ─────────────────────────────────
agentic = at[at["adoption_label"] == "agentic"].copy()
cats  = agentic["adoption_category"].value_counts()
order = ["ai_native", "early", "late", "unknown"]
labels = {"ai_native": "Immediate\n(≤7 days)", "early": "Early\n(8–30 days)",
          "late": "Late\n(>30 days)", "unknown": "Unknown"}
colors = [GREEN, BLUE, ORANGE, GRAY]

counts = [cats.get(k, 0) for k in order]
total_known = sum(counts[:3])
total_all   = sum(counts)

fig, ax = plt.subplots(figsize=(8, 4.5))
bars = ax.barh([labels[k] for k in order], counts, color=colors, edgecolor="white", height=0.55)

for bar, n in zip(bars, counts):
    pct = n / total_all * 100
    ax.text(bar.get_width() + 150, bar.get_y() + bar.get_height() / 2,
            f"{n:,}  ({pct:.1f}%)", va="center", fontsize=10)

ax.set_xlabel("Number of agentic repositories", fontsize=11)
ax.set_title("Adoption Timing — All 40,364 Agentic Repos (Stage 5k)", fontsize=12, fontweight="bold")
ax.set_xlim(0, max(counts) * 1.28)
ax.invert_yaxis()
ax.spines[["top", "right"]].set_visible(False)
ax.text(0.98, 0.03,
        f"Median days to first AI signal: 3.0  |  Mean: 54.1  |  Known: {total_known:,}/{total_all:,}",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=8.5, color="#555555")
plt.tight_layout()
fig.savefig(OUT_DIR / "fig_5k_adoption_timing.png", dpi=300, bbox_inches="tight")
fig.savefig(OUT_DIR / "fig_5k_adoption_timing.pdf", bbox_inches="tight")
plt.close()
print("Saved fig_5k_adoption_timing")

# ── Figure 2: Top First Config Files (5i) ────────────────────────────────────
cfg_ok = cfg[cfg["api_status"] == "ok"].copy()
top_cfg = cfg_ok["first_config_file"].value_counts().head(10)

fig, ax = plt.subplots(figsize=(8, 5))
bars = ax.barh(top_cfg.index[::-1], top_cfg.values[::-1], color=BLUE, edgecolor="white", height=0.6)
for bar, n in zip(bars, top_cfg.values[::-1]):
    pct = n / len(cfg_ok) * 100
    ax.text(bar.get_width() + 50, bar.get_y() + bar.get_height() / 2,
            f"{n:,}  ({pct:.1f}%)", va="center", fontsize=9.5)

ax.set_xlabel("Repositories", fontsize=11)
ax.set_title("First Detected Config File — Top 10 (Stage 5i, n=28,369 repos)", fontsize=12, fontweight="bold")
ax.set_xlim(0, top_cfg.max() * 1.28)
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
fig.savefig(OUT_DIR / "fig_5i_first_config.png", dpi=300, bbox_inches="tight")
fig.savefig(OUT_DIR / "fig_5i_first_config.pdf", bbox_inches="tight")
plt.close()
print("Saved fig_5i_first_config")

# ── Figure 3: Monthly First AI Signal (5i + 5j combined, 2025-02 onwards) ───
cfg_ok["month"] = pd.to_datetime(cfg_ok["first_ai_date"], errors="coerce").dt.to_period("M")
tr_ok = tr[tr["api_status"] == "ok"].copy()
tr_ok["month"] = pd.to_datetime(tr_ok["first_ai_date"], errors="coerce").dt.to_period("M")

start = pd.Period("2025-02", "M")
cfg_monthly = cfg_ok[cfg_ok["month"] >= start]["month"].value_counts().sort_index()
tr_monthly  = tr_ok[tr_ok["month"] >= start]["month"].value_counts().sort_index()

all_months = cfg_monthly.index.union(tr_monthly.index)
cfg_vals = [cfg_monthly.get(m, 0) for m in all_months]
tr_vals  = [tr_monthly.get(m, 0) for m in all_months]
x = np.arange(len(all_months))
labels_m = [str(m) for m in all_months]

fig, ax = plt.subplots(figsize=(12, 4.8))
width = 0.42
b1 = ax.bar(x - width / 2, cfg_vals, width, label="Config file (5i)", color=BLUE,  alpha=0.85)
b2 = ax.bar(x + width / 2, tr_vals,  width, label="Commit trailer (5j)", color=ORANGE, alpha=0.85)

# Release annotations
releases = {"2025-02": "Claude Code\nFeb 2025", "2025-04": "Codex CLI\nApr 2025", "2025-06": "Gemini CLI\nJun 2025"}
for mon, label in releases.items():
    idx = labels_m.index(mon) if mon in labels_m else None
    if idx is not None:
        ax.axvline(idx, color="gray", linestyle="--", linewidth=0.9, alpha=0.7)
        ax.text(idx + 0.1, max(max(cfg_vals), max(tr_vals)) * 0.97,
                label, fontsize=7.5, color="gray", va="top")

ax.set_xticks(x)
ax.set_xticklabels(labels_m, rotation=45, ha="right", fontsize=8)
ax.set_ylabel("Repositories", fontsize=11)
ax.set_title("Monthly First AI Signal Date — Config (5i) vs Trailer (5j)", fontsize=12, fontweight="bold")
ax.legend(fontsize=10)
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
fig.savefig(OUT_DIR / "fig_5ij_monthly_first_signal.png", dpi=300, bbox_inches="tight")
fig.savefig(OUT_DIR / "fig_5ij_monthly_first_signal.pdf", bbox_inches="tight")
plt.close()
print("Saved fig_5ij_monthly_first_signal")

print("\nAll figures saved to:", OUT_DIR)

#!/usr/bin/env python3
"""
fig_framework_adoption.py
Horizontal bar chart: agentic adoption rate for top 20 frameworks.
Output: bachelor_thesis/figures/fig_framework_adoption.png
"""
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
FIG_DIR = ROOT / "bachelor_thesis" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Data from results_summary.tex (top 20 frameworks, sorted by agentic%)
DATA = [
    ("Astro",         83.5, 1417),
    ("Hono",          82.1, 2672),
    ("TanStack Start",79.4,  670),
    ("VitePress",     77.8,  923),
    ("Solid",         77.8,  573),
    ("Fastify",       77.3, 1339),
    ("Electron",      75.6, 4366),
    ("SvelteKit",     75.6,  544),
    ("Svelte",        74.9, 1076),
    ("Preact",        74.2,  472),
    ("Tauri",         73.4, 2777),
    ("tRPC",          70.3,  528),
    ("Expo",          69.0, 1110),
    ("Vue",           68.3, 1911),
    ("Capacitor",     68.2,  588),
    ("React Native",  67.6, 1387),
    ("React",         65.2,30614),
    ("Next.js",       63.6,10807),
    ("NestJS",        62.0,  933),
    ("Express",       57.8, 7131),
]

frameworks = [d[0] for d in DATA]
rates      = [d[1] for d in DATA]
# Colour: green for ≥75%, blue for 65-75%, red for <65%
colors = ["#2166ac" if r >= 75 else "#74add1" if r >= 65 else "#d9d9d9" for r in rates]

fig, ax = plt.subplots(figsize=(10, 6.5))
y = range(len(frameworks))
bars = ax.barh(list(y), rates[::-1] if False else list(reversed(rates)),
               color=list(reversed(colors)), edgecolor="white", height=0.7)

ax.set_yticks(list(y))
ax.set_yticklabels(list(reversed(frameworks)), fontsize=9)
ax.set_xlabel("Agentic Adoption Rate (%)", fontsize=10)
ax.set_title(
    "AI (Agentic) Adoption Rate by JavaScript Framework\n"
    "Top 20 frameworks in the corpus (multi-label; not mutually exclusive)",
    fontsize=11, fontweight="bold"
)
ax.xaxis.set_major_formatter(mtick.PercentFormatter())
ax.set_xlim(0, 95)
ax.axvline(65.7, color="#d62728", lw=1.3, ls="--", alpha=0.75,
           label="Overall agentic rate (65.7%)")
ax.legend(fontsize=9, loc="lower right")

# Value labels
for bar, rate in zip(bars, reversed(rates)):
    ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
            f"{rate:.1f}%", va="center", fontsize=8.5)

ax.grid(axis="x", alpha=0.3)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
plt.tight_layout()
plt.savefig(FIG_DIR / "fig_framework_adoption.png", dpi=150, bbox_inches="tight")
plt.close()
print(f"Saved: {FIG_DIR / 'fig_framework_adoption.png'}")

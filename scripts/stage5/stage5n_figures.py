#!/usr/bin/env python3
"""
Figures for Stage 5n — Chinese Developer Agent Adoption
Four figures saved to bachelor_thesis/figures/stage5/

Fig 1: Top 15 countries — repo count + agentic rate
Fig 2: Tool mix comparison — China vs Global (all major tools)
Fig 3: Chinese tool adoption — which countries use them
Fig 4: Within Chinese agentic repos — tool category breakdown
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
DATA    = ROOT / "data" / "stage5"
GEO     = ROOT / "data" / "stage2" / "owner_locations_all.csv"
CORPUS  = ROOT / "data" / "stage3" / "corpus_detected_full.csv"
OUT_DIR = ROOT / "bachelor_thesis" / "figures" / "stage5"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BLUE   = "#1f77b4"
ORANGE = "#ff7f0e"
GREEN  = "#2ca02c"
RED    = "#d62728"
GRAY   = "#aaaaaa"
PURPLE = "#9467bd"
GOLD   = "#c9a800"
TEAL   = "#17becf"
PINK   = "#e377c2"

CHINESE_TOOLS = ["Trae / MarsCode", "Qwen Code", "Kimi Code"]
WESTERN_TOOLS = ["Claude Code", "Cursor", "GitHub Copilot", "OpenAI Codex",
                 "Gemini CLI", "Amp", "OpenCode", "Kiro", "Aider", "Windsurf",
                 "Cline / Roo Code", "Roo Code", "Devin", "Replit", "Junie",
                 "Amazon Q", "CodeRabbit", "PR-Agent", "Sourcery", "Sweep",
                 "Codeium", "Continue", "Augment Code", "Goose"]

# ── Load & merge data ─────────────────────────────────────────────────────────
geo    = pd.read_csv(GEO)
corpus = pd.read_csv(CORPUS)
df     = corpus.merge(geo[["owner_login", "inferred_country"]],
                      on="owner_login", how="left")

valid   = df[df["inferred_country"].notna() & (df["inferred_country"] != "not_specified")]
china_a = df[(df["inferred_country"] == "China") & (df["adoption_label"] == "agentic")]
global_a = df[df["adoption_label"] == "agentic"]
global_rate = (df["adoption_label"] == "agentic").mean() * 100

# ── Figure 1: Top 15 countries — repo count + agentic rate ───────────────────

top15_names = valid["inferred_country"].value_counts().head(15).index.tolist()

countries, totals, agentic_ns, non_agentic_ns, agentic_rates = [], [], [], [], []
for country in top15_names:
    sub   = valid[valid["inferred_country"] == country]
    n_tot = len(sub)
    n_ag  = (sub["adoption_label"] == "agentic").sum()
    countries.append(country)
    totals.append(n_tot)
    agentic_ns.append(n_ag)
    non_agentic_ns.append(n_tot - n_ag)
    agentic_rates.append(n_ag / n_tot * 100)

# Sort by total repos descending (China first)
order = np.argsort(totals)[::-1]
countries    = [countries[i]     for i in order]
agentic_ns   = [agentic_ns[i]    for i in order]
non_agentic_ns = [non_agentic_ns[i] for i in order]
agentic_rates  = [agentic_rates[i]  for i in order]
totals         = [agentic_ns[i] + non_agentic_ns[i] for i in range(len(countries))]

y_pos = np.arange(len(countries))

fig, ax = plt.subplots(figsize=(10, 6.5))

# Bars: stacked agentic (blue) + non-agentic (gray)
bar_ag  = ax.barh(y_pos, agentic_ns,   color=BLUE, height=0.65, label="Agentic")
bar_non = ax.barh(y_pos, non_agentic_ns, left=agentic_ns,
                  color=GRAY, height=0.65, alpha=0.45, label="Non-agentic")

# Highlight China in a warmer color
china_idx = countries.index("China")
ax.barh(china_idx, agentic_ns[china_idx],   color=RED,  height=0.65)
ax.barh(china_idx, non_agentic_ns[china_idx], left=agentic_ns[china_idx],
        color="#f4b8b8", height=0.65)

# Annotate agentic % at end of each bar
for i, (tot, rate) in enumerate(zip(totals, agentic_rates)):
    ax.text(tot + 30, i, f"{rate:.0f}%",
            va="center", ha="left", fontsize=8.5,
            color=RED if i == china_idx else "#444444",
            fontweight="bold" if i == china_idx else "normal")

ax.set_yticks(y_pos)
ax.set_yticklabels(countries, fontsize=10)
ax.set_xlabel("Number of Repositories", fontsize=11)
ax.set_title("Top 15 Countries by GitHub Corpus Size\n"
             "— bars split by adoption label; % = agentic rate —",
             fontsize=12, fontweight="bold")

# Baseline line
ax.axvline(0, color="black", linewidth=0.5)

legend_patches = [
    mpatches.Patch(color=RED,  label="China — agentic"),
    mpatches.Patch(color=BLUE, label="Other countries — agentic"),
    mpatches.Patch(color=GRAY, alpha=0.6, label="Non-agentic"),
]
ax.legend(handles=legend_patches, loc="lower right", fontsize=9)
ax.spines[["top", "right"]].set_visible(False)
ax.set_xlim(0, max(totals) * 1.12)

plt.tight_layout()
fig.savefig(OUT_DIR / "fig_5n_top15_countries.png", dpi=300, bbox_inches="tight")
fig.savefig(OUT_DIR / "fig_5n_top15_countries.pdf", bbox_inches="tight")
plt.close()
print("Saved fig_5n_top15_countries")


# ── Figure 2: Tool mix — China vs Global (grouped horizontal bars) ────────────

tools_labels = [
    ("Claude Code",      BLUE),
    ("Generic",          GRAY),
    ("OpenAI Codex",     ORANGE),
    ("Cursor",           PURPLE),
    ("GitHub Copilot",   GREEN),
    ("Gemini CLI",       TEAL),
    ("Trae / MarsCode",  RED),
    ("Qwen Code",        PINK),
    ("Kimi Code",        GOLD),
]

tool_names  = [t for t, _ in tools_labels]
tool_colors = [c for _, c in tools_labels]

china_pcts  = []
global_pcts = []
for tool in tool_names:
    china_pcts.append(
        china_a["agents_found"].apply(
            lambda s, t=tool: t in str(s) if pd.notna(s) else False
        ).mean() * 100
    )
    global_pcts.append(
        global_a["agents_found"].apply(
            lambda s, t=tool: t in str(s) if pd.notna(s) else False
        ).mean() * 100
    )

n_tools = len(tool_names)
y       = np.arange(n_tools)
h       = 0.38

fig, ax = plt.subplots(figsize=(10, 6))

bars_g = ax.barh(y + h/2, global_pcts, height=h, color=GRAY,    alpha=0.75, label="Global average")
bars_c = ax.barh(y - h/2, china_pcts,  height=h, color="#c0392b", alpha=0.85, label="China")

# Value labels
for bar, val in zip(bars_g, global_pcts):
    if val > 0.5:
        ax.text(bar.get_width() + 0.4, bar.get_y() + bar.get_height()/2,
                f"{val:.1f}%", va="center", fontsize=8, color="#555555")
for bar, val in zip(bars_c, china_pcts):
    if val > 0.5:
        ax.text(bar.get_width() + 0.4, bar.get_y() + bar.get_height()/2,
                f"{val:.1f}%", va="center", fontsize=8, color="#c0392b", fontweight="bold")

# Mark Chinese tools with a flag
for i, tool in enumerate(tool_names):
    if tool in CHINESE_TOOLS:
        ax.text(-1.5, i, "[CN]", va="center", ha="right", fontsize=8,
                color=RED, fontweight="bold")

ax.set_yticks(y)
ax.set_yticklabels(tool_names, fontsize=10)
ax.set_xlabel("% of agentic repositories using this tool", fontsize=11)
ax.set_title(
    f"AI Agent Tool Mix — China vs Global\n"
    f"(China: n={len(china_a):,} agentic repos  |  Global: n={len(global_a):,})",
    fontsize=12, fontweight="bold"
)
ax.legend(fontsize=10, loc="lower right")
ax.spines[["top", "right"]].set_visible(False)
ax.set_xlim(-3, max(max(china_pcts), max(global_pcts)) * 1.18)

# Annotation box: the paradox
ax.text(0.98, 0.98,
        "Despite internet restrictions,\n"
        "Chinese devs on GitHub\n"
        "overwhelmingly use Western tools",
        transform=ax.transAxes, ha="right", va="top", fontsize=8.5,
        color="#333333",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fff3cd", edgecolor="#cccccc"))

plt.tight_layout()
fig.savefig(OUT_DIR / "fig_5n_tool_mix_china_vs_global.png", dpi=300, bbox_inches="tight")
fig.savefig(OUT_DIR / "fig_5n_tool_mix_china_vs_global.pdf", bbox_inches="tight")
plt.close()
print("Saved fig_5n_tool_mix_china_vs_global")


# ── Figure 3: Chinese tool (Trae + Qwen + Kimi) by country ───────────────────

tool_colors_cn = {
    "Trae / MarsCode": RED,
    "Qwen Code":       ORANGE,
    "Kimi Code":       GOLD,
}

# Collect per-country counts for each Chinese tool
country_tool_counts = {}
for tool in CHINESE_TOOLS:
    users = df[(df["adoption_label"] == "agentic") &
               df["agents_found"].apply(
                   lambda s, t=tool: t in str(s) if pd.notna(s) else False
               )]
    country_counts = users["inferred_country"].value_counts()
    country_counts = country_counts[country_counts.index != "not_specified"]
    for country, n in country_counts.items():
        if country not in country_tool_counts:
            country_tool_counts[country] = {"Trae / MarsCode": 0, "Qwen Code": 0, "Kimi Code": 0}
        country_tool_counts[country][tool] += n

# Sort by total Chinese tool usage
sorted_countries = sorted(country_tool_counts.items(),
                           key=lambda x: sum(x[1].values()), reverse=True)[:12]

cn_countries = [c for c, _ in sorted_countries]
cn_trae  = [d["Trae / MarsCode"] for _, d in sorted_countries]
cn_qwen  = [d["Qwen Code"]       for _, d in sorted_countries]
cn_kimi  = [d["Kimi Code"]       for _, d in sorted_countries]
cn_totals = [a + b + c for a, b, c in zip(cn_trae, cn_qwen, cn_kimi)]

y3 = np.arange(len(cn_countries))

fig, ax = plt.subplots(figsize=(9, 6))

b1 = ax.barh(y3, cn_trae, height=0.6, color=RED,    label="Trae / MarsCode (ByteDance)")
b2 = ax.barh(y3, cn_qwen,  height=0.6, left=cn_trae,
             color=ORANGE, label="Qwen Code (Alibaba)")
b3 = ax.barh(y3, cn_kimi,  height=0.6,
             left=[a+b for a, b in zip(cn_trae, cn_qwen)],
             color=GOLD,   label="Kimi Code (Moonshot AI)")

# Total label
for i, tot in enumerate(cn_totals):
    ax.text(tot + 0.2, i, str(tot), va="center", fontsize=9, fontweight="bold")

ax.set_yticks(y3)
ax.set_yticklabels(cn_countries, fontsize=10)
ax.set_xlabel("Number of agentic repositories", fontsize=11)
ax.set_title("Chinese-Made AI Agent Adoption by Country\n"
             "(Trae/MarsCode + Qwen Code + Kimi Code)",
             fontsize=12, fontweight="bold")
ax.legend(fontsize=9.5, loc="lower right")
ax.spines[["top", "right"]].set_visible(False)
ax.set_xlim(0, max(cn_totals) * 1.18)

# Note
ax.text(0.98, 0.04,
        "China accounts for 57% of Trae/MarsCode usage",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=8.5,
        color="#555555", style="italic")

plt.tight_layout()
fig.savefig(OUT_DIR / "fig_5n_chinese_tools_by_country.png", dpi=300, bbox_inches="tight")
fig.savefig(OUT_DIR / "fig_5n_chinese_tools_by_country.pdf", bbox_inches="tight")
plt.close()
print("Saved fig_5n_chinese_tools_by_country")


# ── Figure 4: Tool category breakdown — Chinese repos vs Global ───────────────

def get_category(s):
    if pd.isna(s) or s == "":
        return "none"
    has_cn  = any(t in s for t in CHINESE_TOOLS)
    has_w   = any(t in s for t in WESTERN_TOOLS)
    has_gen = "Generic" in s
    if has_cn and has_w:
        return "Chinese + Western"
    if has_cn:
        return "Chinese tool only"
    if has_w:
        return "Western tool only"
    if has_gen:
        return "Generic only"
    return "Other"

china_a_copy  = china_a.copy()
global_a_copy = global_a.copy()
china_a_copy["cat"]  = china_a_copy["agents_found"].apply(get_category)
global_a_copy["cat"] = global_a_copy["agents_found"].apply(get_category)

cat_order = ["Western tool only", "Generic only", "Chinese tool only",
             "Chinese + Western", "Other"]
cat_colors = [BLUE, GRAY, RED, ORANGE, "#cccccc"]

china_cats  = china_a_copy["cat"].value_counts().reindex(cat_order, fill_value=0)
global_cats = global_a_copy["cat"].value_counts().reindex(cat_order, fill_value=0)

china_pct_cats  = china_cats  / len(china_a_copy)  * 100
global_pct_cats = global_cats / len(global_a_copy) * 100

x  = np.arange(len(cat_order))
w  = 0.35

fig, ax = plt.subplots(figsize=(10, 5.5))

bars_g2 = ax.bar(x - w/2, global_pct_cats.values, width=w,
                  color=GRAY, alpha=0.8, label="Global", edgecolor="white")
bars_c2 = ax.bar(x + w/2, china_pct_cats.values,  width=w,
                  color=RED,  alpha=0.85, label="China", edgecolor="white")

for bar, val in zip(bars_g2, global_pct_cats.values):
    if val > 0.5:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.4,
                f"{val:.1f}%", ha="center", fontsize=8.5, color="#444444")

for bar, val in zip(bars_c2, china_pct_cats.values):
    if val > 0.5:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.4,
                f"{val:.1f}%", ha="center", fontsize=8.5, color="#c0392b", fontweight="bold")

ax.set_xticks(x)
ax.set_xticklabels(cat_order, fontsize=10)
ax.set_ylabel("% of agentic repositories", fontsize=11)
ax.set_title(
    "Agent Tool Category — China vs Global\n"
    f"(China n={len(china_a_copy):,}  |  Global n={len(global_a_copy):,} agentic repos)",
    fontsize=12, fontweight="bold"
)
ax.legend(fontsize=10)
ax.spines[["top", "right"]].set_visible(False)
ax.set_ylim(0, max(china_pct_cats.max(), global_pct_cats.max()) * 1.22)

# Key insight box
cn_cn_pct = china_pct_cats.get("Chinese tool only", 0) + china_pct_cats.get("Chinese + Western", 0)
ax.text(0.98, 0.97,
        f"Only {cn_cn_pct:.1f}% of Chinese agentic repos\n"
        f"use a Chinese-made tool",
        transform=ax.transAxes, ha="right", va="top", fontsize=9,
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fff3cd", edgecolor="#cccccc"))

plt.tight_layout()
fig.savefig(OUT_DIR / "fig_5n_tool_categories.png", dpi=300, bbox_inches="tight")
fig.savefig(OUT_DIR / "fig_5n_tool_categories.pdf", bbox_inches="tight")
plt.close()
print("Saved fig_5n_tool_categories")

print(f"\nAll figures saved to: {OUT_DIR}")
print(f"\nKey numbers:")
print(f"  China = #1 country: 6,764 repos")
print(f"  China agentic rate: {(china_a['agents_found'].notna()).sum() / len(china_a) * 100:.0f}% repos with agents")
cn_cn = china_a["agents_found"].apply(
    lambda s: any(t in str(s) for t in CHINESE_TOOLS) if pd.notna(s) else False
).mean() * 100
print(f"  Chinese tool usage in China: {cn_cn:.1f}%")
print(f"  Claude Code in China: {china_a['agents_found'].apply(lambda s: 'Claude Code' in str(s) if pd.notna(s) else False).mean()*100:.1f}%")

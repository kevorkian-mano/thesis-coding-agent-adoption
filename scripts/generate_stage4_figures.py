#!/usr/bin/env python3
"""
generate_stage4_figures.py
==========================
Regenerates all figures for results_summary.tex from the latest CSVs.
Saves everything to figures/ (project root).

Usage:
    python3 scripts/generate_stage4_figures.py
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from pathlib import Path
from collections import Counter
from statsmodels.stats.proportion import proportion_confint

ROOT    = Path(__file__).resolve().parents[1]
D4      = ROOT / "data" / "stage4"
D5      = ROOT / "data" / "stage5"
D3      = ROOT / "data" / "stage3"
FIG     = ROOT / "figures"
FIG.mkdir(exist_ok=True)

BLUE   = "#2563EB"
RED    = "#DC2626"
GREEN  = "#16A34A"
ORANGE = "#EA580C"
GRAY   = "#6B7280"

def save(fig, name):
    for ext in ("png", "pdf"):
        fig.savefig(FIG / f"{name}.{ext}", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: figures/{name}.png")

def wilson_ci(k, n):
    if n == 0: return 0.0, 0.0
    lo, hi = proportion_confint(k, n, alpha=0.05, method="wilson")
    return lo * 100, hi * 100


# ── 1. Pass contributions bar chart ───────────────────────────────────────────
def fig_pass_contributions():
    data = {
        "Pass 3a\n(config files)":   28397,
        "Pass 3b\n(commit trailers)": 11937,
        "Pass 3c\n(deep scan)":          70,
    }
    fig, ax = plt.subplots(figsize=(7, 4.5))
    colors = [BLUE, ORANGE, GREEN]
    bars = ax.bar(data.keys(), data.values(), color=colors, edgecolor="white", width=0.55, zorder=3)
    for bar, val in zip(bars, data.values()):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 200,
                f"{val:,}", ha="center", fontsize=11, fontweight="bold")
    ax.set_ylabel("New Agentic Repos Detected", fontsize=11)
    ax.set_title("Stage 3 — Agentic Detections per Pass", fontsize=13, fontweight="bold")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.set_ylim(0, 33000)
    ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.text(0.98, 0.95, "Total: 40,404", transform=ax.transAxes,
            ha="right", va="top", fontsize=10, color=GRAY)
    plt.tight_layout()
    save(fig, "fig_pass_contributions")


# ── 2. Ecosystem stacked bar ──────────────────────────────────────────────────
def fig_ecosystem_stacked():
    df = pd.read_csv(D4 / "breakdown_ecosystem.csv")
    df = df[df["ecosystem_type"] != "unknown"].copy()
    df = df.sort_values("adoption_rate", ascending=True)
    eco   = df["ecosystem_type"].tolist()
    total = df["total_repos"].tolist()
    ag    = [a/t*100 for a, t in zip(df["agentic"].tolist(), total)]
    ai    = [a/t*100 for a, t in zip(df["ai_assisted"].tolist(), total)]
    no    = [a/t*100 for a, t in zip(df["none"].tolist(), total)]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(eco, ag, color="#2563EB", label="Agentic", zorder=3)
    ax.barh(eco, ai, left=ag, color="#F59E0B", label="AI-Assisted", zorder=3)
    ax.barh(eco, no, left=[a+b for a, b in zip(ag, ai)], color="#E5E7EB", label="None", zorder=3)
    ax.axvline(74.4, color="black", linestyle="--", linewidth=1.2, label="Global 74.4%", zorder=4)
    for i, (eco_name, t_repos) in enumerate(zip(eco, total)):
        ax.text(102, i, f"n={t_repos:,}", va="center", fontsize=7.5, color=GRAY)
    ax.set_xlabel("Share of repos (%)", fontsize=10)
    ax.set_title("AI Adoption by Package Ecosystem", fontsize=13, fontweight="bold")
    ax.xaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_xlim(0, 115)
    ax.legend(loc="lower right", fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", linestyle="--", alpha=0.3, zorder=0)
    plt.tight_layout()
    save(fig, "fig_ecosystem_stacked")


# ── 3. Tool distribution (top 15) ─────────────────────────────────────────────
def fig_tool_distribution():
    df = pd.read_csv(D4 / "coadoption_tool_counts.csv").head(15)
    df = df.sort_values("repos", ascending=True)
    fig, ax = plt.subplots(figsize=(8, 6))
    bars = ax.barh(df["tool"], df["repos"], color=BLUE, edgecolor="white", linewidth=0.5, zorder=3)
    max_v = df["repos"].max()
    for bar, (_, row) in zip(bars, df.iterrows()):
        ax.text(bar.get_width() + max_v * 0.01, bar.get_y() + bar.get_height()/2,
                f"{row['repos']:,}  ({row['pct_of_corpus']:.1f}%)",
                va="center", fontsize=8)
    ax.set_xlabel("Repositories", fontsize=10)
    ax.set_title("Top 15 Detected AI Coding Agents", fontsize=13, fontweight="bold")
    ax.set_xlim(0, max_v * 1.28)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", linestyle="--", alpha=0.35, zorder=0)
    plt.tight_layout()
    save(fig, "fig_tool_distribution")


# ── 4. Tool loyalty (single vs multi) ─────────────────────────────────────────
def fig_tool_loyalty():
    df = pd.read_csv(D4 / "coadoption_per_repo.csv").head(5)
    # Keep rows with n_tools 1–5
    df = df[df["n_tools"] <= 5].copy()
    labels = [f"{n} tool{'s' if n>1 else ''}" for n in df["n_tools"]]
    pcts   = df["pct_of_adopters"].tolist()
    colors = [BLUE] + [ORANGE] * (len(labels) - 1)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5))

    # Left: stacked bar
    adopted = df["repos"].sum()
    cum = 0
    for i, (label, repos, color) in enumerate(zip(labels, df["repos"].tolist(), colors)):
        ax1.bar(0, repos/adopted*100, bottom=cum, color=color, edgecolor="white",
                label=label, width=0.5, zorder=3)
        mid = cum + repos/adopted*100/2
        if repos/adopted*100 > 3:
            ax1.text(0, mid, f"{repos/adopted*100:.1f}%", ha="center", va="center",
                     fontsize=9, fontweight="bold", color="white" if i == 0 else "black")
        cum += repos/adopted*100
    ax1.set_xlim(-0.6, 0.6)
    ax1.set_ylim(0, 102)
    ax1.set_xticks([])
    ax1.set_ylabel("% of Adopters", fontsize=10)
    ax1.set_title("Tool Count per Adopter", fontsize=11, fontweight="bold")
    ax1.legend(loc="lower center", fontsize=8, ncol=2)
    ax1.spines[["top", "right"]].set_visible(False)

    # Right: horizontal bars showing top tool pairs
    pairs = pd.read_csv(D4 / "coadoption_tool_pairs.csv").head(8)
    pair_labels = [f"{r['tool_a']}\n+ {r['tool_b']}" for _, r in pairs.iterrows()][::-1]
    pair_vals   = pairs["repos"].tolist()[::-1]
    ax2.barh(pair_labels, pair_vals, color=ORANGE, edgecolor="white", linewidth=0.4, zorder=3)
    max_pv = max(pair_vals)
    for i, v in enumerate(pair_vals):
        ax2.text(v + max_pv*0.01, i, f"{v:,}", va="center", fontsize=8)
    ax2.set_xlabel("Repositories", fontsize=10)
    ax2.set_title("Top Co-occurring Tool Pairs", fontsize=11, fontweight="bold")
    ax2.set_xlim(0, max_pv * 1.2)
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.grid(axis="x", linestyle="--", alpha=0.35, zorder=0)

    fig.suptitle("Tool Loyalty & Co-adoption", fontsize=13, fontweight="bold")
    plt.tight_layout()
    save(fig, "fig_tool_loyalty")


# ── 5. Top 10 / Bottom 10 countries ───────────────────────────────────────────
def fig_top_bottom_countries():
    df  = pd.read_csv(D4 / "country_adoption.csv")
    top = df.head(10).copy()
    bot = df.tail(10).copy()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.5))

    for ax, data, title, color in [
        (ax1, top, "Top 10 Countries", GREEN),
        (ax2, bot, "Bottom 10 Countries", RED),
    ]:
        data = data.sort_values("adoption_rate")
        ctry = data["country"].tolist()
        rate = data["adoption_rate"].tolist()
        ci_lo = data["ci_lower"].tolist()
        ci_hi = data["ci_upper"].tolist()
        err_lo = [r - lo for r, lo in zip(rate, ci_lo)]
        err_hi = [hi - r  for r, hi in zip(rate, ci_hi)]
        ax.barh(ctry, rate, color=color, edgecolor="white", zorder=3, alpha=0.85)
        ax.errorbar(rate, ctry, xerr=[err_lo, err_hi],
                    fmt="none", color="#333", capsize=3, linewidth=1, zorder=4)
        ax.axvline(74.4, color="black", linestyle="--", linewidth=1.1, alpha=0.6, label="Global 74.4%")
        ax.set_xlabel("Adoption Rate (%)", fontsize=10)
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xlim(0, 110)
        ax.xaxis.set_major_formatter(mtick.PercentFormatter())
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x", linestyle="--", alpha=0.35, zorder=0)
        ax.legend(fontsize=8)
        for i, (r, row) in enumerate(zip(rate, data.itertuples())):
            ax.text(r + 1.5, i, f"{row.total_repos:,}", va="center", fontsize=7.5, color=GRAY)

    fig.suptitle("Country Adoption Rates (95% Wilson CI)", fontsize=13, fontweight="bold")
    plt.tight_layout()
    save(fig, "fig_top_bottom_countries")


# ── 6. All-country bar chart (replaces choropleth) ─────────────────────────────
def fig_choropleth():
    df = pd.read_csv(D4 / "country_adoption.csv").sort_values("adoption_rate", ascending=True)
    # Color by adoption level
    colors = [GREEN if r >= 74.4 else (ORANGE if r >= 55 else RED)
              for r in df["adoption_rate"]]
    fig, ax = plt.subplots(figsize=(12, max(10, len(df) * 0.28)))
    ax.barh(df["country"], df["adoption_rate"], color=colors, edgecolor="white",
            linewidth=0.3, zorder=3)
    ax.axvline(74.4, color="black", linestyle="--", linewidth=1.2, label="Global 74.4%")
    ax.set_xlabel("Adoption Rate (%)", fontsize=10)
    ax.set_title("AI Adoption Rate — All 66 Countries (≥30 repos)", fontsize=13, fontweight="bold")
    ax.xaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_xlim(0, 108)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", linestyle="--", alpha=0.3, zorder=0)
    ax.legend(fontsize=9)
    ax.tick_params(axis="y", labelsize=7.5)
    plt.tight_layout()
    save(fig, "fig_choropleth")


# ── 7. Size analysis grouped bar ──────────────────────────────────────────────
def fig_size_grouped_bar():
    df = pd.read_csv(D4 / "size_comparison.csv")
    approaches = {
        "A_stars":    "A: Stars",
        "B_commits":  "B: Commits",
        "C_langbytes":"C: Code volume",
    }
    strata  = ["small", "medium", "large"]
    x       = np.arange(len(strata))
    width   = 0.25
    colors  = [BLUE, ORANGE, GREEN]
    fig, ax = plt.subplots(figsize=(8, 5))

    for i, (key, label) in enumerate(approaches.items()):
        sub    = df[df["approach"] == key].set_index("stratum")
        rates  = [sub.loc[s, "adoption_rate"] for s in strata]
        ci_lo  = [sub.loc[s, "ci_lower"] for s in strata]
        ci_hi  = [sub.loc[s, "ci_upper"] for s in strata]
        err_lo = [r - lo for r, lo in zip(rates, ci_lo)]
        err_hi = [hi - r  for r, hi in zip(rates, ci_hi)]
        offset = (i - 1) * width
        bars   = ax.bar(x + offset, rates, width * 0.9, color=colors[i],
                        label=label, edgecolor="white", zorder=3)
        ax.errorbar(x + offset, rates, yerr=[err_lo, err_hi],
                    fmt="none", color="#333", capsize=3, linewidth=1, zorder=4)
        for bar, rate in zip(bars, rates):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                    f"{rate:.0f}%", ha="center", va="bottom", fontsize=8)

    ax.axhline(74.4, color="gray", linestyle="--", linewidth=1, alpha=0.6, label="Global 74.4%")
    ax.set_xticks(x)
    ax.set_xticklabels(["Small", "Medium", "Large"], fontsize=11)
    ax.set_ylabel("Adoption Rate (%)", fontsize=11)
    ax.set_title("AI Adoption Rate by Repository Size\n(Three Operationalisations)", fontsize=13, fontweight="bold")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_ylim(0, 100)
    ax.legend(fontsize=9, loc="upper left")
    ax.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    save(fig, "fig_size_grouped_bar")


# ── 8. MENA sub-region bar chart ──────────────────────────────────────────────
def fig_mena_bar():
    df = pd.read_csv(D4 / "mena" / "mena_subregion.csv")
    df = df.sort_values("adoption_rate", ascending=True)
    regions = df["subregion"].tolist()
    rates   = df["adoption_rate"].tolist()
    ci_lo   = df["ci_lower"].tolist()
    ci_hi   = df["ci_upper"].tolist()
    err_lo  = [r - lo for r, lo in zip(rates, ci_lo)]
    err_hi  = [hi - r  for r, hi in zip(rates, ci_hi)]

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    colors = [GREEN if r >= 65.85 else RED for r in rates]
    ax.barh(regions, rates, color=colors, edgecolor="white", linewidth=0.5, zorder=3, alpha=0.85)
    ax.errorbar(rates, regions, xerr=[err_lo, err_hi],
                fmt="none", color="#333", capsize=4, linewidth=1.2, zorder=4)
    ax.axvline(65.85, color=ORANGE, linestyle="--", linewidth=1.3, label="MENA 65.9%")
    ax.axvline(74.4,  color="black", linestyle=":",  linewidth=1.1, label="Global 74.4%")
    for i, (rate, row) in enumerate(zip(rates, df.itertuples())):
        ax.text(rate + 1, i, f"{row.total_repos:,} repos", va="center", fontsize=8.5, color=GRAY)
    ax.set_xlabel("Adoption Rate (%)", fontsize=10)
    ax.set_title("MENA Sub-region Adoption Rates (95% Wilson CI)", fontsize=12, fontweight="bold")
    ax.set_xlim(0, 110)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter())
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", linestyle="--", alpha=0.35, zorder=0)
    ax.legend(fontsize=9)
    plt.tight_layout()
    save(fig, "fig_mena_bar")


# ── 9. Country bubble chart ────────────────────────────────────────────────────
def fig_country_bubble():
    df = pd.read_csv(D4 / "country_adoption.csv")
    sizes = np.sqrt(df["total_repos"]) * 6
    colors = [GREEN if r >= 74.4 else (ORANGE if r >= 55 else RED) for r in df["adoption_rate"]]

    fig, ax = plt.subplots(figsize=(10, 6))
    sc = ax.scatter(df["total_repos"], df["adoption_rate"],
                    s=sizes, c=colors, alpha=0.65, edgecolors="white", linewidth=0.5, zorder=3)
    ax.axhline(74.4, color="black", linestyle="--", linewidth=1, alpha=0.6, label="Global 74.4%")

    # Label notable countries
    notable = ["United States", "China", "India", "South Korea", "Belgium",
               "Rwanda", "Egypt", "Bangladesh", "Germany", "Brazil"]
    for _, row in df.iterrows():
        if row["country"] in notable:
            ax.annotate(row["country"],
                        (row["total_repos"], row["adoption_rate"]),
                        textcoords="offset points", xytext=(4, 3), fontsize=7.5)

    ax.set_xscale("log")
    ax.set_xlabel("Repository Count (log scale)", fontsize=10)
    ax.set_ylabel("Adoption Rate (%)", fontsize=10)
    ax.set_title("Country Adoption Rate vs Repository Count\n(bubble size ∝ √repos)", fontsize=12, fontweight="bold")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(linestyle="--", alpha=0.3, zorder=0)
    ax.legend(fontsize=9)
    plt.tight_layout()
    save(fig, "fig_country_bubble")


# ── 10. Framework adoption bar ─────────────────────────────────────────────────
def fig_framework_adoption():
    # Try to compute from repo_frameworks.csv + corpus
    fw_path = D5 / "repo_frameworks.csv"
    corpus_path = D4 / "corpus_with_country.csv"
    if not fw_path.exists() or not corpus_path.exists():
        print("  Skipped fig_framework_adoption (missing framework data)")
        return

    fw     = pd.read_csv(fw_path, low_memory=False)
    corpus = pd.read_csv(corpus_path, low_memory=False, usecols=["full_name", "adoption_label"])
    merged = fw.merge(corpus, on="full_name", how="inner")

    rows = []
    for fw_name in ["React", "Next.js", "Express", "Electron", "Tauri", "Hono",
                    "Vue", "Astro", "React Native", "Fastify", "Expo", "Svelte",
                    "NestJS", "VitePress", "TanStack Start", "Capacitor", "Solid",
                    "SvelteKit", "tRPC", "Preact"]:
        mask  = merged["frameworks"].str.contains(fw_name, na=False, regex=False)
        sub   = merged[mask]
        if len(sub) == 0: continue
        agentic = (sub["adoption_label"] == "agentic").sum()
        rows.append({"framework": fw_name, "repos": len(sub),
                     "agentic_rate": agentic / len(sub) * 100})

    rdf = pd.DataFrame(rows).sort_values("agentic_rate", ascending=True)
    global_rate = (corpus["adoption_label"] == "agentic").sum() / len(corpus) * 100

    fig, ax = plt.subplots(figsize=(9, 7))
    colors  = [GREEN if r >= global_rate else RED for r in rdf["agentic_rate"]]
    bars    = ax.barh(rdf["framework"], rdf["agentic_rate"],
                      color=colors, edgecolor="white", linewidth=0.4, zorder=3, alpha=0.85)
    ax.axvline(global_rate, color="black", linestyle="--", linewidth=1.2,
               label=f"Global agentic {global_rate:.1f}%")
    max_v = rdf["agentic_rate"].max()
    for bar, (_, row) in zip(bars, rdf.iterrows()):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                f"{row['repos']:,}", va="center", fontsize=7.5, color=GRAY)
    ax.set_xlabel("Agentic Adoption Rate (%)", fontsize=10)
    ax.set_title("Agentic Adoption by JS/TS Framework\n(multi-label; repos counted in each applicable row)",
                 fontsize=12, fontweight="bold")
    ax.xaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_xlim(0, max_v + 10)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", linestyle="--", alpha=0.35, zorder=0)
    ax.legend(fontsize=9)
    plt.tight_layout()
    save(fig, "fig_framework_adoption")


# ── 11. Pricing by income group ───────────────────────────────────────────────
def fig_pricing_income():
    df = pd.read_csv(D4 / "pricing_income_groups.csv")
    order  = ["HIC", "UMIC", "LMIC", "LIC"]
    labels = {"HIC": "High Income", "UMIC": "Upper-Middle", "LMIC": "Lower-Middle", "LIC": "Low Income"}
    df     = df.set_index("income_group").loc[order].reset_index()
    names  = [labels[g] for g in df["income_group"]]
    adopt  = df["adoption_rate"].tolist()
    paid   = df["paid_pct"].tolist()
    free   = df["free_pct"].tolist()

    x = np.arange(len(names))
    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax2 = ax1.twinx()

    bars = ax1.bar(x - 0.15, adopt, 0.3, color=BLUE, label="Adoption rate", zorder=3)
    for bar, v in zip(bars, adopt):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                 f"{v:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")

    ax2.bar(x + 0.15, paid, 0.15, color=ORANGE, label="Paid tool %", zorder=3)
    ax2.bar(x + 0.3,  free, 0.15, color=GREEN,  label="Free tool %", zorder=3)

    ax1.set_xticks(x)
    ax1.set_xticklabels(names, fontsize=10)
    ax1.set_ylabel("Adoption Rate (%)", color=BLUE, fontsize=10)
    ax1.set_ylim(0, 95)
    ax1.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax2.set_ylabel("Tool Type Share (% of agentic repos)", fontsize=9)
    ax2.set_ylim(0, 95)
    ax2.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax1.spines[["top"]].set_visible(False)
    ax2.spines[["top"]].set_visible(False)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc="upper right")
    ax1.set_title("AI Adoption & Tool Pricing by World Bank Income Group", fontsize=12, fontweight="bold")
    ax1.grid(axis="y", linestyle="--", alpha=0.3, zorder=0)
    plt.tight_layout()
    save(fig, "fig_pricing_income")


# ══════════════════════════════════════════════════════════════════════════════
def main():
    print("Generating stage4 figures")
    print("=" * 45)
    fig_pass_contributions()
    fig_ecosystem_stacked()
    fig_tool_distribution()
    fig_tool_loyalty()
    fig_top_bottom_countries()
    fig_choropleth()
    fig_size_grouped_bar()
    fig_mena_bar()
    fig_country_bubble()
    fig_framework_adoption()
    fig_pricing_income()
    print(f"\nAll figures saved to: figures/")


if __name__ == "__main__":
    main()

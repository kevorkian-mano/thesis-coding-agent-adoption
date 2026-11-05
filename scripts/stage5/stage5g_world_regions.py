#!/usr/bin/env python3
"""
Stage 5g -- Worldwide Regional Adoption Analysis
=================================================
Replicates the full country-level analysis (adoption rate, stats, agent
breakdown) scoped to 10 macro-regions that together cover the entire corpus.
Middle East & North Africa is one of the 10 regions so results are directly
comparable to stage4e.

Macro-regions
-------------
  North America              USA, Canada, Mexico
  Latin America & Caribbean  Brazil, Argentina, Colombia, Chile, Peru, ...
  Western Europe             UK, Germany, France, Netherlands, ...
  Eastern Europe & C. Asia   Russia, Ukraine, Poland, Romania, ...
  Middle East & N. Africa    UAE, Saudi Arabia, Israel, Egypt, Turkey, ...
  Sub-Saharan Africa         Nigeria, Kenya, South Africa, Ghana, ...
  South Asia                 India, Pakistan, Bangladesh, Sri Lanka, ...
  East Asia                  China, Japan, South Korea, Taiwan, ...
  Southeast Asia             Vietnam, Philippines, Indonesia, Singapore, ...
  Oceania                    Australia, New Zealand

Analyses
--------
  1. Regional coverage     — repos, % of corpus, % of located repos
  2. Regional ranking      — adoption rate + Wilson 95% CI per region
  3. Statistical tests     — chi-squared across regions
                           — each region vs rest-of-world Fisher exact + BH FDR
  4. Agent breakdown       — top 5 agents per region as % of agentic repos
  5. Tool loyalty          — single-homing rate per region

Figures produced
----------------
  fig_world_regions_adoption.png  — horizontal bar chart (sorted by rate) with CI
  fig_world_regions_agents.png    — heatmap: region x agent (% of agentic repos)

Input
-----
  data/stage4/corpus_with_country.csv

Output
------
  data/stage5/world_regions.csv
  data/stage5/world_regions_agents.csv
  data/stage5/world_regions_pairwise.csv
  data/stage5/world_regions_report.txt
  figures/stage5/fig_world_regions_adoption.png/.pdf
  figures/stage5/fig_world_regions_agents.png/.pdf

Usage
-----
  python3 scripts/stage5/stage5g_world_regions.py
"""

import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from collections import Counter
from pathlib import Path
from scipy.stats import chi2_contingency, fisher_exact

ROOT        = Path(__file__).resolve().parents[2]
CORPUS_FILE = ROOT / "data" / "stage4" / "corpus_with_country.csv"
OUT_DIR     = ROOT / "data"  / "stage5"
FIG_DIR     = ROOT / "figures" / "stage5"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

MIN_REPOS = 30   # same threshold as global analysis
ALPHA     = 0.05
TOP_AGENTS = 8   # agents shown in heatmap

# ── World region definitions ───────────────────────────────────────────────────
REGIONS = {
    "North America": {
        "United States", "Canada", "Mexico",
    },
    "Latin America & Caribbean": {
        "Brazil", "Argentina", "Colombia", "Chile", "Peru", "Venezuela",
        "Ecuador", "Bolivia", "Uruguay", "Paraguay", "Costa Rica",
        "Guatemala", "Honduras", "Nicaragua", "El Salvador",
        "Dominican Republic", "Cuba", "Jamaica", "Panama", "Trinidad and Tobago",
    },
    "Western Europe": {
        "United Kingdom", "Germany", "France", "Netherlands", "Sweden",
        "Denmark", "Norway", "Finland", "Switzerland", "Austria",
        "Belgium", "Ireland", "Portugal", "Spain", "Italy",
        "Luxembourg", "Greece", "Czech Republic", "Slovakia", "Slovenia",
    },
    "Eastern Europe & Central Asia": {
        "Russia", "Ukraine", "Poland", "Romania", "Bulgaria", "Serbia",
        "Croatia", "Hungary", "Belarus", "Lithuania", "Latvia", "Estonia",
        "Moldova", "Georgia", "Armenia", "Azerbaijan",
        "Kazakhstan", "Uzbekistan", "Kyrgyzstan", "Tajikistan", "Turkmenistan",
    },
    "Middle East & North Africa": {
        "United Arab Emirates", "Saudi Arabia", "Kuwait", "Qatar",
        "Bahrain", "Oman", "Israel", "Jordan", "Lebanon", "Syria",
        "Iraq", "Egypt", "Morocco", "Algeria", "Tunisia", "Libya",
        "Turkey", "Iran", "Yemen", "Palestine",
    },
    "Sub-Saharan Africa": {
        "Nigeria", "Kenya", "South Africa", "Ghana", "Ethiopia",
        "Tanzania", "Rwanda", "Uganda", "Cameroon", "Senegal",
        "Côte d'Ivoire", "Zimbabwe", "Mozambique", "Zambia", "Sudan",
    },
    "South Asia": {
        "India", "Pakistan", "Bangladesh", "Sri Lanka", "Nepal",
        "Afghanistan", "Maldives",
    },
    "East Asia": {
        "China", "Japan", "South Korea", "Taiwan", "Hong Kong",
        "Mongolia", "Macau",
    },
    "Southeast Asia": {
        "Vietnam", "Philippines", "Indonesia", "Malaysia", "Thailand",
        "Singapore", "Myanmar", "Cambodia", "Laos", "Brunei",
    },
    "Oceania": {
        "Australia", "New Zealand", "Fiji", "Papua New Guinea",
    },
}

REGION_ORDER = [
    "North America",
    "Western Europe",
    "East Asia",
    "South Asia",
    "Southeast Asia",
    "Eastern Europe & Central Asia",
    "Middle East & North Africa",
    "Latin America & Caribbean",
    "Oceania",
    "Sub-Saharan Africa",
]

COUNTRY_TO_REGION = {
    country: region
    for region, countries in REGIONS.items()
    for country in countries
}


# ── helpers ───────────────────────────────────────────────────────────────────

def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p      = k / n
    denom  = 1 + z ** 2 / n
    centre = (p + z ** 2 / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def bh_correction(p_values: list) -> list:
    n = len(p_values)
    if n == 0:
        return []
    arr   = np.array(p_values, dtype=float)
    order = np.argsort(arr)
    ranks = np.empty(n)
    ranks[order] = np.arange(1, n + 1)
    adj   = np.minimum(1.0, arr * n / ranks)
    mono  = np.minimum.accumulate(adj[order[::-1]])[::-1]
    result = np.empty(n)
    result[order] = mono
    return result.tolist()


# ── figures ───────────────────────────────────────────────────────────────────

def plot_adoption_bar(reg_df: pd.DataFrame) -> None:
    """Horizontal bar chart of regional adoption rates with CI error bars."""
    df = reg_df.sort_values("adoption_rate", ascending=True)
    regions = df["region"].tolist()
    rates   = df["adoption_rate"].tolist()
    err_lo  = [r - lo for r, lo in zip(rates, df["ci_lower"])]
    err_hi  = [hi - r for r, hi in zip(rates, df["ci_upper"])]

    colors = ["#4878CF" if r != "Middle East & North Africa" else "#E8601C"
              for r in regions]

    fig, ax = plt.subplots(figsize=(9, 6))
    bars = ax.barh(regions, rates, xerr=[err_lo, err_hi],
                   color=colors, error_kw={"elinewidth": 1.2, "capsize": 3},
                   edgecolor="white", linewidth=0.6)

    for bar, rate in zip(bars, rates):
        ax.text(bar.get_width() + 0.4, bar.get_y() + bar.get_height() / 2,
                f"{rate:.1f}%", va="center", fontsize=8)

    ax.set_xlabel("Adoption rate (agentic + ai_assisted, %)", fontsize=9)
    ax.set_title("AI Coding Agent Adoption by World Region", fontsize=12, fontweight="bold")
    ax.set_xlim(0, max(rates) * 1.3)
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    ax.tick_params(axis="y", labelsize=8)

    plt.tight_layout()
    out = FIG_DIR / "fig_world_regions_adoption.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


def plot_agent_heatmap(agent_df: pd.DataFrame, reg_df: pd.DataFrame) -> None:
    """
    Heatmap: regions (rows) x top agents (columns).
    Cell value = % of agentic repos in that region using the agent.
    """
    if agent_df.empty:
        print("  Agent heatmap skipped (no agent data).")
        return

    # Pick top agents globally
    top_agents = (
        agent_df.groupby("agent")["repos"].sum()
        .sort_values(ascending=False)
        .head(TOP_AGENTS)
        .index.tolist()
    )

    # Pivot: region x agent -> pct_of_agentic
    sub = agent_df[agent_df["agent"].isin(top_agents)]
    pivot = sub.pivot_table(index="region", columns="agent",
                            values="pct_of_agentic", fill_value=0)
    # Order rows by adoption rate
    rate_order = reg_df.sort_values("adoption_rate", ascending=False)["region"].tolist()
    pivot = pivot.reindex([r for r in rate_order if r in pivot.index])
    pivot = pivot.reindex(columns=top_agents, fill_value=0)

    fig, ax = plt.subplots(figsize=(max(10, len(top_agents) * 1.1), 6))
    im = ax.imshow(pivot.values, aspect="auto", cmap="YlOrRd", vmin=0, vmax=100)

    ax.set_xticks(range(len(top_agents)))
    ax.set_xticklabels(top_agents, rotation=40, ha="right", fontsize=8)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)

    for r in range(len(pivot.index)):
        for c in range(len(top_agents)):
            val = pivot.values[r, c]
            if val > 0:
                txt_color = "white" if val > 60 else "black"
                ax.text(c, r, f"{val:.0f}%", ha="center", va="center",
                        fontsize=7, color=txt_color)

    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("% of agentic repos in region", fontsize=8)
    ax.set_title("Top Agent Usage by World Region (% of agentic repos)",
                 fontsize=11, fontweight="bold")

    plt.tight_layout()
    out = FIG_DIR / "fig_world_regions_agents.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    lines = []

    def log(s: str = ""):
        lines.append(s)
        print(s)

    log("Stage 5g -- Worldwide Regional Adoption Analysis")
    log("=" * 72)

    if not CORPUS_FILE.exists():
        raise SystemExit(f"Missing: {CORPUS_FILE}\nRun stage4a first.")

    corpus = pd.read_csv(CORPUS_FILE, low_memory=False)
    corpus["region"] = corpus["country"].map(COUNTRY_TO_REGION)

    n_total   = len(corpus)
    n_located = (corpus["country"] != "not_specified").sum()
    n_mapped  = corpus["region"].notna().sum()
    n_global_adopted = corpus["adoption_label"].isin(["agentic", "ai_assisted"]).sum()
    global_rate = n_global_adopted / n_total

    log()
    log(f"  Full corpus          : {n_total:,}")
    log(f"  Located repos        : {n_located:,}  ({n_located/n_total*100:.1f}%)")
    log(f"  Mapped to a region   : {n_mapped:,}  ({n_mapped/n_total*100:.1f}%)")
    log(f"  Global adoption rate : {global_rate*100:.2f}%")
    log()

    # ── 1. Build regional summary ─────────────────────────────────────────────
    reg_rows = []
    for region in REGION_ORDER:
        grp     = corpus[corpus["region"] == region]
        n       = len(grp)
        n_ag    = (grp["adoption_label"] == "agentic").sum()
        n_ai    = (grp["adoption_label"] == "ai_assisted").sum()
        n_adpt  = n_ag + n_ai
        n_none  = (grp["adoption_label"] == "none").sum()
        rate    = n_adpt / n if n else 0.0
        ag_rate = n_ag   / n if n else 0.0
        ci_lo, ci_hi = wilson_ci(n_adpt, n)

        # Countries in region present in corpus
        countries_found = sorted(grp["country"].unique().tolist())

        # Tool loyalty in this region (single-homing %)
        adopted_grp = grp[
            grp["adoption_label"].isin(["agentic", "ai_assisted"]) &
            grp["agents_found"].notna() &
            (grp["agents_found"].astype(str) != "")
        ].copy()
        adopted_grp["n_agents"] = adopted_grp["agents_found"].apply(
            lambda x: len([a for a in str(x).split("|") if a.strip()])
        )
        single_rate = (
            (adopted_grp["n_agents"] == 1).sum() / len(adopted_grp) * 100
            if len(adopted_grp) > 0 else 0.0
        )

        reg_rows.append({
            "region":           region,
            "total_repos":      n,
            "pct_corpus":       round(n / n_total * 100, 1),
            "agentic":          int(n_ag),
            "ai_assisted":      int(n_ai),
            "none":             int(n_none),
            "adopted":          int(n_adpt),
            "adoption_rate":    round(rate    * 100, 2),
            "agentic_rate":     round(ag_rate * 100, 2),
            "ci_lower":         round(ci_lo   * 100, 2),
            "ci_upper":         round(ci_hi   * 100, 2),
            "countries_in_corpus": len(countries_found),
            "single_homing_pct": round(single_rate, 1),
        })

    reg_df = pd.DataFrame(reg_rows)
    reg_df.to_csv(OUT_DIR / "world_regions.csv", index=False)
    log(f"  Saved: world_regions.csv")

    # ── 2. Print regional ranking ─────────────────────────────────────────────
    log()
    log("── Regional Adoption Ranking ─────────────────────────────────────────")
    ranked = reg_df.sort_values("adoption_rate", ascending=False).reset_index(drop=True)
    hdr = (f"  {'Rank':<4} {'Region':<34} {'Repos':>7} {'Adopted':>8} "
           f"{'Rate%':>7}  {'95% CI':>16}  {'Single%':>8}")
    log(hdr)
    log(f"  {'-' * 95}")
    for i, row in ranked.iterrows():
        ci = f"[{row['ci_lower']:.1f}, {row['ci_upper']:.1f}]"
        log(f"  {i+1:<4} {row['region']:<34} {row['total_repos']:>7,} "
            f"{row['adopted']:>8,} {row['adoption_rate']:>7.1f}%  "
            f"{ci:>16}  {row['single_homing_pct']:>7.1f}%")

    # ── 3. Statistical tests ───────────────────────────────────────────────────
    log()
    log("── Statistical Tests ─────────────────────────────────────────────────")

    # Chi-squared across all regions
    contingency = np.array([
        [int(r["adopted"]), int(r["total_repos"]) - int(r["adopted"])]
        for _, r in reg_df.iterrows()
        if r["total_repos"] > 0
    ])
    chi2, p_chi2, dof, _ = chi2_contingency(contingency)
    log()
    log(f"  Chi-squared: adoption rate across {len(reg_df)} world regions")
    log(f"    Chi2 = {chi2:.2f},  df = {dof},  p = {p_chi2:.4e}")
    log(f"    Decision: {'REJECT H0 — rates vary across regions' if p_chi2 < ALPHA else 'FAIL to reject H0'}")

    # Pairwise Fisher: each region vs rest-of-world + BH FDR
    log()
    log("  Pairwise Fisher (each region vs rest-of-world) + BH FDR:")
    total_adopted     = int(reg_df["adopted"].sum())
    total_not_adopted = int((reg_df["total_repos"] - reg_df["adopted"]).sum())

    p_raw_list    = []
    pairwise_rows = []
    for _, row in reg_df.iterrows():
        a_val = int(row["adopted"])
        b_val = int(row["total_repos"]) - a_val
        c_val = max(total_adopted     - a_val, 0)
        d_val = max(total_not_adopted - b_val, 0)
        _, p_f = fisher_exact([[a_val, b_val], [c_val, d_val]], alternative="two-sided")
        or_v   = (a_val * d_val) / (b_val * c_val) if b_val * c_val > 0 else float("nan")
        p_raw_list.append(p_f)
        pairwise_rows.append({
            "region":        row["region"],
            "total_repos":   int(row["total_repos"]),
            "adopted":       a_val,
            "adoption_rate": row["adoption_rate"],
            "ci_lower":      row["ci_lower"],
            "ci_upper":      row["ci_upper"],
            "odds_ratio":    round(or_v, 3),
            "fisher_p_raw":  round(p_f, 6),
        })

    p_adj = bh_correction(p_raw_list)
    hdr3 = (f"  {'Region':<34} {'Rate%':>6}  {'95% CI':>16}  "
            f"{'OR':>6}  {'p_raw':>10}  {'p_adj':>10}  {'Sig':>4}")
    log(hdr3)
    log(f"  {'-' * 92}")
    for i, row in enumerate(pairwise_rows):
        row["fisher_p_adj"] = round(p_adj[i], 6)
        row["significant"]  = p_adj[i] < ALPHA
        ci  = f"[{row['ci_lower']:.1f}, {row['ci_upper']:.1f}]"
        sig = "*" if row["significant"] else ""
        log(f"  {row['region']:<34} {row['adoption_rate']:>6.1f}%  {ci:>16}  "
            f"{row['odds_ratio']:>6.3f}  {row['fisher_p_raw']:>10.3e}  "
            f"{row['fisher_p_adj']:>10.4f}  {sig:>4}")

    pairwise_df = (pd.DataFrame(pairwise_rows)
                   .sort_values("adoption_rate", ascending=False)
                   .reset_index(drop=True))
    pairwise_df.to_csv(OUT_DIR / "world_regions_pairwise.csv", index=False)
    n_sig = pairwise_df["significant"].sum()
    log(f"\n  Significant (BH p < {ALPHA}): {n_sig} / {len(pairwise_df)} regions")
    log(f"  Saved: world_regions_pairwise.csv")

    # ── 4. Agent breakdown per region ─────────────────────────────────────────
    log()
    log("── Agent Breakdown per Region ────────────────────────────────────────")

    agent_rows = []
    for region in REGION_ORDER:
        grp = corpus[corpus["region"] == region]
        n_ag_region = (grp["adoption_label"] == "agentic").sum()
        agentic_grp = grp[
            (grp["adoption_label"] == "agentic") &
            grp["agents_found"].notna() &
            (grp["agents_found"].astype(str).str.strip() != "")
        ]
        agent_counts: Counter = Counter()
        for agents_str in agentic_grp["agents_found"].astype(str):
            for a in agents_str.split("|"):
                a = a.strip()
                if a:
                    agent_counts[a] += 1

        for agent, count in agent_counts.most_common():
            agent_rows.append({
                "region":          region,
                "agent":           agent,
                "repos":           count,
                "pct_of_agentic":  round(count / n_ag_region * 100, 1) if n_ag_region else 0.0,
            })

    agent_df = pd.DataFrame(agent_rows)
    agent_df.to_csv(OUT_DIR / "world_regions_agents.csv", index=False)
    log(f"  Saved: world_regions_agents.csv")

    log()
    log(f"  {'Region':<34} {'Top agent':<30} {'% of agentic':>13}")
    log(f"  {'-' * 80}")
    for region in REGION_ORDER:
        sub = agent_df[agent_df["region"] == region]
        if sub.empty:
            continue
        top = sub.iloc[0]
        log(f"  {region:<34} {top['agent']:<30} {top['pct_of_agentic']:>12.1f}%")

    # ── 5. Generate figures ────────────────────────────────────────────────────
    log()
    log("── Generating figures ────────────────────────────────────────────────")
    plot_adoption_bar(reg_df)
    plot_agent_heatmap(agent_df, reg_df)

    # ── Save full text report ──────────────────────────────────────────────────
    report_path = OUT_DIR / "world_regions_report.txt"
    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    log(f"  Saved: world_regions_report.txt")
    log()
    log("Stage 5g complete.")


if __name__ == "__main__":
    main()

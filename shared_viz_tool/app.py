#!/usr/bin/env python3
"""
app.py  —  AI Coding Agent Adoption Cross-Stack Dashboard
==========================================================
Loads all *.csv files from shared_viz_tool/data/.
Each CSV must include a 'stack' column and 'adoption_label' column.

Run:
    streamlit run shared_viz_tool/app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from pathlib import Path
from collections import Counter
from statsmodels.stats.proportion import proportion_confint

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# ── Stack colour palette ───────────────────────────────────────────────────────
STACK_COLORS = {
    "TypeScript/JavaScript": "#F0A500",
    "Python":                "#3776AB",
    "Java":                  "#ED8B00",
    "Rust":                  "#CE422B",
    "C#":                    "#178600",
    "C++":                   "#00599C",
}

def stack_color(name: str) -> str:
    return STACK_COLORS.get(name, "#888888")

# ── Income group mapping (World Bank 2024) ────────────────────────────────────
INCOME_MAP = {
    "United States": "HIC", "United Kingdom": "HIC", "Germany": "HIC",
    "France": "HIC", "Japan": "HIC", "South Korea": "HIC", "Australia": "HIC",
    "Canada": "HIC", "Israel": "HIC", "United Arab Emirates": "HIC",
    "UAE": "HIC", "Sweden": "HIC", "Switzerland": "HIC", "Netherlands": "HIC",
    "Denmark": "HIC", "Singapore": "HIC", "Taiwan": "HIC", "Belgium": "HIC",
    "Norway": "HIC", "Austria": "HIC", "Finland": "HIC", "New Zealand": "HIC",
    "Ireland": "HIC", "Hong Kong": "HIC", "Italy": "HIC", "Spain": "HIC",
    "Portugal": "HIC", "Czech Republic": "HIC", "Saudi Arabia": "HIC",
    "Greece": "HIC", "Cyprus": "HIC", "Estonia": "HIC", "Latvia": "HIC",
    "Lithuania": "HIC", "Slovakia": "HIC", "Slovenia": "HIC", "Luxembourg": "HIC",
    "China": "UMIC", "Brazil": "UMIC", "Turkey": "UMIC", "Russia": "UMIC",
    "Mexico": "UMIC", "Argentina": "UMIC", "Thailand": "UMIC",
    "Malaysia": "UMIC", "Colombia": "UMIC", "Ukraine": "UMIC",
    "South Africa": "UMIC", "Poland": "UMIC", "Romania": "UMIC",
    "Bulgaria": "UMIC", "Serbia": "UMIC", "Chile": "UMIC", "Egypt": "UMIC",
    "Georgia": "UMIC", "Kazakhstan": "UMIC", "Uzbekistan": "UMIC",
    "Algeria": "UMIC", "Tunisia": "UMIC", "Hungary": "UMIC", "Peru": "UMIC",
    "Venezuela": "UMIC", "Ecuador": "UMIC", "Azerbaijan": "UMIC",
    "Bosnia and Herzegovina": "UMIC", "Albania": "UMIC", "Jordan": "UMIC",
    "Armenia": "UMIC", "Croatia": "UMIC",
    "India": "LMIC", "Vietnam": "LMIC", "Philippines": "LMIC",
    "Indonesia": "LMIC", "Bangladesh": "LMIC", "Pakistan": "LMIC",
    "Nigeria": "LMIC", "Ghana": "LMIC", "Kenya": "LMIC", "Morocco": "LMIC",
    "Sri Lanka": "LMIC", "Nepal": "LMIC", "Ethiopia": "LMIC", "Iran": "LMIC",
    "Bolivia": "LMIC", "Honduras": "LMIC", "Nicaragua": "LMIC",
    "Senegal": "LMIC", "Tanzania": "LMIC", "Cameroon": "LMIC",
    "Palestine": "LMIC",
    "Rwanda": "LIC", "Uganda": "LIC", "Mali": "LIC", "Niger": "LIC",
    "Mozambique": "LIC", "Madagascar": "LIC",
}
INCOME_ORDER  = ["HIC", "UMIC", "LMIC", "LIC"]
INCOME_LABELS = {
    "HIC":  "High Income",
    "UMIC": "Upper-Middle",
    "LMIC": "Lower-Middle",
    "LIC":  "Low Income",
}

# ── MENA countries ────────────────────────────────────────────────────────────
MENA_COUNTRIES = {
    "Algeria", "Bahrain", "Egypt", "Iran", "Iraq", "Israel", "Jordan",
    "Kuwait", "Lebanon", "Libya", "Morocco", "Oman", "Palestine",
    "Qatar", "Saudi Arabia", "Syria", "Tunisia", "Turkey",
    "United Arab Emirates", "UAE", "Yemen",
}

# ── Tool pricing classification ───────────────────────────────────────────────
PAID_TOOLS = {
    "claude code", "claude code / generic", "junie", "devin", "roo code",
    "codegen", "factory", "greptile", "ellipsis", "amp", "openai codex",
}
FREE_TOOLS = {
    "github copilot", "cursor", "windsurf", "codeium", "aider", "continue",
    "gemini cli", "opencode", "openhands", "swe-agent", "amazon q", "kiro",
    "coderabbit", "sweep", "jules", "replit", "deepsource", "pr-agent", "sourcery",
}

def classify_tool_pricing(name: str) -> str:
    n = name.strip().lower()
    if n in PAID_TOOLS:
        return "paid"
    if n in FREE_TOOLS:
        return "free"
    return "ambiguous"

# Columns that may contain filterable package/ecosystem info
FILTERABLE_COLS = ["ecosystem_type", "primary_language", "corpus_source", "size_stratum", "topics"]

# ── Wilson 95% CI ──────────────────────────────────────────────────────────────
def wilson_ci(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    lo, hi = proportion_confint(k, n, alpha=0.05, method="wilson")
    return lo * 100, hi * 100

# ── Helpers ────────────────────────────────────────────────────────────────────
def parse_agents(s) -> list[str]:
    if pd.isna(s) or str(s).strip() == "":
        return []
    return [a.strip() for a in str(s).split("|") if a.strip()]

def is_adopted(label) -> bool:
    return label in ("agentic", "ai_assisted")

def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived columns: country alias, income_group, code_kb, is_mena."""
    if "inferred_country" in df.columns and "country" not in df.columns:
        df = df.rename(columns={"inferred_country": "country"})
    if "country" in df.columns:
        if "income_group" not in df.columns:
            df["income_group"] = df["country"].map(INCOME_MAP)
        if "is_mena" not in df.columns:
            df["is_mena"] = df["country"].isin(MENA_COUNTRIES)
    if "lang_bytes" in df.columns and "code_kb" not in df.columns:
        df["code_kb"] = df["lang_bytes"] / 1024
    return df

# ── Data loading ───────────────────────────────────────────────────────────────
@st.cache_data
def load_all_stacks() -> pd.DataFrame:
    frames = []
    for f in sorted(DATA_DIR.glob("*.csv")):
        try:
            df = pd.read_csv(f, low_memory=False)
        except Exception:
            continue
        if "stack" not in df.columns or "adoption_label" not in df.columns:
            continue
        frames.append(_enrich(df))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)

# ── Summary table ──────────────────────────────────────────────────────────────
def compute_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for stack, grp in df.groupby("stack"):
        n       = len(grp)
        agentic = (grp["adoption_label"] == "agentic").sum()
        ai_asst = (grp["adoption_label"] == "ai_assisted").sum()
        adopted = agentic + ai_asst
        none_n  = (grp["adoption_label"] == "none").sum()
        rate    = adopted / n * 100 if n > 0 else 0.0
        ci_lo, ci_hi = wilson_ci(adopted, n)
        rows.append({
            "Stack":       stack,
            "Repos":       n,
            "Agentic":     int(agentic),
            "AI-Assisted": int(ai_asst),
            "Adopted":     int(adopted),
            "None":        int(none_n),
            "Rate %":      round(rate, 2),
            "CI Low":      round(ci_lo, 2),
            "CI High":     round(ci_hi, 2),
        })
    return pd.DataFrame(rows).sort_values("Rate %", ascending=False).reset_index(drop=True)

# ── Top agents per stack ───────────────────────────────────────────────────────
def top_agents_per_stack(df: pd.DataFrame, top_n: int = 10) -> dict:
    result = {}
    for stack, grp in df.groupby("stack"):
        counts = Counter()
        for agents in grp["agents_found"].dropna():
            for a in parse_agents(agents):
                counts[a] += 1
        result[stack] = counts.most_common(top_n)
    return result

# ── Country stats per stack ────────────────────────────────────────────────────
def country_stats(df: pd.DataFrame, min_repos: int = 10) -> dict:
    result = {}
    if "country" not in df.columns:
        return result
    for stack, grp in df.groupby("stack"):
        rows = []
        for country, cgrp in grp.groupby("country"):
            if pd.isna(country) or str(country).lower() in ("not_specified", "unknown", "", "nan"):
                continue
            n = len(cgrp)
            if n < min_repos:
                continue
            adopted = cgrp["adoption_label"].apply(is_adopted).sum()
            rate    = adopted / n * 100
            ci_lo, ci_hi = wilson_ci(adopted, n)
            rows.append({"country": country, "total": n, "adopted": int(adopted),
                         "rate": round(rate, 2), "ci_lo": round(ci_lo, 2),
                         "ci_hi": round(ci_hi, 2)})
        result[stack] = pd.DataFrame(rows).sort_values("rate", ascending=False).reset_index(drop=True)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# CHART FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def fig_adoption_bars(summary: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(max(5, len(summary) * 1.4), 5))
    stacks = summary["Stack"].tolist()
    rates  = summary["Rate %"].tolist()
    ci_lo  = summary["CI Low"].tolist()
    ci_hi  = summary["CI High"].tolist()
    colors = [stack_color(s) for s in stacks]
    err_lo = [r - lo for r, lo in zip(rates, ci_lo)]
    err_hi = [hi - r  for r, hi in zip(rates, ci_hi)]
    bars = ax.bar(stacks, rates, color=colors, edgecolor="white", linewidth=0.8, zorder=3)
    ax.errorbar(stacks, rates, yerr=[err_lo, err_hi],
                fmt="none", color="#333333", capsize=6, linewidth=1.8, zorder=4)
    for bar, rate in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.8,
                f"{rate:.1f}%", ha="center", va="bottom", fontsize=11, fontweight="bold")
    ax.axhline(50, color="gray", linestyle="--", linewidth=0.9, alpha=0.5, zorder=2)
    ax.set_ylabel("AI Adoption Rate (%)", fontsize=11)
    ax.set_title("AI Coding Agent Adoption by Language Stack\n(with 95% Wilson CI)",
                 fontsize=13, fontweight="bold")
    ax.set_ylim(0, 105)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    return fig


def fig_adoption_split(summary: pd.DataFrame, df: pd.DataFrame) -> plt.Figure:
    stacks  = summary["Stack"].tolist()
    total   = summary["Repos"].tolist()
    agentic = summary["Agentic"].tolist()
    ai_asst = summary["AI-Assisted"].tolist()
    none_n  = summary["None"].tolist()
    ag_pct  = [a / t * 100 for a, t in zip(agentic, total)]
    aa_pct  = [a / t * 100 for a, t in zip(ai_asst, total)]
    no_pct  = [a / t * 100 for a, t in zip(none_n, total)]
    x     = np.arange(len(stacks))
    width = 0.55
    fig, ax = plt.subplots(figsize=(max(5, len(stacks) * 1.4), 5))
    b1 = ax.bar(x, ag_pct, width, label="Agentic",      color="#2196F3", zorder=3)
    ax.bar(x, aa_pct, width, bottom=ag_pct, label="AI-Assisted", color="#81D4FA", zorder=3)
    ax.bar(x, no_pct, width, bottom=[a + b for a, b in zip(ag_pct, aa_pct)],
           label="No AI", color="#E0E0E0", zorder=3)
    for bar, ag, aa in zip(b1, ag_pct, aa_pct):
        total_pct = ag + aa
        ax.text(bar.get_x() + bar.get_width() / 2, total_pct + 1.5,
                f"{total_pct:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(stacks, fontsize=10)
    ax.set_ylabel("Share of repos (%)", fontsize=11)
    ax.set_title("Adoption Label Breakdown by Stack", fontsize=13, fontweight="bold")
    ax.set_ylim(0, 110)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.legend(fontsize=9, loc="upper right")
    ax.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    return fig


def fig_top_agents(agents_dict: dict, top_n: int = 8) -> plt.Figure | None:
    stacks = list(agents_dict.keys())
    if not stacks:
        return None
    n_stacks = len(stacks)
    fig, axes = plt.subplots(1, n_stacks, figsize=(5 * n_stacks, 5), squeeze=False)
    for i, stack in enumerate(stacks):
        ax    = axes[0][i]
        items = agents_dict[stack][:top_n]
        if not items:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            ax.set_title(stack, fontsize=10, fontweight="bold")
            continue
        agents = [a for a, _ in reversed(items)]
        counts = [c for _, c in reversed(items)]
        color  = stack_color(stack)
        ax.barh(agents, counts, color=color, edgecolor="white", linewidth=0.5, zorder=3)
        max_c = max(counts)
        for j, (agent, count) in enumerate(zip(agents, counts)):
            ax.text(count + max_c * 0.02, j, f"{count:,}", va="center", fontsize=8)
        ax.set_title(stack, fontsize=10, fontweight="bold")
        ax.set_xlabel("Repositories", fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x", linestyle="--", alpha=0.35)
        ax.set_xlim(0, max_c * 1.18)
    fig.suptitle(f"Top {top_n} Detected Agents per Stack", fontsize=13, fontweight="bold")
    plt.tight_layout()
    return fig


def fig_tool_loyalty(df: pd.DataFrame) -> plt.Figure | None:
    agentic = df[df["adoption_label"] == "agentic"]
    if agentic.empty or "agents_found" not in agentic.columns:
        return None
    stacks = sorted(agentic["stack"].unique())
    rows   = []
    for stack in stacks:
        grp    = agentic[agentic["stack"] == stack]
        counts = grp["agents_found"].apply(lambda x: len(parse_agents(x)))
        total  = len(grp)
        single = (counts == 1).sum()
        multi  = (counts  > 1).sum()
        rows.append({"stack": stack, "Single": single / total * 100, "Multi": multi / total * 100})
    rdf = pd.DataFrame(rows)
    x   = np.arange(len(stacks))
    fig, ax = plt.subplots(figsize=(max(5, len(stacks) * 1.4), 5))
    ax.bar(x, rdf["Single"], label="Single-tool", color="#4C72B0", zorder=3)
    ax.bar(x, rdf["Multi"],  bottom=rdf["Single"], label="Multi-tool", color="#DD8452", zorder=3)
    for i, row in rdf.iterrows():
        ax.text(i, row["Single"] + 1.0, f"{row['Single']:.1f}%",
                ha="center", va="bottom", fontsize=9, color="#4C72B0", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(rdf["stack"].tolist(), fontsize=10)
    ax.set_ylabel("% of Agentic Repos", fontsize=11)
    ax.set_title("Tool Loyalty — Single vs Multi-Tool Repos", fontsize=13, fontweight="bold")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_ylim(0, 110)
    ax.legend(fontsize=9)
    ax.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    return fig


def fig_top_bottom_countries(country_dict: dict, top_n: int = 10) -> plt.Figure | None:
    stacks = [s for s, d in country_dict.items() if not d.empty]
    if not stacks:
        return None
    n_stacks = len(stacks)
    fig, axes = plt.subplots(2, n_stacks, figsize=(5 * n_stacks, 10), squeeze=False)
    for i, stack in enumerate(stacks):
        data  = country_dict[stack]
        color = stack_color(stack)
        for row_idx, (subset, title_sfx) in enumerate([
            (data.head(top_n), f"Top {top_n} Countries"),
            (data.tail(top_n).iloc[::-1], f"Bottom {top_n} Countries"),
        ]):
            ax = axes[row_idx][i]
            if subset.empty:
                ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
                continue
            countries = subset["country"].tolist()[::-1]
            rates     = subset["rate"].tolist()[::-1]
            ci_lo_v   = subset["ci_lo"].tolist()[::-1]
            ci_hi_v   = subset["ci_hi"].tolist()[::-1]
            err_lo    = [r - lo for r, lo in zip(rates, ci_lo_v)]
            err_hi    = [hi - r  for r, hi in zip(rates, ci_hi_v)]
            ax.barh(countries, rates, color=color, edgecolor="white",
                    linewidth=0.5, zorder=3, alpha=0.85 if row_idx == 0 else 0.5)
            ax.errorbar(rates, countries, xerr=[err_lo, err_hi],
                        fmt="none", color="#333333", capsize=3, linewidth=1, zorder=4)
            ax.set_title(f"{stack}\n{title_sfx}", fontsize=10, fontweight="bold")
            ax.set_xlabel("Adoption Rate (%)", fontsize=9)
            ax.set_xlim(0, 110)
            ax.xaxis.set_major_formatter(mtick.PercentFormatter())
            ax.spines[["top", "right"]].set_visible(False)
            ax.grid(axis="x", linestyle="--", alpha=0.35)
    fig.suptitle(f"Top & Bottom {top_n} Countries by Adoption Rate",
                 fontsize=13, fontweight="bold", y=1.01)
    plt.tight_layout()
    return fig


def fig_income_group(df: pd.DataFrame) -> plt.Figure | None:
    if "income_group" not in df.columns:
        return None
    sub = df[df["income_group"].notna()].copy()
    if sub.empty:
        return None
    stacks   = sorted(sub["stack"].unique())
    n_stacks = len(stacks)
    width    = 0.8 / max(n_stacks, 1)
    x        = np.arange(len(INCOME_ORDER))
    fig, ax  = plt.subplots(figsize=(max(7, n_stacks * 2), 5))
    for i, stack in enumerate(stacks):
        sdf  = sub[sub["stack"] == stack]
        vals = []
        for grp_code in INCOME_ORDER:
            g = sdf[sdf["income_group"] == grp_code]
            n = len(g)
            if n == 0:
                vals.append(0)
                continue
            adopted = g["adoption_label"].apply(is_adopted).sum()
            vals.append(adopted / n * 100)
        offset = (i - n_stacks / 2 + 0.5) * width
        bars   = ax.bar(x + offset, vals, width * 0.9,
                        label=stack, color=stack_color(stack),
                        edgecolor="white", linewidth=0.5, zorder=3)
        for bar, val in zip(bars, vals):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.8,
                        f"{val:.1f}%", ha="center", va="bottom", fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels([INCOME_LABELS[c] for c in INCOME_ORDER], fontsize=10)
    ax.set_ylabel("Adoption Rate (%)", fontsize=11)
    ax.set_title("AI Adoption by Country Income Group (World Bank 2024)",
                 fontsize=13, fontweight="bold")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_ylim(0, 100)
    ax.legend(fontsize=9)
    ax.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    return fig


def fig_pricing_income(df: pd.DataFrame) -> plt.Figure | None:
    """Paid vs Free tool share by income group, with adoption rate overlay."""
    if "income_group" not in df.columns or "agents_found" not in df.columns:
        return None
    agentic = df[(df["adoption_label"] == "agentic") & df["income_group"].notna()].copy()
    if agentic.empty:
        return None

    def repo_pricing(agents_str):
        tools = parse_agents(agents_str)
        if not tools:
            return "none"
        classes = [classify_tool_pricing(t) for t in tools]
        if "paid" in classes:
            return "paid"
        if "free" in classes:
            return "free"
        return "ambiguous"

    agentic["pricing"] = agentic["agents_found"].apply(repo_pricing)

    group_rows = []
    for ig in INCOME_ORDER:
        grp_all = df[df["income_group"] == ig]
        grp_ag  = agentic[agentic["income_group"] == ig]
        n_total = len(grp_all)
        n_ag    = len(grp_ag)
        if n_total == 0:
            continue
        adopted    = grp_all["adoption_label"].apply(is_adopted).sum()
        adopt_rate = adopted / n_total * 100
        n_paid     = (grp_ag["pricing"] == "paid").sum()
        n_free     = (grp_ag["pricing"] == "free").sum()
        n_ambig    = (grp_ag["pricing"] == "ambiguous").sum()
        group_rows.append({
            "ig":         ig,
            "label":      INCOME_LABELS[ig],
            "adopt_rate": adopt_rate,
            "paid_pct":   n_paid  / n_ag * 100 if n_ag else 0,
            "free_pct":   n_free  / n_ag * 100 if n_ag else 0,
            "ambig_pct":  n_ambig / n_ag * 100 if n_ag else 0,
            "n_ag":       n_ag,
            "n_total":    n_total,
        })

    if not group_rows:
        return None

    gdf    = pd.DataFrame(group_rows)
    labels = gdf["label"].tolist()
    x      = np.arange(len(labels))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Left: adoption rate by income group
    colors_ig = ["#1565C0", "#1976D2", "#42A5F5", "#90CAF9"][:len(gdf)]
    bars = ax1.bar(x, gdf["adopt_rate"], color=colors_ig, edgecolor="white",
                   linewidth=0.6, zorder=3)
    for bar, val in zip(bars, gdf["adopt_rate"]):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8,
                 f"{val:.1f}%", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=10)
    ax1.set_ylabel("Adoption Rate (%)", fontsize=11)
    ax1.set_title("Adoption Rate by Income Group", fontsize=12, fontweight="bold")
    ax1.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax1.set_ylim(0, 100)
    ax1.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)
    ax1.spines[["top", "right"]].set_visible(False)

    # Right: paid / free / ambiguous tool share by income group
    paid_bars = ax2.bar(x, gdf["paid_pct"],  label="Paid-dominant", color="#E53935",
                        zorder=3, edgecolor="white")
    free_bars = ax2.bar(x, gdf["free_pct"],  bottom=gdf["paid_pct"],
                        label="Free-accessible", color="#43A047", zorder=3, edgecolor="white")
    ax2.bar(x, gdf["ambig_pct"],
            bottom=gdf["paid_pct"] + gdf["free_pct"],
            label="Ambiguous", color="#9E9E9E", zorder=3, edgecolor="white")

    for i, row in gdf.iterrows():
        if row["paid_pct"] > 3:
            ax2.text(i, row["paid_pct"] / 2, f"{row['paid_pct']:.0f}%",
                     ha="center", va="center", fontsize=8, color="white", fontweight="bold")
        if row["free_pct"] > 3:
            ax2.text(i, row["paid_pct"] + row["free_pct"] / 2, f"{row['free_pct']:.0f}%",
                     ha="center", va="center", fontsize=8, color="white", fontweight="bold")

    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, fontsize=10)
    ax2.set_ylabel("Share of Agentic Repos (%)", fontsize=11)
    ax2.set_title("Paid vs Free Tool Usage by Income Group", fontsize=12, fontweight="bold")
    ax2.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax2.set_ylim(0, 110)
    ax2.legend(fontsize=9, loc="upper right")
    ax2.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)
    ax2.spines[["top", "right"]].set_visible(False)

    fig.suptitle("AI Adoption & Tool Pricing by Country Income Group",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    return fig


def fig_mena_vs_rest(df: pd.DataFrame) -> plt.Figure | None:
    """MENA vs non-MENA adoption rate per stack."""
    if "is_mena" not in df.columns:
        return None
    sub = df[df["country"].notna() &
             ~df["country"].isin(["not_specified", "unknown", ""])].copy()
    if sub.empty:
        return None

    stacks = sorted(sub["stack"].unique())
    mena_rates, rest_rates = [], []
    for stack in stacks:
        sg = sub[sub["stack"] == stack]
        for flag, bucket in [(True, mena_rates), (False, rest_rates)]:
            g = sg[sg["is_mena"] == flag]
            n = len(g)
            if n == 0:
                bucket.append(0)
            else:
                adopted = g["adoption_label"].apply(is_adopted).sum()
                bucket.append(adopted / n * 100)

    x     = np.arange(len(stacks))
    width = 0.35
    fig, ax = plt.subplots(figsize=(max(6, len(stacks) * 1.6), 5))
    bars_m = ax.bar(x - width / 2, mena_rates, width, label="MENA", color="#FF7043",
                    edgecolor="white", linewidth=0.6, zorder=3)
    bars_r = ax.bar(x + width / 2, rest_rates,  width, label="Non-MENA", color="#42A5F5",
                    edgecolor="white", linewidth=0.6, zorder=3)
    for bar, val in list(zip(bars_m, mena_rates)) + list(zip(bars_r, rest_rates)):
        if val > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8,
                    f"{val:.1f}%", ha="center", va="bottom", fontsize=8, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(stacks, fontsize=10)
    ax.set_ylabel("Adoption Rate (%)", fontsize=11)
    ax.set_title("AI Adoption — MENA vs Non-MENA by Stack", fontsize=13, fontweight="bold")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_ylim(0, 105)
    ax.legend(fontsize=10)
    ax.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    return fig


def fig_mena_countries(df: pd.DataFrame, min_repos: int = 5) -> plt.Figure | None:
    """Adoption rate for each MENA country (all selected stacks combined)."""
    if "country" not in df.columns:
        return None
    mena_df = df[df["country"].isin(MENA_COUNTRIES)].copy()
    if mena_df.empty:
        return None

    rows = []
    for country, grp in mena_df.groupby("country"):
        n = len(grp)
        if n < min_repos:
            continue
        adopted = grp["adoption_label"].apply(is_adopted).sum()
        rate    = adopted / n * 100
        ci_lo, ci_hi = wilson_ci(adopted, n)
        rows.append({"country": country, "total": n, "rate": rate,
                     "ci_lo": ci_lo, "ci_hi": ci_hi})
    if not rows:
        return None

    cdf  = pd.DataFrame(rows).sort_values("rate", ascending=True)
    countries = cdf["country"].tolist()
    rates     = cdf["rate"].tolist()
    err_lo    = [r - lo for r, lo in zip(cdf["rate"], cdf["ci_lo"])]
    err_hi    = [hi - r  for r, hi in zip(cdf["rate"], cdf["ci_hi"])]
    totals    = cdf["total"].tolist()

    fig, ax = plt.subplots(figsize=(8, max(4, len(countries) * 0.45)))
    bars = ax.barh(countries, rates, color="#FF7043", edgecolor="white",
                   linewidth=0.5, zorder=3, alpha=0.85)
    ax.errorbar(rates, countries, xerr=[err_lo, err_hi],
                fmt="none", color="#333333", capsize=3, linewidth=1, zorder=4)
    for bar, rate, n in zip(bars, rates, totals):
        ax.text(bar.get_width() + 1.5, bar.get_y() + bar.get_height() / 2,
                f"{rate:.1f}%  (n={n:,})", va="center", fontsize=8)
    ax.set_xlabel("Adoption Rate (%)", fontsize=11)
    ax.set_title("AI Adoption by MENA Country\n(with 95% Wilson CI)",
                 fontsize=12, fontweight="bold")
    ax.set_xlim(0, 115)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter())
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    plt.tight_layout()
    return fig


def fig_time_series(df: pd.DataFrame) -> plt.Figure | None:
    if "created_at" not in df.columns:
        return None
    df = df.copy()
    df["month"] = pd.to_datetime(df["created_at"], errors="coerce").dt.to_period("M")
    rows = []
    for (stack, month), grp in df.groupby(["stack", "month"]):
        if pd.isna(month):
            continue
        n = len(grp)
        if n < 5:
            continue
        adopted = grp["adoption_label"].apply(is_adopted).sum()
        rows.append({"stack": stack, "month": str(month), "rate": adopted / n * 100})
    if not rows:
        return None
    mdf = pd.DataFrame(rows).sort_values("month")
    fig, ax = plt.subplots(figsize=(12, 5))
    for stack, grp in mdf.groupby("stack"):
        ax.plot(grp["month"], grp["rate"], marker="o", markersize=3,
                label=stack, color=stack_color(stack), linewidth=2)
    ticks = sorted(mdf["month"].unique())
    step  = max(1, len(ticks) // 12)
    ax.set_xticks(ticks[::step])
    ax.tick_params(axis="x", rotation=45)
    ax.set_ylabel("Adoption Rate (%)", fontsize=11)
    ax.set_title("AI Adoption Rate by Repository Creation Month",
                 fontsize=13, fontweight="bold")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(linestyle="--", alpha=0.35)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    return fig


def fig_size_three_metrics(df: pd.DataFrame) -> plt.Figure | None:
    metrics = []
    if "stars"   in df.columns: metrics.append(("stars",   "Stars"))
    if "commits" in df.columns: metrics.append(("commits", "Commits"))
    if "code_kb" in df.columns: metrics.append(("code_kb", "Code Size (KB)"))
    if not metrics:
        return None
    stacks    = sorted(df["stack"].unique())
    tertiles  = ["Small", "Medium", "Large"]
    n_metrics = len(metrics)
    fig, axes = plt.subplots(1, n_metrics, figsize=(5 * n_metrics, 5), squeeze=False)
    for col_i, (col, col_label) in enumerate(metrics):
        ax    = axes[0][col_i]
        x     = np.arange(len(tertiles))
        width = 0.8 / max(len(stacks), 1)
        for i, stack in enumerate(stacks):
            grp = df[df["stack"] == stack].copy()
            try:
                grp["tertile"] = pd.qcut(grp[col], q=3, labels=tertiles, duplicates="drop")
            except Exception:
                continue
            vals = []
            for t in tertiles:
                tgrp = grp[grp["tertile"] == t]
                n    = len(tgrp)
                if n == 0:
                    vals.append(0)
                    continue
                adopted = tgrp["adoption_label"].apply(is_adopted).sum()
                vals.append(adopted / n * 100)
            offset = (i - len(stacks) / 2 + 0.5) * width
            ax.bar(x + offset, vals, width * 0.9, label=stack,
                   color=stack_color(stack), edgecolor="white", linewidth=0.5, zorder=3)
        ax.set_xticks(x)
        ax.set_xticklabels(tertiles, fontsize=10)
        ax.set_ylabel("Adoption Rate (%)", fontsize=10)
        ax.set_title(col_label, fontsize=11, fontweight="bold")
        ax.yaxis.set_major_formatter(mtick.PercentFormatter())
        ax.set_ylim(0, 100)
        if col_i == 0:
            ax.legend(fontsize=8)
        ax.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Adoption Rate by Repository Size (Tertile)",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    return fig


def fig_size_by_category(df: pd.DataFrame) -> plt.Figure | None:
    metrics = []
    if "commits" in df.columns: metrics.append(("commits", "Median Commits"))
    if "code_kb" in df.columns: metrics.append(("code_kb", "Median Code Size (KB)"))
    if "stars"   in df.columns: metrics.append(("stars",   "Median Stars"))
    if not metrics:
        return None
    cats       = ["none", "ai_assisted", "agentic"]
    cat_labels = ["No AI", "AI-Assisted", "Agentic"]
    stacks     = sorted(df["stack"].unique())
    fig, axes  = plt.subplots(1, len(metrics), figsize=(5 * len(metrics), 5), squeeze=False)
    for col_i, (col, col_label) in enumerate(metrics):
        ax    = axes[0][col_i]
        x     = np.arange(len(cats))
        width = 0.8 / max(len(stacks), 1)
        for i, stack in enumerate(stacks):
            grp  = df[df["stack"] == stack]
            vals = []
            for cat in cats:
                cgrp = grp[grp["adoption_label"] == cat]
                vals.append(cgrp[col].median() if len(cgrp) > 0 else 0)
            offset = (i - len(stacks) / 2 + 0.5) * width
            ax.bar(x + offset, vals, width * 0.9, label=stack,
                   color=stack_color(stack), edgecolor="white", linewidth=0.5, zorder=3)
        ax.set_xticks(x)
        ax.set_xticklabels(cat_labels, fontsize=10)
        ax.set_ylabel(col_label, fontsize=10)
        ax.set_title(col_label, fontsize=11, fontweight="bold")
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
        if col_i == 0:
            ax.legend(fontsize=8)
        ax.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Median Repository Size by Adoption Category",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    return fig


def fig_agent_diversity(df: pd.DataFrame) -> plt.Figure | None:
    agentic = df[df["adoption_label"] == "agentic"]
    if agentic.empty:
        return None
    stacks = agentic["stack"].unique()
    rows   = []
    for stack in stacks:
        grp    = agentic[agentic["stack"] == stack]
        counts = grp["agents_found"].apply(lambda x: len(parse_agents(x)))
        single = (counts == 1).sum()
        multi  = (counts  > 1).sum()
        total  = len(grp)
        rows.append({"stack": stack, "Single": single / total * 100, "Multi": multi / total * 100})
    rdf     = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(max(5, len(stacks) * 1.4), 5))
    x       = np.arange(len(rdf))
    ax.bar(x, rdf["Single"], label="Single-agent", color="#4C72B0", zorder=3)
    ax.bar(x, rdf["Multi"],  bottom=rdf["Single"], label="Multi-agent", color="#DD8452", zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels(rdf["stack"].tolist(), fontsize=10)
    ax.set_ylabel("% of Agentic Repos", fontsize=11)
    ax.set_title("Agent Diversity — Single vs Multi-Agent Repos",
                 fontsize=13, fontweight="bold")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_ylim(0, 105)
    ax.legend(fontsize=9)
    ax.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# STREAMLIT LAYOUT
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="AI Agent Adoption — Cross-Stack",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 AI Coding Agent Adoption — Cross-Stack Dashboard")
st.caption(
    "Loads all `*.csv` files from `shared_viz_tool/data/`. "
    "Upload extra stacks via the sidebar. Each CSV must have `stack` and `adoption_label` columns."
)

df_all = load_all_stacks()

# ── Sidebar: file upload ───────────────────────────────────────────────────────
st.sidebar.header("Filters")

with st.sidebar.expander("Upload Additional Stack CSV", expanded=False):
    uploaded_file = st.file_uploader(
        "Drop a stack CSV here", type=["csv"],
        help="Must have 'stack' and 'adoption_label' columns.",
        label_visibility="collapsed",
    )
    if uploaded_file is not None:
        try:
            df_up = pd.read_csv(uploaded_file, low_memory=False)
            if "stack" in df_up.columns and "adoption_label" in df_up.columns:
                df_up  = _enrich(df_up)
                df_all = pd.concat([df_all, df_up], ignore_index=True)
                stack_name = df_up["stack"].iloc[0] if len(df_up) > 0 else "unknown"
                st.success(f"Loaded {len(df_up):,} rows — stack: {stack_name}")
            else:
                st.error("CSV must have 'stack' and 'adoption_label' columns.")
        except Exception as e:
            st.error(f"Error reading CSV: {e}")

if df_all.empty:
    st.error(
        "No corpus files found in `shared_viz_tool/data/`.\n\n"
        "Run `python3 shared_viz_tool/prepare_submission.py` or upload a CSV above."
    )
    st.stop()

# ── Sidebar: stack + date filters ─────────────────────────────────────────────
all_stacks      = sorted(df_all["stack"].unique().tolist())
selected_stacks = st.sidebar.multiselect("Show stacks", all_stacks, default=all_stacks)

if "created_at" in df_all.columns:
    df_all["_month"] = pd.to_datetime(df_all["created_at"], errors="coerce").dt.to_period("M")
    valid_months = sorted(df_all["_month"].dropna().unique())
    if len(valid_months) >= 2:
        month_strs   = [str(m) for m in valid_months]
        date_range   = st.sidebar.select_slider(
            "Creation date range", options=month_strs,
            value=(month_strs[0], month_strs[-1]),
        )
        date_start, date_end = date_range
    else:
        date_start, date_end = None, None
else:
    date_start, date_end = None, None

adoption_filter = st.sidebar.radio(
    "Adoption scope",
    ["All adopted (agentic + AI-assisted)", "Agentic only"],
    index=0,
)

min_country = st.sidebar.slider("Min repos per country", 5, 50, 10)

# ── Sidebar: package / ecosystem filters ──────────────────────────────────────
eco_filters: dict[str, list] = {}
detected_eco_cols = [c for c in FILTERABLE_COLS if c in df_all.columns]
if detected_eco_cols:
    with st.sidebar.expander("Package / Ecosystem Filters", expanded=False):
        st.caption("Rows without a value for a column are always kept (other stacks).")
        for col in detected_eco_cols:
            all_vals = sorted(df_all[col].dropna().unique().tolist())
            if 2 <= len(all_vals) <= 50:
                label = col.replace("_", " ").title()
                sel   = st.multiselect(label, all_vals, default=all_vals, key=f"eco_{col}")
                eco_filters[col] = sel

if not selected_stacks:
    st.warning("Select at least one stack from the sidebar.")
    st.stop()

# ── Apply all filters ──────────────────────────────────────────────────────────
df = df_all[df_all["stack"].isin(selected_stacks)].copy()

if date_start and date_end:
    df = df[(df["_month"].astype(str) >= date_start) &
            (df["_month"].astype(str) <= date_end)]

for col, sel_vals in eco_filters.items():
    if col in df.columns and sel_vals:
        # Keep rows where column is NaN (stack doesn't have this field) OR value is selected
        df = df[df[col].isna() | df[col].isin(sel_vals)]

if adoption_filter == "Agentic only":
    def is_adopted(label):  # noqa: F811
        return label == "agentic"
else:
    def is_adopted(label):  # noqa: F811
        return label in ("agentic", "ai_assisted")

# ── Top metrics ────────────────────────────────────────────────────────────────
adopted_mask = df["adoption_label"].apply(is_adopted)
overall_rate = adopted_mask.sum() / len(df) * 100 if len(df) > 0 else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric("Stacks loaded",    len(selected_stacks))
m2.metric("Total repos",      f"{len(df):,}")
m3.metric("Adopted repos",    f"{adopted_mask.sum():,}")
m4.metric("Overall adoption", f"{overall_rate:.1f}%")

st.divider()

# ── Precompute ─────────────────────────────────────────────────────────────────
summary     = compute_summary(df)
agents_dict = top_agents_per_stack(df, top_n=10)
cntry_dict  = country_stats(df, min_repos=min_country)

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Overview", "Agents", "Geography", "Time Series", "Size", "Diversity"
])

# ── Tab 1: Overview ────────────────────────────────────────────────────────────
with tab1:
    st.subheader("Adoption Rate Comparison (95% Wilson CI)")
    fig = fig_adoption_bars(summary)
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

    st.subheader("Agentic vs AI-Assisted Breakdown")
    fig = fig_adoption_split(summary, df)
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

    st.subheader("Summary Table")
    st.dataframe(summary.set_index("Stack"), use_container_width=True)

# ── Tab 2: Agents ──────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Top Detected Agents per Stack")
    top_n_agents = st.slider("Number of agents to show", 3, 15, 8, key="agents_slider")
    agents_dict  = top_agents_per_stack(df, top_n=top_n_agents)
    fig = fig_top_agents(agents_dict, top_n=top_n_agents)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No agent data available.")

    st.subheader("Tool Loyalty — Single vs Multi-Tool")
    fig = fig_tool_loyalty(df)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No agent data for loyalty chart.")

# ── Tab 3: Geography ───────────────────────────────────────────────────────────
with tab3:
    top_n_countries = st.slider("Countries to show (top & bottom)", 5, 15, 10,
                                key="country_slider")
    cntry_dict      = country_stats(df, min_repos=min_country)

    st.subheader("Top & Bottom Countries by Adoption Rate")
    fig = fig_top_bottom_countries(cntry_dict, top_n=top_n_countries)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No country data. Ensure corpus has a 'country' column.")

    st.subheader("Adoption Rate by Country Income Group")
    fig = fig_income_group(df)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No income group data available.")

    st.subheader("AI Adoption & Tool Pricing by Income Group")
    st.caption(
        "Left: overall adoption rate per income group. "
        "Right: share of agentic repos using paid-dominant vs free-accessible tools."
    )
    fig = fig_pricing_income(df)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No income group or agent data for pricing chart.")

    st.subheader("MENA vs Non-MENA Adoption by Stack")
    fig = fig_mena_vs_rest(df)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No MENA country data available.")

    st.subheader("MENA Countries — Adoption Rate Detail")
    mena_min = st.slider("Min repos per MENA country", 3, 30, 5, key="mena_slider")
    fig = fig_mena_countries(df, min_repos=mena_min)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No MENA countries with enough repos.")

# ── Tab 4: Time Series ─────────────────────────────────────────────────────────
with tab4:
    st.subheader("AI Adoption by Repository Creation Month")
    fig = fig_time_series(df)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No time series data. Ensure corpus has a 'created_at' column.")

# ── Tab 5: Size ────────────────────────────────────────────────────────────────
with tab5:
    st.subheader("Adoption Rate by Repository Size (Stars / Commits / Code)")
    fig = fig_size_three_metrics(df)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No size data available.")

    st.subheader("Median Repository Size by Adoption Category")
    fig = fig_size_by_category(df)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No size data available.")

# ── Tab 6: Diversity ───────────────────────────────────────────────────────────
with tab6:
    st.subheader("Agent Diversity — Single vs Multi-Agent Repos")
    fig = fig_agent_diversity(df)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No diversity data.")

st.divider()
st.caption("ME Thesis — AI Coding Agent Adoption on GitHub  ·  Built with Streamlit + matplotlib")

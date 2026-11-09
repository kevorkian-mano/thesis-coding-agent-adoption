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

# ── World region mapping ──────────────────────────────────────────────────────
REGION_MAP = {
    "United States": "North America",   "Canada": "North America",
    "Mexico": "Latin America",          "Brazil": "Latin America",
    "Argentina": "Latin America",       "Colombia": "Latin America",
    "Chile": "Latin America",           "Peru": "Latin America",
    "Venezuela": "Latin America",       "Ecuador": "Latin America",
    "Honduras": "Latin America",        "Nicaragua": "Latin America",
    "Bolivia": "Latin America",
    "United Kingdom": "Western Europe", "Germany": "Western Europe",
    "France": "Western Europe",         "Netherlands": "Western Europe",
    "Spain": "Western Europe",          "Italy": "Western Europe",
    "Sweden": "Western Europe",         "Switzerland": "Western Europe",
    "Belgium": "Western Europe",        "Austria": "Western Europe",
    "Denmark": "Western Europe",        "Finland": "Western Europe",
    "Norway": "Western Europe",         "Portugal": "Western Europe",
    "Ireland": "Western Europe",        "Luxembourg": "Western Europe",
    "Russia": "Eastern Europe",         "Poland": "Eastern Europe",
    "Ukraine": "Eastern Europe",        "Romania": "Eastern Europe",
    "Czech Republic": "Eastern Europe", "Hungary": "Eastern Europe",
    "Bulgaria": "Eastern Europe",       "Serbia": "Eastern Europe",
    "Croatia": "Eastern Europe",        "Slovakia": "Eastern Europe",
    "Slovenia": "Eastern Europe",       "Estonia": "Eastern Europe",
    "Latvia": "Eastern Europe",         "Lithuania": "Eastern Europe",
    "Bosnia and Herzegovina": "Eastern Europe", "Albania": "Eastern Europe",
    "Georgia": "Eastern Europe",        "Armenia": "Eastern Europe",
    "Azerbaijan": "Eastern Europe",     "Kazakhstan": "Eastern Europe",
    "Uzbekistan": "Eastern Europe",
    "Egypt": "MENA",        "Israel": "MENA",   "Saudi Arabia": "MENA",
    "Turkey": "MENA",       "UAE": "MENA",       "United Arab Emirates": "MENA",
    "Jordan": "MENA",       "Morocco": "MENA",   "Tunisia": "MENA",
    "Algeria": "MENA",      "Iran": "MENA",      "Iraq": "MENA",
    "Palestine": "MENA",    "Lebanon": "MENA",   "Qatar": "MENA",
    "Kuwait": "MENA",       "Bahrain": "MENA",   "Oman": "MENA",
    "Libya": "MENA",        "Yemen": "MENA",     "Syria": "MENA",
    "Nigeria": "Sub-Saharan Africa",    "Kenya": "Sub-Saharan Africa",
    "Ghana": "Sub-Saharan Africa",      "South Africa": "Sub-Saharan Africa",
    "Ethiopia": "Sub-Saharan Africa",   "Tanzania": "Sub-Saharan Africa",
    "Senegal": "Sub-Saharan Africa",    "Cameroon": "Sub-Saharan Africa",
    "Rwanda": "Sub-Saharan Africa",     "Uganda": "Sub-Saharan Africa",
    "Mali": "Sub-Saharan Africa",       "Niger": "Sub-Saharan Africa",
    "Mozambique": "Sub-Saharan Africa", "Madagascar": "Sub-Saharan Africa",
    "India": "South Asia",    "Pakistan": "South Asia",
    "Bangladesh": "South Asia", "Sri Lanka": "South Asia", "Nepal": "South Asia",
    "China": "East Asia",   "Japan": "East Asia",    "South Korea": "East Asia",
    "Taiwan": "East Asia",  "Hong Kong": "East Asia",
    "Vietnam": "Southeast Asia",    "Indonesia": "Southeast Asia",
    "Philippines": "Southeast Asia", "Malaysia": "Southeast Asia",
    "Thailand": "Southeast Asia",   "Singapore": "Southeast Asia",
    "Australia": "Oceania", "New Zealand": "Oceania",
}
REGION_ORDER = [
    "North America", "Western Europe", "East Asia", "South Asia",
    "Eastern Europe", "Latin America", "MENA", "Southeast Asia",
    "Sub-Saharan Africa", "Oceania",
]

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

# ── Pre-computed country data (for stacks without per-repo location) ──────────
# Maps stack name → (country_adoption_path, country_timeline_path)
_JAVA_PIPELINE = DATA_DIR.parent.parent / "data" / "java_team_pipeline_results"
_STACK_COUNTRY_PATHS: dict[str, tuple[Path, Path | None]] = {
    "Java": (
        _JAVA_PIPELINE / "stage4" / "country_adoption.csv",
        _JAVA_PIPELINE / "stage5" / "country_timeline.csv",
    ),
}

def _load_precomputed_country_agg(stack: str) -> pd.DataFrame | None:
    """Load pre-computed country_adoption.csv for a stack, return normalised DataFrame."""
    if stack not in _STACK_COUNTRY_PATHS:
        return None
    path, _ = _STACK_COUNTRY_PATHS[stack]
    if not path.exists():
        return None
    df = pd.read_csv(path)
    df = df.rename(columns={
        "total_repos":     "total",
        "adoption_rate":   "rate",
        "ci_lower":        "ci_lo",
        "ci_upper":        "ci_hi",
        "agentic_only":    "agentic",
        "ai_assisted_only":"ai_assisted",
    })
    df["income_group"] = df["country"].map(INCOME_MAP)
    df["is_mena"]      = df["country"].isin(MENA_COUNTRIES)
    df["region"]       = df["country"].map(REGION_MAP)
    return df


def _load_precomputed_country_timeline(stack: str) -> pd.DataFrame | None:
    """Load pre-computed country_timeline.csv for a stack."""
    if stack not in _STACK_COUNTRY_PATHS:
        return None
    _, path = _STACK_COUNTRY_PATHS[stack]
    if path is None or not path.exists():
        return None
    return pd.read_csv(path)


def _expand_country_agg_to_rows(agg: pd.DataFrame, stack: str) -> pd.DataFrame:
    """
    Expand country-level aggregate stats into synthetic per-row data so that
    all geography chart functions (which expect per-row country + adoption_label)
    work correctly for stacks whose per-repo country was removed for privacy.
    The aggregate statistics (rates, counts) are preserved exactly.
    """
    rows = []
    for _, r in agg.iterrows():
        country = r["country"]
        agentic = int(r.get("agentic",    r["total"] * r["rate"] / 100))
        ai_asst = int(r.get("ai_assisted", 0))
        none_n  = int(r["total"]) - agentic - ai_asst
        for _ in range(max(0, agentic)):
            rows.append({"country": country, "adoption_label": "agentic",    "stack": stack})
        for _ in range(max(0, ai_asst)):
            rows.append({"country": country, "adoption_label": "ai_assisted","stack": stack})
        for _ in range(max(0, none_n)):
            rows.append({"country": country, "adoption_label": "none",       "stack": stack})
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out["income_group"] = out["country"].map(INCOME_MAP)
    out["is_mena"]      = out["country"].isin(MENA_COUNTRIES)
    return out


@st.cache_data
def _build_geo_supplement(selected_stacks: tuple, fingerprint: str = "") -> pd.DataFrame:  # noqa: ARG001
    """Synthetic per-row country data (no dates) for static geography charts."""
    frames = []
    for stack in selected_stacks:
        agg = _load_precomputed_country_agg(stack)
        if agg is not None:
            frames.append(_expand_country_agg_to_rows(agg, stack))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _expand_country_timeline_to_rows(timeline_df: pd.DataFrame, stack: str) -> pd.DataFrame:
    """
    Expand per-country-per-month aggregate data into synthetic per-row data
    with created_at set to the first day of each month.
    This lets time-based geography charts (heatmap, bump, cumulative) work
    for stacks that only have aggregate country×month data.
    adopted rows get label 'agentic'; remainder get 'none'.
    """
    rows = []
    for _, r in timeline_df.iterrows():
        country = r["country"]
        created = str(r["month"]) + "-01"   # "YYYY-MM-01"
        adopted = int(r.get("adopted", 0))
        total   = int(r.get("total_repos", 0))
        none_n  = max(0, total - adopted)
        for _ in range(adopted):
            rows.append({"country": country, "adoption_label": "agentic",
                         "stack": stack, "created_at": created})
        for _ in range(none_n):
            rows.append({"country": country, "adoption_label": "none",
                         "stack": stack, "created_at": created})
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out["income_group"] = out["country"].map(INCOME_MAP)
    out["is_mena"]      = out["country"].isin(MENA_COUNTRIES)
    return out


@st.cache_data
def _build_timeline_supplement(selected_stacks: tuple, fingerprint: str = "") -> pd.DataFrame:  # noqa: ARG001
    """Synthetic per-row country+date data for time-based geography charts."""
    frames = []
    for stack in selected_stacks:
        tdf = _load_precomputed_country_timeline(stack)
        if tdf is not None:
            frames.append(_expand_country_timeline_to_rows(tdf, stack))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# ── Data loading ───────────────────────────────────────────────────────────────
def _data_fingerprint() -> str:
    """Return a string that changes whenever any CSV in DATA_DIR is added/modified."""
    parts = []
    for f in sorted(DATA_DIR.glob("*.csv")):
        parts.append(f"{f.name}:{f.stat().st_mtime:.0f}:{f.stat().st_size}")
    return "|".join(parts)

_TSJS_TIMING_PATH = DATA_DIR.parent.parent / "data" / "stage5" / "adoption_timeline.csv"
_JAVA_TIMING_PATH = _JAVA_PIPELINE / "stage5" / "first_agent_commit.csv"

@st.cache_data
def load_adoption_timing(fingerprint: str = "") -> pd.DataFrame:  # noqa: ARG001
    """Load & normalise adoption timing data for TS/JS and Java stacks."""
    frames = []
    if _TSJS_TIMING_PATH.exists():
        t = pd.read_csv(_TSJS_TIMING_PATH)
        t["stack"] = "TypeScript/JavaScript"
        # ai_native = adopted within 7 days (immediate); map all categories
        tsjs_map = {"ai_native": "immediate", "early": "early",
                    "late": "late", "unknown": "unknown"}
        t["timing_category"] = t["adoption_category"].map(tsjs_map).fillna("unknown")
        frames.append(t[["stack", "timing_category", "days_to_adoption"]].copy())
    if _JAVA_TIMING_PATH.exists():
        j = pd.read_csv(_JAVA_TIMING_PATH)
        j["stack"] = "Java"
        # day_1 = trailer on first day (immediate); not_found = unknown
        timing_map = {"day_1": "immediate", "early": "early",
                      "late": "late", "not_found": "unknown"}
        j["timing_category"]  = j["trailer_timing"].map(timing_map).fillna("unknown")
        j["days_to_adoption"] = pd.to_numeric(j["days_to_first_trailer"], errors="coerce")
        frames.append(j[["stack", "timing_category", "days_to_adoption"]].copy())
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


@st.cache_data
def load_all_stacks(fingerprint: str = "") -> pd.DataFrame:  # noqa: ARG001
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
        rdf = pd.DataFrame(rows)
        result[stack] = rdf.sort_values("rate", ascending=False).reset_index(drop=True) if not rdf.empty else rdf
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
    """
    Per-stack dual-axis chart:
      Left  axis: adoption rate by income group (bars)
      Right axis: paid % and free % tool share among agentic repos (lines)
    One subplot per stack.
    """
    if "income_group" not in df.columns:
        return None
    stacks = sorted(df["stack"].unique())
    if not stacks:
        return None

    def _repo_pricing(agents_str):
        tools = parse_agents(agents_str)
        if not tools:
            return "none"
        cl = [classify_tool_pricing(t) for t in tools]
        if "paid" in cl:
            return "paid"
        if "free" in cl:
            return "free"
        return "ambiguous"

    colors_ig = ["#1565C0", "#1976D2", "#42A5F5", "#90CAF9"]
    n_stacks  = len(stacks)
    fig, axes = plt.subplots(1, n_stacks, figsize=(5 * n_stacks, 5), squeeze=False)

    for col_i, stack in enumerate(stacks):
        ax1 = axes[0][col_i]
        ax2 = ax1.twinx()
        sub = df[(df["stack"] == stack) & df["income_group"].notna()].copy()

        if sub.empty:
            ax1.text(0.5, 0.5, "No income data", ha="center", va="center",
                     transform=ax1.transAxes, color="gray")
            ax1.set_title(stack, fontsize=11, fontweight="bold")
            ax2.set_yticks([])
            continue

        rows = []
        for ig in INCOME_ORDER:
            g   = sub[sub["income_group"] == ig]
            n   = len(g)
            if n == 0:
                rows.append({"ig": ig, "rate": 0.0, "paid_pct": 0.0,
                             "free_pct": 0.0, "n": 0})
                continue
            adopted  = g["adoption_label"].apply(is_adopted).sum()
            rate     = adopted / n * 100
            if "agents_found" in g.columns:
                ag   = g[(g["adoption_label"] == "agentic") & g["agents_found"].notna()]
                n_ag = len(ag)
            else:
                ag = pd.DataFrame(); n_ag = 0
            if n_ag > 0:
                pricing  = ag["agents_found"].apply(_repo_pricing)
                paid_pct = (pricing == "paid").sum() / n_ag * 100
                free_pct = (pricing == "free").sum() / n_ag * 100
            else:
                paid_pct = free_pct = 0.0
            rows.append({"ig": ig, "rate": rate, "paid_pct": paid_pct,
                         "free_pct": free_pct, "n": n})

        gdf = pd.DataFrame(rows)
        x   = np.arange(len(INCOME_ORDER))

        bars = ax1.bar(x, gdf["rate"], color=colors_ig[:len(INCOME_ORDER)],
                       edgecolor="white", linewidth=0.6, zorder=3, alpha=0.85)
        for bar, val in zip(bars, gdf["rate"].tolist()):
            if val > 2:
                ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.0,
                         f"{val:.1f}%", ha="center", va="bottom", fontsize=8,
                         fontweight="bold")

        has_pricing = gdf["paid_pct"].sum() > 0 or gdf["free_pct"].sum() > 0
        if has_pricing:
            ax2.plot(x, gdf["paid_pct"], marker="s", markersize=5, color="#E53935",
                     linewidth=2, label="Paid %", linestyle="--", zorder=4)
            ax2.plot(x, gdf["free_pct"], marker="o", markersize=5, color="#43A047",
                     linewidth=2, label="Free %", linestyle="-.", zorder=4)
            ax2.set_ylabel("Tool-type share (%)", fontsize=9, color="#555555")
            ax2.set_ylim(0, 100)
            ax2.yaxis.set_major_formatter(mtick.PercentFormatter())
            ax2.spines[["top", "left"]].set_visible(False)
            ax2.legend(fontsize=8, loc="upper right")
        else:
            ax2.set_yticks([])
            ax2.text(0.97, 0.95, "No per-repo\ntool data",
                     transform=ax1.transAxes, fontsize=7,
                     ha="right", va="top", color="gray", style="italic")

        ax1.set_xticks(x)
        ax1.set_xticklabels([INCOME_LABELS.get(ig, ig) for ig in INCOME_ORDER],
                             fontsize=8, rotation=12, ha="right")
        ax1.set_ylabel("Adoption Rate (%)", fontsize=10)
        ax1.set_title(stack, fontsize=11, fontweight="bold")
        ax1.yaxis.set_major_formatter(mtick.PercentFormatter())
        ax1.set_ylim(0, 100)
        ax1.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)
        ax1.spines[["top"]].set_visible(False)

    fig.suptitle("Adoption Rate (left axis) and Tool-Type Share (right axis) by Income Group",
                 fontsize=12, fontweight="bold")
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


def fig_world_regions(df: pd.DataFrame) -> plt.Figure | None:
    """Adoption rate by world region, one bar group per stack."""
    if "country" not in df.columns:
        return None
    sub = df[df["country"].notna() &
             ~df["country"].isin(["not_specified", "unknown", ""])].copy()
    sub["region"] = sub["country"].map(REGION_MAP)
    sub = sub[sub["region"].notna()]
    if sub.empty:
        return None

    stacks   = sorted(sub["stack"].unique())
    n_stacks = len(stacks)
    regions  = [r for r in REGION_ORDER if r in sub["region"].unique()]
    x        = np.arange(len(regions))
    width    = 0.8 / max(n_stacks, 1)

    fig, ax = plt.subplots(figsize=(max(10, len(regions) * 1.3), 5))
    for i, stack in enumerate(stacks):
        sdf  = sub[sub["stack"] == stack]
        vals, err_lo, err_hi = [], [], []
        for region in regions:
            g = sdf[sdf["region"] == region]
            n = len(g)
            if n == 0:
                vals.append(0); err_lo.append(0); err_hi.append(0); continue
            adopted = g["adoption_label"].apply(is_adopted).sum()
            rate    = adopted / n * 100
            lo, hi  = wilson_ci(adopted, n)
            vals.append(rate); err_lo.append(rate - lo); err_hi.append(hi - rate)
        offset = (i - n_stacks / 2 + 0.5) * width
        bars   = ax.bar(x + offset, vals, width * 0.9,
                        label=stack, color=stack_color(stack),
                        edgecolor="white", linewidth=0.5, zorder=3)
        ax.errorbar(x + offset, vals, yerr=[err_lo, err_hi],
                    fmt="none", color="#333333", capsize=3, linewidth=1, zorder=4)

    ax.set_xticks(x)
    ax.set_xticklabels(regions, fontsize=9, rotation=20, ha="right")
    ax.set_ylabel("Adoption Rate (%)", fontsize=11)
    ax.set_title("AI Adoption by World Region (95% Wilson CI)",
                 fontsize=13, fontweight="bold")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_ylim(0, 100)
    ax.legend(fontsize=9)
    ax.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    return fig


def fig_ecosystem_breakdown(df: pd.DataFrame) -> plt.Figure | None:
    """Adoption rate by ecosystem_type (npm/pnpm/Maven/Gradle…) per stack."""
    if "ecosystem_type" not in df.columns:
        return None
    stacks = sorted(df["stack"].unique())
    if not stacks:
        return None

    n_stacks = len(stacks)
    fig, axes = plt.subplots(1, n_stacks, figsize=(5 * n_stacks, 5), squeeze=False)

    for i, stack in enumerate(stacks):
        ax  = axes[0][i]
        sdf = df[df["stack"] == stack].copy()
        rows = []
        for eco, grp in sdf.groupby("ecosystem_type"):
            if pd.isna(eco):
                continue
            n       = len(grp)
            adopted = grp["adoption_label"].apply(is_adopted).sum()
            rate    = adopted / n * 100
            lo, hi  = wilson_ci(adopted, n)
            rows.append({"eco": str(eco), "rate": rate, "lo": lo, "hi": hi, "n": n})
        if not rows:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            ax.set_title(stack, fontsize=10, fontweight="bold")
            continue
        edf  = pd.DataFrame(rows).sort_values("rate", ascending=True)
        ecos = edf["eco"].tolist()
        rates = edf["rate"].tolist()
        err_lo = (edf["rate"] - edf["lo"]).tolist()
        err_hi = (edf["hi"]  - edf["rate"]).tolist()
        y = np.arange(len(ecos))
        ax.barh(y, rates, color=stack_color(stack), edgecolor="white",
                linewidth=0.5, zorder=3, alpha=0.85)
        ax.errorbar(rates, y, xerr=[err_lo, err_hi],
                    fmt="none", color="#333333", capsize=3, linewidth=1, zorder=4)
        for j, (rate, n) in enumerate(zip(rates, edf["n"])):
            ax.text(rate + 1.0, j, f"{rate:.1f}%  (n={n:,})",
                    va="center", fontsize=8)
        ax.set_yticks(y)
        ax.set_yticklabels(ecos, fontsize=9)
        ax.set_xlabel("Adoption Rate (%)", fontsize=9)
        ax.set_title(stack, fontsize=10, fontweight="bold")
        ax.set_xlim(0, 115)
        ax.xaxis.set_major_formatter(mtick.PercentFormatter())
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x", linestyle="--", alpha=0.35)

    fig.suptitle("AI Adoption Rate by Ecosystem / Build System\n(with 95% Wilson CI)",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    return fig


def fig_agent_market_share(df: pd.DataFrame, top_n: int = 7) -> plt.Figure | None:
    """Monthly market share (% of that month's agentic repos) for top agents."""
    if "created_at" not in df.columns:
        return None
    agentic = df[df["adoption_label"] == "agentic"].copy()
    if agentic.empty:
        return None
    agentic["month"] = pd.to_datetime(agentic["created_at"], errors="coerce").dt.to_period("M")
    agentic = agentic.dropna(subset=["month"])

    # Find top agents globally
    all_agents: Counter = Counter()
    for s in agentic["agents_found"].dropna():
        for a in parse_agents(s):
            all_agents[a] += 1
    top_agents = [a for a, _ in all_agents.most_common(top_n) if a != "Generic"][:top_n]

    months = sorted(agentic["month"].unique())
    if len(months) < 3:
        return None

    rows = []
    for month in months:
        grp = agentic[agentic["month"] == month]
        n   = len(grp)
        if n < 5:
            continue
        row = {"month": str(month)}
        for agent in top_agents:
            count = grp["agents_found"].apply(
                lambda s, a=agent: a in str(s) if pd.notna(s) else False
            ).sum()
            row[agent] = count / n * 100
        rows.append(row)
    if not rows:
        return None

    mdf = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(12, 5))
    colors  = plt.cm.tab10(np.linspace(0, 1, len(top_agents)))
    for agent, color in zip(top_agents, colors):
        if agent in mdf.columns:
            ax.plot(mdf["month"], mdf[agent], marker="o", markersize=3,
                    label=agent, linewidth=2, color=color)

    ticks = mdf["month"].tolist()
    step  = max(1, len(ticks) // 12)
    ax.set_xticks(ticks[::step])
    ax.tick_params(axis="x", rotation=45)
    ax.set_ylabel("% of that month's agentic repos", fontsize=11)
    ax.set_title(f"Agent Market Share Over Time — Top {top_n} Agents\n"
                 f"(% of agentic repos created each month using each tool)",
                 fontsize=12, fontweight="bold")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.legend(loc="upper left", fontsize=9, ncol=2)
    ax.grid(linestyle="--", alpha=0.35)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    return fig


def fig_tool_cooccurrence(df: pd.DataFrame, top_n: int = 8) -> plt.Figure | None:
    """Heatmap: how often do pairs of agents appear in the same repo?"""
    agentic = df[df["adoption_label"] == "agentic"].copy()
    if agentic.empty:
        return None

    # Identify top agents (exclude Generic)
    all_agents: Counter = Counter()
    for s in agentic["agents_found"].dropna():
        for a in parse_agents(s):
            all_agents[a] += 1
    top_agents = [a for a, _ in all_agents.most_common(top_n + 2) if a != "Generic"][:top_n]

    n = len(top_agents)
    matrix = np.zeros((n, n), dtype=int)
    total  = len(agentic)

    for s in agentic["agents_found"].dropna():
        agents_in_repo = set(parse_agents(s))
        for i, ai in enumerate(top_agents):
            for j, aj in enumerate(top_agents):
                if ai in agents_in_repo and aj in agents_in_repo:
                    matrix[i][j] += 1

    # Normalize to % of repos that contain agent i
    pct_matrix = np.zeros((n, n))
    for i in range(n):
        if matrix[i][i] > 0:
            pct_matrix[i] = matrix[i] / matrix[i][i] * 100
        else:
            pct_matrix[i] = 0

    fig, ax = plt.subplots(figsize=(max(7, n * 0.9), max(6, n * 0.8)))
    im = ax.imshow(pct_matrix, cmap="YlOrRd", vmin=0, vmax=100, aspect="auto")

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(top_agents, rotation=40, ha="right", fontsize=9)
    ax.set_yticklabels(top_agents, fontsize=9)

    for i in range(n):
        for j in range(n):
            val = pct_matrix[i][j]
            if val > 0:
                color = "white" if val > 55 else "#333333"
                ax.text(j, i, f"{val:.0f}%", ha="center", va="center",
                        fontsize=7.5, color=color)

    plt.colorbar(im, ax=ax, label="% of row-agent repos that also use column-agent")
    ax.set_title(f"Tool Co-occurrence — Top {top_n} Agents\n"
                 "Row %: of repos with row-agent, what fraction also have column-agent",
                 fontsize=12, fontweight="bold")
    plt.tight_layout()
    return fig


def fig_commit_depth(df: pd.DataFrame) -> plt.Figure | None:
    """AI commit density: trailer_count / commits for agentic repos, by stack."""
    needed = {"trailer_count", "commits", "adoption_label", "stack"}
    if not needed.issubset(df.columns):
        return None
    agentic = df[(df["adoption_label"] == "agentic") &
                 df["trailer_count"].notna() &
                 (df["commits"] > 0)].copy()
    if agentic.empty:
        return None

    agentic["ai_density"] = (agentic["trailer_count"] / agentic["commits"]).clip(0, 1)

    # Bucket into intensity levels
    def bucket(d):
        if d == 0:   return "Config-only\n(0%)"
        if d < 0.10: return "Low\n(<10%)"
        if d < 0.40: return "Medium\n(10–40%)"
        if d < 0.80: return "High\n(40–80%)"
        return "Full\n(≥80%)"

    agentic["bucket"] = agentic["ai_density"].apply(bucket)
    bucket_order = ["Config-only\n(0%)", "Low\n(<10%)", "Medium\n(10–40%)",
                    "High\n(40–80%)", "Full\n(≥80%)"]
    stacks   = sorted(agentic["stack"].unique())
    n_stacks = len(stacks)
    x        = np.arange(len(bucket_order))
    width    = 0.8 / max(n_stacks, 1)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # Left: stacked bucket bars
    for i, stack in enumerate(stacks):
        sdf  = agentic[agentic["stack"] == stack]
        vals = []
        for b in bucket_order:
            n_b = (sdf["bucket"] == b).sum()
            vals.append(n_b / len(sdf) * 100)
        offset = (i - n_stacks / 2 + 0.5) * width
        bars   = ax1.bar(x + offset, vals, width * 0.9,
                         label=stack, color=stack_color(stack),
                         edgecolor="white", linewidth=0.5, zorder=3)
        for bar, val in zip(bars, vals):
            if val > 2:
                ax1.text(bar.get_x() + bar.get_width() / 2,
                         bar.get_height() + 0.5,
                         f"{val:.1f}%", ha="center", va="bottom", fontsize=7)

    ax1.set_xticks(x)
    ax1.set_xticklabels(bucket_order, fontsize=9)
    ax1.set_ylabel("% of agentic repos", fontsize=11)
    ax1.set_title("AI Commit Density Buckets", fontsize=12, fontweight="bold")
    ax1.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax1.set_ylim(0, max(60, ax1.get_ylim()[1] * 1.15))
    ax1.legend(fontsize=9)
    ax1.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)
    ax1.spines[["top", "right"]].set_visible(False)

    # Right: density distribution per stack (violin or box)
    stacks_data = [agentic[agentic["stack"] == s]["ai_density"].dropna().tolist()
                   for s in stacks]
    stacks_data = [d for d in stacks_data if d]
    if stacks_data:
        parts = ax2.violinplot(stacks_data, positions=range(len(stacks)),
                               showmedians=True, showextrema=True)
        for pc in parts["bodies"]:
            pc.set_alpha(0.7)
        ax2.set_xticks(range(len(stacks)))
        ax2.set_xticklabels(stacks, fontsize=10)
        ax2.set_ylabel("AI Density (AI commits / total commits)", fontsize=10)
        ax2.set_title("AI Density Distribution per Stack", fontsize=12, fontweight="bold")
        ax2.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1))
        ax2.set_ylim(0, 1)
        ax2.grid(axis="y", linestyle="--", alpha=0.35)
        ax2.spines[["top", "right"]].set_visible(False)

    fig.suptitle("AI Commit Depth — How Intensively Are Agents Used?\n"
                 "(trailer_count ÷ total commits per agentic repo)",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    return fig


def fig_adoption_stacked_area(df: pd.DataFrame) -> plt.Figure | None:
    """Stacked area: monthly new repos split by adoption label, one panel per stack."""
    if "created_at" not in df.columns:
        return None
    df2 = df.copy()
    df2["month"] = pd.to_datetime(df2["created_at"], errors="coerce").dt.to_period("M")
    df2 = df2.dropna(subset=["month"])
    stacks = sorted(df2["stack"].unique())
    if not stacks:
        return None
    n_stacks = len(stacks)
    fig, axes = plt.subplots(1, n_stacks, figsize=(7 * n_stacks, 5), squeeze=False)
    for i, stack in enumerate(stacks):
        ax  = axes[0][i]
        sdf = df2[df2["stack"] == stack]
        months = sorted(sdf["month"].unique())
        ag, ai, no = [], [], []
        for m in months:
            grp = sdf[sdf["month"] == m]
            ag.append((grp["adoption_label"] == "agentic").sum())
            ai.append((grp["adoption_label"] == "ai_assisted").sum())
            no.append((grp["adoption_label"] == "none").sum())
        x     = range(len(months))
        mstrs = [str(m) for m in months]
        ax.stackplot(x, ag, ai, no,
                     labels=["Agentic", "AI-Assisted", "No AI"],
                     colors=["#2196F3", "#81D4FA", "#E0E0E0"], alpha=0.88)
        step = max(1, len(mstrs) // 10)
        ax.set_xticks(range(0, len(months), step))
        ax.set_xticklabels(mstrs[::step], rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("New repos per month", fontsize=10)
        ax.set_title(stack, fontsize=11, fontweight="bold")
        ax.legend(fontsize=8, loc="upper left")
        ax.grid(axis="y", linestyle="--", alpha=0.3)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Monthly New Repositories by Adoption Label (Stacked Area)",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    return fig


def fig_size_violin(df: pd.DataFrame) -> plt.Figure | None:
    """Violin plots: distribution of repo size metrics by adoption category, per stack."""
    metrics = [("commits", "Commits"), ("lang_bytes", "Code Bytes"),
               ("stars", "Stars"), ("forks", "Forks")]
    available = [(c, l) for c, l in metrics if c in df.columns]
    if not available:
        return None
    stacks  = sorted(df["stack"].unique())
    labels  = ["none", "ai_assisted", "agentic"]
    colors  = ["#E0E0E0", "#81D4FA", "#2196F3"]
    n_m     = len(available)
    n_s     = len(stacks)
    fig, axes = plt.subplots(n_s, n_m, figsize=(4 * n_m, 4 * n_s), squeeze=False)
    for row, stack in enumerate(stacks):
        sdf = df[df["stack"] == stack]
        for col, (metric, label) in enumerate(available):
            ax = axes[row][col]
            data = [sdf[sdf["adoption_label"] == lbl][metric].dropna().tolist()
                    for lbl in labels]
            data = [d if d else [0] for d in data]
            parts = ax.violinplot(data, positions=[0, 1, 2],
                                  showmedians=True, showextrema=False)
            for pc, color in zip(parts["bodies"], colors):
                pc.set_facecolor(color)
                pc.set_alpha(0.75)
            parts["cmedians"].set_color("#333333")
            ax.set_xticks([0, 1, 2])
            ax.set_xticklabels(["No AI", "AI-Assisted", "Agentic"], fontsize=8)
            ax.set_ylabel(label, fontsize=9)
            if col == 0:
                ax.set_title(f"{stack}", fontsize=10, fontweight="bold", loc="left")
            ax.grid(axis="y", linestyle="--", alpha=0.3)
            ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Repository Size Distribution by Adoption Category",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    return fig


def fig_country_heatmap(df: pd.DataFrame, top_n: int = 15) -> plt.Figure | None:
    """Heatmap: monthly adoption rate per country (country × month)."""
    if "country" not in df.columns or "created_at" not in df.columns:
        return None
    df2 = df[df["country"].notna() &
             ~df["country"].isin(["not_specified", "unknown", ""])].copy()
    df2["month"] = pd.to_datetime(df2["created_at"], errors="coerce").dt.to_period("M")
    df2 = df2.dropna(subset=["month"])
    if df2.empty:
        return None
    top_countries = df2["country"].value_counts().head(top_n).index.tolist()
    months = sorted(df2["month"].unique())
    matrix = np.full((len(top_countries), len(months)), np.nan)
    for ci, country in enumerate(top_countries):
        for mi, month in enumerate(months):
            cell = df2[(df2["country"] == country) & (df2["month"] == month)]
            if len(cell) >= 5:
                adopted = cell["adoption_label"].apply(is_adopted).sum()
                matrix[ci, mi] = adopted / len(cell) * 100
    fig, ax = plt.subplots(figsize=(max(10, len(months) * 0.6), max(5, top_n * 0.45)))
    masked = np.ma.masked_invalid(matrix)
    im = ax.imshow(masked, cmap="RdYlGn", vmin=0, vmax=100, aspect="auto")
    plt.colorbar(im, ax=ax, label="Adoption Rate (%)", shrink=0.8)
    ax.set_yticks(range(len(top_countries)))
    ax.set_yticklabels(top_countries, fontsize=9)
    mstrs = [str(m) for m in months]
    step  = max(1, len(mstrs) // 12)
    ax.set_xticks(range(0, len(months), step))
    ax.set_xticklabels(mstrs[::step], rotation=45, ha="right", fontsize=8)
    ax.set_title(f"Monthly AI Adoption Rate by Country — Top {top_n}\n"
                 f"(cells with <5 repos shown as grey)",
                 fontsize=12, fontweight="bold")
    plt.tight_layout()
    return fig


def fig_country_bump(df: pd.DataFrame, top_n: int = 12) -> plt.Figure | None:
    """Bump chart: country rank by adoption rate over time."""
    if "country" not in df.columns or "created_at" not in df.columns:
        return None
    df2 = df[df["country"].notna() &
             ~df["country"].isin(["not_specified", "unknown", ""])].copy()
    df2["month"] = pd.to_datetime(df2["created_at"], errors="coerce").dt.to_period("M")
    df2 = df2.dropna(subset=["month"])
    if df2.empty:
        return None
    top_countries = df2["country"].value_counts().head(top_n).index.tolist()
    months = sorted(df2["month"].unique())
    rank_data: dict[str, list] = {c: [] for c in top_countries}
    for month in months:
        mdf   = df2[df2["month"] == month]
        rates = {}
        for c in top_countries:
            cgrp = mdf[mdf["country"] == c]
            if len(cgrp) >= 3:
                rates[c] = cgrp["adoption_label"].apply(is_adopted).sum() / len(cgrp)
            else:
                rates[c] = np.nan
        ranked = sorted([c for c in top_countries if not np.isnan(rates.get(c, np.nan))],
                        key=lambda c: rates[c], reverse=True)
        for c in top_countries:
            rank_data[c].append(ranked.index(c) + 1 if c in ranked else np.nan)
    fig, ax = plt.subplots(figsize=(max(10, len(months) * 0.5), 6))
    colors = plt.cm.tab20(np.linspace(0, 1, top_n))
    mstrs  = [str(m) for m in months]
    for ci, (country, color) in enumerate(zip(top_countries, colors)):
        ranks = rank_data[country]
        xs    = [i for i, r in enumerate(ranks) if not np.isnan(r)]
        ys    = [r for r in ranks if not np.isnan(r)]
        if xs:
            ax.plot(xs, ys, marker="o", markersize=4, color=color,
                    linewidth=2, label=country, alpha=0.85)
            ax.text(xs[-1] + 0.1, ys[-1], country, fontsize=7,
                    color=color, va="center")
    ax.invert_yaxis()
    step = max(1, len(mstrs) // 10)
    ax.set_xticks(range(0, len(months), step))
    ax.set_xticklabels(mstrs[::step], rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Rank (1 = highest adoption rate)", fontsize=10)
    ax.set_title(f"Country Rank Over Time by Adoption Rate — Top {top_n} Countries\n"
                 f"(ranked monthly by adoption rate; min 3 repos per cell)",
                 fontsize=12, fontweight="bold")
    ax.grid(linestyle="--", alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    return fig


def fig_country_cumulative(df: pd.DataFrame, top_n: int = 10) -> plt.Figure | None:
    """Cumulative agentic repos per country over time."""
    if "country" not in df.columns or "created_at" not in df.columns:
        return None
    df2 = df[(df["adoption_label"] == "agentic") &
             df["country"].notna() &
             ~df["country"].isin(["not_specified", "unknown", ""])].copy()
    df2["month"] = pd.to_datetime(df2["created_at"], errors="coerce").dt.to_period("M")
    df2 = df2.dropna(subset=["month"])
    if df2.empty:
        return None
    top_countries = df2["country"].value_counts().head(top_n).index.tolist()
    months = sorted(df2["month"].unique())
    mstrs  = [str(m) for m in months]
    fig, ax = plt.subplots(figsize=(12, 5))
    colors  = plt.cm.tab10(np.linspace(0, 1, top_n))
    for country, color in zip(top_countries, colors):
        cumulative = []
        total = 0
        for month in months:
            total += ((df2["country"] == country) & (df2["month"] == month)).sum()
            cumulative.append(total)
        ax.plot(range(len(months)), cumulative, marker="o", markersize=3,
                linewidth=2, label=country, color=color)
    step = max(1, len(mstrs) // 10)
    ax.set_xticks(range(0, len(months), step))
    ax.set_xticklabels(mstrs[::step], rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Cumulative Agentic Repositories", fontsize=11)
    ax.set_title(f"Cumulative Agentic Repos per Country Over Time — Top {top_n}",
                 fontsize=12, fontweight="bold")
    ax.legend(fontsize=8, loc="upper left", ncol=2)
    ax.grid(linestyle="--", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    return fig


def fig_world_regions_agents(df: pd.DataFrame, top_n: int = 8) -> plt.Figure | None:
    """Heatmap: world region × agent (% of agentic repos per region using each agent)."""
    if "country" not in df.columns:
        return None
    df2 = df[(df["adoption_label"] == "agentic") &
             df["country"].notna() &
             ~df["country"].isin(["not_specified", "unknown", ""])].copy()
    df2["region"] = df2["country"].map(REGION_MAP)
    df2 = df2[df2["region"].notna()]
    if df2.empty:
        return None
    all_agents: Counter = Counter()
    for s in df2["agents_found"].dropna():
        for a in parse_agents(s):
            all_agents[a] += 1
    top_agents = [a for a, _ in all_agents.most_common(top_n + 2) if a != "Generic"][:top_n]
    regions = [r for r in REGION_ORDER if r in df2["region"].unique()]
    matrix  = np.zeros((len(regions), len(top_agents)))
    for ri, region in enumerate(regions):
        rdf = df2[df2["region"] == region]
        n   = len(rdf)
        if n == 0:
            continue
        for ai, agent in enumerate(top_agents):
            count = rdf["agents_found"].apply(
                lambda s, a=agent: a in str(s) if pd.notna(s) else False
            ).sum()
            matrix[ri, ai] = count / n * 100
    fig, ax = plt.subplots(figsize=(max(8, top_n * 1.1), max(5, len(regions) * 0.6)))
    im = ax.imshow(matrix, cmap="YlOrRd", vmin=0, aspect="auto")
    plt.colorbar(im, ax=ax, label="% of agentic repos in region using this agent", shrink=0.8)
    ax.set_xticks(range(len(top_agents)))
    ax.set_xticklabels(top_agents, rotation=40, ha="right", fontsize=9)
    ax.set_yticks(range(len(regions)))
    ax.set_yticklabels(regions, fontsize=9)
    for ri in range(len(regions)):
        for ai in range(len(top_agents)):
            val = matrix[ri, ai]
            if val > 0:
                color = "white" if val > 50 else "#333333"
                ax.text(ai, ri, f"{val:.0f}%", ha="center", va="center",
                        fontsize=7.5, color=color)
    ax.set_title(f"Agent Adoption by World Region — Top {top_n} Agents\n"
                 f"(% of agentic repos in each region using each agent)",
                 fontsize=12, fontweight="bold")
    plt.tight_layout()
    return fig


def fig_commit_density_hist(df: pd.DataFrame) -> plt.Figure | None:
    """Histogram of AI commit density + median density per top agent, one panel per stack."""
    needed = {"trailer_count", "commits", "adoption_label"}
    if not needed.issubset(df.columns):
        return None
    agentic = df[(df["adoption_label"] == "agentic") &
                 df["trailer_count"].notna() &
                 (df["commits"] > 0)].copy()
    if agentic.empty:
        return None
    agentic["ai_density"] = (agentic["trailer_count"] / agentic["commits"]).clip(0, 1)
    stacks   = sorted(agentic["stack"].unique())
    n_stacks = len(stacks)
    fig, axes = plt.subplots(1, n_stacks, figsize=(6 * n_stacks, 5), squeeze=False)
    for i, stack in enumerate(stacks):
        ax  = axes[0][i]
        sdf = agentic[agentic["stack"] == stack]["ai_density"].dropna()
        if sdf.empty:
            ax.text(0.5, 0.5, "No trailer data", ha="center", va="center",
                    transform=ax.transAxes)
            ax.set_title(stack, fontsize=10, fontweight="bold")
            continue
        ax.hist(sdf, bins=40, color=stack_color(stack), edgecolor="white",
                linewidth=0.4, alpha=0.85)
        ax.axvline(sdf.median(), color="#333333", linestyle="--", linewidth=1.5,
                   label=f"Median {sdf.median():.2f}")
        ax.set_xlabel("AI Density (AI commits / total commits)", fontsize=10)
        ax.set_ylabel("Number of agentic repos", fontsize=10)
        ax.set_title(stack, fontsize=11, fontweight="bold")
        ax.xaxis.set_major_formatter(mtick.PercentFormatter(xmax=1))
        ax.legend(fontsize=9)
        ax.grid(axis="y", linestyle="--", alpha=0.3)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Distribution of AI Commit Density (trailer_count ÷ total_commits)\n"
                 "Among agentic repos with trailer signals",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    return fig


def fig_commit_density_by_agent(df: pd.DataFrame, top_n: int = 12) -> plt.Figure | None:
    """Median AI commit density per agent (horizontal bar + IQR error bars)."""
    needed = {"trailer_count", "commits", "adoption_label", "agents_found"}
    if not needed.issubset(df.columns):
        return None
    agentic = df[(df["adoption_label"] == "agentic") &
                 df["trailer_count"].notna() &
                 (df["commits"] > 0)].copy()
    if agentic.empty:
        return None
    agentic["ai_density"] = (agentic["trailer_count"] / agentic["commits"]).clip(0, 1)
    stacks   = sorted(agentic["stack"].unique())
    n_stacks = len(stacks)
    fig, axes = plt.subplots(1, n_stacks, figsize=(6 * n_stacks, 5), squeeze=False)
    for i, stack in enumerate(stacks):
        ax  = axes[0][i]
        sdf = agentic[agentic["stack"] == stack]
        if sdf.empty:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            ax.set_title(stack, fontsize=10, fontweight="bold")
            continue
        agent_stats = []
        all_ag: Counter = Counter()
        for s in sdf["agents_found"].dropna():
            for a in parse_agents(s):
                all_ag[a] += 1
        top_agents = [a for a, _ in all_ag.most_common(top_n + 2) if a != "Generic"][:top_n]
        for agent in top_agents:
            mask    = sdf["agents_found"].apply(
                lambda s, a=agent: a in str(s) if pd.notna(s) else False
            )
            density = sdf.loc[mask, "ai_density"].dropna()
            if len(density) < 3:
                continue
            agent_stats.append({
                "agent":  agent,
                "median": density.median(),
                "q1":     density.quantile(0.25),
                "q3":     density.quantile(0.75),
                "n":      len(density),
            })
        if not agent_stats:
            ax.text(0.5, 0.5, "Not enough data", ha="center", va="center",
                    transform=ax.transAxes)
            ax.set_title(stack, fontsize=10, fontweight="bold")
            continue
        adf      = pd.DataFrame(agent_stats).sort_values("median")
        y        = range(len(adf))
        err_lo   = (adf["median"] - adf["q1"]).tolist()
        err_hi   = (adf["q3"] - adf["median"]).tolist()
        ax.barh(list(y), adf["median"].tolist(), color=stack_color(stack),
                edgecolor="white", linewidth=0.5, alpha=0.85, zorder=3)
        ax.errorbar(adf["median"].tolist(), list(y),
                    xerr=[err_lo, err_hi],
                    fmt="none", color="#333333", capsize=3, linewidth=1, zorder=4)
        for j, (_, row) in enumerate(adf.iterrows()):
            ax.text(row["median"] + 0.005, j,
                    f"{row['median']:.0%}  (n={row['n']:,})",
                    va="center", fontsize=7.5)
        ax.set_yticks(list(y))
        ax.set_yticklabels(adf["agent"].tolist(), fontsize=8)
        ax.set_xlabel("Median AI Density (IQR error bars)", fontsize=9)
        ax.set_title(stack, fontsize=11, fontweight="bold")
        ax.xaxis.set_major_formatter(mtick.PercentFormatter(xmax=1))
        ax.set_xlim(0, min(1.0, adf["q3"].max() * 1.5))
        ax.grid(axis="x", linestyle="--", alpha=0.3)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(f"Median AI Commit Density per Agent — Top {top_n}\n"
                 f"(error bars = IQR; repos with trailer signals only)",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    return fig


def fig_adoption_timing_bars(timing_df: pd.DataFrame) -> plt.Figure | None:
    """Stacked bar of adoption timing categories per stack."""
    if timing_df.empty or "timing_category" not in timing_df.columns:
        return None
    CAT_ORDER  = ["immediate", "early", "late", "unknown"]
    CAT_LABELS = {"immediate": "Immediate (≤7d)", "early": "Early (8–30d)",
                  "late": "Late (>30d)", "unknown": "Unknown"}
    CAT_COLORS = {"immediate": "#2196F3", "early": "#66BB6A",
                  "late": "#FF7043",      "unknown": "#9E9E9E"}
    stacks   = sorted(timing_df["stack"].unique())
    x        = np.arange(len(stacks))
    fig, ax  = plt.subplots(figsize=(max(5, len(stacks) * 1.4), 5))
    bottoms  = np.zeros(len(stacks))
    for cat in CAT_ORDER:
        vals = []
        for stack in stacks:
            sdf = timing_df[timing_df["stack"] == stack]
            n   = len(sdf)
            vals.append((sdf["timing_category"] == cat).sum() / n * 100 if n else 0)
        bars = ax.bar(x, vals, bottom=bottoms,
                      label=CAT_LABELS[cat], color=CAT_COLORS[cat],
                      edgecolor="white", linewidth=0.5, zorder=3)
        for bar, val in zip(bars, vals):
            if val > 5:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_y() + bar.get_height() / 2,
                        f"{val:.1f}%", ha="center", va="center",
                        fontsize=8, color="white", fontweight="bold")
        bottoms = bottoms + np.array(vals)
    ax.set_xticks(x)
    ax.set_xticklabels(stacks, fontsize=10)
    ax.set_ylabel("% of agentic repos with timing data", fontsize=11)
    ax.set_title("First AI Signal — Adoption Timing\n"
                 "(How Soon After Repo Creation?)",
                 fontsize=13, fontweight="bold")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_ylim(0, 110)
    ax.legend(fontsize=9, loc="upper right")
    ax.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    return fig


def fig_adoption_days_hist(timing_df: pd.DataFrame) -> plt.Figure | None:
    """Histogram of days to first AI signal per stack (capped at 365d)."""
    if timing_df.empty or "days_to_adoption" not in timing_df.columns:
        return None
    sub = timing_df[timing_df["days_to_adoption"].notna() &
                    (timing_df["days_to_adoption"] >= 0)].copy()
    if sub.empty:
        return None
    stacks    = sorted(sub["stack"].unique())
    n_stacks  = len(stacks)
    fig, axes = plt.subplots(1, n_stacks, figsize=(6 * n_stacks, 5), squeeze=False)
    for i, stack in enumerate(stacks):
        ax  = axes[0][i]
        sdf = sub[sub["stack"] == stack]["days_to_adoption"].clip(0, 365)
        if sdf.empty:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            ax.set_title(stack, fontsize=10, fontweight="bold")
            continue
        median = sdf.median()
        ax.hist(sdf, bins=36, range=(0, 365), color=stack_color(stack),
                edgecolor="white", linewidth=0.4, alpha=0.85)
        ax.axvline(median, color="#333333", linestyle="--", linewidth=1.5,
                   label=f"Median {median:.0f}d")
        ax.set_xlabel("Days from repo creation to first AI signal", fontsize=10)
        ax.set_ylabel("Number of repos", fontsize=10)
        ax.set_title(stack, fontsize=11, fontweight="bold")
        ax.legend(fontsize=9)
        ax.grid(axis="y", linestyle="--", alpha=0.3)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Days to First AI Signal — Distribution per Stack\n"
                 "(capped at 365d; repos with unknown timing excluded)",
                 fontsize=13, fontweight="bold")
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

df_all = load_all_stacks(fingerprint=_data_fingerprint())

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

# df_geo: main df PLUS synthetic country rows for stacks whose per-repo country
# was removed for privacy (e.g. Java). All geography chart functions use df_geo.
stacks_missing_country = [
    s for s in df["stack"].unique()
    if df[df["stack"] == s]["country"].isna().all()
       and "country" in df.columns
]
_geo_supplement = _build_geo_supplement(
    tuple(stacks_missing_country), fingerprint=_data_fingerprint()
) if stacks_missing_country else pd.DataFrame()

df_geo = pd.concat([df, _geo_supplement], ignore_index=True) if not _geo_supplement.empty else df

# df_geo_timeline: same as df_geo but with created_at rows from country_timeline.csv
# Used for time-based charts (heatmap, bump, cumulative) — Java uses aggregate timeline data
_timeline_supplement = _build_timeline_supplement(
    tuple(stacks_missing_country), fingerprint=_data_fingerprint()
) if stacks_missing_country else pd.DataFrame()
df_geo_timeline = pd.concat([df, _timeline_supplement], ignore_index=True) if not _timeline_supplement.empty else df

cntry_dict  = country_stats(df_geo, min_repos=min_country)
timing_df   = load_adoption_timing(fingerprint=_data_fingerprint())

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Overview", "Agents", "Geography", "Time Series", "Size", "Depth & Ecosystems"
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

    st.subheader("Tool Diversity — Single vs Multi-Agent Repos")
    st.caption("Share of agentic repos that use exactly one agent vs two or more agents.")
    fig = fig_agent_diversity(df)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No agent data for diversity chart.")

    st.subheader("AI Commit Depth — How Intensively Are Agents Used?")
    st.caption(
        "AI density = AI-trailer commits ÷ total commits per agentic repo. "
        "Buckets: Config-only (0%), Low (<10%), Medium (10–40%), High (40–80%), Full (≥80%). "
        "Right panel: density distribution violin per stack."
    )
    fig = fig_commit_depth(df)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No trailer/commit data available.")

    st.subheader("AI Commit Density — Distribution Histogram")
    st.caption("Distribution of AI density (trailer commits ÷ total commits) among agentic repos with trailer signals.")
    fig = fig_commit_density_hist(df)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No trailer/commit data for density histogram.")

    st.subheader("Median AI Commit Density per Agent")
    st.caption(
        "Median share of commits with an AI trailer per agent (IQR error bars). "
        "Repos with trailer signals only. The slider affects all stacks — "
        "stacks with fewer unique agents (e.g. Java) will show fewer bars regardless of the slider value."
    )
    top_n_da = st.slider("Agents to show", 5, 15, 12, key="da_slider")
    fig = fig_commit_density_by_agent(df, top_n=top_n_da)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No trailer data available for density-by-agent chart.")

# ── Tab 3: Geography ───────────────────────────────────────────────────────────
with tab3:
    st.subheader("Adoption Rate by World Region")
    fig = fig_world_regions(df_geo)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No country data available for region mapping.")

    top_n_countries = st.slider("Countries to show (top & bottom)", 5, 15, 10,
                                key="country_slider")
    cntry_dict      = country_stats(df_geo, min_repos=min_country)

    st.subheader("Top & Bottom Countries by Adoption Rate")
    fig = fig_top_bottom_countries(cntry_dict, top_n=top_n_countries)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No country data. Ensure corpus has a 'country' column.")

    st.subheader("Adoption Rate by Country Income Group")
    fig = fig_income_group(df_geo)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No income group data available.")

    st.subheader("AI Adoption & Tool Pricing by Income Group")
    st.caption(
        "Bars: adoption rate by income group (left axis). "
        "Lines: paid vs free tool share among agentic repos (right axis). "
        "One panel per stack. Tool breakdown requires per-repo agent data."
    )
    fig = fig_pricing_income(df_geo)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No income group or agent data for pricing chart.")

    st.subheader("MENA vs Non-MENA Adoption by Stack")
    fig = fig_mena_vs_rest(df_geo)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No MENA country data available.")

    st.subheader("MENA Countries — Adoption Rate Detail")
    mena_min = st.slider("Min repos per MENA country", 3, 30, 5, key="mena_slider")
    fig = fig_mena_countries(df_geo, min_repos=mena_min)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No MENA countries with enough repos.")

    st.subheader("Country × Month Adoption Heatmap")
    st.caption("Adoption rate per country per month (cells with <5 repos shown as grey).")
    top_n_hm = st.slider("Countries in heatmap", 8, 20, 15, key="hm_slider")
    fig = fig_country_heatmap(df_geo_timeline, top_n=top_n_hm)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No country/date data for heatmap.")

    st.subheader("Country Rank Over Time (Bump Chart)")
    st.caption("Each country's rank by adoption rate per month. Rank 1 = highest adoption.")
    top_n_bp = st.slider("Countries in bump chart", 6, 15, 12, key="bp_slider")
    fig = fig_country_bump(df_geo_timeline, top_n=top_n_bp)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No country/date data for bump chart.")

    st.subheader("Cumulative Agentic Repos per Country")
    st.caption("How fast each country accumulated agentic repositories over time.")
    top_n_cu = st.slider("Countries in cumulative chart", 5, 15, 10, key="cu_slider")
    fig = fig_country_cumulative(df_geo_timeline, top_n=top_n_cu)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No country/date data for cumulative chart.")

# ── Tab 4: Time Series ─────────────────────────────────────────────────────────
with tab4:
    st.subheader("AI Adoption Rate by Repository Creation Month")
    fig = fig_time_series(df)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No time series data. Ensure corpus has a 'created_at' column.")

    st.subheader("Monthly New Repositories by Adoption Label (Stacked Area)")
    st.caption("Shows the volume of new repos per month split into Agentic / AI-Assisted / No AI.")
    fig = fig_adoption_stacked_area(df)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No time series data available.")

    st.subheader("First AI Signal — Adoption Timing")
    st.caption(
        "When did repositories first adopt an AI agent relative to their creation date? "
        "Immediate: within 7 days (repo started AI-first). "
        "Early: 8–30 days. Late: >30 days. Unknown: no timestamp available."
    )
    if not timing_df.empty:
        stacks_in_timing = timing_df["stack"].unique().tolist()
        stacks_to_show   = [s for s in selected_stacks if s in stacks_in_timing]
        t_filtered = timing_df[timing_df["stack"].isin(stacks_to_show)] if stacks_to_show else timing_df
        fig = fig_adoption_timing_bars(t_filtered)
        if fig:
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

        fig = fig_adoption_days_hist(t_filtered)
        if fig:
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)
    else:
        st.info("No adoption timing data found. Run stage 5i/5j/5k scripts.")

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

# ── Tab 6: Depth & Ecosystems ──────────────────────────────────────────────────
with tab6:
    st.subheader("AI Commit Depth — How Intensively Are Agents Used?")
    st.caption(
        "AI density = AI-trailer commits ÷ total commits per agentic repo. "
        "Buckets: Config-only (0%), Low (<10%), Medium (10–40%), High (40–80%), Full (≥80%). "
        "Note: Java repos with no trailers (config-file detected) will appear in Config-only."
    )
    fig = fig_commit_depth(df)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No trailer/commit data available.")

    st.subheader("Agent Diversity — Single vs Multi-Agent Repos")
    fig = fig_agent_diversity(df)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No diversity data.")

    st.subheader("Adoption Rate by Ecosystem / Build System")
    st.caption("npm / pnpm / yarn / deno for TS·JS stack · Maven / Gradle / Neither for Java stack.")
    fig = fig_ecosystem_breakdown(df)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No ecosystem_type column found.")

    st.subheader("AI Commit Density — Distribution Histogram")
    st.caption("Distribution of AI density (trailer commits ÷ total commits) among agentic repos with trailer signals.")
    fig = fig_commit_density_hist(df)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No trailer/commit data for density histogram.")

st.divider()
st.caption("ME Thesis — AI Coding Agent Adoption on GitHub  ·  Built with Streamlit + matplotlib")

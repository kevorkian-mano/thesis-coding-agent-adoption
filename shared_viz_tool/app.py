#!/usr/bin/env python3
"""
app.py  —  AI Coding Agent Adoption Cross-Stack Dashboard
==========================================================
Loads all *_final_corpus.csv files from shared_viz_tool/data/.
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

DATA_DIR    = Path(__file__).parent / "data"
FIGURES_DIR = Path(__file__).parent / "figures"
DATA_DIR.mkdir(exist_ok=True)
FIGURES_DIR.mkdir(exist_ok=True)

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
        # Normalise country column name
        if "inferred_country" in df.columns and "country" not in df.columns:
            df = df.rename(columns={"inferred_country": "country"})
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)

# ── Summary table ──────────────────────────────────────────────────────────────
def compute_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for stack, grp in df.groupby("stack"):
        n        = len(grp)
        agentic  = (grp["adoption_label"] == "agentic").sum()
        ai_asst  = (grp["adoption_label"] == "ai_assisted").sum()
        adopted  = agentic + ai_asst
        none_n   = (grp["adoption_label"] == "none").sum()
        rate     = adopted / n * 100 if n > 0 else 0.0
        ci_lo, ci_hi = wilson_ci(adopted, n)
        rows.append({
            "Stack":      stack,
            "Repos":      n,
            "Agentic":    int(agentic),
            "AI-Assisted":int(ai_asst),
            "Adopted":    int(adopted),
            "None":       int(none_n),
            "Rate %":     round(rate, 2),
            "CI Low":     round(ci_lo, 2),
            "CI High":    round(ci_hi, 2),
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
            adopted  = cgrp["adoption_label"].apply(is_adopted).sum()
            rate     = adopted / n * 100
            ci_lo, ci_hi = wilson_ci(adopted, n)
            rows.append({"country": country, "total": n, "adopted": int(adopted),
                          "rate": round(rate, 2), "ci_lo": round(ci_lo, 2), "ci_hi": round(ci_hi, 2)})
        result[stack] = pd.DataFrame(rows).sort_values("rate", ascending=False)
    return result

# ── Continent heatmap ─────────────────────────────────────────────────────────
def continent_pivot(df: pd.DataFrame) -> pd.DataFrame | None:
    if "continent" not in df.columns:
        return None
    rows = []
    for (stack, cont), grp in df.groupby(["stack", "continent"]):
        if pd.isna(cont) or str(cont).lower() in ("", "unknown", "nan"):
            continue
        n       = len(grp)
        adopted = grp["adoption_label"].apply(is_adopted).sum()
        rows.append({"stack": stack, "continent": cont, "rate": adopted / n * 100 if n > 0 else np.nan})
    if not rows:
        return None
    return pd.DataFrame(rows).pivot(index="continent", columns="stack", values="rate")

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
    ax.set_title("AI Coding Agent Adoption by Language Stack\n(with 95% Wilson CI)", fontsize=13, fontweight="bold")
    ax.set_ylim(0, 105)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
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
        bars   = ax.barh(agents, counts, color=color, edgecolor="white", linewidth=0.5, zorder=3)
        max_c  = max(counts)
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


def fig_countries(country_dict: dict, top_n: int = 10) -> plt.Figure | None:
    stacks = [s for s, d in country_dict.items() if not d.empty]
    if not stacks:
        return None
    n_stacks = len(stacks)
    fig, axes = plt.subplots(1, n_stacks, figsize=(5 * n_stacks, 6), squeeze=False)
    for i, stack in enumerate(stacks):
        ax   = axes[0][i]
        data = country_dict[stack].head(top_n)
        if data.empty:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            continue
        countries = data["country"].tolist()[::-1]
        rates     = data["rate"].tolist()[::-1]
        ci_lo     = data["ci_lo"].tolist()[::-1]
        ci_hi     = data["ci_hi"].tolist()[::-1]
        err_lo    = [r - lo for r, lo in zip(rates, ci_lo)]
        err_hi    = [hi - r  for r, hi in zip(rates, ci_hi)]
        color     = stack_color(stack)
        ax.barh(countries, rates, color=color, edgecolor="white", linewidth=0.5, zorder=3)
        ax.errorbar(rates, countries, xerr=[err_lo, err_hi],
                    fmt="none", color="#333333", capsize=3, linewidth=1, zorder=4)
        ax.set_title(stack, fontsize=10, fontweight="bold")
        ax.set_xlabel("Adoption Rate (%)", fontsize=9)
        ax.set_xlim(0, 110)
        ax.xaxis.set_major_formatter(mtick.PercentFormatter())
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x", linestyle="--", alpha=0.35)
    fig.suptitle(f"Top {top_n} Countries by Adoption Rate (min 10 repos)", fontsize=13, fontweight="bold")
    plt.tight_layout()
    return fig


def fig_heatmap(pivot: pd.DataFrame) -> plt.Figure | None:
    if pivot is None or pivot.empty:
        return None
    fig, ax = plt.subplots(figsize=(max(6, len(pivot.columns) * 1.8), max(4, len(pivot) * 0.9)))
    masked  = np.ma.masked_invalid(pivot.values.astype(float))
    im      = ax.imshow(masked, cmap="YlOrRd", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=30, ha="right", fontsize=10)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=10)
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not (isinstance(val, float) and np.isnan(val)):
                txt_color = "white" if float(val) > 65 else "black"
                ax.text(j, i, f"{float(val):.1f}%", ha="center", va="center",
                        fontsize=9, color=txt_color, fontweight="bold")
    plt.colorbar(im, ax=ax, label="Adoption Rate (%)", shrink=0.75)
    ax.set_title("Adoption Rate: Continent × Stack", fontsize=13, fontweight="bold")
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
    mdf  = pd.DataFrame(rows).sort_values("month")
    fig, ax = plt.subplots(figsize=(12, 5))
    for stack, grp in mdf.groupby("stack"):
        ax.plot(grp["month"], grp["rate"], marker="o", markersize=3,
                label=stack, color=stack_color(stack), linewidth=2)
    ticks = sorted(mdf["month"].unique())
    step  = max(1, len(ticks) // 12)
    ax.set_xticks(ticks[::step])
    ax.tick_params(axis="x", rotation=45)
    ax.set_ylabel("Adoption Rate (%)", fontsize=11)
    ax.set_title("AI Adoption Rate by Repository Creation Month", fontsize=13, fontweight="bold")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(linestyle="--", alpha=0.35)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    return fig


def fig_size(df: pd.DataFrame) -> plt.Figure | None:
    if "stars" not in df.columns:
        return None
    stacks = df["stack"].unique()
    rows   = []
    for stack in stacks:
        grp = df[df["stack"] == stack].copy()
        try:
            grp["tertile"] = pd.qcut(grp["stars"], q=3, labels=["Small", "Medium", "Large"])
        except Exception:
            continue
        for t, tgrp in grp.groupby("tertile", observed=True):
            n = len(tgrp)
            adopted = tgrp["adoption_label"].apply(is_adopted).sum()
            rows.append({"stack": stack, "tertile": str(t), "rate": adopted / n * 100 if n > 0 else 0})
    if not rows:
        return None
    rdf      = pd.DataFrame(rows)
    tertiles = ["Small", "Medium", "Large"]
    x        = np.arange(len(tertiles))
    width    = 0.8 / max(len(stacks), 1)
    fig, ax  = plt.subplots(figsize=(max(6, len(stacks) * 2), 5))
    for i, stack in enumerate(stacks):
        sdata  = rdf[rdf["stack"] == stack]
        rates  = [sdata[sdata["tertile"] == t]["rate"].values[0]
                  if len(sdata[sdata["tertile"] == t]) > 0 else 0 for t in tertiles]
        offset = (i - len(stacks) / 2 + 0.5) * width
        ax.bar(x + offset, rates, width * 0.9, label=stack,
               color=stack_color(stack), edgecolor="white", linewidth=0.5, zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels(tertiles, fontsize=11)
    ax.set_ylabel("Adoption Rate (%)", fontsize=11)
    ax.set_title("Adoption Rate by Repository Size (Star Tertile)", fontsize=13, fontweight="bold")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_ylim(0, 100)
    ax.legend(fontsize=9)
    ax.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    return fig


def fig_agent_diversity(df: pd.DataFrame) -> plt.Figure | None:
    agentic = df[df["adoption_label"] == "agentic"]
    if agentic.empty:
        return None
    stacks = agentic["stack"].unique()
    rows   = []
    for stack in stacks:
        grp     = agentic[agentic["stack"] == stack]
        counts  = grp["agents_found"].apply(lambda x: len(parse_agents(x)))
        single  = (counts == 1).sum()
        multi   = (counts  > 1).sum()
        total   = len(grp)
        rows.append({"stack": stack, "Single": single / total * 100, "Multi": multi / total * 100})
    rdf      = pd.DataFrame(rows)
    fig, ax  = plt.subplots(figsize=(max(5, len(stacks) * 1.4), 5))
    x        = np.arange(len(rdf))
    ax.bar(x, rdf["Single"], label="Single-agent", color="#4C72B0", zorder=3)
    ax.bar(x, rdf["Multi"],  bottom=rdf["Single"], label="Multi-agent", color="#DD8452", zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels(rdf["stack"].tolist(), fontsize=10)
    ax.set_ylabel("% of Agentic Repos", fontsize=11)
    ax.set_title("Agent Diversity — Single vs Multi-Agent Repos", fontsize=13, fontweight="bold")
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
    f"Loads all `*.csv` files from `shared_viz_tool/data/`. "
    "Each team member adds a `stack` column to their corpus and drops it in that folder."
)

df_all = load_all_stacks()

if df_all.empty:
    st.error(
        "No corpus files found in `shared_viz_tool/data/`.\n\n"
        "Run `python3 shared_viz_tool/prepare_submission.py` to generate the JS/TS file first."
    )
    st.stop()

# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.header("Filters")
all_stacks      = sorted(df_all["stack"].unique().tolist())
selected_stacks = st.sidebar.multiselect("Show stacks", all_stacks, default=all_stacks)
min_country     = st.sidebar.slider("Min repos per country", 5, 50, 10)

if not selected_stacks:
    st.warning("Select at least one stack from the sidebar.")
    st.stop()

df = df_all[df_all["stack"].isin(selected_stacks)].copy()

# ── Top metrics ────────────────────────────────────────────────────────────────
adopted_mask = df["adoption_label"].apply(is_adopted)
overall_rate = adopted_mask.sum() / len(df) * 100

m1, m2, m3, m4 = st.columns(4)
m1.metric("Stacks loaded",    len(selected_stacks))
m2.metric("Total repos",      f"{len(df):,}")
m3.metric("Adopted repos",    f"{adopted_mask.sum():,}")
m4.metric("Overall adoption", f"{overall_rate:.1f}%")

st.divider()

# ── Precompute ─────────────────────────────────────────────────────────────────
summary      = compute_summary(df)
agents_dict  = top_agents_per_stack(df, top_n=10)
cntry_dict   = country_stats(df, min_repos=min_country)
cont_pivot   = continent_pivot(df)

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Overview", "🔧 Agents", "🌍 Geography",
    "📅 Time Series", "📏 Size", "🔀 Diversity"
])

# ── Tab 1: Overview ────────────────────────────────────────────────────────────
with tab1:
    st.subheader("Adoption Rate Comparison (95% Wilson CI)")
    fig = fig_adoption_bars(summary)
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

# ── Tab 3: Geography ───────────────────────────────────────────────────────────
with tab3:
    st.subheader("Top Countries by Adoption Rate")
    top_n_countries = st.slider("Countries to show", 5, 20, 10, key="country_slider")
    cntry_dict      = country_stats(df, min_repos=min_country)
    fig = fig_countries(cntry_dict, top_n=top_n_countries)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No country data. Ensure corpus has a 'country' column.")

    if cont_pivot is not None and not cont_pivot.empty:
        st.subheader("Adoption Rate Heatmap: Continent × Stack")
        fig = fig_heatmap(cont_pivot)
        if fig:
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

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
    st.subheader("Adoption Rate by Repository Size Tertile (Stars)")
    fig = fig_size(df)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("No size data. Ensure corpus has a 'stars' column.")

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

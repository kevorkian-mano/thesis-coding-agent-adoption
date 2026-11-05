#!/usr/bin/env python3
"""
Stage 4f -- AI Tool Pricing vs Country Income Analysis
=======================================================
Tests whether AI coding agent adoption correlates with tool pricing models
across country income groups (World Bank classification).

Classifies each detected tool as:
  - paid_dominant : requires paid subscription for meaningful use
                    (Claude Code, Devin, Junie, Codegen, Factory, Greptile,
                     Roo Code, Ellipsis, Amp)
  - free_accessible: free tier, OSS, or free for students/education
                    (GitHub Copilot, Cursor, OpenHands, Amazon Q,
                     CodeRabbit, Sweep, Windsurf, Aider, Codeium,
                     Continue, Gemini CLI, OpenCode, Jules, Replit,
                     DeepSource, PR-Agent, Sourcery, Kiro, SWE-agent)
  - ambiguous      : hard to classify (OpenAI Codex, generic labels)

For each country assigns World Bank 2024 income group and computes:
  - overall adoption rate
  - share of agentic repos using paid-dominant vs free-accessible tools
  - chi-squared test across income groups

Input
-----
  data/stage4/corpus_with_country.csv

Output
------
  data/stage4/pricing_analysis.csv       -- per-country pricing breakdown
  data/stage4/pricing_income_groups.csv  -- aggregated by income group
"""
# ══════════════════════════════════════════════════════════════════════════════
# TEAM CONFIGURATION — edit the variables in this block before running
# ══════════════════════════════════════════════════════════════════════════════
#
# INPUT_CSV  : path to your Stage 1 corpus CSV
#              Required columns: full_name, owner_login, stars, commits,
#                                lang_bytes, created_at, primary_language
#              (replace with the equivalent columns in your stack's corpus)
#
# GITHUB_TOKEN: set via environment variable before running:
#   export GITHUB_TOKEN=ghp_...
#
# Outputs will be written to:  shared_methodology/data/stage4/
# ══════════════════════════════════════════════════════════════════════════════



import pandas as pd
import numpy as np
from pathlib import Path
from collections import Counter
from scipy.stats import chi2_contingency, fisher_exact

ROOT     = Path(__file__).resolve().parents[2]
CORPUS   = ROOT / "data" / "stage4" / "corpus_with_country.csv"
OUT_DIR  = ROOT / "data" / "stage4"
OUT_COUNTRY = OUT_DIR / "pricing_analysis.csv"
OUT_GROUP   = OUT_DIR / "pricing_income_groups.csv"

# ── Tool pricing classification ───────────────────────────────────────────────
# paid_dominant: real use requires paid subscription
PAID_TOOLS = {
    # Anthropic
    "claude code", "claude code / generic",
    # JetBrains
    "junie",
    # Devin (Cognition AI)
    "devin",
    # Roo Code / Kilocode
    "roo code",
    # Codegen / Factory / Greptile / Ellipsis / Amp — paid SaaS
    "codegen", "factory", "greptile", "ellipsis", "amp",
    # OpenAI Codex CLI — pay-per-token API
    "openai codex",
}

# free_accessible: free tier / OSS / free for students
FREE_TOOLS = {
    # GitHub Copilot (free for students / free tier)
    "github copilot",
    # Cursor (free tier)
    "cursor",
    # Windsurf / Codeium (free tier)
    "windsurf", "codeium",
    # Aider (open source)
    "aider",
    # Continue (open source)
    "continue",
    # Gemini CLI (free)
    "gemini cli",
    # OpenCode (open source)
    "opencode",
    # OpenHands / SWE-agent (open source)
    "openhands", "swe-agent",
    # Amazon Q / Kiro (free tier)
    "amazon q", "kiro",
    # CodeRabbit / Sweep (free for open source)
    "coderabbit", "sweep",
    # Jules (Google Labs — free preview)
    "jules",
    # Replit (free tier)
    "replit",
    # DeepSource (free for open source)
    "deepsource",
    # PR-Agent / Sourcery (open source / free tier)
    "pr-agent", "sourcery",
}

def classify_tool(name: str) -> str:
    n = name.strip().lower()
    if n in PAID_TOOLS:
        return "paid"
    if n in FREE_TOOLS:
        return "free"
    return "ambiguous"


# ── World Bank income groups (2024) ───────────────────────────────────────────
# HIC  = High Income      (GNI per capita > $13,845)
# UMIC = Upper-Middle     ($4,466–$13,845)
# LMIC = Lower-Middle     ($1,136–$4,465)
# LIC  = Low Income       (< $1,136)
INCOME_GROUP = {
    # High Income
    "Belgium":        "HIC", "United Arab Emirates": "HIC",
    "South Korea":    "HIC", "Israel":               "HIC",
    "Saudi Arabia":   "HIC", "Taiwan":               "HIC",
    "Sweden":         "HIC", "New Zealand":          "HIC",
    "United States":  "HIC", "Denmark":              "HIC",
    "Netherlands":    "HIC", "Switzerland":          "HIC",
    "Austria":        "HIC", "Finland":              "HIC",
    "United Kingdom": "HIC", "Canada":               "HIC",
    "Germany":        "HIC", "Italy":                "HIC",
    "France":         "HIC", "Singapore":            "HIC",
    "Japan":          "HIC", "Spain":                "HIC",
    "Portugal":       "HIC", "Norway":               "HIC",
    "Ireland":        "HIC", "Hong Kong":            "HIC",
    "Australia":      "HIC", "Czech Republic":       "HIC",
    "Greece":         "HIC", "Luxembourg":           "HIC",
    # Upper-Middle Income
    "China":          "UMIC", "Brazil":       "UMIC",
    "Turkey":         "UMIC", "Mexico":       "UMIC",
    "Argentina":      "UMIC", "Colombia":     "UMIC",
    "Thailand":       "UMIC", "Malaysia":     "UMIC",
    "South Africa":   "UMIC", "Bulgaria":     "UMIC",
    "Romania":        "UMIC", "Serbia":       "UMIC",
    "Ukraine":        "UMIC", "Russia":       "UMIC",
    "Peru":           "UMIC", "Chile":        "UMIC",
    "Georgia":        "UMIC", "Kazakhstan":   "UMIC",
    "Uzbekistan":     "UMIC", "Algeria":      "UMIC",
    "Tunisia":        "UMIC", "Egypt":        "UMIC",
    "Jordan":         "UMIC", "Armenia":      "UMIC",
    "Hungary":        "UMIC", "Poland":       "UMIC",
    "Croatia":        "UMIC",
    # Lower-Middle Income
    "India":          "LMIC", "Vietnam":      "LMIC",
    "Philippines":    "LMIC", "Indonesia":    "LMIC",
    "Morocco":        "LMIC", "Bangladesh":   "LMIC",
    "Pakistan":       "LMIC", "Nigeria":      "LMIC",
    "Ghana":          "LMIC", "Kenya":        "LMIC",
    "Sri Lanka":      "LMIC", "Nepal":        "LMIC",
    "Ethiopia":       "LMIC", "Iran":         "LMIC",
    # Low Income
    "Rwanda":         "LIC",
}

INCOME_LABEL = {
    "HIC":  "High Income",
    "UMIC": "Upper-Middle Income",
    "LMIC": "Lower-Middle Income",
    "LIC":  "Low Income",
}
INCOME_ORDER = ["HIC", "UMIC", "LMIC", "LIC"]


def parse_tools(agents_str) -> list[str]:
    if pd.isna(agents_str) or str(agents_str).strip() in ("", "nan"):
        return []
    return [t.strip() for t in str(agents_str).split("|") if t.strip()]


def main():
    print("Stage 4f -- AI Tool Pricing vs Country Income Analysis")
    print("=" * 60)

    df = pd.read_csv(CORPUS, low_memory=False)
    located = df[df["country"] != "not_specified"].copy()
    located["income_group"] = located["country"].map(INCOME_GROUP)

    agentic = located[located["adoption_label"] == "agentic"].copy()
    print(f"Total corpus          : {len(df):,}")
    print(f"Located repos         : {len(located):,}")
    print(f"Agentic + located     : {len(agentic):,}")
    print(f"Countries mapped      : {located['income_group'].notna().sum():,} repos "
          f"({located['income_group'].isna().sum():,} unmapped)")

    # ── Per-repo tool classification ──────────────────────────────────────────
    def repo_tool_class(row):
        tools = parse_tools(row["agents_found"])
        if not tools:
            return "none"
        classes = [classify_tool(t) for t in tools]
        if "paid" in classes:
            return "paid"
        if "free" in classes:
            return "free"
        return "ambiguous"

    agentic["tool_class"] = agentic.apply(repo_tool_class, axis=1)

    print("\nTool classification of agentic repos (located):")
    for cls, cnt in agentic["tool_class"].value_counts().items():
        print(f"  {cls:<12} {cnt:>6,}  ({cnt/len(agentic)*100:.1f}%)")

    # ── Per-country table ─────────────────────────────────────────────────────
    MIN_REPOS = 30
    country_rows = []

    for country, grp in located.groupby("country"):
        if len(grp) < MIN_REPOS:
            continue
        income = INCOME_GROUP.get(country, "Unknown")
        total   = len(grp)
        adopted = (grp["adoption_label"].isin(["agentic","ai_assisted"])).sum()
        ag_grp  = grp[grp["adoption_label"] == "agentic"].copy()
        ag_grp["tool_class"] = ag_grp.apply(repo_tool_class, axis=1)

        n_paid  = (ag_grp["tool_class"] == "paid").sum()
        n_free  = (ag_grp["tool_class"] == "free").sum()
        n_ag    = len(ag_grp)

        country_rows.append({
            "country":        country,
            "income_group":   income,
            "total_repos":    total,
            "adoption_rate":  round(adopted / total * 100, 1),
            "agentic_repos":  n_ag,
            "paid_tools":     int(n_paid),
            "free_tools":     int(n_free),
            "paid_pct":       round(n_paid / n_ag * 100, 1) if n_ag else 0,
            "free_pct":       round(n_free / n_ag * 100, 1) if n_ag else 0,
        })

    country_df = pd.DataFrame(country_rows).sort_values(
        ["income_group", "adoption_rate"], ascending=[True, False]
    )
    country_df.to_csv(OUT_COUNTRY, index=False)

    # ── Income group aggregation ───────────────────────────────────────────────
    group_rows = []
    for ig in INCOME_ORDER:
        grp = located[located["income_group"] == ig]
        if len(grp) == 0:
            continue
        ag_grp = grp[grp["adoption_label"] == "agentic"].copy()
        ag_grp["tool_class"] = ag_grp.apply(repo_tool_class, axis=1)

        total   = len(grp)
        adopted = (grp["adoption_label"].isin(["agentic","ai_assisted"])).sum()
        n_ag    = len(ag_grp)
        n_paid  = (ag_grp["tool_class"] == "paid").sum()
        n_free  = (ag_grp["tool_class"] == "free").sum()
        n_ambig = (ag_grp["tool_class"] == "ambiguous").sum()

        group_rows.append({
            "income_group":   ig,
            "label":          INCOME_LABEL[ig],
            "total_repos":    total,
            "adopted":        int(adopted),
            "adoption_rate":  round(adopted / total * 100, 1),
            "agentic_repos":  n_ag,
            "paid_tools":     int(n_paid),
            "free_tools":     int(n_free),
            "ambiguous":      int(n_ambig),
            "paid_pct":       round(n_paid / n_ag * 100, 1) if n_ag else 0,
            "free_pct":       round(n_free / n_ag * 100, 1) if n_ag else 0,
        })

    group_df = pd.DataFrame(group_rows)
    group_df.to_csv(OUT_GROUP, index=False)

    # ── Print income group summary ─────────────────────────────────────────────
    print(f"\n{'─'*72}")
    print(f"{'Income Group':<22} {'Repos':>6} {'Adopt%':>7} "
          f"{'Agentic':>8} {'Paid%':>7} {'Free%':>7}")
    print(f"{'─'*72}")
    for _, r in group_df.iterrows():
        print(f"{r['label']:<22} {r['total_repos']:>6,} {r['adoption_rate']:>7.1f}% "
              f"{r['agentic_repos']:>8,} {r['paid_pct']:>7.1f}% {r['free_pct']:>7.1f}%")

    # ── Chi-squared: adoption rate across income groups ───────────────────────
    print(f"\n{'─'*72}")
    print("Chi-squared: adoption rate across income groups")
    contingency = []
    for _, r in group_df.iterrows():
        adopted  = r["adopted"]
        not_adpt = r["total_repos"] - adopted
        contingency.append([adopted, not_adpt])
    chi2, p, dof, _ = chi2_contingency(contingency)
    print(f"  Chi2 = {chi2:.2f},  df = {dof},  p = {p:.4e}")

    # ── Chi-squared: paid vs free tool usage across income groups ─────────────
    print("\nChi-squared: paid vs free tool share across income groups")
    pf_contingency = []
    for _, r in group_df.iterrows():
        pf_contingency.append([r["paid_tools"], r["free_tools"]])
    chi2_pf, p_pf, dof_pf, _ = chi2_contingency(pf_contingency)
    print(f"  Chi2 = {chi2_pf:.2f},  df = {dof_pf},  p = {p_pf:.4e}")

    # ── Per-country table print ────────────────────────────────────────────────
    print(f"\n{'─'*72}")
    print("Per-country breakdown (countries >= 30 repos, sorted by income group):")
    print(f"{'Country':<22} {'IG':>4} {'Repos':>6} {'Adopt%':>7} "
          f"{'AgRep':>6} {'Paid%':>7} {'Free%':>7}")
    print(f"{'─'*72}")
    prev_ig = None
    for _, r in country_df.iterrows():
        if r["income_group"] != prev_ig:
            print(f"  [{INCOME_LABEL.get(r['income_group'], r['income_group'])}]")
            prev_ig = r["income_group"]
        print(f"  {r['country']:<20} {r['income_group']:>4} {r['total_repos']:>6,} "
              f"{r['adoption_rate']:>7.1f}% {r['agentic_repos']:>6,} "
              f"{r['paid_pct']:>7.1f}% {r['free_pct']:>7.1f}%")

    print(f"\nSaved: {OUT_COUNTRY.name}  ({len(country_df):,} countries)")
    print(f"Saved: {OUT_GROUP.name}  ({len(group_df):,} income groups)")
    print("\nStage 4f complete.")


if __name__ == "__main__":
    main()

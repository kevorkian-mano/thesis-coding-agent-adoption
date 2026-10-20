#!/usr/bin/env python3
"""
Stage 4e -- MENA Regional Analysis
=====================================
Replicates the full global analysis (Stage 4a / 4b / 4c) scoped to the
Middle East and North Africa (MENA) region.

MENA definition used here (20 countries):
  Gulf states  : United Arab Emirates, Saudi Arabia, Kuwait, Qatar, Bahrain, Oman
  Levant       : Israel, Jordan, Lebanon, Syria, Iraq
  North Africa : Egypt, Morocco, Algeria, Tunisia, Libya
  Turkey       : Turkey  (bridge country, included in MENA for this study)
  Iran / Yemen : Iran, Yemen

Sub-regions for comparative analysis:
  Gulf states  : UAE, Saudi Arabia, Kuwait, Qatar, Bahrain, Oman
  Levant       : Israel, Jordan, Lebanon, Syria, Iraq
  North Africa : Egypt, Morocco, Algeria, Tunisia, Libya
  Turkey       : Turkey
  Iran         : Iran

Analyses
--------
  1. MENA coverage         — how many repos / owners / countries
  2. Country ranking       — all MENA countries (eligible >= 30 repos and below)
  3. Sub-region comparison — Gulf vs Levant vs North Africa vs Turkey vs Iran
  4. Statistical tests     — MENA overall vs global (Fisher exact)
                           — within-MENA chi-squared (eligible countries)
                           — within-MENA pairwise Fisher + BH FDR
  5. Breakdowns            — ecosystem, language, three size approaches
  6. Co-adoption           — tool usage within MENA

Input
-----
  data/stage4/corpus_with_country.csv   -- produced by stage4a

Output
------
  data/stage4/mena/mena_country_ranking.csv
  data/stage4/mena/mena_subregion.csv
  data/stage4/mena/mena_pairwise_fisher.csv
  data/stage4/mena/mena_statistical_tests.txt
  data/stage4/mena/mena_breakdown_ecosystem.csv
  data/stage4/mena/mena_breakdown_language.csv
  data/stage4/mena/mena_breakdown_size.csv
  data/stage4/mena/mena_coadoption_tools.csv

Usage
-----
  python3 scripts/stage4/stage4e_mena_analysis.py
"""

import math
import numpy as np
import pandas as pd
from collections import Counter
from itertools import combinations
from pathlib import Path
from scipy.stats import chi2_contingency, fisher_exact
from scipy import stats

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parents[2]
CORPUS_FILE = ROOT / "data" / "stage4" / "corpus_with_country.csv"
OUT_DIR     = ROOT / "data" / "stage4" / "mena"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MIN_REPOS = 30   # same threshold as global analysis
ALPHA     = 0.05

# ── MENA country definitions ──────────────────────────────────────────────────

MENA_COUNTRIES = {
    "United Arab Emirates", "Saudi Arabia", "Kuwait", "Qatar", "Bahrain", "Oman",
    "Israel", "Jordan", "Lebanon", "Syria", "Iraq",
    "Egypt", "Morocco", "Algeria", "Tunisia", "Libya",
    "Turkey",
    "Iran", "Yemen",
}

SUBREGIONS = {
    "Gulf":          {"United Arab Emirates", "Saudi Arabia", "Kuwait",
                      "Qatar", "Bahrain", "Oman"},
    "Levant":        {"Israel", "Jordan", "Lebanon", "Syria", "Iraq"},
    "North Africa":  {"Egypt", "Morocco", "Algeria", "Tunisia", "Libya"},
    "Turkey":        {"Turkey"},
    "Iran":          {"Iran", "Yemen"},
}

COUNTRY_SUBREGION = {
    country: region
    for region, countries in SUBREGIONS.items()
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
    adj          = np.minimum(1.0, arr * n / ranks)
    adj_mono     = np.minimum.accumulate(adj[order[::-1]])[::-1]
    result       = np.empty(n)
    result[order] = adj_mono
    return result.tolist()


def adoption_breakdown(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    rows = []
    for val, grp in df.groupby(group_col):
        n       = len(grp)
        n_ag    = (grp["adoption_label"] == "agentic").sum()
        n_ai    = (grp["adoption_label"] == "ai_assisted").sum()
        n_adpt  = n_ag + n_ai
        rate    = n_adpt / n if n else 0.0
        ag_rate = n_ag   / n if n else 0.0
        ci_lo, ci_hi = wilson_ci(n_adpt, n)
        rows.append({
            group_col:       val,
            "total_repos":   n,
            "agentic":       int(n_ag),
            "ai_assisted":   int(n_ai),
            "adopted":       int(n_adpt),
            "none":          int(n - n_adpt),
            "adoption_rate": round(rate    * 100, 2),
            "agentic_rate":  round(ag_rate * 100, 2),
            "ci_lower":      round(ci_lo   * 100, 2),
            "ci_upper":      round(ci_hi   * 100, 2),
        })
    return pd.DataFrame(rows).sort_values("adoption_rate", ascending=False).reset_index(drop=True)


def print_table(df: pd.DataFrame, title: str, group_col: str):
    sep = "─" * 72
    print(f"\n{sep}")
    print(f"  {title}")
    print(sep)
    hdr = (f"  {'Group':<25} {'Repos':>6} {'Adopted':>8} "
           f"{'Rate%':>7}  {'95% CI':>16}  {'Agentic%':>9}")
    print(hdr)
    print(f"  {'-' * 68}")
    for _, row in df.iterrows():
        ci  = f"[{row['ci_lower']:.1f}, {row['ci_upper']:.1f}]"
        print(f"  {str(row[group_col]):<25} {row['total_repos']:>6,} "
              f"{row['adopted']:>8,} {row['adoption_rate']:>7.1f}%  "
              f"{ci:>16}  {row['agentic_rate']:>9.1f}%")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    lines = []

    def log(s: str = ""):
        lines.append(s)
        print(s)

    log("Stage 4e -- MENA Regional Analysis")
    log("=" * 72)

    if not CORPUS_FILE.exists():
        raise SystemExit(f"Missing: {CORPUS_FILE}\nRun stage4a first.")

    corpus = pd.read_csv(CORPUS_FILE, low_memory=False)
    n_global_total   = len(corpus)
    n_global_adopted = corpus["adoption_label"].isin(["agentic", "ai_assisted"]).sum()
    global_rate      = n_global_adopted / n_global_total

    # ── 1. Isolate MENA repos ─────────────────────────────────────────────────
    mena = corpus[corpus["country"].isin(MENA_COUNTRIES)].copy()
    mena["subregion"] = mena["country"].map(COUNTRY_SUBREGION)

    n_mena       = len(mena)
    n_mena_adpt  = mena["adoption_label"].isin(["agentic", "ai_assisted"]).sum()
    n_mena_ag    = (mena["adoption_label"] == "agentic").sum()
    n_mena_ai    = (mena["adoption_label"] == "ai_assisted").sum()
    n_mena_none  = (mena["adoption_label"] == "none").sum()
    mena_rate    = n_mena_adpt / n_mena if n_mena else 0.0
    ci_lo, ci_hi = wilson_ci(n_mena_adpt, n_mena)

    log()
    log("── 1. MENA Coverage ──────────────────────────────────────────────────")
    log(f"  MENA countries defined       : {len(MENA_COUNTRIES)}")
    log(f"  MENA repos in corpus         : {n_mena:,}  "
        f"({n_mena / n_global_total * 100:.1f}% of full corpus)")
    log(f"  Global corpus                : {n_global_total:,}")

    located = corpus[corpus["country"] != "not_specified"]
    log(f"  MENA repos / located repos   : {n_mena:,} / {len(located):,}  "
        f"({n_mena / len(located) * 100:.1f}% of located repos)")
    log()
    log(f"  MENA adoption breakdown:")
    log(f"    Agentic      : {n_mena_ag:,}  ({n_mena_ag / n_mena * 100:.1f}%)")
    log(f"    AI-assisted  : {n_mena_ai:,}  ({n_mena_ai / n_mena * 100:.1f}%)")
    log(f"    None         : {n_mena_none:,}  ({n_mena_none / n_mena * 100:.1f}%)")
    log(f"    Total adopted: {n_mena_adpt:,}  ({mena_rate * 100:.2f}%)")
    log(f"    Wilson 95% CI: [{ci_lo * 100:.2f}%, {ci_hi * 100:.2f}%]")
    log(f"  Global adoption rate         : {global_rate * 100:.2f}%")

    # ── 2. Per-country ranking ─────────────────────────────────────────────────
    log()
    log("── 2. Per-Country Ranking ────────────────────────────────────────────")

    country_rows = []
    for country, grp in mena.groupby("country"):
        n      = len(grp)
        n_ag   = (grp["adoption_label"] == "agentic").sum()
        n_ai   = (grp["adoption_label"] == "ai_assisted").sum()
        n_adpt = n_ag + n_ai
        rate   = n_adpt / n if n else 0.0
        ci_l, ci_h = wilson_ci(n_adpt, n)
        country_rows.append({
            "country":        country,
            "subregion":      COUNTRY_SUBREGION.get(country, "Other"),
            "total_repos":    n,
            "agentic":        int(n_ag),
            "ai_assisted":    int(n_ai),
            "adopted":        int(n_adpt),
            "none":           int(n - n_adpt),
            "adoption_rate":  round(rate    * 100, 2),
            "agentic_rate":   round(n_ag/n  * 100, 2) if n else 0.0,
            "ci_lower":       round(ci_l    * 100, 2),
            "ci_upper":       round(ci_h    * 100, 2),
            "eligible":       n >= MIN_REPOS,
        })

    country_df = (pd.DataFrame(country_rows)
                  .sort_values("adoption_rate", ascending=False)
                  .reset_index(drop=True))
    country_df.to_csv(OUT_DIR / "mena_country_ranking.csv", index=False)

    eligible_df = country_df[country_df["eligible"]].reset_index(drop=True)
    below_df    = country_df[~country_df["eligible"]].reset_index(drop=True)

    hdr = (f"  {'Rank':<4} {'Country':<25} {'Sub-region':<14} {'Repos':>5} "
           f"{'Adopted':>7} {'Rate%':>6}  {'95% CI':>16}  {'Agentic%':>9}")
    print(f"\n  Eligible countries (>= {MIN_REPOS} repos):")
    print(hdr)
    print(f"  {'-' * 90}")
    for i, row in eligible_df.iterrows():
        ci = f"[{row['ci_lower']:.1f}, {row['ci_upper']:.1f}]"
        print(f"  {i+1:<4} {row['country']:<25} {row['subregion']:<14} "
              f"{row['total_repos']:>5,} {row['adopted']:>7,} "
              f"{row['adoption_rate']:>6.1f}%  {ci:>16}  {row['agentic_rate']:>9.1f}%")

    print(f"\n  Below threshold (< {MIN_REPOS} repos — indicative only, no CI):")
    print(f"  {'Country':<25} {'Sub-region':<14} {'Repos':>5} {'Rate%':>6}")
    print(f"  {'-' * 55}")
    for _, row in below_df.iterrows():
        print(f"  {row['country']:<25} {row['subregion']:<14} "
              f"{row['total_repos']:>5,} {row['adoption_rate']:>6.1f}%")

    log(f"\n  Saved: mena_country_ranking.csv  "
        f"({len(eligible_df)} eligible, {len(below_df)} below threshold)")

    # ── 3. Sub-region comparison ───────────────────────────────────────────────
    log()
    log("── 3. Sub-region Comparison ──────────────────────────────────────────")

    subreg_df = adoption_breakdown(mena, "subregion")
    print_table(subreg_df, "Adoption by MENA Sub-region", "subregion")
    subreg_df.to_csv(OUT_DIR / "mena_subregion.csv", index=False)
    log(f"\n  Saved: mena_subregion.csv")

    # ── 4. Statistical tests ───────────────────────────────────────────────────
    log()
    log("── 4. Statistical Tests ──────────────────────────────────────────────")

    # 4a: MENA overall vs global rate (Fisher exact)
    log()
    log("  4a. MENA overall adoption vs global adoption (Fisher exact)")
    a   = int(n_mena_adpt)               # MENA adopted
    b   = int(n_mena - n_mena_adpt)      # MENA not adopted
    c   = int(n_global_adopted - a)      # rest-of-world adopted
    d   = int((n_global_total - n_mena) - c)  # rest-of-world not adopted
    _, p_fisher_global = fisher_exact([[a, b], [c, d]], alternative="two-sided")
    or_global = (a * d) / (b * c) if b * c > 0 else float("nan")
    log(f"    MENA adoption        : {mena_rate * 100:.2f}%  ({n_mena_adpt}/{n_mena})")
    log(f"    Global adoption      : {global_rate * 100:.2f}%  ({n_global_adopted}/{n_global_total})")
    log(f"    Odds ratio           : {or_global:.3f}")
    log(f"    Fisher p             : {p_fisher_global:.4e}")
    log(f"    Decision             : {'SIGNIFICANT' if p_fisher_global < ALPHA else 'Not significant'} "
        f"(alpha={ALPHA})")

    # 4b: within-MENA chi-squared
    log()
    log("  4b. Within-MENA chi-squared across eligible countries")
    if len(eligible_df) >= 2:
        contingency = np.array([
            [int(row["adopted"]), int(row["total_repos"]) - int(row["adopted"])]
            for _, row in eligible_df.iterrows()
        ])
        chi2, p_chi2, dof, _ = chi2_contingency(contingency)
        log(f"    Countries in test    : {len(eligible_df)}")
        log(f"    Chi2                 : {chi2:.2f}")
        log(f"    df                   : {dof}")
        log(f"    p-value              : {p_chi2:.4e}")
        log(f"    Decision             : {'REJECT H0 — rates vary across MENA' if p_chi2 < ALPHA else 'FAIL to reject H0'}")
    else:
        log("    Not enough eligible countries for chi-squared test.")
        chi2, p_chi2, dof = None, None, None

    # 4c: pairwise Fisher within MENA (each country vs rest of MENA)
    log()
    log("  4c. Pairwise Fisher (each eligible country vs rest of MENA) + BH FDR")

    mena_total_adopted     = int(eligible_df["adopted"].sum())
    mena_total_not_adopted = int((eligible_df["total_repos"] - eligible_df["adopted"]).sum())

    p_raw_list   = []
    posthoc_rows = []

    for _, row in eligible_df.iterrows():
        a_val = int(row["adopted"])
        b_val = int(row["total_repos"]) - a_val
        c_val = max(mena_total_adopted     - a_val, 0)
        d_val = max(mena_total_not_adopted - b_val, 0)
        _, p_f = fisher_exact([[a_val, b_val], [c_val, d_val]], alternative="two-sided")
        or_v   = (a_val * d_val) / (b_val * c_val) if b_val * c_val > 0 else float("nan")
        p_raw_list.append(p_f)
        posthoc_rows.append({
            "country":       row["country"],
            "subregion":     row["subregion"],
            "total_repos":   int(row["total_repos"]),
            "adopted":       a_val,
            "adoption_rate": row["adoption_rate"],
            "ci_lower":      row["ci_lower"],
            "ci_upper":      row["ci_upper"],
            "odds_ratio":    round(or_v, 3),
            "fisher_p_raw":  round(p_f, 6),
        })

    p_adj = bh_correction(p_raw_list)
    for i, row in enumerate(posthoc_rows):
        row["fisher_p_adj"] = round(p_adj[i], 6)
        row["significant"]  = p_adj[i] < ALPHA

    posthoc_df = (pd.DataFrame(posthoc_rows)
                  .sort_values("adoption_rate", ascending=False)
                  .reset_index(drop=True))
    posthoc_df.to_csv(OUT_DIR / "mena_pairwise_fisher.csv", index=False)

    hdr2 = (f"  {'Country':<25} {'Rate%':>6}  {'95% CI':>16}  "
            f"{'OR':>6}  {'p_raw':>10}  {'p_adj':>10}  {'Sig':>4}")
    log(hdr2)
    log(f"  {'-' * 85}")
    for _, row in posthoc_df.iterrows():
        ci  = f"[{row['ci_lower']:.1f}, {row['ci_upper']:.1f}]"
        sig = "*" if row["significant"] else ""
        log(f"  {row['country']:<25} {row['adoption_rate']:>6.1f}%  {ci:>16}  "
            f"{row['odds_ratio']:>6.3f}  {row['fisher_p_raw']:>10.3e}  "
            f"{row['fisher_p_adj']:>10.4f}  {sig:>4}")

    n_sig = posthoc_df["significant"].sum()
    log(f"\n  Significant (BH p < {ALPHA}): {n_sig} / {len(posthoc_df)} countries")
    log(f"\n  Saved: mena_pairwise_fisher.csv")

    # ── 5. Adoption breakdowns ─────────────────────────────────────────────────
    log()
    log("── 5. Adoption Breakdowns (MENA subset) ─────────────────────────────")

    # 5a: ecosystem
    eco_df = adoption_breakdown(mena, "ecosystem_type")
    print_table(eco_df, "Adoption by Ecosystem (MENA)", "ecosystem_type")
    eco_df.to_csv(OUT_DIR / "mena_breakdown_ecosystem.csv", index=False)
    log(f"\n  Saved: mena_breakdown_ecosystem.csv")

    # 5b: primary language
    lang_df = adoption_breakdown(mena, "primary_language")
    print_table(lang_df, "Adoption by Language (MENA)", "primary_language")

    # 5c: three size approaches (tertiles computed on MENA subset)
    # Stars (fixed)
    def star_stratum(s):
        if s <= 50:  return "small"
        if s <= 500: return "medium"
        return "large"

    # Commits (MENA tertiles)
    p33_c = int(mena["commits"].quantile(0.33))
    p66_c = int(mena["commits"].quantile(0.66))
    def commit_stratum(c):
        if c <= p33_c: return "small"
        if c <= p66_c: return "medium"
        return "large"

    # Lang bytes (MENA tertiles)
    p33_b = int(mena["lang_bytes"].quantile(0.33))
    p66_b = int(mena["lang_bytes"].quantile(0.66))
    def bytes_stratum(b):
        if b <= p33_b: return "small"
        if b <= p66_b: return "medium"
        return "large"

    mena["size_stars"]    = mena["stars"].apply(star_stratum)
    mena["size_commits"]  = mena["commits"].apply(commit_stratum)
    mena["size_langbytes"] = mena["lang_bytes"].apply(bytes_stratum)

    order = ["small", "medium", "large"]

    size_rows = []
    for approach, col, thresh in [
        ("A_stars",     "size_stars",     f"small<=50 | medium 51-500 | large>500"),
        ("B_commits",   "size_commits",   f"small<={p33_c} (P33) | medium {p33_c+1}-{p66_c} (P66) | large>{p66_c}"),
        ("C_langbytes", "size_langbytes", f"small<={p33_b/1e6:.2f}MB (P33) | medium-{p66_b/1e6:.2f}MB (P66) | large>{p66_b/1e6:.2f}MB"),
    ]:
        for label in order:
            grp    = mena[mena[col] == label]
            n      = len(grp)
            n_adpt = grp["adoption_label"].isin(["agentic", "ai_assisted"]).sum()
            n_ag   = (grp["adoption_label"] == "agentic").sum()
            rate   = n_adpt / n if n else 0.0
            ci_l, ci_h = wilson_ci(n_adpt, n)
            size_rows.append({
                "approach":      approach,
                "thresholds":    thresh,
                "stratum":       label,
                "total_repos":   n,
                "pct_mena":      round(n / n_mena * 100, 1),
                "adopted":       int(n_adpt),
                "adoption_rate": round(rate * 100, 2),
                "agentic_rate":  round(n_ag / n * 100, 2) if n else 0.0,
                "ci_lower":      round(ci_l * 100, 2),
                "ci_upper":      round(ci_h * 100, 2),
            })

    size_df = pd.DataFrame(size_rows)
    size_df.to_csv(OUT_DIR / "mena_breakdown_size.csv", index=False)

    log(f"\n  Size breakdown (MENA) — three approaches:")
    log(f"  Commits tertiles  : P33={p33_c}, P66={p66_c}")
    log(f"  Lang bytes tertiles: P33={p33_b/1e6:.2f} MB, P66={p66_b/1e6:.2f} MB")
    log()
    log(f"  {'Approach':<12} {'Stratum':<8} {'Repos':>6} {'%MENA':>6} {'Rate%':>7}  {'95% CI':>16}")
    log(f"  {'-' * 62}")
    for _, row in size_df.iterrows():
        ci = f"[{row['ci_lower']:.1f}, {row['ci_upper']:.1f}]"
        log(f"  {row['approach']:<12} {row['stratum']:<8} {row['total_repos']:>6,} "
            f"{row['pct_mena']:>6.1f}% {row['adoption_rate']:>7.1f}%  {ci:>16}")

    lang_df.to_csv(OUT_DIR / "mena_breakdown_language.csv", index=False)
    log(f"\n  Saved: mena_breakdown_language.csv")
    log(f"  Saved: mena_breakdown_size.csv")

    # ── 6. Co-adoption / tool usage ────────────────────────────────────────────
    log()
    log("── 6. Co-adoption and Tool Usage (MENA) ─────────────────────────────")

    adopted_mena = mena[
        mena["adoption_label"].isin(["agentic", "ai_assisted"]) &
        mena["agents_found"].notna() &
        (mena["agents_found"] != "")
    ].copy()

    adopted_mena["agent_set"] = adopted_mena["agents_found"].apply(
        lambda x: frozenset(a.strip() for a in str(x).split("|") if a.strip())
    )

    tool_counter = Counter()
    for agent_set in adopted_mena["agent_set"]:
        for agent in agent_set:
            tool_counter[agent] += 1

    log(f"\n  Tool usage (MENA adopted repos: {len(adopted_mena):,}):")
    tool_rows = []
    for tool, count in tool_counter.most_common():
        pct_mena    = count / n_mena * 100
        pct_adopted = count / n_mena_adpt * 100
        log(f"    {tool:<32} {count:>5,}  ({pct_mena:.1f}% of MENA, "
            f"{pct_adopted:.1f}% of MENA adopters)")
        tool_rows.append({
            "tool":             tool,
            "repos":            count,
            "pct_of_mena":      round(pct_mena, 2),
            "pct_of_adopted":   round(pct_adopted, 2),
        })

    tool_df = pd.DataFrame(tool_rows)
    tool_df.to_csv(OUT_DIR / "mena_coadoption_tools.csv", index=False)

    # Tool loyalty
    adopted_mena["n_tools"] = adopted_mena["agent_set"].map(len)
    single = (adopted_mena["n_tools"] == 1).sum()
    multi  = (adopted_mena["n_tools"] >  1).sum()
    only_claude = (adopted_mena["agent_set"] == frozenset(["Claude Code"])).sum()

    log()
    log(f"  Tool loyalty (MENA):")
    log(f"    Single-tool repos  : {single:,}  ({single / len(adopted_mena) * 100:.1f}% of adopters)")
    log(f"    Multi-tool repos   : {multi:,}  ({multi  / len(adopted_mena) * 100:.1f}% of adopters)")
    log(f"    Claude Code only   : {only_claude:,}  ({only_claude / len(adopted_mena) * 100:.1f}% of adopters)")

    # Top pairs
    pair_counter = Counter()
    for agent_set in adopted_mena["agent_set"]:
        if len(agent_set) >= 2:
            for pair in combinations(sorted(agent_set), 2):
                pair_counter[pair] += 1

    if pair_counter:
        log(f"\n  Top tool pairs (MENA):")
        for (t_a, t_b), cnt in pair_counter.most_common(5):
            log(f"    {t_a} + {t_b}: {cnt:,}")

    log(f"\n  Saved: mena_coadoption_tools.csv")

    # ── Save full text report ──────────────────────────────────────────────────
    report_path = OUT_DIR / "mena_statistical_tests.txt"
    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    print(f"\n  Saved: mena_statistical_tests.txt")
    print()
    print("Stage 4e complete.")


if __name__ == "__main__":
    main()

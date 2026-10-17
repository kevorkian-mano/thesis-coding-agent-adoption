#!/usr/bin/env python3
"""
Stage 4b -- Formal Statistical Tests (Geographic Study)
=========================================================
Runs RQ1, RQ2, RQ3 significance tests on the full corpus.

RQ1: Is AI coding agent adoption non-trivial across the global corpus?
  Test: One-sample binomial test against H0: p <= 0.05 (5% baseline)

RQ2: Is there a significant difference in multi-signal vs single-signal
     detection (undercounting by single-signal approaches)?
  Test: McNemar's test on paired per-repo detection outcomes
        (multi-signal pipeline vs config-file-only single-signal)

RQ3: Do adoption rates differ significantly across countries?
  Test: Chi-squared test of independence across all countries with >= MIN_REPOS
  Post-hoc: Pairwise Fisher's exact with Benjamini-Hochberg FDR correction
            for the top 10 countries vs global average

Output
------
data/stage4/statistical_tests.txt   (human-readable report)
data/stage4/pairwise_fisher.csv     (country vs global pairwise results)

Usage
-----
  python3 scripts/stage4/stage4b_statistical_tests.py
"""

import math
import itertools
import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats
from scipy.stats import fisher_exact, chi2_contingency, binom_test

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT          = Path(__file__).resolve().parents[2]
CORPUS_FILE   = ROOT / "data" / "stage4" / "corpus_with_country.csv"
COUNTRY_FILE  = ROOT / "data" / "stage4" / "country_adoption.csv"
PASS1_FILE    = ROOT / "data" / "stage3" / "pass1_results.csv"
OUT_DIR       = ROOT / "data" / "stage4"
OUT_REPORT    = OUT_DIR / "statistical_tests.txt"
OUT_PAIRWISE  = OUT_DIR / "pairwise_fisher.csv"

MIN_REPOS      = 30
ALPHA          = 0.05
NULL_RATE      = 0.05   # H0 for RQ1: adoption <= 5%

# ── helpers ───────────────────────────────────────────────────────────────────
def wilson_ci(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z**2 / n
    c = (p + z**2 / (2*n)) / d
    m = z * math.sqrt(p*(1-p)/n + z**2/(4*n**2)) / d
    return max(0.0, c - m), min(1.0, c + m)

def bh_correction(p_values):
    """Benjamini-Hochberg FDR correction. Returns adjusted p-values."""
    n = len(p_values)
    if n == 0:
        return []
    ranked = sorted(enumerate(p_values), key=lambda x: x[1])
    adjusted = [None] * n
    prev = 1.0
    for rank, (orig_idx, p) in enumerate(reversed(ranked)):
        adj = min(prev, p * n / (n - rank))
        adjusted[orig_idx] = adj
        prev = adj
    return adjusted


def run_tests(corpus: pd.DataFrame, country_df: pd.DataFrame, lines: list):

    def log(s=""):
        lines.append(s)
        print(s)

    # ── RQ1: Global adoption non-trivial ──────────────────────────────────────
    log("=" * 65)
    log("RQ1: Is global AI coding agent adoption non-trivial?")
    log("     H0: adoption rate <= 5%  (two-sided binomial)")
    log("=" * 65)

    known = corpus[corpus["country"] != "not_specified"]
    n_total  = len(known)
    n_adopt  = (known["adoption_label"].isin(["agentic", "ai_assisted"])).sum()
    obs_rate = n_adopt / n_total

    ci_lo, ci_hi = wilson_ci(n_adopt, n_total)
    log(f"  Repos with known country : {n_total:,}")
    log(f"  Adopted repos            : {n_adopt:,}")
    log(f"  Observed rate            : {obs_rate*100:.2f}%  "
        f"(95% CI: [{ci_lo*100:.2f}%, {ci_hi*100:.2f}%])")

    try:
        p_binom = binom_test(n_adopt, n_total, NULL_RATE, alternative="greater")
    except Exception:
        # scipy >= 1.7 uses binomtest
        from scipy.stats import binomtest as bt
        p_binom = bt(n_adopt, n_total, NULL_RATE, alternative="greater").pvalue

    log(f"  Binomial test p-value    : {p_binom:.2e}")
    log(f"  Decision: {'REJECT H0 -- adoption is non-trivial' if p_binom < ALPHA else 'FAIL to reject H0'}")
    log()

    # ── RQ2: Multi-signal vs single-signal undercounting ─────────────────────
    log("=" * 65)
    log("RQ2: Does single-signal detection undercount significantly?")
    log("     McNemar test on Pass-1-only vs full pipeline labels")
    log("=" * 65)

    pass1 = pd.read_csv(PASS1_FILE) if PASS1_FILE.exists() else None
    if pass1 is not None and len(pass1):
        merged = corpus.merge(
            pass1[["full_name", "adoption_label"]].rename(
                columns={"adoption_label": "label_pass1"}),
            on="full_name", how="left"
        )
        # Single-signal positive: config file found (agentic in pass1)
        merged["single_pos"] = merged["label_pass1"] == "agentic"
        # Multi-signal positive: any adopted label
        merged["multi_pos"]  = merged["adoption_label"].isin(["agentic", "ai_assisted"])

        # McNemar: b = multi+ & single-;  c = multi- & single+
        b = ((merged["multi_pos"]) & (~merged["single_pos"])).sum()
        c = ((~merged["multi_pos"]) & (merged["single_pos"])).sum()
        log(f"  Multi+ Single-  (b): {b:,}   [multi catches, single misses]")
        log(f"  Multi- Single+  (c): {c:,}   [single catches, multi misses]")

        if b + c > 0:
            chi2_mc = (abs(b - c) - 1)**2 / (b + c)
            p_mc    = 1 - stats.chi2.cdf(chi2_mc, df=1)
            log(f"  McNemar chi2 (continuity corrected): {chi2_mc:.2f}")
            log(f"  p-value: {p_mc:.2e}")
            log(f"  Decision: {'REJECT H0 -- multi-signal detects significantly more' if p_mc < ALPHA else 'FAIL to reject H0'}")
            undercounting_delta = (b - c) / len(merged) * 100
            log(f"  Undercounting delta (multi - single): +{undercounting_delta:.2f} pp")
        else:
            log("  b + c = 0 -- no discordant pairs, test not applicable.")
    else:
        log("  Pass 1 results not found -- skipping RQ2.")
    log()

    # ── RQ3: Geographic variation ─────────────────────────────────────────────
    log("=" * 65)
    log("RQ3: Do adoption rates differ significantly across countries?")
    log("     Chi-squared test of independence (countries with >= "
        f"{MIN_REPOS} repos)")
    log("=" * 65)

    eligible = country_df[country_df["total_repos"] >= MIN_REPOS].copy()
    log(f"  Countries in test: {len(eligible)}")

    # Build contingency table: rows = countries, cols = [adopted, not_adopted]
    contingency = np.array([
        [row["adopted"], row["total_repos"] - row["adopted"]]
        for _, row in eligible.iterrows()
    ])

    chi2, p_chi2, dof, expected = chi2_contingency(contingency)
    log(f"  Chi2 = {chi2:.2f},  df = {dof},  p = {p_chi2:.2e}")
    log(f"  Decision: {'REJECT H0 -- rates vary significantly' if p_chi2 < ALPHA else 'FAIL to reject H0'}")
    log()

    # Post-hoc: each country vs global
    log("Post-hoc: Country vs global (Fisher's exact + BH correction)")
    log("-" * 65)
    global_adopted     = n_adopt
    global_not_adopted = n_total - n_adopt

    p_raw = []
    rows_posthoc = []
    for _, row in eligible.iterrows():
        a = int(row["adopted"])
        b_val = int(row["total_repos"]) - a
        # Global complement (excluding this country)
        c_val = global_adopted - a
        d     = global_not_adopted - b_val
        if c_val < 0 or d < 0:
            c_val = max(c_val, 0)
            d     = max(d, 0)
        table = [[a, b_val], [c_val, d]]
        _, p = fisher_exact(table, alternative="two-sided")
        or_val = (a * d) / (b_val * c_val) if (b_val * c_val) > 0 else float("nan")
        p_raw.append(p)
        rows_posthoc.append({
            "country":       row["country"],
            "total_repos":   row["total_repos"],
            "adopted":       a,
            "adoption_rate": row["adoption_rate"],
            "fisher_p_raw":  p,
            "odds_ratio":    round(or_val, 3),
        })

    p_adj = bh_correction(p_raw)
    for i, row in enumerate(rows_posthoc):
        row["fisher_p_adj"] = round(p_adj[i], 4)
        row["significant"]  = p_adj[i] < ALPHA

    posthoc_df = pd.DataFrame(rows_posthoc).sort_values("adoption_rate", ascending=False)
    posthoc_df.to_csv(OUT_PAIRWISE, index=False)

    log(f"{'Country':<25} {'Rate%':>7} {'OR':>8} {'p_raw':>12} {'p_adj':>12} {'Sig':>5}")
    log("-" * 72)
    for _, row in posthoc_df.iterrows():
        sig = "*" if row["significant"] else ""
        log(f"{row['country']:<25} {row['adoption_rate']:>7.1f}% "
            f"{row['odds_ratio']:>8.3f} {row['fisher_p_raw']:>12.3e} "
            f"{row['fisher_p_adj']:>12.4f} {sig:>5}")
    log()
    log(f"Saved: {OUT_PAIRWISE}")

    return lines


def main():
    if not CORPUS_FILE.exists():
        raise SystemExit(f"Missing: {CORPUS_FILE}\nRun stage4a first.")
    if not COUNTRY_FILE.exists():
        raise SystemExit(f"Missing: {COUNTRY_FILE}\nRun stage4a first.")

    corpus     = pd.read_csv(CORPUS_FILE, low_memory=False)
    country_df = pd.read_csv(COUNTRY_FILE)

    lines = []
    run_tests(corpus, country_df, lines)

    with open(OUT_REPORT, "w") as f:
        f.write("\n".join(lines))
    print(f"\nSaved: {OUT_REPORT}")


if __name__ == "__main__":
    main()

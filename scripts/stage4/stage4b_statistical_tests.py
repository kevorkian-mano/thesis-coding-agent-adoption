#!/usr/bin/env python3
"""
Stage 4b -- Formal Statistical Tests
======================================
Runs all three research question significance tests on the final classified
corpus produced by stage4a (corpus_with_country.csv) and stage4a's country
ranking (country_adoption.csv).

RQ1 -- Scope of Adoption
  Is AI coding agent adoption non-trivial across the full corpus?
  Test : one-sample binomial test
  H0   : global adoption rate <= 5 %
  Input: full corpus (all 60,129 repos, located + unlocated)

RQ2 -- Single-Signal vs Multi-Signal Undercounting
  Does the multi-signal pipeline detect significantly more than config-file
  detection alone (Pass 1)?
  Test : McNemar's test on paired per-repository labels
         (single-signal = Pass 1 config file; multi-signal = final label)
  Input: full corpus joined with pass1_results.csv

RQ3 -- Geographic Variation
  Do adoption rates differ significantly across countries?
  Test 1: chi-squared test of independence across all eligible countries
  Test 2: pairwise Fisher's exact (each country vs rest-of-world) with
          Benjamini-Hochberg FDR correction
  Input : country_adoption.csv (from stage4a)

Output
------
  data/stage4/statistical_tests.txt    human-readable report
  data/stage4/pairwise_fisher.csv      per-country Fisher results + BH p-values

Usage
-----
  python3 scripts/stage4/stage4b_statistical_tests.py
"""

import math
import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats
from scipy.stats import chi2_contingency, fisher_exact

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT         = Path(__file__).resolve().parents[2]
CORPUS_FILE  = ROOT / "data" / "stage4" / "corpus_with_country.csv"
COUNTRY_FILE = ROOT / "data" / "stage4" / "country_adoption.csv"
PASS1_FILE   = ROOT / "data" / "stage3" / "pass1_results.csv"
OUT_DIR      = ROOT / "data" / "stage4"
OUT_REPORT   = OUT_DIR / "statistical_tests.txt"
OUT_PAIRWISE = OUT_DIR / "pairwise_fisher.csv"

MIN_REPOS  = 30     # same threshold as stage4a
ALPHA      = 0.05
NULL_RATE  = 0.05   # H0 for RQ1: adoption <= 5 %


# ── helpers ───────────────────────────────────────────────────────────────────

def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denom  = 1 + z ** 2 / n
    centre = (p + z ** 2 / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def bh_correction(p_values: list) -> list:
    """Benjamini-Hochberg FDR correction. Returns adjusted p-values."""
    n = len(p_values)
    if n == 0:
        return []
    arr   = np.array(p_values, dtype=float)
    order = np.argsort(arr)
    ranks = np.empty(n)
    ranks[order] = np.arange(1, n + 1)
    adj = np.minimum(1.0, arr * n / ranks)
    # enforce monotonicity (cumulative min from right)
    adj_mono = np.minimum.accumulate(adj[order[::-1]])[::-1]
    result = np.empty(n)
    result[order] = adj_mono
    return result.tolist()


def binomial_test(k: int, n: int, p0: float) -> float:
    """One-sided binomial test (greater). Works with both old and new scipy."""
    try:
        from scipy.stats import binomtest
        return binomtest(k, n, p0, alternative="greater").pvalue
    except ImportError:
        return stats.binom_test(k, n, p0, alternative="greater")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    # ── load inputs ───────────────────────────────────────────────────────────
    if not CORPUS_FILE.exists():
        raise SystemExit(f"Missing: {CORPUS_FILE}\nRun stage4a first.")
    if not COUNTRY_FILE.exists():
        raise SystemExit(f"Missing: {COUNTRY_FILE}\nRun stage4a first.")

    corpus     = pd.read_csv(CORPUS_FILE, low_memory=False)
    country_df = pd.read_csv(COUNTRY_FILE)
    lines      = []

    def log(s: str = ""):
        lines.append(s)
        print(s)

    log("Stage 4b -- Formal Statistical Tests")
    log("=" * 65)
    log(f"Corpus loaded : {len(corpus):,} repos")
    log(f"Countries eligible (>= {MIN_REPOS} repos): {len(country_df)}")
    log()

    # ══════════════════════════════════════════════════════════════════════════
    # RQ1 -- Global adoption rate (full corpus, all 60 k repos)
    # ══════════════════════════════════════════════════════════════════════════
    log("=" * 65)
    log("RQ1: Is global AI coding agent adoption non-trivial?")
    log(f"     H0: adoption rate <= {NULL_RATE * 100:.0f}%  (one-sided binomial test)")
    log("=" * 65)

    n_total  = len(corpus)
    n_adopt  = corpus["adoption_label"].isin(["agentic", "ai_assisted"]).sum()
    n_ag     = (corpus["adoption_label"] == "agentic").sum()
    n_ai     = (corpus["adoption_label"] == "ai_assisted").sum()
    obs_rate = n_adopt / n_total
    ci_lo, ci_hi = wilson_ci(n_adopt, n_total)

    log(f"  Total repos          : {n_total:,}")
    log(f"  Agentic              : {n_ag:,}  ({n_ag / n_total * 100:.1f}%)")
    log(f"  AI-assisted          : {n_ai:,}  ({n_ai / n_total * 100:.1f}%)")
    log(f"  Total adopted        : {n_adopt:,}  ({obs_rate * 100:.2f}%)")
    log(f"  Wilson 95% CI        : [{ci_lo * 100:.2f}%, {ci_hi * 100:.2f}%]")

    p_binom = binomial_test(n_adopt, n_total, NULL_RATE)
    log(f"  Binomial test p      : {p_binom:.2e}")
    if p_binom < ALPHA:
        log(f"  Decision             : REJECT H0 -- adoption is statistically non-trivial")
    else:
        log(f"  Decision             : FAIL to reject H0")
    log()

    # ══════════════════════════════════════════════════════════════════════════
    # RQ2 -- McNemar: single-signal (Pass 1) vs multi-signal pipeline
    # ══════════════════════════════════════════════════════════════════════════
    log("=" * 65)
    log("RQ2: Does single-signal detection undercount significantly?")
    log("     McNemar's test -- Pass 1 config-file-only vs full pipeline")
    log("=" * 65)

    if not PASS1_FILE.exists():
        log(f"  Pass 1 file not found ({PASS1_FILE.name}) -- skipping RQ2.")
    else:
        pass1 = pd.read_csv(PASS1_FILE)[["full_name", "adoption_label"]].rename(
            columns={"adoption_label": "label_pass1"}
        )
        merged = corpus.merge(pass1, on="full_name", how="left")

        # Single-signal positive: Pass 1 found a config file (label == "agentic")
        single_pos = merged["label_pass1"] == "agentic"
        # Multi-signal positive: final label is agentic or ai_assisted
        multi_pos  = merged["adoption_label"].isin(["agentic", "ai_assisted"])

        n_single = single_pos.sum()
        n_multi  = multi_pos.sum()

        # McNemar discordant pairs
        b = (multi_pos  & ~single_pos).sum()   # multi catches, single misses
        c = (~multi_pos &  single_pos).sum()   # single catches, multi misses

        delta_pp = (n_multi - n_single) / n_total * 100

        log(f"  Single-signal detected : {n_single:,}  ({n_single / n_total * 100:.1f}%)")
        log(f"  Multi-signal detected  : {n_multi:,}  ({n_multi / n_total * 100:.1f}%)")
        log(f"  Undercounting delta    : +{delta_pp:.2f} percentage points")
        log()
        log(f"  McNemar table:")
        log(f"    b (multi+ & single-) : {b:,}   [multi catches, single misses]")
        log(f"    c (multi- & single+) : {c:,}   [single catches, multi misses]")

        if b + c > 0:
            chi2_mc = (abs(b - c) - 1) ** 2 / (b + c)
            p_mc    = stats.chi2.sf(chi2_mc, df=1)
            log(f"  McNemar chi2 (CC)      : {chi2_mc:.2f}")
            log(f"  p-value                : {p_mc:.2e}")
            if p_mc < ALPHA:
                log("  Decision               : REJECT H0 -- multi-signal detects significantly more")
            else:
                log("  Decision               : FAIL to reject H0")
        else:
            log("  b + c = 0 -- no discordant pairs, test not applicable.")
    log()

    # ══════════════════════════════════════════════════════════════════════════
    # RQ3 -- Geographic variation
    # ══════════════════════════════════════════════════════════════════════════
    log("=" * 65)
    log("RQ3: Do adoption rates differ significantly across countries?")
    log(f"     Chi-squared test of independence (countries >= {MIN_REPOS} repos)")
    log("=" * 65)

    eligible = country_df[country_df["total_repos"] >= MIN_REPOS].copy()
    log(f"  Countries in test : {len(eligible)}")

    # Chi-squared contingency table: rows = countries, cols = [adopted, not_adopted]
    contingency = np.array([
        [int(row["adopted"]), int(row["total_repos"]) - int(row["adopted"])]
        for _, row in eligible.iterrows()
    ])
    chi2, p_chi2, dof, _ = chi2_contingency(contingency)
    log(f"  Chi2 = {chi2:.2f},  df = {dof},  p = {p_chi2:.2e}")
    if p_chi2 < ALPHA:
        log("  Decision : REJECT H0 -- adoption rates vary significantly across countries")
    else:
        log("  Decision : FAIL to reject H0")
    log()

    # ── Post-hoc: each country vs rest-of-world (Fisher + BH correction) ──────
    log("Post-hoc: country vs rest-of-world (Fisher's exact + BH FDR correction)")
    log("-" * 65)

    # Global totals for rest-of-world calculation
    total_adopted     = int(eligible["adopted"].sum())
    total_not_adopted = int((eligible["total_repos"] - eligible["adopted"]).sum())

    p_raw_list  = []
    posthoc_rows = []

    for _, row in eligible.iterrows():
        a     = int(row["adopted"])
        b_val = int(row["total_repos"]) - a
        # rest-of-world (exclude this country)
        c_val = total_adopted - a
        d     = total_not_adopted - b_val
        c_val = max(c_val, 0)
        d     = max(d, 0)
        _, p_f = fisher_exact([[a, b_val], [c_val, d]], alternative="two-sided")
        or_val = (a * d) / (b_val * c_val) if b_val * c_val > 0 else float("nan")
        p_raw_list.append(p_f)
        posthoc_rows.append({
            "country":       row["country"],
            "total_repos":   int(row["total_repos"]),
            "adopted":       a,
            "adoption_rate": row["adoption_rate"],
            "ci_lower":      row["ci_lower"],
            "ci_upper":      row["ci_upper"],
            "fisher_p_raw":  round(p_f, 6),
            "odds_ratio":    round(or_val, 3),
        })

    p_adj = bh_correction(p_raw_list)
    for i, row in enumerate(posthoc_rows):
        row["fisher_p_adj"] = round(p_adj[i], 6)
        row["significant"]  = p_adj[i] < ALPHA

    posthoc_df = (
        pd.DataFrame(posthoc_rows)
        .sort_values("adoption_rate", ascending=False)
        .reset_index(drop=True)
    )
    posthoc_df.to_csv(OUT_PAIRWISE, index=False)

    hdr = (f"{'Country':<25} {'Rate%':>7} {'95% CI':>14} "
           f"{'OR':>7} {'p_raw':>10} {'p_adj':>10} {'Sig':>4}")
    log(hdr)
    log("-" * len(hdr))
    for _, row in posthoc_df.iterrows():
        ci_str = f"[{row['ci_lower']:.1f},{row['ci_upper']:.1f}]"
        sig    = "*" if row["significant"] else ""
        log(f"{row['country']:<25} {row['adoption_rate']:>7.1f}% "
            f"{ci_str:>14} {row['odds_ratio']:>7.3f} "
            f"{row['fisher_p_raw']:>10.3e} {row['fisher_p_adj']:>10.4f} {sig:>4}")

    log()
    n_sig = posthoc_df["significant"].sum()
    log(f"Significant countries (BH-adjusted p < {ALPHA}): {n_sig} / {len(posthoc_df)}")

    # ── save report ───────────────────────────────────────────────────────────
    with open(OUT_REPORT, "w") as f:
        f.write("\n".join(lines))

    print()
    print(f"Saved: {OUT_REPORT}")
    print(f"Saved: {OUT_PAIRWISE}")


if __name__ == "__main__":
    main()

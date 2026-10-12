# -*- coding: utf-8 -*-
"""
Stage 6 - Formal Statistical Testing (RQ1, RQ2, RQ3)
=====================================================
Reads Stage 4 detection outputs for both corpora and Stage 5 breakdowns.
Performs:
  - RQ1: Adoption rate point estimates + Wilson confidence intervals by
         ecosystem, primary_language, and size_stratum (global corpus only)
  - RQ2: Single-signal vs multi-signal McNemar test (paired, same repos);
         per-signal contribution to coverage
  - RQ3: Fisher's exact test (global multi-signal vs Egyptian multi-signal);
         Mann-Whitney U on signal_count; Benjamini-Hochberg correction;
         Sensitivity analysis: confirmed-Egyptian-only vs all Egyptian

Outputs CSV/JSON per analysis to data/stage6/ and prints a summary.

Dependencies: scipy, statsmodels, pandas, numpy
Install:  pip install scipy statsmodels pandas numpy
"""

import json
import math
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
from scipy.stats import fisher_exact, mannwhitneyu, norm

# ── paths ───────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
DATA4 = ROOT / "data" / "stage4"
DATA5 = ROOT / "data" / "stage5"
DATA6 = ROOT / "data" / "stage6"
DATA6.mkdir(parents=True, exist_ok=True)

# ── helpers ──────────────────────────────────────────────────────────────────

def wilson_ci(k, n, z=1.96):
    """Wilson score confidence interval for a proportion."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    margin = (z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def bh_correct(pvals):
    """Benjamini-Hochberg FDR correction. Returns adjusted p-values."""
    m = len(pvals)
    if m == 0:
        return []
    arr = np.array(pvals, dtype=float)
    order = np.argsort(arr)
    ranks = np.empty(m)
    ranks[order] = np.arange(1, m + 1)
    adj = np.minimum(1.0, arr * m / ranks)
    # ensure monotonicity (take cumulative min from right)
    adj_mono = np.minimum.accumulate(adj[order[::-1]])[::-1]
    result = np.empty(m)
    result[order] = adj_mono
    return result.tolist()


def fmt_ci(lo, hi, pct=True):
    if pct:
        return f"[{lo*100:.1f}%, {hi*100:.1f}%]"
    return f"[{lo:.4f}, {hi:.4f}]"

# ── load data ────────────────────────────────────────────────────────────────
print("=" * 65)
print("Stage 6 — Formal Statistical Testing")
print("=" * 65)

global_df = pd.read_csv(DATA4 / "sample_corpus_detected.csv", low_memory=False)
egypt_df  = pd.read_csv(DATA4 / "egypt_corpus_input_detected.csv", low_memory=False)

print(f"\nGlobal corpus  : {len(global_df):,} repos")
print(f"Egyptian corpus: {len(egypt_df):,} repos")

# normalise boolean columns
for col in ["agent_adopted", "agent_adopted_single", "agent_adopted_multi"]:
    for df in [global_df, egypt_df]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.lower().isin(["true", "1", "yes"])

# ─────────────────────────────────────────────────────────────────────────────
# RQ1 — Adoption rates with confidence intervals
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "─" * 65)
print("RQ1 — Scope of Adoption (multi-signal, global corpus)")
print("─" * 65)

rq1_rows = []

# overall
n_global = len(global_df)
k_global = global_df["agent_adopted_multi"].sum()
lo, hi = wilson_ci(k_global, n_global)
rate = k_global / n_global
print(f"\nOverall  : {k_global}/{n_global} = {rate*100:.1f}%  95%CI {fmt_ci(lo,hi)}")
rq1_rows.append({"group": "overall", "subgroup": "all",
                 "n": n_global, "k": k_global,
                 "rate": round(rate, 4), "ci_lo": round(lo, 4), "ci_hi": round(hi, 4)})

for dim in ["ecosystem_type", "primary_language", "size_stratum"]:
    if dim not in global_df.columns:
        continue
    print(f"\nBy {dim}:")
    for val, grp in sorted(global_df.groupby(dim)):
        n = len(grp)
        k = grp["agent_adopted_multi"].sum()
        if n < 5:
            continue
        r = k / n
        lo, hi = wilson_ci(k, n)
        print(f"  {str(val):<20} {k:>4}/{n:<5} = {r*100:5.1f}%  {fmt_ci(lo,hi)}")
        rq1_rows.append({"group": dim, "subgroup": str(val),
                         "n": n, "k": k,
                         "rate": round(r, 4), "ci_lo": round(lo, 4), "ci_hi": round(hi, 4)})

rq1_df = pd.DataFrame(rq1_rows)
rq1_df.to_csv(DATA6 / "rq1_adoption_rates.csv", index=False)
print(f"\n[saved] rq1_adoption_rates.csv")

# ─────────────────────────────────────────────────────────────────────────────
# RQ2 — Undercounting: McNemar test + signal contribution
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "─" * 65)
print("RQ2 — Signal Undercounting")
print("─" * 65)

n = len(global_df)
k_single = global_df["agent_adopted_single"].sum()
k_multi  = global_df["agent_adopted_multi"].sum()
delta_pp = (k_multi - k_single) / n * 100

print(f"\nSingle-signal detected : {k_single}/{n} = {k_single/n*100:.1f}%")
print(f"Multi-signal  detected : {k_multi}/{n}  = {k_multi/n*100:.1f}%")
print(f"Delta                  : {delta_pp:.1f} pp")

# McNemar test
# b = multi detects but single misses, c = single detects but multi misses
adopted_single = global_df["agent_adopted_single"]
adopted_multi  = global_df["agent_adopted_multi"]
b = ((~adopted_single) & adopted_multi).sum()   # multi-only (undercounting)
c = (adopted_single & (~adopted_multi)).sum()    # single-only (shouldn't exist in our scheme)
print(f"\nMcNemar table: b (multi only) = {b}, c (single only) = {c}")
if b + c > 0:
    # exact McNemar
    result_mcnemar = stats.binom_test(b, b + c, 0.5, alternative="two-sided") if hasattr(stats, "binom_test") else None
    # use scipy chi2 continuity-corrected form
    chi2 = (abs(b - c) - 1)**2 / (b + c) if (b + c) > 0 else 0
    p_mcnemar = stats.chi2.sf(chi2, df=1)
    print(f"McNemar chi2 = {chi2:.3f},  p = {p_mcnemar:.4e}")
else:
    p_mcnemar = 1.0
    print("McNemar: b=c=0, no discordant pairs.")

# Signal-type contribution (from signals CSV)
sig_global = pd.read_csv(DATA4 / "signals_global.csv", low_memory=False)
print(f"\nPer-signal-type detection coverage (global, n={n}):")
sig_type_rows = []
if "signal_type" in sig_global.columns:
    for stype, grp in sig_global.groupby("signal_type"):
        repos_hit = grp["full_name"].nunique() if "full_name" in grp.columns else grp.index.nunique()
        rate_s = repos_hit / n
        lo_s, hi_s = wilson_ci(repos_hit, n)
        print(f"  {str(stype):<30} {repos_hit:>4} repos  {rate_s*100:5.1f}%  {fmt_ci(lo_s,hi_s)}")
        sig_type_rows.append({"signal_type": stype, "repos_hit": repos_hit,
                               "rate": round(rate_s, 4), "ci_lo": round(lo_s, 4), "ci_hi": round(hi_s, 4)})
else:
    print("  (signal_type column not found in signals_global.csv — skipping breakdown)")

rq2_summary = {
    "n_global": int(n),
    "k_single": int(k_single),
    "k_multi": int(k_multi),
    "rate_single": round(k_single / n, 4),
    "rate_multi": round(k_multi / n, 4),
    "delta_pp": round(delta_pp, 2),
    "mcnemar_b": int(b),
    "mcnemar_c": int(c),
    "mcnemar_p": float(p_mcnemar),
}
with open(DATA6 / "rq2_undercounting.json", "w") as f:
    json.dump(rq2_summary, f, indent=2)
if sig_type_rows:
    pd.DataFrame(sig_type_rows).to_csv(DATA6 / "rq2_signal_contribution.csv", index=False)
print(f"\n[saved] rq2_undercounting.json, rq2_signal_contribution.csv")

# ─────────────────────────────────────────────────────────────────────────────
# RQ3 — Egypt vs Global: Fisher's exact + Mann-Whitney U
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "─" * 65)
print("RQ3 — Egypt vs Global Comparison")
print("─" * 65)

n_egy  = len(egypt_df)
k_egy  = egypt_df["agent_adopted_multi"].sum()
n_glob = len(global_df)
k_glob = global_df["agent_adopted_multi"].sum()

r_egy  = k_egy / n_egy
r_glob = k_glob / n_glob

lo_e, hi_e = wilson_ci(k_egy, n_egy)
lo_g, hi_g = wilson_ci(k_glob, n_glob)

print(f"\nGlobal  : {k_glob}/{n_glob} = {r_glob*100:.1f}%  95%CI {fmt_ci(lo_g,hi_g)}")
print(f"Egyptian: {k_egy}/{n_egy}   = {r_egy*100:.1f}%  95%CI {fmt_ci(lo_e,hi_e)}")
print(f"Gap     : {(r_glob - r_egy)*100:.1f} pp  (global − Egyptian)")

# Fisher's exact test (2x2 contingency table)
# [[adopted_egy, not_adopted_egy], [adopted_glob, not_adopted_glob]]
table = [[k_egy, n_egy - k_egy],
         [k_glob, n_glob - k_glob]]
oddsratio, p_fisher = fisher_exact(table, alternative="two-sided")
print(f"\nFisher's exact test:")
print(f"  Odds ratio = {oddsratio:.4f}")
print(f"  p-value    = {p_fisher:.4e}")
print(f"  {'Significant' if p_fisher < 0.05 else 'Not significant'} at alpha = 0.05")

# Mann-Whitney U on signal_count
sc_glob = global_df["signal_count"].fillna(0).astype(float)
sc_egy  = egypt_df["signal_count"].fillna(0).astype(float)
u_stat, p_mwu = mannwhitneyu(sc_egy, sc_glob, alternative="two-sided")
n1, n2 = len(sc_egy), len(sc_glob)
# rank-biserial correlation r = 1 - 2U/(n1*n2)
r_rb = 1 - 2 * u_stat / (n1 * n2)
print(f"\nMann-Whitney U (signal_count, Egyptian vs Global):")
print(f"  U = {u_stat:.0f}, p = {p_mwu:.4e}, r_rb = {r_rb:.4f}")
print(f"  Median Egyptian: {sc_egy.median():.1f},  Median Global: {sc_glob.median():.1f}")

# Sensitivity: confirmed-only Egyptian
# (use corpus_source or owner location confidence if available)
if "owner_confidence" in egypt_df.columns:
    confirmed_df = egypt_df[egypt_df["owner_confidence"].str.lower().isin(["high", "confirmed"])]
    n_conf = len(confirmed_df)
    k_conf = confirmed_df["agent_adopted_multi"].sum()
    if n_conf > 0:
        r_conf = k_conf / n_conf
        lo_c, hi_c = wilson_ci(k_conf, n_conf)
        _, p_conf = fisher_exact([[k_conf, n_conf - k_conf],
                                   [k_glob, n_glob - k_glob]], alternative="two-sided")
        print(f"\nSensitivity (confirmed-Egyptian only, n={n_conf}):")
        print(f"  Adoption = {k_conf}/{n_conf} = {r_conf*100:.1f}%  {fmt_ci(lo_c,hi_c)}")
        print(f"  Fisher p vs global = {p_conf:.4e}")
else:
    print("\n(owner_confidence column not found — skipping sensitivity analysis)")
    n_conf = k_conf = r_conf = lo_c = hi_c = p_conf = None

# Subgroup comparisons (ecosystem, language, size) for BH correction
print("\nSubgroup comparisons (Egyptian vs Global, Fisher's exact):")
subgroup_rows = []
all_pvals = []

for dim in ["ecosystem_type", "primary_language", "size_stratum"]:
    if dim not in egypt_df.columns or dim not in global_df.columns:
        continue
    eg_vals = set(egypt_df[dim].dropna().unique())
    gl_vals = set(global_df[dim].dropna().unique())
    for val in sorted(eg_vals & gl_vals):
        eg_sub = egypt_df[egypt_df[dim] == val]
        gl_sub = global_df[global_df[dim] == val]
        n_e = len(eg_sub); k_e = eg_sub["agent_adopted_multi"].sum()
        n_g = len(gl_sub); k_g = gl_sub["agent_adopted_multi"].sum()
        if n_e < 5 or n_g < 5:
            continue
        _, p_sub = fisher_exact([[k_e, n_e - k_e], [k_g, n_g - k_g]], alternative="two-sided")
        all_pvals.append(p_sub)
        subgroup_rows.append({"dim": dim, "value": str(val),
                               "n_egypt": n_e, "k_egypt": k_e, "rate_egypt": round(k_e/n_e, 4),
                               "n_global": n_g, "k_global": k_g, "rate_global": round(k_g/n_g, 4),
                               "p_raw": round(p_sub, 6)})

adj_pvals = bh_correct(all_pvals)
for i, row in enumerate(subgroup_rows):
    row["p_bh"] = round(adj_pvals[i], 6)
    sig = "**" if row["p_bh"] < 0.05 else ""
    print(f"  {row['dim']:<20} {row['value']:<20} "
          f"EG {row['rate_egypt']*100:.0f}% ({row['n_egypt']}) vs "
          f"GL {row['rate_global']*100:.0f}% ({row['n_global']})  "
          f"p_raw={row['p_raw']:.4f}  p_bh={row['p_bh']:.4f} {sig}")

# Save RQ3
rq3_main = {
    "n_global": int(n_glob), "k_global": int(k_glob), "rate_global": round(r_glob, 4),
    "ci_global": [round(lo_g, 4), round(hi_g, 4)],
    "n_egypt": int(n_egy), "k_egypt": int(k_egy), "rate_egypt": round(r_egy, 4),
    "ci_egypt": [round(lo_e, 4), round(hi_e, 4)],
    "gap_pp": round((r_glob - r_egy) * 100, 2),
    "fisher_oddsratio": round(oddsratio, 4),
    "fisher_p": float(p_fisher),
    "mwu_U": float(u_stat),
    "mwu_p": float(p_mwu),
    "mwu_r_rb": round(r_rb, 4),
    "median_signal_count_egypt": float(sc_egy.median()),
    "median_signal_count_global": float(sc_glob.median()),
}
with open(DATA6 / "rq3_comparison.json", "w") as f:
    json.dump(rq3_main, f, indent=2)

pd.DataFrame(subgroup_rows).to_csv(DATA6 / "rq3_subgroup_tests.csv", index=False)
print(f"\n[saved] rq3_comparison.json, rq3_subgroup_tests.csv")

# ─────────────────────────────────────────────────────────────────────────────
# Final summary
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 65)
print("SUMMARY")
print("=" * 65)
print(f"\nRQ1: Global multi-signal adoption = {r_glob*100:.1f}% "
      f"(95%CI {fmt_ci(lo_g,hi_g)})")
print(f"RQ2: Undercounting delta = {delta_pp:.1f} pp  "
      f"(McNemar p = {p_mcnemar:.4e})")
print(f"RQ3: Egyptian adoption = {r_egy*100:.1f}% vs Global {r_glob*100:.1f}%  "
      f"gap = {(r_glob-r_egy)*100:.1f} pp")
print(f"     Fisher's exact p = {p_fisher:.4e}  "
      f"OR = {oddsratio:.3f}")
print(f"     Mann-Whitney U p = {p_mwu:.4e}  "
      f"r_rb = {r_rb:.3f}")
print()

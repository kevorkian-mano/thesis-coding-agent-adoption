#!/usr/bin/env python3
"""
Stage 4d -- Repo-Size Analysis: Three Sizing Approaches
=========================================================
Compares AI coding agent adoption rates across three independent definitions
of repository "size":

  Approach A — Stars (popularity proxy)
      Thresholds: fixed, inherited from Stage 1a corpus filter
        small   : <= 50 stars
        medium  : 51 – 500 stars
        large   : > 500 stars

  Approach B — Commits (development activity proxy)
      Thresholds: corpus tertiles (33rd / 66th percentile of the full corpus)
        small   : <= P33 commits
        medium  : P33 < commits <= P66
        large   : > P66 commits

  Approach C — Code volume (lang_bytes, JS+TS bytes)
      Thresholds: corpus tertiles (33rd / 66th percentile of the full corpus)
        small   : <= P33 bytes
        medium  : P33 < bytes <= P66
        large   : > P66 bytes
      Note: lang_bytes are measured by GitHub Linguist, which excludes
      node_modules/, dist/, vendor/, and generated files.

For each approach the script reports:
  - stratum thresholds and corpus distribution (count + %)
  - adoption rate per stratum with Wilson 95% CI
  - comparison summary table across all three approaches

Input
-----
  data/stage4/corpus_with_country.csv   -- produced by stage4a

Output
------
  data/stage4/size_stars.csv            -- Approach A breakdown
  data/stage4/size_commits.csv          -- Approach B breakdown
  data/stage4/size_langbytes.csv        -- Approach C breakdown
  data/stage4/size_comparison.csv       -- side-by-side summary (all three)

Usage
-----
  python3 scripts/stage4/stage4d_size_analysis.py
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



import math
import pandas as pd
from pathlib import Path

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parents[2]
CORPUS_FILE = ROOT / "data" / "stage4" / "corpus_with_country.csv"
OUT_DIR     = ROOT / "data" / "stage4"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ── helpers ───────────────────────────────────────────────────────────────────

def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score 95% CI for a proportion. Returns (lower, upper) in [0, 1]."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denom  = 1 + z ** 2 / n
    centre = (p + z ** 2 / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def breakdown(df: pd.DataFrame, stratum_col: str,
              order: list) -> pd.DataFrame:
    """
    Compute adoption counts, rates, and Wilson CIs for each stratum.
    order: list of stratum labels in desired display order.
    """
    rows = []
    for label in order:
        grp     = df[df[stratum_col] == label]
        n       = len(grp)
        n_ag    = (grp["adoption_label"] == "agentic").sum()
        n_ai    = (grp["adoption_label"] == "ai_assisted").sum()
        n_adpt  = n_ag + n_ai
        n_none  = (grp["adoption_label"] == "none").sum()
        rate    = n_adpt / n if n else 0.0
        ag_rate = n_ag   / n if n else 0.0
        ci_lo, ci_hi = wilson_ci(n_adpt, n)
        rows.append({
            "stratum":        label,
            "total_repos":    n,
            "pct_corpus":     round(n / len(df) * 100, 1),
            "agentic":        int(n_ag),
            "ai_assisted":    int(n_ai),
            "adopted":        int(n_adpt),
            "none":           int(n_none),
            "adoption_rate":  round(rate    * 100, 2),
            "agentic_rate":   round(ag_rate * 100, 2),
            "ci_lower":       round(ci_lo   * 100, 2),
            "ci_upper":       round(ci_hi   * 100, 2),
        })
    return pd.DataFrame(rows)


def print_breakdown(df: pd.DataFrame, title: str, thresholds: str):
    sep = "─" * 72
    print(f"\n{sep}")
    print(f"  {title}")
    print(f"  Thresholds: {thresholds}")
    print(sep)
    hdr = (f"  {'Stratum':<10} {'Repos':>7} {'%Corp':>6}  "
           f"{'Adopted':>8} {'Rate%':>7}  {'95% CI':>15}  {'Agentic%':>9}")
    print(hdr)
    print(f"  {'-' * 68}")
    for _, row in df.iterrows():
        ci_str = f"[{row['ci_lower']:.1f}, {row['ci_upper']:.1f}]"
        print(f"  {row['stratum']:<10} {row['total_repos']:>7,} "
              f"{row['pct_corpus']:>6.1f}%  "
              f"{row['adopted']:>8,} {row['adoption_rate']:>7.1f}%  "
              f"{ci_str:>15}  {row['agentic_rate']:>9.1f}%")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("Stage 4d -- Repo-Size Analysis: Three Sizing Approaches")
    print("=" * 72)

    if not CORPUS_FILE.exists():
        raise SystemExit(f"Missing: {CORPUS_FILE}\nRun stage4a first.")

    corpus = pd.read_csv(CORPUS_FILE, low_memory=False)
    n_total = len(corpus)
    print(f"Corpus loaded : {n_total:,} repos\n")

    # ══════════════════════════════════════════════════════════════════════════
    # Approach A — Stars (fixed thresholds from Stage 1a)
    # ══════════════════════════════════════════════════════════════════════════

    STAR_SMALL  = 50
    STAR_MEDIUM = 500

    def star_stratum(s):
        if s <= STAR_SMALL:  return "small"
        if s <= STAR_MEDIUM: return "medium"
        return "large"

    corpus["size_stars"] = corpus["stars"].apply(star_stratum)

    stars_df = breakdown(corpus, "size_stars", ["small", "medium", "large"])
    stars_threshold = (f"small <= {STAR_SMALL} stars  |  "
                       f"medium {STAR_SMALL+1}–{STAR_MEDIUM}  |  "
                       f"large > {STAR_MEDIUM}")
    print_breakdown(stars_df, "Approach A — Stars (popularity proxy)",
                    stars_threshold)
    stars_df.to_csv(OUT_DIR / "size_stars.csv", index=False)
    print(f"  Saved: size_stars.csv")

    # ══════════════════════════════════════════════════════════════════════════
    # Approach B — Commits (development activity proxy, corpus tertiles)
    # ══════════════════════════════════════════════════════════════════════════

    p33_commits = int(corpus["commits"].quantile(0.33))
    p66_commits = int(corpus["commits"].quantile(0.66))

    def commit_stratum(c):
        if c <= p33_commits: return "small"
        if c <= p66_commits: return "medium"
        return "large"

    corpus["size_commits"] = corpus["commits"].apply(commit_stratum)

    commits_df = breakdown(corpus, "size_commits", ["small", "medium", "large"])
    commits_threshold = (f"small <= {p33_commits} commits (P33)  |  "
                         f"medium {p33_commits+1}–{p66_commits} (P66)  |  "
                         f"large > {p66_commits}")
    print_breakdown(commits_df, "Approach B — Commits (development activity proxy)",
                    commits_threshold)
    commits_df.to_csv(OUT_DIR / "size_commits.csv", index=False)
    print(f"  Saved: size_commits.csv")

    # Print corpus percentile reference
    print(f"\n  Commit distribution reference:")
    for pct in [25, 33, 50, 66, 75, 90, 95]:
        val = int(corpus["commits"].quantile(pct / 100))
        print(f"    P{pct:<3}: {val:>6} commits")

    # ══════════════════════════════════════════════════════════════════════════
    # Approach C — Lang bytes (code volume proxy, corpus tertiles)
    # ══════════════════════════════════════════════════════════════════════════

    p33_bytes = int(corpus["lang_bytes"].quantile(0.33))
    p66_bytes = int(corpus["lang_bytes"].quantile(0.66))

    def bytes_stratum(b):
        if b <= p33_bytes: return "small"
        if b <= p66_bytes: return "medium"
        return "large"

    corpus["size_langbytes"] = corpus["lang_bytes"].apply(bytes_stratum)

    bytes_df = breakdown(corpus, "size_langbytes", ["small", "medium", "large"])
    bytes_threshold = (f"small <= {p33_bytes/1e6:.2f} MB (P33)  |  "
                       f"medium {p33_bytes/1e6:.2f}–{p66_bytes/1e6:.2f} MB (P66)  |  "
                       f"large > {p66_bytes/1e6:.2f} MB")
    print_breakdown(bytes_df, "Approach C — Code volume / lang_bytes (JS+TS bytes)",
                    bytes_threshold)
    bytes_df.to_csv(OUT_DIR / "size_langbytes.csv", index=False)
    print(f"  Saved: size_langbytes.csv")

    print(f"\n  Lang bytes distribution reference:")
    for pct in [25, 33, 50, 66, 75, 90, 95]:
        val = int(corpus["lang_bytes"].quantile(pct / 100))
        print(f"    P{pct:<3}: {val/1e6:>8.3f} MB  ({val:,} bytes)")

    # ══════════════════════════════════════════════════════════════════════════
    # Comparison summary — all three approaches side by side
    # ══════════════════════════════════════════════════════════════════════════

    print(f"\n{'═' * 72}")
    print("  COMPARISON SUMMARY — adoption rate (%) per stratum, all approaches")
    print(f"{'═' * 72}")
    hdr2 = (f"  {'Approach':<35} {'Small':>8}  {'Medium':>8}  {'Large':>8}  "
            f"{'Range pp':>9}")
    print(hdr2)
    print(f"  {'-' * 68}")

    for name, df in [
        ("A — Stars (<=50 / 51-500 / >500)", stars_df),
        ("B — Commits (tertiles)", commits_df),
        ("C — Code volume / lang_bytes (tertiles)", bytes_df),
    ]:
        rates = df.set_index("stratum")["adoption_rate"]
        s = rates.get("small",  float("nan"))
        m = rates.get("medium", float("nan"))
        l = rates.get("large",  float("nan"))
        rng = l - s if not (math.isnan(s) or math.isnan(l)) else float("nan")
        print(f"  {name:<35} {s:>7.1f}%  {m:>7.1f}%  {l:>7.1f}%  "
              f"  {rng:>+7.1f} pp")

    # Save comparison CSV
    comparison_rows = []
    for approach, label_name, df in [
        ("A_stars",      "stars",      stars_df),
        ("B_commits",    "commits",    commits_df),
        ("C_langbytes",  "lang_bytes", bytes_df),
    ]:
        for _, row in df.iterrows():
            comparison_rows.append({
                "approach":       approach,
                "metric":         label_name,
                "stratum":        row["stratum"],
                "total_repos":    row["total_repos"],
                "pct_corpus":     row["pct_corpus"],
                "adoption_rate":  row["adoption_rate"],
                "agentic_rate":   row["agentic_rate"],
                "ci_lower":       row["ci_lower"],
                "ci_upper":       row["ci_upper"],
            })
    comparison_df = pd.DataFrame(comparison_rows)
    comparison_df.to_csv(OUT_DIR / "size_comparison.csv", index=False)
    print(f"\n  Saved: size_comparison.csv")

    print()
    print("Stage 4d complete.")


if __name__ == "__main__":
    main()

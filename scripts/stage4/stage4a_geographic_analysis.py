#!/usr/bin/env python3
"""
Stage 4a -- Geographic Adoption Analysis
==========================================
Joins the final detection corpus (corpus_detected_full_v2.csv, produced by
stage3d) with the owner location table (owner_locations_all.csv, produced by
stage2a + stage2b) to build a per-country adoption summary.

For every country that has >= MIN_REPOS repositories in the corpus:
  - total repos in that country
  - repos with any AI signal (agentic + ai_assisted)
  - repos classified strictly agentic
  - adoption rate % = (agentic + ai_assisted) / total
  - agentic-only rate % = agentic / total
  - Wilson 95 % confidence interval on the adoption rate
  - dominant location-inference confidence level for that country's owners

Repos whose owner could not be attributed to any country (label
"not_specified") are kept in the corpus_with_country.csv output and are
counted in the global totals printed at the end, but are excluded from the
per-country ranking table.  This is consistent with the methodology of
Wachs et al. (2022), who document that ~60 % of GitHub developers leave the
location field blank.

Input
-----
  data/stage3/corpus_detected_full_v2.csv   -- final classified corpus
  data/stage2/owner_locations_all.csv       -- owner_login -> inferred_country

Output
------
  data/stage4/corpus_with_country.csv
      Full corpus (all 60 k repos) with a 'country' column added.
      Used by stage4b for RQ1 / RQ2 and by stage4c for breakdowns.

  data/stage4/country_adoption.csv
      One row per eligible country, sorted by adoption_rate descending.
      Columns: country, total_repos, adopted, agentic_only, ai_assisted_only,
               adoption_rate, agentic_rate, ci_lower, ci_upper, confidence_mode

Usage
-----
  python3 scripts/stage4/stage4a_geographic_analysis.py
"""

import math
import pandas as pd
from pathlib import Path

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT           = Path(__file__).resolve().parents[2]
DETECTED_FILE  = ROOT / "data" / "stage3" / "corpus_detected_full_v2.csv"
LOCATIONS_FILE = ROOT / "data" / "stage2" / "owner_locations_all.csv"
OUT_DIR        = ROOT / "data" / "stage4"
OUT_CORPUS     = OUT_DIR / "corpus_with_country.csv"
OUT_COUNTRY    = OUT_DIR / "country_adoption.csv"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MIN_REPOS = 30   # minimum repos per country to appear in the ranking


# ── helpers ───────────────────────────────────────────────────────────────────

def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score 95 % CI for a proportion. Returns (lower, upper) in [0, 1]."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denom  = 1 + z ** 2 / n
    centre = (p + z ** 2 / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("Stage 4a -- Geographic Adoption Analysis")
    print("=" * 60)

    # ── 1. Load inputs ────────────────────────────────────────────────────────
    if not DETECTED_FILE.exists():
        raise SystemExit(
            f"Missing: {DETECTED_FILE}\n"
            "Run stage3d (reclassification) first."
        )
    corpus = pd.read_csv(DETECTED_FILE, low_memory=False)
    print(f"Corpus loaded       : {len(corpus):,} repos")

    if not LOCATIONS_FILE.exists():
        raise SystemExit(
            f"Missing: {LOCATIONS_FILE}\n"
            "Run stage2a + stage2b (location inference) first."
        )
    locations = pd.read_csv(LOCATIONS_FILE)
    n_located = (locations["inferred_country"] != "not_specified").sum()
    print(f"Owner locations     : {len(locations):,} owners "
          f"({n_located:,} with country = "
          f"{n_located / len(locations) * 100:.1f}%)")

    # ── 2. Join: add country column to every repo ─────────────────────────────
    loc_map = locations.set_index("owner_login")["inferred_country"].to_dict()
    corpus["country"] = corpus["owner_login"].map(loc_map).fillna("not_specified")

    # Build a confidence lookup for later per-country mode computation
    conf_map = locations.set_index("owner_login")["confidence"].to_dict()
    corpus["owner_confidence"] = corpus["owner_login"].map(conf_map).fillna("unknown")

    corpus.to_csv(OUT_CORPUS, index=False)
    print(f"\nSaved corpus with country -> {OUT_CORPUS.name}")

    # ── 3. Global adoption summary (all repos, including unlocated) ───────────
    n_total      = len(corpus)
    n_agentic    = (corpus["adoption_label"] == "agentic").sum()
    n_ai_assist  = (corpus["adoption_label"] == "ai_assisted").sum()
    n_none       = (corpus["adoption_label"] == "none").sum()
    n_adopted    = n_agentic + n_ai_assist

    print()
    print("Global adoption (full corpus, all 60 k repos):")
    print(f"  Agentic      : {n_agentic:>6,}  ({n_agentic / n_total * 100:.1f}%)")
    print(f"  AI-assisted  : {n_ai_assist:>6,}  ({n_ai_assist / n_total * 100:.1f}%)")
    print(f"  None         : {n_none:>6,}  ({n_none / n_total * 100:.1f}%)")
    print(f"  Total adopted: {n_adopted:>6,}  ({n_adopted / n_total * 100:.1f}%)")

    # ── 4. Coverage breakdown (located vs unlocated repos) ────────────────────
    known   = corpus[corpus["country"] != "not_specified"]
    unknown = corpus[corpus["country"] == "not_specified"]
    print()
    print("Location coverage:")
    print(f"  Repos with country : {len(known):>6,}  ({len(known) / n_total * 100:.1f}%)")
    print(f"  Repos no country   : {len(unknown):>6,}  ({len(unknown) / n_total * 100:.1f}%)")

    # ── 5. Per-country aggregation ────────────────────────────────────────────
    rows = []
    for country, grp in known.groupby("country"):
        total      = len(grp)
        if total < MIN_REPOS:
            continue
        n_ag   = (grp["adoption_label"] == "agentic").sum()
        n_ai   = (grp["adoption_label"] == "ai_assisted").sum()
        n_adpt = n_ag + n_ai
        rate   = n_adpt / total
        ag_rt  = n_ag   / total
        ci_lo, ci_hi = wilson_ci(n_adpt, total)

        # Most common confidence level among this country's owners
        conf_series  = grp["owner_confidence"]
        conf_mode    = conf_series.mode().iloc[0] if len(conf_series) else "unknown"

        rows.append({
            "country":        country,
            "total_repos":    total,
            "adopted":        int(n_adpt),
            "agentic_only":   int(n_ag),
            "ai_assisted_only": int(n_ai),
            "adoption_rate":  round(rate * 100, 2),
            "agentic_rate":   round(ag_rt * 100, 2),
            "ci_lower":       round(ci_lo * 100, 2),
            "ci_upper":       round(ci_hi * 100, 2),
            "confidence_mode": conf_mode,
        })

    country_df = (
        pd.DataFrame(rows)
        .sort_values("adoption_rate", ascending=False)
        .reset_index(drop=True)
    )
    country_df.to_csv(OUT_COUNTRY, index=False)

    # ── 6. Print ranking table ────────────────────────────────────────────────
    print()
    print(f"Countries with >= {MIN_REPOS} repos: {len(country_df)}")
    print()
    hdr = (f"{'Rank':<5} {'Country':<25} {'Repos':>6} "
           f"{'Adopted':>8} {'Rate%':>7} {'95% CI':>17} {'Agentic%':>9}")
    print(hdr)
    print("-" * len(hdr))
    for rank, row in country_df.iterrows():
        ci_str = f"[{row['ci_lower']:.1f},{row['ci_upper']:.1f}]"
        print(f"{rank + 1:<5} {row['country']:<25} {row['total_repos']:>6,} "
              f"{row['adopted']:>8,} {row['adoption_rate']:>7.1f}% "
              f"{ci_str:>17} {row['agentic_rate']:>9.1f}%")

    # Global rate among located repos only (used as benchmark in stage4b RQ3)
    known_adopted = (known["adoption_label"].isin(["agentic", "ai_assisted"])).sum()
    print()
    print(f"Global adoption (located repos only): "
          f"{known_adopted:,}/{len(known):,} = "
          f"{known_adopted / len(known) * 100:.1f}%")

    print()
    print(f"Saved: {OUT_COUNTRY}")
    print(f"Saved: {OUT_CORPUS}")


if __name__ == "__main__":
    main()

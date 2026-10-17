#!/usr/bin/env python3
"""
Stage 4a -- Geographic Adoption Analysis
==========================================
Joins corpus_detected_full.csv (all 60,129 repos with adoption labels)
with owner_locations_all.csv (owner -> inferred_country) to produce
a per-country adoption summary.

For each country with >= MIN_REPOS repositories in the corpus:
  - total repos
  - repos with any AI signal (ai_assisted + agentic)
  - repos classified agentic
  - adoption rate (%) = (ai_assisted + agentic) / total
  - agentic rate (%) = agentic / total
  - Wilson 95% confidence interval for adoption rate

Countries are ranked by adoption rate (descending).

Output
------
data/stage4/country_adoption.csv
  country, total_repos, adopted, agentic_only, adoption_rate,
  agentic_rate, ci_lower, ci_upper, confidence_median

data/stage4/corpus_with_country.csv
  Full corpus with country column added (for per-repo analysis).

Usage
-----
  python3 scripts/stage4/stage4a_geographic_analysis.py
"""

import math
import pandas as pd
from pathlib import Path

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT          = Path(__file__).resolve().parents[2]
DETECTED_FILE = ROOT / "data" / "stage3" / "corpus_detected_full.csv"
LOCATIONS_FILE= ROOT / "data" / "stage2" / "owner_locations_all.csv"
OUT_DIR       = ROOT / "data" / "stage4"
OUT_COUNTRY   = OUT_DIR / "country_adoption.csv"
OUT_CORPUS    = OUT_DIR / "corpus_with_country.csv"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MIN_REPOS = 30   # minimum repos per country to include in ranking


def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a proportion. Returns (lower, upper) in [0,1]."""
    if n == 0:
        return 0.0, 0.0
    p_hat = successes / n
    denom = 1 + z**2 / n
    centre = (p_hat + z**2 / (2 * n)) / denom
    margin = (z * math.sqrt(p_hat * (1 - p_hat) / n + z**2 / (4 * n**2))) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def main():
    print("Stage 4a -- Geographic Adoption Analysis")
    print("=" * 55)

    # Load detected corpus
    if not DETECTED_FILE.exists():
        raise SystemExit(f"Missing: {DETECTED_FILE}\nRun stage3c first.")
    detected = pd.read_csv(DETECTED_FILE, low_memory=False)
    print(f"Detected corpus    : {len(detected):,} repos")

    # Load owner locations
    if not LOCATIONS_FILE.exists():
        raise SystemExit(f"Missing: {LOCATIONS_FILE}\nRun stage2a + stage2b first.")
    locations = pd.read_csv(LOCATIONS_FILE)
    print(f"Owner locations    : {len(locations):,} owners")
    located_pct = (locations["inferred_country"] != "not_specified").mean() * 100
    print(f"Country labelled   : {located_pct:.1f}% of owners")

    # Join: map each repo's owner to a country
    loc_map = locations.set_index("owner_login")["inferred_country"].to_dict()
    detected["country"] = detected["owner_login"].map(loc_map).fillna("not_specified")

    corpus_with_country = detected.copy()
    corpus_with_country.to_csv(OUT_CORPUS, index=False)
    print(f"\nSaved corpus with country: {OUT_CORPUS}")

    # Filter to repos with a known country
    known = detected[detected["country"] != "not_specified"].copy()
    print(f"\nRepos with country : {len(known):,} ({len(known)/len(detected)*100:.1f}%)")
    print(f"Repos unknown      : {len(detected) - len(known):,}")

    # Per-country aggregation
    rows = []
    for country, grp in known.groupby("country"):
        total   = len(grp)
        if total < MIN_REPOS:
            continue
        adopted  = (grp["adoption_label"].isin(["agentic", "ai_assisted"])).sum()
        agentic  = (grp["adoption_label"] == "agentic").sum()
        rate     = adopted / total
        ag_rate  = agentic / total
        ci_lo, ci_hi = wilson_ci(adopted, total)
        # median confidence level of owner location inference for this group
        conf_vals = locations[locations["owner_login"].isin(grp["owner_login"])]["confidence"].value_counts()
        conf_median = conf_vals.idxmax() if len(conf_vals) else "unknown"
        rows.append({
            "country":         country,
            "total_repos":     total,
            "adopted":         adopted,
            "agentic_only":    agentic,
            "adoption_rate":   round(rate * 100, 2),
            "agentic_rate":    round(ag_rate * 100, 2),
            "ci_lower":        round(ci_lo * 100, 2),
            "ci_upper":        round(ci_hi * 100, 2),
            "confidence_mode": conf_median,
        })

    country_df = pd.DataFrame(rows).sort_values("adoption_rate", ascending=False).reset_index(drop=True)
    country_df.to_csv(OUT_COUNTRY, index=False)

    # ── Print ranking ──────────────────────────────────────────────────────────
    print(f"\nCountries with >= {MIN_REPOS} repos: {len(country_df)}")
    print()
    print(f"{'Rank':<5} {'Country':<25} {'Repos':>6} {'Adopted':>8} {'Rate%':>7} {'95% CI':>16} {'Agentic%':>9}")
    print("-" * 82)
    for rank, row in country_df.iterrows():
        ci_str = f"[{row['ci_lower']:.1f}, {row['ci_upper']:.1f}]"
        print(f"{rank+1:<5} {row['country']:<25} {row['total_repos']:>6,} "
              f"{row['adopted']:>8,} {row['adoption_rate']:>7.1f}% "
              f"{ci_str:>16} {row['agentic_rate']:>9.1f}%")

    print()
    # Global benchmark
    all_adopted = (known["adoption_label"].isin(["agentic", "ai_assisted"])).sum()
    global_rate = all_adopted / len(known) * 100
    print(f"Global adoption (repos with country): {all_adopted:,}/{len(known):,} = {global_rate:.1f}%")

    print(f"\nSaved: {OUT_COUNTRY}")
    print(f"Saved: {OUT_CORPUS}")


if __name__ == "__main__":
    main()

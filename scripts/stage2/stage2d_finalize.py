#!/usr/bin/env python3
"""
Stage 2d — Finalize Owner Classification & Egyptian Sub-corpus
===============================================================
Reads owner_signals_full.csv (all 9 signals applied) and sample_corpus.csv.
No API calls — pure computation. Runs in seconds.

Actions:
  1. Apply final classification to all owners (all 9 signals have now been applied).
  2. Add confidence and location_source columns.
  3. Produce owners_final.csv — definitive owner classification table.
  4. Produce egypt_corpus.csv — repos whose owner is egyptian_confirmed or
     egyptian_probable (the Egyptian sub-corpus for Stage 5 / RQ3).
  5. Produce coverage_stats.csv — methodology coverage numbers for the thesis.

Classification thresholds (final, same as pipeline design):
  Score ≥ 10              → egyptian_confirmed   (in Egypt corpus)
  Score 5–9               → egyptian_probable    (in Egypt corpus)
  Score 1–4 + ≥2 signals  → egyptian_probable    (in Egypt corpus)
  Score 1–4 + 1 signal    → unconfirmed          (NOT in Egypt corpus — weak evidence)
  Score 0                 → unclassified         (NOT in Egypt corpus — no evidence)
  S1 hard negative        → not_egyptian         (NOT in Egypt corpus)

INPUTS
------
  data/stage2/owner_signals_full.csv   — Stage 2c output
  data/stage1/sample_corpus.csv        — repo metadata

OUTPUTS
-------
  data/stage2/owners_final.csv         — all owners, final classification
  data/stage2/egypt_corpus.csv         — Egyptian-owner repos (from global sample)
  data/stage2/coverage_stats.csv       — coverage breakdown (thesis table)

USAGE
-----
  python3 stage2d_finalize.py
"""

import sys
import json
import pandas as pd
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR         = Path(__file__).parent
DATA_DIR           = SCRIPT_DIR / "../../data"
SIGNALS_FULL_CSV   = DATA_DIR / "stage2/owner_signals_full.csv"
CORPUS_CSV         = DATA_DIR / "stage1/sample_corpus.csv"
OWNERS_FINAL_CSV   = DATA_DIR / "stage2/owners_final.csv"
EGYPT_CORPUS_CSV   = DATA_DIR / "stage2/egypt_corpus.csv"
COVERAGE_STATS_CSV = DATA_DIR / "stage2/coverage_stats.csv"

SCORE_COLS = [
    "s1_score", "s2_score", "s3_score", "s4_score",
    "s5_score", "s6_score", "s7_score", "s8_score", "s9_score",
]


# ── Classification ─────────────────────────────────────────────────────────────

def final_classification(total_score: int, hard_negative: bool,
                         signals_fired: int) -> str:
    """Definitive classification after all 9 signals have been applied."""
    if hard_negative:
        return "not_egyptian"
    if total_score >= 10:
        return "egyptian_confirmed"
    if total_score >= 5:
        return "egyptian_probable"
    if total_score >= 1:
        return "egyptian_probable" if signals_fired >= 2 else "unconfirmed"
    return "unclassified"


def confidence_label(classification: str) -> str:
    return {
        "egyptian_confirmed": "high",
        "egyptian_probable":  "medium",
        "unconfirmed":        "low_positive",
        "unclassified":       "none",
        "not_egyptian":       "none",
    }.get(classification, "none")


def location_source(row) -> str:
    """
    Primary source of location evidence, in priority order.
    Used in the thesis methodology section to describe how owners were identified.
    """
    if row["s1_score"] > 0:
        return "direct"        # profile location field
    if any(row[c] > 0 for c in ["s2_score", "s3_score", "s4_score"]):
        return "profile"       # bio, company, or email
    if any(row[c] > 0 for c in ["s5_score", "s6_score"]):
        return "social"        # org membership or network inference
    if any(row[c] > 0 for c in ["s7_score", "s8_score", "s9_score"]):
        return "repository"    # contributor consensus, Arabic README, Egyptian patterns
    return "none"


def in_egypt_corpus(classification: str) -> bool:
    return classification in ("egyptian_confirmed", "egyptian_probable")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    for path in [SIGNALS_FULL_CSV, CORPUS_CSV]:
        if not path.exists():
            sys.exit(f"ERROR: {path} not found. Run Stage 3a first.")

    OWNERS_FINAL_CSV.parent.mkdir(parents=True, exist_ok=True)

    owners_df = pd.read_csv(SIGNALS_FULL_CSV)
    corpus_df = pd.read_csv(CORPUS_CSV)

    print(f"Loaded {len(owners_df):,} owners from Stage 3a.")
    print(f"Loaded {len(corpus_df):,} repos from sample corpus.")

    # ── 1. Ensure score columns are numeric ───────────────────────────────────
    for col in SCORE_COLS:
        owners_df[col] = pd.to_numeric(owners_df[col], errors="coerce").fillna(0).astype(int)

    owners_df["total_score"]   = owners_df[SCORE_COLS].sum(axis=1)
    owners_df["signals_fired"] = (owners_df[SCORE_COLS] > 0).sum(axis=1)
    owners_df["hard_negative"] = owners_df["hard_negative"].astype(bool)

    # ── 2. Apply final classification ─────────────────────────────────────────
    owners_df["classification"] = owners_df.apply(
        lambda r: final_classification(
            int(r["total_score"]),
            bool(r["hard_negative"]),
            int(r["signals_fired"]),
        ),
        axis=1,
    )

    owners_df["confidence"]      = owners_df["classification"].map(confidence_label)
    owners_df["location_source"] = owners_df.apply(location_source, axis=1)
    owners_df["in_egypt_corpus"] = owners_df["classification"].map(in_egypt_corpus)
    owners_df["needs_more"]      = False   # all signals applied — no more stages

    # ── 3. Save owners_final.csv ──────────────────────────────────────────────
    col_order = [
        "login", "name", "location_raw", "bio", "company", "email", "website",
        *SCORE_COLS,
        "total_score", "signals_fired", "hard_negative",
        "classification", "confidence", "location_source",
        "in_egypt_corpus", "needs_more", "evidence_json",
    ]
    # Only keep columns that exist (stage 3a may not have added all profile cols)
    col_order = [c for c in col_order if c in owners_df.columns]
    owners_df[col_order].to_csv(OWNERS_FINAL_CSV, index=False)
    print(f"\nSaved owners_final.csv ({len(owners_df):,} rows)")

    # ── 4. Build egypt_corpus.csv ─────────────────────────────────────────────
    egyptian_logins = set(
        owners_df.loc[owners_df["in_egypt_corpus"], "login"].astype(str)
    )

    egypt_corpus_df = corpus_df[
        corpus_df["owner_login"].astype(str).isin(egyptian_logins)
    ].copy()

    # Enrich with owner classification columns
    owner_meta = owners_df[[
        "login", "classification", "confidence", "total_score",
        "location_source", "evidence_json",
    ]].rename(columns={"login": "owner_login"})

    egypt_corpus_df = egypt_corpus_df.merge(
        owner_meta, on="owner_login", how="left"
    )

    egypt_corpus_df.to_csv(EGYPT_CORPUS_CSV, index=False)
    print(f"Saved egypt_corpus.csv ({len(egypt_corpus_df):,} repos)")

    # ── 5. Coverage stats ──────────────────────────────────────────────────────
    stats_rows = []
    total_owners = len(owners_df)
    total_repos  = len(corpus_df)

    # 5a — Overall owner classification
    cls_counts = owners_df["classification"].value_counts()
    for label in ["egyptian_confirmed", "egyptian_probable",
                  "unconfirmed", "unclassified", "not_egyptian"]:
        n   = int(cls_counts.get(label, 0))
        pct = n / total_owners * 100
        stats_rows.append({
            "dimension":      "overall_classification",
            "category":       label,
            "owner_count":    n,
            "owner_pct":      round(pct, 2),
            "repo_count":     None,
            "repo_pct":       None,
        })

    # 5b — Location source breakdown (how were Egyptian owners identified?)
    src_counts = owners_df.loc[
        owners_df["in_egypt_corpus"], "location_source"
    ].value_counts()
    eg_total = owners_df["in_egypt_corpus"].sum()
    for src in ["direct", "profile", "social", "repository"]:
        n   = int(src_counts.get(src, 0))
        pct = n / eg_total * 100 if eg_total else 0
        stats_rows.append({
            "dimension":      "egypt_location_source",
            "category":       src,
            "owner_count":    n,
            "owner_pct":      round(pct, 2),
            "repo_count":     None,
            "repo_pct":       None,
        })

    # 5c — Per-signal contribution (how many Egyptian owners did each signal discover?)
    for col in SCORE_COLS:
        n = int((owners_df["in_egypt_corpus"] & (owners_df[col] > 0)).sum())
        pct = n / eg_total * 100 if eg_total else 0
        stats_rows.append({
            "dimension":      "signal_contribution",
            "category":       col,
            "owner_count":    n,
            "owner_pct":      round(pct, 2),
            "repo_count":     None,
            "repo_pct":       None,
        })

    # 5d — Egypt corpus by ecosystem
    if "ecosystem_type" in corpus_df.columns:
        corpus_with_cls = corpus_df.merge(
            owners_df[["login", "classification", "in_egypt_corpus"]].rename(
                columns={"login": "owner_login"}
            ),
            on="owner_login",
            how="left",
        )
        for eco, grp in corpus_with_cls.groupby("ecosystem_type"):
            total_eco   = len(grp)
            egypt_eco   = int(grp["in_egypt_corpus"].fillna(False).sum())
            uncls_eco   = int((grp["classification"] == "unclassified").sum())
            stats_rows.append({
                "dimension":   "ecosystem",
                "category":    eco,
                "owner_count": None,
                "owner_pct":   None,
                "repo_count":  egypt_eco,
                "repo_pct":    round(egypt_eco / total_eco * 100, 2),
            })
            stats_rows.append({
                "dimension":   "ecosystem_unclassified",
                "category":    eco,
                "owner_count": None,
                "owner_pct":   None,
                "repo_count":  uncls_eco,
                "repo_pct":    round(uncls_eco / total_eco * 100, 2),
            })

    # 5e — Egypt corpus by size_stratum
    if "size_stratum" in corpus_df.columns and "ecosystem_type" in corpus_df.columns:
        for (eco, size), grp in corpus_with_cls.groupby(
            ["ecosystem_type", "size_stratum"]
        ):
            total_s  = len(grp)
            egypt_s  = int(grp["in_egypt_corpus"].fillna(False).sum())
            stats_rows.append({
                "dimension":   "ecosystem_x_size",
                "category":    f"{eco}__{size}",
                "owner_count": None,
                "owner_pct":   None,
                "repo_count":  egypt_s,
                "repo_pct":    round(egypt_s / total_s * 100, 2),
            })

    coverage_df = pd.DataFrame(stats_rows)
    coverage_df.to_csv(COVERAGE_STATS_CSV, index=False)
    print(f"Saved coverage_stats.csv ({len(coverage_df):,} rows)")

    # ── Summary ───────────────────────────────────────────────────────────────
    confirmed = int(cls_counts.get("egyptian_confirmed", 0))
    probable  = int(cls_counts.get("egyptian_probable",  0))
    uncnf     = int(cls_counts.get("unconfirmed",        0))
    uncls     = int(cls_counts.get("unclassified",       0))
    not_eg    = int(cls_counts.get("not_egyptian",       0))

    print(f"""
─── Stage 3b Summary ─────────────────────────────────────────────
Total owners classified  : {total_owners:,}
Total repos in sample    : {total_repos:,}

Owner classification (final — all 9 signals applied):
  {'Label':<25} {'Owners':>7}   {'%':>6}   {'In Egypt corpus?'}
  {'-'*60}
  {'egyptian_confirmed':<25} {confirmed:>7}   {confirmed/total_owners*100:>5.1f}%   Yes
  {'egyptian_probable':<25}  {probable:>7}   {probable/total_owners*100:>5.1f}%   Yes (flagged)
  {'unconfirmed':<25}        {uncnf:>7}   {uncnf/total_owners*100:>5.1f}%   No — weak single signal
  {'unclassified':<25}       {uncls:>7}   {uncls/total_owners*100:>5.1f}%   No — no evidence found
  {'not_egyptian':<25}       {not_eg:>7}   {not_eg/total_owners*100:>5.1f}%   No — explicit non-Egyptian

Egyptian corpus:
  Repos in egypt_corpus.csv : {len(egypt_corpus_df):,} / {total_repos:,} repos
  ({len(egypt_corpus_df)/total_repos*100:.1f}% of sample corpus)

Location source (how Egyptian owners were identified):""")

    for src, n in src_counts.items():
        print(f"  {src:<15} {n:>5} owners  ({n/eg_total*100:.1f}%)")

    print(f"""
Undercoverage (not in Egypt corpus):
  unconfirmed  : {uncnf:,} owners — all 9 signals ran, only one weak signal fired
  unclassified : {uncls:,} owners — all 9 signals ran, zero evidence found
  → These will be reported as undercoverage in the thesis methodology.

Outputs:
  {OWNERS_FINAL_CSV}
  {EGYPT_CORPUS_CSV}
  {COVERAGE_STATS_CSV}

Next: run Stage 4 (if not already complete), then Stage 5 statistical analysis.
""")


if __name__ == "__main__":
    main()

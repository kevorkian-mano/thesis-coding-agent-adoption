#!/usr/bin/env python3
"""
Stage 5c — Temporal Signal Analysis
=====================================
Analyses WHEN AI signals appeared relative to the repository's creation date.

Questions answered:
  - Did developers start projects with AI from day one, or add it later?
  - What is the typical time between repo creation and first AI signal?
  - Are repos created later in 2025 more likely to have adopted AI?
  - Do early adopters (signal within first month) show different patterns?

INPUTS
------
  data/stage4/sample_corpus_detected.csv       — global detection results
  data/stage4/egypt_corpus_input_detected.csv  — Egyptian detection results

OUTPUTS
-------
  data/stage5/temporal_global.csv
  data/stage5/temporal_egypt.csv
  data/stage5/temporal_summary.csv

USAGE
-----
  python3 scripts/stage5/stage5c_temporal.py
"""

import pandas as pd
import numpy as np
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
DATA_DIR   = SCRIPT_DIR / "../../data"
GLOBAL_CSV = DATA_DIR / "stage4/sample_corpus_detected.csv"
EGYPT_CSV  = DATA_DIR / "stage4/egypt_corpus_input_detected.csv"
OUT_DIR    = DATA_DIR / "stage5"

OUT_DIR.mkdir(parents=True, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def load(path: Path, label: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    for col in ["agent_adopted_multi", "agent_adopted_single"]:
        if col in df.columns:
            df[col] = df[col].map(
                lambda x: True if str(x).strip().lower() == "true" else False
            )
    df["corpus"] = label
    return df


def parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["created_at"]       = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
    df["first_detected_at"] = pd.to_datetime(df.get("first_detected_at"), errors="coerce", utc=True)
    # time_to_adoption may already be in days as a number
    if "time_to_adoption" in df.columns:
        df["time_to_adoption"] = pd.to_numeric(df["time_to_adoption"], errors="coerce")
    else:
        df["time_to_adoption"] = (df["first_detected_at"] - df["created_at"]).dt.days
    df["created_month"] = df["created_at"].dt.to_period("M").astype(str)
    return df


def adoption_timing_bucket(days) -> str:
    if pd.isna(days):
        return "unknown"
    if days <= 7:    return "within 1 week"
    if days <= 30:   return "within 1 month"
    if days <= 90:   return "1–3 months"
    if days <= 180:  return "3–6 months"
    return "6+ months"


def print_section(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    global_df = parse_dates(load(GLOBAL_CSV, "global"))
    egypt_df  = parse_dates(load(EGYPT_CSV,  "egyptian"))

    adopted_global = global_df[global_df["agent_adopted_multi"]]
    adopted_egypt  = egypt_df[egypt_df["agent_adopted_multi"]]

    summary_rows = []

    # ── Time to first AI signal ───────────────────────────────────────────────
    print_section("Time from repo creation to first AI signal")

    for label, df in [("Global", adopted_global), ("Egyptian", adopted_egypt)]:
        t = df["time_to_adoption"].dropna()
        if len(t) == 0:
            print(f"  {label}: no timing data available")
            continue
        print(f"\n  {label} (n={len(t)} repos with timing data):")
        print(f"    Median  : {t.median():.0f} days")
        print(f"    Mean    : {t.mean():.0f} days")
        print(f"    Min     : {t.min():.0f} days")
        print(f"    Max     : {t.max():.0f} days")
        print(f"    Within 7 days   : {(t <= 7).sum()} ({(t <= 7).mean()*100:.1f}%)")
        print(f"    Within 30 days  : {(t <= 30).sum()} ({(t <= 30).mean()*100:.1f}%)")
        print(f"    Within 90 days  : {(t <= 90).sum()} ({(t <= 90).mean()*100:.1f}%)")
        summary_rows.append({
            "corpus": label, "metric": "median_days_to_adoption",
            "value": round(t.median(), 1)
        })
        summary_rows.append({
            "corpus": label, "metric": "pct_adopted_within_7_days",
            "value": round((t <= 7).mean() * 100, 1)
        })
        summary_rows.append({
            "corpus": label, "metric": "pct_adopted_within_30_days",
            "value": round((t <= 30).mean() * 100, 1)
        })

    # ── Adoption timing buckets ───────────────────────────────────────────────
    print_section("Adoption timing breakdown")
    bucket_order = ["within 1 week", "within 1 month", "1–3 months",
                    "3–6 months", "6+ months", "unknown"]

    for label, df in [("Global", adopted_global), ("Egyptian", adopted_egypt)]:
        df = df.copy()
        df["timing_bucket"] = df["time_to_adoption"].map(adoption_timing_bucket)
        print(f"\n  {label}:")
        for b in bucket_order:
            n    = (df["timing_bucket"] == b).sum()
            pct  = n / len(df) * 100 if len(df) else 0
            print(f"    {b:<20} {n:>5}  ({pct:.1f}%)")

    # ── Adoption rate by creation month (global) ──────────────────────────────
    print_section("Global adoption rate by repo creation month")
    monthly = global_df.groupby("created_month").apply(
        lambda g: pd.Series({
            "n_repos":      len(g),
            "adopted":      g["agent_adopted_multi"].sum(),
            "adoption_%":   round(g["agent_adopted_multi"].mean() * 100, 1),
        })
    ).reset_index()
    monthly = monthly[monthly["n_repos"] >= 10]  # skip months with too few repos
    print(monthly.to_string(index=False))
    monthly.to_csv(OUT_DIR / "temporal_global.csv", index=False)

    # ── Egyptian: adoption rate by creation month ─────────────────────────────
    if egypt_df["created_at"].notna().sum() > 0:
        print_section("Egyptian adoption rate by repo creation month")
        monthly_eg = egypt_df.groupby("created_month").apply(
            lambda g: pd.Series({
                "n_repos":    len(g),
                "adopted":    g["agent_adopted_multi"].sum(),
                "adoption_%": round(g["agent_adopted_multi"].mean() * 100, 1),
            })
        ).reset_index()
        monthly_eg = monthly_eg[monthly_eg["n_repos"] >= 3]
        print(monthly_eg.to_string(index=False))
        monthly_eg.to_csv(OUT_DIR / "temporal_egypt.csv", index=False)

    # ── "Born agentic" — adopted within first week ───────────────────────────
    print_section("'Born agentic' repos — AI signal within first 7 days of creation")
    for label, df in [("Global", global_df), ("Egyptian", egypt_df)]:
        born_agentic = df[
            df["agent_adopted_multi"] & (df["time_to_adoption"].fillna(999) <= 7)
        ]
        total_adopted = df["agent_adopted_multi"].sum()
        pct_of_adopted = born_agentic.shape[0] / total_adopted * 100 if total_adopted else 0
        pct_of_all     = born_agentic.shape[0] / len(df) * 100 if len(df) else 0
        print(f"\n  {label}:")
        print(f"    Born-agentic repos : {born_agentic.shape[0]}")
        print(f"    % of all adopters  : {pct_of_adopted:.1f}%")
        print(f"    % of all repos     : {pct_of_all:.1f}%")

    # ── Save summary ──────────────────────────────────────────────────────────
    pd.DataFrame(summary_rows).to_csv(OUT_DIR / "temporal_summary.csv", index=False)
    print(f"\nOutputs saved to {OUT_DIR}/")


if __name__ == "__main__":
    main()

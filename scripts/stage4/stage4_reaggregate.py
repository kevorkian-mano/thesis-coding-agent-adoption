"""
Stage 4 — Re-aggregation (no API calls)
========================================
Reads the already-saved signals_global.csv, removes the generic `openai`
npm_dependency signal (too broad — any app calling the OpenAI API gets flagged),
then recomputes all per-repo adoption columns and saves a clean result.

Run this whenever you want to tweak signal rules without hitting the GitHub API.

INPUTS
------
  data/stage4/signals_global.csv       — raw signals from the full Stage 4 run
  data/stage1/global_corpus_2025.csv   — base corpus (repo metadata)

OUTPUTS
-------
  data/stage4/signals_global_clean.csv      — signals after removals
  data/stage4/global_corpus_detected.csv    — overwritten with new adoption columns
"""

import os
import pandas as pd
from datetime import datetime
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent
DATA_DIR     = SCRIPT_DIR / "../../data"
SIGNALS_IN   = DATA_DIR / "stage4/signals_global.csv"
SIGNALS_CLEAN= DATA_DIR / "stage4/signals_global_clean.csv"
CORPUS_IN    = DATA_DIR / "stage1/global_corpus_2025.csv"
CORPUS_OUT   = DATA_DIR / "stage4/global_corpus_detected.csv"

# ── Signals to remove ─────────────────────────────────────────────────────────
# Each entry is (signal_type, agent_name, evidence_prefix)
# Set evidence_prefix to None to remove ALL signals of that type+agent combo.
REMOVE_SIGNALS = [
    # "openai" npm package is used by apps calling the OpenAI API — not a
    # reliable indicator that a coding agent wrote the code.
    ("npm_dependency", "openai", "package:openai"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Classification (same rules as stage4_detection.py OBS-012)
# ─────────────────────────────────────────────────────────────────────────────

def classify_adoption_level(has_config_file: bool,
                             distinct_types: int,
                             signal_occurrences: int) -> str:
    if signal_occurrences == 0:
        return "none"
    if (has_config_file
            or distinct_types >= 2
            or signal_occurrences >= 3):
        return "agentic"
    return "ai_assisted"


# ─────────────────────────────────────────────────────────────────────────────
# Aggregation (mirrors stage4_detection.py aggregate_repo_signals)
# ─────────────────────────────────────────────────────────────────────────────

def aggregate_repo_signals(signals_df: pd.DataFrame,
                            corpus_df: pd.DataFrame) -> pd.DataFrame:
    df = corpus_df.copy()

    # Defaults
    df["agent_adopted_single"] = False
    df["agent_adopted_multi"]  = False
    df["agent_adopted"]        = False
    df["adoption_level"]       = "none"
    df["first_detected_at"]    = None
    df["agent_name"]           = None
    df["signal_count"]         = 0
    df["signal_occurrences"]   = 0
    df["multi_agent"]          = False
    df["time_to_adoption"]     = None
    df["adoption_month"]       = None

    if signals_df.empty:
        return df

    for full_name, grp in signals_df.groupby("full_name"):
        mask = df["full_name"] == full_name
        if not mask.any():
            continue

        trailer_signals    = grp[grp["signal_type"] == "commit_trailer"]
        distinct_types     = grp["signal_type"].nunique()
        signal_occurrences = len(grp)
        has_config_file    = "config_file" in grp["signal_type"].values

        df.loc[mask, "agent_adopted_single"] = not trailer_signals.empty
        df.loc[mask, "agent_adopted_multi"]  = True
        df.loc[mask, "agent_adopted"]        = True
        df.loc[mask, "signal_count"]         = distinct_types
        df.loc[mask, "signal_occurrences"]   = signal_occurrences
        df.loc[mask, "adoption_level"]       = classify_adoption_level(
            has_config_file, distinct_types, signal_occurrences
        )

        agent_counts = grp["agent_name"].value_counts()
        df.loc[mask, "agent_name"] = agent_counts.index[0]
        df.loc[mask, "multi_agent"] = grp["agent_name"].nunique() > 1

        dated = grp.dropna(subset=["detected_at"])
        if not dated.empty:
            first_date = dated["detected_at"].min()
            df.loc[mask, "first_detected_at"] = first_date
            df.loc[mask, "adoption_month"]    = first_date[:7]

            created = df.loc[mask, "created_at"].values[0]
            if created and isinstance(created, str) and len(created) >= 10:
                try:
                    delta = (
                        datetime.strptime(first_date, "%Y-%m-%d") -
                        datetime.strptime(str(created)[:10], "%Y-%m-%d")
                    ).days
                    df.loc[mask, "time_to_adoption"] = max(delta, 0)
                except ValueError:
                    pass

    return df


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    signals_df = pd.read_csv(SIGNALS_IN)
    corpus_df  = pd.read_csv(CORPUS_IN)
    total      = len(corpus_df)

    print(f"Loaded {len(signals_df)} signals")
    print(f"Loaded {total} repos\n")

    # ── Remove unwanted signals ───────────────────────────────────────────────
    original_count = len(signals_df)
    for sig_type, agent, evidence_prefix in REMOVE_SIGNALS:
        mask = (
            (signals_df["signal_type"] == sig_type) &
            (signals_df["agent_name"]  == agent) &
            (signals_df["evidence"].str.startswith(evidence_prefix))
        )
        removed = mask.sum()
        signals_df = signals_df[~mask].copy()
        print(f"Removed {removed} signals: {sig_type} / {agent} / {evidence_prefix}")

    print(f"\nSignals after cleaning: {len(signals_df)} (was {original_count})")

    signals_df.to_csv(SIGNALS_CLEAN, index=False)
    print(f"Clean signals saved → {SIGNALS_CLEAN}")

    # ── Re-aggregate ──────────────────────────────────────────────────────────
    corpus_final = aggregate_repo_signals(signals_df, corpus_df)
    corpus_final.to_csv(CORPUS_OUT, index=False)

    # ── Summary ───────────────────────────────────────────────────────────────
    adopted_single = corpus_final["agent_adopted_single"].sum()
    adopted_multi  = corpus_final["agent_adopted_multi"].sum()

    print(f"\n─── Updated Summary ──────────────────────────────────────────")
    print(f"Total repos                           : {total}")
    print(f"Single-signal adopted (trailers only) : {adopted_single} "
          f"({adopted_single/total*100:.1f}%)")
    print(f"Multi-signal adopted  (all signals)   : {adopted_multi}  "
          f"({adopted_multi/total*100:.1f}%)")
    print(f"Undercounting delta                   : "
          f"{(adopted_multi-adopted_single)/total*100:.1f} pp")
    print(f"\nAdoption level breakdown (OBS-012):")
    print(corpus_final["adoption_level"].value_counts().to_string())
    print(f"\nSignal type breakdown:")
    print(signals_df["signal_type"].value_counts().to_string())
    print(f"\nAgent breakdown:")
    print(signals_df["agent_name"].value_counts().head(10).to_string())
    print(f"\nSaved: {CORPUS_OUT}")


if __name__ == "__main__":
    main()

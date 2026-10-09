#!/usr/bin/env python3
"""
Stage 5a — Adoption Breakdowns
================================
Analyses 1–4 using existing Stage 4 output files (no API calls needed).

  Analysis 1 — Adoption by ecosystem (global)
    npm vs pnpm vs yarn vs bun vs npm_no_lock vs vanilla

  Analysis 2 — Adoption by language (global + Egyptian)
    JavaScript vs TypeScript in both corpora

  Analysis 3 — Adoption by size stratum (global + Egyptian)
    small (≤50 stars) vs medium (51–500) vs large (>500)

  Analysis 4 — Cross-tabulation: ecosystem × language (global)
    Which combination has the highest adoption rate?

INPUTS
------
  data/stage4/sample_corpus_detected.csv       — global detection results
  data/stage4/egypt_corpus_input_detected.csv  — Egyptian detection results

OUTPUTS
-------
  data/stage5/breakdown_ecosystem.csv
  data/stage5/breakdown_language.csv
  data/stage5/breakdown_size.csv
  data/stage5/breakdown_crosstab.csv

USAGE
-----
  python3 scripts/stage5/stage5a_breakdowns.py
"""

import pandas as pd
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent
DATA_DIR     = SCRIPT_DIR / "../../data"
GLOBAL_CSV   = DATA_DIR / "stage4/sample_corpus_detected.csv"
EGYPT_CSV    = DATA_DIR / "stage4/egypt_corpus_input_detected.csv"
OUT_DIR      = DATA_DIR / "stage5"

OUT_DIR.mkdir(parents=True, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Normalise boolean columns that may have been saved as strings
    for col in ["agent_adopted_multi", "agent_adopted_single", "agent_adopted"]:
        if col in df.columns:
            df[col] = df[col].map(
                lambda x: True if str(x).strip().lower() == "true" else False
            )
    return df


def adoption_table(df: pd.DataFrame, group_col: str, label: str) -> pd.DataFrame:
    """Compute multi-signal and single-signal adoption rates per group."""
    rows = []
    for val, grp in df.groupby(group_col):
        n        = len(grp)
        multi    = grp["agent_adopted_multi"].sum()
        single   = grp["agent_adopted_single"].sum() if "agent_adopted_single" in grp.columns else 0
        agentic  = (grp["adoption_level"] == "agentic").sum() if "adoption_level" in grp.columns else 0
        rows.append({
            group_col:           val,
            "n_repos":           n,
            "multi_adopted":     int(multi),
            "multi_rate_%":      round(multi / n * 100, 1),
            "single_adopted":    int(single),
            "single_rate_%":     round(single / n * 100, 1) if n else 0,
            "agentic_count":     int(agentic),
            "agentic_rate_%":    round(agentic / n * 100, 1),
            "corpus":            label,
        })
    return pd.DataFrame(rows).sort_values("multi_rate_%", ascending=False)


def print_table(df: pd.DataFrame, title: str, group_col: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")
    cols = [group_col, "n_repos", "multi_rate_%", "single_rate_%", "agentic_rate_%"]
    cols = [c for c in cols if c in df.columns]
    print(df[cols].to_string(index=False))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    global_df = load(GLOBAL_CSV)
    egypt_df  = load(EGYPT_CSV)

    print(f"Loaded global corpus : {len(global_df):,} repos")
    print(f"Loaded Egyptian corpus: {len(egypt_df):,} repos")

    # ── Analysis 1: Ecosystem (global only — Egypt is all npm) ────────────────
    eco_df = adoption_table(global_df, "ecosystem_type", "global")
    print_table(eco_df, "Analysis 1 — Adoption by Ecosystem (Global)", "ecosystem_type")
    eco_df.to_csv(OUT_DIR / "breakdown_ecosystem.csv", index=False)

    # ── Analysis 2: Language (global + Egyptian) ──────────────────────────────
    lang_global = adoption_table(global_df, "primary_language", "global")
    lang_egypt  = adoption_table(egypt_df,  "primary_language", "egyptian")
    lang_df     = pd.concat([lang_global, lang_egypt], ignore_index=True)
    print_table(lang_df, "Analysis 2 — Adoption by Language (Global + Egyptian)", "primary_language")
    lang_df.to_csv(OUT_DIR / "breakdown_language.csv", index=False)

    # ── Analysis 3: Size stratum (global + Egyptian) ──────────────────────────
    size_global = adoption_table(global_df, "size_stratum", "global")
    size_egypt  = adoption_table(egypt_df,  "size_stratum", "egyptian")
    size_df     = pd.concat([size_global, size_egypt], ignore_index=True)
    print_table(size_df, "Analysis 3 — Adoption by Size Stratum (Global + Egyptian)", "size_stratum")
    size_df.to_csv(OUT_DIR / "breakdown_size.csv", index=False)

    # ── Analysis 4: Cross-tabulation ecosystem × language (global) ────────────
    # Only keep main ecosystems for clarity
    main_eco = ["npm", "pnpm", "yarn", "bun", "npm_no_lock", "vanilla"]
    ct_df = global_df[global_df["ecosystem_type"].isin(main_eco)].copy()

    pivot = ct_df.groupby(["ecosystem_type", "primary_language"]).apply(
        lambda g: round(g["agent_adopted_multi"].sum() / len(g) * 100, 1)
    ).unstack(fill_value=0)
    pivot.columns = [f"{c}_adoption_%" for c in pivot.columns]
    pivot["n_repos"] = ct_df.groupby("ecosystem_type").size()
    pivot = pivot.sort_values(list(pivot.columns)[0], ascending=False)

    print(f"\n{'─' * 60}")
    print(f"  Analysis 4 — Cross-tab: Ecosystem × Language — Multi-signal Adoption Rate (%)")
    print(f"{'─' * 60}")
    print(pivot.to_string())
    pivot.to_csv(OUT_DIR / "breakdown_crosstab.csv")

    print(f"\n\nAll outputs saved to {OUT_DIR}/")


if __name__ == "__main__":
    main()

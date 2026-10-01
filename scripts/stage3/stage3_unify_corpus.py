"""
Stage 3 — Unify Corpus
======================
Merges the global corpus (Stage 1) and Egyptian corpus (Stage 2c) into a
single unified corpus, with two operations:

  1. CLEAN GLOBAL CORPUS: Remove any repo from the global corpus whose
     owner_login appears in the Egyptian accounts list. These repos belong
     to Egyptian developers and must not be counted as non-Egyptian.
     If they also appear in the Egyptian corpus they stay there; if not,
     they are added to the Egyptian corpus.

  2. MERGE & LABEL: Combine both corpora. Every repo gets a corpus_source
     label: "global" (non-Egyptian) or "egyptian". Repos that appear in
     both after cleaning are labeled "both" and counted once.

NOTE ON DATE FILTERING
----------------------
Both input files are already filtered to pushed_at >= 2025-01-01.
This was applied as a separate step after Stage 1 and Stage 2c ran,
producing global_corpus_2025.csv and egyptian_corpus_2025.csv.
Repos inactive before 2025 predate the mainstream agentic AI era
(Claude Code: March 2025, Devin: March 2024, Cursor agentic: 2024).

INPUTS
------
  data/stage1/global_corpus_2025.csv       (Stage 1 output, date-filtered)
  data/stage2/egyptian_corpus_2025.csv     (Stage 2c output, date-filtered)
  data/stage2/egypt_combined_accounts.csv  (Stage 2a/2b accounts list)

OUTPUTS
-------
  data/stage3/unified_corpus.csv           — final corpus for Stage 4

USAGE
-----
  python3 stage3_unify_corpus.py
"""

import os
import pandas as pd

# ── Input paths ───────────────────────────────────────────────────────────────
BASE         = os.path.dirname(os.path.abspath(__file__))
GLOBAL_CSV   = os.path.join(BASE, "../../data/stage1/global_corpus_2025.csv")
EGYPTIAN_CSV = os.path.join(BASE, "../../data/stage2/egyptian_corpus_2025.csv")
ACCOUNTS_CSV = os.path.join(BASE, "../../data/stage2/egypt_combined_accounts.csv")

# ── Output ────────────────────────────────────────────────────────────────────
UNIFIED_OUT  = os.path.join(BASE, "../../data/stage3/unified_corpus.csv")


def main():
    # ── Load files ────────────────────────────────────────────────────────────
    global_df   = pd.read_csv(GLOBAL_CSV)
    egyptian_df = pd.read_csv(EGYPTIAN_CSV)
    accounts_df = pd.read_csv(ACCOUNTS_CSV)

    print(f"Loaded global corpus    : {len(global_df)} repos")
    print(f"Loaded Egyptian corpus  : {len(egyptian_df)} repos")
    print(f"Loaded Egyptian accounts: {len(accounts_df)} accounts")

    egyptian_logins = set(accounts_df["login"].dropna().str.lower().unique())

    # ── Step 1: Remove Egyptian-owned repos from global corpus ───────────────
    # Any repo in the global corpus whose owner is an Egyptian developer does
    # not belong in the non-Egyptian comparison group.
    is_egyptian_owned = global_df["owner_login"].str.lower().isin(egyptian_logins)
    moved_df          = global_df[is_egyptian_owned].copy()
    global_df         = global_df[~is_egyptian_owned].copy()

    print(f"\nRemoved {len(moved_df)} Egyptian-owned repos from global corpus.")
    print(f"  Global corpus after cleaning: {len(global_df)} repos")

    # Repos removed from global but not already in Egyptian corpus → add them
    existing_egyptian = set(egyptian_df["full_name"].str.lower())
    to_add = moved_df[~moved_df["full_name"].str.lower().isin(existing_egyptian)].copy()
    to_add["corpus_source"] = "egyptian"

    if len(to_add) > 0:
        egyptian_df = pd.concat([egyptian_df, to_add], ignore_index=True)
        print(f"  Added {len(to_add)} repos to Egyptian corpus (were in global but Egyptian-owned).")

    # ── Step 2: Merge and label ───────────────────────────────────────────────
    global_df["corpus_source"]   = "global"
    egyptian_df["corpus_source"] = "egyptian"

    # Find repos that appear in both (after cleaning)
    global_names   = set(global_df["full_name"].str.lower())
    egyptian_names = set(egyptian_df["full_name"].str.lower())
    overlap        = global_names & egyptian_names

    if overlap:
        print(f"\n{len(overlap)} repos appear in both corpora → labeled 'both', counted once.")
        # Keep the Egyptian version, label it "both"
        egyptian_df.loc[
            egyptian_df["full_name"].str.lower().isin(overlap), "corpus_source"
        ] = "both"
        # Remove duplicates from global
        global_df = global_df[~global_df["full_name"].str.lower().isin(overlap)].copy()

    unified_df = pd.concat([global_df, egyptian_df], ignore_index=True)

    # Final dedup on full_name (safety net)
    before_dedup = len(unified_df)
    unified_df   = unified_df.drop_duplicates(subset=["full_name"])
    if before_dedup != len(unified_df):
        print(f"  Dedup removed {before_dedup - len(unified_df)} duplicate rows.")

    # ── Save ──────────────────────────────────────────────────────────────────
    unified_df.to_csv(UNIFIED_OUT, index=False)

    # ── Summary ───────────────────────────────────────────────────────────────
    source_counts = unified_df["corpus_source"].value_counts()
    strata        = unified_df["size_stratum"].value_counts()
    languages     = unified_df["primary_language"].value_counts()

    print(f"\n─── Summary ───────────────────────────────────────────────")
    print(f"Total unified corpus     : {len(unified_df)} repos")
    print(f"\nCorpus source breakdown:\n{source_counts.to_string()}")
    print(f"\nStratum breakdown:\n{strata.to_string()}")
    print(f"\nPrimary language:\n{languages.to_string()}")
    print(f"\nSaved: {UNIFIED_OUT}")


if __name__ == "__main__":
    main()

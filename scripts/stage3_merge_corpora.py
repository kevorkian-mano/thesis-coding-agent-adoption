"""
Stage 3: Merge Base Corpus + Egypt Corpus → Unified Corpus

Combines:
  - base_jsts_corpus_pilot.csv   (Stage 1: global JS/TS repos)
  - egypt_corpus.csv             (Stage 2c: repos from Egyptian developer accounts)

Deduplicates by full_name. Repos that appear in both corpora keep the
base-corpus row (more complete metadata) and are tagged corpus_source="both".
Egypt-only repos are tagged corpus_source="egypt"; base-only as corpus_source="base".

Output: unified_corpus.csv

Requires: pip install pandas
"""

import os
import pandas as pd

# ── Inputs / outputs ──────────────────────────────────────────────────────────
BASE_CORPUS_FILE   = "base_jsts_corpus_pilot.csv"
EGYPT_CORPUS_FILE  = "egypt_corpus.csv"
OUTPUT_FILE        = "unified_corpus.csv"

# ── Columns present in the base corpus (Stage 1) ─────────────────────────────
# These may be missing from the Egypt corpus — filled with None if absent.
BASE_ONLY_COLS = [
    "repo_id", "forks", "created_at", "default_branch",
    "archived", "fork", "disabled", "description", "topics",
    "size_kb", "open_issues", "contributor_count", "total_commits",
]

# ── Shared columns (both corpora must have these) ─────────────────────────────
SHARED_COLS = [
    "owner_login", "repo_name", "full_name", "primary_language",
    "stars", "pushed_at", "has_manifest", "js_ts_byte_share",
    "size_stratum", "agent_adopted", "topic_id", "ecosystem",
]

# ── Egypt-specific column kept in unified corpus ──────────────────────────────
EGYPT_EXTRA_COL = "seed_account"   # which Egyptian developer owns the repo


def load_and_tag(path: str, tag: str) -> pd.DataFrame | None:
    if not os.path.exists(path):
        print(f"WARNING: {path} not found — skipping.")
        return None
    df = pd.read_csv(path)
    df["corpus_source"] = tag
    print(f"Loaded {len(df):>5} rows from {path}")
    return df


def main():
    base_df  = load_and_tag(BASE_CORPUS_FILE,  "base")
    egypt_df = load_and_tag(EGYPT_CORPUS_FILE, "egypt")

    if base_df is None and egypt_df is None:
        print("Error: neither corpus file found. Run Stage 1 and Stage 2c first.")
        return

    # ── Ensure Egypt corpus has all base columns (fill with None if missing) ──
    if egypt_df is not None:
        for col in BASE_ONLY_COLS:
            if col not in egypt_df.columns:
                egypt_df[col] = None

    # ── Ensure base corpus has the Egypt extra column ─────────────────────────
    if base_df is not None and EGYPT_EXTRA_COL not in base_df.columns:
        base_df[EGYPT_EXTRA_COL] = None

    # ── Concatenate ───────────────────────────────────────────────────────────
    frames = [df for df in [base_df, egypt_df] if df is not None]
    combined = pd.concat(frames, ignore_index=True)

    # ── Deduplicate: repos in both corpora ────────────────────────────────────
    # Mark overlapping repos as "both", then keep the base-corpus row
    # (richer metadata) for the actual data.

    overlap = combined.duplicated(subset=["full_name"], keep=False)
    overlap_names = set(combined.loc[overlap, "full_name"])
    print(f"\nRepos in both corpora (overlap): {len(overlap_names)}")

    # Tag overlapping rows in the base corpus as "both"
    combined.loc[
        (combined["full_name"].isin(overlap_names)) & (combined["corpus_source"] == "base"),
        "corpus_source"
    ] = "both"

    # Drop the duplicate egypt-only rows for repos already in base
    combined = combined.sort_values(
        "corpus_source",
        key=lambda s: s.map({"both": 0, "base": 1, "egypt": 2}),
    )
    combined = combined.drop_duplicates(subset=["full_name"], keep="first")

    # ── Column order ──────────────────────────────────────────────────────────
    ordered_cols = (
        ["full_name", "owner_login", "repo_name", "corpus_source"]
        + [c for c in SHARED_COLS if c not in ("full_name", "owner_login", "repo_name")]
        + BASE_ONLY_COLS
        + [EGYPT_EXTRA_COL]
    )
    # Only keep columns that actually exist
    ordered_cols = [c for c in ordered_cols if c in combined.columns]
    # Append any remaining columns not in ordered_cols
    remaining = [c for c in combined.columns if c not in ordered_cols]
    combined = combined[ordered_cols + remaining]

    combined = combined.reset_index(drop=True)
    combined.to_csv(OUTPUT_FILE, index=False)

    # ── Summary ───────────────────────────────────────────────────────────────
    source_counts = combined["corpus_source"].value_counts()
    strata_counts = combined["size_stratum"].value_counts() if "size_stratum" in combined.columns else None
    lang_counts   = combined["primary_language"].value_counts() if "primary_language" in combined.columns else None

    print(f"\n─── Stage 3 Summary ─────────────────────────────────────────")
    print(f"Base-only repos         : {source_counts.get('base',  0)}")
    print(f"Egypt-only repos        : {source_counts.get('egypt', 0)}")
    print(f"In both corpora         : {source_counts.get('both',  0)}")
    print(f"Total unique repos      : {len(combined)}")
    if strata_counts is not None:
        print(f"\nStratum breakdown:")
        print(strata_counts.to_string())
    if lang_counts is not None:
        print(f"\nPrimary language breakdown:")
        print(lang_counts.to_string())
    print(f"\nSaved to {OUTPUT_FILE}")
    print("NEXT: run Stage 4 (agent adoption detection) on unified_corpus.csv")


if __name__ == "__main__":
    main()

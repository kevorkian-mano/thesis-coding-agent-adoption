#!/usr/bin/env python3
"""
prepare_submission.py  —  TypeScript/JavaScript stack
======================================================
Creates shared_viz_tool/data/ts_js_final_corpus.csv from the pipeline outputs.
Run this once after Stage 4 completes.

Usage:
    python3 shared_viz_tool/prepare_submission.py
"""

import pandas as pd
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[1]
CORPUS  = ROOT / "data" / "stage4" / "corpus_with_country.csv"
OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)
OUT     = OUT_DIR / "ts_js_final_corpus.csv"

STACK = "TypeScript/JavaScript"


def main():
    print(f"Loading corpus from {CORPUS.relative_to(ROOT)} ...")
    df = pd.read_csv(CORPUS, low_memory=False)
    print(f"  {len(df):,} repos loaded")

    # Rename country column to standardised name used by the dashboard
    if "inferred_country" in df.columns and "country" not in df.columns:
        df = df.rename(columns={"inferred_country": "country"})

    # Tag this stack
    df["stack"] = STACK

    df.to_csv(OUT, index=False)
    print(f"Saved {len(df):,} rows → {OUT.relative_to(ROOT)}")

    # Quick sanity print
    adopted = ((df["adoption_label"] == "agentic") | (df["adoption_label"] == "ai_assisted")).sum()
    rate    = adopted / len(df) * 100
    print(f"\nStack summary")
    print(f"  Stack          : {STACK}")
    print(f"  Total repos    : {len(df):,}")
    print(f"  Adopted        : {adopted:,}  ({rate:.1f}%)")
    print(f"  Agentic        : {(df['adoption_label']=='agentic').sum():,}")
    print(f"  AI-assisted    : {(df['adoption_label']=='ai_assisted').sum():,}")
    print(f"  None           : {(df['adoption_label']=='none').sum():,}")


if __name__ == "__main__":
    main()

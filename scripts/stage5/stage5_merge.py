#!/usr/bin/env python3
"""
Stage 5 Merge -- Build corpus_detected_full_v3.csv
===================================================
Combines Stage 3 base labels with Stage 5a/5b updates into one
definitive classification file for all 60,129 repos.

Merge logic
-----------
  - Repos labelled agentic in Stage 3 (39,496): kept unchanged.
    Stage 5 only scanned none/ai_assisted repos.
  - Repos scanned by Stage 5 (20,633): take final label + signal
    families from Stage 5b (which carries Stage 5a labels forward).
  - agents_found: combine Stage 3 agents with any new tools found
    in Stage 5a/5b (| separated, deduped).

Output
------
  data/stage5/corpus_detected_full_v3.csv

Usage
-----
  python3 scripts/stage5/stage5_merge.py
"""

import pandas as pd
from pathlib import Path

ROOT     = Path(__file__).resolve().parents[2]
V2       = ROOT / "data" / "stage3" / "corpus_detected_full_v2.csv"
S5A      = ROOT / "data" / "stage5" / "stage5a_results.csv"
S5B      = ROOT / "data" / "stage5" / "stage5b_results.csv"
OUT_DIR  = ROOT / "data" / "stage5"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_V3   = OUT_DIR / "corpus_detected_full_v3.csv"


def merge_tools(existing: str, new_tools: str) -> str:
    """Combine two | separated tool strings, deduped, sorted."""
    parts = set()
    for s in [existing, new_tools]:
        if s and str(s) not in ("nan", ""):
            parts.update(t.strip() for t in str(s).split("|") if t.strip())
    return "|".join(sorted(parts)) if parts else ""


def main():
    print("Stage 5 Merge -- corpus_detected_full_v3.csv")
    print("=" * 60)

    # ── Load inputs ───────────────────────────────────────────────
    v2  = pd.read_csv(V2,  low_memory=False)
    s5a = pd.read_csv(S5A, low_memory=False)
    s5b = pd.read_csv(S5B, low_memory=False)

    print(f"Stage 3 base        : {len(v2):,} repos")
    print(f"Stage 5a results    : {len(s5a):,} repos")
    print(f"Stage 5b results    : {len(s5b):,} repos")

    # ── Build Stage 5 update lookup (Stage 5b is authoritative) ──
    # Stage 5b carries 5a labels forward so it covers all 20,633 repos.
    s5b_idx = s5b.set_index("full_name")
    s5a_idx = s5a.set_index("full_name")

    # ── Apply updates ─────────────────────────────────────────────
    v3 = v2.copy()

    updated       = 0
    label_changed = 0

    for idx, row in v3.iterrows():
        fn = row["full_name"]

        if fn not in s5b_idx.index:
            # Was already agentic in Stage 3 — not scanned by Stage 5
            continue

        s5b_row = s5b_idx.loc[fn]

        # Final label: Stage 5b new_label
        new_label = s5b_row["new_label"]
        if new_label != row["adoption_label"]:
            label_changed += 1
        v3.at[idx, "adoption_label"] = new_label

        # Signal families: use Stage 5b finals
        v3.at[idx, "strong_families"] = s5b_row.get("strong_families_final", row["strong_families"])
        v3.at[idx, "medium_families"] = s5b_row.get("medium_families_final", row["medium_families"])
        v3.at[idx, "weak_families"]   = s5b_row.get("weak_families_final",   row["weak_families"])
        v3.at[idx, "agent_attributed_count"] = s5b_row.get("agent_attributed_count", row["agent_attributed_count"])

        # Merge tools: Stage 3 agents + Stage 5a tools + Stage 5b tools
        s5a_tools = s5a_idx.loc[fn, "tools_found"] if fn in s5a_idx.index else ""
        s5b_tools = s5b_row.get("tools_found", "")
        v3.at[idx, "agents_found"] = merge_tools(
            merge_tools(row["agents_found"], s5a_tools), s5b_tools
        )

        updated += 1

    v3.to_csv(OUT_V3, index=False)

    # ── Summary ───────────────────────────────────────────────────
    print(f"\nRepos updated       : {updated:,}")
    print(f"Label changes       : {label_changed:,}")

    print(f"\nFinal label distribution:")
    counts = v3["adoption_label"].value_counts()
    for label, count in counts.items():
        print(f"  {label:<15} {count:>7,}  ({count/len(v3)*100:.1f}%)")

    print(f"\nSaved: {OUT_V3}  ({len(v3):,} rows)")
    print("\nStage 5 merge complete.")


if __name__ == "__main__":
    main()

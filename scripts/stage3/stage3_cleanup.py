#!/usr/bin/env python3
"""
Stage 3 -- Post-Processing Cleanup
====================================
Fixes two data quality issues in corpus_detected_full.csv and all pass CSVs:

  1. Pi (380 repos)
       .pi was removed from CONFIG_FILES after stage3a already ran.
       Remove "Pi" from every agents_found entry.
       For the 40 repos where Pi was the ONLY detected agent (all agentic
       via config_file signal) → reclassify to "none".

  2. claude-code (222 repos)
       Stage3c sometimes emits "claude-code" (lowercase hyphenated) instead
       of "Claude Code". Rename to "Claude Code" everywhere and deduplicate
       any entry that already had "Claude Code" alongside "claude-code".

  3. MCP (154 repos) → NO ACTION NEEDED
       MCP-only repos (28) are already correctly labelled ai_assisted via
       tool_configuration signal (medium). MCP = Model Context Protocol
       configuration, a legitimate AI-tooling signal. Kept as-is.

Files updated
-------------
  data/stage3/corpus_detected_full.csv   (primary output)
  data/stage3/pass1_results.csv
  data/stage3/pass2_results.csv
  data/stage3/pass3_results.csv

Usage
-----
  python3 scripts/stage3/stage3_cleanup.py
"""

import pandas as pd
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "stage3"

CORPUS_FILE = OUT_DIR / "corpus_detected_full.csv"
PASS1_FILE  = OUT_DIR / "pass1_results.csv"
PASS2_FILE  = OUT_DIR / "pass2_results.csv"
PASS3_FILE  = OUT_DIR / "pass3_results.csv"

REMOVE_AGENTS = {"Pi"}
RENAME_MAP    = {"claude-code": "Claude Code"}


# ── helpers ───────────────────────────────────────────────────────────────────

def clean_agents(raw):
    """Remove banned agents, apply renames, deduplicate, re-sort."""
    if pd.isna(raw) or str(raw).strip() == "":
        return ""
    agents = [a.strip() for a in str(raw).split("|") if a.strip()]
    agents = [RENAME_MAP.get(a, a) for a in agents]        # rename
    agents = [a for a in agents if a not in REMOVE_AGENTS]  # remove
    seen, deduped = set(), []
    for a in agents:
        if a not in seen:
            seen.add(a)
            deduped.append(a)
    return "|".join(sorted(deduped))


def fix_pass_csv(filepath):
    """Apply agent fixes to a pass CSV (no reclassification — pass CSVs
    don't need it; only corpus_detected_full carries the final label)."""
    if not filepath.exists():
        print(f"  Skipped (not found): {filepath.name}")
        return
    df = pd.read_csv(filepath, low_memory=False)
    if "agents_found" not in df.columns:
        print(f"  Skipped (no agents_found column): {filepath.name}")
        return
    before = df["agents_found"].copy()
    df["agents_found"] = df["agents_found"].apply(clean_agents)
    changed = (before != df["agents_found"]).sum()
    df.to_csv(filepath, index=False)
    print(f"  Updated {filepath.name}  ({changed:,} rows changed)")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("Stage 3 Cleanup")
    print("=" * 55)

    df = pd.read_csv(CORPUS_FILE, low_memory=False)

    # ── Before stats ──────────────────────────────────────────
    print("\nBEFORE")
    n_agentic    = (df["adoption_label"] == "agentic").sum()
    n_ai         = (df["adoption_label"] == "ai_assisted").sum()
    n_none       = (df["adoption_label"] == "none").sum()
    total        = len(df)
    total_adopted = n_agentic + n_ai
    print(f"  Agentic     : {n_agentic:>6,}  ({n_agentic/total*100:.1f}%)")
    print(f"  AI-assisted : {n_ai:>6,}  ({n_ai/total*100:.1f}%)")
    print(f"  None        : {n_none:>6,}  ({n_none/total*100:.1f}%)")
    print(f"  Total adopted: {total_adopted:,}  ({total_adopted/total*100:.1f}%)")

    pi_total  = df["agents_found"].str.contains("Pi", na=False).sum()
    pi_only   = (df["agents_found"] == "Pi").sum()
    cc_lower  = df["agents_found"].str.contains("claude-code", na=False).sum()
    print(f"\n  Pi repos       : {pi_total:,} total  ({pi_only:,} Pi-only → will become none)")
    print(f"  claude-code    : {cc_lower:,} repos  → will be renamed to Claude Code")
    print(f"  MCP            : no action (already correctly ai_assisted)")

    # ── Fix 1 & 2: clean agents_found ─────────────────────────
    df["agents_found"] = df["agents_found"].apply(clean_agents)

    # ── Reclassify Pi-only repos ──────────────────────────────
    # A repo that was agentic only because of a Pi config file and now has
    # no remaining agents → reclassify to none.
    # Use signal_source == "config_file" rather than strong_families because
    # corpus_detected_full.csv may store non-null strong_families for pass1 rows.
    empty_agents       = df["agents_found"].isna() | (df["agents_found"] == "")
    was_agentic        = df["adoption_label"] == "agentic"
    config_only_signal = df["signal_source"].fillna("") == "config_file"
    reclassify         = empty_agents & was_agentic & config_only_signal
    df.loc[reclassify, "adoption_label"] = "none"
    print(f"\n  Reclassified {reclassify.sum():,} repos: agentic → none")

    # ── After stats ───────────────────────────────────────────
    print("\nAFTER")
    n_agentic     = (df["adoption_label"] == "agentic").sum()
    n_ai          = (df["adoption_label"] == "ai_assisted").sum()
    n_none        = (df["adoption_label"] == "none").sum()
    total_adopted = n_agentic + n_ai
    print(f"  Agentic     : {n_agentic:>6,}  ({n_agentic/total*100:.1f}%)")
    print(f"  AI-assisted : {n_ai:>6,}  ({n_ai/total*100:.1f}%)")
    print(f"  None        : {n_none:>6,}  ({n_none/total*100:.1f}%)")
    print(f"  Total adopted: {total_adopted:,}  ({total_adopted/total*100:.1f}%)")

    print("\nTop 20 agents after cleanup:")
    agent_series = (
        df[df["agents_found"] != ""]["agents_found"]
        .str.split("|").explode()
    )
    top = agent_series.value_counts().head(20)
    for agent, count in top.items():
        print(f"  {agent:<40} {count:>6,}")

    # ── Save corpus ───────────────────────────────────────────
    df.to_csv(CORPUS_FILE, index=False)
    print(f"\nSaved: {CORPUS_FILE.name}")

    # ── Fix pass CSVs for consistency ─────────────────────────
    print("\nUpdating pass CSVs:")
    for f in [PASS1_FILE, PASS2_FILE, PASS3_FILE]:
        fix_pass_csv(f)

    print("\nDone.")


if __name__ == "__main__":
    main()

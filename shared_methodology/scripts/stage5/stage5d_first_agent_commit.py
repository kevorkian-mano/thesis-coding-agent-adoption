#!/usr/bin/env python3
"""
Stage 5g -- First Claude Code Commit + Config File Detection  (Point 3)
========================================================================
Samples Claude Code agentic React + Next.js repositories and determines:
  (A) When the FIRST Claude Code commit trailer appeared
  (B) When Claude Code config files (CLAUDE.md / .claude/) were first committed

Combining (A) and (B) reveals the developer's adoption pattern:

  ai_native      : both config AND trailer appear within DAY1_DAYS of creation
  config_first   : developer set up CLAUDE.md/config BEFORE first trailer commit
  trailer_first  : developer used Claude Code (got trailers) BEFORE adding config
  trailer_only   : trailers found but no config file ever committed

Population: React + Next.js (no Express) → agentic → Claude Code detected
            → trailer_count > 0

API calls per repo:
  ~2–3 pages  for all commits (trailer detection)
  ~3 calls    for config paths (CLAUDE.md, .claude/settings.json, .claude/CLAUDE.md)
  Total: ~5–6 calls per repo → 500 repos ≈ 2,500–3,000 calls ≈ ~30 min

Usage
-----
  export GITHUB_TOKEN=ghp_...
  python stage5g_first_agent_commit.py [--sample N] [--seed 42]

Input
-----
  data/stage5/rn_corpus.csv   (produced by stage5f)

Output
------
  data/stage5/first_agent_commit.csv         -- per-repo detailed results
  data/stage5/first_agent_commit_summary.csv -- aggregate statistics
  figures/stage5/fig_adoption_timing.pdf/.png
  figures/stage5/fig_adoption_pattern.pdf/.png
"""
# ══════════════════════════════════════════════════════════════════════════════
# TEAM CONFIGURATION — edit the variables in this block before running
# ══════════════════════════════════════════════════════════════════════════════
#
# NOTE FOR TEAM: This script is scoped to Claude Code repos with trailer_count > 0.
# Adjust the AGENT_FILTER variable below if studying a different agent.
#   AGENT_FILTER = "claude"   # filter string matched against agents_found column
#
# INPUT_CSV  : path to your Stage 1 corpus CSV
#              Required columns: full_name, owner_login, stars, commits,
#                                lang_bytes, created_at, primary_language
#              (replace with the equivalent columns in your stack's corpus)
#
# GITHUB_TOKEN: set via environment variable before running:
#   export GITHUB_TOKEN=ghp_...
#
# Outputs will be written to:  shared_methodology/data/stage5/
# ══════════════════════════════════════════════════════════════════════════════



import os
import re
import sys
import time
import argparse
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from pathlib import Path

ROOT        = Path(__file__).resolve().parents[2]
RN_CORP     = ROOT / "data" / "stage5" / "rn_corpus.csv"
OUT_DIR     = ROOT / "data"  / "stage5"
FIG_DIR     = ROOT / "figures" / "stage5"
CHECKPOINT  = OUT_DIR / "first_agent_commit.csv"   # live-written per repo
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

# ── Timing thresholds ─────────────────────────────────────────────────────────
DAY1_DAYS  =  7    # "day-1 adopter"  — used within first week
EARLY_DAYS = 30    # "early adopter"  — used within first month

# ── Claude Code config file paths to check ───────────────────────────────────
CONFIG_PATHS = [
    "CLAUDE.md",
    ".claude/settings.json",
    ".claude/CLAUDE.md",
]

# ── Commit trailer patterns (same as stage3c) ─────────────────────────────────
AGENT_PATTERNS = [
    (re.compile(r"co-authored-by:.*claude.*anthropic", re.I), "Claude Code"),
    (re.compile(r"co-authored-by:.*claude",            re.I), "Claude Code"),
    (re.compile(r"generated with claude code",         re.I), "Claude Code"),
    (re.compile(r"🤖 generated with claude",           re.I), "Claude Code"),
    (re.compile(r"co-authored-by:.*devin",             re.I), "Devin"),
    (re.compile(r"co-authored-by:.*codex",             re.I), "OpenAI Codex"),
    (re.compile(r"co-authored-by:.*jules",             re.I), "Jules"),
    (re.compile(r"co-authored-by:.*copilot",           re.I), "GitHub Copilot"),
    (re.compile(r"co-authored-by:.*cursor",            re.I), "Cursor"),
    (re.compile(r"co-authored-by:.*aider",             re.I), "Aider"),
    (re.compile(r"co-authored-by:.*windsurf",          re.I), "Windsurf"),
    (re.compile(r"co-authored-by:.*gemini",            re.I), "Gemini CLI"),
    (re.compile(r"co-authored-by:.*coderabbit",        re.I), "CodeRabbit"),
    (re.compile(r"co-authored-by:.*sweep",             re.I), "Sweep"),
    (re.compile(r"co-authored-by:.*openhands",         re.I), "OpenHands"),
]


def match_agent(message: str) -> str | None:
    for pattern, label in AGENT_PATTERNS:
        if pattern.search(message):
            return label
    return None


# ── GitHub API helpers ────────────────────────────────────────────────────────

def get_token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("ERROR: GITHUB_TOKEN not set.  Export it and rerun.")
        sys.exit(1)
    return token


def github_get(url: str, headers: dict, params: dict = None) -> requests.Response:
    """GET with automatic rate-limit retry and timeout retry."""
    timeout_wait = 15
    for attempt in range(4):          # up to 3 retries on timeout
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=45)
        except (requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectionError) as exc:
            if attempt < 3:
                print(f"\n  Network error ({exc.__class__.__name__}), "
                      f"retry {attempt+1}/3 in {timeout_wait}s …", flush=True)
                time.sleep(timeout_wait)
                timeout_wait *= 2
                continue
            raise   # give up after 3 retries
        if resp.status_code == 403 and "X-RateLimit-Reset" in resp.headers:
            reset_ts = int(resp.headers["X-RateLimit-Reset"])
            wait_sec = max(reset_ts - int(time.time()), 1)
            print(f"\n  Rate limited — sleeping {wait_sec}s …", flush=True)
            time.sleep(wait_sec + 2)
            continue
        if resp.status_code == 429:
            retry = int(resp.headers.get("Retry-After", 60))
            print(f"\n  429 — sleeping {retry}s …", flush=True)
            time.sleep(retry + 2)
            continue
        return resp


# ── Signal A: First commit trailer ───────────────────────────────────────────

def find_first_trailer_commit(owner: str, repo: str,
                               headers: dict,
                               total_commits: int) -> dict | None:
    """
    Paginate all commits (newest→oldest), sort chronologically, return the
    FIRST (oldest) commit containing a Claude Code trailer.
    """
    PER_PAGE    = 100
    total_pages = max(1, int(np.ceil(total_commits / PER_PAGE)))
    all_commits = []

    for page in range(1, total_pages + 1):
        url  = f"https://api.github.com/repos/{owner}/{repo}/commits"
        resp = github_get(url, headers, {"per_page": PER_PAGE, "page": page})
        if resp.status_code != 200:
            break
        data = resp.json()
        if not data:
            break
        for c in data:
            try:
                all_commits.append((
                    c["commit"]["committer"]["date"],
                    c["sha"],
                    c["commit"]["message"],
                ))
            except (KeyError, TypeError):
                pass
        time.sleep(0.05)

    if not all_commits:
        return None

    all_commits.sort(key=lambda x: x[0])   # oldest first

    for idx, (dt_str, sha, msg) in enumerate(all_commits):
        agent = match_agent(msg)
        if agent:
            return {
                "sha":          sha,
                "date":         dt_str[:10],
                "agent":        agent,
                "commit_index": idx,
                "total_found":  len(all_commits),
            }
    return None


# ── Signal B: First config file commit ───────────────────────────────────────

def find_first_config_commit(owner: str, repo: str, headers: dict) -> dict | None:
    """
    For each Claude Code config path, retrieve all commits that touched it
    and find the OLDEST one.  Returns the earliest date across all paths,
    plus which file was found first.

    Uses path-filtered commits API — very fast since config files
    typically have only a handful of commits touching them.
    """
    earliest_date = None
    earliest_path = None

    for config_path in CONFIG_PATHS:
        url  = f"https://api.github.com/repos/{owner}/{repo}/commits"
        page = 1
        path_oldest = None

        while True:
            resp = github_get(url, headers,
                              {"path": config_path, "per_page": 100, "page": page})
            if resp.status_code != 200:
                break
            data = resp.json()
            if not data:
                break
            for c in data:
                try:
                    dt = c["commit"]["committer"]["date"]
                    # keep going — last item on last page = oldest commit
                    path_oldest = dt
                except (KeyError, TypeError):
                    pass
            if len(data) < 100:
                break   # no more pages
            page += 1

        time.sleep(0.05)

        if path_oldest:
            if earliest_date is None or path_oldest < earliest_date:
                earliest_date = path_oldest
                earliest_path = config_path

    if earliest_date is None:
        return None
    return {"date": earliest_date[:10], "path": earliest_path}


# ── Categorisation ────────────────────────────────────────────────────────────

def timing_category(days: float) -> str:
    if days <= DAY1_DAYS:
        return "day_1"
    if days <= EARLY_DAYS:
        return "early"
    return "late"


def adoption_pattern(trailer_days, config_days) -> str:
    """
    Classify how the developer adopted Claude Code based on the relative
    timing of the first commit trailer vs the first config file.

      ai_native      — both appear within DAY1_DAYS (7 days) of repo creation
      config_first   — CLAUDE.md / .claude/ committed before first trailer
      trailer_first  — trailer appeared before config was set up
      trailer_only   — trailers detected but no config file ever committed
    """
    has_trailer = trailer_days is not None
    has_config  = config_days  is not None

    if not has_trailer:
        return "no_trailer"        # shouldn't happen given our filter
    if not has_config:
        return "trailer_only"

    # Both present — classify by relative order
    both_early = (trailer_days <= DAY1_DAYS) and (config_days <= DAY1_DAYS)
    if both_early:
        return "ai_native"

    if config_days <= trailer_days:
        return "config_first"
    return "trailer_first"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=None,
                        help="Limit to N repos (default: full population)")
    parser.add_argument("--seed",   type=int, default=42,
                        help="Random seed when --sample is used")
    parser.add_argument("--force",  action="store_true",
                        help="Ignore existing checkpoint and restart from scratch")
    args = parser.parse_args()

    print("Stage 5g -- First Claude Code Commit + Config File Detection")
    print("=" * 65)

    token   = get_token()
    headers = {
        "Authorization": f"token {token}",
        "Accept":        "application/vnd.github.v3+json",
    }

    if not RN_CORP.exists():
        print(f"ERROR: {RN_CORP} not found.  Run stage5f first.")
        sys.exit(1)

    df = pd.read_csv(RN_CORP, low_memory=False)
    df["created_at"] = pd.to_datetime(df["created_at"])

    # ── Claude Code filter ────────────────────────────────────────────────────
    CLAUDE_RE = re.compile(r"claude", re.I)
    df["has_claude"] = df["agents_found"].fillna("").apply(
        lambda x: bool(CLAUDE_RE.search(x))
    )
    candidates = df[
        (df["adoption_label"] == "agentic") &
        df["has_claude"] &
        (df["trailer_count"].fillna(0) > 0)
    ].copy()

    total_agentic = (df["adoption_label"] == "agentic").sum()
    print(f"Agentic React+Next.js repos              : {total_agentic:,}")
    print(f"  → with Claude Code detected            : {df['has_claude'].sum():,}")
    print(f"  → with Claude Code + trailer signals   : {len(candidates):,}")

    # ── Checkpoint: load already-processed repos ──────────────────────────────
    done_repos: set[str] = set()
    if CHECKPOINT.exists() and not args.force:
        ckpt = pd.read_csv(CHECKPOINT, usecols=["full_name"])
        done_repos = set(ckpt["full_name"].dropna().tolist())
        print(f"\nCheckpoint found : {len(done_repos):,} repos already processed.")
    elif args.force and CHECKPOINT.exists():
        CHECKPOINT.unlink()
        print("\n--force: deleted checkpoint, restarting from scratch.")

    # ── Build work list ───────────────────────────────────────────────────────
    if args.sample:
        work = candidates.sample(
            n=min(args.sample, len(candidates)), random_state=args.seed
        )
        print(f"Sample mode      : {len(work):,} repos  (seed={args.seed})")
    else:
        work = candidates.copy()
        print(f"Full population  : {len(work):,} repos")

    remaining = work[~work["full_name"].isin(done_repos)].copy()
    print(f"Remaining        : {len(remaining):,}  "
          f"(skipping {len(done_repos):,} already done)")
    print(f"(React+Next.js · agentic · Claude Code · trailer_count > 0)")
    print()

    if remaining.empty:
        print("Nothing left to process — all repos already in checkpoint.")
        print("Proceeding to generate summary and figures from existing data.")

    # ── CSV columns in order (written once as header if new file) ─────────────
    CSV_COLS = [
        "full_name", "created_at", "total_commits",
        "first_trailer_date", "first_trailer_agent",
        "trailer_commit_index", "pct_commits_before_ai",
        "days_to_first_trailer", "trailer_timing",
        "first_config_date", "first_config_file", "days_to_first_config",
        "adoption_pattern",
    ]
    write_header = not CHECKPOINT.exists()

    total_work = len(work)   # for progress display

    for i, (_, row) in enumerate(remaining.iterrows(), len(done_repos) + 1):
        full_name = row["full_name"]
        owner, repo = full_name.split("/", 1)
        created = pd.Timestamp(row["created_at"]).normalize()
        total_c = int(row["commits"]) if pd.notna(row["commits"]) else 200

        print(f"[{i:>4}/{total_work}]  {full_name:<52}", end=" ", flush=True)

        try:
            # ── Signal A: first trailer commit ───────────────────────────────
            trailer = find_first_trailer_commit(owner, repo, headers, total_c)

            # ── Signal B: first config file commit ───────────────────────────
            config = find_first_config_commit(owner, repo, headers)
        except Exception as exc:
            print(f"ERROR: {exc}", flush=True)
            # Write a placeholder row so this repo is skipped on resume
            record = {col: None for col in CSV_COLS}
            record["full_name"]       = full_name
            record["created_at"]      = str(row["created_at"])[:10]
            record["total_commits"]   = total_c
            record["adoption_pattern"] = "error"
            pd.DataFrame([record], columns=CSV_COLS).to_csv(
                CHECKPOINT, mode="a", header=write_header, index=False
            )
            write_header = False
            continue

        # ── Compute derived fields ────────────────────────────────────────────
        trailer_days = trailer_date = commit_index = total_found = None
        pct_before   = None
        timing       = "not_found"

        if trailer:
            trailer_dt   = pd.Timestamp(trailer["date"])
            trailer_days = (trailer_dt - created).days
            trailer_date = trailer["date"]
            commit_index = trailer["commit_index"]
            total_found  = trailer["total_found"]
            pct_before   = round(commit_index / total_found * 100, 1) if total_found else 0
            timing       = timing_category(trailer_days)

        config_days = config_date = config_file = None
        if config:
            config_dt   = pd.Timestamp(config["date"])
            config_days = (config_dt - created).days
            config_date = config["date"]
            config_file = config["path"]

        pattern = adoption_pattern(trailer_days, config_days)

        # ── Print one-line summary ────────────────────────────────────────────
        t_str = f"trailer day {trailer_days:>3}" if trailer_days is not None else "no trailer  "
        c_str = f"config day {config_days:>3}" if config_days is not None else "no config  "
        print(f"{t_str}  |  {c_str}  [{pattern}]")

        # ── Write row immediately to checkpoint CSV ───────────────────────────
        record = {
            "full_name":             full_name,
            "created_at":            str(row["created_at"])[:10],
            "total_commits":         total_found or total_c,
            "first_trailer_date":    trailer_date,
            "first_trailer_agent":   trailer["agent"] if trailer else None,
            "trailer_commit_index":  commit_index,
            "pct_commits_before_ai": pct_before,
            "days_to_first_trailer": trailer_days,
            "trailer_timing":        timing,
            "first_config_date":     config_date,
            "first_config_file":     config_file,
            "days_to_first_config":  config_days,
            "adoption_pattern":      pattern,
        }
        pd.DataFrame([record], columns=CSV_COLS).to_csv(
            CHECKPOINT, mode="a", header=write_header, index=False
        )
        write_header = False   # header written once

    # ── Load full checkpoint for summary + figures ────────────────────────────
    res_df = pd.read_csv(CHECKPOINT, low_memory=False)
    print(f"\nCheckpoint total: {len(res_df):,} repos processed.")

    # ── Summary statistics ────────────────────────────────────────────────────
    found    = res_df[res_df["trailer_timing"] != "not_found"].copy()
    found["days_to_first_trailer"] = found["days_to_first_trailer"].astype(float)
    has_cfg  = res_df["first_config_date"].notna()

    timing_counts  = found["trailer_timing"].value_counts()
    pattern_counts = res_df["adoption_pattern"].value_counts()

    print(f"\n{'─'*65}")
    print(f"TRAILER signals")
    print(f"  Found in          : {len(found):,} / {len(res_df):,} repos "
          f"({len(found)/len(res_df)*100:.1f}%)")
    print(f"  day_1 (≤{DAY1_DAYS}d)   : {timing_counts.get('day_1',0):,}  "
          f"({timing_counts.get('day_1',0)/len(found)*100:.1f}%)")
    print(f"  early (≤{EARLY_DAYS}d)  : {timing_counts.get('early',0):,}  "
          f"({timing_counts.get('early',0)/len(found)*100:.1f}%)")
    print(f"  late  (>{EARLY_DAYS}d)  : {timing_counts.get('late',0):,}  "
          f"({timing_counts.get('late',0)/len(found)*100:.1f}%)")
    print(f"  Median days       : {found['days_to_first_trailer'].median():.0f}")
    print(f"  Median % before   : {found['pct_commits_before_ai'].median():.1f}%")

    print(f"\nCONFIG FILES (CLAUDE.md / .claude/)")
    print(f"  Found in          : {has_cfg.sum():,} / {len(res_df):,} repos "
          f"({has_cfg.sum()/len(res_df)*100:.1f}%)")
    if has_cfg.sum() > 0:
        cfg_days = res_df.loc[has_cfg, "days_to_first_config"].astype(float)
        print(f"  Median config day : {cfg_days.median():.0f}")
        cfg_files = res_df.loc[has_cfg, "first_config_file"].value_counts()
        for f, c in cfg_files.items():
            print(f"    {f:<35} {c:,}")

    print(f"\nADOPTION PATTERNS")
    pattern_order = ["ai_native", "config_first", "trailer_first", "trailer_only"]
    pattern_labels = {
        "ai_native":     "AI-native (both ≤7d)",
        "config_first":  "Config-first (CLAUDE.md before trailers)",
        "trailer_first": "Trailer-first (used before configuring)",
        "trailer_only":  "Trailer-only (no config file found)",
    }
    for p in pattern_order:
        n = pattern_counts.get(p, 0)
        print(f"  {pattern_labels[p]:<45} {n:>5,}  ({n/len(res_df)*100:.1f}%)")

    # Save summary
    pd.DataFrame([{
        "sample_n":           len(res_df),
        "trailer_found_n":    len(found),
        "trailer_found_pct":  round(len(found)/len(res_df)*100, 1),
        "day1_n":             timing_counts.get("day_1", 0),
        "early_n":            timing_counts.get("early", 0),
        "late_n":             timing_counts.get("late",  0),
        "day1_pct":           round(timing_counts.get("day_1",0)/max(len(found),1)*100, 1),
        "early_pct":          round(timing_counts.get("early",0)/max(len(found),1)*100, 1),
        "late_pct":           round(timing_counts.get("late", 0)/max(len(found),1)*100, 1),
        "median_trailer_days":  found["days_to_first_trailer"].median(),
        "median_pct_before":    found["pct_commits_before_ai"].median(),
        "config_found_n":       int(has_cfg.sum()),
        "config_found_pct":     round(has_cfg.sum()/len(res_df)*100, 1),
        "ai_native_n":          pattern_counts.get("ai_native",    0),
        "config_first_n":       pattern_counts.get("config_first", 0),
        "trailer_first_n":      pattern_counts.get("trailer_first",0),
        "trailer_only_n":       pattern_counts.get("trailer_only", 0),
    }]).to_csv(OUT_DIR / "first_agent_commit_summary.csv", index=False)

    # ── Figure 1: timing donut + days histogram ───────────────────────────────
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    sizes_d  = [timing_counts.get(k, 0) for k in ["day_1", "early", "late"]]
    labels_d = [f"Day-1\n(≤{DAY1_DAYS}d)", f"Early\n({DAY1_DAYS+1}–{EARLY_DAYS}d)",
                f"Late\n(>{EARLY_DAYS}d)"]
    wedges, _, autotexts = ax1.pie(
        sizes_d, labels=labels_d,
        colors=["#2166ac", "#74add1", "#d9d9d9"],
        autopct="%1.1f%%", startangle=90,
        wedgeprops=dict(width=0.55),
        textprops=dict(fontsize=10),
    )
    for at in autotexts:
        at.set_fontsize(10); at.set_fontweight("bold")
    ax1.set_title("When Was Claude Code First Used?\n(days since repo creation)",
                  fontweight="bold")

    days_vals = found["days_to_first_trailer"].clip(upper=365)
    ax2.hist(days_vals, bins=30, color="#2166ac", edgecolor="white", alpha=0.85)
    ax2.axvline(DAY1_DAYS,  color="#d62728", ls="--", lw=1.5,
                label=f"Day-1 threshold ({DAY1_DAYS}d)")
    ax2.axvline(EARLY_DAYS, color="#f1a340", ls="--", lw=1.5,
                label=f"Early threshold ({EARLY_DAYS}d)")
    med = found["days_to_first_trailer"].median()
    ax2.axvline(med, color="black", ls="-", lw=2, label=f"Median ({med:.0f}d)")
    ax2.set_xlabel("Days from Repo Creation to First Claude Code Commit")
    ax2.set_ylabel("Number of Repos")
    ax2.set_title("Distribution of Adoption Delay\n(capped at 365 days)",
                  fontweight="bold")
    ax2.legend(fontsize=9)
    ax2.grid(axis="y", alpha=0.3)

    fig.suptitle(
        f"First Claude Code Commit — React + Next.js sample (n={len(found):,})",
        fontsize=12, fontweight="bold",
    )
    plt.tight_layout()
    for ext in ("pdf", "png"):
        plt.savefig(FIG_DIR / f"fig_adoption_timing.{ext}",
                    bbox_inches="tight", dpi=150)
    plt.close()
    print("\nSaved: fig_adoption_timing.pdf / .png")

    # ── Figure 2: adoption pattern horizontal bar chart ───────────────────────
    fig, ax = plt.subplots(figsize=(10, 4.5))
    pattern_data = [(pattern_labels[p], pattern_counts.get(p, 0))
                    for p in pattern_order]
    labels_p = [x[0] for x in pattern_data]
    counts_p = [x[1] for x in pattern_data]
    pcts_p   = [c / len(res_df) * 100 for c in counts_p]

    colours_p = ["#2166ac", "#74add1", "#f1a340", "#d9d9d9"]
    bars = ax.barh(labels_p, pcts_p, color=colours_p, edgecolor="white", height=0.55)
    for bar, pct, cnt in zip(bars, pcts_p, counts_p):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                f"{pct:.1f}%  (n={cnt:,})", va="center", fontsize=10)

    ax.set_xlabel("Share of Sampled Repos (%)", fontsize=11)
    ax.set_title(
        "How Developers Adopted Claude Code\n"
        "Trailer timing vs CLAUDE.md / .claude/ config setup",
        fontsize=12, fontweight="bold",
    )
    ax.xaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_xlim(0, max(pcts_p) * 1.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    for ext in ("pdf", "png"):
        plt.savefig(FIG_DIR / f"fig_adoption_pattern.{ext}",
                    bbox_inches="tight", dpi=150)
    plt.close()
    print("Saved: fig_adoption_pattern.pdf / .png")
    print("\nStage 5g complete.")


if __name__ == "__main__":
    main()

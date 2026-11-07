#!/usr/bin/env python3
"""
Stage 5i -- Config File Timestamps
====================================
For every repo detected as agentic via config file (Pass 3a of Stage 3),
retrieve the OLDEST commit that first added each detected config file.
This gives the exact date AI tooling was first configured in the repo.

  first_ai_date = min(oldest_commit_date)  across all detected config files

API pattern
-----------
  GET /repos/{owner}/{repo}/commits?path={file}&per_page=100
  For each file: check Link header for last page → fetch last page → last
  commit on that page is the oldest.  Typically 1–3 API calls per repo.

Scale estimate
--------------
  ~28,397 agentic-via-config repos
  ~1–3 API calls each → ~56,000–85,000 calls
  At GitHub's 5,000 req/hr authenticated limit → 11–17 hours
  Checkpointing lets you resume from where you left off.

Input
-----
  data/stage3/pass1_results.csv
    Columns: full_name, config_files_found, agents_found, adoption_label, ...

Output
------
  data/stage5/config_timestamps.csv
    Columns: full_name, first_ai_date, first_config_file, n_configs, api_status

Usage
-----
  export GITHUB_TOKEN=ghp_...
  python3 scripts/stage5/stage5i_config_timestamps.py [--limit N] [--resume]
"""

import os
import re
import sys
import time
import argparse
import requests
import pandas as pd
from pathlib import Path

ROOT       = Path(__file__).resolve().parents[2]
PASS1      = ROOT / "data" / "stage3" / "pass1_results.csv"
OUT_DIR    = ROOT / "data" / "stage5"
OUT_CSV    = OUT_DIR / "config_timestamps.csv"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SLEEP_BETWEEN = 0.08   # seconds between requests (stays under rate limit)


# ── GitHub API helpers ────────────────────────────────────────────────────────

def get_token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        sys.exit("ERROR: GITHUB_TOKEN not set.  Export it and rerun.")
    return token


def github_get(url: str, headers: dict, params: dict | None = None) -> requests.Response:
    wait = 20
    for attempt in range(5):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=45)
        except (requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectionError) as exc:
            if attempt < 4:
                print(f"\n  Network error ({exc.__class__.__name__}), "
                      f"retry {attempt+1}/4 in {wait}s …", flush=True)
                time.sleep(wait)
                wait *= 2
                continue
            raise
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
    return resp  # return last attempt


def parse_last_page(link_header: str) -> int | None:
    """Extract the last page number from a GitHub Link header."""
    if not link_header:
        return None
    m = re.search(r'[?&]page=(\d+)[^>]*>;\s*rel="last"', link_header)
    return int(m.group(1)) if m else None


# ── Core: oldest commit for a single file path ───────────────────────────────

def oldest_commit_for_path(owner: str, repo: str, path: str,
                            headers: dict) -> str | None:
    """
    Returns the ISO date string of the oldest commit that touched `path`,
    or None if the path has no commit history or the API returns an error.
    """
    base_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    params   = {"path": path, "per_page": 100, "page": 1}

    # First request — may be the only one
    resp = github_get(base_url, headers, params)
    time.sleep(SLEEP_BETWEEN)

    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        return None

    commits = resp.json()
    if not commits:
        return None

    # Check whether there are more pages
    last_page = parse_last_page(resp.headers.get("Link", ""))

    if last_page and last_page > 1:
        # Fetch the last page — its final commit is the oldest
        params2 = {"path": path, "per_page": 100, "page": last_page}
        resp2 = github_get(base_url, headers, params2)
        time.sleep(SLEEP_BETWEEN)
        if resp2.status_code == 200 and resp2.json():
            commits = resp2.json()

    # Last item on the last page = oldest commit for this file
    oldest = commits[-1]
    try:
        return oldest["commit"]["committer"]["date"][:10]
    except (KeyError, TypeError):
        try:
            return oldest["commit"]["author"]["date"][:10]
        except (KeyError, TypeError):
            return None


# ── Per-repo processing ───────────────────────────────────────────────────────

def process_repo(full_name: str, config_files_raw: str,
                 headers: dict) -> dict:
    """
    Given a repo full_name and the pipe-separated list of detected config
    files, find the oldest commit across all files.
    """
    result = {
        "full_name":        full_name,
        "first_ai_date":    None,
        "first_config_file": None,
        "n_configs":        0,
        "api_status":       "ok",
    }

    if pd.isna(config_files_raw) or not str(config_files_raw).strip():
        result["api_status"] = "no_config_list"
        return result

    files = [f.strip() for f in str(config_files_raw).split("|") if f.strip()]
    result["n_configs"] = len(files)

    owner, repo = full_name.split("/", 1)
    best_date  = None
    best_file  = None

    for f in files:
        date = oldest_commit_for_path(owner, repo, f, headers)
        if date:
            if best_date is None or date < best_date:
                best_date = date
                best_file = f

    result["first_ai_date"]     = best_date
    result["first_config_file"] = best_file
    if best_date is None:
        result["api_status"] = "no_date_found"

    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit",  type=int, default=0,
                        help="Process at most N repos (0 = all)")
    parser.add_argument("--resume", action="store_true",
                        help="Skip repos already in output CSV")
    args = parser.parse_args()

    if not PASS1.exists():
        sys.exit(f"Missing: {PASS1}\nRun stage3a first.")

    headers = {"Authorization": f"token {get_token()}",
               "Accept": "application/vnd.github+json"}

    # Load pass1 and filter to agentic repos with config files
    df = pd.read_csv(PASS1, low_memory=False)
    agentic = df[df["adoption_label"] == "agentic"].copy()
    # config_files_found may be NaN for some; keep only rows where it's present
    agentic = agentic[agentic["config_files_found"].notna() &
                      (agentic["config_files_found"].str.strip() != "")]
    repos = agentic["full_name"].tolist()

    # Resume: skip already-processed repos
    done: set[str] = set()
    if args.resume and OUT_CSV.exists():
        done_df = pd.read_csv(OUT_CSV)
        done = set(done_df["full_name"].tolist())
        print(f"Resuming — {len(done):,} repos already processed.")

    repos = [r for r in repos if r not in done]
    if args.limit > 0:
        repos = repos[:args.limit]

    total = len(repos)
    print(f"Stage 5i -- Config File Timestamps")
    print("=" * 55)
    print(f"Repos to process : {total:,}")
    print(f"Output           : {OUT_CSV}")
    print()

    # Open output file (append mode so checkpointing works)
    write_header = not OUT_CSV.exists() or not args.resume
    out_fh = open(OUT_CSV, "a", buffering=1)
    if write_header:
        out_fh.write("full_name,first_ai_date,first_config_file,n_configs,api_status\n")

    ok_count   = 0
    err_count  = 0
    start_time = time.time()

    for i, full_name in enumerate(repos, 1):
        config_files_raw = agentic.loc[
            agentic["full_name"] == full_name, "config_files_found"
        ].iloc[0]

        result = process_repo(full_name, config_files_raw, headers)

        # Write line immediately (checkpointing)
        cfg_file = str(result["first_config_file"] or "").replace(",", ";")
        line = (f"{result['full_name']},"
                f"{result['first_ai_date'] or ''},"
                f"{cfg_file},"
                f"{result['n_configs']},"
                f"{result['api_status']}\n")
        out_fh.write(line)

        if result["first_ai_date"]:
            ok_count += 1
        else:
            err_count += 1

        if i % 100 == 0 or i == total:
            elapsed = time.time() - start_time
            rate    = i / elapsed if elapsed > 0 else 0
            eta_s   = (total - i) / rate if rate > 0 else 0
            eta_m   = eta_s / 60
            print(f"  [{i:>6,}/{total:,}]  ok={ok_count:,}  no_date={err_count:,}"
                  f"  rate={rate:.1f} repos/s  ETA={eta_m:.0f}m", flush=True)

    out_fh.close()
    print()
    print(f"Done.  Timestamps found: {ok_count:,} / {total:,}")
    print(f"Saved: {OUT_CSV}")


if __name__ == "__main__":
    main()

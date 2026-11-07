#!/usr/bin/env python3
"""
Stage 5j -- Trailer-Based First AI Timestamps
===============================================
For every repo detected as agentic via commit trailers (Pass 3b of Stage 3),
scan the full commit history and find the OLDEST commit that carries an
AI-agent trailer.  That commit's date = first_ai_date for the repo.

Strategy
--------
  GitHub returns commits newest-first (page 1 = most recent).
  We want the OLDEST trailer commit, so we:
    1. Fetch page 1 to get total_commits estimate via Link header.
    2. Jump straight to the LAST page (oldest commits).
    3. Scan page-by-page from last → first, collecting ALL commits.
    4. Sort chronologically and find the first (oldest) trailer match.

  This avoids downloading every page for large repos when the first AI
  commit appeared late in the project.  However, to be exact we still scan
  all pages (trailer could appear on any page).

Scale estimate
--------------
  ~11,937 repos with trailer_count > 0
  Avg ~5–10 pages per repo (repos created since Feb 2025, so young)
  → ~60,000–120,000 API calls → 12–24 hours
  Checkpointing allows safe resumption.

Input
-----
  data/stage3/pass2_results.csv
    Columns: full_name, trailer_count, agents_found, adoption_label, ...

Output
------
  data/stage5/trailer_timestamps.csv
    Columns: full_name, first_ai_date, first_trailer_agent, total_commits_scanned,
             api_status

Usage
-----
  export GITHUB_TOKEN=ghp_...
  python3 scripts/stage5/stage5j_trailer_timestamps.py [--limit N] [--resume]
"""

import os
import re
import sys
import time
import argparse
import requests
import pandas as pd
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
PASS2   = ROOT / "data" / "stage3" / "pass2_results.csv"
OUT_DIR = ROOT / "data" / "stage5"
OUT_CSV = OUT_DIR / "trailer_timestamps.csv"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SLEEP_BETWEEN = 0.08   # seconds between requests

# Same trailer patterns as stage3b / stage5d
AGENT_PATTERNS = [
    (re.compile(r"co-authored-by:.*claude.*anthropic",    re.I), "Claude Code"),
    (re.compile(r"co-authored-by:.*claude",               re.I), "Claude Code"),
    (re.compile(r"generated with claude code",            re.I), "Claude Code"),
    (re.compile(r"🤖 generated with claude",              re.I), "Claude Code"),
    (re.compile(r"co-authored-by:.*devin",                re.I), "Devin"),
    (re.compile(r"co-authored-by:.*codex",                re.I), "OpenAI Codex"),
    (re.compile(r"co-authored-by:.*jules",                re.I), "Jules"),
    (re.compile(r"co-authored-by:.*copilot",              re.I), "GitHub Copilot"),
    (re.compile(r"co-authored-by:.*cursor",               re.I), "Cursor"),
    (re.compile(r"co-authored-by:.*aider",                re.I), "Aider"),
    (re.compile(r"co-authored-by:.*windsurf",             re.I), "Windsurf"),
    (re.compile(r"co-authored-by:.*gemini",               re.I), "Gemini CLI"),
    (re.compile(r"co-authored-by:.*coderabbit",           re.I), "CodeRabbit"),
    (re.compile(r"co-authored-by:.*sweep",                re.I), "Sweep"),
    (re.compile(r"co-authored-by:.*openhands",            re.I), "OpenHands"),
    (re.compile(r"co-authored-by:.*github-actions\[bot\]", re.I), "Generic"),
    (re.compile(r"co-authored-by:",                       re.I), "Generic"),
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
    return resp


def parse_last_page(link_header: str) -> int:
    """Extract last page number from Link header; returns 1 if not found."""
    if not link_header:
        return 1
    m = re.search(r'[?&]page=(\d+)[^>]*>;\s*rel="last"', link_header)
    return int(m.group(1)) if m else 1


# ── Core: find oldest trailer commit across all commits ───────────────────────

def find_first_trailer(owner: str, repo: str, headers: dict) -> dict:
    """
    Scan all commits of the repo and return details of the OLDEST commit
    carrying an AI trailer.  Returns a dict with keys:
      first_ai_date, first_trailer_agent, total_commits_scanned, api_status
    """
    base_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    per_page = 100

    # Page 1: get total pages
    resp1 = github_get(base_url, headers, {"per_page": per_page, "page": 1})
    time.sleep(SLEEP_BETWEEN)

    if resp1.status_code == 404:
        return {"first_ai_date": None, "first_trailer_agent": None,
                "total_commits_scanned": 0, "api_status": "repo_not_found"}
    if resp1.status_code != 200:
        return {"first_ai_date": None, "first_trailer_agent": None,
                "total_commits_scanned": 0,
                "api_status": f"http_{resp1.status_code}"}

    page1_data = resp1.json()
    if not page1_data:
        return {"first_ai_date": None, "first_trailer_agent": None,
                "total_commits_scanned": 0, "api_status": "empty_response"}

    last_page = parse_last_page(resp1.headers.get("Link", ""))

    # Collect all commits: start from page 1 data, then fetch remaining pages
    all_commits: list[tuple[str, str, str]] = []  # (date, sha, message)

    for c in page1_data:
        try:
            all_commits.append((
                c["commit"]["committer"]["date"],
                c["sha"],
                c["commit"]["message"],
            ))
        except (KeyError, TypeError):
            pass

    for page in range(2, last_page + 1):
        resp = github_get(base_url, headers, {"per_page": per_page, "page": page})
        time.sleep(SLEEP_BETWEEN)
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

    if not all_commits:
        return {"first_ai_date": None, "first_trailer_agent": None,
                "total_commits_scanned": 0, "api_status": "no_commits"}

    # Sort oldest → newest and find first trailer
    all_commits.sort(key=lambda x: x[0])

    for date_str, sha, msg in all_commits:
        agent = match_agent(msg)
        if agent:
            return {
                "first_ai_date":          date_str[:10],
                "first_trailer_agent":    agent,
                "total_commits_scanned":  len(all_commits),
                "api_status":             "ok",
            }

    return {
        "first_ai_date":         None,
        "first_trailer_agent":   None,
        "total_commits_scanned": len(all_commits),
        "api_status":            "trailer_not_found",
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit",  type=int, default=0,
                        help="Process at most N repos (0 = all)")
    parser.add_argument("--resume", action="store_true",
                        help="Skip repos already in output CSV")
    args = parser.parse_args()

    if not PASS2.exists():
        sys.exit(f"Missing: {PASS2}\nRun stage3b first.")

    headers = {"Authorization": f"token {get_token()}",
               "Accept": "application/vnd.github+json"}

    df = pd.read_csv(PASS2, low_memory=False)
    # Only repos where trailers were actually found
    agentic = df[(df["adoption_label"] == "agentic") &
                 (df["trailer_count"].fillna(0) > 0)]
    repos = agentic["full_name"].tolist()

    # Resume
    done: set[str] = set()
    if args.resume and OUT_CSV.exists():
        done_df = pd.read_csv(OUT_CSV)
        done = set(done_df["full_name"].tolist())
        print(f"Resuming — {len(done):,} repos already processed.")

    repos = [r for r in repos if r not in done]
    if args.limit > 0:
        repos = repos[:args.limit]

    total = len(repos)
    print(f"Stage 5j -- Trailer-Based First AI Timestamps")
    print("=" * 55)
    print(f"Repos to process : {total:,}")
    print(f"Output           : {OUT_CSV}")
    print()

    write_header = not OUT_CSV.exists() or not args.resume
    out_fh = open(OUT_CSV, "a", buffering=1)
    if write_header:
        out_fh.write("full_name,first_ai_date,first_trailer_agent,"
                     "total_commits_scanned,api_status\n")

    ok_count  = 0
    err_count = 0
    start_time = time.time()

    for i, full_name in enumerate(repos, 1):
        owner, repo = full_name.split("/", 1)
        result = find_first_trailer(owner, repo, headers)

        agent_safe = str(result["first_trailer_agent"] or "").replace(",", ";")
        line = (f"{full_name},"
                f"{result['first_ai_date'] or ''},"
                f"{agent_safe},"
                f"{result['total_commits_scanned']},"
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
            print(f"  [{i:>6,}/{total:,}]  ok={ok_count:,}  no_date={err_count:,}"
                  f"  rate={rate:.1f} repos/s  ETA={eta_s/60:.0f}m", flush=True)

    out_fh.close()
    print()
    print(f"Done.  Timestamps found: {ok_count:,} / {total:,}")
    print(f"Saved: {OUT_CSV}")


if __name__ == "__main__":
    main()

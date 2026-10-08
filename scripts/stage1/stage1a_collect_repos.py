#!/usr/bin/env python3
"""
Stage 1a — Global Corpus Collection
=====================================
Collects JavaScript / TypeScript repositories from GitHub that meet the
professor's criteria. Based on the team's shared collection script, adapted
for the JS/TS/npm thesis topic.

Filters applied here (Stage 1a):
  - language: JavaScript OR TypeScript
  - created:  >= 2025-02-24  (repos born in the AI agent era)
  - stars:    >= 4
  - commits:  >= 50
  - fork:     false (repo itself is not a fork)
  - JS+TS combined language bytes >= 175,000 (175 KB)

NOT applied here (applied in Stage 1b):
  - package.json + lockfile check (npm ecosystem verification)

Two-stage fetch (same as team template):
  Stage 1 (cheap)  — search returns metadata + language bytes.
                     Drop repos where JS+TS bytes < MIN_LANG_BYTES.
  Stage 2 (costly) — fetch commit counts only for repos that survived stage 1.
                     Drop repos with commits < MIN_COMMITS.

Date windowing: searches are split into WINDOW_DAYS-day windows to stay under
GitHub's 1000-result-per-query cap. Windows with >1000 results are split
recursively by time.

Resume support: completed windows are written to PROGRESS_FILE so the script
can be stopped and restarted without re-fetching.

INPUTS
------
  None (pulls from GitHub API)

OUTPUTS
-------
  data/stage1/global_corpus_raw.csv   — repos that passed Stage 1a filters
  data/stage1/progress_stage1a.txt    — completed windows (resume support)

USAGE
-----
  export GITHUB_TOKEN=your_token_here
  python3 stage1a_collect_repos.py
"""

import csv
import os
import sys
import time
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path

import requests

# ── Configuration ─────────────────────────────────────────────────────────────
TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    sys.exit("ERROR: GITHUB_TOKEN environment variable is not set.\n"
             "Run: export GITHUB_TOKEN=your_token_here")

MIN_STARS      = 4           # repos with fewer stars are excluded
MIN_COMMITS    = 50          # repos with fewer commits are excluded
MIN_LANG_BYTES = 175_000     # combined JS + TS bytes must be >= 175 KB
CREATED_FROM   = date(2025, 2, 24)   # only repos created on or after this date
CREATED_TO     = date.today()

WINDOW_DAYS    = 5           # initial date window size (days)
PAGE_SIZE      = 50          # repos per GraphQL page (max 100)
MAX_RETRIES    = 10
REQUEST_DELAY  = 0           # seconds between requests
LOW_POINTS     = 50          # sleep until reset when fewer GraphQL points remain
VERBOSE        = False

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR    = Path(__file__).parent
DATA_DIR      = SCRIPT_DIR / "../../data/stage1"
DATA_DIR.mkdir(parents=True, exist_ok=True)

OUT_FILE      = DATA_DIR / "global_corpus_raw.csv"
PROGRESS_FILE = DATA_DIR / "progress_stage1a.txt"

# ── GraphQL queries ───────────────────────────────────────────────────────────
GQL = """
query($q:String!, $after:String, $n:Int!) {
  rateLimit { cost remaining resetAt }
  search(query:$q, type:REPOSITORY, first:$n, after:$after) {
    repositoryCount
    pageInfo { hasNextPage endCursor }
    nodes { ... on Repository {
      id nameWithOwner url stargazerCount forkCount createdAt
      languages(first:10, orderBy:{field:SIZE, direction:DESC}) {
        edges { size node { name } }
      }
    } }
  }
}"""

COUNT_GQL = """
query($q:String!) {
  rateLimit { cost remaining resetAt }
  search(query:$q, type:REPOSITORY, first:1) { repositoryCount }
}"""

COMMITS_GQL = """
query($ids:[ID!]!) {
  rateLimit { cost remaining resetAt }
  nodes(ids:$ids) { ... on Repository {
    id
    defaultBranchRef { target { ... on Commit { history { totalCount } } } }
  } }
}"""

# ── State ─────────────────────────────────────────────────────────────────────
session       = requests.Session()
session.headers["Authorization"] = f"Bearer {TOKEN}"
seen          = set()   # full_name strings already written to CSV
writer        = None
last_remaining = None


# ── HTTP / rate-limit helpers (unchanged from team template) ──────────────────

def new_session():
    global session
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {TOKEN}"


def backoff(attempt):
    wait = min(15 * attempt, 120)
    print(f"  [RETRY] Waiting {wait}s...")
    time.sleep(wait)


def sleep_until(reset_iso):
    try:
        reset = datetime.fromisoformat(reset_iso.replace("Z", "+00:00"))
        wait  = (reset - datetime.now(timezone.utc)).total_seconds() + 5
    except Exception:
        wait = 60
    wait = max(wait, 5)
    print(f"  [RATE LIMIT] Sleeping {int(wait)}s until reset...")
    time.sleep(wait)


def wait_for_http_limit(r):
    retry_after = r.headers.get("Retry-After")
    reset       = r.headers.get("X-RateLimit-Reset")
    remaining   = r.headers.get("X-RateLimit-Remaining")
    if retry_after and retry_after.isdigit():
        wait = int(retry_after) + 2
    elif remaining == "0" and reset and reset.isdigit():
        wait = max(int(reset) - time.time(), 0) + 5
    else:
        wait = 60
    print(f"  [RATE LIMIT] HTTP {r.status_code}, sleeping {int(wait)}s...")
    time.sleep(wait)


def run(q=None, after=None, count_only=False, ids=None):
    global last_remaining

    if ids is not None:
        gql, variables, key = COMMITS_GQL, {"ids": ids}, "nodes"
    elif count_only:
        gql, variables, key = COUNT_GQL, {"q": q}, "search"
    else:
        gql, variables, key = GQL, {"q": q, "after": after, "n": PAGE_SIZE}, "search"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.post(
                "https://api.github.com/graphql",
                json={"query": gql, "variables": variables},
                timeout=60,
            )
        except requests.exceptions.RequestException as e:
            print(f"  [NETWORK ERROR] {e} (attempt {attempt}/{MAX_RETRIES})")
            if attempt < MAX_RETRIES:
                backoff(attempt)
                new_session()
            continue

        if r.status_code in (403, 429):
            wait_for_http_limit(r)
            continue

        if r.status_code in (499, 502, 503, 504):
            print(f"  [API ERROR] HTTP {r.status_code} (attempt {attempt}/{MAX_RETRIES})")
            if attempt < MAX_RETRIES:
                backoff(attempt)
                new_session()
            continue

        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:500]}")

        try:
            data = r.json()
        except ValueError:
            print(f"  [JSON ERROR] (attempt {attempt}/{MAX_RETRIES}): {r.text[:300]}")
            if attempt < MAX_RETRIES:
                backoff(attempt)
            continue

        errors = data.get("errors")
        d      = data.get("data")

        if errors:
            types = {e.get("type") for e in errors}
            if "RATE_LIMITED" in types:
                reset = (d or {}).get("rateLimit", {}).get("resetAt") if d else None
                sleep_until(reset) if reset else time.sleep(60)
                continue
            if not d or not d.get(key):
                print(f"  [GRAPHQL ERROR] (attempt {attempt}/{MAX_RETRIES}) {errors}")
                if attempt < MAX_RETRIES:
                    backoff(attempt)
                continue
            print(f"  [GRAPHQL WARNING] partial errors: {errors[0].get('message')}")

        if not d or not d.get(key):
            print(f"  [UNEXPECTED] (attempt {attempt}/{MAX_RETRIES}) {data}")
            if attempt < MAX_RETRIES:
                backoff(attempt)
            continue

        rl = d["rateLimit"]
        last_remaining = rl["remaining"]
        if VERBOSE:
            print(f"  [API OK] cost={rl['cost']} remaining={rl['remaining']}")
        if rl["remaining"] < LOW_POINTS:
            sleep_until(rl["resetAt"])

        time.sleep(REQUEST_DELAY)
        return d

    raise RuntimeError(f"GitHub API failed after {MAX_RETRIES} attempts")


# ── Language helpers ──────────────────────────────────────────────────────────

def get_js_ts_bytes(edges: list) -> int:
    """Sum language bytes for JavaScript and TypeScript combined."""
    return sum(
        e["size"] for e in edges
        if e["node"]["name"].lower() in ("javascript", "typescript")
    )


def get_primary_language(edges: list) -> str:
    """Return whichever of JS/TS has the higher byte count."""
    js = sum(e["size"] for e in edges if e["node"]["name"].lower() == "javascript")
    ts = sum(e["size"] for e in edges if e["node"]["name"].lower() == "typescript")
    return "TypeScript" if ts >= js else "JavaScript"


def get_size_stratum(stars: int) -> str:
    if stars <= 50:
        return "small"
    if stars <= 500:
        return "medium"
    return "large"


# ── Repository handling ───────────────────────────────────────────────────────

def handle_page(nodes: list):
    """
    Stage 1 (cheap): filter by JS+TS language bytes.
    Stage 2 (costly): fetch commit counts for survivors only.
    """
    candidates = []
    for n in nodes:
        if not n or n["nameWithOwner"] in seen:
            continue
        lang_bytes = get_js_ts_bytes(n["languages"]["edges"])
        if lang_bytes >= MIN_LANG_BYTES:
            n["_lang_bytes"] = lang_bytes
            candidates.append(n)

    if not candidates:
        return

    # Fetch commit counts only for repos that passed language filter
    d = run(ids=[n["id"] for n in candidates])
    commits_by_id = {}
    for x in d["nodes"]:
        if not x:
            continue
        ref = x.get("defaultBranchRef")
        commits_by_id[x["id"]] = (
            ref["target"]["history"]["totalCount"]
            if ref and ref.get("target") else 0
        )

    for n in candidates:
        commits = commits_by_id.get(n["id"], 0)
        if commits < MIN_COMMITS:
            continue

        full_name   = n["nameWithOwner"]
        owner, repo = full_name.split("/", 1)
        stars       = n["stargazerCount"]
        created_at  = n.get("createdAt", "")[:10]  # YYYY-MM-DD
        primary_lang = get_primary_language(n["languages"]["edges"])
        stratum      = get_size_stratum(stars)

        seen.add(full_name)
        writer.writerow([
            full_name,          # original: repo   (renamed to full_name — same content)
            stars,              # original: stars
            n["forkCount"],     # original: forks
            commits,            # original: commits
            n["_lang_bytes"],   # original: lang_bytes
            n["url"],           # original: url
            owner,              # added:    owner_login
            repo,               # added:    repo_name
            primary_lang,       # added:    primary_language
            stratum,            # added:    size_stratum
            created_at,         # added:    created_at
        ])
        print(
            f"{full_name:50} stars={stars:<6} commits={commits:<6} "
            f"bytes={n['_lang_bytes']:<9} lang={primary_lang}"
        )


# ── Query building ────────────────────────────────────────────────────────────

def fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_query(start: datetime, end: datetime, language: str) -> str:
    """Build query for a single language. Run once for JS, once for TS."""
    parts = [
        f'language:"{language}"',
        f"stars:>={MIN_STARS}",
        "fork:false",
        f"created:{fmt(start)}..{fmt(end)}",
        "sort:stars-desc",
    ]
    return " ".join(parts)


# ── Window processing ─────────────────────────────────────────────────────────

def process(start: datetime, end: datetime, language: str):
    """
    Fetch one created-date window for one language.
    If > 1000 results, split in half recursively.
    """
    q     = build_query(start, end, language)
    total = run(q, count_only=True)["search"]["repositoryCount"]

    if total == 0:
        return

    if total > 1000:
        span = int((end - start).total_seconds())
        if span >= 1:
            mid = start + timedelta(seconds=span // 2)
            print(f"  {fmt(start)}..{fmt(end)}: {total} repos > 1000, splitting")
            process(start, mid, language)
            process(mid + timedelta(seconds=1), end, language)
            return
        print(f"  {fmt(start)}: {total} repos in one second (>1000, some skipped)")

    d = run(q, None)
    while True:
        s = d["search"]
        handle_page(s["nodes"])
        if not s["pageInfo"]["hasNextPage"]:
            break
        d = run(q, s["pageInfo"]["endCursor"])


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    global writer

    # Load already-completed windows
    done = set()
    if PROGRESS_FILE.exists():
        done = set(PROGRESS_FILE.read_text().split())

    # Load already-written repos (resume support)
    new_file = not OUT_FILE.exists()
    if not new_file:
        with open(OUT_FILE, newline="", encoding="utf-8") as f:
            for i, row in enumerate(csv.reader(f)):
                if i > 0 and row:
                    seen.add(row[0])   # full_name is column 0
        print(f"Resuming: {len(seen)} repos already collected.")

    out    = open(OUT_FILE, "a", newline="", encoding="utf-8")
    writer = csv.writer(out)
    if new_file:
        writer.writerow([
            "full_name",        # original: repo
            "stars",            # original
            "forks",            # original
            "commits",          # original
            "lang_bytes",       # original
            "url",              # original
            "owner_login",      # added
            "repo_name",        # added
            "primary_language", # added
            "size_stratum",     # added
            "created_at",       # added
        ])

    print(f"\nCollecting JS/TypeScript repos created {CREATED_FROM} → {CREATED_TO}")
    print(f"Filters: stars>={MIN_STARS}, commits>={MIN_COMMITS}, "
          f"lang_bytes>={MIN_LANG_BYTES:,}, fork=false")
    print(f"Running two passes (JavaScript then TypeScript). "
          f"Duplicates deduplicated via seen set.\n")

    try:
        for language in ["JavaScript", "TypeScript"]:
            print(f"\n{'='*60}")
            print(f"  Pass: {language}")
            print(f"{'='*60}\n")
            day = CREATED_FROM
            while day <= CREATED_TO:
                last_day = min(day + timedelta(days=WINDOW_DAYS - 1), CREATED_TO)
                key = f"{language}:{day}..{last_day}"

                if key in done:
                    print(f"[{key}] already done, skipping")
                else:
                    start = datetime.combine(day, dtime(0, 0, 0))
                    end   = datetime.combine(last_day, dtime(23, 59, 59))
                    process(start, end, language)
                    out.flush()
                    with open(PROGRESS_FILE, "a") as p:
                        p.write(key + "\n")
                    print(f"[{key}] done — total repos: {len(seen)}  "
                          f"(API points left: {last_remaining})")

                day = last_day + timedelta(days=1)
    finally:
        out.close()

    print(f"\nStage 1a complete. {len(seen)} repos saved to {OUT_FILE}")
    print("Next: run stage1b_verify_npm.py to apply lockfile filter.")


if __name__ == "__main__":
    main()

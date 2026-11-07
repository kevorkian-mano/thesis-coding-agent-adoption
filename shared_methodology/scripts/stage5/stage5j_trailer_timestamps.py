#!/usr/bin/env python3
"""
Stage 5j -- Trailer-Based First AI Timestamps  (GraphQL batch edition)
========================================================================
For every repo detected as agentic via commit trailers (Pass 3b), find the
OLDEST commit carrying an AI-agent trailer → first_ai_date for the repo.

GraphQL batching + oldest-first pagination strategy
------------------------------------------------------
Round 1  — query BATCH_SIZE repos at once, fetching their OLDEST 100 commits
           (`history(last: 100)`).  For each repo, check those commits for
           AI trailer patterns.
             • Trailer found  → record min-date trailer, repo is DONE.
             • No trailer yet → keep repo in a "needs-more-pages" queue
               with its `startCursor` for round 2.
Round 2+ — same batch approach using `history(last: 100, before: cursor)`
           to slide the window toward newer commits, until all repos are done
           or all commits are exhausted.

Why this is fast
-----------------
  REST sequential  : ~11,937 repos × 5 pages  = ~60,000 calls → ~12 hrs
  GraphQL batched  : ~11,937/10 × ~1.65 rounds = ~1,970 calls
  Each request ≈ 0.5s network + 0.8s sleep → ~1.3s/batch
  Total: ~1,970 × 1.3s ≈ 43 minutes  (down from ~12 hours)

  Most pass-2 repos adopted AI early (day-1 trailers), so they finish in
  round 1.  Only late-adopter repos need extra rounds.

Input
-----
  data/stage3/pass2_results.csv
    Columns: full_name, trailer_count, agents_found, adoption_label, ...

Output
------
  data/stage5/trailer_timestamps.csv
    Columns: full_name, first_ai_date, first_trailer_agent, rounds_needed,
             api_status

Usage
-----
  export GITHUB_TOKEN=ghp_...
  python3 scripts/stage5/stage5j_trailer_timestamps.py [--limit N] [--resume]
"""

import os, re, sys, time, argparse, requests, pandas as pd
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
PASS2   = ROOT / "data" / "stage3" / "pass2_results.csv"
OUT_DIR = ROOT / "data" / "stage5"
OUT_CSV = OUT_DIR / "trailer_timestamps.csv"
OUT_DIR.mkdir(parents=True, exist_ok=True)

GRAPHQL_URL = "https://api.github.com/graphql"
BATCH_SIZE  = 10     # repos per GraphQL request
SLEEP_BATCH = 0.80   # seconds between batches (~1,250/hr — safe buffer under 5,000)

# AI trailer patterns (same as stage3b)
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
    (re.compile(r"co-authored-by:",                       re.I), "Generic"),
]


def match_agent(message: str) -> str | None:
    for pattern, label in AGENT_PATTERNS:
        if pattern.search(message):
            return label
    return None


# ── GitHub helpers ────────────────────────────────────────────────────────────

def get_headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        sys.exit("ERROR: GITHUB_TOKEN not set.")
    return {"Authorization": f"Bearer {token}",
            "Content-Type": "application/json"}


def gql_post(query: str, headers: dict) -> dict:
    """POST a GraphQL query with retry for rate limits, 5xx errors, and timeouts."""
    wait = 15
    for attempt in range(6):
        try:
            resp = requests.post(GRAPHQL_URL,
                                 json={"query": query},
                                 headers=headers,
                                 timeout=60)
        except (requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectionError) as exc:
            if attempt < 5:
                print(f"\n  Network error ({exc.__class__.__name__}), "
                      f"retry {attempt+1}/5 in {wait}s …", flush=True)
                time.sleep(wait)
                wait = min(wait * 2, 120)
                continue
            raise

        if resp.status_code == 200:
            return resp.json()

        if resp.status_code in (403, 429):
            reset  = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait_s = max(reset - int(time.time()), 10)
            print(f"\n  Rate limited ({resp.status_code}) — sleeping {wait_s}s …",
                  flush=True)
            time.sleep(wait_s + 2)
            continue

        if resp.status_code in (500, 502, 503, 504):
            print(f"\n  Server error {resp.status_code} — "
                  f"retry {attempt+1}/5 in {wait}s …", flush=True)
            time.sleep(wait)
            wait = min(wait * 2, 120)
            continue

        print(f"\n  Unexpected HTTP {resp.status_code}", flush=True)
        return {}

    print("\n  Giving up after 5 retries — returning empty result.", flush=True)
    return {}


# ── GraphQL query builders ────────────────────────────────────────────────────

def build_round_query(batch_state: list[dict]) -> str:
    """
    batch_state: list of dicts, each with:
      { 'idx': int, 'owner': str, 'repo': str, 'cursor': str | None }

    cursor = None → first round (`history(last: 100)`)
    cursor = str  → subsequent rounds (`history(last: 100, before: cursor)`)
    """
    parts = []
    for s in batch_state:
        i      = s["idx"]
        owner  = s["owner"]
        repo   = s["repo"]
        cursor = s["cursor"]

        if cursor:
            hist_args = f'first: 100, after: "{cursor}"'
        else:
            hist_args = "first: 100"

        parts.append(f"""
  r{i}: repository(owner: "{owner}", name: "{repo}") {{
    object(expression: "HEAD") {{
      ... on Commit {{
        history({hist_args}) {{
          pageInfo {{ hasNextPage endCursor }}
          nodes {{ committedDate message }}
        }}
      }}
    }}
  }}""")
    return "query {" + "".join(parts) + "\n}"


# ── Response parser ───────────────────────────────────────────────────────────

def parse_round_response(response: dict,
                         batch_state: list[dict]
                         ) -> tuple[list[dict], list[dict]]:
    """
    Returns:
      finished : list of result dicts (repo is done)
      pending  : list of updated state dicts (repo needs another round)
    """
    data     = response.get("data") or {}
    finished = []
    pending  = []

    for s in batch_state:
        i         = s["idx"]
        full_name = f"{s['owner']}/{s['repo']}"
        repo_data = data.get(f"r{i}")

        if repo_data is None:
            finished.append({
                "full_name":           full_name,
                "first_ai_date":       None,
                "first_trailer_agent": None,
                "rounds_needed":       s.get("rounds", 1),
                "api_status":          "null_response",
            })
            continue

        try:
            history = (repo_data["object"]["history"])
        except (TypeError, KeyError):
            finished.append({
                "full_name":           full_name,
                "first_ai_date":       None,
                "first_trailer_agent": None,
                "rounds_needed":       s.get("rounds", 1),
                "api_status":          "no_default_branch",
            })
            continue

        if history is None:
            finished.append({
                "full_name":           full_name,
                "first_ai_date":       None,
                "first_trailer_agent": None,
                "rounds_needed":       s.get("rounds", 1),
                "api_status":          "empty_repo",
            })
            continue

        nodes        = history.get("nodes") or []
        page_info    = history.get("pageInfo") or {}
        has_next     = page_info.get("hasNextPage", False)
        end_cursor   = page_info.get("endCursor")

        # Accumulate best (oldest) trailer found so far across all rounds
        prev_best_date  = s.get("best_date")
        prev_best_agent = s.get("best_agent")
        best_date  = prev_best_date
        best_agent = prev_best_agent

        for node in nodes:
            msg   = node.get("message", "")
            agent = match_agent(msg)
            if agent:
                date = node.get("committedDate", "")[:10]
                if date and (best_date is None or date < best_date):
                    best_date  = date
                    best_agent = agent

        if has_next and end_cursor:
            # More (older) commits to scan — keep going
            pending.append({
                **s,
                "cursor":     end_cursor,
                "best_date":  best_date,
                "best_agent": best_agent,
                "rounds":     s.get("rounds", 1) + 1,
            })
        else:
            # All commits scanned — finalise
            finished.append({
                "full_name":           full_name,
                "first_ai_date":       best_date,
                "first_trailer_agent": best_agent,
                "rounds_needed":       s.get("rounds", 1),
                "api_status":          "ok" if best_date else "trailer_not_found",
            })

    return finished, pending


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit",  type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if not PASS2.exists():
        sys.exit(f"Missing: {PASS2}")

    headers = get_headers()

    df = pd.read_csv(PASS2, low_memory=False)
    agentic = df[(df["adoption_label"] == "agentic") &
                 (df["trailer_count"].fillna(0) > 0)]
    repos = agentic["full_name"].tolist()

    # Resume
    done: set[str] = set()
    if args.resume and OUT_CSV.exists():
        done = set(pd.read_csv(OUT_CSV)["full_name"].tolist())
        print(f"Resuming — {len(done):,} repos already processed.")
    repos = [r for r in repos if r not in done]
    if args.limit > 0:
        repos = repos[:args.limit]

    total = len(repos)
    print("Stage 5j -- Trailer Timestamps  [GraphQL oldest-first]")
    print("=" * 55)
    print(f"Repos to process : {total:,}")
    print(f"Batch size       : {BATCH_SIZE}")
    est_batches = total // BATCH_SIZE * 1.5   # ~1.5 rounds avg
    print(f"Est. batches     : ~{int(est_batches):,}  (~1.5 rounds avg)")
    print(f"Est. time        : ~{int(est_batches * SLEEP_BATCH / 60)} min")
    print(f"Output           : {OUT_CSV}")
    print()

    write_header = not OUT_CSV.exists() or not args.resume
    out_fh = open(OUT_CSV, "a", buffering=1)
    if write_header:
        out_fh.write("full_name,first_ai_date,first_trailer_agent,"
                     "rounds_needed,api_status\n")

    # Build initial state list
    pending_state: list[dict] = []
    for idx, full_name in enumerate(repos):
        owner, repo = full_name.split("/", 1)
        pending_state.append({
            "idx":    idx % BATCH_SIZE,   # local batch index (re-assigned per batch)
            "owner":  owner,
            "repo":   repo,
            "cursor": None,
            "rounds": 1,
            "_full_name": full_name,
        })

    ok_count   = 0
    err_count  = 0
    batch_num  = 0
    start      = time.time()

    while pending_state:
        # Re-index the batch (idx must be unique within each batch)
        batch = pending_state[:BATCH_SIZE]
        for i, s in enumerate(batch):
            s["idx"] = i
        pending_state = pending_state[BATCH_SIZE:]

        query    = build_round_query(batch)
        response = gql_post(query, headers)
        finished, still_pending = parse_round_response(response, batch)

        for r in finished:
            agent = str(r["first_trailer_agent"] or "").replace(",", ";")
            out_fh.write(
                f"{r['full_name']},"
                f"{r['first_ai_date'] or ''},"
                f"{agent},"
                f"{r['rounds_needed']},"
                f"{r['api_status']}\n"
            )
            if r["first_ai_date"]:
                ok_count += 1
            else:
                err_count += 1

        # Put repos needing more pages back into the queue
        # (append to end so we process current batch fully before retrying)
        pending_state.extend(still_pending)

        batch_num += 1
        if batch_num % 50 == 0 or not pending_state:
            elapsed   = time.time() - start
            rate      = batch_num / elapsed if elapsed else 0
            remaining = len(pending_state)
            eta_m     = (remaining / BATCH_SIZE) / rate / 60 if rate and remaining else 0
            done_total = ok_count + err_count
            print(f"  [batch {batch_num:>5,}]  done={done_total:>6,}/{total}  "
                  f"ok={ok_count:,}  no_date={err_count:,}  "
                  f"pending={remaining:,}  ETA={eta_m:.0f}m", flush=True)

        time.sleep(SLEEP_BATCH)

    out_fh.close()
    print()
    print(f"Done.  Timestamps found: {ok_count:,} / {total:,}")
    print(f"Saved: {OUT_CSV}")


if __name__ == "__main__":
    main()

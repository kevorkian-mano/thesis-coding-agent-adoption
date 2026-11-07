#!/usr/bin/env python3
"""
Stage 5i -- Config File Timestamps  (GraphQL batch edition)
=============================================================
For every repo detected as agentic via config file (Pass 3a), find the OLDEST
commit that first added each detected config file → first_ai_date for the repo.

  first_ai_date = min(oldest_commit)  across all detected config files

GraphQL batching strategy
--------------------------
Instead of 1–3 REST calls per repo (56,000–85,000 total), we build a single
GraphQL query that handles BATCH_SIZE repos at once.  For each repo we ask for
the history of EVERY detected config file with `last: 1`, which returns the
single oldest commit for that path in one round-trip.

  Requests = ceil(28,397 / BATCH_SIZE) ≈ 2,840  (batch = 10)
  Each request ≈ 0.5s network + 0.8s sleep → ~1.3s/batch
  Total: 2,840 × 1.3s ≈ 61 minutes  (down from 11–17 hours)

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

import os, re, sys, time, json, argparse, requests, pandas as pd
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
PASS1   = ROOT / "data" / "stage3" / "pass1_results.csv"
OUT_DIR = ROOT / "data" / "stage5"
OUT_CSV = OUT_DIR / "config_timestamps.csv"
OUT_DIR.mkdir(parents=True, exist_ok=True)

GRAPHQL_URL   = "https://api.github.com/graphql"
BATCH_SIZE    = 10     # repos per GraphQL request
SLEEP_BATCH   = 0.80   # seconds between batches (~1,250/hr — safe buffer under 5,000)


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


# ── GraphQL query builder ─────────────────────────────────────────────────────

def _alias(s: str) -> str:
    """Turn an arbitrary string into a valid GraphQL field alias."""
    return re.sub(r'[^a-zA-Z0-9]', '_', s)


def build_query(batch: list[tuple[str, str, list[str]]]) -> str:
    """
    batch: [(owner, repo, [config_file, ...]), ...]
    Returns a GraphQL query string that fetches the oldest commit for every
    config file of every repo in one request.
    """
    parts = []
    for i, (owner, repo, files) in enumerate(batch):
        file_queries = []
        for j, path in enumerate(files):
            escaped = path.replace('\\', '\\\\').replace('"', '\\"')
            file_queries.append(
                f'          f{j}: history(path: "{escaped}", first: 100) '
                f'{{ nodes {{ committedDate }} }}'
            )
        joined = "\n".join(file_queries)
        parts.append(f"""
  r{i}: repository(owner: "{owner}", name: "{repo}") {{
    object(expression: "HEAD") {{
      ... on Commit {{
{joined}
      }}
    }}
  }}""")
    return "query {" + "".join(parts) + "\n}"


# ── Response parser ───────────────────────────────────────────────────────────

def parse_batch_response(response: dict,
                         batch: list[tuple[str, str, list[str]]]
                         ) -> list[dict]:
    """
    Parse the JSON response and return one result dict per repo in batch.
    """
    data   = response.get("data") or {}
    errors = {e.get("path", [None])[0]: e.get("message", "")
              for e in response.get("errors", [])}
    results = []

    for i, (owner, repo, files) in enumerate(batch):
        full_name = f"{owner}/{repo}"
        alias     = f"r{i}"
        repo_data = data.get(alias)

        if repo_data is None:
            results.append({
                "full_name":         full_name,
                "first_ai_date":     None,
                "first_config_file": None,
                "n_configs":         len(files),
                "api_status":        errors.get(alias, "null_response"),
            })
            continue

        commit_obj = repo_data.get("object")
        if not commit_obj:
            results.append({
                "full_name":         full_name,
                "first_ai_date":     None,
                "first_config_file": None,
                "n_configs":         len(files),
                "api_status":        "empty_repo",
            })
            continue

        best_date = None
        best_file = None
        for j, path in enumerate(files):
            nodes = (commit_obj.get(f"f{j}") or {}).get("nodes") or []
            if nodes:
                # nodes sorted newest→oldest; last item = oldest commit for this file
                date = nodes[-1].get("committedDate", "")[:10]
                if date and (best_date is None or date < best_date):
                    best_date = date
                    best_file = path

        results.append({
            "full_name":         full_name,
            "first_ai_date":     best_date,
            "first_config_file": best_file,
            "n_configs":         len(files),
            "api_status":        "ok" if best_date else "no_date_found",
        })

    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit",  type=int, default=0,
                        help="Process at most N repos (0 = all)")
    parser.add_argument("--resume", action="store_true",
                        help="Skip repos already in output CSV")
    args = parser.parse_args()

    if not PASS1.exists():
        sys.exit(f"Missing: {PASS1}")

    headers = get_headers()

    df = pd.read_csv(PASS1, low_memory=False)
    agentic = df[(df["adoption_label"] == "agentic") &
                 df["config_files_found"].notna() &
                 (df["config_files_found"].str.strip() != "")]

    # Build (owner, repo, [files]) tuples
    repo_tuples: list[tuple[str, str, list[str]]] = []
    for _, row in agentic.iterrows():
        files = [f.strip() for f in str(row["config_files_found"]).split("|") if f.strip()]
        if files:
            owner, repo = row["full_name"].split("/", 1)
            repo_tuples.append((owner, repo, files))

    # Resume: skip already-processed
    done: set[str] = set()
    if args.resume and OUT_CSV.exists():
        done = set(pd.read_csv(OUT_CSV)["full_name"].tolist())
        print(f"Resuming — {len(done):,} repos already processed.")
    repo_tuples = [(o, r, f) for o, r, f in repo_tuples
                   if f"{o}/{r}" not in done]

    if args.limit > 0:
        repo_tuples = repo_tuples[:args.limit]

    total   = len(repo_tuples)
    n_batches = -(-total // BATCH_SIZE)   # ceiling division

    print("Stage 5i -- Config File Timestamps  [GraphQL]")
    print("=" * 55)
    print(f"Repos to process : {total:,}")
    print(f"Batch size       : {BATCH_SIZE}")
    print(f"Total batches    : {n_batches:,}")
    print(f"Est. time        : ~{n_batches * SLEEP_BATCH / 60:.0f} min")
    print(f"Output           : {OUT_CSV}")
    print()

    write_header = not OUT_CSV.exists() or not args.resume
    out_fh = open(OUT_CSV, "a", buffering=1)
    if write_header:
        out_fh.write("full_name,first_ai_date,first_config_file,n_configs,api_status\n")

    ok_count  = 0
    err_count = 0
    start     = time.time()

    for batch_num, start_i in enumerate(range(0, total, BATCH_SIZE), 1):
        batch = repo_tuples[start_i:start_i + BATCH_SIZE]
        query = build_query(batch)

        response = gql_post(query, headers)
        results  = parse_batch_response(response, batch)

        for r in results:
            cfg = str(r["first_config_file"] or "").replace(",", ";")
            out_fh.write(
                f"{r['full_name']},"
                f"{r['first_ai_date'] or ''},"
                f"{cfg},"
                f"{r['n_configs']},"
                f"{r['api_status']}\n"
            )
            if r["first_ai_date"]:
                ok_count += 1
            else:
                err_count += 1

        if batch_num % 50 == 0 or batch_num == n_batches:
            elapsed = time.time() - start
            rate    = batch_num / elapsed if elapsed else 0
            eta_m   = (n_batches - batch_num) / rate / 60 if rate else 0
            done_r  = start_i + len(batch)
            print(f"  [{batch_num:>5,}/{n_batches:,} batches | "
                  f"{done_r:>6,}/{total:,} repos]  "
                  f"ok={ok_count:,}  no_date={err_count:,}  "
                  f"ETA={eta_m:.0f}m", flush=True)

        time.sleep(SLEEP_BATCH)

    out_fh.close()
    print()
    print(f"Done.  Timestamps found: {ok_count:,} / {total:,}")
    print(f"Saved: {OUT_CSV}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Stage 5l -- TypeScript Adoption Timing
========================================
For every JavaScript-primary repo in the corpus, find the oldest commit that
added tsconfig.json. Compare to the repo's first AI signal date to classify
whether TypeScript adoption preceded or followed agent adoption.

Timing categories:
  ts_before_ai   -- tsconfig.json added before first AI signal
  ts_after_ai    -- tsconfig.json added after first AI signal
  ts_same_day    -- added on the same day as first AI signal
  no_tsconfig    -- no tsconfig.json found in repo
  no_ai_date     -- agentic repo but first_ai_date not available

Non-agentic repos use: ts_present / ts_absent (control group)

Input
-----
  data/stage3/corpus_detected_full.csv
  data/stage5/adoption_timeline.csv

Output
------
  data/stage5/ts_adoption_timing.csv
    Columns: full_name, adoption_label, tsconfig_date, first_ai_date,
             days_diff, timing_category, api_status

Usage
-----
  export GITHUB_TOKEN=ghp_...
  python3 scripts/stage5/stage5l_ts_adoption_timing.py [--limit N] [--resume]
"""

import os, re, sys, time, json, argparse, requests
import pandas as pd
from pathlib import Path

ROOT     = Path(__file__).resolve().parents[2]
CORPUS   = ROOT / "data" / "stage3" / "corpus_detected_full.csv"
TIMELINE = ROOT / "data" / "stage5" / "adoption_timeline.csv"
OUT_DIR  = ROOT / "data" / "stage5"
OUT_CSV  = OUT_DIR / "ts_adoption_timing.csv"
OUT_DIR.mkdir(parents=True, exist_ok=True)

GRAPHQL_URL = "https://api.github.com/graphql"
BATCH_SIZE  = 10
SLEEP_BATCH = 0.80


# ── GitHub helpers ─────────────────────────────────────────────────────────────

def get_headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        sys.exit("ERROR: GITHUB_TOKEN not set.")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def gql_post(query: str, headers: dict) -> dict:
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


# ── GraphQL query builder ──────────────────────────────────────────────────────

def build_query(batch: list[tuple[str, str]]) -> str:
    """Fetch oldest commit for tsconfig.json for each (owner, repo) in batch."""
    parts = []
    for i, (owner, repo) in enumerate(batch):
        parts.append(f"""
  r{i}: repository(owner: "{owner}", name: "{repo}") {{
    object(expression: "HEAD") {{
      ... on Commit {{
        tsconfig: history(path: "tsconfig.json", first: 100) {{
          nodes {{ committedDate }}
        }}
      }}
    }}
  }}""")
    return "query {" + "".join(parts) + "\n}"


# ── Response parser ────────────────────────────────────────────────────────────

def parse_batch(response: dict, batch: list[tuple[str, str]]) -> list[dict]:
    data   = response.get("data") or {}
    errors = response.get("errors", [])
    err_set = {str(e.get("path", "")): e.get("message", "") for e in errors}

    results = []
    for i, (owner, repo) in enumerate(batch):
        full_name = f"{owner}/{repo}"
        alias     = f"r{i}"
        repo_data = data.get(alias)

        if repo_data is None:
            results.append({"full_name": full_name,
                            "tsconfig_date": None,
                            "api_status": "error"})
            continue

        obj = (repo_data.get("object") or {})
        if not obj:
            results.append({"full_name": full_name,
                            "tsconfig_date": None,
                            "api_status": "empty_repo"})
            continue

        nodes = obj.get("tsconfig", {}).get("nodes", [])
        if not nodes:
            results.append({"full_name": full_name,
                            "tsconfig_date": None,
                            "api_status": "ok"})
        else:
            dates = [n["committedDate"] for n in nodes if n.get("committedDate")]
            oldest = min(dates) if dates else None
            results.append({"full_name": full_name,
                            "tsconfig_date": oldest,
                            "api_status": "ok"})
    return results


# ── Classification ─────────────────────────────────────────────────────────────

def classify(row: pd.Series) -> str:
    label         = row["adoption_label"]
    tsconfig_date = row["tsconfig_date"]
    first_ai_date = row["first_ai_date"]

    if pd.isna(tsconfig_date):
        return "ts_absent" if label == "none" else "no_tsconfig"

    if label == "none":
        return "ts_present"

    # agentic repo
    if pd.isna(first_ai_date):
        return "no_ai_date"

    try:
        t = pd.Timestamp(tsconfig_date).tz_localize(None)
        a = pd.Timestamp(first_ai_date).tz_localize(None)
    except Exception:
        return "parse_error"

    diff = (t - a).days
    if diff < 0:
        return "ts_before_ai"
    elif diff == 0:
        return "ts_same_day"
    else:
        return "ts_after_ai"


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit",  type=int, default=0, help="Process only first N repos (0 = all)")
    ap.add_argument("--resume", action="store_true",  help="Skip repos already in output file")
    args = ap.parse_args()

    headers = get_headers()

    # Load corpus — JavaScript-primary repos only
    corpus = pd.read_csv(CORPUS)
    js_repos = corpus[corpus["primary_language"] == "JavaScript"][
        ["full_name", "adoption_label"]].copy()

    if args.limit:
        js_repos = js_repos.head(args.limit)

    # Load first AI signal dates
    timeline = pd.read_csv(TIMELINE)[["full_name", "first_ai_date"]]
    js_repos = js_repos.merge(timeline, on="full_name", how="left")

    # Resume: skip already-processed repos
    done: set[str] = set()
    if args.resume and OUT_CSV.exists():
        done = set(pd.read_csv(OUT_CSV)["full_name"])
        print(f"Resume: {len(done):,} repos already done.")

    todo = js_repos[~js_repos["full_name"].isin(done)].copy()
    print(f"JS repos to process: {len(todo):,}  "
          f"(agentic={( todo['adoption_label']=='agentic').sum():,}, "
          f"none={(todo['adoption_label']=='none').sum():,})")

    if todo.empty:
        print("Nothing to do.")
        return

    # Prepare batches
    pairs = [(r.split("/")[0], r.split("/")[1]) for r in todo["full_name"]]
    ai_lookup  = js_repos.set_index("full_name")["first_ai_date"].to_dict()
    lbl_lookup = js_repos.set_index("full_name")["adoption_label"].to_dict()

    batches = [pairs[i:i+BATCH_SIZE] for i in range(0, len(pairs), BATCH_SIZE)]
    total   = len(batches)
    written = 0

    write_header = not (args.resume and OUT_CSV.exists())

    print(f"Running {total:,} batches (batch size={BATCH_SIZE}) …\n")

    for b_idx, batch in enumerate(batches):
        query    = build_query(batch)
        response = gql_post(query, headers)
        rows     = parse_batch(response, batch)

        records = []
        for row in rows:
            fn   = row["full_name"]
            tsd  = row["tsconfig_date"]
            aid  = ai_lookup.get(fn)
            lbl  = lbl_lookup.get(fn, "unknown")

            # days_diff only meaningful for agentic repos with both dates
            days_diff = None
            if tsd and aid and lbl == "agentic":
                try:
                    t = pd.Timestamp(tsd).tz_localize(None)
                    a = pd.Timestamp(aid).tz_localize(None)
                    days_diff = (t - a).days
                except Exception:
                    pass

            records.append({
                "full_name":      fn,
                "adoption_label": lbl,
                "tsconfig_date":  tsd,
                "first_ai_date":  aid,
                "days_diff":      days_diff,
                "timing_category": classify(pd.Series({
                    "adoption_label": lbl,
                    "tsconfig_date":  tsd,
                    "first_ai_date":  aid,
                })),
                "api_status":     row["api_status"],
            })

        df_out = pd.DataFrame(records)
        df_out.to_csv(OUT_CSV, mode="a", index=False, header=write_header)
        write_header = False
        written += len(records)

        if (b_idx + 1) % 50 == 0 or (b_idx + 1) == total:
            pct = (b_idx + 1) / total * 100
            print(f"  [{b_idx+1:,}/{total:,}  {pct:.1f}%]  written={written:,}",
                  flush=True)

        time.sleep(SLEEP_BATCH)

    print(f"\nDone. {written:,} rows written to {OUT_CSV}")

    # Quick summary
    result = pd.read_csv(OUT_CSV)
    print("\n--- Category distribution ---")
    print(result["timing_category"].value_counts().to_string())
    agentic = result[result["adoption_label"] == "agentic"]
    if not agentic.empty:
        after   = (agentic["timing_category"] == "ts_after_ai").sum()
        before  = (agentic["timing_category"] == "ts_before_ai").sum()
        same    = (agentic["timing_category"] == "ts_same_day").sum()
        no_ts   = (agentic["timing_category"] == "no_tsconfig").sum()
        total_a = len(agentic)
        print(f"\nAgentic JS repos ({total_a:,}):")
        print(f"  TS after AI signal : {after:,}  ({after/total_a*100:.1f}%)")
        print(f"  TS before AI signal: {before:,}  ({before/total_a*100:.1f}%)")
        print(f"  TS same day        : {same:,}  ({same/total_a*100:.1f}%)")
        print(f"  No tsconfig.json   : {no_ts:,}  ({no_ts/total_a*100:.1f}%)")


if __name__ == "__main__":
    main()

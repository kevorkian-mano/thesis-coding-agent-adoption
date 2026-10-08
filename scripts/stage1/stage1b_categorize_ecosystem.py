#!/usr/bin/env python3
"""
Stage 1b — Ecosystem Categorization
=====================================
Reads all repos from Stage 1a and categorizes each one by its JavaScript
package manager / ecosystem. No repos are dropped — every repo gets a
category label. The sampling step (Stage 1c) decides which categories to
include and how many to take from each.

Categories:
  npm        — package.json + package-lock.json
  yarn       — package.json + yarn.lock
  pnpm       — package.json + pnpm-lock.yaml
  bun        — package.json + bun.lockb
  npm_no_lock— package.json present but no lockfile found
  deno       — deno.json or deno.jsonc present
  vanilla    — no package.json, no deno config (plain JS/TS)

If a repo has multiple lockfiles (e.g. both yarn.lock and package-lock.json),
the first match in priority order is used:
  npm > yarn > pnpm > bun

Detection uses GraphQL object(expression:"HEAD:<file>") — checks whether the
file exists at repo root. Cheap: no history traversal, no file content read.

Batch size: 15 repos × 7 file checks = 105 object lookups per request
(well within GitHub's 500-node limit).

Resume support: a checkpoint file is written every SAVE_EVERY repos.

INPUTS
------
  data/stage1/global_corpus_raw.csv     — Stage 1a output (60k repos)

OUTPUTS
-------
  data/stage1/global_corpus.csv         — all repos with ecosystem_type column
  data/stage1/ecosystem_audit.csv       — category breakdown summary
  data/stage1/checkpoint_1b.csv         — partial results (resume support)

USAGE
-----
  export GITHUB_TOKEN=your_token_here
  python3 stage1b_categorize_ecosystem.py
"""

import os
import sys
import time
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

# ── Configuration ─────────────────────────────────────────────────────────────
TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    sys.exit("ERROR: GITHUB_TOKEN environment variable is not set.\n"
             "Run: export GITHUB_TOKEN=your_token_here")

BATCH_SIZE  = 15     # repos per GraphQL request (7 file checks = 105 lookups)
SAVE_EVERY  = 300    # checkpoint every N repos
MAX_RETRIES = 6

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR     = Path(__file__).parent
DATA_DIR       = SCRIPT_DIR / "../../data/stage1"

RAW_CSV        = DATA_DIR / "global_corpus_raw.csv"
CORPUS_OUT     = DATA_DIR / "global_corpus.csv"
AUDIT_OUT      = DATA_DIR / "ecosystem_audit.csv"
CHECKPOINT_CSV = DATA_DIR / "checkpoint_1b.csv"

GRAPHQL_URL = "https://api.github.com/graphql"
GQL_HEADERS = {"Authorization": f"Bearer {TOKEN}"}


# ── Network helpers ───────────────────────────────────────────────────────────

def sleep_until(reset_iso: str):
    try:
        reset = datetime.fromisoformat(reset_iso.replace("Z", "+00:00"))
        wait  = (reset - datetime.now(timezone.utc)).total_seconds() + 5
    except Exception:
        wait = 60
    wait = max(wait, 5)
    print(f"  [RATE LIMIT] Sleeping {int(wait)}s until reset...")
    time.sleep(wait)


def graphql_post(query: str) -> dict:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.post(
                GRAPHQL_URL,
                json={"query": query},
                headers=GQL_HEADERS,
                timeout=30,
            )
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            wait = 2 ** attempt
            print(f"  [NETWORK ERROR] {e}, retry {attempt} in {wait}s...")
            time.sleep(wait)
            continue

        if r.status_code in (403, 429):
            reset = r.headers.get("X-RateLimit-Reset")
            wait  = max(int(reset) - time.time(), 0) + 5 if reset else 60
            print(f"  [RATE LIMIT] HTTP {r.status_code}, sleeping {int(wait)}s...")
            time.sleep(wait)
            continue

        if r.status_code in (499, 502, 503, 504):
            wait = 2 ** attempt
            print(f"  [SERVER ERROR] HTTP {r.status_code}, retry {attempt} in {wait}s...")
            time.sleep(wait)
            continue

        if r.status_code != 200:
            print(f"  [HTTP {r.status_code}] {r.text[:300]}")
            return {}

        data   = r.json()
        errors = data.get("errors", [])

        if errors:
            types = {e.get("type") for e in errors}
            if "RATE_LIMITED" in types:
                reset = (data.get("data") or {}).get("rateLimit", {}).get("resetAt")
                sleep_until(reset) if reset else time.sleep(60)
                continue
            print(f"  [GQL WARNING] {errors[0].get('message', '')}")

        rl = (data.get("data") or {}).get("rateLimit") or {}
        if rl.get("remaining", 999) < 50:
            sleep_until(rl.get("resetAt", ""))

        return data.get("data") or {}

    return {}


# ── GraphQL query builder ─────────────────────────────────────────────────────

def build_categorize_query(batch: list) -> str:
    """
    Checks 7 files per repo in one GraphQL request:
      package.json      — confirms npm/yarn/pnpm/bun project
      package-lock.json — npm lockfile
      yarn.lock         — Yarn lockfile
      pnpm-lock.yaml    — pnpm lockfile
      bun.lockb         — Bun lockfile
      deno.json         — Deno config
      deno.jsonc        — Deno config (alternative extension)
    """
    fragments = []
    for idx, (owner, repo) in enumerate(batch):
        o = owner.replace('"', "")
        r = repo.replace('"', "")
        fragments.append(f"""
        repo_{idx}: repository(owner: "{o}", name: "{r}") {{
            packageJson:  object(expression: "HEAD:package.json")      {{ id }}
            npmLock:      object(expression: "HEAD:package-lock.json") {{ id }}
            yarnLock:     object(expression: "HEAD:yarn.lock")         {{ id }}
            pnpmLock:     object(expression: "HEAD:pnpm-lock.yaml")    {{ id }}
            bunLock:      object(expression: "HEAD:bun.lockb")         {{ id }}
            denoJson:     object(expression: "HEAD:deno.json")         {{ id }}
            denoJsonc:    object(expression: "HEAD:deno.jsonc")        {{ id }}
        }}
        """)
    return "query { rateLimit { remaining resetAt } " + " ".join(fragments) + " }"


# ── Categorization logic ──────────────────────────────────────────────────────

def categorize_repo(repo_data: dict) -> str:
    """
    Returns the ecosystem category for a repo based on which files exist.

    Priority order when multiple lockfiles present:
      npm > yarn > pnpm > bun

    Special cases:
      deno.json/deno.jsonc → deno  (checked before npm to catch Deno+package.json combos)
      package.json only   → npm_no_lock
      nothing             → vanilla
    """
    if not repo_data:
        return "unknown"

    has_package_json = bool(repo_data.get("packageJson"))
    has_npm_lock     = bool(repo_data.get("npmLock"))
    has_yarn_lock    = bool(repo_data.get("yarnLock"))
    has_pnpm_lock    = bool(repo_data.get("pnpmLock"))
    has_bun_lock     = bool(repo_data.get("bunLock"))
    has_deno         = bool(repo_data.get("denoJson")) or bool(repo_data.get("denoJsonc"))

    # Deno: if deno.json exists, classify as deno regardless of package.json
    if has_deno:
        return "deno"

    if has_package_json:
        if has_npm_lock:
            return "npm"
        if has_yarn_lock:
            return "yarn"
        if has_pnpm_lock:
            return "pnpm"
        if has_bun_lock:
            return "bun"
        return "npm_no_lock"

    return "vanilla"


def categorize_batch(batch_df: pd.DataFrame) -> list:
    """Categorizes one batch of repos. Returns list of result dicts."""
    # Guard: rows where owner_login or repo_name is NaN cannot be queried
    valid_mask = batch_df["owner_login"].notna() & batch_df["repo_name"].notna()
    invalid_df = batch_df[~valid_mask]
    valid_df   = batch_df[valid_mask]

    results = []

    # Mark invalid rows immediately as unknown
    for row in invalid_df.itertuples(index=False):
        results.append({"full_name": row.full_name, "ecosystem_type": "unknown"})

    if valid_df.empty:
        return results

    pairs = list(zip(valid_df["owner_login"].astype(str),
                     valid_df["repo_name"].astype(str)))
    query = build_categorize_query(pairs)
    data  = graphql_post(query)

    for idx, row in enumerate(valid_df.itertuples(index=False)):
        repo_data      = data.get(f"repo_{idx}")
        ecosystem_type = categorize_repo(repo_data)
        results.append({
            "full_name":      row.full_name,
            "ecosystem_type": ecosystem_type,
        })

    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not RAW_CSV.exists():
        sys.exit(f"ERROR: {RAW_CSV} not found. Run stage1a_collect_repos.py first.")

    raw_df = pd.read_csv(RAW_CSV)
    total  = len(raw_df)
    print(f"Loaded {total} repos from Stage 1a.\n")

    # ── Resume support ────────────────────────────────────────────────────────
    if CHECKPOINT_CSV.exists():
        checkpoint_df   = pd.read_csv(CHECKPOINT_CSV)
        already_checked = set(checkpoint_df["full_name"])
        remaining_df    = raw_df[~raw_df["full_name"].isin(already_checked)].copy()
        all_results     = checkpoint_df.to_dict("records")
        print(f"Resuming: {len(already_checked)} already categorized, "
              f"{len(remaining_df)} remaining.\n")
    else:
        remaining_df = raw_df.copy()
        all_results  = []

    # ── Process in batches ────────────────────────────────────────────────────
    total_batches = (len(remaining_df) + BATCH_SIZE - 1) // BATCH_SIZE

    for b_num, start in enumerate(range(0, len(remaining_df), BATCH_SIZE), 1):
        batch   = remaining_df.iloc[start: start + BATCH_SIZE]
        results = categorize_batch(batch)
        all_results.extend(results)

        # Print category for each repo in batch
        for r in results:
            print(f"  {r['full_name']:55} → {r['ecosystem_type']}")

        # Checkpoint
        if b_num % (SAVE_EVERY // BATCH_SIZE) == 0:
            pd.DataFrame(all_results).to_csv(CHECKPOINT_CSV, index=False)
            done = len(all_results)
            print(f"\n  [Checkpoint {b_num}/{total_batches}] "
                  f"{done}/{total} categorized\n")

        time.sleep(0.5)

    # ── Merge category back into corpus ──────────────────────────────────────
    results_df = pd.DataFrame(all_results)
    corpus_df  = raw_df.merge(
        results_df[["full_name", "ecosystem_type"]],
        on="full_name",
        how="left",
    )
    corpus_df["ecosystem_type"] = corpus_df["ecosystem_type"].fillna("unknown")
    corpus_df["corpus_source"]  = "global"

    corpus_df.to_csv(CORPUS_OUT, index=False)

    # Clean up checkpoint
    if CHECKPOINT_CSV.exists():
        CHECKPOINT_CSV.unlink()

    # ── Ecosystem audit ───────────────────────────────────────────────────────
    audit = corpus_df["ecosystem_type"].value_counts().reset_index()
    audit.columns = ["ecosystem_type", "count"]
    audit["percent"] = (audit["count"] / total * 100).round(1)
    audit.to_csv(AUDIT_OUT, index=False)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n─── Stage 1b Summary ─────────────────────────────────────────")
    print(f"Total repos categorized  : {total}")
    print(f"\nEcosystem breakdown:")
    print(f"  {'Category':<15} {'Count':>8}  {'%':>6}")
    print(f"  {'-'*32}")
    for _, row in audit.iterrows():
        marker = " ← thesis target" if row["ecosystem_type"] in ("npm","yarn","pnpm","bun") else ""
        print(f"  {row['ecosystem_type']:<15} {row['count']:>8}  {row['percent']:>5}%{marker}")
    print(f"\nSaved: {CORPUS_OUT}")
    print(f"       {AUDIT_OUT}")
    print(f"\nNext: run stage1c_sample.py to create the analysis sample.")


if __name__ == "__main__":
    main()

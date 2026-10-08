#!/usr/bin/env python3
"""
Stage 1b — npm Ecosystem Verification
=======================================
Reads the raw corpus from Stage 1a and verifies that each repo is a genuine
npm/JS/TS project by checking for package.json + at least one lockfile.

Filter logic:
  PASS  →  package.json exists  AND  (package-lock.json OR yarn.lock OR pnpm-lock.yaml)
  FAIL  →  missing package.json  OR  no lockfile found

Repos that have package.json but no lockfile are dropped — a lockfile confirms
active npm dependency management, not just a stale or auto-generated package.json.
The lockfile type found is recorded in the output for potential subgroup analysis.

Uses GraphQL batching: 20 repos per request, 4 file checks per repo (80 object
lookups per request — well within GitHub's node limit of 500).

Resume support: a checkpoint file is written every SAVE_EVERY repos so the
script can be stopped and restarted without re-checking already-verified repos.

INPUTS
------
  data/stage1/global_corpus_raw.csv    — Stage 1a output

OUTPUTS
-------
  data/stage1/global_corpus.csv        — repos that passed npm verification
  data/stage1/filter_audit_1b.csv      — all repos with pass/fail reason
  data/stage1/checkpoint_1b.csv        — partial results (resume support)

USAGE
-----
  export GITHUB_TOKEN=your_token_here
  python3 stage1b_verify_npm.py
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

BATCH_SIZE  = 20     # repos per GraphQL request (4 file checks each = 80 lookups)
SAVE_EVERY  = 200    # checkpoint every N repos
MAX_RETRIES = 6

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR     = Path(__file__).parent
DATA_DIR       = SCRIPT_DIR / "../../data/stage1"

RAW_CSV        = DATA_DIR / "global_corpus_raw.csv"
CORPUS_OUT     = DATA_DIR / "global_corpus.csv"
AUDIT_OUT      = DATA_DIR / "filter_audit_1b.csv"
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

        if r.status_code in (502, 503, 504):
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
            # Partial errors with usable data — warn and continue
            print(f"  [GQL WARNING] {errors[0].get('message', '')}")

        rl = (data.get("data") or {}).get("rateLimit") or {}
        if rl.get("remaining", 999) < 50:
            sleep_until(rl.get("resetAt", ""))

        return data.get("data") or {}

    return {}


# ── GraphQL query builder ─────────────────────────────────────────────────────

def build_verify_query(batch: list) -> str:
    """
    Checks 4 files per repo in one GraphQL request:
      package.json       — required (confirms npm project)
      package-lock.json  — npm lockfile
      yarn.lock          — Yarn lockfile
      pnpm-lock.yaml     — pnpm lockfile

    Uses object(expression:"HEAD:<filename>") which returns null if the file
    does not exist at the repo root — cheap, no history traversal.
    """
    fragments = []
    for idx, (owner, repo) in enumerate(batch):
        o = owner.replace('"', "")
        r = repo.replace('"', "")
        fragments.append(f"""
        repo_{idx}: repository(owner: "{o}", name: "{r}") {{
            rateLimit {{ remaining resetAt }}
            packageJson:  object(expression: "HEAD:package.json")       {{ id }}
            npmLock:      object(expression: "HEAD:package-lock.json")  {{ id }}
            yarnLock:     object(expression: "HEAD:yarn.lock")          {{ id }}
            pnpmLock:     object(expression: "HEAD:pnpm-lock.yaml")     {{ id }}
        }}
        """)
    return "query { rateLimit { remaining resetAt } " + " ".join(fragments) + " }"


# ── Verification logic ────────────────────────────────────────────────────────

def determine_lockfile(repo_data: dict) -> str | None:
    """
    Returns the lockfile type found, or None if no lockfile exists.
    Priority: package-lock.json > yarn.lock > pnpm-lock.yaml
    """
    if repo_data.get("npmLock"):
        return "package-lock.json"
    if repo_data.get("yarnLock"):
        return "yarn.lock"
    if repo_data.get("pnpmLock"):
        return "pnpm-lock.yaml"
    return None


def verify_batch(batch_df: pd.DataFrame) -> list:
    """
    Verifies one batch of repos. Returns a list of result dicts.
    Each dict has: full_name, passed, fail_reason, lockfile_type
    """
    pairs = list(zip(batch_df["owner_login"], batch_df["repo_name"]))
    query = build_verify_query(pairs)
    data  = graphql_post(query)

    results = []
    for idx, row in enumerate(batch_df.itertuples(index=False)):
        repo_data = data.get(f"repo_{idx}")

        if not repo_data:
            results.append({
                "full_name":    row.full_name,
                "passed":       False,
                "fail_reason":  "api_error",
                "lockfile_type": None,
            })
            continue

        has_package_json = bool(repo_data.get("packageJson"))
        lockfile_type    = determine_lockfile(repo_data)

        if not has_package_json:
            reason = "no_package_json"
        elif not lockfile_type:
            reason = "no_lockfile"
        else:
            reason = None

        results.append({
            "full_name":    row.full_name,
            "passed":       reason is None,
            "fail_reason":  reason,
            "lockfile_type": lockfile_type,
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
        print(f"Resuming: {len(already_checked)} already verified, "
              f"{len(remaining_df)} remaining.\n")
    else:
        remaining_df = raw_df.copy()
        all_results  = []

    # ── Process in batches ────────────────────────────────────────────────────
    total_batches = (len(remaining_df) + BATCH_SIZE - 1) // BATCH_SIZE

    for b_num, start in enumerate(range(0, len(remaining_df), BATCH_SIZE), 1):
        batch = remaining_df.iloc[start: start + BATCH_SIZE]
        results = verify_batch(batch)
        all_results.extend(results)

        passed_in_batch = sum(1 for r in results if r["passed"])
        print(f"  Batch [{b_num}/{total_batches}] "
              f"passed: {passed_in_batch}/{len(results)}")

        # Checkpoint
        if b_num % (SAVE_EVERY // BATCH_SIZE) == 0:
            pd.DataFrame(all_results).to_csv(CHECKPOINT_CSV, index=False)
            print(f"    Checkpoint saved ({len(all_results)} verified so far)")

        time.sleep(0.5)

    # ── Save final outputs ────────────────────────────────────────────────────
    results_df = pd.DataFrame(all_results)

    # Audit file — all repos with pass/fail
    audit_df = raw_df.merge(
        results_df[["full_name", "passed", "fail_reason", "lockfile_type"]],
        on="full_name",
        how="left",
    )
    audit_df.to_csv(AUDIT_OUT, index=False)

    # Final corpus — only repos that passed
    passed_names = set(results_df[results_df["passed"]]["full_name"])
    corpus_df    = raw_df[raw_df["full_name"].isin(passed_names)].copy()

    # Add lockfile_type column to corpus
    lockfile_map = results_df.set_index("full_name")["lockfile_type"].to_dict()
    corpus_df["lockfile_type"] = corpus_df["full_name"].map(lockfile_map)
    corpus_df["corpus_source"] = "global"

    corpus_df.to_csv(CORPUS_OUT, index=False)

    # Clean up checkpoint file
    if CHECKPOINT_CSV.exists():
        CHECKPOINT_CSV.unlink()

    # ── Summary ───────────────────────────────────────────────────────────────
    passed      = results_df["passed"].sum()
    failed      = total - passed
    fail_counts = results_df[~results_df["passed"]]["fail_reason"].value_counts()
    lock_counts = corpus_df["lockfile_type"].value_counts()

    print(f"\n─── Stage 1b Summary ─────────────────────────────────────────")
    print(f"Input repos (Stage 1a)   : {total}")
    print(f"Passed npm verification  : {passed} ({passed/total*100:.1f}%)")
    print(f"Failed                   : {failed} ({failed/total*100:.1f}%)")
    print(f"\nFail reasons:")
    print(fail_counts.to_string())
    print(f"\nLockfile types (passing repos):")
    print(lock_counts.to_string())
    print(f"\nSaved: {CORPUS_OUT}")
    print(f"       {AUDIT_OUT}")
    print(f"\nNext: run stage2c_egyptian_corpus.py")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Stage 3b — Egyptian Corpus Construction & Quality Filtering
============================================================
Builds the targeted Egyptian repository corpus in two phases:

  Phase 1 — Repo pull (skipped if raw corpus already exists)
    For each account in egypt_accounts.csv, fetches their public
    non-fork JS/TS repositories via GraphQL and applies the same
    inclusion filters as Stage 1 (language, has package.json,
    not archived, not a tutorial repo).

    Why same filters as Stage 1?
    The Egyptian corpus is the comparison group for RQ3. If the two
    corpora are selected by different criteria, any adoption rate
    difference could be explained by selection differences rather
    than developer location. Identical filters eliminate this confound.

  Phase 1.5 — Commit count enrichment (runs after Phase 1)
    Fetches commit counts for repos that passed Phase 1 inclusion filters.
    Filters out repos with commits < 50 (same threshold as Stage 1).

  Phase 2 — Quality filtering (always runs)
    Takes the raw corpus (already-pulled or freshly built) and applies
    the same quality thresholds used in Stage 1 sampling:
      - stars >= 4
      - created >= 2025-02-24  (repos born in the AI agent era)
      - commits >= 50
      - deduplicate by full_name
    Outputs the final corpus ready as input for Stage 4 detection.

STATUS: Re-run from scratch with creation date filter applied in Phase 1.

INPUTS
------
  data/stage3/egypt_accounts.csv        — from Stage 3a  (Phase 1 only)
  data/stage3/egyptian_corpus_raw.csv   — Phase 1 output / Phase 2 input

OUTPUTS
-------
  data/stage3/egyptian_corpus_raw.csv   — all repos pulled from Egyptian accounts
  data/stage3/egypt_corpus_input.csv    — filtered corpus ready for Stage 4

USAGE
-----
  export GITHUB_TOKEN=your_token_here
  python3 stage2d_egypt_corpus.py
"""

import os
import re
import sys
import time
import json
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

# ── Configuration ─────────────────────────────────────────────────────────────
TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    sys.exit("ERROR: GITHUB_TOKEN environment variable not set.")

# Phase 1 — repo pull settings
ACCOUNT_BATCH_SIZE = 5     # accounts per GraphQL request
REPO_BATCH_SIZE    = 25    # repos per GraphQL verification request
SAVE_EVERY         = 200   # checkpoint every N account batches
MIN_JS_TS_SHARE    = 0.5   # JS+TS must be >= 50% of language bytes

# Phase 2 — quality filter settings (must match Stage 1)
MIN_STARS         = 4
MIN_CREATED_AT    = "2025-02-24"   # must match Stage 1a creation date filter
MIN_COMMITS       = 50

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent
DATA_DIR     = SCRIPT_DIR / "../../data"
ACCOUNTS_CSV = DATA_DIR / "stage3/egypt_accounts.csv"
RAW_CSV      = DATA_DIR / "stage3/egyptian_corpus_raw.csv"
OUTPUT_CSV   = DATA_DIR / "stage3/egypt_corpus_input.csv"
AUDIT_CSV    = DATA_DIR / "stage3/egypt_corpus_filter_audit.csv"

GRAPHQL_URL = "https://api.github.com/graphql"
GQL_HEADERS = {"Authorization": f"Bearer {TOKEN}"}

LANGUAGES = ["JavaScript", "TypeScript"]

TUTORIAL_RE = re.compile(
    r"(^awesome-|-(tutorial|course|bootcamp|exercises|solutions)$)",
    re.IGNORECASE,
)

audit_rows = []


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def graphql_post(query: str, max_retries: int = 6) -> dict:
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(GRAPHQL_URL, json={"query": query},
                              headers=GQL_HEADERS, timeout=30)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout):
            time.sleep(2 ** attempt)
            continue

        if r.status_code in (403, 429):
            reset = r.headers.get("X-RateLimit-Reset")
            wait  = max(int(reset) - time.time(), 0) + 5 if reset else 60
            time.sleep(wait)
            continue

        if r.status_code in (502, 503, 504):
            time.sleep(2 ** attempt)
            continue

        if r.status_code == 200:
            data   = r.json()
            errors = data.get("errors", [])
            if any(e.get("type") == "RATE_LIMITED" for e in errors):
                time.sleep(60)
                continue
            return data.get("data") or {}

        time.sleep(2 ** attempt)
    return {}


def add_audit(full_name: str, passed: bool, reason: str = ""):
    audit_rows.append({
        "full_name":   full_name,
        "passed":      passed,
        "fail_reason": reason,
    })


# ── Phase 1 helpers ───────────────────────────────────────────────────────────

def build_account_repos_query(logins: list) -> str:
    """Fetch top repos for a batch of accounts — Pass 1."""
    frags = []
    for i, login in enumerate(logins):
        l = login.replace('"', "")
        frags.append(f"""
        u{i}: user(login: "{l}") {{
            repositories(
                first: 30,
                isFork: false,
                orderBy: {{field: STARGAZERS, direction: DESC}}
            ) {{
                nodes {{
                    nameWithOwner
                    name
                    primaryLanguage {{ name }}
                    stargazerCount
                    createdAt
                    pushedAt
                    isArchived
                    description
                    languages(first: 5) {{
                        edges {{ size node {{ name }} }}
                    }}
                }}
            }}
        }}
        """)
    return "{ rateLimit { remaining resetAt } " + " ".join(frags) + " }"


def build_manifest_query(owner_repo_pairs: list) -> str:
    """Check package.json + lockfile existence — Pass 2 (same as Stage 1)."""
    frags = []
    for i, (owner, name) in enumerate(owner_repo_pairs):
        o = owner.replace('"', "")
        n = name.replace('"', "")
        frags.append(f"""
        r{i}: repository(owner: "{o}", name: "{n}") {{
            pkg:   object(expression: "HEAD:package.json")       {{ __typename }}
            lock:  object(expression: "HEAD:package-lock.json")  {{ __typename }}
            yarn:  object(expression: "HEAD:yarn.lock")          {{ __typename }}
            pnpm:  object(expression: "HEAD:pnpm-lock.yaml")     {{ __typename }}
        }}
        """)
    return "{ rateLimit { remaining resetAt } " + " ".join(frags) + " }"


def build_commit_count_query(owner_repo_pairs: list) -> str:
    """Fetch commit count for each repo via defaultBranchRef — Phase 1.5."""
    frags = []
    for i, (owner, name) in enumerate(owner_repo_pairs):
        o = owner.replace('"', "")
        n = name.replace('"', "")
        frags.append(f"""
        r{i}: repository(owner: "{o}", name: "{n}") {{
            defaultBranchRef {{
                target {{
                    ... on Commit {{
                        history {{ totalCount }}
                    }}
                }}
            }}
        }}
        """)
    return "{ rateLimit { remaining resetAt } " + " ".join(frags) + " }"


def enrich_with_commit_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Phase 1.5: fetch commit count for every repo and add as a column."""
    pairs = list(zip(df["owner_login"].astype(str), df["repo_name"].astype(str)))
    counts = {}

    print(f"\nPhase 1.5 — Fetching commit counts for {len(pairs):,} repos...")
    for start in range(0, len(pairs), REPO_BATCH_SIZE):
        batch = pairs[start: start + REPO_BATCH_SIZE]
        data  = graphql_post(build_commit_count_query(batch))
        for i, (owner, name) in enumerate(batch):
            rd     = data.get(f"r{i}") or {}
            ref    = rd.get("defaultBranchRef") or {}
            target = ref.get("target") or {}
            hist   = target.get("history") or {}
            counts[f"{owner}/{name}"] = hist.get("totalCount", 0)
        if (start // REPO_BATCH_SIZE + 1) % 50 == 0:
            done = min(start + REPO_BATCH_SIZE, len(pairs))
            print(f"  [{done}/{len(pairs)}] commit counts fetched...")
        time.sleep(0.3)

    df = df.copy()
    df["commit_count"] = df["full_name"].map(counts).fillna(0).astype(int)
    return df


def classify_ecosystem(has_lock: bool, has_yarn: bool, has_pnpm: bool) -> str:
    if has_pnpm:  return "pnpm"
    if has_yarn:  return "yarn"
    if has_lock:  return "npm"
    return "npm_no_lock"


def compute_stratum(stars: int) -> str:
    if stars <= 50:   return "small"
    if stars <= 500:  return "medium"
    return "large"


def pull_repos_from_accounts(accounts_df: pd.DataFrame) -> list:
    """Phase 1: Pull repos from each Egyptian developer account."""
    logins = accounts_df["login"].astype(str).tolist()
    passed_repos = []

    for start in range(0, len(logins), ACCOUNT_BATCH_SIZE):
        batch = logins[start: start + ACCOUNT_BATCH_SIZE]
        data  = graphql_post(build_account_repos_query(batch))

        for i, login in enumerate(batch):
            user_data = data.get(f"u{i}") or {}
            repos     = (user_data.get("repositories") or {}).get("nodes") or []

            for repo in repos:
                full_name = repo.get("nameWithOwner") or ""
                lang      = (repo.get("primaryLanguage") or {}).get("name", "")
                stars     = repo.get("stargazerCount", 0)
                created   = repo.get("createdAt", "") or ""
                pushed    = repo.get("pushedAt", "") or ""
                archived  = repo.get("isArchived", False)
                name      = repo.get("name", "")
                desc      = repo.get("description") or ""

                # Language filter
                if lang not in LANGUAGES:
                    add_audit(full_name, False, "language")
                    continue

                # Archived
                if archived:
                    add_audit(full_name, False, "archived")
                    continue

                # Creation date filter — must match Stage 1a
                if created[:10] < MIN_CREATED_AT:
                    add_audit(full_name, False, "created_before_agent_era")
                    continue

                # Tutorial/auto-gen name patterns
                if TUTORIAL_RE.search(name):
                    add_audit(full_name, False, "tutorial_pattern")
                    continue

                # JS+TS share
                lang_edges  = (repo.get("languages") or {}).get("edges") or []
                total_bytes = sum(e["size"] for e in lang_edges)
                jsts_bytes  = sum(
                    e["size"] for e in lang_edges
                    if e["node"]["name"] in LANGUAGES
                )
                share = jsts_bytes / total_bytes if total_bytes else 0
                if share < MIN_JS_TS_SHARE:
                    add_audit(full_name, False, "js_ts_share")
                    continue

                passed_repos.append({
                    "full_name":        full_name,
                    "owner_login":      login,
                    "repo_name":        name,
                    "primary_language": lang,
                    "stars":            stars,
                    "created_at":       created,
                    "pushed_at":        pushed,
                    "js_ts_byte_share": round(share, 3),
                    "size_stratum":     compute_stratum(stars),
                    "description":      desc[:200],
                    "corpus_source":    "egyptian_targeted",
                })

        if (start // ACCOUNT_BATCH_SIZE + 1) % SAVE_EVERY == 0:
            print(f"  [{start + ACCOUNT_BATCH_SIZE}/{len(logins)}] "
                  f"repos so far: {len(passed_repos)}")
        time.sleep(0.3)

    # Pass 2: verify package.json presence
    print(f"\nPass 2 — Verifying package.json for {len(passed_repos)} repos...")
    pairs   = [(r["owner_login"], r["repo_name"]) for r in passed_repos]
    with_pkg = set()

    for start in range(0, len(pairs), REPO_BATCH_SIZE):
        batch = pairs[start: start + REPO_BATCH_SIZE]
        data  = graphql_post(build_manifest_query(batch))
        for i, (owner, name) in enumerate(batch):
            rd = data.get(f"r{i}") or {}
            if rd.get("pkg"):
                with_pkg.add(f"{owner}/{name}")
                has_lock  = bool(rd.get("lock"))
                has_yarn  = bool(rd.get("yarn"))
                has_pnpm  = bool(rd.get("pnpm"))
                for r in passed_repos:
                    if r["full_name"] == f"{owner}/{name}":
                        r["ecosystem_type"] = classify_ecosystem(has_lock, has_yarn, has_pnpm)
        time.sleep(0.3)

    final = [r for r in passed_repos if r["full_name"] in with_pkg]
    removed = len(passed_repos) - len(final)
    print(f"  {removed} repos removed (no package.json)")
    return final


# ── Phase 2: Quality filter ────────────────────────────────────────────────────

def apply_quality_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Apply Stage 1-equivalent quality filters to the raw corpus."""
    n0 = len(df)
    print(f"\nPhase 2 — Quality filtering ({n0:,} raw repos)")

    # Numeric stars
    df["stars"] = pd.to_numeric(df["stars"], errors="coerce").fillna(0).astype(int)
    df = df[df["stars"] >= MIN_STARS]
    print(f"  After stars >= {MIN_STARS}       : {len(df):,}  (removed {n0 - len(df):,})")

    # Commits threshold (matches Stage 1a)
    if "commit_count" in df.columns:
        n_pre = len(df)
        df["commit_count"] = pd.to_numeric(df["commit_count"], errors="coerce").fillna(0).astype(int)
        df = df[df["commit_count"] >= MIN_COMMITS]
        print(f"  After commits >= {MIN_COMMITS}     : {len(df):,}  (removed {n_pre - len(df):,})")

    # Creation date filter (matches Stage 1a exactly)
    n1 = len(df)
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
    df = df[df["created_at"] >= pd.Timestamp(MIN_CREATED_AT, tz="UTC")]
    df["created_at"] = df["created_at"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"  After created >= {MIN_CREATED_AT}: {len(df):,}  (removed {n1 - len(df):,})")

    # Ensure ecosystem_type column exists
    if "ecosystem_type" not in df.columns and "ecosystem" in df.columns:
        df = df.rename(columns={"ecosystem": "ecosystem_type"})
    if "ecosystem_type" not in df.columns:
        df["ecosystem_type"] = "npm"

    # Deduplicate
    n2 = len(df)
    df = df.drop_duplicates(subset=["full_name"])
    if n2 != len(df):
        print(f"  After dedup              : {len(df):,}  (removed {n2 - len(df):,} duplicates)")

    # Mark corpus source
    df["corpus_source"] = "egyptian_targeted"

    return df


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    # ── Phase 1 ───────────────────────────────────────────────────────────────
    if RAW_CSV.exists():
        print(f"Raw corpus found at {RAW_CSV.name} — skipping Phase 1 (repo pull).")
        print(f"  Delete {RAW_CSV.name} and re-run to rebuild from accounts.\n")
    else:
        if not ACCOUNTS_CSV.exists():
            sys.exit(f"ERROR: {ACCOUNTS_CSV} not found. Run stage2c_egypt_discovery.py first.")

        accounts_df = pd.read_csv(ACCOUNTS_CSV)
        print(f"Loaded {len(accounts_df):,} Egyptian developer accounts.")
        print(f"\nPhase 1 — Pulling repos from {len(accounts_df):,} accounts...")

        repos = pull_repos_from_accounts(accounts_df)
        raw_df = pd.DataFrame(repos)
        raw_df.to_csv(RAW_CSV, index=False)
        print(f"\nRaw corpus saved: {len(raw_df):,} repos → {RAW_CSV}")

        if audit_rows:
            pd.DataFrame(audit_rows).to_csv(AUDIT_CSV, index=False)

    # ── Phase 1.5 — Enrich with commit counts (skipped if already done) ──────
    raw_df = pd.read_csv(RAW_CSV)
    print(f"Loaded raw corpus: {len(raw_df):,} repos from {RAW_CSV.name}")

    if "commit_count" not in raw_df.columns:
        raw_df = enrich_with_commit_counts(raw_df)
        raw_df.to_csv(RAW_CSV, index=False)
        print(f"Commit counts saved back to {RAW_CSV.name}")
    else:
        print("Commit counts already present — skipping Phase 1.5.")

    # ── Phase 2 ───────────────────────────────────────────────────────────────

    filtered_df = apply_quality_filters(raw_df)
    filtered_df.to_csv(OUTPUT_CSV, index=False)

    # ── Summary ───────────────────────────────────────────────────────────────
    eco_counts = filtered_df.get("ecosystem_type", pd.Series()).value_counts()
    lang_counts = filtered_df.get("primary_language", pd.Series()).value_counts()

    print(f"\n─── Stage 3b Summary ─────────────────────────────────────────────")
    print(f"Raw Egyptian corpus   : {len(raw_df):,} repos")
    print(f"After quality filters : {len(filtered_df):,} repos")
    print(f"\nBy ecosystem:")
    for eco, n in eco_counts.items():
        print(f"  {eco:<15} {n:>6}")
    print(f"\nBy language:")
    for lang, n in lang_counts.items():
        print(f"  {lang:<15} {n:>6}")
    print(f"\nSaved: {OUTPUT_CSV}")
    print(f"\nNext: run Stage 4 on the Egyptian corpus:")
    print(f"  python3 scripts/stage4/stage4_detection.py --corpus data/stage3/egypt_corpus_input.csv")


if __name__ == "__main__":
    main()

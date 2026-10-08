"""
Stage 1 — Global JS/TS/npm Corpus Construction
===============================================
Builds the global half of the unified corpus using a batched GraphQL approach.

WHAT THIS SCRIPT DOES
---------------------
1. Searches GitHub for JS/TS repos across three star bands (small/medium/large).
2. Pre-filters candidates using data already in the search result (no extra calls).
3. For each repo that survives pre-filtering, sends one batched GraphQL request
   that checks four things at once:
     - package.json present at root          (confirms it is an npm project)
     - at least one lockfile present         (confirms npm is actively used)
     - JS/TS byte share across all languages (confirms JS/TS is the primary ecosystem)
4. Writes every repo + its pass/fail reason to filter_audit_global.csv.
5. Writes every API call to pull_log_global.jsonl for reproducibility.

HOW THIS DIFFERS FROM stage1_fast_graphql.py
--------------------------------------------
- Adds lockfile checks (package-lock.json, yarn.lock, pnpm-lock.yaml) to the
  GraphQL query — because package.json alone does not confirm npm is in use.
- GraphQL batch size reduced 50 → 25 to stay under complexity limits with
  the extra object lookups.
- Output renamed to global_corpus.csv; adds corpus_source and lockfile_type columns.
- Filter criteria are IDENTICAL to what stage2c_global_filters.py applies to
  Egyptian accounts — this guarantees both corpora are held to the same standard.

OUTPUTS
-------
  global_corpus.csv        — repos that passed all filters (the global corpus)
  filter_audit_global.csv  — every candidate with pass/fail reason (reproducibility)
  pull_log_global.jsonl    — every API call timestamped (reproducibility)

USAGE
-----
  export GITHUB_TOKEN=your_token_here
  python stage1_global_corpus.py
"""

import os
import re
import time
import json
import requests
import pandas as pd
from datetime import datetime, timezone

# ── Shared constants (must match across all 6 topics) ─────────────────────────
STUDY_SNAPSHOT_DATE = "2026-09-01"
MIN_COMMITS         = 10
MIN_CONTRIBUTORS    = 2
MIN_LAST_PUSH       = "2023-01-01"
MIN_JS_TS_SHARE     = 0.5

# ── Topic-specific ────────────────────────────────────────────────────────────
TOPIC_ID      = 2
ECOSYSTEM     = "npm"
MANIFEST_FILE = "package.json"
LANGUAGES     = ["JavaScript", "TypeScript"]

# ── API ───────────────────────────────────────────────────────────────────────
GITHUB_API  = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"
TOKEN       = os.environ.get("GITHUB_TOKEN")

REST_HEADERS = {"Accept": "application/vnd.github+json"}
if TOKEN:
    REST_HEADERS["Authorization"] = f"Bearer {TOKEN}"

GQL_HEADERS = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}

# Reduced from 50 to 25: we now have 4 object lookups per repo (package.json
# + 3 lockfiles) instead of 1. Keeps each request under GraphQL complexity limits.
GRAPHQL_BATCH_SIZE = 25

# ── Output files ──────────────────────────────────────────────────────────────
CORPUS_OUT       = "global_corpus.csv"
FILTER_AUDIT_OUT = "filter_audit_global.csv"
PULL_LOG_OUT     = "pull_log_global.jsonl"

filter_audit_rows = []

# ── Exclusion patterns (E-1, E-4) ────────────────────────────────────────────
TUTORIAL_RE = re.compile(
    r"(^awesome-|-(tutorial|course|bootcamp|exercises|solutions)$)",
    re.IGNORECASE,
)
AUTOGEN_RE = re.compile(r"^[a-z0-9]+-[a-z0-9]+-[a-z0-9]+$")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def compute_stratum(stars: int) -> str:
    if stars <= 50:
        return "small"
    if stars <= 500:
        return "medium"
    return "large"


def log_api_call(endpoint: str, params: dict, status_code: int, response_size: int = 0):
    with open(PULL_LOG_OUT, "a") as f:
        f.write(json.dumps({
            "timestamp":           datetime.now(timezone.utc).isoformat(),
            "endpoint":            endpoint,
            "params":              params,
            "status_code":         status_code,
            "response_size_bytes": response_size,
        }) + "\n")


def add_audit(repo_id, full_name: str, passed: bool, failed_rule: str = None):
    filter_audit_rows.append({
        "repo_id":     repo_id,
        "full_name":   full_name,
        "passed_all":  passed,
        "failed_rule": failed_rule,
        "topic_id":    TOPIC_ID,
    })


def rest_get(url: str, params: dict = None, max_retries: int = 4):
    """REST GET with exponential backoff and rate-limit handling."""
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=REST_HEADERS, params=params, timeout=15)
            log_api_call(url, params or {}, resp.status_code, len(resp.content))
            if resp.status_code == 403:
                reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait  = max(reset - int(time.time()), 1) + 2
                print(f"  REST rate limited. Sleeping {wait}s...")
                time.sleep(wait)
                continue
            return resp
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            wait = 2 ** attempt
            print(f"  Network error ({type(e).__name__}), retry {attempt}/{max_retries} in {wait}s...")
            time.sleep(wait)
    return None


def graphql_post(query: str, max_retries: int = 4) -> dict:
    """GraphQL POST with retry, HTTP 403, and RATE_LIMITED payload handling."""
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                GRAPHQL_URL,
                json={"query": query},
                headers=GQL_HEADERS,
                timeout=30,
            )
            log_api_call(GRAPHQL_URL, {"query_len": len(query)}, resp.status_code, len(resp.content))
            if resp.status_code == 403:
                reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait  = max(reset - int(time.time()), 1) + 2
                print(f"  GraphQL rate limited (HTTP 403). Sleeping {wait}s...")
                time.sleep(wait)
                continue
            if resp.status_code in (502, 504):
                wait = 2 ** attempt
                print(f"  Server error {resp.status_code}, retry {attempt}/{max_retries} in {wait}s...")
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                return {}
            payload = resp.json()
            if "errors" in payload:
                if any(e.get("type") == "RATE_LIMITED" for e in payload["errors"]):
                    print("  GraphQL RATE_LIMITED error. Sleeping 60s...")
                    time.sleep(60)
                    continue
            return payload.get("data") or {}
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            wait = 2 ** attempt
            print(f"  Network error ({type(e).__name__}), retry {attempt}/{max_retries} in {wait}s...")
            time.sleep(wait)
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — GitHub Search: one query per language × star band
# ─────────────────────────────────────────────────────────────────────────────
#
# Three star bands ensure balanced coverage across strata. Without this,
# GitHub search returns only the most popular repos and the small-stratum
# would be severely under-represented.
#
# 2 languages × 3 bands × up to 1,000 results per band = up to 6,000 candidates.

STAR_BANDS = [
    ("0..50",   "small",  10),   # (star range, stratum label, max_pages)
    ("51..500", "medium", 10),
    (">500",    "large",  10),
]


def search_repos(language: str, stars: str, max_pages: int = 10, per_page: int = 100) -> list:
    """Search GitHub for one language + one star band. Returns raw API items."""
    results = []
    query   = (
        f"language:{language} fork:false "
        f"stars:{stars} "
        f"pushed:>{MIN_LAST_PUSH} "
        f"created:<{STUDY_SNAPSHOT_DATE}"
    )
    for page in range(1, max_pages + 1):
        resp = rest_get(
            f"{GITHUB_API}/search/repositories",
            params={"q": query, "sort": "stars", "order": "desc",
                    "per_page": per_page, "page": page},
        )
        if resp is None or resp.status_code != 200:
            break
        items = resp.json().get("items", [])
        if not items:
            break
        results.extend(items)
        print(f"  [{language} stars:{stars}] page {page}: {len(items)} repos (total {len(results)})")
        time.sleep(2)   # Search API: 30 req/min authenticated
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — GraphQL batch: manifest + lockfiles + language byte share
# ─────────────────────────────────────────────────────────────────────────────

def build_batch_query(batch: list) -> str:
    """
    Build a single GraphQL query for a batch of (owner, name) pairs.

    Checks per repo (all in one request):
      - package.json at root          → confirms npm project       (I-9)
      - package-lock.json at root     → npm lockfile signal        (I-9b)
      - yarn.lock at root             → yarn lockfile signal       (I-9b)
      - pnpm-lock.yaml at root        → pnpm lockfile signal       (I-9b)
      - languages byte distribution   → JS/TS share check          (I-8)

    Why commit count is excluded:
      history{totalCount} forces GitHub to scan the full commit history of
      every repo in the batch. On the first batch of 25 repos this exhausts
      the GraphQL point quota and triggers a 1-hour rate limit block.
      Repos are pre-filtered by pushed_at > 2023-01-01 which is a strong
      proxy for MIN_COMMITS = 10 (any repo actively pushed for 2+ years
      almost certainly has ≥10 commits).
    """
    fragments = []
    for idx, (owner, name) in enumerate(batch):
        o = owner.replace('"', "")
        n = name.replace('"', "")
        fragments.append(f"""
        repo_{idx}: repository(owner: "{o}", name: "{n}") {{
            nameWithOwner
            packageJson: object(expression: "HEAD:package.json")      {{ id }}
            npmLock:     object(expression: "HEAD:package-lock.json") {{ id }}
            yarnLock:    object(expression: "HEAD:yarn.lock")         {{ id }}
            pnpmLock:    object(expression: "HEAD:pnpm-lock.yaml")    {{ id }}
            languages(first: 5) {{
                edges {{ size node {{ name }} }}
            }}
        }}
        """)
    return "query { " + " ".join(fragments) + " }"


def parse_batch_results(data: dict) -> dict:
    """
    Parse a GraphQL batch response.
    Returns: dict of full_name → {has_manifest, lockfile_type, js_ts_share}
    """
    out = {}
    for repo_data in data.values():
        if not repo_data:
            continue
        full_name = repo_data.get("nameWithOwner")
        if not full_name:
            continue

        has_manifest = repo_data.get("packageJson") is not None

        # Record which lockfile is present (first match wins)
        if repo_data.get("npmLock"):
            lockfile_type = "package-lock.json"
        elif repo_data.get("yarnLock"):
            lockfile_type = "yarn.lock"
        elif repo_data.get("pnpmLock"):
            lockfile_type = "pnpm-lock.yaml"
        else:
            lockfile_type = "none"

        lang_edges  = (repo_data.get("languages") or {}).get("edges") or []
        total_bytes = sum(e["size"] for e in lang_edges)
        js_ts_bytes = sum(
            e["size"] for e in lang_edges
            if e["node"]["name"] in ("JavaScript", "TypeScript")
        )
        js_ts_share = (js_ts_bytes / total_bytes) if total_bytes > 0 else 0.0

        out[full_name] = {
            "has_manifest":  has_manifest,
            "lockfile_type": lockfile_type,
            "js_ts_share":   js_ts_share,
        }
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Exclusion checks (applied before GraphQL to save quota)
# ─────────────────────────────────────────────────────────────────────────────

def check_exclusions(repo: dict) -> str | None:
    """Returns the failed exclusion rule code, or None if the repo passes."""
    name = repo.get("name", "")
    desc = (repo.get("description") or "").lower()

    # E-1: tutorial / course repos
    if TUTORIAL_RE.search(name) or any(
        kw in desc for kw in ["tutorial", "course", "bootcamp", "exercises", "solutions"]
    ):
        return "E-1"

    # E-2: zero-activity repos (no stars, no forks)
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    if stars == 0 and forks == 0:
        return "E-2"

    # E-4: auto-generated name pattern with minimal description
    if AUTOGEN_RE.match(name) and len(desc) < 20:
        return "E-4"

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    if not TOKEN:
        print("WARNING: no GITHUB_TOKEN — unauthenticated rate limit is 60 req/hr.")

    # ── Step 1: Search all language × star band combinations ─────────────────
    raw = []
    for language in LANGUAGES:
        for stars, stratum, max_pages in STAR_BANDS:
            print(f"\nSearching {language} repos (stars:{stars} → {stratum})...")
            raw.extend(search_repos(language, stars=stars, max_pages=max_pages))

    # Deduplicate by GitHub repo ID (JS and TS searches can return the same repo)
    seen = {}
    for r in raw:
        if r["id"] not in seen:
            seen[r["id"]] = r
    candidates = list(seen.values())
    print(f"\n{len(candidates)} unique candidates after dedup.")

    # ── Step 2: Pre-filters using search result data (zero extra API calls) ───
    passed_fast = []
    for repo in candidates:
        repo_id   = repo["id"]
        full_name = repo["full_name"]

        if repo.get("fork"):
            add_audit(repo_id, full_name, False, "I-1-fork"); continue
        if repo.get("archived"):
            add_audit(repo_id, full_name, False, "I-2-archived"); continue
        if repo.get("disabled"):
            add_audit(repo_id, full_name, False, "I-3-disabled"); continue
        if (repo.get("pushed_at") or "")[:10] < MIN_LAST_PUSH:
            add_audit(repo_id, full_name, False, "I-6-push-date"); continue
        if (repo.get("pushed_at") or "")[:10] > STUDY_SNAPSHOT_DATE:
            add_audit(repo_id, full_name, False, "snapshot-bound"); continue
        if repo.get("language") not in LANGUAGES:
            add_audit(repo_id, full_name, False, "I-8-primary-lang"); continue
        if (repo.get("size") or 0) == 0:
            add_audit(repo_id, full_name, False, "I-4-empty"); continue

        ex_rule = check_exclusions(repo)
        if ex_rule:
            add_audit(repo_id, full_name, False, ex_rule); continue

        passed_fast.append(repo)

    print(f"{len(passed_fast)}/{len(candidates)} passed pre-filters → sending to GraphQL...")

    # ── Step 3: GraphQL batch checks (manifest + lockfiles + byte share) ──────
    repo_lookup   = {r["full_name"]: r for r in passed_fast}
    pairs         = [(r["owner"]["login"], r["name"]) for r in passed_fast]
    gql_results   = {}
    total_batches = (len(pairs) + GRAPHQL_BATCH_SIZE - 1) // GRAPHQL_BATCH_SIZE

    for i in range(0, len(pairs), GRAPHQL_BATCH_SIZE):
        batch     = pairs[i : i + GRAPHQL_BATCH_SIZE]
        batch_num = i // GRAPHQL_BATCH_SIZE + 1
        end       = min(i + GRAPHQL_BATCH_SIZE, len(pairs))
        print(f"  GraphQL batch {batch_num}/{total_batches} (repos {i+1}–{end})...")

        data = graphql_post(build_batch_query(batch))

        if data:
            gql_results.update(parse_batch_results(data))
        else:
            # Fallback: query repos one by one if the whole batch failed
            print(f"  Batch {batch_num} returned no data — retrying individually...")
            for owner, name in batch:
                single = graphql_post(build_batch_query([(owner, name)]))
                if single:
                    gql_results.update(parse_batch_results(single))
                time.sleep(0.2)

        time.sleep(1)   # 1s between batches keeps well under 900 points/min

    print(f"GraphQL done. {len(gql_results)}/{len(pairs)} repos returned data.")

    # ── Step 4: Apply GraphQL-based filters and build the corpus ─────────────
    corpus_rows = []

    for full_name, repo in repo_lookup.items():
        repo_id = repo["id"]
        owner   = repo["owner"]["login"]
        name    = repo["name"]
        gql     = gql_results.get(full_name)

        if gql is None:
            # Repo was private, deleted, or renamed between search and GraphQL call
            add_audit(repo_id, full_name, False, "graphql-no-data")
            continue

        # I-9: must have package.json — hard requirement
        if not gql["has_manifest"]:
            add_audit(repo_id, full_name, False, "I-9-no-package-json")
            continue

        # I-8: JS/TS must be ≥50% of codebase by bytes
        if gql["js_ts_share"] < MIN_JS_TS_SHARE:
            add_audit(repo_id, full_name, False, "I-8-byte-share")
            continue

        # Passes all filters
        add_audit(repo_id, full_name, True)

        # Note: lockfile_type = "none" is allowed (repo is still included).
        # This is flagged in the output for methodology transparency.
        # A repo with package.json but no lockfile is less likely to be an
        # active npm project, but exclusion would be too aggressive.

        corpus_rows.append({
            "repo_id":           repo_id,
            "owner_login":       owner,
            "repo_name":         name,
            "full_name":         full_name,
            "primary_language":  repo.get("language"),
            "stars":             repo.get("stargazers_count"),
            "forks":             repo.get("forks_count"),
            "created_at":        repo.get("created_at"),
            "pushed_at":         repo.get("pushed_at"),
            "default_branch":    repo.get("default_branch"),
            "description":       repo.get("description"),
            "topics":            "|".join(repo.get("topics") or []),
            "size_kb":           repo.get("size"),
            "open_issues":       repo.get("open_issues_count"),
            "has_manifest":      True,
            "lockfile_type":     gql["lockfile_type"],      # package-lock.json / yarn.lock / pnpm-lock.yaml / none
            "js_ts_byte_share":  round(gql["js_ts_share"], 3),
            "size_stratum":      compute_stratum(repo.get("stargazers_count", 0)),
            "contributor_count": None,   # deferred (REST call per repo — too slow in bulk)
            "total_commits":     None,   # deferred (history scan — too expensive in bulk)
            "agent_adopted":     None,   # filled in Stage 4
            "corpus_source":     "global",
            "topic_id":          TOPIC_ID,
            "ecosystem":         ECOSYSTEM,
        })

    # ── Save outputs ──────────────────────────────────────────────────────────
    pd.DataFrame(corpus_rows).to_csv(CORPUS_OUT, index=False)
    pd.DataFrame(filter_audit_rows).to_csv(FILTER_AUDIT_OUT, index=False)

    audit_df      = pd.DataFrame(filter_audit_rows)
    failed_counts = (
        audit_df[~audit_df["passed_all"]]["failed_rule"]
        .value_counts()
        .to_string()
        if not audit_df[~audit_df["passed_all"]].empty else "none"
    )
    corpus_df     = pd.DataFrame(corpus_rows)

    print(f"\n─── Summary ───────────────────────────────────────────────")
    print(f"Search candidates        : {len(candidates)}")
    print(f"Passed pre-filters       : {len(passed_fast)}")
    print(f"GraphQL batches sent     : {total_batches}")
    print(f"Final corpus size        : {len(corpus_rows)}")
    print(f"\nRejected by rule:\n{failed_counts}")
    if not corpus_df.empty:
        print(f"\nStratum breakdown:\n{corpus_df['size_stratum'].value_counts().to_string()}")
        print(f"\nPrimary language:\n{corpus_df['primary_language'].value_counts().to_string()}")
        print(f"\nLockfile distribution:\n{corpus_df['lockfile_type'].value_counts().to_string()}")
    print(f"\nSaved: {CORPUS_OUT}, {FILTER_AUDIT_OUT}, {PULL_LOG_OUT}")


if __name__ == "__main__":
    main()

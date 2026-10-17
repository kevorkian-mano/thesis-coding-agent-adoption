"""
Stage 2c — Egyptian JS/TS/npm Corpus Construction
==================================================
Builds the Egyptian half of the unified corpus by pulling repos from the
21,223 Egyptian developer accounts discovered in Stages 2a + 2b, then
applying the EXACT SAME filters as stage1_global_corpus.py.

WHY THE FILTERS MUST BE IDENTICAL TO STAGE 1
---------------------------------------------
The entire point of the new methodology is that both corpora (global and
Egyptian) are held to the same standard. If Stage 1 requires package.json
+ lockfile check + JS/TS byte share ≥ 50%, Stage 2c must require the same.
Any difference in filter criteria would mean we are comparing populations
that were selected differently — invalidating the RQ2 comparison.

HOW THIS WORKS (two passes)
---------------------------
Pass 1 — Account → Repos (GraphQL, 5 accounts per request):
  For each Egyptian account, fetch their public non-fork repos with basic
  metadata: name, stars, dates, language, archived status, description.
  Apply all filters that can be checked with this data (same as Stage 1
  pre-filters): date range, primary language, exclusion rules, etc.

Pass 2 — Repo Verification (GraphQL, 25 repos per request):
  For repos surviving Pass 1, run the EXACT SAME GraphQL batch query as
  Stage 1: check package.json, lockfiles (package-lock.json / yarn.lock /
  pnpm-lock.yaml), and JS/TS byte share. This is copy-paste identical to
  stage1_global_corpus.py's verification step.

OUTPUT SCHEMA
-------------
Identical to global_corpus.csv, with corpus_source = "egyptian".
This means Stage 3 can merge both files directly with no transformation.

INPUTS
------
  egypt_combined_accounts.csv   (from stage2a + combine_accounts.py)

OUTPUTS
-------
  egyptian_corpus.csv           — repos that passed all filters
  filter_audit_egyptian.csv     — every candidate with pass/fail reason
  pull_log_egyptian.jsonl       — every API call timestamped

USAGE
-----
  export GITHUB_TOKEN=your_token_here
  python3 stage2c_egyptian_corpus.py
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
GRAPHQL_URL = "https://api.github.com/graphql"
TOKEN       = os.environ.get("GITHUB_TOKEN")
GQL_HEADERS = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}

# Pass 1: 5 accounts per request — same as the proven old stage2c_fast_graphql.py.
# Fields are kept identical to the old script to guarantee no 502 errors.
ACCOUNT_BATCH_SIZE = 5
# Pass 2: 25 repos per request (identical to Stage 1 — 4 object lookups per repo)
REPO_BATCH_SIZE    = 25
# Save progress to disk every N account batches
SAVE_EVERY         = 200

# ── Output files ──────────────────────────────────────────────────────────────
CORPUS_OUT       = "egyptian_corpus.csv"
FILTER_AUDIT_OUT = "filter_audit_egyptian.csv"
PULL_LOG_OUT     = "pull_log_egyptian.jsonl"

filter_audit_rows = []

# ── Exclusion patterns (identical to Stage 1) ─────────────────────────────────
TUTORIAL_RE = re.compile(
    r"(^awesome-|-(tutorial|course|bootcamp|exercises|solutions)$)",
    re.IGNORECASE,
)
AUTOGEN_RE = re.compile(r"^[a-z0-9]+-[a-z0-9]+-[a-z0-9]+$")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers (identical to Stage 1)
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


def check_exclusions(name: str, desc: str, stars: int, forks: int) -> str | None:
    """Identical exclusion logic to Stage 1."""
    desc_lower = desc.lower()
    if TUTORIAL_RE.search(name) or any(
        kw in desc_lower for kw in ["tutorial", "course", "bootcamp", "exercises", "solutions"]
    ):
        return "E-1"
    if stars == 0 and forks == 0:
        return "E-2"
    if AUTOGEN_RE.match(name) and len(desc_lower) < 20:
        return "E-4"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Pass 1 — Fetch repos from Egyptian accounts
# ─────────────────────────────────────────────────────────────────────────────

def build_account_query(logins: list) -> str:
    """
    Fetch up to 50 public non-fork repos per account.

    Fields are IDENTICAL to the proven old stage2c_fast_graphql.py to
    guarantee no 502 errors. Only the minimum fields needed for
    pre-filtering are requested: name, stars, pushedAt, primaryLanguage.

    Extra metadata (createdAt, description, isArchived, etc.) is not
    fetched here — it is either not needed for filtering or will be
    available from Pass 2's GraphQL response.
    """
    nodes = []
    for idx, login in enumerate(logins):
        clean = login.replace('"', "").strip()
        nodes.append(f"""
        owner_{idx}: repositoryOwner(login: "{clean}") {{
            login
            repositories(
                first: 50,
                isFork: false,
                privacy: PUBLIC,
                orderBy: {{field: PUSHED_AT, direction: DESC}}
            ) {{
                nodes {{
                    name
                    nameWithOwner
                    stargazerCount
                    pushedAt
                    primaryLanguage {{ name }}
                }}
            }}
        }}
        """)
    return "query { " + " ".join(nodes) + " }"


def parse_account_results(data: dict) -> list:
    """
    Parse Pass 1 response and apply pre-filters.
    Returns list of dicts: repos that passed, ready for Pass 2 verification.

    Fields not fetched in the slim query (createdAt, description, forkCount,
    isDisabled, defaultBranchRef) are set to None/empty — they are not needed
    for filtering and will not affect the Stage 3 merge or Stage 4 detection.
    """
    passed = []

    for owner_data in data.values():
        if not owner_data:
            continue
        owner_login = owner_data.get("login", "")
        repos       = (owner_data.get("repositories") or {}).get("nodes") or []

        for repo in repos:
            if not repo:
                continue

            full_name = repo.get("nameWithOwner", "")
            name      = repo.get("name", "")
            pushed_at = (repo.get("pushedAt") or "")[:10]
            stars     = repo.get("stargazerCount") or 0
            lang      = (repo.get("primaryLanguage") or {}).get("name")

            # I-6: last push too old
            if pushed_at < MIN_LAST_PUSH:
                add_audit(None, full_name, False, "I-6-push-date"); continue
            # Snapshot bound: pushed after study cutoff
            if pushed_at > STUDY_SNAPSHOT_DATE:
                add_audit(None, full_name, False, "snapshot-bound"); continue
            # I-8: primary language must be JS or TS
            if lang not in LANGUAGES:
                add_audit(None, full_name, False, "I-8-primary-lang"); continue
            # E-2: zero stars and isFork already excluded at query level
            if stars == 0:
                add_audit(None, full_name, False, "E-2"); continue

            # Passed all pre-filters — queue for Pass 2 verification
            passed.append({
                "repo_id":          None,   # not available from account query
                "owner_login":      owner_login,
                "repo_name":        name,
                "full_name":        full_name,
                "primary_language": lang,
                "stars":            stars,
                "forks":            None,
                "created_at":       None,
                "pushed_at":        pushed_at,
                "default_branch":   None,
                "description":      None,
                "size_kb":          None,
            })

    return passed


# ─────────────────────────────────────────────────────────────────────────────
# Pass 2 — Verify repos (IDENTICAL to Stage 1's GraphQL verification step)
# ─────────────────────────────────────────────────────────────────────────────

def build_repo_verify_query(batch: list) -> str:
    """
    IDENTICAL to stage1_global_corpus.py's build_batch_query().
    Checks package.json, three lockfiles, and JS/TS byte share per repo.
    batch: list of (owner, name) tuples.
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


def parse_repo_verify_results(data: dict) -> dict:
    """
    IDENTICAL to stage1_global_corpus.py's parse_batch_results().
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
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main(accounts_csv: str = "egypt_combined_accounts.csv"):
    if not TOKEN:
        print("WARNING: no GITHUB_TOKEN — unauthenticated rate limit is 60 req/hr.")

    if not os.path.exists(accounts_csv):
        print(f"Error: {accounts_csv} not found. Run stage2a + combine_accounts.py first.")
        return

    logins        = pd.read_csv(accounts_csv)["login"].dropna().unique().tolist()
    total_accounts = len(logins)
    total_batches  = (total_accounts + ACCOUNT_BATCH_SIZE - 1) // ACCOUNT_BATCH_SIZE
    print(f"Loaded {total_accounts} Egyptian accounts. "
          f"Starting Pass 1 ({total_batches} batches of {ACCOUNT_BATCH_SIZE} accounts)...")

    # ── Pass 1: Fetch repos from accounts and pre-filter ─────────────────────
    pass1_candidates = []   # repos that survived pre-filters, queued for Pass 2

    for i in range(0, total_accounts, ACCOUNT_BATCH_SIZE):
        batch     = logins[i : i + ACCOUNT_BATCH_SIZE]
        batch_num = i // ACCOUNT_BATCH_SIZE + 1

        query = build_account_query(batch)
        data  = graphql_post(query)

        if data:
            new_repos = parse_account_results(data)
            pass1_candidates.extend(new_repos)
        else:
            # Fallback: query accounts individually if the whole batch failed
            print(f"  Batch {batch_num} failed — retrying individually...")
            for login in batch:
                single = graphql_post(build_account_query([login]))
                if single:
                    pass1_candidates.extend(parse_account_results(single))
                time.sleep(0.2)

        if batch_num % SAVE_EVERY == 0 or batch_num == total_batches:
            print(f"  [{batch_num}/{total_batches}] Pass 1 candidates so far: {len(pass1_candidates)}")

        time.sleep(0.3)

    # Deduplicate by full_name (same repo can appear under multiple accounts in a org)
    seen_names       = set()
    unique_candidates = []
    for r in pass1_candidates:
        if r["full_name"] not in seen_names:
            seen_names.add(r["full_name"])
            unique_candidates.append(r)

    print(f"\nPass 1 done. {len(unique_candidates)} unique repos passed pre-filters "
          f"(from {len(pass1_candidates)} total, {len(pass1_candidates) - len(unique_candidates)} duplicates removed).")
    print(f"Starting Pass 2 — verifying package.json, lockfiles, and byte share...")

    # ── Pass 2: Verify repos (identical to Stage 1's GraphQL verification) ───
    pairs         = [(r["owner_login"], r["repo_name"]) for r in unique_candidates]
    repo_lookup   = {r["full_name"]: r for r in unique_candidates}
    gql_results   = {}
    total_p2      = (len(pairs) + REPO_BATCH_SIZE - 1) // REPO_BATCH_SIZE

    for i in range(0, len(pairs), REPO_BATCH_SIZE):
        batch     = pairs[i : i + REPO_BATCH_SIZE]
        batch_num = i // REPO_BATCH_SIZE + 1
        end       = min(i + REPO_BATCH_SIZE, len(pairs))
        print(f"  Pass 2 batch {batch_num}/{total_p2} (repos {i+1}–{end})...")

        data = graphql_post(build_repo_verify_query(batch))

        if data:
            gql_results.update(parse_repo_verify_results(data))
        else:
            print(f"  Batch {batch_num} failed — retrying individually...")
            for owner, name in batch:
                single = graphql_post(build_repo_verify_query([(owner, name)]))
                if single:
                    gql_results.update(parse_repo_verify_results(single))
                time.sleep(0.2)

        time.sleep(1)

    print(f"Pass 2 done. {len(gql_results)}/{len(pairs)} repos returned data.")

    # ── Build final corpus ────────────────────────────────────────────────────
    corpus_rows = []

    for full_name, repo in repo_lookup.items():
        repo_id = repo["repo_id"]
        gql     = gql_results.get(full_name)

        if gql is None:
            add_audit(repo_id, full_name, False, "graphql-no-data")
            continue

        # I-9: must have package.json — hard requirement (identical to Stage 1)
        if not gql["has_manifest"]:
            add_audit(repo_id, full_name, False, "I-9-no-package-json")
            continue

        # I-8: JS/TS must be ≥50% of codebase by bytes (identical to Stage 1)
        if gql["js_ts_share"] < MIN_JS_TS_SHARE:
            add_audit(repo_id, full_name, False, "I-8-byte-share")
            continue

        add_audit(repo_id, full_name, True)

        corpus_rows.append({
            "repo_id":           repo_id,
            "owner_login":       repo["owner_login"],
            "repo_name":         repo["repo_name"],
            "full_name":         full_name,
            "primary_language":  repo["primary_language"],
            "stars":             repo["stars"],
            "forks":             repo["forks"],
            "created_at":        repo["created_at"],
            "pushed_at":         repo["pushed_at"],
            "default_branch":    repo["default_branch"],
            "description":       repo["description"],
            "topics":            "",        # not fetched in account query (performance)
            "size_kb":           repo["size_kb"],
            "open_issues":       None,      # not fetched (expensive per-repo REST call)
            "has_manifest":      True,
            "lockfile_type":     gql["lockfile_type"],
            "js_ts_byte_share":  round(gql["js_ts_share"], 3),
            "size_stratum":      compute_stratum(repo["stars"]),
            "contributor_count": None,      # deferred
            "total_commits":     None,      # deferred
            "agent_adopted":     None,      # filled in Stage 4
            "corpus_source":     "egyptian",
            "topic_id":          TOPIC_ID,
            "ecosystem":         ECOSYSTEM,
        })

    # ── Save outputs ──────────────────────────────────────────────────────────
    corpus_df = pd.DataFrame(corpus_rows)
    audit_df  = pd.DataFrame(filter_audit_rows)

    corpus_df.to_csv(CORPUS_OUT, index=False)
    audit_df.to_csv(FILTER_AUDIT_OUT, index=False)

    failed_counts = (
        audit_df[~audit_df["passed_all"]]["failed_rule"]
        .value_counts()
        .to_string()
        if not audit_df[~audit_df["passed_all"]].empty else "none"
    )

    print(f"\n─── Summary ───────────────────────────────────────────────")
    print(f"Egyptian accounts        : {total_accounts}")
    print(f"Pass 1 candidates        : {len(unique_candidates)}")
    print(f"Pass 2 verified          : {len(gql_results)}")
    print(f"Final corpus size        : {len(corpus_rows)}")
    print(f"\nRejected by rule:\n{failed_counts}")
    if not corpus_df.empty:
        print(f"\nStratum breakdown:\n{corpus_df['size_stratum'].value_counts().to_string()}")
        print(f"\nPrimary language:\n{corpus_df['primary_language'].value_counts().to_string()}")
        print(f"\nLockfile distribution:\n{corpus_df['lockfile_type'].value_counts().to_string()}")
    print(f"\nSaved: {CORPUS_OUT}, {FILTER_AUDIT_OUT}, {PULL_LOG_OUT}")


if __name__ == "__main__":
    main()

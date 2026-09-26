"""
Stage 2c: Egyptian Corpus — Direct Repo Pull (REST version)

Pulls repositories directly owned by each account in the combined
Egyptian seed+snowball list, then applies the same inclusion/exclusion
filters as Stage 1 (fork, push date, JS/TS dominance, commit count,
contributor count, package.json presence).

Input:  egypt_combined_accounts.csv  (login, account_type columns)
Output: egypt_corpus.csv, egypt_filter_audit.csv, egypt_pull_log.jsonl

Requires: pip install requests pandas
Set GITHUB_TOKEN as an environment variable first.
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

# ── Topic-specific ────────────────────────────────────────────────────────────
TOPIC_ID        = 2
ECOSYSTEM       = "npm"
MANIFEST_FILE   = "package.json"
MIN_JS_TS_SHARE = 0.5

# ── API ───────────────────────────────────────────────────────────────────────
GITHUB_API = "https://api.github.com"
TOKEN      = os.environ.get("GITHUB_TOKEN")
HEADERS    = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
HEADERS["Accept"] = "application/vnd.github+json"

# ── Output files ──────────────────────────────────────────────────────────────
CORPUS_OUT       = "egypt_corpus.csv"
FILTER_AUDIT_OUT = "egypt_filter_audit.csv"
PULL_LOG_OUT     = "egypt_pull_log.jsonl"

filter_audit_rows = []

# ── Exclusion patterns ────────────────────────────────────────────────────────
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
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "endpoint":  endpoint,
            "params":    params,
            "status_code": status_code,
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


def rate_limited_get(url: str, params: dict = None, max_retries: int = 4):
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
            log_api_call(url, params or {}, resp.status_code, len(resp.content))
            if resp.status_code == 403:
                reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait  = max(reset - int(time.time()), 1) + 2
                print(f"  Rate limited. Sleeping {wait}s...")
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


# ─────────────────────────────────────────────────────────────────────────────
# Data fetchers
# ─────────────────────────────────────────────────────────────────────────────

def get_account_repos(login: str, account_type: str, max_pages: int = 5) -> list:
    """
    GET /users/{login}/repos or /orgs/{login}/repos.
    Fetches all public, non-fork repos sorted by push date descending.
    """
    endpoint = "orgs" if account_type == "Organization" else "users"
    results  = []
    for page in range(1, max_pages + 1):
        resp = rate_limited_get(
            f"{GITHUB_API}/{endpoint}/{login}/repos",
            params={"per_page": 100, "page": page, "type": "owner", "sort": "pushed"},
        )
        if resp is None or resp.status_code != 200:
            break
        items = resp.json()
        if not items:
            break
        results.extend(items)
        if len(items) < 100:
            break  # last page
        time.sleep(0.5)
    return results


def get_js_ts_share(owner: str, repo: str) -> float:
    resp = rate_limited_get(f"{GITHUB_API}/repos/{owner}/{repo}/languages")
    if resp is None or resp.status_code != 200:
        return 0.0
    lang_bytes = resp.json()
    total = sum(lang_bytes.values())
    if total == 0:
        return 0.0
    js_ts = lang_bytes.get("JavaScript", 0) + lang_bytes.get("TypeScript", 0)
    return js_ts / total


def verify_manifest(owner: str, repo: str) -> bool:
    resp = rate_limited_get(
        f"{GITHUB_API}/repos/{owner}/{repo}/contents/{MANIFEST_FILE}",
        params={"ref": "HEAD"},
    )
    return resp is not None and resp.status_code == 200


def approximate_commit_count(owner: str, repo: str) -> int:
    resp = rate_limited_get(
        f"{GITHUB_API}/repos/{owner}/{repo}/commits",
        params={"per_page": 1, "until": f"{STUDY_SNAPSHOT_DATE}T00:00:00Z"},
    )
    if resp is None or resp.status_code != 200:
        return 0
    link = resp.headers.get("Link", "")
    if not link:
        return len(resp.json())
    match = re.search(r'page=(\d+)>; rel="last"', link)
    return int(match.group(1)) if match else 0


def get_contributor_count(owner: str, repo: str) -> int:
    resp = rate_limited_get(
        f"{GITHUB_API}/repos/{owner}/{repo}/contributors",
        params={"per_page": 1, "anon": "false"},
    )
    if resp is None or resp.status_code == 204:
        return 0
    if resp.status_code != 200:
        return 0
    link = resp.headers.get("Link", "")
    if not link:
        return len(resp.json())
    match = re.search(r'page=(\d+)>; rel="last"', link)
    return int(match.group(1)) if match else 1


# ─────────────────────────────────────────────────────────────────────────────
# Exclusion rules
# ─────────────────────────────────────────────────────────────────────────────

def check_exclusions(repo: dict, commit_count: int) -> str | None:
    name  = repo.get("name", "")
    desc  = (repo.get("description") or "").lower()
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)

    if TUTORIAL_RE.search(name) or any(
        kw in desc for kw in ["tutorial", "course", "bootcamp", "exercises", "solutions"]
    ):
        return "E-1"
    if stars == 0 and forks == 0 and commit_count < 5:
        return "E-2"
    if AUTOGEN_RE.match(name) and len(desc) < 20:
        return "E-4"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main(seed_csv_path: str = "egypt_combined_accounts.csv"):
    seeds = pd.read_csv(seed_csv_path)
    print(f"Loaded {len(seeds)} accounts from {seed_csv_path}")

    corpus_rows = []

    for i, acct in seeds.iterrows():
        login     = str(acct["login"])
        acct_type = str(acct.get("account_type") or "User")
        print(f"[{i+1}/{len(seeds)}] pulling repos for {login} ({acct_type})...")

        repos = get_account_repos(login, acct_type)

        for repo in repos:
            repo_id   = repo.get("id")
            full_name = repo.get("full_name", "")
            owner     = repo["owner"]["login"]
            name      = repo["name"]

            # Fast filters from API response
            if repo.get("fork"):
                add_audit(repo_id, full_name, False, "I-1"); continue
            if repo.get("archived"):
                add_audit(repo_id, full_name, False, "I-2"); continue
            if repo.get("disabled"):
                add_audit(repo_id, full_name, False, "I-3"); continue
            if (repo.get("pushed_at") or "")[:10] < MIN_LAST_PUSH:
                add_audit(repo_id, full_name, False, "I-6"); continue

            # I-9: package.json at root
            has_manifest = verify_manifest(owner, name)
            if not has_manifest:
                add_audit(repo_id, full_name, False, "I-9"); continue

            # I-8: JS/TS byte-share
            js_ts_share = get_js_ts_share(owner, name)
            if js_ts_share < MIN_JS_TS_SHARE:
                add_audit(repo_id, full_name, False, "I-8-share"); continue

            # I-4: minimum commits
            commit_count = approximate_commit_count(owner, name)
            if commit_count < MIN_COMMITS:
                add_audit(repo_id, full_name, False, "I-4"); continue

            # I-5: minimum contributors
            contributor_count = get_contributor_count(owner, name)
            if contributor_count < MIN_CONTRIBUTORS:
                add_audit(repo_id, full_name, False, "I-5"); continue

            # Exclusion rules
            ex_rule = check_exclusions(repo, commit_count)
            if ex_rule:
                add_audit(repo_id, full_name, False, ex_rule); continue

            # All filters passed
            add_audit(repo_id, full_name, True)

            corpus_rows.append({
                "repo_id":           repo_id,
                "seed_account":      login,
                "owner_login":       owner,
                "repo_name":         name,
                "full_name":         full_name,
                "primary_language":  repo.get("language"),
                "stars":             repo.get("stargazers_count"),
                "forks":             repo.get("forks_count"),
                "created_at":        repo.get("created_at"),
                "pushed_at":         repo.get("pushed_at"),
                "default_branch":    repo.get("default_branch"),
                "archived":          repo.get("archived"),
                "fork":              repo.get("fork"),
                "disabled":          repo.get("disabled"),
                "description":       repo.get("description"),
                "topics":            "|".join(repo.get("topics") or []),
                "size_kb":           repo.get("size"),
                "open_issues":       repo.get("open_issues_count"),
                "contributor_count": contributor_count,
                "total_commits":     commit_count,
                "has_manifest":      has_manifest,
                "js_ts_byte_share":  round(js_ts_share, 3),
                "size_stratum":      compute_stratum(repo.get("stargazers_count", 0)),
                "agent_adopted":     None,   # filled in Stage 4
                "topic_id":          TOPIC_ID,
                "ecosystem":         ECOSYSTEM,
            })

            time.sleep(0.3)

    df = pd.DataFrame(corpus_rows).drop_duplicates(subset=["full_name"])
    df.to_csv(CORPUS_OUT, index=False)
    pd.DataFrame(filter_audit_rows).to_csv(FILTER_AUDIT_OUT, index=False)

    print(f"\n─── Summary ─────────────────────────────────────────────")
    print(f"Accounts checked         : {len(seeds)}")
    print(f"Repos passing all filters: {len(df)}")
    if not df.empty:
        print(f"Stratum breakdown:\n{df['size_stratum'].value_counts().to_string()}")
    print(f"\nSaved: {CORPUS_OUT}, {FILTER_AUDIT_OUT}, {PULL_LOG_OUT}")

    if len(df) < 30:
        print("\n*** WARNING: fewer than 30 repos found. Consider widening scope to MENA region. ***")


if __name__ == "__main__":
    main()

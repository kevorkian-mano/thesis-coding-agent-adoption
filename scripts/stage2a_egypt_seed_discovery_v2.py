"""
Stage 2a: Egyptian Seed List Discovery (v2 -- with retry + resume)

Searches GitHub for developer accounts with Egypt-linked locations,
fetches their profile details, and saves a candidate seed list for
manual review before Stage 2b snowball expansion.

Includes Arabic location terms to avoid undercounting Egyptian accounts
who write their location in Arabic.

Requires: pip install requests pandas
Set GITHUB_TOKEN as an environment variable first.
"""

import os
import time
import requests
import pandas as pd

GITHUB_API = "https://api.github.com"
TOKEN      = os.environ.get("GITHUB_TOKEN")
HEADERS    = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
HEADERS["Accept"] = "application/vnd.github+json"

# English and Arabic location terms (both are needed to avoid undercounting)
LOCATION_TERMS = [
    "Egypt", "Cairo", "Alexandria", "Giza",
    "مصر", "القاهرة", "الإسكندرية", "الجيزة",
]

# Minimum activity to be included as a seed candidate
# (per methodology: ≥10 followers OR ≥5 public repos)
MIN_FOLLOWERS   = 10
MIN_PUBLIC_REPOS = 5

OUTPUT_FILE = "egypt_seed_candidates.csv"
SAVE_EVERY  = 25  # write progress every N accounts


# ─────────────────────────────────────────────────────────────────────────────
# Network helpers
# ─────────────────────────────────────────────────────────────────────────────

def request_with_retry(method: str, url: str, max_retries: int = 4, **kwargs):
    """Retry on transient network errors; wait on 403 rate limit."""
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.request(method, url, timeout=15, **kwargs)
            if resp.status_code == 403:
                reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait  = max(reset - int(time.time()), 1) + 2
                print(f"    Rate limited. Sleeping {wait}s (resets at epoch {reset})...")
                time.sleep(wait)
                continue
            return resp
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            wait = 2 ** attempt
            print(f"    Network error ({type(e).__name__}), retry {attempt}/{max_retries} in {wait}s...")
            time.sleep(wait)
    print(f"    FAILED after {max_retries} retries: {url}")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Search and profile fetching
# ─────────────────────────────────────────────────────────────────────────────

def search_users_by_location(location_term: str, max_pages: int = 5, per_page: int = 100) -> list:
    """GET /search/users?q=location:<term> — paginated."""
    results = []
    query = f"location:{location_term}"
    for page in range(1, max_pages + 1):
        resp = request_with_retry(
            "GET", f"{GITHUB_API}/search/users",
            headers=HEADERS,
            params={"q": query, "per_page": per_page, "page": page,
                    "sort": "repositories", "order": "desc"},
        )
        if resp is None or resp.status_code != 200:
            break
        items = resp.json().get("items", [])
        if not items:
            break
        results.extend(items)
        print(f"  [{query}] page {page}: {len(items)} accounts (running total {len(results)})")
        time.sleep(2)  # Search API: 30 req/min
    return results


def get_account_details(login: str) -> dict:
    """GET /users/{login} — returns the fields we need for filtering and output."""
    resp = request_with_retry("GET", f"{GITHUB_API}/users/{login}", headers=HEADERS)
    if resp is None or resp.status_code != 200:
        return {}
    d = resp.json()
    return {
        "name":          d.get("name"),
        "company":       d.get("company"),
        "blog":          d.get("blog"),
        "bio":           d.get("bio"),
        "location_raw":  d.get("location"),
        "public_repos":  d.get("public_repos"),
        "followers":     d.get("followers"),
        "following":     d.get("following"),
        "account_type":  d.get("type"),
        "created_at":    d.get("created_at"),
    }


def meets_activity_filter(details: dict) -> bool:
    """
    Rule: ≥10 followers OR ≥5 public repos.
    Filters out brand-new or completely inactive accounts that are unlikely
    to have meaningful JS/TS repositories.
    JS/TS-specific filtering is applied in Stage 2c after repo pull.
    """
    followers    = details.get("followers") or 0
    public_repos = details.get("public_repos") or 0
    return followers >= MIN_FOLLOWERS or public_repos >= MIN_PUBLIC_REPOS


# ─────────────────────────────────────────────────────────────────────────────
# Resume support
# ─────────────────────────────────────────────────────────────────────────────

def load_existing_progress() -> pd.DataFrame:
    if os.path.exists(OUTPUT_FILE):
        existing = pd.read_csv(OUTPUT_FILE)
        print(f"Resuming from existing file: {len(existing)} accounts already fetched.")
        return existing
    return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    if not TOKEN:
        print("WARNING: no GITHUB_TOKEN set — unauthenticated limit is 60 req/hr.")

    # Collect all candidate account logins across all location terms
    all_accounts = {}
    for term in LOCATION_TERMS:
        print(f"\nSearching for location: {term}")
        found = search_users_by_location(term, max_pages=5)
        for acct in found:
            login = acct["login"]
            if login not in all_accounts:
                all_accounts[login] = {
                    "login":       login,
                    "matched_term": term,
                    "profile_url": acct["html_url"],
                }

    print(f"\nFound {len(all_accounts)} unique candidate accounts across all location terms.")

    # Resume support: skip accounts already fetched
    existing_df  = load_existing_progress()
    already_done = set(existing_df["login"]) if not existing_df.empty else set()
    rows         = existing_df.to_dict("records") if not existing_df.empty else []

    remaining = {k: v for k, v in all_accounts.items() if k not in already_done}
    print(f"Fetching details for {len(remaining)} remaining accounts "
          f"({len(already_done)} already done from a previous run)...")

    filtered_out = 0
    for i, (login, base) in enumerate(remaining.items()):
        details = get_account_details(login)

        # Apply activity filter before adding to the list
        if not meets_activity_filter(details):
            filtered_out += 1
            time.sleep(0.3)
            continue

        rows.append({**base, **details})

        if (i + 1) % SAVE_EVERY == 0:
            pd.DataFrame(rows).to_csv(OUTPUT_FILE, index=False)
            print(f"  ...{i+1}/{len(remaining)} processed (progress saved)")

        time.sleep(0.3)

    df = pd.DataFrame(rows).drop_duplicates(subset=["login"])
    df["review_priority_score"] = df["public_repos"].fillna(0) + df["followers"].fillna(0)
    df = df.sort_values("review_priority_score", ascending=False)
    df.to_csv(OUTPUT_FILE, index=False)

    print(f"\n─── Summary ─────────────────────────────────────────────")
    print(f"Total unique candidates found   : {len(all_accounts)}")
    print(f"Filtered out (low activity)     : {filtered_out}")
    print(f"Saved to seed list              : {len(df)}")
    print(f"  Organizations                 : {(df.get('account_type') == 'Organization').sum()}")
    print(f"  Users                         : {(df.get('account_type') == 'User').sum()}")
    print(f"\nSaved to {OUTPUT_FILE}")
    print("NEXT: manually review this file, remove false positives, then run Stage 2b.")


if __name__ == "__main__":
    main()

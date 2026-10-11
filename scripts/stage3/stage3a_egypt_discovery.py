#!/usr/bin/env python3
"""
Stage 3a — Egyptian Developer Account Discovery
================================================
Discovers Egyptian developer accounts on GitHub in two phases:

  Phase 1 — Seed discovery
    Searches GitHub REST API for users whose location field contains
    Egyptian city/country names (English + Arabic). Applies a minimum
    activity filter (≥10 followers OR ≥5 public repos) to exclude
    inactive accounts. Produces an initial seed list.

  Phase 2 — Snowball expansion
    Takes every seed account and fetches their followers + following
    (up to MAX_CONNECTIONS_PER_SEED each) via GraphQL. Any connection
    that also has an Egyptian location is added to the account list.
    Runs up to MAX_ROUNDS rounds, stopping early at convergence.

Why snowball?
  Many Egyptian developers leave their location field blank. If they
  follow and are followed by Egyptian developers who DO have a location
  set, the snowball round discovers them. This is the same principle
  as S6 in the owner signals pipeline, applied at corpus-building time.

STATUS: Already ran — output is in data/stage3/egypt_accounts.csv.
        Re-run only if you need to refresh the account list.

INPUTS
------
  None — searches GitHub directly.

OUTPUTS
-------
  data/stage3/egypt_accounts.csv    — combined deduplicated account list

USAGE
-----
  export GITHUB_TOKEN=your_token_here
  python3 stage2c_egypt_discovery.py
"""

import os
import sys
import time
import requests
import pandas as pd
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────
TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    sys.exit("ERROR: GITHUB_TOKEN environment variable not set.")

MIN_FOLLOWERS           = 10
MIN_PUBLIC_REPOS        = 5
MAX_CONNECTIONS_PER_SEED = 30   # followers + following fetched per account
MAX_ROUNDS              = 3     # snowball expansion rounds
BATCH_SIZE              = 5     # accounts per GraphQL request
SAVE_EVERY              = 200

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent
DATA_DIR     = SCRIPT_DIR / "../../data"
OUTPUT_CSV   = DATA_DIR / "stage3/egypt_accounts.csv"

GITHUB_API  = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"
REST_HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
}
GQL_HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# ── Egyptian location terms ───────────────────────────────────────────────────
SEARCH_TERMS = [
    "Egypt", "Cairo", "Alexandria", "Giza", "Luxor", "Aswan",
    "Port Said", "Mansoura", "Tanta", "Helwan", "Heliopolis",
    "مصر", "القاهرة", "الإسكندرية", "الجيزة",
]

LOCATION_TERMS = [t.lower() for t in SEARCH_TERMS]


def is_egyptian_location(location: str) -> bool:
    if not location:
        return False
    loc = location.lower().strip()
    return any(term in loc for term in LOCATION_TERMS)


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def rest_get(url: str, params: dict = None, max_retries: int = 4):
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(url, headers=REST_HEADERS, params=params, timeout=30)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout):
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 403:
            reset = r.headers.get("X-RateLimit-Reset")
            wait  = max(int(reset) - time.time(), 0) + 5 if reset else 60
            time.sleep(wait)
            continue
        if r.status_code == 200:
            return r.json()
        return None
    return None


def graphql_post(query: str, max_retries: int = 4) -> dict:
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(GRAPHQL_URL, json={"query": query},
                              headers=GQL_HEADERS, timeout=30)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout):
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 403:
            time.sleep(60)
            continue
        if r.status_code == 200:
            data = r.json()
            errors = data.get("errors", [])
            if any(e.get("type") == "RATE_LIMITED" for e in errors):
                time.sleep(60)
                continue
            return data.get("data") or {}
        time.sleep(2 ** attempt)
    return {}


# ── Phase 1: Seed discovery ───────────────────────────────────────────────────

def search_users_by_location(term: str) -> list:
    """Search GitHub REST for users with a given location term."""
    accounts = []
    for page in range(1, 11):   # max 10 pages × 100 = 1,000 results per term
        result = rest_get(
            f"{GITHUB_API}/search/users",
            params={"q": f"location:{term}", "per_page": 100, "page": page},
        )
        if not result:
            break
        items = result.get("items", [])
        if not items:
            break
        accounts.extend(items)
        total = result.get("total_count", 0)
        if len(accounts) >= min(total, 1000):
            break
        time.sleep(1)
    return accounts


def build_profile_query(logins: list) -> str:
    frags = []
    for i, login in enumerate(logins):
        l = login.replace('"', "")
        frags.append(
            f'u{i}: user(login: "{l}") {{'
            f'  login location followers {{ totalCount }} repositories {{ totalCount }}'
            f'}}'
        )
    return "{ " + " ".join(frags) + " }"


def fetch_seed_accounts() -> list:
    """Run Phase 1: search all location terms, batch-fetch profiles, apply filter."""
    print("Phase 1 — Seed discovery")
    raw_logins = set()
    for term in SEARCH_TERMS:
        items = search_users_by_location(term)
        for item in items:
            if item.get("type") == "User":
                raw_logins.add(item["login"])
        print(f"  {term:<20} → {len(items)} results  (total unique: {len(raw_logins)})")
        time.sleep(1)

    print(f"\nBatch-fetching profiles for {len(raw_logins)} candidates...")
    logins = list(raw_logins)
    seed   = []

    for start in range(0, len(logins), BATCH_SIZE):
        batch = logins[start: start + BATCH_SIZE]
        data  = graphql_post(build_profile_query(batch))
        for i, login in enumerate(batch):
            profile = data.get(f"u{i}") or {}
            loc     = profile.get("location") or ""
            if not is_egyptian_location(loc):
                continue
            followers  = (profile.get("followers") or {}).get("totalCount", 0)
            repo_count = (profile.get("repositories") or {}).get("totalCount", 0)
            if followers >= MIN_FOLLOWERS or repo_count >= MIN_PUBLIC_REPOS:
                seed.append({
                    "login":        login,
                    "location":     loc,
                    "followers":    followers,
                    "public_repos": repo_count,
                    "source":       "seed",
                })
        time.sleep(0.3)

    print(f"Seed list: {len(seed)} Egyptian developer accounts")
    return seed


# ── Phase 2: Snowball expansion ───────────────────────────────────────────────

def build_network_query(logins: list) -> str:
    frags = []
    n = MAX_CONNECTIONS_PER_SEED // 2
    for i, login in enumerate(logins):
        l = login.replace('"', "")
        frags.append(
            f'u{i}: user(login: "{l}") {{'
            f'  followers(first: {n}) {{ nodes {{ login location }} }}'
            f'  following(first: {n}) {{ nodes {{ login location }} }}'
            f'}}'
        )
    return "{ " + " ".join(frags) + " }"


def snowball_expand(known_logins: set, seed_logins: list) -> list:
    """Expand account list through follower/following networks."""
    new_accounts = []
    logins = list(seed_logins)

    for start in range(0, len(logins), BATCH_SIZE):
        batch = logins[start: start + BATCH_SIZE]
        data  = graphql_post(build_network_query(batch))
        for i in range(len(batch)):
            user_data = data.get(f"u{i}") or {}
            network   = (
                (user_data.get("followers") or {}).get("nodes", []) +
                (user_data.get("following") or {}).get("nodes", [])
            )
            for conn in network:
                login = conn.get("login")
                loc   = conn.get("location") or ""
                if login and login not in known_logins and is_egyptian_location(loc):
                    known_logins.add(login)
                    new_accounts.append({
                        "login":    login,
                        "location": loc,
                        "source":   "snowball",
                    })
        time.sleep(0.3)

    return new_accounts


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    # Phase 1
    seed_accounts = fetch_seed_accounts()
    all_accounts  = seed_accounts.copy()
    known_logins  = {a["login"] for a in all_accounts}

    # Phase 2: snowball
    print(f"\nPhase 2 — Snowball expansion (up to {MAX_ROUNDS} rounds)")
    for round_num in range(1, MAX_ROUNDS + 1):
        expand_from = list(known_logins)
        new = snowball_expand(known_logins, expand_from)
        print(f"  Round {round_num}: {len(new)} new Egyptian accounts found")
        if not new:
            print("  Converged — stopping early.")
            break
        all_accounts.extend(new)

    # Deduplicate + save
    df = pd.DataFrame(all_accounts).drop_duplicates(subset=["login"])
    df.to_csv(OUTPUT_CSV, index=False)

    print(f"\n─── Stage 2c Summary ─────────────────────────────────────────")
    print(f"Total Egyptian developer accounts : {len(df):,}")
    print(f"  Seed (direct location search)   : {(df['source']=='seed').sum():,}")
    print(f"  Snowball (network expansion)     : {(df['source']=='snowball').sum():,}")
    print(f"\nSaved: {OUTPUT_CSV}")
    print(f"\nNext: run stage2d_egypt_corpus.py")


if __name__ == "__main__":
    main()

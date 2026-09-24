"""
Stage 2b: Egyptian Seed List Snowball Expansion

Takes the cleaned seed list from Stage 2a and expands it by pulling
each seed account's followers and following via the GitHub GraphQL API.
New accounts with Egypt-linked locations are collected and become the
frontier for the next round.

Runs up to 3 rounds, stopping early if a round finds no new accounts
(convergence).

Input: a CSV with a 'login' column (your cleaned Stage 2a output)
Output: egypt_snowball_candidates.csv with a 'round' column indicating
        which expansion round discovered each account.

Requires: pip install requests pandas
Set GITHUB_TOKEN as an environment variable first.
"""

import os
import time
import requests
import pandas as pd

GRAPHQL_URL = "https://api.github.com/graphql"
TOKEN       = os.environ.get("GITHUB_TOKEN")
HEADERS     = {"Authorization": f"Bearer {TOKEN}"}

MAX_ROUNDS               = 3
MAX_CONNECTIONS_PER_SEED = 100  # followers + following per account per round

# English and Arabic location terms — must match Stage 2a
LOCATION_TERMS = [
    "egypt", "cairo", "alexandria", "giza",
    "مصر", "القاهرة", "الإسكندرية", "الجيزة",
]


# ─────────────────────────────────────────────────────────────────────────────
# Network helpers
# ─────────────────────────────────────────────────────────────────────────────

def graphql_post(query: str, variables: dict, max_retries: int = 4) -> dict:
    """POST to the GraphQL endpoint with retry on network errors and 403."""
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                GRAPHQL_URL,
                headers=HEADERS,
                json={"query": query, "variables": variables},
                timeout=15,
            )
            if resp.status_code == 403:
                reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait  = max(reset - int(time.time()), 1) + 2
                print(f"    Rate limited. Sleeping {wait}s (resets at epoch {reset})...")
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                return {}
            data = resp.json()
            # GraphQL rate-limit errors come back as 200 with an error payload
            if "errors" in data:
                errs = data["errors"]
                if any(e.get("type") == "RATE_LIMITED" for e in errs):
                    print("    GraphQL rate limited. Sleeping 60s...")
                    time.sleep(60)
                    continue
            return data.get("data", {})
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            wait = 2 ** attempt
            print(f"    Network error ({type(e).__name__}), retry {attempt}/{max_retries} in {wait}s...")
            time.sleep(wait)
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# GraphQL: fetch followers + following in one query
# ─────────────────────────────────────────────────────────────────────────────

CONNECTIONS_QUERY = """
query($login: String!, $count: Int!) {
  user(login: $login) {
    followers(first: $count) {
      nodes { login name location bio }
    }
    following(first: $count) {
      nodes { login name location bio }
    }
  }
}
"""


def fetch_connections(login: str, max_connections: int = MAX_CONNECTIONS_PER_SEED):
    """Returns (followers_list, following_list) for a given login."""
    data = graphql_post(CONNECTIONS_QUERY, {"login": login, "count": max_connections})
    user = data.get("user")
    if not user:
        return [], []
    followers = (user.get("followers") or {}).get("nodes") or []
    following = (user.get("following") or {}).get("nodes") or []
    return followers, following


# ─────────────────────────────────────────────────────────────────────────────
# Location matching
# ─────────────────────────────────────────────────────────────────────────────

def location_matches_egypt(location_str) -> bool:
    if not location_str:
        return False
    loc_lower = location_str.lower()
    # Arabic terms are matched as-is (already lowercase-safe for Latin; Arabic is case-insensitive)
    return any(term.lower() in loc_lower for term in LOCATION_TERMS)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main(seed_csv_path: str = "egypt_seed_candidates.csv"):
    seeds = pd.read_csv(seed_csv_path)
    seed_logins = set(seeds["login"].astype(str))
    print(f"Loaded {len(seed_logins)} seed accounts from {seed_csv_path}")

    # `all_confirmed` tracks every account we've already catalogued so we
    # never re-add them in a later round.
    all_confirmed   = set(seed_logins)
    current_frontier = set(seed_logins)  # accounts to expand in this round

    all_discovered_rows = []

    for round_num in range(1, MAX_ROUNDS + 1):
        print(f"\n=== Snowball Round {round_num} (frontier: {len(current_frontier)} accounts) ===")
        new_this_round = {}

        for i, login in enumerate(current_frontier):
            print(f"  [{i+1}/{len(current_frontier)}] pulling connections for {login}...")
            followers, following = fetch_connections(login)

            for acct in followers + following:
                candidate_login = acct.get("login")
                if not candidate_login:
                    continue
                if candidate_login in all_confirmed:
                    continue  # already in our set
                if location_matches_egypt(acct.get("location")):
                    if candidate_login not in new_this_round:
                        new_this_round[candidate_login] = {
                            "login":           candidate_login,
                            "name":            acct.get("name"),
                            "location_raw":    acct.get("location"),
                            "bio":             acct.get("bio"),
                            "discovered_from": login,
                            "round":           round_num,
                        }

            time.sleep(0.5)

        if not new_this_round:
            print(f"  No new accounts found in round {round_num}. Converged early.")
            break

        print(f"  Round {round_num} complete: {len(new_this_round)} new Egypt-linked accounts.")
        all_discovered_rows.extend(new_this_round.values())

        # Next round's frontier = only the accounts just discovered
        all_confirmed.update(new_this_round.keys())
        current_frontier = set(new_this_round.keys())

    df = pd.DataFrame(all_discovered_rows) if all_discovered_rows else pd.DataFrame()
    df.to_csv("egypt_snowball_candidates.csv", index=False)

    print(f"\n─── Summary ─────────────────────────────────────────────")
    print(f"Seeds processed               : {len(seed_logins)}")
    print(f"New Egypt-linked accounts     : {len(df)}")
    if not df.empty and "round" in df.columns:
        print(f"By round:\n{df['round'].value_counts().sort_index().to_string()}")
    print(f"\nSaved to egypt_snowball_candidates.csv")
    print("NEXT: run combine_accounts.py, then Stage 2c on the combined list.")


if __name__ == "__main__":
    main()

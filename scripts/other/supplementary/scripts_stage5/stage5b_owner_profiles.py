#!/usr/bin/env python3
"""
Stage 5b — Egyptian Owner Profile Scan
========================================
Fetches GitHub profile data for the owners of the 136 Egyptian repos
and correlates developer characteristics with AI adoption.

Questions answered:
  - Do developers with more followers adopt AI more?
  - Do newer GitHub accounts adopt more than older ones?
  - Do more prolific developers (more repos) adopt more?
  - Do developers from companies/organisations adopt more than individuals?

INPUTS
------
  data/stage4/egypt_corpus_input_detected.csv  — Egyptian detection results

OUTPUTS
-------
  data/stage5/egypt_owner_profiles.csv         — raw profile data per owner
  data/stage5/egypt_owner_adoption_summary.csv — adoption rates by profile group

USAGE
-----
  export GITHUB_TOKEN=your_token_here
  python3 scripts/stage5/stage5b_owner_profiles.py
"""

import os
import sys
import time
import requests
import pandas as pd
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
DATA_DIR   = SCRIPT_DIR / "../../data"
EGYPT_CSV  = DATA_DIR / "stage4/egypt_corpus_input_detected.csv"
OUT_DIR    = DATA_DIR / "stage5"
PROFILES_CSV = OUT_DIR / "egypt_owner_profiles.csv"
SUMMARY_CSV  = OUT_DIR / "egypt_owner_adoption_summary.csv"

OUT_DIR.mkdir(parents=True, exist_ok=True)

TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    sys.exit("ERROR: GITHUB_TOKEN not set.")

GRAPHQL_URL = "https://api.github.com/graphql"
GQL_HEADERS = {"Authorization": f"Bearer {TOKEN}"}
BATCH_SIZE  = 10


# ── GraphQL ───────────────────────────────────────────────────────────────────

def build_profile_query(logins: list) -> str:
    frags = []
    for i, login in enumerate(logins):
        l = login.replace('"', "")
        frags.append(f"""
        u{i}: user(login: "{l}") {{
            login
            createdAt
            followers  {{ totalCount }}
            following  {{ totalCount }}
            repositories(isFork: false) {{ totalCount }}
            company
            location
            websiteUrl
            bio
            organizations(first: 5) {{
                nodes {{ name login }}
            }}
        }}
        """)
    return "{ rateLimit { remaining } " + " ".join(frags) + " }"


def graphql_post(query: str) -> dict:
    for attempt in range(1, 6):
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
        if r.status_code == 200:
            data = r.json()
            if any(e.get("type") == "RATE_LIMITED"
                   for e in data.get("errors", [])):
                time.sleep(60)
                continue
            return data.get("data") or {}
        time.sleep(2 ** attempt)
    return {}


# ── Profile fetch ─────────────────────────────────────────────────────────────

def fetch_profiles(logins: list) -> list:
    results = []
    print(f"Fetching profiles for {len(logins)} owners...")
    for start in range(0, len(logins), BATCH_SIZE):
        batch = logins[start: start + BATCH_SIZE]
        data  = graphql_post(build_profile_query(batch))
        for i, login in enumerate(batch):
            u = data.get(f"u{i}") or {}
            if not u:
                results.append({"login": login})
                continue
            orgs = [o.get("login", "") for o in
                    (u.get("organizations") or {}).get("nodes", [])]
            results.append({
                "login":        login,
                "created_at":   u.get("createdAt", ""),
                "followers":    (u.get("followers") or {}).get("totalCount", 0),
                "following":    (u.get("following") or {}).get("totalCount", 0),
                "public_repos": (u.get("repositories") or {}).get("totalCount", 0),
                "company":      (u.get("company") or "").strip(),
                "location":     u.get("location", ""),
                "has_website":  bool(u.get("websiteUrl")),
                "has_bio":      bool(u.get("bio")),
                "org_count":    len(orgs),
                "orgs":         "|".join(orgs),
            })
        print(f"  [{min(start + BATCH_SIZE, len(logins))}/{len(logins)}] done")
        time.sleep(0.5)
    return results


# ── Analysis helpers ──────────────────────────────────────────────────────────

def adoption_rate(series: pd.Series) -> float:
    return round(series.mean() * 100, 1)


def bucket_followers(n: int) -> str:
    if n == 0:    return "0"
    if n <= 10:   return "1–10"
    if n <= 50:   return "11–50"
    if n <= 200:  return "51–200"
    return "200+"


def bucket_repos(n: int) -> str:
    if n <= 5:    return "1–5"
    if n <= 20:   return "6–20"
    if n <= 50:   return "21–50"
    return "50+"


def account_age_bucket(created_at: str) -> str:
    if not created_at:
        return "unknown"
    try:
        year = int(created_at[:4])
        if year <= 2018:  return "before 2019"
        if year <= 2020:  return "2019–2020"
        if year <= 2022:  return "2021–2022"
        return "2023 or later"
    except Exception:
        return "unknown"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    egypt_df = pd.read_csv(EGYPT_CSV)
    for col in ["agent_adopted_multi"]:
        egypt_df[col] = egypt_df[col].map(
            lambda x: True if str(x).strip().lower() == "true" else False
        )

    logins = egypt_df["owner_login"].dropna().unique().tolist()
    print(f"Unique owners in Egyptian corpus: {len(logins)}")

    # Fetch (or load from cache)
    if PROFILES_CSV.exists():
        print(f"Profile cache found at {PROFILES_CSV.name} — loading.")
        profiles_df = pd.read_csv(PROFILES_CSV)
    else:
        profiles = fetch_profiles(logins)
        profiles_df = pd.DataFrame(profiles)
        profiles_df.to_csv(PROFILES_CSV, index=False)
        print(f"Profiles saved: {len(profiles_df)} owners → {PROFILES_CSV}")

    # Rename profiles created_at to avoid clash with repo created_at
    profiles_df = profiles_df.rename(columns={"created_at": "account_created_at"})

    # Merge with adoption data (one row per repo, keep owner profile)
    merged = egypt_df.merge(
        profiles_df,
        how="left",
        left_on="owner_login",
        right_on="login"
    )

    merged["follower_bucket"] = merged["followers"].fillna(0).astype(int).map(bucket_followers)
    merged["repos_bucket"]    = merged["public_repos"].fillna(0).astype(int).map(bucket_repos)
    merged["account_age"]     = merged["account_created_at"].fillna("").map(account_age_bucket)
    merged["has_company"]     = merged["company"].fillna("").map(lambda x: bool(x.strip()))

    rows = []

    print(f"\n{'─' * 55}")
    print("  Adoption rate by follower count")
    print(f"{'─' * 55}")
    order = ["0", "1–10", "11–50", "51–200", "200+"]
    for bucket in order:
        grp = merged[merged["follower_bucket"] == bucket]
        if len(grp) == 0:
            continue
        rate = adoption_rate(grp["agent_adopted_multi"])
        print(f"  {bucket:<10}  n={len(grp):<5}  adoption={rate}%")
        rows.append({"dimension": "followers", "group": bucket,
                     "n": len(grp), "adoption_%": rate})

    print(f"\n{'─' * 55}")
    print("  Adoption rate by account age")
    print(f"{'─' * 55}")
    for bucket in ["before 2019", "2019–2020", "2021–2022", "2023 or later", "unknown"]:
        grp = merged[merged["account_age"] == bucket]
        if len(grp) == 0:
            continue
        rate = adoption_rate(grp["agent_adopted_multi"])
        print(f"  {bucket:<18}  n={len(grp):<5}  adoption={rate}%")
        rows.append({"dimension": "account_age", "group": bucket,
                     "n": len(grp), "adoption_%": rate})

    print(f"\n{'─' * 55}")
    print("  Adoption rate by public repo count")
    print(f"{'─' * 55}")
    for bucket in ["1–5", "6–20", "21–50", "50+"]:
        grp = merged[merged["repos_bucket"] == bucket]
        if len(grp) == 0:
            continue
        rate = adoption_rate(grp["agent_adopted_multi"])
        print(f"  {bucket:<10}  n={len(grp):<5}  adoption={rate}%")
        rows.append({"dimension": "public_repos", "group": bucket,
                     "n": len(grp), "adoption_%": rate})

    print(f"\n{'─' * 55}")
    print("  Adoption rate: company-affiliated vs individual")
    print(f"{'─' * 55}")
    for label, mask in [("has company", merged["has_company"]),
                        ("no company",  ~merged["has_company"])]:
        grp  = merged[mask]
        rate = adoption_rate(grp["agent_adopted_multi"])
        print(f"  {label:<20}  n={len(grp):<5}  adoption={rate}%")
        rows.append({"dimension": "company", "group": label,
                     "n": len(grp), "adoption_%": rate})

    summary_df = pd.DataFrame(rows)
    summary_df.to_csv(SUMMARY_CSV, index=False)
    print(f"\nSummary saved → {SUMMARY_CSV}")


if __name__ == "__main__":
    main()

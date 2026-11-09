#!/usr/bin/env python3
"""
Stage 2 -- Inference Validation (Ground Truth Test)
=====================================================
Validates the deep inference pipeline (stage2b) by testing it on users
whose country is ALREADY KNOWN from their GitHub location field.

Method
------
1. Sample 50 users from owner_locations_all.csv where source='location_field'
   (stratified across top countries so the test is geographically diverse).
2. Fetch each user's full GitHub profile (bio, company, email, website,
   orgs, followers, following) — same query as stage2b.
3. Strip the location field from the profile (pretend we don't have it).
4. Run the stage2b infer_country() logic on the remaining signals only.
5. Compare inferred country vs known country and report accuracy.

This tells us: "If a user hadn't filled in their location field, would our
secondary signals (bio, company, email, org, network) still find them?"

Output
------
  data/stage2/validation_results.csv
    Columns: owner_login, known_country, inferred_country, match,
             signal_used, confidence, location_raw (original text)

  Printed summary: overall accuracy, per-signal accuracy, failures

Usage
-----
  export GITHUB_TOKEN=ghp_...
  python3 scripts/stage2/stage2_validate_inference.py [--sample N] [--seed S]
"""

import os, sys, time, json, argparse, requests
import pandas as pd
from pathlib import Path
from collections import Counter

ROOT    = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "stage2"
ALL_CSV = OUT_DIR / "owner_locations_all.csv"
OUT_CSV = OUT_DIR / "validation_results.csv"

TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    sys.exit("ERROR: GITHUB_TOKEN not set.")

HEADERS     = {"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"}
GRAPHQL_URL = "https://api.github.com/graphql"
SLEEP_OK    = 1.2
SLEEP_RETRY = 60

MIN_NETWORK_CONNECTIONS = 3
MIN_NETWORK_MAJORITY    = 0.40

# Countries to sample from (top countries to ensure diversity)
SAMPLE_COUNTRIES = [
    "India", "China", "United States", "Germany", "United Kingdom",
    "France", "Brazil", "Japan", "Canada", "Indonesia",
]

# ── Country lookup maps (copied from stage2b) ─────────────────────────────────

COUNTRY_MAP = {
    "egypt": "Egypt", "cairo": "Egypt", "alexandria": "Egypt",
    "giza": "Egypt", "مصر": "Egypt", "القاهرة": "Egypt",
    "الإسكندرية": "Egypt", "الجيزة": "Egypt",
    "nigeria": "Nigeria", "lagos": "Nigeria", "abuja": "Nigeria",
    "south africa": "South Africa", "johannesburg": "South Africa",
    "cape town": "South Africa", "kenya": "Kenya", "nairobi": "Kenya",
    "ghana": "Ghana", "accra": "Ghana", "ethiopia": "Ethiopia",
    "morocco": "Morocco", "casablanca": "Morocco",
    "tunisia": "Tunisia", "tunis": "Tunisia", "algeria": "Algeria",
    "senegal": "Senegal", "tanzania": "Tanzania", "uganda": "Uganda",
    "rwanda": "Rwanda", "zimbabwe": "Zimbabwe",
    "saudi arabia": "Saudi Arabia", "riyadh": "Saudi Arabia",
    "jeddah": "Saudi Arabia", "uae": "United Arab Emirates",
    "united arab emirates": "United Arab Emirates", "dubai": "United Arab Emirates",
    "abu dhabi": "United Arab Emirates", "qatar": "Qatar", "doha": "Qatar",
    "kuwait": "Kuwait", "bahrain": "Bahrain", "oman": "Oman",
    "jordan": "Jordan", "amman": "Jordan", "lebanon": "Lebanon",
    "beirut": "Lebanon", "iraq": "Iraq", "baghdad": "Iraq",
    "iran": "Iran", "tehran": "Iran", "israel": "Israel",
    "tel aviv": "Israel", "turkey": "Turkey", "istanbul": "Turkey",
    "ankara": "Turkey", "pakistan": "Pakistan", "karachi": "Pakistan",
    "lahore": "Pakistan", "islamabad": "Pakistan",
    "india": "India", "bangalore": "India", "bengaluru": "India",
    "mumbai": "India", "delhi": "India", "hyderabad": "India",
    "chennai": "India", "pune": "India", "kolkata": "India",
    "china": "China", "beijing": "China", "shanghai": "China",
    "shenzhen": "China", "guangzhou": "China",
    "japan": "Japan", "tokyo": "Japan", "osaka": "Japan",
    "south korea": "South Korea", "seoul": "South Korea",
    "indonesia": "Indonesia", "jakarta": "Indonesia",
    "vietnam": "Vietnam", "ho chi minh": "Vietnam", "hanoi": "Vietnam",
    "thailand": "Thailand", "bangkok": "Thailand",
    "malaysia": "Malaysia", "kuala lumpur": "Malaysia",
    "singapore": "Singapore", "philippines": "Philippines",
    "taiwan": "Taiwan", "taipei": "Taiwan",
    "bangladesh": "Bangladesh", "dhaka": "Bangladesh",
    "hong kong": "Hong Kong",
    "united kingdom": "United Kingdom", "uk": "United Kingdom",
    "england": "United Kingdom", "london": "United Kingdom",
    "scotland": "United Kingdom", "manchester": "United Kingdom",
    "germany": "Germany", "berlin": "Germany", "munich": "Germany",
    "hamburg": "Germany", "frankfurt": "Germany", "deutschland": "Germany",
    "france": "France", "paris": "France", "lyon": "France",
    "spain": "Spain", "madrid": "Spain", "barcelona": "Spain",
    "italy": "Italy", "rome": "Italy", "milan": "Italy",
    "netherlands": "Netherlands", "amsterdam": "Netherlands",
    "sweden": "Sweden", "stockholm": "Sweden",
    "norway": "Norway", "oslo": "Norway",
    "denmark": "Denmark", "copenhagen": "Denmark",
    "finland": "Finland", "helsinki": "Finland",
    "switzerland": "Switzerland", "zurich": "Switzerland",
    "austria": "Austria", "vienna": "Austria",
    "belgium": "Belgium", "brussels": "Belgium",
    "portugal": "Portugal", "lisbon": "Portugal",
    "poland": "Poland", "warsaw": "Poland",
    "ukraine": "Ukraine", "kyiv": "Ukraine",
    "russia": "Russia", "moscow": "Russia",
    "czech republic": "Czech Republic", "prague": "Czech Republic",
    "romania": "Romania", "bucharest": "Romania",
    "hungary": "Hungary", "budapest": "Hungary",
    "greece": "Greece", "athens": "Greece",
    "ireland": "Ireland", "dublin": "Ireland",
    "united states": "United States", "usa": "United States",
    "u.s.a": "United States", "u.s.": "United States",
    "new york": "United States", "san francisco": "United States",
    "los angeles": "United States", "seattle": "United States",
    "chicago": "United States", "boston": "United States",
    "austin": "United States", "denver": "United States",
    "washington": "United States",
    "canada": "Canada", "toronto": "Canada", "vancouver": "Canada",
    "montreal": "Canada", "ottawa": "Canada",
    "brazil": "Brazil", "são paulo": "Brazil", "sao paulo": "Brazil",
    "rio de janeiro": "Brazil", "brasilia": "Brazil",
    "mexico": "Mexico", "mexico city": "Mexico",
    "argentina": "Argentina", "buenos aires": "Argentina",
    "colombia": "Colombia", "bogota": "Colombia",
    "chile": "Chile", "santiago": "Chile",
    "peru": "Peru", "lima": "Peru",
    "australia": "Australia", "sydney": "Australia",
    "melbourne": "Australia", "brisbane": "Australia",
    "new zealand": "New Zealand", "auckland": "New Zealand",
}

TLD_MAP = {
    ".eg": "Egypt", ".ng": "Nigeria", ".za": "South Africa",
    ".ke": "Kenya", ".gh": "Ghana", ".et": "Ethiopia",
    ".ma": "Morocco", ".tn": "Tunisia", ".dz": "Algeria",
    ".sa": "Saudi Arabia", ".ae": "United Arab Emirates",
    ".qa": "Qatar", ".kw": "Kuwait", ".bh": "Bahrain",
    ".om": "Oman", ".jo": "Jordan", ".lb": "Lebanon",
    ".iq": "Iraq", ".ir": "Iran", ".il": "Israel",
    ".tr": "Turkey", ".pk": "Pakistan", ".in": "India",
    ".cn": "China", ".jp": "Japan", ".kr": "South Korea",
    ".id": "Indonesia", ".vn": "Vietnam", ".th": "Thailand",
    ".my": "Malaysia", ".sg": "Singapore", ".ph": "Philippines",
    ".tw": "Taiwan", ".bd": "Bangladesh", ".hk": "Hong Kong",
    ".gb": "United Kingdom", ".uk": "United Kingdom",
    ".de": "Germany", ".fr": "France", ".es": "Spain",
    ".it": "Italy", ".nl": "Netherlands", ".se": "Sweden",
    ".no": "Norway", ".dk": "Denmark", ".fi": "Finland",
    ".ch": "Switzerland", ".at": "Austria", ".be": "Belgium",
    ".pt": "Portugal", ".pl": "Poland", ".ua": "Ukraine",
    ".ru": "Russia", ".cz": "Czech Republic", ".ro": "Romania",
    ".hu": "Hungary", ".gr": "Greece", ".ie": "Ireland",
    ".us": "United States", ".ca": "Canada", ".br": "Brazil",
    ".mx": "Mexico", ".ar": "Argentina", ".co": "Colombia",
    ".cl": "Chile", ".pe": "Peru", ".au": "Australia",
    ".nz": "New Zealand",
}


def parse_country(text: str) -> str | None:
    if not text:
        return None
    t = text.lower().strip()
    for key in sorted(COUNTRY_MAP, key=len, reverse=True):
        if key in t:
            return COUNTRY_MAP[key]
    return None


def parse_tld(email_or_domain: str) -> str | None:
    if not email_or_domain:
        return None
    s = email_or_domain.lower().strip()
    for tld, country in TLD_MAP.items():
        if s.endswith(tld):
            return country
    return None


# ── GitHub API ─────────────────────────────────────────────────────────────────

PROFILE_QUERY = """
query($login: String!) {
  user(login: $login) {
    login
    location
    bio
    company
    email
    websiteUrl
    organizations(first: 10) {
      nodes { location }
    }
    followers(first: 30) {
      nodes { login location }
    }
    following(first: 30) {
      nodes { login location }
    }
  }
}
"""


def fetch_profile(login: str) -> dict:
    for attempt in range(5):
        try:
            resp = requests.post(
                GRAPHQL_URL,
                json={"query": PROFILE_QUERY, "variables": {"login": login}},
                headers=HEADERS,
                timeout=30,
            )
        except Exception as e:
            wait = 10 * (attempt + 1)
            print(f"  Network error ({e.__class__.__name__}), retry in {wait}s …")
            time.sleep(wait)
            continue
        if resp.status_code == 200:
            return (resp.json().get("data") or {}).get("user") or {}
        elif resp.status_code in (403, 429):
            print(f"  Rate limited. Sleeping {SLEEP_RETRY}s …")
            time.sleep(SLEEP_RETRY)
        else:
            time.sleep(5)
    return {}


# ── Inference logic (identical to stage2b, location field excluded) ────────────

def infer_without_location(profile: dict) -> tuple[str, str, str]:
    """
    Runs the stage2b inference signals in order, but deliberately skips the
    'location' field — simulating a user who didn't fill it in.
    Returns (inferred_country, confidence, signal_used).
    """
    # Signal 1: bio text
    bio = profile.get("bio") or ""
    c = parse_country(bio)
    if c:
        return c, "medium", "bio_text"

    # Signal 2: company field
    company = profile.get("company") or ""
    c = parse_country(company)
    if c:
        return c, "medium", "company_name"
    c = parse_tld(company)
    if c:
        return c, "medium", "company_domain"

    # Signal 3: email domain
    email = profile.get("email") or ""
    c = parse_tld(email)
    if c:
        return c, "medium", "email_tld"

    # Signal 4: website TLD
    website = profile.get("websiteUrl") or ""
    c = parse_tld(website)
    if c:
        return c, "low", "website_tld"

    # Signal 5: organisation locations
    orgs = profile.get("organizations", {}).get("nodes") or []
    for org in orgs:
        org_loc = org.get("location") or ""
        c = parse_country(org_loc)
        if c:
            return c, "medium", "org_location"

    # Signal 6: follower/following network majority
    connections = (
        (profile.get("followers", {}).get("nodes") or []) +
        (profile.get("following", {}).get("nodes") or [])
    )
    located = [parse_country(n.get("location") or "") for n in connections]
    located = [c for c in located if c]
    if len(located) >= MIN_NETWORK_CONNECTIONS:
        counts = Counter(located)
        top, n = counts.most_common(1)[0]
        if n / len(located) >= MIN_NETWORK_MAJORITY:
            return top, "low", "network_majority"

    return "not_specified", "none", "not_specified"


# ── Sampling ───────────────────────────────────────────────────────────────────

def build_sample(n_total: int, seed: int) -> pd.DataFrame:
    """
    Stratified sample: n_per_country from each of SAMPLE_COUNTRIES,
    fill remainder randomly from other countries.
    """
    df = pd.read_csv(ALL_CSV)
    known = df[(df["source"] == "location_field") &
               (df["inferred_country"] != "not_specified")].copy()

    n_per_country = max(1, n_total // len(SAMPLE_COUNTRIES))
    frames = []
    for country in SAMPLE_COUNTRIES:
        sub = known[known["inferred_country"] == country]
        take = min(n_per_country, len(sub))
        if take > 0:
            frames.append(sub.sample(take, random_state=seed))

    sample = pd.concat(frames, ignore_index=True)

    # Fill up to n_total with random others if needed
    remaining = n_total - len(sample)
    if remaining > 0:
        already = set(sample["owner_login"])
        rest = known[~known["owner_login"].isin(already)]
        extra = rest.sample(min(remaining, len(rest)), random_state=seed)
        sample = pd.concat([sample, extra], ignore_index=True)

    return sample.head(n_total)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=50,
                    help="Number of users to test (default: 50)")
    ap.add_argument("--seed",   type=int, default=42,
                    help="Random seed for reproducibility (default: 42)")
    args = ap.parse_args()

    print(f"Stage 2 Inference Validation — n={args.sample}, seed={args.seed}")
    print("=" * 60)

    sample = build_sample(args.sample, args.seed)
    print(f"Sample built: {len(sample)} users across {sample['inferred_country'].nunique()} countries\n")
    print("Country distribution in sample:")
    print(sample["inferred_country"].value_counts().to_string())
    print()

    records = []
    total = len(sample)

    for i, row in sample.iterrows():
        login        = row["owner_login"]
        known_country = row["inferred_country"]
        location_raw  = row["location_raw"]

        print(f"  [{len(records)+1:>2}/{total}] {login:<30} known={known_country}", end=" … ", flush=True)

        profile = fetch_profile(login)
        if not profile:
            print("SKIP (no profile)")
            records.append({
                "owner_login":      login,
                "known_country":    known_country,
                "location_raw":     location_raw,
                "inferred_country": "api_error",
                "signal_used":      "api_error",
                "confidence":       "none",
                "match":            False,
                "bio":              "",
                "company":          "",
                "email":            "",
                "website":          "",
            })
            time.sleep(SLEEP_OK)
            continue

        inferred, confidence, signal = infer_without_location(profile)
        match = (inferred == known_country)

        status = "✓ CORRECT" if match else (
            f"✗ GOT {inferred}" if inferred != "not_specified" else "— MISSED"
        )
        print(f"inferred={inferred:<20} signal={signal:<20} {status}")

        records.append({
            "owner_login":      login,
            "known_country":    known_country,
            "location_raw":     location_raw,
            "inferred_country": inferred,
            "signal_used":      signal,
            "confidence":       confidence,
            "match":            match,
            "bio":              (profile.get("bio") or "")[:150],
            "company":          profile.get("company") or "",
            "email":            profile.get("email") or "",
            "website":          profile.get("websiteUrl") or "",
        })

        time.sleep(SLEEP_OK)

    # Save results
    df_out = pd.DataFrame(records)
    df_out.to_csv(OUT_CSV, index=False)
    print(f"\nResults saved to: {OUT_CSV}\n")

    # ── Summary report ─────────────────────────────────────────────────────────
    valid   = df_out[df_out["inferred_country"] != "api_error"]
    n_valid = len(valid)
    if n_valid == 0:
        print("No valid results to summarise.")
        return

    correct = valid["match"].sum()
    wrong   = ((valid["inferred_country"] != "not_specified") & ~valid["match"]).sum()
    missed  = (valid["inferred_country"] == "not_specified").sum()

    predicted = correct + wrong   # users where pipeline made ANY prediction
    precision = correct / predicted * 100 if predicted > 0 else 0.0
    coverage  = predicted / n_valid * 100

    print("=" * 60)
    print(f"VALIDATION SUMMARY  (n={n_valid} users)")
    print("=" * 60)
    print(f"  Correct (inferred == known) : {correct:>3}  ({correct/n_valid*100:.1f}% of total)")
    print(f"  Wrong   (wrong country)     : {wrong:>3}  ({wrong/n_valid*100:.1f}% of total)")
    print(f"  Missed  (not_specified)     : {missed:>3}  ({missed/n_valid*100:.1f}% of total — not an error)")
    print()
    print("  ── Key metrics ──────────────────────────────────")
    print(f"  Coverage  (pipeline made a prediction)  : {predicted:>3}/{n_valid}  ({coverage:.1f}%)")
    print(f"  Precision (correct when predicted)      : {correct:>3}/{predicted}  ({precision:.1f}%)")
    print(f"  Wrong rate (of all predictions made)    : {wrong:>3}/{predicted}  ({wrong/predicted*100:.1f}% ← the real risk)")
    print()

    print("By signal type (correct / total tried):")
    for sig in valid[valid["inferred_country"] != "not_specified"]["signal_used"].unique():
        sub  = valid[valid["signal_used"] == sig]
        c    = sub["match"].sum()
        t    = len(sub)
        print(f"  {sig:<25} {c}/{t}  ({c/t*100:.0f}% accurate)")

    print()
    print("Wrong predictions only (these are the real errors):")
    wrong_df = valid[(valid["inferred_country"] != "not_specified") & ~valid["match"]]
    if wrong_df.empty:
        print("  None — no wrong predictions!")
    else:
        for _, r in wrong_df.iterrows():
            print(f"  {r['owner_login']:<28} known={r['known_country']:<20} "
                  f"inferred={r['inferred_country']:<20} signal={r['signal_used']}")

    print()
    print(f"PRECISION: {correct}/{predicted} = {precision:.1f}%  "
          f"| COVERAGE: {predicted}/{n_valid} = {coverage:.1f}%")


if __name__ == "__main__":
    main()

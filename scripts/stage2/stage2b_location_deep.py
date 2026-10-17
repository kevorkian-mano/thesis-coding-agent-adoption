#!/usr/bin/env python3
"""
Stage 2b -- Owner Location Deep Inference
==========================================
Runs on owners that stage2a could not locate (not_specified).
Applies additional profile signals to infer country:
  - Bio text: country keywords, regional language patterns
  - Company field: company name or domain TLD
  - Email domain: country-code TLD (.eg, .de, .fr, etc.)
  - Organisation affiliations: org location fields
  - Follower/following network: majority-country of located connections

Owners that remain unresolved after all signals are labelled not_specified
and reported as a limitation. No country is forced.

Output
------
data/stage2/owner_locations_deep.csv
  owner_login, location_raw, bio, company, email,
  inferred_country, confidence, source

data/stage2/owner_locations_all.csv
  Combined fast + deep results for all owners.
  This is the file used by downstream stages.

Usage
-----
  export GITHUB_TOKEN=ghp_...
  python3 scripts/stage2/stage2b_location_deep.py
"""

import os
import re
import time
import requests
import pandas as pd
from pathlib import Path
from collections import Counter

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parents[2]
OUT_DIR    = ROOT / "data" / "stage2"
FAST_FILE  = OUT_DIR / "owner_locations_fast.csv"
UNRES_FILE = OUT_DIR / "not_specified_owners.csv"
OUT_DEEP   = OUT_DIR / "owner_locations_deep.csv"
OUT_ALL    = OUT_DIR / "owner_locations_all.csv"

TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    raise SystemExit("Set GITHUB_TOKEN environment variable before running.")

HEADERS     = {"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"}
GRAPHQL_URL = "https://api.github.com/graphql"
BATCH_SIZE  = 10      # smaller batches — each query fetches bio, company, orgs, network
SLEEP_OK    = 1.2
SLEEP_RETRY = 60
MIN_NETWORK_CONNECTIONS = 3     # minimum located connections to trust network signal
MIN_NETWORK_MAJORITY   = 0.40   # fraction that must agree on same country

# ── reuse country map and parse_country from stage2a ──────────────────────────
# (imported inline to keep scripts self-contained)
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

# Country-code TLD to country name
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

# ── GraphQL query — fetch profile + orgs + connections ────────────────────────
PROFILE_QUERY = """
query($login: String!) {
  user(login: $login) {
    login
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
            print(f"  Network error ({e.__class__.__name__}), retry {attempt+1}/5 in {wait}s ...")
            time.sleep(wait)
            continue
        if resp.status_code == 200:
            return (resp.json().get("data") or {}).get("user") or {}
        elif resp.status_code in (403, 429):
            print(f"  Rate limited. Sleeping {SLEEP_RETRY}s ...")
            time.sleep(SLEEP_RETRY)
        else:
            time.sleep(5)
    return {}

# ── inference logic ────────────────────────────────────────────────────────────
def infer_country(profile: dict) -> tuple[str, str, str]:
    """
    Returns (inferred_country, confidence, source).
    Tries signals in order; stops at the first match.
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
        counts  = Counter(located)
        top, n  = counts.most_common(1)[0]
        if n / len(located) >= MIN_NETWORK_MAJORITY:
            return top, "low", "network_majority"

    return "not_specified", "none", "not_specified"

# ── main ──────────────────────────────────────────────────────────────────────
def main():
    print("Stage 2b -- Owner Location Deep Inference")
    print("=" * 50)

    if not UNRES_FILE.exists():
        raise SystemExit(f"Run stage2a first. Missing: {UNRES_FILE}")

    unres_logins = pd.read_csv(UNRES_FILE)["owner_login"].tolist()
    print(f"Owners to process: {len(unres_logins):,}")

    # Resume support
    if OUT_DEEP.exists():
        done = set(pd.read_csv(OUT_DEEP)["owner_login"].tolist())
        unres_logins = [l for l in unres_logins if l not in done]
        print(f"Resuming: {len(unres_logins):,} remaining")

    results = []
    total   = len(unres_logins)
    SAVE_EVERY = 200  # flush to disk every N owners

    for i, login in enumerate(unres_logins):
        profile = fetch_profile(login)
        country, confidence, source = infer_country(profile)

        results.append({
            "owner_login":      login,
            "location_raw":     profile.get("location") or "",
            "bio":              (profile.get("bio") or "")[:200],
            "company":          profile.get("company") or "",
            "email":            profile.get("email") or "",
            "inferred_country": country,
            "confidence":       confidence,
            "source":           source,
        })

        # Incremental save every SAVE_EVERY owners so crashes don't lose progress
        if (i + 1) % SAVE_EVERY == 0:
            chunk = pd.DataFrame(results)
            if OUT_DEEP.exists():
                existing = pd.read_csv(OUT_DEEP)
                chunk = pd.concat([existing, chunk], ignore_index=True)
            chunk.to_csv(OUT_DEEP, index=False)
            results = []  # clear buffer after saving
            labelled_so_far = (chunk["inferred_country"] != "not_specified").sum()
            print(f"  {i+1:>6,}/{total:,}  labelled so far (cumulative): {labelled_so_far:,}  [saved]")
        elif (i + 1) % 100 == 0:
            labelled = sum(1 for r in results if r["inferred_country"] != "not_specified")
            print(f"  {i+1:>6,}/{total:,}  newly labelled this run: {labelled:,}")

        time.sleep(SLEEP_OK)

    # Save any remaining results not yet flushed
    if results:
        new_df = pd.DataFrame(results)
        if OUT_DEEP.exists():
            existing = pd.read_csv(OUT_DEEP)
            new_df = pd.concat([existing, new_df], ignore_index=True)
        new_df.to_csv(OUT_DEEP, index=False)
    elif not OUT_DEEP.exists():
        pd.DataFrame(columns=["owner_login","location_raw","bio","company",
                               "email","inferred_country","confidence","source"]
                     ).to_csv(OUT_DEEP, index=False)

    # Merge fast + deep into combined file
    fast_df = pd.read_csv(FAST_FILE)
    # Only keep fast results that were labelled (not_specified ones are now superseded by deep)
    fast_labelled = fast_df[fast_df["inferred_country"] != "not_specified"][
        ["owner_login", "location_raw", "inferred_country", "confidence", "source"]
    ]
    deep_cols = ["owner_login", "location_raw", "inferred_country", "confidence", "source"]
    deep_slim = new_df[deep_cols]
    combined  = pd.concat([fast_labelled, deep_slim], ignore_index=True)
    combined.to_csv(OUT_ALL, index=False)

    # Summary
    total_all  = len(combined)
    labelled   = (combined["inferred_country"] != "not_specified").sum()
    unresolved = (combined["inferred_country"] == "not_specified").sum()

    print()
    print("=" * 50)
    print(f"All owners (fast + deep) : {total_all:,}")
    print(f"Country labelled         : {labelled:,}  ({labelled/total_all*100:.1f}%)")
    print(f"Still not specified      : {unresolved:,}  ({unresolved/total_all*100:.1f}%)")
    print()
    print("Top 25 countries:")
    top = (combined[combined["inferred_country"] != "not_specified"]
           .groupby("inferred_country").size()
           .sort_values(ascending=False).head(25))
    for country, count in top.items():
        print(f"  {country:<30} {count:>6,}")
    print()
    print(f"Saved: {OUT_DEEP}")
    print(f"Saved: {OUT_ALL}  (use this for downstream stages)")

if __name__ == "__main__":
    main()

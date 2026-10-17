#!/usr/bin/env python3
"""
Stage 2a -- Owner Location Fast Pass
======================================
Reads all unique repo owners from global_corpus.csv and fetches their
GitHub profile location field via GraphQL (50 owners per request).

For each owner the location string is parsed against a country lookup
table. If a country is recognised the owner is labelled with that country
at high confidence. If the field is empty or unrecognisable the owner is
labelled not_specified and will be passed to stage2b for deeper inference.

Output
------
data/stage2/owner_locations_fast.csv
  owner_login, location_raw, inferred_country, confidence, source

data/stage2/not_specified_owners.csv
  owner_login  (subset to pass to stage2b)

Usage
-----
  export GITHUB_TOKEN=ghp_...
  python3 scripts/stage2/stage2a_location_fast.py
"""

import os
import re
import time
import requests
import pandas as pd
from pathlib import Path

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).resolve().parents[2]
CORPUS    = ROOT / "data" / "stage1" / "global_corpus.csv"
OUT_DIR   = ROOT / "data" / "stage2"
OUT_FAST  = OUT_DIR / "owner_locations_fast.csv"
OUT_UNRES = OUT_DIR / "not_specified_owners.csv"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    raise SystemExit("Set GITHUB_TOKEN environment variable before running.")

HEADERS = {"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"}
GRAPHQL_URL = "https://api.github.com/graphql"
BATCH_SIZE  = 50       # owners per GraphQL request
SLEEP_OK    = 0.8      # seconds between requests (well within rate limit)
SLEEP_RETRY = 60       # seconds to wait on rate limit hit

# ── country lookup ─────────────────────────────────────────────────────────────
# Maps lowercase keywords found in location strings to a canonical country name.
# Ordered: more specific entries first (e.g. "new zealand" before "new").
COUNTRY_MAP = {
    # Africa
    "egypt": "Egypt", "cairo": "Egypt", "alexandria": "Egypt",
    "giza": "Egypt", "مصر": "Egypt", "القاهرة": "Egypt",
    "الإسكندرية": "Egypt", "الجيزة": "Egypt",
    "nigeria": "Nigeria", "lagos": "Nigeria", "abuja": "Nigeria",
    "south africa": "South Africa", "johannesburg": "South Africa",
    "cape town": "South Africa", "kenya": "Kenya", "nairobi": "Kenya",
    "ghana": "Ghana", "accra": "Ghana", "ethiopia": "Ethiopia",
    "addis ababa": "Ethiopia", "morocco": "Morocco", "casablanca": "Morocco",
    "tunisia": "Tunisia", "tunis": "Tunisia", "algeria": "Algeria",
    "senegal": "Senegal", "ivory coast": "Ivory Coast", "tanzania": "Tanzania",
    "uganda": "Uganda", "rwanda": "Rwanda", "zimbabwe": "Zimbabwe",

    # Middle East
    "saudi arabia": "Saudi Arabia", "riyadh": "Saudi Arabia",
    "jeddah": "Saudi Arabia", "uae": "United Arab Emirates",
    "united arab emirates": "United Arab Emirates", "dubai": "United Arab Emirates",
    "abu dhabi": "United Arab Emirates", "qatar": "Qatar", "doha": "Qatar",
    "kuwait": "Kuwait", "bahrain": "Bahrain", "oman": "Oman",
    "jordan": "Jordan", "amman": "Jordan", "lebanon": "Lebanon",
    "beirut": "Lebanon", "iraq": "Iraq", "baghdad": "Iraq",
    "iran": "Iran", "tehran": "Iran", "israel": "Israel",
    "tel aviv": "Israel", "jerusalem": "Israel", "turkey": "Turkey",
    "istanbul": "Turkey", "ankara": "Turkey", "syria": "Syria",
    "yemen": "Yemen", "pakistan": "Pakistan", "karachi": "Pakistan",
    "lahore": "Pakistan", "islamabad": "Pakistan",

    # Asia
    "india": "India", "bangalore": "India", "bengaluru": "India",
    "mumbai": "India", "delhi": "India", "hyderabad": "India",
    "chennai": "India", "pune": "India", "kolkata": "India",
    "china": "China", "beijing": "China", "shanghai": "China",
    "shenzhen": "China", "guangzhou": "China", "chengdu": "China",
    "japan": "Japan", "tokyo": "Japan", "osaka": "Japan",
    "south korea": "South Korea", "seoul": "South Korea",
    "indonesia": "Indonesia", "jakarta": "Indonesia",
    "vietnam": "Vietnam", "ho chi minh": "Vietnam", "hanoi": "Vietnam",
    "thailand": "Thailand", "bangkok": "Thailand",
    "malaysia": "Malaysia", "kuala lumpur": "Malaysia",
    "singapore": "Singapore", "philippines": "Philippines",
    "manila": "Philippines", "taiwan": "Taiwan", "taipei": "Taiwan",
    "bangladesh": "Bangladesh", "dhaka": "Bangladesh",
    "sri lanka": "Sri Lanka", "nepal": "Nepal", "myanmar": "Myanmar",
    "hong kong": "Hong Kong", "cambodia": "Cambodia",

    # Europe
    "united kingdom": "United Kingdom", "uk": "United Kingdom",
    "england": "United Kingdom", "london": "United Kingdom",
    "scotland": "United Kingdom", "wales": "United Kingdom",
    "manchester": "United Kingdom", "birmingham": "United Kingdom",
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
    "croatia": "Croatia", "serbia": "Serbia",
    "slovakia": "Slovakia", "bulgaria": "Bulgaria",
    "estonia": "Estonia", "latvia": "Latvia", "lithuania": "Lithuania",
    "luxembourg": "Luxembourg", "ireland": "Ireland", "dublin": "Ireland",

    # Americas
    "united states": "United States", "usa": "United States",
    "u.s.a": "United States", "u.s.": "United States",
    "new york": "United States", "san francisco": "United States",
    "los angeles": "United States", "seattle": "United States",
    "chicago": "United States", "boston": "United States",
    "austin": "United States", "denver": "United States",
    "san jose": "United States", "washington": "United States",
    "canada": "Canada", "toronto": "Canada", "vancouver": "Canada",
    "montreal": "Canada", "ottawa": "Canada",
    "brazil": "Brazil", "são paulo": "Brazil", "sao paulo": "Brazil",
    "rio de janeiro": "Brazil", "brasilia": "Brazil",
    "mexico": "Mexico", "mexico city": "Mexico",
    "argentina": "Argentina", "buenos aires": "Argentina",
    "colombia": "Colombia", "bogota": "Colombia",
    "chile": "Chile", "santiago": "Chile",
    "peru": "Peru", "lima": "Peru",
    "venezuela": "Venezuela",

    # Oceania
    "australia": "Australia", "sydney": "Australia",
    "melbourne": "Australia", "brisbane": "Australia",
    "new zealand": "New Zealand", "auckland": "New Zealand",
}

def parse_country(location_raw: str) -> str | None:
    """Return a canonical country name or None if unrecognised."""
    if not location_raw:
        return None
    loc = location_raw.lower().strip()
    # Exact and substring match — longest key first to avoid partial matches
    for key in sorted(COUNTRY_MAP, key=len, reverse=True):
        if key in loc:
            return COUNTRY_MAP[key]
    return None

# ── GraphQL query ──────────────────────────────────────────────────────────────
def build_query(logins: list[str]) -> str:
    aliases = "\n".join(
        f'  u{i}: user(login: "{login}") {{ login location }}'
        for i, login in enumerate(logins)
    )
    return f"{{ {aliases} }}"

def fetch_batch(logins: list[str]) -> dict:
    """Fetch location for a batch of logins. Returns {login: location_raw}."""
    query = build_query(logins)
    for attempt in range(3):
        resp = requests.post(GRAPHQL_URL, json={"query": query}, headers=HEADERS, timeout=30)
        if resp.status_code == 200:
            data = resp.json().get("data", {}) or {}
            result = {}
            for i, login in enumerate(logins):
                node = data.get(f"u{i}") or {}
                result[login] = node.get("location") or ""
            return result
        elif resp.status_code in (403, 429):
            print(f"  Rate limited. Sleeping {SLEEP_RETRY}s ...")
            time.sleep(SLEEP_RETRY)
        else:
            print(f"  HTTP {resp.status_code} on attempt {attempt+1}")
            time.sleep(5)
    return {login: "" for login in logins}

# ── main ──────────────────────────────────────────────────────────────────────
def main():
    print("Stage 2a -- Owner Location Fast Pass")
    print("=" * 50)

    df = pd.read_csv(CORPUS, low_memory=False)
    owners = df["owner_login"].dropna().unique().tolist()
    print(f"Unique owners to process: {len(owners):,}")

    # Resume support: skip already processed owners
    if OUT_FAST.exists():
        done = pd.read_csv(OUT_FAST)["owner_login"].tolist()
        owners = [o for o in owners if o not in done]
        print(f"Resuming: {len(owners):,} owners remaining")

    results = []
    total   = len(owners)

    for start in range(0, total, BATCH_SIZE):
        batch   = owners[start:start + BATCH_SIZE]
        fetched = fetch_batch(batch)

        for login, loc_raw in fetched.items():
            country = parse_country(loc_raw)
            if country:
                results.append({
                    "owner_login":      login,
                    "location_raw":     loc_raw,
                    "inferred_country": country,
                    "confidence":       "high",
                    "source":           "location_field",
                })
            else:
                results.append({
                    "owner_login":      login,
                    "location_raw":     loc_raw,
                    "inferred_country": "not_specified",
                    "confidence":       "none",
                    "source":           "not_specified",
                })

        if (start // BATCH_SIZE) % 20 == 0:
            done_count = start + len(batch)
            pct = done_count / total * 100
            labelled = sum(1 for r in results if r["inferred_country"] != "not_specified")
            print(f"  {done_count:>6,}/{total:,} ({pct:.1f}%)  labelled so far: {labelled:,}")

        time.sleep(SLEEP_OK)

    # Save full results (append if resuming)
    new_df = pd.DataFrame(results)
    if OUT_FAST.exists():
        existing = pd.read_csv(OUT_FAST)
        new_df = pd.concat([existing, new_df], ignore_index=True)

    new_df.to_csv(OUT_FAST, index=False)

    # Save not_specified subset for stage2b
    unres = new_df[new_df["inferred_country"] == "not_specified"][["owner_login"]]
    unres.to_csv(OUT_UNRES, index=False)

    # Summary
    total_processed = len(new_df)
    labelled   = (new_df["inferred_country"] != "not_specified").sum()
    unresolved = (new_df["inferred_country"] == "not_specified").sum()

    print()
    print("=" * 50)
    print(f"Total owners processed : {total_processed:,}")
    print(f"Country labelled       : {labelled:,} ({labelled/total_processed*100:.1f}%)")
    print(f"Not specified          : {unresolved:,} ({unresolved/total_processed*100:.1f}%)")
    print()
    print("Top 20 countries found:")
    top = (new_df[new_df["inferred_country"] != "not_specified"]
           .groupby("inferred_country").size()
           .sort_values(ascending=False).head(20))
    for country, count in top.items():
        print(f"  {country:<30} {count:>6,}")
    print()
    print(f"Saved: {OUT_FAST}")
    print(f"Saved: {OUT_UNRES} ({len(unres):,} owners for stage2b)")

if __name__ == "__main__":
    main()

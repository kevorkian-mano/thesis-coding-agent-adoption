#!/usr/bin/env python3
"""
Stage 2d -- Company / Org Membership Location Inference
========================================================
Runs on owners still not_specified after Stage 2c (~21,788 owners).

One GraphQL batch call per 10 owners fetches both the company field
and public org memberships (with location) simultaneously.

Pass 1 -- Company field → ROR API  (academic institutions only)
  Detect university/institute keywords in company field → query ROR
  Free, no auth, ~1 req/s
  Accept results with score ≥ 0.85

Pass 2 -- Org memberships → blocklist → Nominatim → majority vote
  Public org memberships (up to 10 per owner) via GraphQL
  Skip orgs on blocklist (multinationals + global OSS foundations)
  Geocode each org's location string via Nominatim (cached)
  Majority vote → assign country if ≥1 non-blocklisted org resolves

Input
-----
  data/stage2/owner_locations_all.csv   (not_specified rows → targets)

Output
------
  data/stage2/owner_locations_d.csv     -- stage2d results (all attempted)
  data/stage2/owner_locations_all.csv   -- UPDATED with newly resolved owners

Usage
-----
  export GITHUB_TOKEN=ghp_...
  python3 scripts/stage2/stage2d_company_orgs.py
"""
# ══════════════════════════════════════════════════════════════════════════════
# TEAM CONFIGURATION — edit the variables in this block before running
# ══════════════════════════════════════════════════════════════════════════════
#
# INPUT_CSV  : path to your Stage 1 corpus CSV
#              Required columns: full_name, owner_login, stars, commits,
#                                lang_bytes, created_at, primary_language
#              (replace with the equivalent columns in your stack's corpus)
#
# GITHUB_TOKEN: set via environment variable before running:
#   export GITHUB_TOKEN=ghp_...
#
# Outputs will be written to:  shared_methodology/data/stage2/
# ══════════════════════════════════════════════════════════════════════════════



import os
import re
import time
import requests
import pandas as pd
from pathlib import Path
from collections import Counter

ROOT     = Path(__file__).resolve().parents[2]
ALL_FILE = ROOT / "data" / "stage2" / "owner_locations_all.csv"
OUT_DIR  = ROOT / "data" / "stage2"
OUT_D    = OUT_DIR / "owner_locations_d.csv"

TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    raise SystemExit("Set GITHUB_TOKEN before running.")

GQL_HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type":  "application/json",
}
NOMINATIM_HEADERS = {
    "User-Agent": "thesis-location-inference/1.0 (github.com/kevorkian/me-thesis)"
}

GRAPHQL_URL   = "https://api.github.com/graphql"
ROR_URL       = "https://api.ror.org/v1/organizations"
GRAPHQL_BATCH = 10
SAVE_EVERY    = 500      # rows between checkpoint saves
ROR_SCORE_MIN = 0.85     # minimum ROR relevance score to accept

# ── Academic institution keywords (case-insensitive substring match) ──────────
ACADEMIC_KEYWORDS = [
    "university", "universidad", "universität", "université", "universidade",
    "universitá", "universitat", "universite", "polytechnic", "politecnico",
    "politécnico", "college", "institute of technology", "institute of",
    " institute", "school of", "faculty of", "academy", "académie",
    "hochschule", "national laboratory", "national lab", "research center",
    "research centre", "research institute", "iit ", "iit-", " iit",
    " mit", "mit ", "caltech", "eth ", "epfl", "inria", "cnrs",
    "tum", "rwth", "kth ", "ntnu", "dtu ", "delft", "sorbonne",
    "grandes écoles", "grande école",
]

def is_academic(company: str) -> bool:
    if not company or not company.strip():
        return False
    c = company.lower().strip()
    return any(kw in c for kw in ACADEMIC_KEYWORDS)


# ── Blocklist: multinationals + global OSS foundations ────────────────────────
# Org logins (lowercase) that should NOT be used as location signals.
BLOCKLIST: set[str] = {
    # Big tech — globally distributed employees
    "google", "microsoft", "amazon", "apple", "meta", "netflix", "uber",
    "airbnb", "twitter", "x", "linkedin", "salesforce", "oracle", "ibm",
    "intel", "nvidia", "amd", "qualcomm", "cisco", "vmware", "sap",
    "adobe", "spotify", "stripe", "paypal", "atlassian", "github",
    "gitlab", "jetbrains", "slack", "zoom", "dropbox", "mongodb",
    "elastic", "hashicorp", "docker", "datadog", "twilio", "cloudflare",
    "digitalocean", "heroku", "vercel", "netlify", "shopify", "square",
    "palantir", "snowflake", "databricks", "confluent", "grafana-labs",
    "influxdata", "redhat", "canonical", "suse", "arm", "broadcom",
    "huawei", "samsung", "sony", "toshiba", "hitachi", "fujitsu",
    "nec", "lg", "siemens", "bosch", "philips", "ericsson", "nokia",
    "accenture", "capgemini", "infosys", "tcs", "wipro", "hcl",
    # Global OSS foundations — location is org HQ not contributor location
    "apache", "linux", "mozilla", "cncf", "eclipse", "openstack",
    "python", "nodejs", "node", "rust-lang", "golang", "golang-org",
    "tensorflow", "pytorch", "huggingface", "openai", "anthropic",
    "deepmind", "kubernetes", "homebrew", "vim", "neovim", "emacs",
    "gnome", "kde", "freedesktop", "fsf", "eff", "w3c", "whatwg",
    "owasp", "ietf", "ieee", "iso", "lf-edge", "lfai", "lf-ai",
    "openjsf", "llvm", "clangd", "gcc", "llvmorg", "webkit",
}


# ── ISO 3166-1 alpha-2 → canonical country name ───────────────────────────────
ISO2_COUNTRY = {
    "af": "Afghanistan",   "al": "Albania",        "dz": "Algeria",
    "ar": "Argentina",     "am": "Armenia",         "au": "Australia",
    "at": "Austria",       "az": "Azerbaijan",      "bh": "Bahrain",
    "bd": "Bangladesh",    "be": "Belgium",         "bo": "Bolivia",
    "ba": "Bosnia",        "br": "Brazil",          "bg": "Bulgaria",
    "kh": "Cambodia",      "ca": "Canada",          "cl": "Chile",
    "cn": "China",         "co": "Colombia",        "hr": "Croatia",
    "cz": "Czech Republic","dk": "Denmark",         "ec": "Ecuador",
    "eg": "Egypt",         "et": "Ethiopia",        "fi": "Finland",
    "fr": "France",        "ge": "Georgia",         "de": "Germany",
    "gh": "Ghana",         "gr": "Greece",          "hk": "Hong Kong",
    "hu": "Hungary",       "in": "India",           "id": "Indonesia",
    "ir": "Iran",          "iq": "Iraq",            "ie": "Ireland",
    "il": "Israel",        "it": "Italy",           "jp": "Japan",
    "jo": "Jordan",        "kz": "Kazakhstan",      "ke": "Kenya",
    "kr": "South Korea",   "kw": "Kuwait",          "lb": "Lebanon",
    "ly": "Libya",         "lu": "Luxembourg",      "my": "Malaysia",
    "mx": "Mexico",        "ma": "Morocco",         "mm": "Myanmar",
    "np": "Nepal",         "nl": "Netherlands",     "nz": "New Zealand",
    "ng": "Nigeria",       "no": "Norway",          "om": "Oman",
    "pk": "Pakistan",      "ps": "Palestine",       "pe": "Peru",
    "ph": "Philippines",   "pl": "Poland",          "pt": "Portugal",
    "qa": "Qatar",         "ro": "Romania",         "ru": "Russia",
    "sa": "Saudi Arabia",  "sn": "Senegal",         "rs": "Serbia",
    "sg": "Singapore",     "sk": "Slovakia",        "za": "South Africa",
    "es": "Spain",         "lk": "Sri Lanka",       "se": "Sweden",
    "ch": "Switzerland",   "sy": "Syria",           "tw": "Taiwan",
    "tz": "Tanzania",      "th": "Thailand",        "tn": "Tunisia",
    "tr": "Turkey",        "ug": "Uganda",          "ua": "Ukraine",
    "ae": "United Arab Emirates",                   "gb": "United Kingdom",
    "us": "United States", "uy": "Uruguay",         "uz": "Uzbekistan",
    "ve": "Venezuela",     "vn": "Vietnam",         "ye": "Yemen",
    "zw": "Zimbabwe",      "rw": "Rwanda",
}


# ── Nominatim geocoding (cached) ───────────────────────────────────────────────
_nominatim_cache: dict[str, str | None] = {}

def nominatim_geocode(location_raw: str) -> str | None:
    if not location_raw or not location_raw.strip():
        return None
    key = location_raw.strip().lower()
    if key in _nominatim_cache:
        return _nominatim_cache[key]
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": location_raw.strip(), "format": "json",
                    "limit": 1, "addressdetails": 1},
            headers=NOMINATIM_HEADERS,
            timeout=10,
        )
        time.sleep(1.1)
        if r.status_code == 200 and r.json():
            address      = r.json()[0].get("address", {})
            country_code = address.get("country_code", "").lower()
            country      = ISO2_COUNTRY.get(country_code)
            if not country:
                country = address.get("country", "").strip() or None
            _nominatim_cache[key] = country
            return country
    except Exception as e:
        print(f"    [nominatim error] {location_raw!r}: {e}")
        time.sleep(2)
    _nominatim_cache[key] = None
    return None


# ── ROR API lookup (cached) ────────────────────────────────────────────────────
_ror_cache: dict[str, str | None] = {}

def ror_lookup(company: str) -> str | None:
    """
    Query ROR for a research/academic institution name.
    Returns canonical country name or None.
    Only accepts results with score ≥ ROR_SCORE_MIN to avoid false positives.
    """
    key = company.strip().lower()
    if key in _ror_cache:
        return _ror_cache[key]
    try:
        r = requests.get(
            ROR_URL,
            params={"query": company.strip()},
            timeout=10,
        )
        time.sleep(1.0)
        if r.status_code == 200:
            items = r.json().get("items", [])
            if items:
                top = items[0]
                score = top.get("score", 0)
                if score >= ROR_SCORE_MIN:
                    org          = top.get("organization", {})
                    country_info = org.get("country") or {}
                    code         = country_info.get("country_code", "").lower()
                    country      = ISO2_COUNTRY.get(code) or country_info.get("country_name", "").strip() or None
                    _ror_cache[key] = country
                    return country
    except Exception as e:
        print(f"    [ROR error] {company!r}: {e}")
        time.sleep(2)
    _ror_cache[key] = None
    return None


# ── GraphQL: fetch company + public org memberships ───────────────────────────
def build_user_query(batch: list[tuple[str, str]]) -> str:
    """batch: list of (alias, login). Returns GraphQL query string."""
    frags = []
    for alias, login in batch:
        # Escape any quotes in login (defensive)
        safe = login.replace('"', "")
        frags.append(f"""
  {alias}: user(login: "{safe}") {{
    company
    organizations(first: 10) {{
      nodes {{
        login
        location
      }}
    }}
  }}""")
    return "{ " + "\n".join(frags) + " }"


def run_graphql(query: str) -> dict:
    for attempt in range(3):
        try:
            r = requests.post(
                GRAPHQL_URL,
                json={"query": query},
                headers=GQL_HEADERS,
                timeout=30,
            )
            if r.status_code == 200:
                return r.json().get("data") or {}
            if r.status_code in (403, 429):
                reset = int(r.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait  = max(reset - int(time.time()), 1)
                print(f"    Rate limited. Sleeping {min(wait,120)}s ...")
                time.sleep(min(wait, 120))
            elif r.status_code in (502, 503):
                time.sleep(5 * (attempt + 1))
        except requests.RequestException:
            time.sleep(5 * (attempt + 1))
    return {}


# ── Checkpoint save ────────────────────────────────────────────────────────────
def _flush(rows: list[dict]) -> None:
    if not rows:
        return
    new_chunk = pd.DataFrame(rows)
    if OUT_D.exists() and OUT_D.stat().st_size > 0:
        try:
            existing  = pd.read_csv(OUT_D)
            new_chunk = pd.concat([existing, new_chunk], ignore_index=True)
        except Exception:
            pass
    new_chunk.to_csv(OUT_D, index=False)


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    print("Stage 2d -- Company / Org Membership Location Inference")
    print("=" * 60)

    all_df     = pd.read_csv(ALL_FILE)
    unresolved = all_df[all_df["inferred_country"] == "not_specified"]["owner_login"].tolist()

    # Resume support
    if OUT_D.exists() and OUT_D.stat().st_size > 0:
        try:
            done       = set(pd.read_csv(OUT_D)["owner_login"].tolist())
            unresolved = [o for o in unresolved if o not in done]
            print(f"Resuming. Remaining : {len(unresolved):,}")
        except Exception:
            print(f"Owners to process   : {len(unresolved):,}")
    else:
        print(f"Owners to process   : {len(unresolved):,}")

    total       = len(unresolved)
    results     = []
    p1_resolved = 0   # resolved by ROR
    p2_resolved = 0   # resolved by org majority

    gql_batches = [
        [(f"r{j}", unresolved[i + j])
         for j in range(min(GRAPHQL_BATCH, total - i))]
        for i in range(0, total, GRAPHQL_BATCH)
    ]

    print(f"GraphQL batches     : {len(gql_batches):,}  (size {GRAPHQL_BATCH})\n")

    for b_idx, batch in enumerate(gql_batches):
        query    = build_user_query(batch)
        gql_data = run_graphql(query)
        time.sleep(0.3)

        for alias, login in batch:
            user_data = gql_data.get(alias) or {}

            # Strip leading @ from company field (common on GitHub)
            company = (user_data.get("company") or "").strip().lstrip("@").strip()
            orgs    = ((user_data.get("organizations") or {})
                       .get("nodes") or [])

            resolved_country = None
            source           = ""

            # ── Pass 1: Company → ROR ─────────────────────────────────────────
            if company and is_academic(company):
                country = ror_lookup(company)
                if country:
                    resolved_country = country
                    source           = f"ror({company[:50]})"
                    p1_resolved     += 1

            # ── Pass 2: Org memberships → Nominatim → majority vote ───────────
            if not resolved_country:
                country_votes: list[str] = []
                for org in orgs:
                    org_login    = (org.get("login") or "").lower()
                    org_location = (org.get("location") or "").strip()

                    if org_login in BLOCKLIST:
                        continue
                    if not org_location:
                        continue

                    c = nominatim_geocode(org_location)
                    if c:
                        country_votes.append(c)

                if country_votes:
                    top_country, top_count = Counter(country_votes).most_common(1)[0]
                    resolved_country = top_country
                    source           = f"org_majority({top_count}/{len(country_votes)})"
                    p2_resolved     += 1

            results.append({
                "owner_login":      login,
                "inferred_country": resolved_country or "not_specified",
                "confidence":       "medium" if resolved_country else "none",
                "source":           source or "not_specified",
            })

        owners_done = min((b_idx + 1) * GRAPHQL_BATCH, total)
        if (b_idx + 1) % 20 == 0:
            pct          = owners_done / total * 100
            nom_hits     = sum(1 for v in _nominatim_cache.values() if v)
            nom_total    = len(_nominatim_cache)
            print(f"  [{owners_done:>7,}/{total:,}] {pct:5.1f}%  "
                  f"ROR: {p1_resolved:,}  orgs: {p2_resolved:,}  "
                  f"total resolved: {p1_resolved + p2_resolved:,}  "
                  f"nom cache: {nom_hits}/{nom_total}")

        if (b_idx + 1) % (SAVE_EVERY // GRAPHQL_BATCH) == 0:
            _flush(results)
            results = []
            pct = owners_done / total * 100
            print(f"    [checkpoint saved at {owners_done:,}/{total:,} ({pct:.1f}%)  "
                  f"ROR: {p1_resolved:,}  orgs: {p2_resolved:,}  "
                  f"total: {p1_resolved + p2_resolved:,}]")

    # Final flush
    if results:
        _flush(results)

    # ── Update owner_locations_all.csv ────────────────────────────────────────
    d_df         = pd.read_csv(OUT_D)
    new_resolved = d_df[d_df["inferred_country"] != "not_specified"][
        ["owner_login", "inferred_country", "confidence", "source"]
    ].copy()
    new_resolved["location_raw"] = ""

    all_updated  = all_df[~all_df["owner_login"].isin(new_resolved["owner_login"])]
    all_updated  = pd.concat([all_updated, new_resolved], ignore_index=True)
    all_updated.to_csv(ALL_FILE, index=False)

    # ── Summary ───────────────────────────────────────────────────────────────
    total_resolved = (d_df["inferred_country"] != "not_specified").sum()
    total_all      = len(all_updated)
    labelled       = (all_updated["inferred_country"] != "not_specified").sum()

    print(f"\n{'=' * 60}")
    print(f"Owners attempted    : {len(d_df):,}")
    print(f"Resolved by ROR     : {p1_resolved:,}")
    print(f"Resolved by orgs    : {p2_resolved:,}")
    print(f"Total resolved      : {total_resolved:,}  "
          f"({total_resolved / max(len(d_df), 1) * 100:.1f}%)")
    print(f"\nUpdated owner_locations_all.csv:")
    print(f"  Total owners      : {total_all:,}")
    print(f"  Located           : {labelled:,}  ({labelled/total_all*100:.1f}%)")
    print(f"  Not specified     : {total_all - labelled:,}  "
          f"({(total_all - labelled)/total_all*100:.1f}%)")

    print("\nTop 20 newly resolved countries:")
    top = (d_df[d_df["inferred_country"] != "not_specified"]
           .groupby("inferred_country").size()
           .sort_values(ascending=False).head(20))
    for country, count in top.items():
        print(f"  {country:<30} {count:>6,}")

    print(f"\nSaved  : {OUT_D}")
    print(f"Updated: {ALL_FILE}")
    print("\nStage 2d complete.")


if __name__ == "__main__":
    main()

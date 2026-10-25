#!/usr/bin/env python3
"""
Stage 2c -- Nominatim Geocoding + Commit Timezone + Commit Messages + README
=============================================================================
Runs on owners still labelled not_specified after stage2b.
Applies FOUR signals in order — stops as soon as one resolves.

  Signal 0 -- Nominatim / OpenStreetMap geocoding           [FREE, no auth]
    Many owners DID fill in a location string in stage2a but our keyword
    map failed to recognise it (e.g. "Cascais", "Antwerp", "Dalian",
    "Guadalajara", "Göteborg"). Nominatim resolves any city/region string
    to a country via the OpenStreetMap database.
      GET https://nominatim.openstreetmap.org/search?q=<location_raw>
    Only called for owners whose location_raw is non-empty.
    Rate-limited to 1 req/s per Nominatim's usage policy.
    Results cached in memory — same string is never queried twice.

  Signal 1 -- Commit timezone offset                        [1 GitHub API call]
    Fetches 20 recent commits from the owner's most-starred corpus repo.
    Extracts UTC offset from author.date (e.g. "+05:30").
    Highly distinctive offsets resolve directly:
      +05:30 → India    +05:45 → Nepal    +06:30 → Myanmar
      +03:30 → Iran     +09:30 → Australia +04:30 → Afghanistan

  Signal 2 -- Commit message script detection               [FREE — same call]
    The same 20 commits contain commit message text at no extra cost.
    Non-Latin scripts in messages reveal the developer's native language:
    Korean → South Korea, Hiragana → Japan, Arabic+TZ → Arab country,
    Persian chars → Iran, Devanagari → India, Thai → Thailand,
    Hebrew → Israel, Bengali → Bangladesh, Cyrillic → Russia/Ukraine,
    CJK → Chinese-speaking region.

  Signal 3 -- README script detection                       [1 API call only
    Same Unicode detection on the repo README.               if still needed]

Resolution order
----------------
  0. Nominatim resolves location_raw   → done (0 GitHub calls)
  1. Unique timezone                   → done (1 GitHub call)
  2. Ambiguous TZ + commit script      → done (1 GitHub call)
  3. Commit script alone               → done (1 GitHub call)
  4. Ambiguous TZ + README script      → done (2 GitHub calls)
  5. README script alone               → done (2 GitHub calls)
  6. Nothing resolves                  → not_specified

Input
-----
  data/stage2/owner_locations_all.csv      (keep only not_specified rows)
  data/stage2/owner_locations_fast.csv     (location_raw strings from stage2a)
  data/stage1/global_corpus.csv            (to find each owner's repos)

Output
------
  data/stage2/owner_locations_c.csv        -- stage2c results (all attempted)
  data/stage2/owner_locations_all.csv      -- UPDATED with newly resolved owners

Usage
-----
  export GITHUB_TOKEN=ghp_...
  python3 scripts/stage2/stage2c_timezone_readme.py
"""

import os
import re
import time
import base64
import requests
import pandas as pd
from pathlib import Path
from collections import Counter

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parents[2]
CORPUS     = ROOT / "data" / "stage1" / "global_corpus.csv"
ALL_FILE   = ROOT / "data" / "stage2" / "owner_locations_all.csv"
FAST_FILE  = ROOT / "data" / "stage2" / "owner_locations_fast.csv"
OUT_DIR    = ROOT / "data" / "stage2"
OUT_C      = OUT_DIR / "owner_locations_c.csv"

TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    raise SystemExit("Set GITHUB_TOKEN before running.")

HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept":        "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# Nominatim requires a descriptive User-Agent per usage policy
NOMINATIM_HEADERS = {
    "User-Agent": "thesis-location-inference/1.0 (github.com/kevorkian/me-thesis)"
}

SLEEP_OK         = 0.3    # seconds between GraphQL requests
SLEEP_LIMIT      = 60     # seconds to wait on rate-limit hit
COMMITS_PER_REPO = 20
GRAPHQL_BATCH    = 10     # owners per GraphQL request
SAVE_EVERY       = 300

GRAPHQL_URL = "https://api.github.com/graphql"
GQL_HEADERS = {
    "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN', '')}",
    "Content-Type":  "application/json",
}

# ── Timezone offset → country mapping ─────────────────────────────────────────
# Each value is either a string (unambiguous) or a list (needs script to resolve).
TIMEZONE_COUNTRY: dict[str, str | list[str]] = {
    # Unique / near-unique offsets
    "+05:30": "India",
    "+0530":  "India",
    "+05:45": "Nepal",
    "+0545":  "Nepal",
    "+06:30": "Myanmar",
    "+0630":  "Myanmar",
    "+03:30": "Iran",
    "+0330":  "Iran",
    "+04:30": "Afghanistan",
    "+0430":  "Afghanistan",
    "+09:30": "Australia",
    "+0930":  "Australia",
    "+12:45": "New Zealand",   # Chatham Islands
    "+1245":  "New Zealand",
    # Ambiguous — script will disambiguate
    "+09:00": ["Japan", "South Korea"],
    "+0900":  ["Japan", "South Korea"],
    "+08:00": ["China", "Taiwan", "Singapore", "Malaysia", "Philippines", "Hong Kong"],
    "+0800":  ["China", "Taiwan", "Singapore", "Malaysia", "Philippines", "Hong Kong"],
    "+07:00": ["Thailand", "Vietnam", "Indonesia"],
    "+0700":  ["Thailand", "Vietnam", "Indonesia"],
    "+06:00": ["Bangladesh", "Kazakhstan"],
    "+0600":  ["Bangladesh", "Kazakhstan"],
    "+05:00": ["Pakistan", "Uzbekistan"],
    "+0500":  ["Pakistan", "Uzbekistan"],
    "+04:00": ["United Arab Emirates", "Oman", "Azerbaijan"],
    "+0400":  ["United Arab Emirates", "Oman", "Azerbaijan"],
    "+03:00": ["Saudi Arabia", "Iraq", "Kenya", "Ethiopia", "Russia"],
    "+0300":  ["Saudi Arabia", "Iraq", "Kenya", "Ethiopia", "Russia"],
    "+02:00": ["Israel", "Egypt", "South Africa", "Ukraine", "Romania", "Greece"],
    "+0200":  ["Israel", "Egypt", "South Africa", "Ukraine", "Romania", "Greece"],
    "+01:00": ["Nigeria", "Algeria", "Morocco", "Tunisia"],
    "+0100":  ["Nigeria", "Algeria", "Morocco", "Tunisia"],
    "-03:00": ["Brazil", "Argentina"],
    "-0300":  ["Brazil", "Argentina"],
    "-04:00": ["Chile", "Venezuela", "Bolivia"],
    "-0400":  ["Chile", "Venezuela", "Bolivia"],
    "-05:00": ["United States", "Colombia", "Peru", "Ecuador"],
    "-0500":  ["United States", "Colombia", "Peru", "Ecuador"],
    "-06:00": ["United States", "Mexico"],
    "-0600":  ["United States", "Mexico"],
    "-07:00": ["United States", "Canada"],
    "-0700":  ["United States", "Canada"],
    "-08:00": ["United States", "Canada"],
    "-0800":  ["United States", "Canada"],
    "+10:00": ["Australia"],
    "+1000":  ["Australia"],
    "+12:00": ["New Zealand"],
    "+1200":  ["New Zealand"],
    "+11:00": ["Australia"],
    "+1100":  ["Australia"],
    "+00:00": ["United Kingdom", "Ireland", "Portugal", "Ghana", "Senegal"],
    "+0000":  ["United Kingdom", "Ireland", "Portugal", "Ghana", "Senegal"],
}

# ── Script → country mapping (Unicode range detection) ────────────────────────
# Order matters: more specific scripts first.
# Returns (country, confidence) or (None, None)
def detect_script(text: str) -> tuple[str | None, str]:
    """
    Counts characters in Unicode script ranges.
    Returns the most strongly detected country, or None.
    """
    if not text:
        return None, "none"

    counts: dict[str, int] = {}

    # Hangul (Korean) — unique to South Korea
    counts["Korean"]   = len(re.findall(r"[\uAC00-\uD7AF\u1100-\u11FF\u3130-\u318F]", text))
    # Hiragana / Katakana — unique to Japanese
    counts["Japanese"] = len(re.findall(r"[\u3040-\u30FF]", text))
    # CJK Unified Ideographs (shared by Chinese/Japanese/Korean) — use AFTER JP/KR check
    counts["CJK"]      = len(re.findall(r"[\u4E00-\u9FFF\u3400-\u4DBF]", text))
    # Arabic script (Arabic + Persian/Farsi share this range)
    counts["Arabic"]   = len(re.findall(r"[\u0600-\u06FF\u0750-\u077F]", text))
    # Persian-specific characters (letters only in Farsi, not in Arabic)
    counts["Persian"]  = len(re.findall(r"[\u06A9\u06AF\u06CC\u06F0-\u06F9\u0686\u0698]", text))
    # Devanagari (Hindi)
    counts["Hindi"]    = len(re.findall(r"[\u0900-\u097F]", text))
    # Thai
    counts["Thai"]     = len(re.findall(r"[\u0E00-\u0E7F]", text))
    # Cyrillic
    counts["Cyrillic"] = len(re.findall(r"[\u0400-\u04FF]", text))
    # Hebrew
    counts["Hebrew"]   = len(re.findall(r"[\u0590-\u05FF]", text))
    # Bengali
    counts["Bengali"]  = len(re.findall(r"[\u0980-\u09FF]", text))
    # Ethiopic (Amharic)
    counts["Ethiopic"] = len(re.findall(r"[\u1200-\u137F]", text))
    # Armenian
    counts["Armenian"] = len(re.findall(r"[\u0530-\u058F]", text))
    # Vietnamese — mostly Latin but with specific combining marks
    counts["Vietnamese"] = len(re.findall(r"[\u1EA0-\u1EF9]", text))

    THRESHOLD = 30  # minimum characters to be confident

    # Korean takes priority over generic CJK
    if counts["Korean"] >= THRESHOLD:
        return "South Korea", "medium"
    # Japanese (hiragana/katakana) takes priority over CJK
    if counts["Japanese"] >= THRESHOLD:
        return "Japan", "medium"
    # Persian-specific chars inside Arabic script → Iran
    if counts["Persian"] >= 5 and counts["Arabic"] >= THRESHOLD:
        return "Iran", "medium"
    if counts["Arabic"] >= THRESHOLD:
        return None, "arabic_region"   # need TZ to pick country
    if counts["Hindi"] >= THRESHOLD:
        return "India", "medium"
    if counts["Thai"] >= THRESHOLD:
        return "Thailand", "medium"
    if counts["Hebrew"] >= THRESHOLD:
        return "Israel", "medium"
    if counts["Bengali"] >= THRESHOLD:
        return "Bangladesh", "medium"
    if counts["Ethiopic"] >= THRESHOLD:
        return "Ethiopia", "medium"
    if counts["Armenian"] >= THRESHOLD:
        return "Armenia", "medium"
    if counts["Vietnamese"] >= THRESHOLD:
        return "Vietnam", "medium"
    if counts["Cyrillic"] >= THRESHOLD:
        return None, "cyrillic_region"  # need TZ: Russia vs Ukraine
    # Generic CJK without JP/KR markers → Chinese-speaking
    if counts["CJK"] >= THRESHOLD:
        return None, "cjk_region"      # need TZ to disambiguate China vs TW vs SG

    return None, "none"


def resolve_combined(tz_candidates: list[str] | None,
                     script_country: str | None,
                     script_note: str) -> tuple[str, str, str]:
    """
    Combine timezone candidates and script signal into a final assignment.
    Returns (country, confidence, source).
    """
    # Case 1: No timezone data, script gives a country
    if not tz_candidates and script_country:
        return script_country, "medium", "readme_script"

    # Case 2: Ambiguous timezone, script picks one
    if tz_candidates and script_country:
        if script_country in tz_candidates:
            return script_country, "medium", "timezone+script"
        # Script points elsewhere — prefer script (more specific)
        return script_country, "low", "script_override"

    # Case 3: Ambiguous timezone + Arabic script → pick first Arab candidate
    if tz_candidates and script_note == "arabic_region":
        arab = [c for c in tz_candidates if c in
                {"Saudi Arabia", "Iraq", "Jordan", "Egypt", "Algeria",
                 "Morocco", "Tunisia", "Kuwait", "Bahrain", "Oman",
                 "Lebanon", "Libya", "Sudan", "Syria", "Yemen"}]
        if arab:
            return arab[0], "low", "timezone+arabic_script"

    # Case 4: Ambiguous timezone + Cyrillic → Russia vs Ukraine
    if tz_candidates and script_note == "cyrillic_region":
        cyr = [c for c in tz_candidates if c in {"Russia", "Ukraine"}]
        if cyr:
            return cyr[0], "low", "timezone+cyrillic"

    # Case 5: Ambiguous timezone + CJK (Chinese) → pick most likely from TZ
    if tz_candidates and script_note == "cjk_region":
        cjk_priority = ["China", "Taiwan", "Singapore",
                         "Malaysia", "Hong Kong", "Philippines"]
        for c in cjk_priority:
            if c in tz_candidates:
                return c, "low", "timezone+cjk_script"

    # Case 6: Single timezone candidate
    if tz_candidates and len(tz_candidates) == 1:
        return tz_candidates[0], "medium", "timezone_only"

    return "not_specified", "none", "not_specified"


# ── ISO 3166-1 alpha-2 → canonical country name ───────────────────────────────
# Nominatim always returns country_code in ASCII regardless of UI language.
ISO2_COUNTRY = {
    "af": "Afghanistan",   "al": "Albania",      "dz": "Algeria",
    "ar": "Argentina",     "am": "Armenia",       "au": "Australia",
    "at": "Austria",       "az": "Azerbaijan",    "bh": "Bahrain",
    "bd": "Bangladesh",    "be": "Belgium",       "bo": "Bolivia",
    "ba": "Bosnia",        "br": "Brazil",        "bg": "Bulgaria",
    "kh": "Cambodia",      "ca": "Canada",        "cl": "Chile",
    "cn": "China",         "co": "Colombia",      "hr": "Croatia",
    "cz": "Czech Republic","dk": "Denmark",       "ec": "Ecuador",
    "eg": "Egypt",         "et": "Ethiopia",      "fi": "Finland",
    "fr": "France",        "ge": "Georgia",       "de": "Germany",
    "gh": "Ghana",         "gr": "Greece",        "hk": "Hong Kong",
    "hu": "Hungary",       "in": "India",         "id": "Indonesia",
    "ir": "Iran",          "iq": "Iraq",          "ie": "Ireland",
    "il": "Israel",        "it": "Italy",         "jp": "Japan",
    "jo": "Jordan",        "kz": "Kazakhstan",    "ke": "Kenya",
    "kr": "South Korea",   "kw": "Kuwait",        "lb": "Lebanon",
    "ly": "Libya",         "lu": "Luxembourg",    "my": "Malaysia",
    "mx": "Mexico",        "ma": "Morocco",       "mm": "Myanmar",
    "np": "Nepal",         "nl": "Netherlands",   "nz": "New Zealand",
    "ng": "Nigeria",       "no": "Norway",        "om": "Oman",
    "pk": "Pakistan",      "ps": "Palestine",     "pe": "Peru",
    "ph": "Philippines",   "pl": "Poland",        "pt": "Portugal",
    "qa": "Qatar",         "ro": "Romania",       "ru": "Russia",
    "sa": "Saudi Arabia",  "sn": "Senegal",       "rs": "Serbia",
    "sg": "Singapore",     "sk": "Slovakia",      "za": "South Africa",
    "es": "Spain",         "lk": "Sri Lanka",     "se": "Sweden",
    "ch": "Switzerland",   "sy": "Syria",         "tw": "Taiwan",
    "tz": "Tanzania",      "th": "Thailand",      "tn": "Tunisia",
    "tr": "Turkey",        "ug": "Uganda",        "ua": "Ukraine",
    "ae": "United Arab Emirates", "gb": "United Kingdom",
    "us": "United States", "uy": "Uruguay",       "uz": "Uzbekistan",
    "ve": "Venezuela",     "vn": "Vietnam",       "ye": "Yemen",
    "zw": "Zimbabwe",      "dz": "Algeria",       "rw": "Rwanda",
}

# ── Nominatim geocoding (Signal 0) ────────────────────────────────────────────
_nominatim_cache: dict[str, str | None] = {}   # location_raw → country or None

def nominatim_geocode(location_raw: str) -> str | None:
    """
    Query Nominatim to resolve an unrecognised location string to a country.
    Returns canonical country name or None.
    Caches results — each unique string is only queried once.
    Rate-limited to 1 req/s per Nominatim's usage policy.
    """
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
        time.sleep(1.1)   # Nominatim: max 1 req/s
        if r.status_code == 200 and r.json():
            hit          = r.json()[0]
            address      = hit.get("address", {})
            # country_code is always ASCII (ISO 3166-1 alpha-2) — language independent
            country_code = address.get("country_code", "").lower()
            country      = ISO2_COUNTRY.get(country_code)
            # Fallback: use Nominatim's display_name country portion
            if not country:
                country_raw = address.get("country", "")
                if country_raw:
                    country = country_raw.strip()
            _nominatim_cache[key] = country
            return country
    except Exception as e:
        print(f"    [nominatim error] {location_raw!r}: {e}")
        time.sleep(2)

    _nominatim_cache[key] = None
    return None


# ── GraphQL batch commit fetch (Signals 1 + 2) ───────────────────────────────
def _build_commits_query(batch: list[tuple[str, str, str]]) -> str:
    """
    batch: list of (alias, owner, repo)
    Returns a GraphQL query fetching last COMMITS_PER_REPO commits per repo.
    GitTimestamp preserves the original timezone offset — unlike REST DateTime.
    """
    frags = []
    for alias, owner, repo in batch:
        frags.append(f"""
  {alias}: repository(owner: "{owner}", name: "{repo}") {{
    defaultBranchRef {{
      target {{
        ... on Commit {{
          history(first: {COMMITS_PER_REPO}) {{
            nodes {{
              author {{ user {{ login }} date }}
              message
            }}
          }}
        }}
      }}
    }}
  }}""")
    return "{ " + "\n".join(frags) + " }"


def run_graphql_commits(batch: list[tuple[str, str, str]]) -> dict:
    """
    Run one GraphQL request for a batch of (alias, owner, repo) tuples.
    Returns raw GraphQL data dict (partial results kept even if some repos error).
    """
    query = _build_commits_query(batch)
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


def parse_commit_data(repo_data: dict, owner_login: str) -> tuple[str | None, str]:
    """
    Extract (modal_tz_offset, commit_messages) from a single repo's GraphQL data.
    Filters to commits authored by owner_login.
    GitTimestamp format: "2025-04-15T09:30:00+08:00" — offset preserved.
    """
    tz_re    = re.compile(r"([+-]\d{2}:\d{2})$")
    offsets  = []
    messages = []

    history = (
        ((repo_data.get("defaultBranchRef") or {})
         .get("target") or {})
        .get("history") or {}
    ).get("nodes") or []

    for node in history:
        author = node.get("author") or {}
        # Filter to this owner's commits only
        user_login = ((author.get("user") or {}).get("login") or "").lower()
        if user_login and user_login != owner_login.lower():
            continue
        # Timezone from GitTimestamp
        date_str = author.get("date") or ""
        m = tz_re.search(date_str)
        if m:
            offsets.append(m.group(1))
        # Commit message
        msg = node.get("message") or ""
        if msg:
            messages.append(msg)

    tz = Counter(offsets).most_common(1)[0][0] if offsets else None
    return tz, "\n".join(messages)


# ── REST README fetch (Signal 3) ──────────────────────────────────────────────
def fetch_readme_text(owner: str, repo: str) -> str:
    """Fetch README via REST (handles case-insensitive filename automatically)."""
    for attempt in range(3):
        try:
            r = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/readme",
                headers=HEADERS,
                timeout=20,
            )
            if r.status_code == 200:
                data = r.json()
                content  = data.get("content", "")
                encoding = data.get("encoding", "base64")
                if encoding == "base64":
                    return base64.b64decode(content).decode("utf-8", errors="ignore")[:8000]
                return content[:8000]
            if r.status_code == 404:
                return ""
            if r.status_code in (403, 429):
                reset = int(r.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait  = max(reset - int(time.time()), 1)
                time.sleep(min(wait, 120))
            else:
                time.sleep(5 * (attempt + 1))
        except requests.RequestException:
            time.sleep(5 * (attempt + 1))
    return ""


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    print("Stage 2c -- Nominatim + Commit Timezone + Commit Messages + README")
    print("=" * 60)

    if not ALL_FILE.exists():
        raise SystemExit(f"Missing: {ALL_FILE}\nRun stage2a + stage2b first.")

    all_df  = pd.read_csv(ALL_FILE)
    corpus  = pd.read_csv(CORPUS, low_memory=False)

    # Build owner → location_raw from stage2a (owners who had a string we
    # couldn't parse — Nominatim will try to resolve those strings)
    location_raw_map: dict[str, str] = {}
    if FAST_FILE.exists():
        fast_df = pd.read_csv(FAST_FILE)
        # Only non-empty location_raw that stage2a failed to map
        unmatched = fast_df[
            (fast_df["inferred_country"] == "not_specified") &
            (fast_df["location_raw"].notna()) &
            (fast_df["location_raw"].str.strip() != "")
        ]
        location_raw_map = dict(
            zip(unmatched["owner_login"], unmatched["location_raw"])
        )
        print(f"Owners with unparsed location strings: {len(location_raw_map):,}  "
              f"(Signal 0 — Nominatim)")
    else:
        print("owner_locations_fast.csv not found — skipping Signal 0")

    # Build owner → sorted list of repos (by stars desc, take first)
    owner_repos: dict[str, list[str]] = {}
    for _, row in corpus.iterrows():
        owner = row["owner_login"]
        owner_repos.setdefault(owner, []).append(
            (int(row.get("stars", 0) or 0), str(row["full_name"]))
        )
    # Sort each owner's repos by stars descending
    for owner in owner_repos:
        owner_repos[owner].sort(reverse=True)

    # Filter to not_specified owners
    unresolved = all_df[all_df["inferred_country"] == "not_specified"]["owner_login"].tolist()

    # Resume support
    if OUT_C.exists() and OUT_C.stat().st_size > 0:
        try:
            done = set(pd.read_csv(OUT_C)["owner_login"].tolist())
            unresolved = [o for o in unresolved if o not in done]
            print(f"Resuming. Remaining: {len(unresolved):,}")
        except Exception:
            print(f"Unresolved owners: {len(unresolved):,}")
    else:
        print(f"Unresolved owners: {len(unresolved):,}")

    results  = []
    resolved = 0

    # ── Pass A: Signal 0 — Nominatim (only owners with unparsed location strings)
    print("\nPass A — Nominatim geocoding (owners with unparsed location strings)...")

    # Split upfront: owners with a location string vs. those with nothing
    has_location    = [o for o in unresolved if location_raw_map.get(o, "")]
    no_location     = [o for o in unresolved if not location_raw_map.get(o, "")]
    needs_github: list[str] = []

    # Owners with no location string → skip straight to Pass B
    for owner in no_location:
        if owner_repos.get(owner):
            needs_github.append(owner)
        else:
            results.append({
                "owner_login":      owner,
                "inferred_country": "not_specified",
                "confidence":       "none",
                "source":           "no_repos_in_corpus",
            })

    print(f"  Owners with no location string  → skip to Pass B : {len(no_location):,}")
    print(f"  Owners with unparsed location   → run Nominatim  : {len(has_location):,}")
    print()

    nom_total = len(has_location)
    for nom_idx, owner in enumerate(has_location, 1):
        loc_raw = location_raw_map[owner]

        if not owner_repos.get(owner):
            results.append({
                "owner_login":      owner,
                "inferred_country": "not_specified",
                "confidence":       "none",
                "source":           "no_repos_in_corpus",
            })
            continue

        geo_country = nominatim_geocode(loc_raw)
        if geo_country:
            results.append({
                "owner_login":      owner,
                "inferred_country": geo_country,
                "confidence":       "high",
                "source":           f"nominatim({loc_raw[:50]})",
            })
            resolved += 1
        else:
            needs_github.append(owner)

        if nom_idx % 100 == 0:
            pct = nom_idx / nom_total * 100
            print(f"  Pass A  [{nom_idx:>5,}/{nom_total:,}] {pct:5.1f}%  "
                  f"resolved: {resolved:,}  "
                  f"forwarded to B: {len(needs_github) - len(no_location):,}  "
                  f"cache: {len(_nominatim_cache):,}")

        if nom_idx % SAVE_EVERY == 0:
            _flush(results)
            results = []
            print(f"    [checkpoint saved]")

    print(f"\n  Pass A done.")
    print(f"  Nominatim resolved : {resolved:,}")
    print(f"  Total → Pass B     : {len(needs_github):,}  "
          f"({len(no_location):,} no-location + "
          f"{len(needs_github)-len(no_location):,} nominatim-failed)")

    # ── Pass B: Signals 1+2 — batched GraphQL (10 owners per request) ─────────
    b_total = len(needs_github)
    print(f"\nPass B — GraphQL commit batches  ({b_total:,} owners, "
          f"~{b_total // GRAPHQL_BATCH:,} requests)...")
    needs_readme: list[str] = []
    b_resolved_here = 0

    gql_batches = [
        needs_github[i:i + GRAPHQL_BATCH]
        for i in range(0, len(needs_github), GRAPHQL_BATCH)
    ]

    for b_idx, batch_owners in enumerate(gql_batches):
        batch_items = []
        for i, owner in enumerate(batch_owners):
            _, full_name = owner_repos[owner][0]
            repo = full_name.split("/", 1)[1]
            batch_items.append((f"r{i}", owner, repo))

        gql_data = run_graphql_commits(batch_items)
        time.sleep(SLEEP_OK)

        for alias, owner, repo in batch_items:
            repo_data  = gql_data.get(alias) or {}
            tz_offset, commit_text = parse_commit_data(repo_data, owner)

            tz_result     = TIMEZONE_COUNTRY.get(tz_offset) if tz_offset else None
            tz_candidates = tz_result if isinstance(tz_result, list) else None

            if isinstance(tz_result, str):
                results.append({
                    "owner_login":      owner,
                    "inferred_country": tz_result,
                    "confidence":       "high",
                    "source":           f"commit_timezone({tz_offset})",
                })
                resolved += 1
                b_resolved_here += 1
                continue

            msg_country, msg_note = detect_script(commit_text)
            country, confidence, source = resolve_combined(
                tz_candidates, msg_country, msg_note
            )
            if country != "not_specified":
                source = source.replace("script", "commit_msg")
                results.append({
                    "owner_login":      owner,
                    "inferred_country": country,
                    "confidence":       confidence,
                    "source":           source,
                })
                resolved += 1
                b_resolved_here += 1
                continue

            needs_readme.append((owner, repo, tz_candidates, msg_country, msg_note))

        owners_done = (b_idx + 1) * GRAPHQL_BATCH
        if (b_idx + 1) % 50 == 0:
            pct = min(owners_done, b_total) / b_total * 100
            print(f"  Pass B  [{min(owners_done,b_total):>7,}/{b_total:,}] {pct:5.1f}%  "
                  f"resolved this pass: {b_resolved_here:,}  "
                  f"total resolved: {resolved:,}  "
                  f"→ README queue: {len(needs_readme):,}")

        if (b_idx + 1) % (SAVE_EVERY // GRAPHQL_BATCH) == 0:
            _flush(results)
            results = []
            print(f"    [checkpoint saved at batch {b_idx+1:,}]")

    print(f"\n  Pass B done.")
    print(f"  Resolved by timezone/script : {b_resolved_here:,}")
    print(f"  Forwarded to Pass C (README): {len(needs_readme):,}")

    # ── Pass C: Signal 3 — README fetch (one REST call per owner) ─────────────
    c_total = len(needs_readme)
    print(f"\nPass C — README script detection  ({c_total:,} owners)...")
    c_resolved_here = 0

    for r_idx, (owner, repo, tz_candidates, msg_country, msg_note) in \
            enumerate(needs_readme, 1):

        readme = fetch_readme_text(owner, repo)
        time.sleep(SLEEP_OK)

        readme_country, readme_note = detect_script(readme)
        final_country = readme_country or msg_country
        final_note    = readme_note if readme_note != "none" else msg_note

        country, confidence, source = resolve_combined(
            tz_candidates, final_country, final_note
        )
        if country != "not_specified":
            resolved += 1
            c_resolved_here += 1

        results.append({
            "owner_login":      owner,
            "inferred_country": country,
            "confidence":       confidence,
            "source":           source,
        })

        if r_idx % 200 == 0:
            pct = r_idx / c_total * 100
            print(f"  Pass C  [{r_idx:>7,}/{c_total:,}] {pct:5.1f}%  "
                  f"resolved this pass: {c_resolved_here:,}  "
                  f"total resolved: {resolved:,}")

        if r_idx % SAVE_EVERY == 0:
            _flush(results)
            results = []
            print(f"    [checkpoint saved]")

    # Final flush
    if results:
        _flush(results)

    # ── Update owner_locations_all.csv ────────────────────────────────────────
    c_df   = pd.read_csv(OUT_C)
    # Keep only newly resolved rows
    new_resolved = c_df[c_df["inferred_country"] != "not_specified"][
        ["owner_login", "inferred_country", "confidence", "source"]
    ].copy()
    new_resolved["location_raw"] = ""

    # Replace not_specified rows in all_df with new results
    all_df_updated = all_df[~all_df["owner_login"].isin(new_resolved["owner_login"])]
    all_df_updated = pd.concat([all_df_updated, new_resolved], ignore_index=True)
    all_df_updated.to_csv(ALL_FILE, index=False)

    # ── Summary ───────────────────────────────────────────────────────────────
    total_resolved = (c_df["inferred_country"] != "not_specified").sum()
    print(f"\n{'=' * 60}")
    print(f"Owners attempted  : {len(c_df):,}")
    print(f"Newly resolved    : {total_resolved:,}  ({total_resolved/len(c_df)*100:.1f}%)")
    print(f"Still unresolved  : {len(c_df) - total_resolved:,}")

    total_all = len(all_df_updated)
    labelled  = (all_df_updated["inferred_country"] != "not_specified").sum()
    print(f"\nUpdated owner_locations_all.csv:")
    print(f"  Total owners : {total_all:,}")
    print(f"  Located      : {labelled:,}  ({labelled/total_all*100:.1f}%)")
    print(f"  Not specified: {total_all - labelled:,}  ({(total_all-labelled)/total_all*100:.1f}%)")

    print("\nTop 20 newly resolved countries:")
    top = (c_df[c_df["inferred_country"] != "not_specified"]
           .groupby("inferred_country").size()
           .sort_values(ascending=False).head(20))
    for country, count in top.items():
        print(f"  {country:<30} {count:>6,}")

    print(f"\nSaved: {OUT_C}")
    print(f"Updated: {ALL_FILE}")
    print("\nStage 2c complete.")


def _flush(rows: list[dict]) -> None:
    """Append rows to OUT_C, creating file if needed."""
    if not rows:
        return
    new_chunk = pd.DataFrame(rows)
    if OUT_C.exists() and OUT_C.stat().st_size > 0:
        try:
            existing  = pd.read_csv(OUT_C)
            new_chunk = pd.concat([existing, new_chunk], ignore_index=True)
        except Exception:
            pass   # corrupted/empty file — overwrite cleanly
    new_chunk.to_csv(OUT_C, index=False)


if __name__ == "__main__":
    main()

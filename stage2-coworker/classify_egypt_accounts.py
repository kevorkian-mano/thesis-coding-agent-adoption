"""
classify_egypt_accounts.py
==========================
Decides which accounts in egypt_combined_accounts.csv are really Egyptian.

Why: the snowball step (Stage 2b) added everyone who follows / is followed by
an Egyptian seed account, so the list contains many non-Egyptians.

How it works (two passes):

  PASS 1 - profile clues (cheap, all accounts)
    1. Location field   -> mentions Egypt or an Egyptian city?
    2. Email / website  -> ends in .eg (e.g. guc.edu.eg, company.com.eg)?
    3. Company / bio    -> mentions Egypt or an Egyptian university/company?

  PASS 2 - network share (more expensive, only accounts still unresolved)
    4. Of the account's followers + following WHO HAVE A LOCATION SET,
       what fraction are located in Egypt? (default threshold: 70%)

Tiers written to the output:
    confirmed  - location says Egypt, OR an .eg email/website
    likely     - no location, but company/bio clue OR network share >= threshold
    excluded   - location is set and points somewhere else
    unknown    - no usable clues

Main analysis should use `confirmed`; `likely` is for a sensitivity check.
Manually check the random sample in egypt_validation_sample.csv to measure
how accurate this is.

Usage:
    pip install requests pandas
    export GITHUB_TOKEN=ghp_xxx          (Windows PowerShell: $env:GITHUB_TOKEN="ghp_xxx")
    python classify_egypt_accounts.py --limit 50     # quick test run first
    python classify_egypt_accounts.py                # full run

The script saves progress as it goes (cache files), so if it crashes or you
stop it with Ctrl+C, just run it again and it continues where it left off.
"""

import argparse
import json
import os
import re
import sys
import time

import pandas as pd
import requests

# ─────────────────────────────────────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────────────────────────────────────

GRAPHQL_URL = "https://api.github.com/graphql"
PROFILE_BATCH_SIZE = 25     # accounts per request in pass 1 (profile only, light)
NETWORK_BATCH_SIZE = 5      # accounts per request in pass 2 (pulls 200 connections each)
NETWORK_SAMPLE = 100        # followers and following fetched per account (max 100 each)

# ─────────────────────────────────────────────────────────────────────────────
# Keyword lists  (edit these freely - they are the "rules" of the classifier)
# ─────────────────────────────────────────────────────────────────────────────

# Egyptian places: country, governorates, major cities, Cairo/Giza districts.
EGYPT_PLACES = [
    "egypt", "egyptian", "misr", "masr",
    "cairo", "giza", "alexandria", "mansoura", "tanta", "zagazig", "ismailia",
    "suez", "port said", "portsaid", "luxor", "aswan", "asyut", "assiut",
    "sohag", "minya", "minia", "faiyum", "fayoum", "beni suef", "benisuef",
    "damanhur", "damanhour", "kafr el sheikh", "kafrelsheikh", "hurghada",
    "sharm el sheikh", "sharm elsheikh", "damietta", "banha", "benha",
    "shebin", "qena", "matrouh", "arish", "el obour", "obour",
    "6th of october", "6 october", "6th october", "october city",
    "sheikh zayed", "new cairo", "nasr city", "maadi", "heliopolis",
    "mokattam", "dokki", "zamalek", "shubra", "new capital",
]
EGYPT_PLACES_AR = [
    "مصر", "القاهرة", "الاسكندرية", "الإسكندرية", "الجيزة", "المنصورة",
    "طنطا", "الزقازيق", "الإسماعيلية", "الاسماعيلية", "السويس", "بورسعيد",
    "الأقصر", "الاقصر", "أسوان", "اسوان", "أسيوط", "اسيوط", "سوهاج", "المنيا",
    "الفيوم", "بني سويف", "دمنهور", "كفر الشيخ", "الغردقة", "دمياط", "بنها",
    "قنا", "مصري", "مصرية",
]

# If a location mentions one of these, "Cairo"/"Alexandria" are probably
# NOT the Egyptian ones (Alexandria, Virginia; Cairo, Illinois; ...).
NOT_EGYPT_HINTS = [
    "usa", "u.s.", "united states", "virginia", ", va", "illinois", ", il",
    "louisiana", "georgia", ", ga", "romania", "minnesota", ", mn",
    "kentucky", ", ky", "new zealand", "west virginia", "ontario", "scotland",
]

# Locations that carry no information -> treated as empty.
JUNK_LOCATIONS = [
    "earth", "world", "worldwide", "planet earth", "remote", "internet",
    "localhost", "127.0.0.1", "home", "everywhere", "anywhere", "/dev/null",
    "the internet", "online", "global", "somewhere", "here", "mars", "moon",
]

# Egyptian universities and companies (for company / bio fields).
# Short acronyms are matched as whole words only.
EGYPT_ORGS = [
    "german international university", "german university in cairo",
    "american university in cairo", "cairo university", "ain shams",
    "alexandria university", "mansoura university", "helwan university",
    "nile university", "zewail city", "british university in egypt",
    "arab academy for science", "misr international university",
    "misr university", "october university", "msa university",
    "future university in egypt", "benha university", "zagazig university",
    "assiut university", "tanta university", "menoufia university",
    "information technology institute", "iti egypt",
    "vodafone egypt", "orange egypt", "etisalat egypt", "telecom egypt",
    "valeo egypt", "siemens egypt", "instabug", "swvl", "fawry", "vezeeta",
    "paymob", "breadfast", "elmenus", "sumerge", "itworx", "giza systems",
    "raya it", "raya holding", "e-finance", "efinance", "thndr",
]
EGYPT_ORG_ACRONYMS = ["giu", "guc", "auc", "bue", "aast", "fcai", "fcis", "fci"]

# Domains that are Egyptian but don't end in .eg
EGYPT_SPECIAL_DOMAINS = ["aucegypt.edu", "giu-uni.de"]


# ─────────────────────────────────────────────────────────────────────────────
# Matching helpers
# ─────────────────────────────────────────────────────────────────────────────

def _norm(text):
    if not isinstance(text, str):   # None / NaN / numbers -> empty
        return ""
    return text.strip().lower()


def _has_word(text, word):
    """Whole-word / whole-phrase match (so 'giza' doesn't match 'gizarra')."""
    return re.search(r"(?<![a-z0-9])" + re.escape(word) + r"(?![a-z0-9])", text) is not None


def location_status(location):
    """Returns 'egypt', 'elsewhere', or 'empty'."""
    loc = _norm(location)
    if not loc or loc in JUNK_LOCATIONS:
        return "empty"
    if any(w in loc for w in EGYPT_PLACES_AR):
        return "egypt"
    if _has_word(loc, "egypt") or _has_word(loc, "misr") or _has_word(loc, "masr"):
        return "egypt"
    if any(_has_word(loc, w) for w in EGYPT_PLACES):
        # "Alexandria, VA" or "Cairo, Illinois" -> not Egypt
        if any(h in loc for h in NOT_EGYPT_HINTS):
            return "elsewhere"
        return "egypt"
    return "elsewhere"


def has_eg_domain(*values):
    """True if any email / URL is an Egyptian domain (.eg or a known special one)."""
    for v in values:
        v = _norm(v)
        if not v:
            continue
        if re.search(r"\.eg(?![a-z0-9])", v):
            return True
        if any(d in v for d in EGYPT_SPECIAL_DOMAINS):
            return True
    return False


def company_bio_match(company, bio):
    """Returns the matched keyword (string) or None."""
    text = _norm(company) + " | " + _norm(bio)
    if not text.strip(" |"):
        return None
    for w in EGYPT_PLACES_AR:
        if w in text:
            return w
    for w in ["egypt", "egyptian"] + EGYPT_ORGS + EGYPT_ORG_ACRONYMS:
        if _has_word(text, w):
            return w
    return None


def classify(row, threshold, min_located):
    """Applies the tier rules to one account. Returns (tier, reason)."""
    loc = row["loc_status"]
    if loc == "egypt":
        return "confirmed", "location"
    if row["eg_domain"]:
        return "confirmed", "eg_domain"
    if loc == "elsewhere":
        return "excluded", "location_elsewhere"

    reasons = []
    if isinstance(row.get("company_bio_match"), str):
        reasons.append("company_bio")
    share = row.get("net_share")
    located = row.get("net_located")
    if (share is not None and not pd.isna(share)
            and located is not None and not pd.isna(located)
            and located >= min_located and share >= threshold):
        reasons.append("network")
    if reasons:
        return "likely", "+".join(reasons)
    return "unknown", "no_clues"


# ─────────────────────────────────────────────────────────────────────────────
# GitHub API
# ─────────────────────────────────────────────────────────────────────────────

def make_session():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("ERROR: set the GITHUB_TOKEN environment variable first.")
    s = requests.Session()
    s.headers.update({"Authorization": f"bearer {token}"})
    return s


def post_graphql(session, query, max_retries=5):
    """Sends a query, retrying on server errors and waiting out rate limits."""
    for attempt in range(max_retries):
        try:
            r = session.post(GRAPHQL_URL, json={"query": query}, timeout=60)
        except requests.RequestException as e:
            print(f"  network error ({e}), retrying...")
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code in (502, 503, 504):
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code in (403, 429):
            wait = int(r.headers.get("Retry-After", 60))
            print(f"  rate limited, sleeping {wait}s...")
            time.sleep(wait)
            continue
        if r.status_code != 200:
            print(f"  HTTP {r.status_code}: {r.text[:200]}")
            time.sleep(5)
            continue
        try:
            data = r.json()
        except ValueError:          # GitHub sometimes answers 200 with an empty body
            print("  empty response from GitHub, retrying...")
            time.sleep(5 * (attempt + 1))
            continue
        rl = (data.get("data") or {}).get("rateLimit")
        if rl and rl["remaining"] < 100:
            reset = pd.Timestamp(rl["resetAt"]).timestamp()
            wait = max(0, reset - time.time()) + 5
            print(f"  hourly limit almost used up, sleeping {int(wait)}s...")
            time.sleep(wait)
        return data
    return None


def _safe_login(login):
    return str(login).replace('"', "").replace("\\", "").strip()


def profile_query(logins):
    parts = []
    for i, login in enumerate(logins):
        parts.append(f"""
        a{i}: repositoryOwner(login: "{_safe_login(login)}") {{
          login
          __typename
          ... on User {{ location company bio websiteUrl email }}
          ... on Organization {{ location description websiteUrl email }}
        }}""")
    return "query { rateLimit { remaining resetAt } " + " ".join(parts) + " }"


def network_query(logins, n):
    parts = []
    for i, login in enumerate(logins):
        parts.append(f"""
        a{i}: user(login: "{_safe_login(login)}") {{
          followers(first: {n}) {{ nodes {{ location }} }}
          following(first: {n}) {{ nodes {{ location }} }}
        }}""")
    return "query { rateLimit { remaining resetAt } " + " ".join(parts) + " }"


# ─────────────────────────────────────────────────────────────────────────────
# Cache (so the script can resume after a crash)
# ─────────────────────────────────────────────────────────────────────────────

def load_cache(path):
    cache = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    cache[rec["login"].lower()] = rec
                except (json.JSONDecodeError, KeyError):
                    pass
    return cache


def append_cache(path, records):
    with open(path, "a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# Passes
# ─────────────────────────────────────────────────────────────────────────────

def run_profile_pass(session, logins, cache_path):
    cache = load_cache(cache_path)
    todo = [l for l in logins if l.lower() not in cache]
    print(f"Pass 1 (profiles): {len(logins) - len(todo)} cached, {len(todo)} to fetch")
    for start in range(0, len(todo), PROFILE_BATCH_SIZE):
        batch = todo[start:start + PROFILE_BATCH_SIZE]
        data = post_graphql(session, profile_query(batch))
        payload = (data or {}).get("data") or {}
        records = []
        for i, login in enumerate(batch):
            node = payload.get(f"a{i}")
            if node is None:   # deleted / renamed account, or request failed
                rec = {"login": login, "found": False}
            else:
                rec = {
                    "login": login,
                    "found": True,
                    "type": node.get("__typename"),
                    "location": node.get("location"),
                    "company": node.get("company"),
                    "bio": node.get("bio") or node.get("description"),
                    "website": node.get("websiteUrl"),
                    "email": node.get("email"),
                }
            records.append(rec)
            cache[login.lower()] = rec
        if data is not None:   # don't cache a failed batch; retry it next run
            append_cache(cache_path, records)
        done = min(start + PROFILE_BATCH_SIZE, len(todo))
        print(f"  {done}/{len(todo)}", end="\r", flush=True)
    print()
    return cache


def fetch_network(session, batch):
    """Returns (records, failed_logins). An account only gets a record if
    GitHub answered for it: either its connections, or 'account not found'.
    Accounts lost to a timeout are returned as failed, not as 0 connections."""
    data = post_graphql(session, network_query(batch, NETWORK_SAMPLE))
    if data is None:
        return [], list(batch)
    payload = data.get("data") or {}
    not_found = {
        (e.get("path") or [None])[0]
        for e in data.get("errors") or [] if e.get("type") == "NOT_FOUND"
    }
    records, failed = [], []
    for i, login in enumerate(batch):
        node = payload.get(f"a{i}")
        if node is None:
            if f"a{i}" in not_found:      # deleted / renamed account
                records.append({"login": login, "net_located": 0, "net_egypt": 0})
            else:                         # timeout or other error: try again
                failed.append(login)
            continue
        people = node["followers"]["nodes"] + node["following"]["nodes"]
        statuses = [location_status((p or {}).get("location")) for p in people]
        located = [s for s in statuses if s != "empty"]
        records.append({
            "login": login,
            "net_located": len(located),
            "net_egypt": sum(s == "egypt" for s in located),
        })
    return records, failed


def run_network_pass(session, logins, cache_path):
    cache = load_cache(cache_path)
    todo = [l for l in logins if l.lower() not in cache]
    print(f"Pass 2 (network): {len(logins) - len(todo)} cached, {len(todo)} to fetch")
    still_failed = 0
    for start in range(0, len(todo), NETWORK_BATCH_SIZE):
        batch = todo[start:start + NETWORK_BATCH_SIZE]
        records, failed = fetch_network(session, batch)
        if failed and len(batch) > 1:     # retry the failed ones one at a time
            for login in failed:
                one, f = fetch_network(session, [login])
                records += one
                still_failed += len(f)
        else:
            still_failed += len(failed)
        for rec in records:
            cache[rec["login"].lower()] = rec
        append_cache(cache_path, records)
        done = min(start + NETWORK_BATCH_SIZE, len(todo))
        print(f"  {done}/{len(todo)}  (failed: {still_failed})", end="\r", flush=True)
    print()
    if still_failed:
        print(f"WARNING: {still_failed} accounts failed in pass 2 and count as 'unknown' "
              "in this output. Run the same command again to retry them.")
    return cache


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Classify accounts as Egyptian or not.")
    ap.add_argument("--input", default="egypt_combined_accounts.csv")
    ap.add_argument("--output", default="egypt_accounts_classified.csv")
    ap.add_argument("--sample-output", default="egypt_validation_sample.csv")
    ap.add_argument("--threshold", type=float, default=0.70,
                    help="network share needed for 'likely' (default 0.70)")
    ap.add_argument("--min-located", type=int, default=5,
                    help="min. connections with a location before network share counts")
    ap.add_argument("--sample-size", type=int, default=150,
                    help="accounts in the manual validation sample")
    ap.add_argument("--limit", type=int, default=None,
                    help="only process the first N accounts (for a test run)")
    args = ap.parse_args()

    df = pd.read_csv(args.input)
    if "login" not in df.columns:
        sys.exit(f"ERROR: {args.input} has no 'login' column.")
    df = df.dropna(subset=["login"]).drop_duplicates(subset=["login"])
    if args.limit:
        df = df.head(args.limit)
    logins = df["login"].astype(str).tolist()
    print(f"Loaded {len(logins)} accounts from {args.input}")

    session = make_session()

    # Pass 1: profiles
    profiles = run_profile_pass(session, logins, "cache_profiles.jsonl")

    rows = []
    for login in logins:
        p = profiles.get(login.lower(), {"found": False})
        rows.append({
            "login": login,
            "found": p.get("found", False),
            "type": p.get("type"),
            "location": p.get("location"),
            "company": p.get("company"),
            "bio": p.get("bio"),
            "website": p.get("website"),
            "email": p.get("email"),
        })
    out = pd.DataFrame(rows)
    out["loc_status"] = out["location"].apply(location_status)
    out["eg_domain"] = out.apply(lambda r: has_eg_domain(r["email"], r["website"]), axis=1)
    out["company_bio_match"] = out.apply(lambda r: company_bio_match(r["company"], r["bio"]), axis=1)

    # Pass 2: network share, only for users still unresolved after pass 1
    unresolved = out[
        out["found"]
        & (out["type"] == "User")
        & (out["loc_status"] == "empty")
        & (~out["eg_domain"])
    ]["login"].tolist()
    network = run_network_pass(session, unresolved, "cache_network.jsonl") if unresolved else {}

    out["net_located"] = out["login"].apply(lambda l: network.get(l.lower(), {}).get("net_located"))
    out["net_egypt"] = out["login"].apply(lambda l: network.get(l.lower(), {}).get("net_egypt"))
    out["net_share"] = out.apply(
        lambda r: (r["net_egypt"] / r["net_located"]) if r["net_located"] else None, axis=1
    )

    # Tiers
    tiers = out.apply(lambda r: classify(r, args.threshold, args.min_located), axis=1)
    out["tier"] = [t[0] for t in tiers]
    out["reason"] = [t[1] for t in tiers]
    out.loc[~out["found"], ["tier", "reason"]] = ["unknown", "account_not_found"]

    # Carry over seed/snowball info from the input file if present
    if "source" in df.columns:
        out = out.merge(df[["login", "source"]], on="login", how="left")

    out.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"\nSaved {args.output}")

    # Summary
    print("\n── Results ──")
    print(out["tier"].value_counts().to_string())
    print("\nBy reason:")
    print(out.groupby(["tier", "reason"]).size().to_string())
    if "source" in out.columns:
        print("\nTier by source (seed vs snowball):")
        print(pd.crosstab(out["source"], out["tier"]).to_string())

    # Random sample for manual checking (confirmed + likely)
    pool = out[out["tier"].isin(["confirmed", "likely"])]
    n = min(args.sample_size, len(pool))
    if n:
        sample = pool.sample(n=n, random_state=42).copy()
        sample["profile_url"] = "https://github.com/" + sample["login"]
        sample["manual_is_egyptian"] = ""   # fill in: yes / no / unsure
        cols = ["login", "profile_url", "tier", "reason", "location", "company",
                "bio", "website", "net_share", "manual_is_egyptian"]
        sample[cols].to_csv(args.sample_output, index=False, encoding="utf-8-sig")
        print(f"\nSaved {n} accounts for manual checking -> {args.sample_output}")


if __name__ == "__main__":
    main()

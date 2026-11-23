#!/usr/bin/env python3
"""
Stage 2e -- Commit Author Email TLD
=====================================
Runs on the owners still unresolved after Stage 2d.

Each owner's highest-commit corpus repository is selected. The 10 most recent
commits on its default branch are fetched via the GitHub REST API. Commit
author emails are extracted at the git-config level — distinct from the GitHub
profile email that Stage 2b already tried. Many developers configure git with a
work or university address (e.g. john@tu-berlin.de) while leaving their GitHub
profile email blank.

Signal logic:
  1. Fetch up to 10 recent commits from the owner's most-active corpus repo.
  2. Collect all non-generic author emails.
  3. Map each email's ccTLD to a country.
  4. If any ccTLD country appears: accept it.
     Confidence = "medium" if ≥ 2 commits agree, "low" if only 1.

Resumable: results are flushed to a JSON cache every --flush-every owners so
the run can be interrupted and restarted without re-fetching.

Output
------
  data/stage2/owner_locations_e.csv       -- stage2e results (all attempted)
  data/stage2/owner_locations_e_cache.json
  data/stage2/owner_locations_all.csv     -- UPDATED with newly resolved owners

Usage
-----
  export GITHUB_TOKEN=ghp_...
  python3 scripts/stage2/stage2e_commit_email.py
  python3 scripts/stage2/stage2e_commit_email.py --limit 500   # probe run
  python3 scripts/stage2/stage2e_commit_email.py --workers 4   # default
"""

import os
import sys
import json
import time
import argparse
import requests
import pandas as pd
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT      = Path(__file__).resolve().parents[2]
ALL_FILE  = ROOT / "data" / "stage2" / "owner_locations_all.csv"
CORPUS    = ROOT / "data" / "stage1" / "global_corpus.csv"
OUT_DIR   = ROOT / "data" / "stage2"
OUT_E     = OUT_DIR / "owner_locations_e.csv"
CACHE_FILE = OUT_DIR / "owner_locations_e_cache.json"

TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    sys.exit("ERROR: GITHUB_TOKEN not set.")

REST_URL   = "https://api.github.com/repos/{owner}/{repo}/commits"
REST_HEADERS = {
    "Authorization":        f"Bearer {TOKEN}",
    "Accept":               "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

SLEEP_OK    = 0.8    # seconds between requests (5,000/hr limit → 1.39 req/s max)
SLEEP_RETRY = 60     # seconds to wait on 403/429
COMMITS_PER_REPO = 10

# ── Generic email providers whose TLD carries no location signal ───────────────
GENERIC_PROVIDERS = {
    "gmail.com", "googlemail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "live.com", "icloud.com", "me.com", "mac.com", "aol.com", "protonmail.com",
    "proton.me", "pm.me", "mail.com", "gmx.com", "gmx.net", "fastmail.com",
    "zoho.com", "yandex.com", "yandex.ru", "ymail.com", "inbox.com",
    "msn.com", "users.noreply.github.com", "noreply.github.com", "example.com",
    "163.com", "126.com", "qq.com", "sina.com", "foxmail.com",   # Chinese generic
    "naver.com", "daum.net", "hanmail.net",                        # Korean generic
    "web.de", "t-online.de",                                       # German generic
}

# ── ccTLD → country name ───────────────────────────────────────────────────────
TLD_MAP = {
    ".eg": "Egypt",          ".ng": "Nigeria",        ".za": "South Africa",
    ".ke": "Kenya",          ".gh": "Ghana",           ".et": "Ethiopia",
    ".ma": "Morocco",        ".tn": "Tunisia",         ".dz": "Algeria",
    ".sa": "Saudi Arabia",   ".ae": "United Arab Emirates", ".qa": "Qatar",
    ".kw": "Kuwait",         ".bh": "Bahrain",         ".om": "Oman",
    ".jo": "Jordan",         ".lb": "Lebanon",          ".iq": "Iraq",
    ".ir": "Iran",           ".il": "Israel",           ".tr": "Turkey",
    ".pk": "Pakistan",       ".in": "India",            ".cn": "China",
    ".jp": "Japan",          ".kr": "South Korea",      ".id": "Indonesia",
    ".vn": "Vietnam",        ".th": "Thailand",         ".my": "Malaysia",
    ".sg": "Singapore",      ".ph": "Philippines",      ".tw": "Taiwan",
    ".bd": "Bangladesh",     ".hk": "Hong Kong",        ".gb": "United Kingdom",
    ".uk": "United Kingdom", ".de": "Germany",          ".fr": "France",
    ".es": "Spain",          ".it": "Italy",             ".nl": "Netherlands",
    ".se": "Sweden",         ".no": "Norway",            ".dk": "Denmark",
    ".fi": "Finland",        ".ch": "Switzerland",       ".at": "Austria",
    ".be": "Belgium",        ".pt": "Portugal",          ".pl": "Poland",
    ".ua": "Ukraine",        ".ru": "Russia",            ".cz": "Czech Republic",
    ".ro": "Romania",        ".hu": "Hungary",           ".gr": "Greece",
    ".ie": "Ireland",        ".us": "United States",     ".ca": "Canada",
    ".br": "Brazil",         ".mx": "Mexico",            ".ar": "Argentina",
    ".co": "Colombia",       ".cl": "Chile",             ".pe": "Peru",
    ".au": "Australia",      ".nz": "New Zealand",       ".ac": None,  # ignore .ac
    ".io": None,             ".ai": None,                ".app": None,  # generic SLDs
    ".dev": None,            ".me": None,                ".cc": None,
}


def email_to_country(email: str) -> str | None:
    """Map an email address to a country via ccTLD. Returns None if no match."""
    if not email:
        return None
    email = email.strip().lower()
    if "@" not in email:
        return None
    domain = email.rsplit("@", 1)[-1]
    if domain in GENERIC_PROVIDERS:
        return None
    # Walk TLD_MAP longest-match first
    for tld in sorted(TLD_MAP, key=len, reverse=True):
        if domain.endswith(tld):
            return TLD_MAP[tld]  # may be None for explicitly excluded TLDs
    return None


def build_owner_repo_map(corpus_path: Path) -> dict[str, str]:
    """
    Returns {owner_login: repo_name} mapping the owner to their
    highest-commit corpus repository.
    """
    df = pd.read_csv(corpus_path, usecols=["owner_login", "repo_name", "commits"])
    idx = df.groupby("owner_login")["commits"].idxmax()
    best = df.loc[idx].set_index("owner_login")["repo_name"]
    return best.to_dict()


def fetch_commit_emails(session: requests.Session, owner: str, repo: str) -> list[str]:
    """
    Fetches up to COMMITS_PER_REPO recent commits and returns a list of
    non-empty author email strings.
    """
    url = REST_URL.format(owner=owner, repo=repo)
    params = {"per_page": COMMITS_PER_REPO}
    for attempt in range(4):
        try:
            r = session.get(url, params=params, timeout=20)
        except Exception:
            time.sleep(10 * (attempt + 1))
            continue
        if r.status_code == 200:
            commits = r.json() or []
            emails = []
            for c in commits:
                email = (
                    (c.get("commit") or {})
                    .get("author") or {}
                ).get("email") or ""
                if email:
                    emails.append(email.strip().lower())
            return emails
        elif r.status_code in (403, 429):
            time.sleep(SLEEP_RETRY)
        elif r.status_code in (404, 451):
            return []   # repo gone or blocked
        else:
            time.sleep(5)
    return []


def resolve_owner(
    session: requests.Session,
    owner: str,
    repo: str,
    min_sleep: float,
) -> dict:
    """
    Attempt to resolve owner's country via commit author email TLD.
    Returns a record dict with keys matching owner_locations_all.csv columns.
    """
    record = {
        "owner_login":      owner,
        "location_raw":     "",
        "inferred_country": "not_specified",
        "confidence":       "none",
        "source":           "not_specified",
    }

    emails = fetch_commit_emails(session, owner, repo)
    time.sleep(min_sleep)

    if not emails:
        return record

    countries = []
    for email in emails:
        country = email_to_country(email)
        if country:
            countries.append(country)

    if not countries:
        return record

    counts = Counter(countries)
    top_country, top_count = counts.most_common(1)[0]

    record["inferred_country"] = top_country
    record["confidence"]       = "medium" if top_count >= 2 else "low"
    record["source"]           = (
        f"commit_author_email_tld({top_count})"
        if top_count >= 2
        else "commit_author_email_tld(1)"
    )
    return record


# ── Cache helpers ──────────────────────────────────────────────────────────────

def load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    tmp = CACHE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
    tmp.replace(CACHE_FILE)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit",       type=int,   default=0,    help="cap owners processed (0 = all)")
    ap.add_argument("--workers",     type=int,   default=4,    help="parallel HTTP workers")
    ap.add_argument("--min-sleep",   type=float, default=SLEEP_OK)
    ap.add_argument("--flush-every", type=int,   default=500)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load unresolved owners
    all_df = pd.read_csv(ALL_FILE)
    unresolved = all_df[all_df["inferred_country"] == "not_specified"]["owner_login"].tolist()
    print(f"Unresolved owners: {len(unresolved)}")

    # Build owner → best repo map
    print("Building owner→repo map from corpus …")
    owner_repo = build_owner_repo_map(CORPUS)
    # Keep only owners that appear in corpus
    targets = [o for o in unresolved if o in owner_repo]
    print(f"Owners with corpus repos: {len(targets)}")

    # Load cache and filter already-done
    cache = load_cache()
    todo = [o for o in targets if o not in cache]
    if args.limit > 0:
        todo = todo[:args.limit]
    print(f"To process this run: {len(todo)}\n")

    if not todo:
        print("Nothing to do — all owners already cached.")
        return _write_outputs(cache, all_df)

    session = requests.Session()
    session.headers.update(REST_HEADERS)

    processed = 0
    resolved  = 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {
            ex.submit(resolve_owner, session, o, owner_repo[o], args.min_sleep): o
            for o in todo
        }
        for fut in as_completed(futs):
            owner = futs[fut]
            try:
                rec = fut.result()
            except Exception as e:
                rec = {
                    "owner_login":      owner,
                    "location_raw":     "",
                    "inferred_country": "not_specified",
                    "confidence":       "none",
                    "source":           f"error:{e}",
                }
            cache[owner] = rec
            processed += 1
            if rec["inferred_country"] != "not_specified":
                resolved += 1

            if processed % args.flush_every == 0:
                save_cache(cache)
                dt = time.time() - t0
                rate = processed / dt if dt > 0 else 0
                eta  = (len(todo) - processed) / rate / 60 if rate > 0 else 0
                print(
                    f"  {processed:>6}/{len(todo)}  resolved={resolved}"
                    f"  ({100*resolved/processed:.1f}%)  rate={rate:.1f}/s  ETA={eta:.0f}min"
                )

    save_cache(cache)
    print(f"\nRun complete: processed={processed}  newly_resolved={resolved}"
          f"  ({100*resolved/processed:.1f}%)\n")

    return _write_outputs(cache, all_df)


def _write_outputs(cache: dict, all_df: pd.DataFrame) -> None:
    """Write owner_locations_e.csv and patch owner_locations_all.csv."""

    # Build stage2e results dataframe
    records = list(cache.values())
    df_e = pd.DataFrame(records)
    df_e.to_csv(OUT_E, index=False)
    print(f"Wrote {OUT_E}")

    resolved_df = df_e[df_e["inferred_country"] != "not_specified"]
    print(f"  Total in cache:   {len(df_e)}")
    print(f"  Resolved:         {len(resolved_df)}")
    if len(resolved_df):
        print("\nTop countries resolved:")
        print(resolved_df["inferred_country"].value_counts().head(15).to_string())
        print("\nTop sources:")
        print(resolved_df["source"].value_counts().head(10).to_string())

    if resolved_df.empty:
        print("\nNo new resolutions — owner_locations_all.csv unchanged.")
        return

    # Patch owner_locations_all.csv
    new_entries = resolved_df[["owner_login", "location_raw",
                                "inferred_country", "confidence", "source"]].copy()
    # Only update rows that are still not_specified
    idx_unresolved = all_df[all_df["inferred_country"] == "not_specified"]["owner_login"]
    to_update = new_entries[new_entries["owner_login"].isin(idx_unresolved)]

    # Remove old not_specified rows for these owners and append resolved ones
    all_updated = all_df[~all_df["owner_login"].isin(to_update["owner_login"])]
    all_updated = pd.concat([all_updated, to_update], ignore_index=True)
    all_updated.to_csv(ALL_FILE, index=False)

    old_res = (all_df["inferred_country"] != "not_specified").sum()
    new_res = (all_updated["inferred_country"] != "not_specified").sum()
    total   = len(all_updated)
    print(f"\nUpdated {ALL_FILE.name}")
    print(f"  Before: {old_res}/{total} resolved ({100*old_res/total:.1f}%)")
    print(f"  After:  {new_res}/{total} resolved ({100*new_res/total:.1f}%)")
    print(f"  Gain:   +{new_res - old_res} owners")


if __name__ == "__main__":
    main()

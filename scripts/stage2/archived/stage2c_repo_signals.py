#!/usr/bin/env python3
"""
Stage 2c — Repo-Level Signals (S7, S8, S9)
===========================================
Reads owner_signals.csv from Stage 2b and processes only owners who still
need more evidence (needs_more = True, i.e. total_score < 10 and not
hard_negative). Applies three repo-level signals:

  S7 (7 pts) — Contributor consensus
    Fetches top-20 contributors per repo via REST API.
    Batch-fetches contributor location profiles via GraphQL.
    If ≥ 40% of contributors with disclosed locations are confirmed Egyptian
    AND at least MIN_CONTRIBUTORS_WITH_LOC have locations → +7 points.

    Rationale: Developers collaborate with peers in their geographic area.
    An Egyptian developer's repos will disproportionately have Egyptian
    contributors even if the owner's own profile has no location set.

  S8 (3 pts) — Arabic README
    Fetches README.md and CONTRIBUTING.md via GraphQL.
    Counts Arabic Unicode characters (U+0600–U+06FF) as a fraction
    of all alphabetic characters in the text.
    If Arabic ratio > 10% → +3 points.

  S9 (4 pts) — Egyptian dummy data
    Scans README + CONTRIBUTING text for Egyptian-specific patterns:
      - Egyptian mobile prefixes: 010, 011, 012, 015 (10-digit format)
      - Country code: +20
      - Currency: EGP or "Egyptian Pound"
      - National ID: 14-digit number starting with 2 or 3
    → +4 points if any pattern found (capped at 4 total for S9).

INPUTS
------
  data/stage2/owner_signals.csv    — Stage 2b output
  data/stage1/sample_corpus.csv    — to find repos belonging to each owner

OUTPUTS
-------
  data/stage2/owner_signals_full.csv  — all 9 signals populated
  data/stage2/checkpoint_2c.csv       — resume support

USAGE
-----
  export GITHUB_TOKEN=your_token_here
  python3 stage2c_repo_signals.py
"""

import os
import re
import sys
import json
import time
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

# ── Configuration ─────────────────────────────────────────────────────────────
TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    sys.exit("ERROR: GITHUB_TOKEN environment variable not set.")

SAVE_EVERY                     = 50    # checkpoint every N owners processed
MAX_RETRIES                    = 6
MAX_CONTRIBUTORS_PER_REPO      = 20    # top N contributors fetched per repo
MIN_CONTRIBUTORS_WITH_LOC      = 3     # min located contributors for S7 to fire
EGYPTIAN_CONTRIBUTOR_THRESHOLD = 0.40  # 40% Egyptian for S7
ARABIC_RATIO_THRESHOLD         = 0.10  # >10% Arabic alphabetic chars for S8
README_BATCH_SIZE              = 10    # repos per GraphQL request for READMEs
PROFILE_BATCH_SIZE             = 50    # contributor logins per GraphQL batch

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR     = Path(__file__).parent
DATA_DIR       = SCRIPT_DIR / "../../data"
SIGNALS_CSV    = DATA_DIR / "stage2/owner_signals.csv"
CORPUS_CSV     = DATA_DIR / "stage1/sample_corpus.csv"
OUTPUT_CSV     = DATA_DIR / "stage2/owner_signals_full.csv"
CHECKPOINT_CSV = DATA_DIR / "stage2/checkpoint_2c.csv"

REST_URL    = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"
REST_HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
GQL_HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# ── Egyptian location terms (same as prior stages) ────────────────────────────
EGYPTIAN_LOCATION_TERMS = [
    "egypt", "cairo", "alexandria", "giza", "luxor", "aswan", "suez",
    "port said", "mansoura", "tanta", "zagazig", "ismailia",
    "sharm el sheikh", "sharm", "hurghada", "helwan", "heliopolis",
    "maadi", "nasr city", "new cairo", "6th of october", "october city",
    "dokki", "mohandessin", "zamalek", "asyut", "sohag", "qena",
    "beni suef", "fayoum", "minya", "damanhour",
    "مصر", "القاهرة", "الإسكندرية", "الجيزة", "الأقصر", "أسوان",
    "السويس", "بورسعيد", "المنصورة", "طنطا", "الزقازيق", "الإسماعيلية",
    "شرم الشيخ", "الغردقة", "حلوان", "مدينة نصر", "القاهرة الجديدة",
    "أكتوبر", "الدقي", "المهندسين", "الزمالك", "أسيوط", "سوهاج",
]

# ── S9 Egyptian pattern regexes ───────────────────────────────────────────────
RE_EGY_MOBILE   = re.compile(r'\b0(10|11|12|15)\d{8}\b')
RE_COUNTRY_CODE = re.compile(r'\+20[\s\-]?\d')
RE_EGP          = re.compile(r'\bEGP\b|\bEgyptian\s+Pound\b', re.IGNORECASE)
RE_NID          = re.compile(r'\b[23]\d{13}\b')


def is_egyptian_location(location: str) -> bool:
    if not location or not location.strip():
        return False
    loc_lower = location.lower().strip()
    return any(term.lower() in loc_lower for term in EGYPTIAN_LOCATION_TERMS)


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def sleep_until(reset_iso: str):
    try:
        reset = datetime.fromisoformat(reset_iso.replace("Z", "+00:00"))
        wait  = (reset - datetime.now(timezone.utc)).total_seconds() + 5
    except Exception:
        wait = 60
    wait = max(wait, 5)
    print(f"  [RATE LIMIT] Sleeping {int(wait)}s until reset...")
    time.sleep(wait)


def rest_get(url: str, params: dict = None):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, headers=REST_HEADERS, params=params, timeout=30)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout):
            time.sleep(2 ** attempt)
            continue

        if r.status_code in (403, 429):
            reset = r.headers.get("X-RateLimit-Reset")
            wait  = max(int(reset) - time.time(), 0) + 5 if reset else 60
            time.sleep(wait)
            continue

        if r.status_code in (404, 451):
            return None   # not found / blocked

        if r.status_code in (499, 502, 503, 504):
            time.sleep(2 ** attempt)
            continue

        if r.status_code != 200:
            return None

        return r.json()

    return None


def graphql_post(query: str) -> dict:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.post(
                GRAPHQL_URL,
                json={"query": query},
                headers=GQL_HEADERS,
                timeout=30,
            )
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout):
            time.sleep(2 ** attempt)
            continue

        if r.status_code in (403, 429):
            reset = r.headers.get("X-RateLimit-Reset")
            wait  = max(int(reset) - time.time(), 0) + 5 if reset else 60
            time.sleep(wait)
            continue

        if r.status_code in (499, 502, 503, 504):
            time.sleep(2 ** attempt)
            continue

        if r.status_code != 200:
            return {}

        data   = r.json()
        errors = data.get("errors", [])
        if errors:
            types = {e.get("type") for e in errors}
            if "RATE_LIMITED" in types:
                reset = (data.get("data") or {}).get("rateLimit", {}).get("resetAt")
                sleep_until(reset) if reset else time.sleep(60)
                continue
            for e in errors:
                if e.get("type") not in ("NOT_FOUND", "FORBIDDEN"):
                    print(f"  [GQL WARNING] {e.get('message', '')[:100]}")

        rl = ((data.get("data") or {}).get("rateLimit") or {})
        if rl.get("remaining", 999) < 50:
            sleep_until(rl.get("resetAt", ""))

        return data.get("data") or {}

    return {}


# ── S7: Contributor consensus ─────────────────────────────────────────────────

def fetch_contributors(owner: str, repo: str) -> list:
    """Fetch top-N contributor logins for a repo via REST."""
    url    = f"{REST_URL}/repos/{owner}/{repo}/contributors"
    result = rest_get(url, params={"per_page": MAX_CONTRIBUTORS_PER_REPO, "anon": "false"})
    if not result or not isinstance(result, list):
        return []
    return [
        c["login"] for c in result
        if c.get("type") == "User" and c.get("login")
    ]


def build_profile_query(logins: list) -> str:
    """GraphQL query to fetch login + location for a batch of users."""
    fragments = []
    for idx, login in enumerate(logins):
        l = login.replace('"', "").replace("'", "").strip()
        fragments.append(f'u{idx}: user(login: "{l}") {{ login location }}')
    return "{ rateLimit { remaining resetAt } " + " ".join(fragments) + " }"


def batch_fetch_locations(logins: list, cache: dict) -> dict:
    """
    Fetch locations for logins not already in cache.
    Returns updated cache dict.
    """
    unknown = [l for l in logins if l not in cache]
    if not unknown:
        return cache

    for start in range(0, len(unknown), PROFILE_BATCH_SIZE):
        batch = unknown[start: start + PROFILE_BATCH_SIZE]
        data  = graphql_post(build_profile_query(batch))
        for idx, login in enumerate(batch):
            profile       = data.get(f"u{idx}") or {}
            cache[login]  = profile.get("location") or None
        time.sleep(0.2)

    return cache


def score_s7(owner_login: str, repos: list, loc_cache: dict) -> tuple:
    """
    S7: Contributor consensus.
    Collects all contributors across the owner's repos, fetches their
    locations, and scores if ≥40% of located contributors are Egyptian.
    Returns (score, evidence, updated_cache).
    """
    all_contributors = set()
    for repo_name in repos:
        logins = fetch_contributors(owner_login, repo_name)
        for l in logins:
            if l.lower() != owner_login.lower():
                all_contributors.add(l)
        time.sleep(0.2)

    if not all_contributors:
        return 0, None, loc_cache

    loc_cache = batch_fetch_locations(list(all_contributors), loc_cache)

    located_count  = 0
    egyptian_count = 0
    egyptian_names = []

    for login in all_contributors:
        loc = (loc_cache.get(login) or "").strip()
        if not loc:
            continue
        located_count += 1
        if is_egyptian_location(loc):
            egyptian_count += 1
            egyptian_names.append(login)

    if located_count < MIN_CONTRIBUTORS_WITH_LOC:
        return 0, None, loc_cache

    ratio = egyptian_count / located_count
    if ratio >= EGYPTIAN_CONTRIBUTOR_THRESHOLD:
        evidence = (
            f"contributor_ratio:{ratio:.2f}|"
            f"egyptian:{egyptian_count}/{located_count}|"
            f"eg_contributors:{','.join(egyptian_names[:5])}"
        )
        return 7, evidence, loc_cache

    return 0, None, loc_cache


# ── S8 + S9: README signals ───────────────────────────────────────────────────

def build_readme_query(repo_pairs: list) -> str:
    """
    GraphQL query to fetch README.md and CONTRIBUTING.md for a batch of repos.
    repo_pairs: list of (owner, repo_name) tuples.
    """
    fragments = []
    for idx, (owner, name) in enumerate(repo_pairs):
        o = owner.replace('"', "").replace("'", "").strip()
        n = name.replace('"', "").replace("'", "").strip()
        fragments.append(f"""
        r{idx}: repository(owner: "{o}", name: "{n}") {{
            readme:       object(expression: "HEAD:README.md")       {{ ... on Blob {{ text }} }}
            readme_lc:    object(expression: "HEAD:readme.md")       {{ ... on Blob {{ text }} }}
            contributing: object(expression: "HEAD:CONTRIBUTING.md") {{ ... on Blob {{ text }} }}
        }}
        """)
    return "{ rateLimit { remaining resetAt } " + " ".join(fragments) + " }"


def arabic_ratio(text: str) -> float:
    """Fraction of alphabetic characters that are Arabic (U+0600–U+06FF)."""
    if not text:
        return 0.0
    alpha = [c for c in text if c.isalpha()]
    if not alpha:
        return 0.0
    arabic = sum(1 for c in alpha if '\u0600' <= c <= '\u06FF')
    return arabic / len(alpha)


def score_s8_s9(texts: list) -> tuple:
    """
    texts: list of text strings (READMEs / CONTRIBUTING files).
    Returns (s8_score, s9_score, s8_evidence, s9_evidence).
    """
    combined = "\n".join(t for t in texts if t)

    # S8 — Arabic README
    ratio       = arabic_ratio(combined)
    s8_score    = 3 if ratio > ARABIC_RATIO_THRESHOLD else 0
    s8_evidence = f"arabic_ratio:{ratio:.3f}" if s8_score else None

    # S9 — Egyptian dummy data patterns
    patterns_found = []
    if RE_EGY_MOBILE.search(combined):
        patterns_found.append("mobile_prefix")
    if RE_COUNTRY_CODE.search(combined):
        patterns_found.append("+20")
    if RE_EGP.search(combined):
        patterns_found.append("EGP")
    if RE_NID.search(combined):
        patterns_found.append("NID")

    s9_score    = 4 if patterns_found else 0
    s9_evidence = "patterns:" + ",".join(patterns_found) if patterns_found else None

    return s8_score, s9_score, s8_evidence, s9_evidence


def fetch_readme_texts(owner: str, repos: list) -> list:
    """
    Fetch README + CONTRIBUTING text for all repos belonging to owner.
    Returns list of non-empty text strings.
    """
    repo_pairs = [(owner, r) for r in repos]
    texts = []

    for start in range(0, len(repo_pairs), README_BATCH_SIZE):
        batch = repo_pairs[start: start + README_BATCH_SIZE]
        data  = graphql_post(build_readme_query(batch))

        for idx in range(len(batch)):
            repo_data = data.get(f"r{idx}") or {}
            for field in ("readme", "readme_lc", "contributing"):
                text = (repo_data.get(field) or {}).get("text") or ""
                if text.strip():
                    texts.append(text)

        time.sleep(0.3)

    return texts


# ── Classification (same logic as prior stages) ───────────────────────────────

def classify_preliminary(total_score: int, hard_negative: bool,
                          signals_fired: int) -> str:
    if hard_negative:
        return "not_egyptian"
    if total_score >= 10:
        return "egyptian_confirmed"
    if total_score >= 5:
        return "egyptian_probable"
    if total_score >= 1:
        return "egyptian_probable" if signals_fired >= 2 else "unconfirmed"
    return "unclassified"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    for path in [SIGNALS_CSV, CORPUS_CSV]:
        if not path.exists():
            sys.exit(f"ERROR: {path} not found.")

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    signals_df = pd.read_csv(SIGNALS_CSV)
    corpus_df  = pd.read_csv(CORPUS_CSV)
    total_owners = len(signals_df)

    # Build owner_login → list of repo_names from sample corpus
    owner_repos: dict = (
        corpus_df.groupby("owner_login")["repo_name"]
        .apply(list)
        .to_dict()
    )

    # Filter to owners needing repo signals
    to_process = signals_df[signals_df["needs_more"] == True].copy()
    print(f"Loaded {total_owners:,} owners from Stage 2b.")
    print(f"Owners needing repo signals: {len(to_process):,}\n")

    # Pre-populate location cache with already-known profiles (avoids re-fetching)
    loc_cache: dict = {}
    for _, row in signals_df.iterrows():
        loc = str(row.get("location_raw") or "").strip()
        if loc:
            loc_cache[str(row["login"])] = loc

    # ── Resume support ────────────────────────────────────────────────────────
    if CHECKPOINT_CSV.exists():
        done_df      = pd.read_csv(CHECKPOINT_CSV)
        already_done = set(done_df["login"].astype(str))
        remaining    = to_process[~to_process["login"].astype(str).isin(already_done)]
        done_updates = done_df.to_dict("records")
        print(f"Resuming: {len(already_done)} done, {len(remaining)} remaining.\n")
    else:
        remaining    = to_process
        done_updates = []

    all_updates = done_updates.copy()
    total       = len(remaining)

    for i, row in enumerate(remaining.itertuples(index=False), 1):
        login = str(row.login)
        repos = owner_repos.get(login, [])

        # S7 — contributor consensus
        s7_score, ev7, loc_cache = score_s7(login, repos, loc_cache)

        # S8 + S9 — README signals
        texts = fetch_readme_texts(login, repos)
        s8_score, s9_score, ev8, ev9 = score_s8_s9(texts)

        all_updates.append({
            "login":    login,
            "s7_score": s7_score,
            "s8_score": s8_score,
            "s9_score": s9_score,
            "ev7":      ev7,
            "ev8":      ev8,
            "ev9":      ev9,
        })

        any_fired = any(x > 0 for x in [s7_score, s8_score, s9_score])
        if any_fired or (i % 100 == 0):
            print(f"  [{i:>5}/{total}] {login:<30}  "
                  f"S7:{s7_score}  S8:{s8_score}  S9:{s9_score}")

        # Checkpoint
        if i % SAVE_EVERY == 0:
            pd.DataFrame(all_updates).to_csv(CHECKPOINT_CSV, index=False)
            print(f"  [Checkpoint saved at owner {i}]")

        time.sleep(0.1)

    # ── Apply updates back to signals_df ──────────────────────────────────────
    updates_df = pd.DataFrame(all_updates).set_index("login")

    for login, upd in updates_df.iterrows():
        mask = signals_df["login"].astype(str) == str(login)
        if not mask.any():
            continue

        signals_df.loc[mask, "s7_score"] = upd["s7_score"]
        signals_df.loc[mask, "s8_score"] = upd["s8_score"]
        signals_df.loc[mask, "s9_score"] = upd["s9_score"]

        # Merge new evidence into existing evidence_json
        existing_ev = {}
        try:
            existing_ev = json.loads(
                signals_df.loc[mask, "evidence_json"].values[0] or "{}"
            )
        except Exception:
            pass
        for key, val in [("s7", upd.get("ev7")),
                         ("s8", upd.get("ev8")),
                         ("s9", upd.get("ev9"))]:
            if val and not (isinstance(val, float) and pd.isna(val)):
                existing_ev[key] = val
        signals_df.loc[mask, "evidence_json"] = json.dumps(
            existing_ev, ensure_ascii=False
        )

    # Recalculate totals across all 9 signals
    score_cols = ["s1_score", "s2_score", "s3_score", "s4_score",
                  "s5_score", "s6_score", "s7_score", "s8_score", "s9_score"]
    signals_df["total_score"] = signals_df[score_cols].sum(axis=1)

    def recompute_row(row):
        fired = sum(1 for col in score_cols if row[col] > 0)
        cls   = classify_preliminary(
            int(row["total_score"]),
            bool(row["hard_negative"]),
            fired,
        )
        needs = not bool(row["hard_negative"]) and int(row["total_score"]) < 10
        return pd.Series({
            "classification": cls,
            "signals_fired":  fired,
            "needs_more":     needs,
        })

    signals_df[["classification", "signals_fired", "needs_more"]] = (
        signals_df.apply(recompute_row, axis=1)
    )

    # Save full output (new file — keeps stage2 output intact)
    signals_df.to_csv(OUTPUT_CSV, index=False)

    # Clean up checkpoint
    if CHECKPOINT_CSV.exists():
        CHECKPOINT_CSV.unlink()

    # ── Summary ───────────────────────────────────────────────────────────────
    s7_total   = (signals_df["s7_score"] > 0).sum()
    s8_total   = (signals_df["s8_score"] > 0).sum()
    s9_total   = (signals_df["s9_score"] > 0).sum()
    cls_counts = signals_df["classification"].value_counts()
    needs_3b   = signals_df["needs_more"].sum()

    print(f"\n─── Stage 3a Summary ─────────────────────────────────────────────")
    print(f"Owners processed (S7+S8+S9)      : {len(to_process):,}")
    print(f"S7 (contributor consensus) fired  : {s7_total:,}")
    print(f"S8 (Arabic README) fired          : {s8_total:,}")
    print(f"S9 (Egyptian dummy data) fired    : {s9_total:,}")
    print(f"\nFinal classification (S1–S9):")
    print(f"  {'Label':<25} {'Count':>7}  {'%':>6}")
    print(f"  {'-'*42}")
    for label, count in cls_counts.items():
        pct = count / total_owners * 100
        print(f"  {label:<25} {count:>7}  {pct:>5.1f}%")
    print(f"\nOwners with total_score < 10 after all 9 signals: {needs_3b:,}")
    print(f"  (These will be classified as 'unconfirmed' or 'unclassified' in Stage 2d)")
    print(f"\nSaved: {OUTPUT_CSV}")
    print(f"\nNext: run stage2d_finalize.py")


if __name__ == "__main__":
    main()

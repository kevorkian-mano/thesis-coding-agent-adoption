#!/usr/bin/env python3
"""
Stage 2a — Owner Profile Fetch & Profile-Level Signals (S1–S4)
==============================================================
Reads sample_corpus.csv, extracts unique repo owners, batch-fetches their
GitHub profiles via GraphQL, and applies the first four location signals.

Every owner gets a score sheet. Signals are not binary — each signal that
fires adds points. Final classification happens in Stage 2d after all 9
signals are collected. This script outputs preliminary scores so that
Stage 2b and Stage 3a only process owners who still need more evidence.

Signals applied here
--------------------
  S1 (10 pts) — Profile location field contains Egyptian keyword
                 HARD NEGATIVE: location set but non-Egyptian → not_egyptian
  S2 ( 5 pts) — Bio has Arabic text OR Egyptian keywords/universities
  S3 ( 5 pts) — Company field has Egyptian org name or .eg domain
  S4 ( 8 pts) — Email has .eg TLD or Egyptian university domain

Score interpretation (preliminary — final thresholds applied in Stage 2d)
--------------------------------------------------------------------------
  ≥ 10  →  egyptian_confirmed   (no further signals needed)
   5–9  →  egyptian_probable    (pass to Stage 2b for social signals)
   1–4  →  suspicious           (pass to Stage 2b)
     0  →  unknown              (pass to Stage 2b)
  hard negative → not_egyptian  (skip all further stages)

INPUTS
------
  data/stage1/sample_corpus.csv

OUTPUTS
-------
  data/stage2/owner_signals.csv     — one row per unique owner, all scores
  data/stage2/checkpoint_2a.csv     — resume support

USAGE
-----
  export GITHUB_TOKEN=your_token_here
  python3 stage2a_owner_profiles.py
"""

import os
import sys
import re
import time
import json
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

# ── Configuration ─────────────────────────────────────────────────────────────
TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    sys.exit("ERROR: GITHUB_TOKEN environment variable not set.")

BATCH_SIZE  = 50    # owners per GraphQL request
SAVE_EVERY  = 200   # checkpoint every N owners
MAX_RETRIES = 6

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR     = Path(__file__).parent
DATA_DIR       = SCRIPT_DIR / "../../data"
CORPUS_IN      = DATA_DIR / "stage1/sample_corpus.csv"
SIGNALS_OUT    = DATA_DIR / "stage2/owner_signals.csv"
CHECKPOINT_CSV = DATA_DIR / "stage2/checkpoint_2a.csv"

GRAPHQL_URL = "https://api.github.com/graphql"
GQL_HEADERS = {"Authorization": f"Bearer {TOKEN}"}


# ── Egyptian keyword lists ────────────────────────────────────────────────────

# S1 — location field keywords (English + Arabic)
EGYPTIAN_LOCATION_TERMS = [
    # English
    "egypt", "cairo", "alexandria", "giza", "luxor", "aswan", "suez",
    "port said", "mansoura", "tanta", "zagazig", "ismailia",
    "sharm el sheikh", "sharm", "hurghada", "helwan", "heliopolis",
    "maadi", "nasr city", "new cairo", "6th of october", "october city",
    "dokki", "mohandessin", "zamalek", "asyut", "sohag", "qena",
    "beni suef", "fayoum", "minya", "damanhour", "kafr",
    # Arabic
    "مصر", "القاهرة", "الإسكندرية", "الجيزة", "الأقصر", "أسوان",
    "السويس", "بورسعيد", "المنصورة", "طنطا", "الزقازيق", "الإسماعيلية",
    "شرم الشيخ", "الغردقة", "حلوان", "مدينة نصر", "القاهرة الجديدة",
    "أكتوبر", "الدقي", "المهندسين", "الزمالك", "أسيوط", "سوهاج",
    "قنا", "بني سويف", "الفيوم", "المنيا", "دمنهور",
]

# S2 — bio keywords
EGYPTIAN_BIO_TERMS = [
    "egyptian", "egypt", "cairo", "alexandria", "giza",
    "مصر", "مصري", "مصرية", "القاهرة", "الإسكندرية", "الجيزة",
]

EGYPTIAN_UNIVERSITY_ABBREVIATIONS = [
    "guc", "auc", "giu", "aast", "must", "msa", "bue", "met",
    "nile university", "future university", "misr university",
]

EGYPTIAN_UNIVERSITY_FULL = [
    "cairo university", "ain shams", "helwan university",
    "alexandria university", "mansoura university", "zagazig university",
    "benha university", "american university in cairo",
    "german university in cairo", "german international university",
    "arab academy", "british university in egypt",
    "modern science and arts", "october university",
]

# S3 — company keywords (same location + org terms)
EGYPTIAN_COMPANY_TERMS = (
    EGYPTIAN_LOCATION_TERMS[:10]      # top location terms
    + EGYPTIAN_UNIVERSITY_FULL
    + ["egypt", "egyptian", ".eg", "cairo", "alexandria"]
)

# S4 — email domains
EGYPTIAN_EMAIL_DOMAINS = [
    ".eg",
    "aucegypt.edu", "guc.edu.eg", "giu.edu.eg", "cu.edu.eg",
    "alexu.edu.eg", "must.edu.eg", "msa.edu.eg", "bue.edu.eg",
    "nileuniversity.edu.eg", "fci-cu.edu.eg", "eng.asu.edu.eg",
]


# ── Helper: Arabic text detection ────────────────────────────────────────────

def has_arabic(text: str) -> bool:
    """Returns True if text contains any Arabic Unicode characters."""
    if not text:
        return False
    return any("\u0600" <= c <= "\u06ff" for c in text)


def arabic_ratio(text: str) -> float:
    """Returns fraction of characters that are Arabic."""
    if not text:
        return 0.0
    arabic_chars = sum(1 for c in text if "\u0600" <= c <= "\u06ff")
    return arabic_chars / len(text)


# ── Signal scoring functions ──────────────────────────────────────────────────

def score_s1(location: str) -> tuple:
    """
    S1: Profile location field.
    Returns (score, evidence).
      10  → location contains Egyptian keyword
      -1  → location is set but NOT Egyptian (hard negative)
       0  → location is empty/blank
    """
    if not location or not location.strip():
        return 0, None

    loc_lower = location.lower().strip()
    for term in EGYPTIAN_LOCATION_TERMS:
        if term.lower() in loc_lower:
            return 10, f"location_match:{location[:80]}"

    # Location is set but no Egyptian keyword found → hard negative
    return -1, f"non_egyptian_location:{location[:60]}"


def score_s2(bio: str) -> tuple:
    """
    S2: Bio text — Arabic chars or Egyptian keywords.
    Returns (score, evidence).
    """
    if not bio or not bio.strip():
        return 0, None

    bio_lower = bio.lower()
    evidence  = []

    # Arabic text in bio
    if has_arabic(bio):
        ratio = arabic_ratio(bio)
        evidence.append(f"arabic_text:{ratio:.2f}")

    # Egyptian keywords
    for term in EGYPTIAN_BIO_TERMS:
        if term.lower() in bio_lower:
            evidence.append(f"bio_keyword:{term}")
            break

    # University abbreviations (whole word match to avoid false positives)
    for abbr in EGYPTIAN_UNIVERSITY_ABBREVIATIONS:
        pattern = r"\b" + re.escape(abbr) + r"\b"
        if re.search(pattern, bio_lower):
            evidence.append(f"university_abbr:{abbr}")
            break

    # Full university names
    for name in EGYPTIAN_UNIVERSITY_FULL:
        if name.lower() in bio_lower:
            evidence.append(f"university:{name}")
            break

    if evidence:
        return 5, ",".join(evidence)
    return 0, None


def score_s3(company: str) -> tuple:
    """
    S3: Company field — Egyptian org names or .eg domain.
    Returns (score, evidence).
    """
    if not company or not company.strip():
        return 0, None

    company_lower = company.lower()

    for term in EGYPTIAN_COMPANY_TERMS:
        if term.lower() in company_lower:
            return 5, f"company_match:{company[:60]}"

    if has_arabic(company):
        return 5, f"arabic_company:{company[:60]}"

    return 0, None


def score_s4(email: str) -> tuple:
    """
    S4: Email domain — .eg TLD or Egyptian university domain.
    Returns (score, evidence).
    """
    if not email or not email.strip():
        return 0, None

    email_lower = email.lower().strip()

    for domain in EGYPTIAN_EMAIL_DOMAINS:
        if email_lower.endswith(domain) or f"@{domain.lstrip('.')}" in email_lower:
            return 8, f"email_domain:{email[:60]}"

    return 0, None


def classify_preliminary(total_score: int, hard_negative: bool,
                          signals_fired: int = 0) -> str:
    """
    Preliminary classification based on S1–S4 only.
    Used to decide which owners need further signals (Stage 2b, Stage 3a).
    Final classification with full thresholds is applied in Stage 2d.

    Thresholds:
      egyptian_confirmed  — score ≥ 10
      egyptian_probable   — score 5–9, OR score 1–4 with ≥2 signals fired
      unconfirmed         — score 1–4 with only 1 signal fired
      unclassified        — score 0, no signals found
      not_egyptian        — S1 hard negative (explicit non-Egyptian location)
    """
    if hard_negative:
        return "not_egyptian"
    if total_score >= 10:
        return "egyptian_confirmed"
    if total_score >= 5:
        return "egyptian_probable"
    if total_score >= 1:
        return "egyptian_probable" if signals_fired >= 2 else "unconfirmed"
    return "unclassified"


# ── Network helpers ───────────────────────────────────────────────────────────

def sleep_until(reset_iso: str):
    try:
        reset = datetime.fromisoformat(reset_iso.replace("Z", "+00:00"))
        wait  = (reset - datetime.now(timezone.utc)).total_seconds() + 5
    except Exception:
        wait = 60
    wait = max(wait, 5)
    print(f"  [RATE LIMIT] Sleeping {int(wait)}s until reset...")
    time.sleep(wait)


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
                requests.exceptions.Timeout) as e:
            wait = 2 ** attempt
            print(f"  [NETWORK] {e}, retry {attempt} in {wait}s...")
            time.sleep(wait)
            continue

        if r.status_code in (403, 429):
            reset = r.headers.get("X-RateLimit-Reset")
            wait  = max(int(reset) - time.time(), 0) + 5 if reset else 60
            print(f"  [RATE LIMIT] HTTP {r.status_code}, sleeping {int(wait)}s...")
            time.sleep(wait)
            continue

        if r.status_code in (499, 502, 503, 504):
            wait = 2 ** attempt
            print(f"  [SERVER ERROR] HTTP {r.status_code}, retry {attempt} in {wait}s...")
            time.sleep(wait)
            continue

        if r.status_code != 200:
            print(f"  [HTTP {r.status_code}] {r.text[:200]}")
            return {}

        data   = r.json()
        errors = data.get("errors", [])

        if errors:
            types = {e.get("type") for e in errors}
            if "RATE_LIMITED" in types:
                reset = (data.get("data") or {}).get("rateLimit", {}).get("resetAt")
                sleep_until(reset) if reset else time.sleep(60)
                continue
            # Partial errors (e.g. one user not found) — log and continue
            for e in errors:
                if e.get("type") != "NOT_FOUND":
                    print(f"  [GQL WARNING] {e.get('message', '')[:100]}")

        rl = ((data.get("data") or {}).get("rateLimit") or {})
        if rl.get("remaining", 999) < 50:
            sleep_until(rl.get("resetAt", ""))

        return data.get("data") or {}

    return {}


# ── GraphQL query builder ─────────────────────────────────────────────────────

def build_profile_query(logins: list) -> str:
    """
    Fetches profile fields for up to BATCH_SIZE users in one request.
    Uses aliased user() calls so results are keyed by index.
    """
    fragments = []
    for idx, login in enumerate(logins):
        l = login.replace('"', "").replace("'", "").strip()
        fragments.append(f"""
        u{idx}: user(login: "{l}") {{
            login
            name
            location
            bio
            company
            email
            websiteUrl
        }}
        """)
    return ("{ rateLimit { remaining resetAt } "
            + " ".join(fragments) + " }")


# ── Process one batch ─────────────────────────────────────────────────────────

def process_batch(logins: list) -> list:
    """Fetches profiles and scores S1–S4 for a batch of owner logins."""
    query = build_profile_query(logins)
    data  = graphql_post(query)

    results = []
    for idx, login in enumerate(logins):
        profile = data.get(f"u{idx}") or {}

        location  = (profile.get("location")  or "").strip()
        bio       = (profile.get("bio")       or "").strip()
        company   = (profile.get("company")   or "").strip()
        email     = (profile.get("email")     or "").strip()
        name      = (profile.get("name")      or "").strip()
        website   = (profile.get("websiteUrl") or "").strip()

        # Score each signal
        s1, ev1 = score_s1(location)
        hard_negative = (s1 == -1)
        s1_score = 0 if hard_negative else s1

        s2_score, ev2 = score_s2(bio)
        s3_score, ev3 = score_s3(company)
        s4_score, ev4 = score_s4(email)

        # Hard negative overrides all other signals
        if hard_negative:
            s2_score = s3_score = s4_score = 0

        total_score   = s1_score + s2_score + s3_score + s4_score
        signals_fired = sum(1 for s in [s1_score, s2_score, s3_score, s4_score] if s > 0)
        classification = classify_preliminary(total_score, hard_negative, signals_fired)

        # Build evidence JSON
        evidence = {}
        if ev1: evidence["s1"] = ev1
        if ev2: evidence["s2"] = ev2
        if ev3: evidence["s3"] = ev3
        if ev4: evidence["s4"] = ev4

        # needs_more_signals: True = pass to Stage 2b
        needs_more = not hard_negative and total_score < 10

        results.append({
            "login":            login,
            "name":             name,
            "location_raw":     location,
            "bio":              bio[:200] if bio else "",
            "company":          company,
            "email":            email,
            "website":          website,
            "s1_score":         s1_score,
            "s2_score":         s2_score,
            "s3_score":         s3_score,
            "s4_score":         s4_score,
            "s5_score":         0,   # filled by Stage 2b
            "s6_score":         0,   # filled by Stage 2b
            "s7_score":         0,   # filled by Stage 3a
            "s8_score":         0,   # filled by Stage 3a
            "s9_score":         0,   # filled by Stage 3a
            "total_score":      total_score,
            "hard_negative":    hard_negative,
            "classification":   classification,
            "needs_more":       needs_more,
            "evidence_json":    json.dumps(evidence, ensure_ascii=False),
        })

    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not CORPUS_IN.exists():
        sys.exit(f"ERROR: {CORPUS_IN} not found. Run stage1c first.")

    SIGNALS_OUT.parent.mkdir(parents=True, exist_ok=True)

    corpus_df = pd.read_csv(CORPUS_IN)

    # Extract unique owners
    all_owners = (
        corpus_df["owner_login"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )
    total = len(all_owners)
    print(f"Loaded {len(corpus_df):,} repos → {total:,} unique owners.\n")

    # ── Resume support ────────────────────────────────────────────────────────
    if CHECKPOINT_CSV.exists():
        done_df        = pd.read_csv(CHECKPOINT_CSV)
        already_done   = set(done_df["login"].astype(str))
        remaining      = [o for o in all_owners if o not in already_done]
        all_results    = done_df.to_dict("records")
        print(f"Resuming: {len(already_done)} done, {len(remaining)} remaining.\n")
    else:
        remaining   = all_owners
        all_results = []

    # ── Process in batches ────────────────────────────────────────────────────
    total_batches = (len(remaining) + BATCH_SIZE - 1) // BATCH_SIZE

    for b_num, start in enumerate(range(0, len(remaining), BATCH_SIZE), 1):
        batch   = remaining[start: start + BATCH_SIZE]
        results = process_batch(batch)
        all_results.extend(results)

        # Progress line
        confirmed = sum(1 for r in results if r["classification"] == "egyptian_confirmed")
        probable  = sum(1 for r in results if r["classification"] == "egyptian_probable")
        neg       = sum(1 for r in results if r["hard_negative"])
        done_total = len(all_results)

        print(f"  [{b_num}/{total_batches}] +{len(batch)} owners "
              f"(confirmed:{confirmed} probable:{probable} not_eg:{neg}) "
              f"| total:{done_total}/{total}")

        # Checkpoint
        if b_num % (SAVE_EVERY // BATCH_SIZE) == 0:
            pd.DataFrame(all_results).to_csv(CHECKPOINT_CSV, index=False)
            print(f"  [Checkpoint saved — {done_total}/{total}]")

        time.sleep(0.5)

    # ── Save final output ─────────────────────────────────────────────────────
    out_df = pd.DataFrame(all_results)
    out_df.to_csv(SIGNALS_OUT, index=False)

    # Remove checkpoint
    if CHECKPOINT_CSV.exists():
        CHECKPOINT_CSV.unlink()

    # ── Summary ───────────────────────────────────────────────────────────────
    classification_counts = out_df["classification"].value_counts()
    needs_more_count      = out_df["needs_more"].sum()

    print(f"\n─── Stage 2a Summary ────────────────────────────────────────────")
    print(f"Unique owners processed : {total:,}")
    print(f"\nPreliminary classification (S1–S4 only):")
    print(f"  {'Label':<25} {'Count':>7}  {'%':>6}")
    print(f"  {'-'*42}")
    for label, count in classification_counts.items():
        pct = count / total * 100
        print(f"  {label:<25} {count:>7}  {pct:>5.1f}%")

    print(f"\nSignal coverage:")
    for signal in ["s1_score", "s2_score", "s3_score", "s4_score"]:
        fired = (out_df[signal] > 0).sum()
        print(f"  {signal}: fired for {fired:,} owners ({fired/total*100:.1f}%)")

    print(f"\nOwners needing further signals (Stage 2b): {needs_more_count:,}")
    print(f"\nSaved: {SIGNALS_OUT}")
    print(f"\nNext: run stage2b_social_signals.py")


if __name__ == "__main__":
    main()

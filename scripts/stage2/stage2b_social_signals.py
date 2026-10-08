#!/usr/bin/env python3
"""
Stage 2b — Social Signals (S5: Org Membership, S6: Network Inference)
======================================================================
Reads owner_signals.csv from Stage 2a and processes only owners who still
need more evidence (needs_more = True, i.e. total_score < 10 and not
hard_negative). Applies two social-level signals:

  S5 (7 pts) — Organization membership
    Fetches the user's GitHub organizations and checks their location fields.
    If any org has an Egyptian location → +7 points.

  S6 (5 pts) — Network inference
    Fetches the user's followers and following (top 50 each).
    Checks the raw location field of every connection.
    If ≥ 40% of connections with a disclosed location are Egyptian
    AND at least MIN_NETWORK_WITH_LOCATION connections have locations
    → +5 points.

    Rationale: developers follow and are followed by people in their
    professional/social circle. A blank-location Egyptian developer is
    likely to have a network skewed toward Egyptian accounts.

Why these are "social" signals (not "profile"):
  S1–S4 look at the owner's own profile fields.
  S5–S6 look at who the owner is associated with — their orgs and network.
  This distinction matters for the methodology chapter.

Batch design:
  Each user query fetches orgs (10) + followers (50) + following (50) = 110 nodes.
  GitHub GraphQL complexity cap is ~500 nodes per query.
  → Batch size: 4 users per request (4 × 110 = 440 nodes, safe margin).

Runtime estimate: 2,649 owners / 4 per batch = ~663 requests.
  At 0.5s sleep between requests ≈ 6–8 minutes.
  (GraphQL rate limit: 5,000 points/hour — well within budget.)

INPUTS
------
  data/stage2/owner_signals.csv     — Stage 2a output

OUTPUTS
-------
  data/stage2/owner_signals.csv     — updated in-place (s5, s6 columns filled)
  data/stage2/checkpoint_2b.csv     — resume support

USAGE
-----
  export GITHUB_TOKEN=your_token_here
  python3 stage2b_social_signals.py
"""

import os
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

BATCH_SIZE            = 4      # users per GraphQL request (110 nodes each)
SAVE_EVERY            = 100    # checkpoint every N owners processed
MAX_RETRIES           = 6
MIN_NETWORK_WITH_LOC  = 3      # minimum connections with location for S6 to fire
EGYPTIAN_NETWORK_THRESHOLD = 0.40   # 40% of located connections must be Egyptian

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR     = Path(__file__).parent
DATA_DIR       = SCRIPT_DIR / "../../data"
SIGNALS_CSV    = DATA_DIR / "stage2/owner_signals.csv"
CHECKPOINT_CSV = DATA_DIR / "stage2/checkpoint_2b.csv"

GRAPHQL_URL = "https://api.github.com/graphql"
GQL_HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# ── Egyptian location terms (same as Stage 2a) ────────────────────────────────
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


def is_egyptian_location(location: str) -> bool:
    """Returns True if a location string contains any Egyptian keyword."""
    if not location or not location.strip():
        return False
    loc_lower = location.lower().strip()
    return any(term.lower() in loc_lower for term in EGYPTIAN_LOCATION_TERMS)


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
            print(f"  [SERVER ERROR] HTTP {r.status_code}, retry {attempt}...")
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
            for e in errors:
                if e.get("type") not in ("NOT_FOUND", "FORBIDDEN"):
                    print(f"  [GQL WARNING] {e.get('message', '')[:100]}")

        rl = ((data.get("data") or {}).get("rateLimit") or {})
        if rl.get("remaining", 999) < 50:
            sleep_until(rl.get("resetAt", ""))

        return data.get("data") or {}

    return {}


# ── GraphQL query builder ─────────────────────────────────────────────────────

def build_social_query(logins: list) -> str:
    """
    Fetches for each user:
      - organizations (first 10): login + location
      - followers    (first 50): login + location
      - following    (first 50): login + location
    """
    fragments = []
    for idx, login in enumerate(logins):
        l = login.replace('"', "").replace("'", "").strip()
        fragments.append(f"""
        u{idx}: user(login: "{l}") {{
            login
            organizations(first: 10) {{
                nodes {{ login location }}
            }}
            followers(first: 50) {{
                nodes {{ login location }}
            }}
            following(first: 50) {{
                nodes {{ login location }}
            }}
        }}
        """)
    return ("{ rateLimit { remaining resetAt } "
            + " ".join(fragments) + " }")


# ── Signal scoring ────────────────────────────────────────────────────────────

def score_s5(orgs: list) -> tuple:
    """
    S5: Organization membership.
    Returns (score, evidence).
    Fires (+7) if any org has an Egyptian location.
    """
    if not orgs:
        return 0, None

    for org in orgs:
        loc = org.get("location") or ""
        if is_egyptian_location(loc):
            return 7, f"org:{org.get('login','?')}|loc:{loc[:50]}"

    return 0, None


def score_s6(followers: list, following: list) -> tuple:
    """
    S6: Network inference.
    Returns (score, evidence).

    Combines followers + following into one network pool.
    Counts connections with location set and how many are Egyptian.
    Fires (+5) if:
      - at least MIN_NETWORK_WITH_LOC connections have location set
      - egyptian_count / located_count >= EGYPTIAN_NETWORK_THRESHOLD
    """
    network = followers + following

    located_count  = 0
    egyptian_count = 0

    for person in network:
        loc = (person.get("location") or "").strip()
        if not loc:
            continue
        located_count += 1
        if is_egyptian_location(loc):
            egyptian_count += 1

    if located_count < MIN_NETWORK_WITH_LOC:
        return 0, None   # too few data points

    ratio = egyptian_count / located_count
    if ratio >= EGYPTIAN_NETWORK_THRESHOLD:
        return 5, (f"network_ratio:{ratio:.2f}|"
                   f"egyptian:{egyptian_count}/{located_count}")

    return 0, None


# ── Classification (same logic as Stage 2a) ───────────────────────────────────

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


# ── Process one batch ─────────────────────────────────────────────────────────

def process_batch(batch_df: pd.DataFrame) -> list:
    """
    Fetches social data and scores S5+S6 for a batch of owners.
    Returns list of update dicts: {login, s5_score, s6_score, evidence_update}.
    """
    logins = batch_df["login"].astype(str).tolist()
    query  = build_social_query(logins)
    data   = graphql_post(query)

    updates = []
    for idx, row in enumerate(batch_df.itertuples(index=False)):
        profile = data.get(f"u{idx}") or {}

        orgs      = (profile.get("organizations") or {}).get("nodes") or []
        followers = (profile.get("followers")     or {}).get("nodes") or []
        following = (profile.get("following")     or {}).get("nodes") or []

        s5_score, ev5 = score_s5(orgs)
        s6_score, ev6 = score_s6(followers, following)

        updates.append({
            "login":    row.login,
            "s5_score": s5_score,
            "s6_score": s6_score,
            "ev5":      ev5,
            "ev6":      ev6,
        })

    return updates


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not SIGNALS_CSV.exists():
        sys.exit(f"ERROR: {SIGNALS_CSV} not found. Run stage2a first.")

    signals_df = pd.read_csv(SIGNALS_CSV)
    total_owners = len(signals_df)

    # Filter to owners that need more signals
    to_process = signals_df[signals_df["needs_more"] == True].copy()
    print(f"Loaded {total_owners:,} owners from Stage 2a.")
    print(f"Owners needing social signals: {len(to_process):,}\n")

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

    # ── Process in batches ────────────────────────────────────────────────────
    total_batches = (len(remaining) + BATCH_SIZE - 1) // BATCH_SIZE
    all_updates   = done_updates.copy()

    for b_num, start in enumerate(range(0, len(remaining), BATCH_SIZE), 1):
        batch   = remaining.iloc[start: start + BATCH_SIZE]
        updates = process_batch(batch)
        all_updates.extend(updates)

        s5_fired = sum(1 for u in updates if u["s5_score"] > 0)
        s6_fired = sum(1 for u in updates if u["s6_score"] > 0)
        print(f"  [{b_num}/{total_batches}] +{len(batch)} "
              f"(S5 fired:{s5_fired} S6 fired:{s6_fired}) "
              f"| total done:{len(all_updates)}/{len(to_process)}")

        # Checkpoint
        if b_num % (SAVE_EVERY // BATCH_SIZE) == 0:
            pd.DataFrame(all_updates).to_csv(CHECKPOINT_CSV, index=False)
            print(f"  [Checkpoint saved]")

        time.sleep(0.5)

    # ── Apply updates back to signals_df ─────────────────────────────────────
    updates_df = pd.DataFrame(all_updates).set_index("login")

    for login, upd in updates_df.iterrows():
        mask = signals_df["login"].astype(str) == str(login)
        if not mask.any():
            continue

        signals_df.loc[mask, "s5_score"] = upd["s5_score"]
        signals_df.loc[mask, "s6_score"] = upd["s6_score"]

        # Update evidence_json — merge new evidence into existing
        existing_ev = {}
        try:
            existing_ev = json.loads(
                signals_df.loc[mask, "evidence_json"].values[0] or "{}"
            )
        except Exception:
            pass
        if upd.get("ev5"):
            existing_ev["s5"] = upd["ev5"]
        if upd.get("ev6"):
            existing_ev["s6"] = upd["ev6"]
        signals_df.loc[mask, "evidence_json"] = json.dumps(
            existing_ev, ensure_ascii=False
        )

    # Recalculate total_score, signals_fired, classification, needs_more
    score_cols    = ["s1_score","s2_score","s3_score","s4_score",
                     "s5_score","s6_score"]
    signals_df["total_score"] = signals_df[score_cols].sum(axis=1)

    def recompute_row(row):
        fired = sum(1 for col in score_cols if row[col] > 0)
        cls   = classify_preliminary(
            int(row["total_score"]),
            bool(row["hard_negative"]),
            fired,
        )
        needs = not bool(row["hard_negative"]) and int(row["total_score"]) < 10
        return pd.Series({"classification": cls, "needs_more": needs})

    signals_df[["classification","needs_more"]] = (
        signals_df.apply(recompute_row, axis=1)
    )

    # Save final output
    signals_df.to_csv(SIGNALS_CSV, index=False)

    # Clean up checkpoint
    if CHECKPOINT_CSV.exists():
        CHECKPOINT_CSV.unlink()

    # ── Summary ───────────────────────────────────────────────────────────────
    s5_total = (signals_df["s5_score"] > 0).sum()
    s6_total = (signals_df["s6_score"] > 0).sum()
    needs_3a = signals_df["needs_more"].sum()
    cls_counts = signals_df["classification"].value_counts()

    print(f"\n─── Stage 2b Summary ────────────────────────────────────────────")
    print(f"Owners processed (S5+S6) : {len(to_process):,}")
    print(f"S5 (org membership) fired: {s5_total:,}")
    print(f"S6 (network inference) fired: {s6_total:,}")
    print(f"\nUpdated classification (S1–S6):")
    print(f"  {'Label':<25} {'Count':>7}  {'%':>6}")
    print(f"  {'-'*42}")
    for label, count in cls_counts.items():
        pct = count / total_owners * 100
        print(f"  {label:<25} {count:>7}  {pct:>5.1f}%")
    print(f"\nOwners needing Stage 3a (repo signals): {needs_3a:,}")
    print(f"\nSaved: {SIGNALS_CSV}")
    print(f"\nNext: run stage3a_repo_signals.py")


if __name__ == "__main__":
    main()

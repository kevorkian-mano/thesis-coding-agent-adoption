#!/usr/bin/env python3
"""
Stage 2e -- Commit Email TLD Validation
========================================
Validates stage2e_commit_email.py by running its inference on owners whose
country is ALREADY KNOWN from Pass 1 (GitHub location field).

Method
------
1. Sample owners from owner_locations_all.csv where source='location_field'
   (stratified across top countries for geographic diversity).
2. Find each owner's highest-commit corpus repository (same logic as stage2e).
3. Fetch up to 10 recent commit author emails via REST API (same call as stage2e).
4. Apply the ccTLD inference logic (identical to stage2e).
5. Compare inferred country vs known country and report accuracy.

This tells us: "For owners whose country is known, does the commit email ccTLD
signal agree?"

Output
------
  data/stage2/validation_results_stage2e.csv
    Columns: owner_login, known_country, inferred_country, match,
             emails_found, ccTLD_emails, confidence, repo_used

  Printed summary: precision, coverage, wrong predictions

Usage
-----
  export GITHUB_TOKEN=ghp_...
  python3 scripts/stage2/stage2e_validate.py [--sample N] [--seed S]
"""

import os, sys, time, argparse, requests
import pandas as pd
from pathlib import Path
from collections import Counter

ROOT      = Path(__file__).resolve().parents[2]
OUT_DIR   = ROOT / "data" / "stage2"
ALL_CSV   = OUT_DIR / "owner_locations_all.csv"
CORPUS    = ROOT / "data" / "stage1" / "global_corpus.csv"
OUT_CSV   = OUT_DIR / "validation_results_stage2e.csv"

TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    sys.exit("ERROR: GITHUB_TOKEN not set.")

REST_HEADERS = {
    "Authorization":        f"Bearer {TOKEN}",
    "Accept":               "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
REST_URL        = "https://api.github.com/repos/{owner}/{repo}/commits"
COMMITS_PER_REPO = 10
SLEEP_OK        = 1.0
SLEEP_RETRY     = 60

# Countries to stratify the sample across
SAMPLE_COUNTRIES = [
    "Germany", "France", "Brazil", "United Kingdom", "China",
    "India", "United States", "Russia", "Netherlands", "Japan",
    "Canada", "Italy", "Poland", "Sweden", "Spain",
]

# ── Identical to stage2e_commit_email.py ──────────────────────────────────────

GENERIC_PROVIDERS = {
    "gmail.com", "googlemail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "live.com", "icloud.com", "me.com", "mac.com", "aol.com", "protonmail.com",
    "proton.me", "pm.me", "mail.com", "gmx.com", "gmx.net", "fastmail.com",
    "zoho.com", "yandex.com", "yandex.ru", "ymail.com", "inbox.com",
    "msn.com", "users.noreply.github.com", "noreply.github.com", "example.com",
    "163.com", "126.com", "qq.com", "sina.com", "foxmail.com",
    "naver.com", "daum.net", "hanmail.net",
    "web.de", "t-online.de",
}

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
    ".au": "Australia",      ".nz": "New Zealand",
    ".ac": None, ".io": None, ".ai": None, ".app": None,
    ".dev": None, ".me": None, ".cc": None,
}


def email_to_country(email: str) -> str | None:
    if not email:
        return None
    email = email.strip().lower()
    if "@" not in email:
        return None
    domain = email.rsplit("@", 1)[-1]
    if domain in GENERIC_PROVIDERS:
        return None
    for tld in sorted(TLD_MAP, key=len, reverse=True):
        if domain.endswith(tld):
            return TLD_MAP[tld]
    return None


# ── Corpus helper ──────────────────────────────────────────────────────────────

def build_owner_repo_map() -> dict[str, str]:
    df = pd.read_csv(CORPUS, usecols=["owner_login", "repo_name", "commits"])
    idx  = df.groupby("owner_login")["commits"].idxmax()
    best = df.loc[idx].set_index("owner_login")["repo_name"]
    return best.to_dict()


# ── GitHub REST ────────────────────────────────────────────────────────────────

def fetch_commit_emails(session: requests.Session, owner: str, repo: str) -> list[str]:
    url = REST_URL.format(owner=owner, repo=repo)
    params = {"per_page": COMMITS_PER_REPO}
    for attempt in range(4):
        try:
            r = session.get(url, params=params, timeout=20)
        except Exception:
            time.sleep(10 * (attempt + 1))
            continue
        if r.status_code == 200:
            emails = []
            for c in r.json() or []:
                email = ((c.get("commit") or {}).get("author") or {}).get("email") or ""
                if email:
                    emails.append(email.strip().lower())
            return emails
        elif r.status_code in (403, 429):
            print(f"  Rate limited. Sleeping {SLEEP_RETRY}s …")
            time.sleep(SLEEP_RETRY)
        elif r.status_code in (404, 451):
            return []
        else:
            time.sleep(5)
    return []


# ── Sampling ───────────────────────────────────────────────────────────────────

def build_sample(n_total: int, seed: int, owner_repo: dict) -> pd.DataFrame:
    df = pd.read_csv(ALL_CSV)
    # Only owners resolved by Pass 1 that also have a corpus repo
    known = df[
        (df["source"] == "location_field") &
        (df["inferred_country"] != "not_specified") &
        (df["owner_login"].isin(owner_repo))
    ].copy()

    n_per_country = max(1, n_total // len(SAMPLE_COUNTRIES))
    frames = []
    for country in SAMPLE_COUNTRIES:
        sub  = known[known["inferred_country"] == country]
        take = min(n_per_country, len(sub))
        if take > 0:
            frames.append(sub.sample(take, random_state=seed))

    sample = pd.concat(frames, ignore_index=True)

    remaining = n_total - len(sample)
    if remaining > 0:
        already = set(sample["owner_login"])
        rest  = known[~known["owner_login"].isin(already)]
        extra = rest.sample(min(remaining, len(rest)), random_state=seed)
        sample = pd.concat([sample, extra], ignore_index=True)

    return sample.head(n_total)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=150,
                    help="Number of owners to test (default: 150)")
    ap.add_argument("--seed",   type=int, default=42,
                    help="Random seed (default: 42)")
    args = ap.parse_args()

    print(f"Stage 2e Commit Email Validation — n={args.sample}, seed={args.seed}")
    print("=" * 60)

    print("Building owner→repo map from corpus …")
    owner_repo = build_owner_repo_map()

    sample = build_sample(args.sample, args.seed, owner_repo)
    print(f"Sample: {len(sample)} owners across {sample['inferred_country'].nunique()} countries\n")
    print("Country distribution in sample:")
    print(sample["inferred_country"].value_counts().to_string())
    print()

    session = requests.Session()
    session.headers.update(REST_HEADERS)

    records = []
    total = len(sample)

    for _, row in sample.iterrows():
        login         = row["owner_login"]
        known_country = row["inferred_country"]
        repo          = owner_repo[login]
        idx           = len(records) + 1

        print(f"  [{idx:>3}/{total}] {login:<30} known={known_country}", end=" … ", flush=True)

        emails = fetch_commit_emails(session, login, repo)
        time.sleep(SLEEP_OK)

        all_emails   = emails
        ccTLD_emails = [e for e in emails if email_to_country(e) is not None]
        countries    = [email_to_country(e) for e in ccTLD_emails]
        countries    = [c for c in countries if c]

        if countries:
            counts = Counter(countries)
            top_country, top_count = counts.most_common(1)[0]
            inferred   = top_country
            confidence = "medium" if top_count >= 2 else "low"
        else:
            inferred   = "not_specified"
            confidence = "none"

        match = (inferred == known_country)
        status = "✓" if match else ("✗ GOT " + inferred if inferred != "not_specified" else "— MISSED")
        print(f"inferred={inferred:<22} ccTLD_emails={len(ccTLD_emails)}  {status}")

        records.append({
            "owner_login":    login,
            "known_country":  known_country,
            "repo_used":      repo,
            "inferred_country": inferred,
            "confidence":     confidence,
            "match":          match,
            "emails_found":   len(all_emails),
            "ccTLD_emails":   len(ccTLD_emails),
            "raw_emails":     "|".join(all_emails[:5]),
        })

    df_out = pd.DataFrame(records)
    df_out.to_csv(OUT_CSV, index=False)
    print(f"\nResults saved to: {OUT_CSV}\n")

    # ── Summary ────────────────────────────────────────────────────────────────
    n_valid   = len(df_out)
    correct   = df_out["match"].sum()
    wrong     = ((df_out["inferred_country"] != "not_specified") & ~df_out["match"]).sum()
    missed    = (df_out["inferred_country"] == "not_specified").sum()
    predicted = correct + wrong

    precision = correct / predicted * 100 if predicted > 0 else 0.0
    coverage  = predicted / n_valid  * 100

    print("=" * 60)
    print(f"VALIDATION SUMMARY  (n={n_valid} owners)")
    print("=" * 60)
    print(f"  Correct (inferred == known) : {correct:>3}  ({correct/n_valid*100:.1f}% of total)")
    print(f"  Wrong   (wrong country)     : {wrong:>3}  ({wrong/n_valid*100:.1f}% of total)")
    print(f"  Missed  (not_specified)     : {missed:>3}  ({missed/n_valid*100:.1f}% of total — not an error)")
    print()
    print("  ── Key metrics ──────────────────────────────────")
    print(f"  Coverage  (pipeline made a prediction) : {predicted:>3}/{n_valid}  ({coverage:.1f}%)")
    print(f"  Precision (correct when predicted)     : {correct:>3}/{predicted}  ({precision:.1f}%)")
    print(f"  Wrong rate (of all predictions made)   : {wrong:>3}/{predicted}  ({wrong/predicted*100:.1f}% ← the real risk)")
    print()

    print("Wrong predictions only:")
    wrong_df = df_out[(df_out["inferred_country"] != "not_specified") & ~df_out["match"]]
    if wrong_df.empty:
        print("  None — no wrong predictions!")
    else:
        for _, r in wrong_df.iterrows():
            print(f"  {r['owner_login']:<28} known={r['known_country']:<22} "
                  f"inferred={r['inferred_country']:<22} emails={r['raw_emails'][:60]}")

    print()
    print(f"PRECISION: {correct}/{predicted} = {precision:.1f}%  "
          f"| COVERAGE: {predicted}/{n_valid} = {coverage:.1f}%")


if __name__ == "__main__":
    main()

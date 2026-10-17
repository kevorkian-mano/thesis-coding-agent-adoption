#!/usr/bin/env python3
"""
Stage 3c -- Pass 3: Deep Scan (tiered classification, GraphQL batch)
=====================================================================
Runs only on repos not classified by Pass 1 or Pass 2 (pass2_unclassified.csv).

Speed optimisation vs. the REST version
----------------------------------------
Instead of 4 sequential REST calls per repo (3 commit pages + 1 PR page),
this version batches BATCH_SIZE repos into a single GraphQL query.
At BATCH_SIZE=5 this gives ~4-5x throughput improvement, reducing runtime
from ~15 hours (REST) to ~3-4 hours for ~23,000 repos.

Commit depth: 150 per repo (GraphQL history, in between the old 100/300).
PRs:          50 per repo (most recent, all states).

Tiered signal families
----------------------
STRONG  (any 1 alone -> agentic):
  agent_attribution  agent-specific commit trailer OR author email, deduped
                     per commit (Claude Code, Codex, Devin, Jules, Copilot
                     coding agent, Cursor, Aider, Windsurf, Gemini)
  pr_branch          copilot/, codex/, devin/, claude/, cursor/, jules-, sweep/
  bot_author         known agent bot account as commit or PR author

MEDIUM  (>= 2 different families, OR 1 + activity evidence -> agentic;
         1 alone -> ai_assisted):
  pr_label           PR label containing agent name

WEAK    (>= 1 alone -> ai_assisted):
  pr_body            agent/AI mention anywhere in PR description

EXCLUDED:
  npm_dependency     indicates AI *product* development, not AI-assisted
                     development of this repo -- too many false positives

Classification rule
-------------------
  agentic     if  strong_families is not empty
              OR  len(medium_families) >= 2
              OR  len(medium_families) >= 1 and agent_attributed_count >= 1
  ai_assisted if  no strong, and (medium_families or weak_families)
  none        if  0 signals

Output
------
  data/stage3/pass3_results.csv
  data/stage3/corpus_detected_full.csv   (merged pass 1 + 2 + 3)
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
OUT_DIR   = ROOT / "data" / "stage3"
IN_FILE   = OUT_DIR / "pass2_unclassified.csv"
PASS1     = OUT_DIR / "pass1_results.csv"
PASS2     = OUT_DIR / "pass2_results.csv"
OUT_PASS3 = OUT_DIR / "pass3_results.csv"
OUT_FULL  = OUT_DIR / "corpus_detected_full.csv"

TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    raise SystemExit("Set GITHUB_TOKEN environment variable before running.")

HEADERS_GRAPHQL = {"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"}
GRAPHQL_URL     = "https://api.github.com/graphql"

BATCH_SIZE  = 5     # repos per GraphQL request (~4-5x faster than REST)
MAX_COMMITS = 150   # per repo (was 300 REST; 150 catches most signal at lower cost)
MAX_PRS     = 50    # per repo
SLEEP_OK    = 0.4   # between batches (less sleep needed; one call per 5 repos)
SLEEP_RETRY = 60
SAVE_EVERY  = 200   # save to disk every N repos processed

# ── STRONG: agent attribution patterns (commit message + author email) ────────
# One match per commit (break after first). Dedupes trailer + email naturally.
AGENT_ATTRIBUTION_PATTERNS = [
    (re.compile(r"co-authored-by:.*claude.*anthropic", re.I), "Claude Code"),
    (re.compile(r"noreply@anthropic\.com",              re.I), "Claude Code"),
    (re.compile(r"generated with claude code",          re.I), "Claude Code"),
    (re.compile(r"🤖 generated with claude",            re.I), "Claude Code"),
    (re.compile(r"co-authored-by:.*devin",              re.I), "Devin"),
    (re.compile(r"devin-ai-integration",                re.I), "Devin"),
    (re.compile(r"co-authored-by:.*codex",              re.I), "OpenAI Codex"),
    (re.compile(r"chatgpt-codex",                       re.I), "OpenAI Codex"),
    (re.compile(r"co-authored-by:.*jules",              re.I), "Jules"),
    (re.compile(r"google-labs-jules",                   re.I), "Jules"),
    (re.compile(r"co-authored-by:.*copilot",            re.I), "GitHub Copilot"),
    (re.compile(r"co-authored-by:.*cursor",             re.I), "Cursor"),
    (re.compile(r"co-authored-by:.*aider",              re.I), "Aider"),
    (re.compile(r"co-authored-by:.*windsurf",           re.I), "Windsurf"),
    (re.compile(r"co-authored-by:.*gemini",             re.I), "Gemini"),
    (re.compile(r"co-authored-by:.*codeium",            re.I), "Codeium"),
]

# ── STRONG: known agent bot account logins ────────────────────────────────────
BOT_AUTHOR_MAP = {
    "github-copilot[bot]":           "GitHub Copilot",
    "devin-ai-integration[bot]":     "Devin",
    "claude[bot]":                   "Claude Code",
    "chatgpt-codex-connector[bot]":  "OpenAI Codex",
    "google-labs-jules[bot]":        "Jules",
    "sweep-ai[bot]":                 "Sweep",
    "openhands-agent":               "OpenHands",
    "cursor[bot]":                   "Cursor",
    "copilot-swe-agent[bot]":        "GitHub Copilot",
}
BOT_SUBSTRINGS = ["copilot", "devin-ai", "codex-connector", "jules[bot]",
                  "sweep-ai", "openhands", "cursor[bot]"]

# ── STRONG: agent-style PR branch prefixes ────────────────────────────────────
PR_BRANCH_PATTERNS = [
    (re.compile(r"^copilot/",   re.I), "GitHub Copilot"),
    (re.compile(r"^codex/",     re.I), "OpenAI Codex"),
    (re.compile(r"^devin/",     re.I), "Devin"),
    (re.compile(r"^claude/",    re.I), "Claude Code"),
    (re.compile(r"^cursor/",    re.I), "Cursor"),
    (re.compile(r"^jules-",     re.I), "Jules"),
    (re.compile(r"^sweep/",     re.I), "Sweep"),
    (re.compile(r"^openhands/", re.I), "OpenHands"),
]

# ── MEDIUM: PR labels ─────────────────────────────────────────────────────────
PR_LABEL_PATTERNS = [
    (re.compile(r"copilot",       re.I), "GitHub Copilot"),
    (re.compile(r"claude",        re.I), "Claude Code"),
    (re.compile(r"devin",         re.I), "Devin"),
    (re.compile(r"ai.generated",  re.I), "AI"),
    (re.compile(r"agent",         re.I), "AI"),
]

# ── WEAK: PR body patterns (one match per PR) ─────────────────────────────────
PR_BODY_PATTERNS = [
    re.compile(r"claude code",        re.I),
    re.compile(r"github copilot",     re.I),
    re.compile(r"copilot workspace",  re.I),
    re.compile(r"generated by devin", re.I),
    re.compile(r"cursor ai",          re.I),
    re.compile(r"chatgpt",            re.I),
    re.compile(r"openai codex",       re.I),
    re.compile(r"windsurf agent",     re.I),
    re.compile(r"aider\.chat",        re.I),
]


# ── helpers ───────────────────────────────────────────────────────────────────

def _bot_agent(login: str) -> str | None:
    if not login:
        return None
    if login in BOT_AUTHOR_MAP:
        return BOT_AUTHOR_MAP[login]
    lower = login.lower()
    for sub in BOT_SUBSTRINGS:
        if sub in lower:
            return sub.split("[")[0].replace("-", " ").title()
    return None


# ── GraphQL batch fetch ───────────────────────────────────────────────────────

def build_batch_query(repos: list[tuple[str, str]]) -> str:
    """
    Build a single GraphQL query that fetches commits + PRs for up to
    BATCH_SIZE repos simultaneously.
    """
    parts = []
    for i, (owner, name) in enumerate(repos):
        parts.append(f"""
  r{i}: repository(owner: "{owner}", name: "{name}") {{
    nameWithOwner
    defaultBranchRef {{
      target {{
        ... on Commit {{
          history(first: {MAX_COMMITS}) {{
            nodes {{
              message
              author {{
                email
                user {{ login }}
              }}
              committer {{
                user {{ login }}
              }}
            }}
          }}
        }}
      }}
    }}
    pullRequests(first: {MAX_PRS}, states: [OPEN, CLOSED, MERGED]) {{
      nodes {{
        headRefName
        author {{ login }}
        labels(first: 10) {{ nodes {{ name }} }}
        body
      }}
    }}
  }}""")
    return "{\n" + "\n".join(parts) + "\n}"


def graphql_batch(repos: list[tuple[str, str]]) -> dict:
    """
    Execute the batch query and return {full_name: repo_data_dict}.
    Retries up to 5 times on network errors or rate limits.
    """
    query = build_batch_query(repos)
    for attempt in range(5):
        try:
            resp = requests.post(
                GRAPHQL_URL,
                json={"query": query},
                headers=HEADERS_GRAPHQL,
                timeout=45,
            )
            if resp.status_code == 200:
                data = resp.json()
                gql_data = data.get("data") or {}
                result = {}
                for i, (owner, name) in enumerate(repos):
                    full_name = f"{owner}/{name}"
                    result[full_name] = gql_data.get(f"r{i}") or {}
                return result
            elif resp.status_code in (403, 429):
                print(f"  Rate limited, sleeping {SLEEP_RETRY}s ...")
                time.sleep(SLEEP_RETRY)
            else:
                print(f"  HTTP {resp.status_code}, attempt {attempt+1}/5")
                time.sleep(5)
        except Exception as e:
            wait = 10 * (attempt + 1)
            print(f"  Network error ({e.__class__.__name__}), retry {attempt+1}/5 in {wait}s ...")
            time.sleep(wait)
    # Return empty dicts on total failure
    return {f"{o}/{n}": {} for o, n in repos}


# ── tiered classification ─────────────────────────────────────────────────────

def classify(strong_families: set, medium_families: set,
             weak_families: set, agent_attributed_count: int) -> str:
    if strong_families:
        return "agentic"
    if len(medium_families) >= 2:
        return "agentic"
    if len(medium_families) >= 1 and agent_attributed_count >= 1:
        return "agentic"
    if medium_families or weak_families:
        return "ai_assisted"
    return "none"


def process_repo_data(repo_data: dict) -> dict:
    """
    Apply tiered signal detection to a single repo's GraphQL data.
    Returns the result dict (without full_name).
    """
    strong   = set()
    medium   = set()
    weak     = set()
    agents   = set()
    activity = 0

    # ── commits ───────────────────────────────────────────────────────────────
    default_ref = repo_data.get("defaultBranchRef") or {}
    target      = default_ref.get("target") or {}
    history     = target.get("history") or {}
    commits     = history.get("nodes") or []

    for c in commits:
        msg   = c.get("message") or ""
        author_data    = c.get("author") or {}
        email          = author_data.get("email") or ""
        author_user    = author_data.get("user") or {}
        author_login   = author_user.get("login") or ""
        committer_data = c.get("committer") or {}
        committer_user = committer_data.get("user") or {}
        committer_login = committer_user.get("login") or ""

        matched = False

        # STRONG: agent_attribution -- one match per commit, break after first
        for pat, agent in AGENT_ATTRIBUTION_PATTERNS:
            if pat.search(msg) or pat.search(email):
                strong.add("agent_attribution")
                agents.add(agent)
                activity += 1
                matched = True
                break

        # STRONG: bot commit author (only if no attribution match)
        if not matched:
            for login in (author_login, committer_login):
                bot = _bot_agent(login)
                if bot:
                    strong.add("bot_author")
                    agents.add(bot)
                    activity += 1
                    break

    # ── PRs ───────────────────────────────────────────────────────────────────
    prs = (repo_data.get("pullRequests") or {}).get("nodes") or []

    for pr in prs:
        branch       = pr.get("headRefName") or ""
        author_obj   = pr.get("author") or {}
        author_login = author_obj.get("login") or ""
        label_nodes  = (pr.get("labels") or {}).get("nodes") or []
        labels       = [lb.get("name", "") for lb in label_nodes]
        body         = (pr.get("body") or "")[:5000]  # truncate large PR bodies

        pr_matched = False

        # STRONG: agent-style branch name
        for pat, agent in PR_BRANCH_PATTERNS:
            if pat.search(branch):
                strong.add("pr_branch")
                agents.add(agent)
                activity += 1
                pr_matched = True
                break

        # STRONG: bot PR author
        if not pr_matched:
            bot = _bot_agent(author_login)
            if bot:
                strong.add("bot_author")
                agents.add(bot)
                activity += 1
                pr_matched = True

        # MEDIUM: PR labels (one match per PR)
        if not pr_matched:
            for label in labels:
                matched_label = False
                for pat, agent in PR_LABEL_PATTERNS:
                    if pat.search(label):
                        medium.add("pr_label")
                        agents.add(agent)
                        if not pr_matched:
                            activity += 1
                            pr_matched = True
                        matched_label = True
                        break
                if matched_label:
                    break

        # WEAK: PR body -- one match per PR
        if not pr_matched:
            for pat in PR_BODY_PATTERNS:
                if pat.search(body):
                    weak.add("pr_body")
                    break

    label = classify(strong, medium, weak, activity)

    return {
        "strong_families":        "|".join(sorted(strong)),
        "medium_families":        "|".join(sorted(medium)),
        "weak_families":          "|".join(sorted(weak)),
        "agents_found":           "|".join(sorted(agents)),
        "agent_attributed_count": activity,
        "adoption_label":         label,
    }


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("Stage 3c -- Pass 3: Deep Scan (GraphQL batch, 150 commits)")
    print("=" * 60)

    if not IN_FILE.exists():
        raise SystemExit(f"Run stage3b first. Missing: {IN_FILE}")

    all_repos = pd.read_csv(IN_FILE)["full_name"].tolist()
    print(f"Repos to process: {len(all_repos):,}")

    # Resume support
    if OUT_PASS3.exists():
        done  = set(pd.read_csv(OUT_PASS3)["full_name"].tolist())
        repos = [r for r in all_repos if r not in done]
        print(f"Resuming: {len(repos):,} remaining")
    else:
        repos = all_repos

    # Parse into (owner, name) pairs
    pairs = []
    for full_name in repos:
        parts = full_name.split("/", 1)
        if len(parts) == 2:
            pairs.append((parts[0], parts[1]))

    results    = []
    total      = len(pairs)
    processed  = 0
    n_agentic  = 0
    n_ai       = 0

    for batch_start in range(0, total, BATCH_SIZE):
        batch = pairs[batch_start: batch_start + BATCH_SIZE]

        batch_data = graphql_batch(batch)

        for owner, name in batch:
            full_name = f"{owner}/{name}"
            repo_data = batch_data.get(full_name) or {}

            try:
                result = process_repo_data(repo_data)
            except Exception as e:
                print(f"  Error processing {full_name}: {e}")
                result = {
                    "strong_families": "", "medium_families": "", "weak_families": "",
                    "agents_found": "", "agent_attributed_count": 0, "adoption_label": "none",
                }

            result["full_name"] = full_name
            results.append(result)

            if result["adoption_label"] == "agentic":
                n_agentic += 1
            elif result["adoption_label"] == "ai_assisted":
                n_ai += 1

        processed += len(batch)

        if processed % SAVE_EVERY < BATCH_SIZE or processed >= total:
            pct = processed / total * 100
            print(f"  {processed:>6,}/{total:,} ({pct:.1f}%)  "
                  f"agentic: {n_agentic:,}  ai_assisted: {n_ai:,}")
            chunk = pd.DataFrame(results)
            if OUT_PASS3.exists():
                existing = pd.read_csv(OUT_PASS3)
                chunk    = pd.concat([existing, chunk], ignore_index=True)
            chunk.to_csv(OUT_PASS3, index=False)
            results    = []
            n_agentic  = 0
            n_ai       = 0

        time.sleep(SLEEP_OK)

    # Final buffer flush
    if results:
        chunk = pd.DataFrame(results)
        if OUT_PASS3.exists():
            existing = pd.read_csv(OUT_PASS3)
            chunk    = pd.concat([existing, chunk], ignore_index=True)
        chunk.to_csv(OUT_PASS3, index=False)

    new_df = pd.read_csv(OUT_PASS3)

    # ── Merge all passes into corpus_detected_full.csv ────────────────────────
    print("\nMerging all passes into corpus_detected_full.csv ...")
    corpus = pd.read_csv(CORPUS, low_memory=False)

    p1 = pd.read_csv(PASS1)[["full_name", "adoption_label", "agent_detected"]]
    p1 = p1.rename(columns={"agent_detected": "agents_found"})
    p1 = p1[p1["adoption_label"] == "agentic"]
    p1["strong_families"] = "config_file"
    p1["signal_source"]   = "config_file"

    p2 = pd.read_csv(PASS2)[["full_name", "adoption_label", "agents_found",
                              "signal_source", "trailer_count"]]
    p2 = p2[p2["adoption_label"] != "unclassified"]

    p3 = new_df[["full_name", "adoption_label", "agents_found",
                 "strong_families", "medium_families", "weak_families",
                 "agent_attributed_count"]]

    detected = pd.concat([p1, p2, p3], ignore_index=True)
    detected = detected.drop_duplicates(subset="full_name", keep="first")

    full = corpus.merge(detected, on="full_name", how="left")
    full["adoption_label"] = full["adoption_label"].fillna("none")
    full["agents_found"]   = full["agents_found"].fillna("")
    full.to_csv(OUT_FULL, index=False)

    total_all = len(full)
    print()
    print("=" * 60)
    for label in ["agentic", "ai_assisted", "none"]:
        n = (full["adoption_label"] == label).sum()
        print(f"  {label:<15} {n:>6,}  ({n/total_all*100:.1f}%)")
    adopted = full["adoption_label"].isin(["agentic", "ai_assisted"]).sum()
    print(f"\n  Total adopted : {adopted:,}  ({adopted/total_all*100:.1f}%)")
    print(f"\nSaved: {OUT_PASS3}")
    print(f"Saved: {OUT_FULL}")


if __name__ == "__main__":
    main()

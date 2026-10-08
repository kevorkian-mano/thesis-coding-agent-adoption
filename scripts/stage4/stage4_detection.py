"""
Stage 4: Multi-Signal Agent Adoption Detection

Scans the unified corpus for coding agent adoption signals in two passes:

  Pass 1 — Root file tree check (GraphQL batch, ALL 77,315 repos)
    Checks for agent config files at repo root (CLAUDE.md, .cursorrules, etc.)
    and for .github/copilot-instructions.md.
    5 repos per GraphQL request. No commit history traversal — fast and safe.

  Pass 2 — Deep scan (REST, base corpus only: ~4,372 repos)
    a) Commit message scan  — trailers + bot author logins (up to 300 commits)
    b) PR body + label scan — agent markers in PR descriptions and labels
    c) package.json check   — AI SDK npm packages (Topic 2 specific)

Rationale for the split:
  The Egypt corpus (72,943 repos) is too large for full commit/PR scanning
  within GitHub's API rate limits. Config file detection gives a conservative
  lower bound for Egypt repos. The base corpus gets full multi-signal detection.
  This asymmetry is documented as a known limitation.

Single vs. Multi-Signal labelling (for RQ1 undercounting analysis):
  agent_adopted_single  = True if ANY commit trailer signal found
  agent_adopted_multi   = True if ANY signal type found (all passes)
  The delta = multi_rate - single_rate = the undercounting estimate.

Outputs (written to ../../data/):
  signals.csv               — one row per detected signal instance
  unified_corpus_detected.csv — unified_corpus.csv with detection columns filled

Requires: pip install requests pandas
Set GITHUB_TOKEN as an environment variable first.
"""

import os
import re
import time
import base64
import json
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).parent
DATA_DIR    = SCRIPT_DIR / "../../data"
CORPUS_IN   = DATA_DIR / "stage1/sample_corpus.csv"
CORPUS_OUT  = DATA_DIR / "stage4/sample_corpus_detected.csv"
SIGNALS_OUT = DATA_DIR / "stage4/signals_global.csv"

# ── Shared constants ──────────────────────────────────────────────────────────
STUDY_SNAPSHOT_DATE = "2026-10-01"   # approximate date Stage 1a collection ran
MIN_LAST_PUSH       = "2025-01-01"   # all corpus repos created >= 2025-02-24

# ── API ───────────────────────────────────────────────────────────────────────
GITHUB_API  = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"
TOKEN       = os.environ.get("GITHUB_TOKEN")

REST_HEADERS = {"Accept": "application/vnd.github+json"}
GQL_HEADERS  = {}
if TOKEN:
    REST_HEADERS["Authorization"] = f"Bearer {TOKEN}"
    GQL_HEADERS["Authorization"]  = f"Bearer {TOKEN}"

# ── Tuning ────────────────────────────────────────────────────────────────────
FILE_TREE_BATCH_SIZE = 5    # repos per GraphQL request (Pass 1)
MAX_COMMIT_PAGES     = 3    # × 100 commits = up to 300 commits scanned per repo
MAX_PR_PAGES         = 2    # × 100 PRs    = up to 200 PRs scanned per repo
SAVE_EVERY           = 100  # checkpoint every N repos in Pass 2

# ── Agent config file signals ─────────────────────────────────────────────────
# Root-level files/dirs whose presence indicates a specific agent was configured.
AGENT_CONFIG_FILES = {
    "CLAUDE.md":            "claude_code",
    "AGENTS.md":            "claude_code",
    ".cursorrules":         "cursor",
    ".cursor":              "cursor",
    ".copilot":             "copilot",
    ".aider.conf.yml":      "aider",
    ".aiderignore":         "aider",
    ".aider.model.settings.yml": "aider",
    ".continue":            "continue",
    ".codeium":             "codeium",
    "codeium.json":         "codeium",
    ".windsurfrules":       "windsurf",
    "GEMINI.md":            "gemini",
    ".roomodes":            "roo_code",
    ".clinerules":          "cline",
}

# Checked via object(expression:...) in the same GraphQL batch
SUBDIR_CONFIG_FILES = {
    ".github/copilot-instructions.md": "copilot",
}

# ── Commit trailer patterns ───────────────────────────────────────────────────
TRAILER_PATTERNS = [
    (re.compile(r"co-authored-by:.*github-copilot", re.I), "copilot"),
    (re.compile(r"co-authored-by:.*copilot",        re.I), "copilot"),
    (re.compile(r"co-authored-by:.*cursor",         re.I), "cursor"),
    (re.compile(r"co-authored-by:.*claude",         re.I), "claude_code"),
    (re.compile(r"co-authored-by:.*aider",          re.I), "aider"),
    (re.compile(r"co-authored-by:.*devin",          re.I), "devin"),
    (re.compile(r"co-authored-by:.*codeium",        re.I), "codeium"),
    (re.compile(r"co-authored-by:.*windsurf",       re.I), "windsurf"),
    (re.compile(r"generated with claude code",      re.I), "claude_code"),
    (re.compile(r"🤖 generated with claude",        re.I), "claude_code"),
]

BOT_AUTHOR_PATTERNS = [
    (re.compile(r"github-copilot\[bot\]", re.I), "copilot"),
    (re.compile(r"cursor-ai\[bot\]",      re.I), "cursor"),
    (re.compile(r"aider-bot",             re.I), "aider"),
    (re.compile(r"devin-ai-integration",  re.I), "devin"),
]

# ── Commit author email signals ───────────────────────────────────────────────
# Source: Robbes et al. (MSR '26) catalogued 2.7M commits from noreply@anthropic.com.
# Checked against commit.commit.author.email (the git-level email, not the GitHub login).
AUTHOR_EMAIL_PATTERNS = [
    (re.compile(r"noreply@anthropic\.com", re.I), "claude_code"),
]

# ── PR signals ────────────────────────────────────────────────────────────────
PR_BODY_PATTERNS = [
    (re.compile(r"generated with claude code",  re.I), "claude_code"),
    (re.compile(r"🤖 generated with claude",    re.I), "claude_code"),
    (re.compile(r"co-authored-by:.*copilot",    re.I), "copilot"),
    (re.compile(r"co-authored-by:.*cursor",     re.I), "cursor"),
    (re.compile(r"co-authored-by:.*claude",     re.I), "claude_code"),
]

PR_BRANCH_PATTERNS = [
    (re.compile(r"^copilot/",  re.I), "copilot"),
    (re.compile(r"^cursor/",   re.I), "cursor"),
    (re.compile(r"^codex/",    re.I), "openai"),
    (re.compile(r"^aider/",    re.I), "aider"),
]

PR_LABEL_PATTERNS = [
    (re.compile(r"^copilot$",      re.I), "copilot"),
    (re.compile(r"^codex$",        re.I), "openai"),
    (re.compile(r"^ai-generated$", re.I), "ai_generic"),
    (re.compile(r"^claude$",       re.I), "claude_code"),
]

# ── npm AI dependency signals (Topic 2 specific) ─────────────────────────────
# NOTE: generic "openai" package removed — it is used by millions of developers
# for API calls (not coding agent use) and inflates adoption rate artificially.
# See stage4_reaggregate.py for the previous analysis of this decision.
NPM_AI_PACKAGES = {
    "@anthropic-ai/sdk":              "claude_code",
    "@anthropic-ai/claude-code":      "claude_code",
    "@openai/agents":                 "openai",
    "@github/copilot-language-server": "copilot",
}


# ─────────────────────────────────────────────────────────────────────────────
# Network helpers
# ─────────────────────────────────────────────────────────────────────────────

def rest_get(url: str, params: dict = None, max_retries: int = 4):
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=REST_HEADERS,
                                params=params, timeout=15)
            if resp.status_code == 403:
                reset = int(resp.headers.get("X-RateLimit-Reset",
                                             time.time() + 60))
                wait = max(reset - int(time.time()), 1) + 2
                print(f"    REST rate limited. Sleeping {wait}s...")
                time.sleep(wait)
                continue
            if resp.status_code == 404:
                return None
            return resp
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            wait = 2 ** attempt
            print(f"    Network error ({type(e).__name__}), retry {attempt} in {wait}s...")
            time.sleep(wait)
    return None


def graphql_post(query: str, max_retries: int = 4) -> dict:
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(GRAPHQL_URL, json={"query": query},
                                 headers=GQL_HEADERS, timeout=30)
            if resp.status_code == 403:
                reset = int(resp.headers.get("X-RateLimit-Reset",
                                             time.time() + 60))
                wait = max(reset - int(time.time()), 1) + 2
                print(f"    GraphQL rate limited. Sleeping {wait}s...")
                time.sleep(wait)
                continue
            if resp.status_code in (502, 504):
                wait = 2 ** attempt
                print(f"    Server error {resp.status_code}, retry {attempt} in {wait}s...")
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                return {}
            payload = resp.json()
            if "errors" in payload:
                if any(e.get("type") == "RATE_LIMITED"
                       for e in payload["errors"]):
                    print("    GraphQL RATE_LIMITED. Sleeping 60s...")
                    time.sleep(60)
                    continue
            return payload.get("data") or {}
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            wait = 2 ** attempt
            print(f"    Network error ({type(e).__name__}), retry {attempt} in {wait}s...")
            time.sleep(wait)
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# Pass 1 — Config file detection (GraphQL, all repos)
# ─────────────────────────────────────────────────────────────────────────────

def build_file_tree_query(batch: list) -> str:
    """
    Fetches root tree entries + checks for .github/copilot-instructions.md
    for up to FILE_TREE_BATCH_SIZE repos in one GraphQL request.

    Uses defaultBranchRef → tree → entries (lists root files/dirs).
    This is NOT history traversal — it's a single tree read, cheap per repo.
    """
    fragments = []
    for idx, (owner, repo_name) in enumerate(batch):
        o = owner.replace('"', "")
        r = repo_name.replace('"', "")
        fragments.append(f"""
        repo_{idx}: repository(owner: "{o}", name: "{r}") {{
            defaultBranchRef {{
                target {{
                    ... on Commit {{
                        tree {{
                            entries {{ name type }}
                        }}
                    }}
                }}
            }}
            copilotInstructions: object(
                expression: "HEAD:.github/copilot-instructions.md"
            ) {{ __typename }}
        }}
        """)
    return "query { " + " ".join(fragments) + " }"


def parse_config_file_signals(tree_entries: list,
                               copilot_instr_exists: bool,
                               full_name: str) -> list:
    """Returns list of signal dicts from file tree check."""
    signals = []
    root_names = {e["name"].lower() for e in (tree_entries or [])}

    for config_name, agent_name in AGENT_CONFIG_FILES.items():
        if config_name.lower() in root_names:
            signals.append({
                "full_name":   full_name,
                "signal_type": "config_file",
                "agent_name":  agent_name,
                "detected_at": None,   # file exists now; creation date unknown
                "evidence":    config_name,
            })

    if copilot_instr_exists:
        signals.append({
            "full_name":   full_name,
            "signal_type": "config_file",
            "agent_name":  "copilot",
            "detected_at": None,
            "evidence":    ".github/copilot-instructions.md",
        })

    return signals


def run_pass1_file_tree(repos_df: pd.DataFrame) -> list:
    """
    Runs GraphQL file tree check on ALL repos in the corpus.
    Returns a flat list of signal dicts.
    """
    pairs = list(zip(repos_df["owner_login"], repos_df["repo_name"]))
    full_names = repos_df["full_name"].tolist()
    total = len(pairs)
    total_batches = (total + FILE_TREE_BATCH_SIZE - 1) // FILE_TREE_BATCH_SIZE
    all_signals = []

    print(f"\n── Pass 1: Config file check ({total} repos, "
          f"{total_batches} batches) ──")

    for i in range(0, total, FILE_TREE_BATCH_SIZE):
        batch_pairs = pairs[i: i + FILE_TREE_BATCH_SIZE]
        batch_names = full_names[i: i + FILE_TREE_BATCH_SIZE]
        b_num       = i // FILE_TREE_BATCH_SIZE + 1

        query = build_file_tree_query(batch_pairs)
        data  = graphql_post(query)

        for idx, full_name in enumerate(batch_names):
            repo_data = data.get(f"repo_{idx}")
            if not repo_data:
                continue

            # Root tree entries
            branch_ref  = repo_data.get("defaultBranchRef") or {}
            target      = (branch_ref.get("target") or {})
            tree        = (target.get("tree") or {})
            entries     = tree.get("entries") or []

            # .github/copilot-instructions.md
            copilot_exists = bool(repo_data.get("copilotInstructions"))

            signals = parse_config_file_signals(entries, copilot_exists, full_name)
            all_signals.extend(signals)

        if b_num % 200 == 0 or b_num == total_batches:
            print(f"  [{b_num}/{total_batches}] "
                  f"Total signals so far: {len(all_signals)}")

        time.sleep(0.5)

    print(f"Pass 1 complete. Config file signals found: {len(all_signals)}")
    return all_signals


# ─────────────────────────────────────────────────────────────────────────────
# Pass 2 — Deep scan (REST, base corpus only)
# ─────────────────────────────────────────────────────────────────────────────

def scan_commits(owner: str, repo: str, full_name: str) -> list:
    """Scans up to MAX_COMMIT_PAGES × 100 commits for trailer and bot signals."""
    signals = []
    for page in range(1, MAX_COMMIT_PAGES + 1):
        resp = rest_get(
            f"{GITHUB_API}/repos/{owner}/{repo}/commits",
            params={
                "per_page": 100,
                "page":     page,
                "since":    f"{MIN_LAST_PUSH}T00:00:00Z",
                "until":    f"{STUDY_SNAPSHOT_DATE}T00:00:00Z",
            },
        )
        if resp is None or resp.status_code != 200:
            break
        commits = resp.json()
        if not commits:
            break

        for commit in commits:
            sha        = commit.get("sha", "")[:12]
            committed  = ((commit.get("commit") or {})
                          .get("author") or {}).get("date", "")
            date_str   = committed[:10] if committed else None
            msg        = ((commit.get("commit") or {})
                          .get("message") or "")
            author_login = ((commit.get("author") or {})
                            .get("login") or "").lower()
            author_email = ((commit.get("commit") or {})
                            .get("author") or {}).get("email", "").lower()

            # Commit trailer patterns
            for pattern, agent_name in TRAILER_PATTERNS:
                if pattern.search(msg):
                    signals.append({
                        "full_name":   full_name,
                        "signal_type": "commit_trailer",
                        "agent_name":  agent_name,
                        "detected_at": date_str,
                        "evidence":    f"commit:{sha}",
                    })
                    break   # one signal per commit

            # Bot author login
            for pattern, agent_name in BOT_AUTHOR_PATTERNS:
                if pattern.search(author_login):
                    signals.append({
                        "full_name":   full_name,
                        "signal_type": "bot_author",
                        "agent_name":  agent_name,
                        "detected_at": date_str,
                        "evidence":    f"author:{author_login}",
                    })
                    break

            # Author email (e.g. noreply@anthropic.com — Robbes et al. MSR '26)
            for pattern, agent_name in AUTHOR_EMAIL_PATTERNS:
                if pattern.search(author_email):
                    signals.append({
                        "full_name":   full_name,
                        "signal_type": "author_email",
                        "agent_name":  agent_name,
                        "detected_at": date_str,
                        "evidence":    f"email:{author_email}",
                    })
                    break

        time.sleep(0.2)

    return signals


def scan_prs(owner: str, repo: str, full_name: str) -> list:
    """Scans PRs for body markers, branch name patterns, and labels."""
    signals = []
    for page in range(1, MAX_PR_PAGES + 1):
        resp = rest_get(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
            params={"state": "all", "per_page": 100, "page": page},
        )
        if resp is None or resp.status_code != 200:
            break
        prs = resp.json()
        if not prs:
            break

        for pr in prs:
            created_at = (pr.get("created_at") or "")[:10] or None
            if created_at and created_at > STUDY_SNAPSHOT_DATE:
                continue  # skip PRs after snapshot

            body   = pr.get("body") or ""
            branch = (pr.get("head") or {}).get("ref") or ""
            labels = [l.get("name", "") for l in (pr.get("labels") or [])]
            pr_num = pr.get("number", "")

            # Body patterns
            for pattern, agent_name in PR_BODY_PATTERNS:
                if pattern.search(body):
                    signals.append({
                        "full_name":   full_name,
                        "signal_type": "pr_body",
                        "agent_name":  agent_name,
                        "detected_at": created_at,
                        "evidence":    f"pr:{pr_num}",
                    })
                    break

            # Branch name patterns
            for pattern, agent_name in PR_BRANCH_PATTERNS:
                if pattern.search(branch):
                    signals.append({
                        "full_name":   full_name,
                        "signal_type": "pr_branch",
                        "agent_name":  agent_name,
                        "detected_at": created_at,
                        "evidence":    f"branch:{branch[:60]}",
                    })
                    break

            # Label patterns
            for label in labels:
                for pattern, agent_name in PR_LABEL_PATTERNS:
                    if pattern.search(label):
                        signals.append({
                            "full_name":   full_name,
                            "signal_type": "pr_label",
                            "agent_name":  agent_name,
                            "detected_at": created_at,
                            "evidence":    f"label:{label}",
                        })
                        break

        time.sleep(0.2)

    return signals


def check_npm_dependencies(owner: str, repo: str, full_name: str) -> list:
    """
    Fetches package.json and checks for AI SDK dependencies.
    Returns signals list.
    """
    resp = rest_get(
        f"{GITHUB_API}/repos/{owner}/{repo}/contents/package.json",
        params={"ref": "HEAD"},
    )
    if resp is None or resp.status_code != 200:
        return []

    try:
        content = resp.json().get("content", "")
        decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
        pkg     = json.loads(decoded)
    except Exception:
        return []

    signals = []
    all_deps = {}
    all_deps.update(pkg.get("dependencies", {}))
    all_deps.update(pkg.get("devDependencies", {}))

    for pkg_name, agent_name in NPM_AI_PACKAGES.items():
        if pkg_name in all_deps:
            signals.append({
                "full_name":   full_name,
                "signal_type": "npm_dependency",
                "agent_name":  agent_name,
                "detected_at": None,
                "evidence":    f"package:{pkg_name}",
            })

    return signals, len(pkg.get("dependencies", {})), len(pkg.get("devDependencies", {}))


def run_pass2_deep_scan(base_repos: pd.DataFrame,
                        existing_signals: list) -> list:
    """
    Runs deep commit/PR/dependency scan on base corpus repos.
    Returns new signals (existing_signals not included).
    """
    already_scanned = {s["full_name"] for s in existing_signals
                       if s.get("signal_type") != "config_file"}
    new_signals = []
    dep_counts  = {}   # full_name → (dependency_count, devdep_count)

    total = len(base_repos)
    print(f"\n── Pass 2: Deep scan ({total} base corpus repos) ──")

    for idx, row in base_repos.iterrows():
        owner     = str(row["owner_login"])
        repo_name = str(row["repo_name"])
        full_name = str(row["full_name"])
        n         = base_repos.index.get_loc(idx) + 1

        if full_name in already_scanned:
            continue

        print(f"  [{n}/{total}] {full_name}")

        # Commit scan
        commit_signals = scan_commits(owner, repo_name, full_name)
        new_signals.extend(commit_signals)

        # PR scan
        pr_signals = scan_prs(owner, repo_name, full_name)
        new_signals.extend(pr_signals)

        # npm dependency check
        result = check_npm_dependencies(owner, repo_name, full_name)
        if isinstance(result, tuple):
            dep_signals, dep_count, devdep_count = result
            new_signals.extend(dep_signals)
            dep_counts[full_name] = (dep_count, devdep_count)

        # Checkpoint
        if n % SAVE_EVERY == 0:
            all_so_far = existing_signals + new_signals
            pd.DataFrame(all_so_far).to_csv(SIGNALS_OUT, index=False)
            print(f"    Checkpoint saved. Signals so far: {len(all_so_far)}")

        time.sleep(0.3)

    print(f"Pass 2 complete. New signals found: {len(new_signals)}")
    return new_signals, dep_counts


# ─────────────────────────────────────────────────────────────────────────────
# Aggregate signals → per-repo detection columns
# ─────────────────────────────────────────────────────────────────────────────

def classify_adoption_level(has_config_file: bool,
                             distinct_types: int,
                             signal_occurrences: int) -> str:
    """
    Three-tier adoption classification (OBS-012):
      none        — no signals at all
      ai_assisted — signals detected, but weak evidence (could be autocomplete,
                    snippet tools, or one-off AI usage, not a configured agent)
      agentic     — strong evidence of a configured, recurring agent workflow

    Rules:
      agentic     if: config file present
                  OR  distinct signal types >= 2
                  OR  total signal occurrences >= 3
      ai_assisted if: any signals but none of the agentic conditions apply
      none        if: no signals
    """
    if signal_occurrences == 0:
        return "none"
    if (has_config_file
            or distinct_types >= 2
            or signal_occurrences >= 3):
        return "agentic"
    return "ai_assisted"


def aggregate_repo_signals(signals_df: pd.DataFrame,
                            corpus_df: pd.DataFrame,
                            dep_counts: dict) -> pd.DataFrame:
    """
    Derives per-repo columns from signals:
      agent_adopted_single  — commit trailer signals only (for undercounting RQ)
      agent_adopted_multi   — any signal type
      agent_adopted         — same as multi (canonical label)
      adoption_level        — 'none' / 'ai_assisted' / 'agentic' (OBS-012)
      first_detected_at     — earliest dated signal
      agent_name            — most common detected agent
      signal_count          — number of distinct signal types
      signal_occurrences    — total raw signal rows for this repo
      multi_agent           — >1 distinct agent detected
      time_to_adoption      — days from created_at to first_detected_at
      adoption_month        — calendar month of first_detected_at
      dependency_count      — from package.json (base corpus)
      devdep_count          — from package.json (base corpus)
    """
    df = corpus_df.copy()

    # Defaults
    df["agent_adopted_single"] = False
    df["agent_adopted_multi"]  = False
    df["agent_adopted"]        = False
    df["adoption_level"]       = "none"
    df["first_detected_at"]    = None
    df["agent_name"]           = None
    df["signal_count"]         = 0
    df["signal_occurrences"]   = 0
    df["multi_agent"]          = False
    df["time_to_adoption"]     = None
    df["adoption_month"]       = None
    df["dependency_count"]     = None
    df["devdep_count"]         = None

    if signals_df.empty:
        return df

    for full_name, grp in signals_df.groupby("full_name"):
        mask = df["full_name"] == full_name
        if not mask.any():
            continue

        # Single-signal (commit trailers only)
        trailer_signals = grp[grp["signal_type"] == "commit_trailer"]
        df.loc[mask, "agent_adopted_single"] = not trailer_signals.empty

        # Multi-signal (all types)
        df.loc[mask, "agent_adopted_multi"] = True
        df.loc[mask, "agent_adopted"]       = True

        # Distinct signal types and total occurrences
        distinct_types      = grp["signal_type"].nunique()
        signal_occurrences  = len(grp)
        has_config_file     = "config_file" in grp["signal_type"].values

        df.loc[mask, "signal_count"]       = distinct_types
        df.loc[mask, "signal_occurrences"] = signal_occurrences

        # Adoption level (OBS-012)
        df.loc[mask, "adoption_level"] = classify_adoption_level(
            has_config_file, distinct_types, signal_occurrences
        )

        # Agent name (most frequent)
        agent_counts = grp["agent_name"].value_counts()
        df.loc[mask, "agent_name"] = agent_counts.index[0]

        # Multi-agent
        df.loc[mask, "multi_agent"] = grp["agent_name"].nunique() > 1

        # First detected at (earliest dated signal)
        dated = grp.dropna(subset=["detected_at"])
        if not dated.empty:
            first_date = dated["detected_at"].min()
            df.loc[mask, "first_detected_at"] = first_date
            df.loc[mask, "adoption_month"]    = first_date[:7]

            # Time to adoption
            created = df.loc[mask, "created_at"].values[0]
            if created and isinstance(created, str) and len(created) >= 10:
                try:
                    delta = (
                        datetime.strptime(first_date, "%Y-%m-%d") -
                        datetime.strptime(str(created)[:10], "%Y-%m-%d")
                    ).days
                    df.loc[mask, "time_to_adoption"] = max(delta, 0)
                except ValueError:
                    pass

    # npm dependency counts
    for full_name, (dep_count, devdep_count) in dep_counts.items():
        mask = df["full_name"] == full_name
        df.loc[mask, "dependency_count"] = dep_count
        df.loc[mask, "devdep_count"]     = devdep_count

    return df


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    if not TOKEN:
        print("WARNING: no GITHUB_TOKEN — unauthenticated limit is 60 req/hr.")

    if not CORPUS_IN.exists():
        print(f"Error: {CORPUS_IN} not found. Run Stage 1 first.")
        return

    # Create output directory if it doesn't exist
    CORPUS_OUT.parent.mkdir(parents=True, exist_ok=True)

    corpus_df = pd.read_csv(CORPUS_IN)
    print(f"Loaded {len(corpus_df)} repos from sample_corpus.csv")

    # ── Resume support ────────────────────────────────────────────────────────
    if SIGNALS_OUT.exists():
        existing_signals = pd.read_csv(SIGNALS_OUT).to_dict("records")
        print(f"Resuming: {len(existing_signals)} signals already recorded.")
    else:
        existing_signals = []

    already_pass1 = {s["full_name"] for s in existing_signals
                     if s.get("signal_type") == "config_file"}
    remaining_pass1 = corpus_df[~corpus_df["full_name"].isin(already_pass1)]

    # ── Pass 1: Config file check (all repos) ─────────────────────────────────
    pass1_signals = []
    if not remaining_pass1.empty:
        pass1_signals = run_pass1_file_tree(remaining_pass1)
    else:
        print("Pass 1 already complete (resuming).")

    all_signals = existing_signals + pass1_signals

    # Save after Pass 1
    pd.DataFrame(all_signals).to_csv(SIGNALS_OUT, index=False)
    print(f"Pass 1 saved. Total signals: {len(all_signals)}")

    # ── Pass 2: Deep scan (all repos in global corpus) ───────────────────────
    pass2_signals, dep_counts = run_pass2_deep_scan(corpus_df.copy(), all_signals)

    all_signals += pass2_signals
    pd.DataFrame(all_signals).to_csv(SIGNALS_OUT, index=False)
    print(f"Pass 2 saved. Total signals: {len(all_signals)}")

    # ── Aggregate to per-repo columns ─────────────────────────────────────────
    signals_df   = pd.DataFrame(all_signals)
    corpus_final = aggregate_repo_signals(signals_df, corpus_df, dep_counts)
    corpus_final.to_csv(CORPUS_OUT, index=False)

    # ── Summary ───────────────────────────────────────────────────────────────
    adopted_single = corpus_final["agent_adopted_single"].sum()
    adopted_multi  = corpus_final["agent_adopted_multi"].sum()
    total          = len(corpus_final)

    print(f"\n─── Stage 4 Summary ──────────────────────────────────────────")
    print(f"Total repos scanned            : {total}")
    print(f"")
    print(f"Single-signal adopted (trailers only) : {adopted_single} "
          f"({adopted_single/total*100:.1f}%)")
    print(f"Multi-signal adopted  (all signals)   : {adopted_multi}  "
          f"({adopted_multi/total*100:.1f}%)")
    print(f"Undercounting delta                   : "
          f"{(adopted_multi-adopted_single)/total*100:.1f} pp")
    print(f"")
    print(f"Adoption level breakdown (OBS-012):")
    print(corpus_final["adoption_level"].value_counts().to_string())
    print(f"")
    if not signals_df.empty:
        print(f"Signal type breakdown:")
        print(signals_df["signal_type"].value_counts().to_string())
        print(f"\nAgent breakdown:")
        print(signals_df["agent_name"].value_counts().head(10).to_string())
    print(f"\nSaved: {CORPUS_OUT}")
    print(f"       {SIGNALS_OUT}")


if __name__ == "__main__":
    main()

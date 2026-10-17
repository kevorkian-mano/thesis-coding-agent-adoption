#!/usr/bin/env python3
"""
Stage 3d -- Deep Reclassification of AI-Assisted Repositories
==============================================================
Takes every repo labelled ai_assisted in corpus_detected_full.csv and:

  Phase 1 – Re-interpret existing signals under the tiered rule.
    The 3b pass used a count-based rule (1-2 signals → ai_assisted).
    Under the tiered rule, a single commit_trailer or pr_branch hit is
    STRONG (agent_attribution / pr_branch family) → immediately agentic.
    This phase upgrades those repos without any API calls.

  Phase 2 – Deep checks for repos still ai_assisted after Phase 1.
    Runs four new check families and classifies with accumulated evidence.

Tiered rule (same as stage3c)
------------------------------
  STRONG  (bot_author, ci_workflow, pr_branch, agent_attribution)
  MEDIUM  (config_file, pr_label)
  WEAK    (pr_body, editor_config)

  classify(strong_families, medium_families, weak_families, agent_attributed_count):
    ≥1 STRONG                                   → agentic
    ≥2 distinct MEDIUM families                 → agentic
    ≥1 MEDIUM family AND agent_attributed_count≥1 → agentic
    any MEDIUM or WEAK                          → ai_assisted
    nothing                                     → none

New signal families checked in Phase 2
---------------------------------------
  A. Extended config files (subdirectories + new tools not in stage3a)
  B. Bot account authorship in up to 300 commits
  C. Agent-style PR branch prefixes (expanded set)
  D. CI workflow files (.github/workflows/*.yml) for agent actions
  E. PR labels and PR body patterns

Input
-----
  data/stage3/corpus_detected_full.csv   (output of stage3c / merge)

Output
------
  data/stage3/reclassification_results.csv   -- per-repo decisions
  data/stage3/corpus_detected_full_v2.csv    -- updated labels
"""

import os
import re
import time
import base64
import requests
import pandas as pd
from pathlib import Path

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parents[2]
OUT_DIR     = ROOT / "data" / "stage3"
IN_FILE     = OUT_DIR / "corpus_detected_full.csv"
OUT_RECLASS = OUT_DIR / "reclassification_results.csv"
OUT_V2      = OUT_DIR / "corpus_detected_full_v2.csv"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    raise SystemExit("Set GITHUB_TOKEN environment variable before running.")

HEADERS_REST    = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json"}
HEADERS_GRAPHQL = {"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"}
REST_URL        = "https://api.github.com"
GRAPHQL_URL     = "https://api.github.com/graphql"

SLEEP_OK    = 0.6
SLEEP_RETRY = 60
SAVE_EVERY  = 100   # save to disk every N repos

# ── A. Extended config files (MEDIUM signal: config_file family) ──────────────
EXTENDED_CONFIGS = {
    ".claude/settings.json":            "Claude Code",
    ".claude/settings.local.json":      "Claude Code",
    ".clinerules":                      "Cline",
    ".mcp.json":                        "MCP",
    ".aider.chat.history.md":           "Aider",
    ".roo/rules.yaml":                  "Roo Code",
    ".roo/config.yaml":                 "Roo Code",
    ".cursor/rules/README.md":          "Cursor",
    ".github/instructions/coding.instructions.md": "GitHub Copilot",
    "AGENTS.json":                      "OpenAI Codex",
}

# ── B. Known bot account logins (STRONG signal: bot_author family) ────────────
BOT_AUTHOR_MAP = {
    "github-copilot[bot]":          "GitHub Copilot",
    "devin-ai-integration[bot]":    "Devin",
    "claude[bot]":                  "Claude Code",
    "chatgpt-codex-connector[bot]": "OpenAI Codex",
    "google-labs-jules[bot]":       "Jules",
    "sweep-ai[bot]":                "Sweep",
    "openhands-agent":              "OpenHands",
    "cursor[bot]":                  "Cursor",
    "copilot-swe-agent[bot]":       "GitHub Copilot",
    "sourcery-ai[bot]":             "Sourcery",
}
# Substring match fallback (lower-cased login)
BOT_SUBSTRINGS = [
    "copilot", "devin-ai", "claude-bot", "codex",
    "jules", "sweep-ai", "openhands", "cursor-bot",
]

# ── C. PR branch name patterns (STRONG signal: pr_branch family) ──────────────
PR_BRANCH_PATTERNS = [
    (re.compile(r"^copilot/",   re.I), "GitHub Copilot"),
    (re.compile(r"^codex/",     re.I), "OpenAI Codex"),
    (re.compile(r"^devin/",     re.I), "Devin"),
    (re.compile(r"^claude/",    re.I), "Claude Code"),
    (re.compile(r"^cursor/",    re.I), "Cursor"),
    (re.compile(r"^sweep/",     re.I), "Sweep"),
    (re.compile(r"^jules-",     re.I), "Jules"),
    (re.compile(r"^openhands/", re.I), "OpenHands"),
    (re.compile(r"^swe-agent/", re.I), "SWE-agent"),
]

# ── D. CI workflow agent action patterns (STRONG signal: ci_workflow family) ──
WORKFLOW_AGENT_PATTERNS = [
    (re.compile(r"anthropics/claude-code-action", re.I),  "Claude Code"),
    (re.compile(r"openai/codex-action",           re.I),  "OpenAI Codex"),
    (re.compile(r"devin-ai/",                     re.I),  "Devin"),
    (re.compile(r"github/copilot",                re.I),  "GitHub Copilot"),
    (re.compile(r"@claude\b",                     re.I),  "Claude Code"),
    (re.compile(r"@copilot\b",                    re.I),  "GitHub Copilot"),
    (re.compile(r"sweep-ai/",                     re.I),  "Sweep"),
    (re.compile(r"princeton-nlp/swe-agent",       re.I),  "SWE-agent"),
    (re.compile(r"all-hands-ai/openhands",        re.I),  "OpenHands"),
]

# ── E. PR label patterns (MEDIUM signal: pr_label family) ─────────────────────
PR_LABEL_PATTERNS = [
    (re.compile(r"\bcopilot\b",     re.I), "GitHub Copilot"),
    (re.compile(r"\bclaude\b",      re.I), "Claude Code"),
    (re.compile(r"\bdevin\b",       re.I), "Devin"),
    (re.compile(r"ai.generated",    re.I), "AI"),
    (re.compile(r"\bagent\b",       re.I), "AI"),
]

# ── E. PR body patterns (WEAK signal: pr_body family) ─────────────────────────
PR_BODY_PATTERNS = [
    (re.compile(r"assigned to copilot",         re.I),  "GitHub Copilot"),
    (re.compile(r"@github-copilot",             re.I),  "GitHub Copilot"),
    (re.compile(r"@claude\b",                   re.I),  "Claude Code"),
    (re.compile(r"@devin\b",                    re.I),  "Devin"),
    (re.compile(r"generated with claude code",  re.I),  "Claude Code"),
    (re.compile(r"🤖 generated with claude",    re.I),  "Claude Code"),
    (re.compile(r"noreply@anthropic\.com",      re.I),  "Claude Code"),
    (re.compile(r"co-authored-by:.*anthropic",  re.I),  "Claude Code"),
    (re.compile(r"co-authored-by:.*copilot",    re.I),  "GitHub Copilot"),
    (re.compile(r"co-authored-by:.*devin",      re.I),  "Devin"),
    (re.compile(r"openai codex",                re.I),  "OpenAI Codex"),
    (re.compile(r"cursor agent",                re.I),  "Cursor"),
]

# ── Mapping: signal_source values from 3b → tiers ─────────────────────────────
# Used to re-interpret existing 3b labels under the tiered rule.
SIGNAL_SOURCE_TIER = {
    "commit_trailer": ("strong", "agent_attribution"),
    "pr_branch":      ("strong", "pr_branch"),
    "config_file":    ("medium", "config_file"),
    "pr_body":        ("weak",   "pr_body"),
    "editor_config":  ("weak",   "editor_config"),
    "pr_label":       ("medium", "pr_label"),
}


# ── Classification rule (identical to stage3c) ────────────────────────────────

def classify(strong_families: set, medium_families: set,
             weak_families: set, agent_attributed_count: int) -> str:
    """
    Tiered rule:
      ≥1 STRONG family                                    → agentic
      ≥2 distinct MEDIUM families                         → agentic
      ≥1 MEDIUM family AND agent_attributed_count ≥ 1    → agentic
      any MEDIUM or WEAK (but not enough for agentic)    → ai_assisted
      nothing                                             → none
    """
    if strong_families:
        return "agentic"
    if len(medium_families) >= 2:
        return "agentic"
    if len(medium_families) >= 1 and agent_attributed_count >= 1:
        return "agentic"
    if medium_families or weak_families:
        return "ai_assisted"
    return "none"


# ── Helpers ───────────────────────────────────────────────────────────────────

def safe_get(url: str, params: dict = None):
    """REST GET with 5-retry exception handling and rate-limit backoff."""
    for attempt in range(5):
        try:
            resp = requests.get(url, headers=HEADERS_REST, params=params, timeout=20)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code in (403, 429):
                print(f"  Rate limited, sleeping {SLEEP_RETRY}s ...")
                time.sleep(SLEEP_RETRY)
            elif resp.status_code == 404:
                return None
            else:
                time.sleep(5)
        except Exception as e:
            wait = 10 * (attempt + 1)
            print(f"  Network error ({e.__class__.__name__}), retry {attempt+1}/5 in {wait}s ...")
            time.sleep(wait)
    return None


def graphql_query(query: str) -> dict:
    """GraphQL POST with 5-retry exception handling and rate-limit backoff."""
    for attempt in range(5):
        try:
            resp = requests.post(GRAPHQL_URL, json={"query": query},
                                 headers=HEADERS_GRAPHQL, timeout=30)
            if resp.status_code == 200:
                return resp.json().get("data") or {}
            elif resp.status_code in (403, 429):
                print(f"  Rate limited, sleeping {SLEEP_RETRY}s ...")
                time.sleep(SLEEP_RETRY)
            else:
                time.sleep(5)
        except Exception as e:
            wait = 10 * (attempt + 1)
            print(f"  Network error ({e.__class__.__name__}), retry {attempt+1}/5 in {wait}s ...")
            time.sleep(wait)
    return {}


def _is_bot(login: str) -> str | None:
    """Returns agent name if login matches a known bot account, else None."""
    if not login:
        return None
    if login in BOT_AUTHOR_MAP:
        return BOT_AUTHOR_MAP[login]
    lower = login.lower()
    for sub in BOT_SUBSTRINGS:
        if sub in lower:
            return sub.replace("-", " ").title()
    return None


# ── Phase 1: Re-interpret existing signals under tiered rule ─────────────────

def reinterpret_signals(row: pd.Series) -> tuple[set, set, set, int]:
    """
    Parse signal information stored in the corpus row and return
    (strong_families, medium_families, weak_families, agent_attributed_count).

    Handles both the new 3c schema (strong_families column) and the older
    3b schema (signal_source column).
    """
    strong_families  = set()
    medium_families  = set()
    weak_families    = set()
    agent_attributed_count = 0

    # New 3c schema: strong_families / medium_families / weak_families columns
    if "strong_families" in row.index and pd.notna(row.get("strong_families")):
        for f in str(row["strong_families"]).split("|"):
            if f:
                strong_families.add(f)
    if "medium_families" in row.index and pd.notna(row.get("medium_families")):
        for f in str(row["medium_families"]).split("|"):
            if f:
                medium_families.add(f)
    if "weak_families" in row.index and pd.notna(row.get("weak_families")):
        for f in str(row["weak_families"]).split("|"):
            if f:
                weak_families.add(f)
    if "agent_attributed_count" in row.index and pd.notna(row.get("agent_attributed_count")):
        try:
            agent_attributed_count = int(row["agent_attributed_count"])
        except (ValueError, TypeError):
            agent_attributed_count = 0

    # If no 3c columns, fall back to signal_source from 3b
    if not (strong_families or medium_families or weak_families):
        signal_source = str(row.get("signal_source") or "")
        for src_token in signal_source.split("|"):
            src_token = src_token.strip()
            if src_token in SIGNAL_SOURCE_TIER:
                tier, family = SIGNAL_SOURCE_TIER[src_token]
                if tier == "strong":
                    strong_families.add(family)
                elif tier == "medium":
                    medium_families.add(family)
                elif tier == "weak":
                    weak_families.add(family)

        # trailer_count from 3b maps to agent_attributed_count
        if "trailer_count" in row.index and pd.notna(row.get("trailer_count")):
            try:
                agent_attributed_count = int(row["trailer_count"])
            except (ValueError, TypeError):
                agent_attributed_count = 0

    return strong_families, medium_families, weak_families, agent_attributed_count


# ── Phase 2: Deep check new signal families ───────────────────────────────────

def check_extended_configs(owner: str, name: str) -> dict[str, str]:
    """
    GraphQL check for extended config files not covered by stage3a.
    Returns {file_path: agent_name}.  Contributes to MEDIUM config_file family.
    """
    file_checks = "\n".join(
        f'  f{i}: object(expression: "HEAD:{fpath}") {{ __typename }}'
        for i, fpath in enumerate(EXTENDED_CONFIGS.keys())
    )
    query = f"""
    {{
      repository(owner: "{owner}", name: "{name}") {{
        {file_checks}
      }}
    }}
    """
    data = graphql_query(query)
    repo_data = data.get("repository") or {}
    found = {}
    for i, (fpath, agent) in enumerate(EXTENDED_CONFIGS.items()):
        node = repo_data.get(f"f{i}")
        if node and node.get("__typename"):
            found[fpath] = agent
    return found


def scan_commit_authors(owner: str, name: str) -> dict[str, str]:
    """
    Fetches up to 300 commits and checks author/committer login for bot accounts.
    Returns {login: agent_name}.  Contributes to STRONG bot_author family.
    """
    found_bots = {}
    for page in range(1, 4):  # 3 pages × 100 = 300 commits
        data = safe_get(
            f"{REST_URL}/repos/{owner}/{name}/commits",
            params={"per_page": 100, "page": page},
        )
        if not data:
            break
        for commit in data:
            for field in ("author", "committer"):
                login = (commit.get(field) or {}).get("login", "")
                agent = _is_bot(login)
                if agent:
                    found_bots[login] = agent
        if len(data) < 100:
            break
    return found_bots


def scan_prs(owner: str, name: str) -> tuple[dict, dict, dict]:
    """
    Fetches up to 100 PRs and checks:
      - head branch name       → STRONG pr_branch family
      - PR author bot login    → STRONG bot_author family
      - PR label names         → MEDIUM pr_label family
      - PR body (first match)  → WEAK   pr_body family

    Returns (branch_agents, label_agents, body_agents) as {signal_key: agent_name}.
    """
    branch_agents = {}
    label_agents  = {}
    body_agents   = {}

    data = safe_get(
        f"{REST_URL}/repos/{owner}/{name}/pulls",
        params={"state": "all", "per_page": 100},
    )
    if not data:
        return branch_agents, label_agents, body_agents

    for pr in data:
        pr_num = pr.get("number", "?")

        # Branch name → STRONG pr_branch
        branch = (pr.get("head") or {}).get("ref", "")
        for pattern, agent in PR_BRANCH_PATTERNS:
            if pattern.search(branch):
                branch_agents[f"branch:{branch}"] = agent
                break

        # PR author bot → STRONG bot_author
        author_login = (pr.get("user") or {}).get("login", "")
        bot_agent = _is_bot(author_login)
        if bot_agent:
            branch_agents[f"pr_author:{author_login}"] = bot_agent

        # PR labels → MEDIUM pr_label (one match per PR)
        for label_obj in (pr.get("labels") or []):
            label_name = label_obj.get("name", "")
            matched = False
            for pattern, agent in PR_LABEL_PATTERNS:
                if pattern.search(label_name):
                    label_agents[f"label:{pr_num}:{label_name}"] = agent
                    matched = True
                    break
            if matched:
                break  # one label match per PR

        # PR body → WEAK pr_body (one match per PR)
        body = pr.get("body") or ""
        for pattern, agent in PR_BODY_PATTERNS:
            if pattern.search(body):
                body_agents[f"pr_body:{pr_num}"] = agent
                break

    return branch_agents, label_agents, body_agents


def scan_ci_workflows(owner: str, name: str) -> dict[str, str]:
    """
    Lists .github/workflows/ and reads each .yml file for agent action patterns.
    Returns {workflow_file: agent_name}.  Contributes to STRONG ci_workflow family.
    """
    found = {}

    data = safe_get(f"{REST_URL}/repos/{owner}/{name}/contents/.github/workflows")
    if not data or not isinstance(data, list):
        return found

    yml_files = [f["name"] for f in data if f["name"].endswith((".yml", ".yaml"))]

    for fname in yml_files[:10]:  # cap at 10 workflow files
        content_data = safe_get(
            f"{REST_URL}/repos/{owner}/{name}/contents/.github/workflows/{fname}"
        )
        if not content_data:
            continue
        raw = content_data.get("content", "")
        try:
            decoded = base64.b64decode(raw).decode("utf-8", errors="ignore")
        except Exception:
            continue
        for pattern, agent in WORKFLOW_AGENT_PATTERNS:
            if pattern.search(decoded):
                found[f"workflow:{fname}"] = agent
        time.sleep(0.2)

    return found


def deep_check(owner: str, name: str,
               init_strong: set, init_medium: set,
               init_weak: set, init_attributed: int) -> dict:
    """
    Runs all four new check families and accumulates signal evidence.
    Returns a result dict with updated families and final label.
    """
    strong_families  = set(init_strong)
    medium_families  = set(init_medium)
    weak_families    = set(init_weak)
    agent_attributed_count = init_attributed
    new_signals      = {}   # signal_key → agent_name

    # A. Extended config files → MEDIUM config_file family
    config_hits = check_extended_configs(owner, name)
    if config_hits:
        medium_families.add("config_file")
        new_signals.update({f"config:{k}": v for k, v in config_hits.items()})
    time.sleep(0.3)

    # B. Bot commit authors → STRONG bot_author family
    bot_authors = scan_commit_authors(owner, name)
    if bot_authors:
        strong_families.add("bot_author")
        new_signals.update(bot_authors)
    time.sleep(0.3)

    # C. PR branches (STRONG pr_branch), PR author bots (STRONG bot_author),
    #    PR labels (MEDIUM pr_label), PR bodies (WEAK pr_body)
    branch_agents, label_agents, body_agents = scan_prs(owner, name)
    if branch_agents:
        # Separate pr_branch from bot_author
        for key, agent in branch_agents.items():
            if key.startswith("branch:"):
                strong_families.add("pr_branch")
            elif key.startswith("pr_author:"):
                strong_families.add("bot_author")
        new_signals.update(branch_agents)
    if label_agents:
        medium_families.add("pr_label")
        new_signals.update(label_agents)
    if body_agents:
        weak_families.add("pr_body")
        new_signals.update(body_agents)
    time.sleep(0.3)

    # D. CI workflow files → STRONG ci_workflow family
    workflow_agents = scan_ci_workflows(owner, name)
    if workflow_agents:
        strong_families.add("ci_workflow")
        new_signals.update({f"workflow:{k}": v for k, v in workflow_agents.items()})

    new_label = classify(strong_families, medium_families, weak_families,
                         agent_attributed_count)

    return {
        "new_signals_count":    len(new_signals),
        "new_signals":          "|".join(f"{k}={v}" for k, v in new_signals.items()),
        "strong_families_final": "|".join(sorted(strong_families)),
        "medium_families_final": "|".join(sorted(medium_families)),
        "weak_families_final":   "|".join(sorted(weak_families)),
        "new_label":             new_label,
        "upgraded":              new_label == "agentic",
    }


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("Stage 3d -- Deep Reclassification of AI-Assisted Repositories")
    print("=" * 65)

    if not IN_FILE.exists():
        raise SystemExit(f"Run stage3c (and merge) first. Missing: {IN_FILE}")

    corpus = pd.read_csv(IN_FILE, low_memory=False)
    ai_assisted = corpus[corpus["adoption_label"] == "ai_assisted"].copy()
    print(f"AI-assisted repos loaded: {len(ai_assisted):,}")

    # ── Phase 1: re-interpret existing signals under tiered rule ─────────────
    print("\nPhase 1: re-interpreting existing signals under tiered rule ...")
    phase1_upgrades = 0
    phase1_labels   = {}

    for _, row in ai_assisted.iterrows():
        full_name = row["full_name"]
        strong, medium, weak, attributed = reinterpret_signals(row)
        new_label = classify(strong, medium, weak, attributed)
        phase1_labels[full_name] = new_label
        if new_label == "agentic":
            phase1_upgrades += 1

    print(f"  Phase 1 upgrades (no new API calls): {phase1_upgrades:,}")
    still_ai = [fn for fn, lbl in phase1_labels.items() if lbl == "ai_assisted"]
    print(f"  Remaining ai_assisted for Phase 2: {len(still_ai):,}")

    # ── Phase 2: deep checks on remaining ai_assisted repos ──────────────────
    print("\nPhase 2: deep checks on remaining ai_assisted repos ...")

    # Resume support
    if OUT_RECLASS.exists():
        done_df  = pd.read_csv(OUT_RECLASS)
        done_set = set(done_df["full_name"].tolist())
        still_ai = [fn for fn in still_ai if fn not in done_set]
        print(f"  Resuming: {len(still_ai):,} remaining in Phase 2")
    else:
        done_df = pd.DataFrame()

    # Build lookup for Phase 2 input rows
    ai_dict = ai_assisted.set_index("full_name").to_dict("index")

    results  = []
    total    = len(still_ai)
    upgraded = 0

    for i, full_name in enumerate(still_ai):
        parts = full_name.split("/", 1)
        if len(parts) != 2:
            continue
        owner, name = parts

        row = pd.Series(ai_dict.get(full_name, {}))
        strong, medium, weak, attributed = reinterpret_signals(row)

        result = deep_check(owner, name, strong, medium, weak, attributed)
        result["full_name"]      = full_name
        result["phase1_label"]   = phase1_labels.get(full_name, "ai_assisted")
        if result["upgraded"]:
            upgraded += 1

        results.append(result)

        if (i + 1) % SAVE_EVERY == 0 or (i + 1) == total:
            pct = (i + 1) / total * 100 if total > 0 else 100
            print(f"  {i+1:>5,}/{total:,} ({pct:.1f}%)  upgraded so far: {upgraded:,}")
            chunk = pd.DataFrame(results)
            if OUT_RECLASS.exists():
                existing_saved = pd.read_csv(OUT_RECLASS)
                chunk = pd.concat([existing_saved, chunk], ignore_index=True)
            chunk.to_csv(OUT_RECLASS, index=False)
            results = []

    # Final buffer flush
    if results:
        chunk = pd.DataFrame(results)
        if OUT_RECLASS.exists():
            existing_saved = pd.read_csv(OUT_RECLASS)
            chunk = pd.concat([existing_saved, chunk], ignore_index=True)
        chunk.to_csv(OUT_RECLASS, index=False)

    # ── Build corpus_detected_full_v2.csv ─────────────────────────────────────
    corpus_v2 = corpus.copy()

    # Apply Phase 1 upgrades
    for full_name, new_label in phase1_labels.items():
        if new_label != "ai_assisted":
            corpus_v2.loc[corpus_v2["full_name"] == full_name, "adoption_label"] = new_label

    # Apply Phase 2 upgrades (overrides Phase 1 for repos that went through deep check)
    if OUT_RECLASS.exists():
        reclass_df = pd.read_csv(OUT_RECLASS)
        label_map = dict(zip(reclass_df["full_name"], reclass_df["new_label"]))
        mask = corpus_v2["full_name"].isin(label_map)
        corpus_v2.loc[mask, "adoption_label"] = corpus_v2.loc[mask, "full_name"].map(label_map)

    corpus_v2.to_csv(OUT_V2, index=False)

    # ── Summary ───────────────────────────────────────────────────────────────
    n_total_ai   = len(ai_assisted)
    n_p1_upgrade = phase1_upgrades
    n_p2_upgrade = upgraded
    n_total_upg  = n_p1_upgrade + n_p2_upgrade

    v2_agentic     = (corpus_v2["adoption_label"] == "agentic").sum()
    v2_ai_assisted = (corpus_v2["adoption_label"] == "ai_assisted").sum()
    v2_none        = (corpus_v2["adoption_label"] == "none").sum()
    total_repos    = len(corpus_v2)

    print()
    print("=" * 65)
    print(f"AI-assisted repos examined  : {n_total_ai:,}")
    print(f"  Upgraded (Phase 1, re-interpret) : {n_p1_upgrade:,}  "
          f"({n_p1_upgrade/n_total_ai*100:.1f}%)")
    print(f"  Upgraded (Phase 2, deep check)   : {n_p2_upgrade:,}  "
          f"({n_p2_upgrade/n_total_ai*100:.1f}%)")
    print(f"  Total upgraded to agentic         : {n_total_upg:,}  "
          f"({n_total_upg/n_total_ai*100:.1f}%)")
    print(f"  Confirmed ai_assisted             : {n_total_ai - n_total_upg:,}")
    print()
    print("Updated corpus (v2):")
    print(f"  agentic     : {v2_agentic:,}  ({v2_agentic/total_repos*100:.1f}%)")
    print(f"  ai_assisted : {v2_ai_assisted:,}  ({v2_ai_assisted/total_repos*100:.1f}%)")
    print(f"  none        : {v2_none:,}  ({v2_none/total_repos*100:.1f}%)")
    print()

    # Top new signal types that triggered Phase 2 upgrades
    if OUT_RECLASS.exists():
        reclass_df = pd.read_csv(OUT_RECLASS)
        upgraded_rows = reclass_df[reclass_df["upgraded"]]
        signal_counts: dict[str, int] = {}
        for signals_str in upgraded_rows["new_signals"].dropna():
            for signal in signals_str.split("|"):
                if "=" in signal:
                    stype = signal.split(":")[0]
                    signal_counts[stype] = signal_counts.get(stype, 0) + 1
        if signal_counts:
            print("Top signal types that triggered Phase 2 upgrades:")
            for stype, cnt in sorted(signal_counts.items(), key=lambda x: -x[1])[:10]:
                print(f"  {stype:<30} {cnt:>5,}")
        print()

    print(f"Saved: {OUT_RECLASS}")
    print(f"Saved: {OUT_V2}")


if __name__ == "__main__":
    main()

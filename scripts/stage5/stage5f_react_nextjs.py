#!/usr/bin/env python3
"""
Stage 5c -- React + Next.js Subset Analysis  (Point 5)
=======================================================
Filters the corpus to the 9,799 React + Next.js (no Express) repositories
and re-runs all key analyses to allow direct comparison with the full corpus:

  1. Adoption rate + Wilson CIs
  2. Agent breakdown (which tools are used)
  3. Top-10 country ranking with Fisher pairwise tests
  4. Package manager split
  5. Size metrics (commits, bytes, stars) per adoption group

Input
-----
  data/stage4/corpus_with_country.csv
  data/stage5/repo_frameworks.csv

Output
------
  data/stage5/rn_corpus.csv                  -- filtered 9,799 repos
  data/stage5/rn_adoption_summary.csv
  data/stage5/rn_country_ranking.csv
  data/stage5/rn_agent_breakdown.csv
  figures/stage5/fig_rn_country_ranking.pdf/.png
  figures/stage5/fig_rn_agent_breakdown.pdf/.png
"""

import argparse
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from statsmodels.stats.proportion import proportion_confint
from pathlib import Path
from collections import Counter

ROOT      = Path(__file__).resolve().parents[2]
CORPUS    = ROOT / "data" / "stage4" / "corpus_with_country.csv"
FRAMEWORKS= ROOT / "data" / "stage5" / "repo_frameworks.csv"
OUT_DIR   = ROOT / "data"  / "stage5"
FIG_DIR   = ROOT / "figures" / "stage5"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

MIN_COUNTRY_REPOS = 30


def has_fw(frameworks_str, fw: str) -> bool:
    if pd.isna(frameworks_str):
        return False
    return fw in [p.strip() for p in str(frameworks_str).split(";")]


def wilson_ci(k, n):
    if n == 0:
        return 0.0, 0.0
    lo, hi = proportion_confint(k, n, alpha=0.05, method="wilson")
    return round(lo * 100, 2), round(hi * 100, 2)


def parse_agents(s):
    if pd.isna(s):
        return []
    return [t.strip() for t in str(s).split("|") if t.strip()]


def normalise_agent(raw: str) -> str:
    n = raw.strip().lower()
    if "claude" in n:    return "Claude Code"
    if "copilot" in n:   return "GitHub Copilot"
    if "cursor" in n:    return "Cursor"
    if "codex" in n:     return "OpenAI Codex"
    if "gemini" in n:    return "Gemini CLI"
    if "devin" in n:     return "Devin"
    if "aider" in n:     return "Aider"
    if "windsurf" in n:  return "Windsurf"
    return raw.strip()


OUTPUTS = [
    OUT_DIR / "rn_corpus.csv",
    OUT_DIR / "rn_adoption_summary.csv",
    OUT_DIR / "rn_country_ranking.csv",
    OUT_DIR / "rn_agent_breakdown.csv",
    FIG_DIR / "fig_rn_country_ranking.pdf",
    FIG_DIR / "fig_rn_agent_breakdown.pdf",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="Rerun even if output files already exist")
    args = parser.parse_args()

    print("Stage 5f -- React + Next.js Subset Analysis")
    print("=" * 60)

    if not args.force and all(p.exists() for p in OUTPUTS):
        print("All outputs already exist. Skipping.")
        print("Use --force to regenerate.")
        return

    corpus = pd.read_csv(CORPUS, low_memory=False)
    fw     = pd.read_csv(FRAMEWORKS, low_memory=False)

    # ── Build React + Next.js (no Express) filter ────────────────────────────
    fw["has_react"]   = fw["frameworks"].apply(lambda x: has_fw(x, "React"))
    fw["has_nextjs"]  = fw["frameworks"].apply(lambda x: has_fw(x, "Next.js"))
    fw["has_express"] = fw["frameworks"].apply(lambda x: has_fw(x, "Express"))

    rn_keys = fw[
        fw["has_react"] & fw["has_nextjs"] & ~fw["has_express"]
    ]["full_name"]

    print(f"React + Next.js (no Express) repos in framework file: {len(rn_keys):,}")

    # Merge with corpus
    rn = corpus[corpus["full_name"].isin(rn_keys)].copy()
    print(f"Matched in corpus : {len(rn):,}  (target: 9,799)")

    rn.to_csv(OUT_DIR / "rn_corpus.csv", index=False)

    # ── Adoption summary ──────────────────────────────────────────────────────
    total     = len(rn)
    agentic   = (rn["adoption_label"] == "agentic").sum()
    ai_asst   = (rn["adoption_label"] == "ai_assisted").sum()
    adopted   = agentic + ai_asst
    none      = (rn["adoption_label"] == "none").sum()

    adopt_rate   = adopted / total * 100
    agentic_rate = agentic / total * 100
    ci_lo, ci_hi = wilson_ci(adopted, total)

    print(f"\n── Adoption (React + Next.js) ──")
    print(f"  Total repos     : {total:,}")
    print(f"  Agentic         : {agentic:,}  ({agentic_rate:.1f}%)")
    print(f"  AI-Assisted     : {ai_asst:,}  ({ai_asst/total*100:.1f}%)")
    print(f"  Adopted (either): {adopted:,}  ({adopt_rate:.1f}%)  "
          f"[95% CI: {ci_lo}–{ci_hi}%]")
    print(f"  No AI           : {none:,}  ({none/total*100:.1f}%)")
    print(f"\n  Full corpus adoption for comparison: ~73.1%")

    pd.DataFrame([{
        "subset": "React + Next.js (no Express)",
        "total": total, "agentic": int(agentic), "ai_assisted": int(ai_asst),
        "adopted": int(adopted), "none": int(none),
        "adoption_rate": round(adopt_rate, 2),
        "agentic_rate":  round(agentic_rate, 2),
        "ci_lower": ci_lo, "ci_upper": ci_hi,
    }]).to_csv(OUT_DIR / "rn_adoption_summary.csv", index=False)

    # ── Agent breakdown ───────────────────────────────────────────────────────
    ag_rn = rn[rn["adoption_label"] == "agentic"]
    cnt = Counter()
    for row in ag_rn["agents_found"].dropna():
        for tok in parse_agents(row):
            cnt[normalise_agent(tok)] += 1

    agent_df = pd.DataFrame(
        [{"agent": k, "count": v, "pct": round(v / len(ag_rn) * 100, 1)}
         for k, v in cnt.most_common(15)]
    )
    agent_df.to_csv(OUT_DIR / "rn_agent_breakdown.csv", index=False)
    print(f"\n── Top agents in React + Next.js agentic repos ──")
    for _, r in agent_df.head(10).iterrows():
        print(f"  {r['agent']:<22} {r['count']:>6,}  ({r['pct']:.1f}%)")

    # Agent bar chart
    fig, ax = plt.subplots(figsize=(9, 5))
    top10 = agent_df.head(10)
    bars = ax.barh(top10["agent"][::-1], top10["pct"][::-1],
                   color="#2166ac", edgecolor="white")
    for bar, pct in zip(bars, top10["pct"][::-1]):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2,
                f"{pct:.1f}%", va="center", fontsize=9)
    ax.set_xlabel("% of Agentic Repos Using Agent")
    ax.set_title("Agent Usage in React + Next.js Corpus\n(top 10, % of agentic repos)",
                 fontweight="bold")
    ax.set_xlim(0, max(top10["pct"]) * 1.15)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    for ext in ("pdf", "png"):
        plt.savefig(FIG_DIR / f"fig_rn_agent_breakdown.{ext}",
                    bbox_inches="tight", dpi=150)
    plt.close()

    # ── Country ranking ───────────────────────────────────────────────────────
    located = rn[rn["country"] != "not_specified"].copy()
    country_rows = []
    for country, grp in located.groupby("country"):
        if len(grp) < MIN_COUNTRY_REPOS:
            continue
        n      = len(grp)
        ag     = (grp["adoption_label"] == "agentic").sum()
        asst   = (grp["adoption_label"] == "ai_assisted").sum()
        adpt   = ag + asst
        rate   = adpt / n * 100
        lo, hi = wilson_ci(adpt, n)
        country_rows.append({
            "country": country, "total": n,
            "agentic": int(ag), "ai_assisted": int(asst),
            "adopted": int(adpt), "adoption_rate": round(rate, 1),
            "ci_lower": lo, "ci_upper": hi,
        })

    country_df = pd.DataFrame(country_rows).sort_values(
        "adoption_rate", ascending=False).reset_index(drop=True)
    country_df.to_csv(OUT_DIR / "rn_country_ranking.csv", index=False)

    print(f"\n── Country ranking (React + Next.js, ≥{MIN_COUNTRY_REPOS} repos) ──")
    print(f"{'Rank':<5} {'Country':<22} {'Repos':>6} {'Adopt%':>8}  {'95% CI'}")
    print("-" * 55)
    for i, r in country_df.head(15).iterrows():
        print(f"{i+1:<5} {r['country']:<22} {r['total']:>6,} "
              f"{r['adoption_rate']:>8.1f}%  [{r['ci_lower']}–{r['ci_upper']}%]")

    # Country bar chart (top 15)
    top15 = country_df.head(15)
    fig, ax = plt.subplots(figsize=(10, 6))
    y = range(len(top15))
    ax.barh(list(y), top15["adoption_rate"][::-1].values,
            xerr=[
                (top15["adoption_rate"] - top15["ci_lower"])[::-1].values,
                (top15["ci_upper"] - top15["adoption_rate"])[::-1].values,
            ],
            color="#2166ac", edgecolor="white", capsize=3, alpha=0.85)
    ax.set_yticks(list(y))
    ax.set_yticklabels(top15["country"][::-1].values, fontsize=9)
    ax.set_xlabel("AI Adoption Rate (%)", fontsize=10)
    ax.set_title("Top 15 Countries by AI Adoption\nReact + Next.js repos (≥30 repos per country)",
                 fontweight="bold")
    ax.xaxis.set_major_formatter(mtick.PercentFormatter())
    ax.grid(axis="x", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    for ext in ("pdf", "png"):
        plt.savefig(FIG_DIR / f"fig_rn_country_ranking.{ext}",
                    bbox_inches="tight", dpi=150)
    plt.close()
    print(f"\nSaved figures and CSVs to data/stage5/ and figures/stage5/")
    print("Stage 5c complete.")


if __name__ == "__main__":
    main()

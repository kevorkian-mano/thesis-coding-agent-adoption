#!/usr/bin/env python3
"""
Stage 5n — Chinese Developer Agent Adoption Analysis
======================================================
Analyses the 6,764 Chinese repos in the corpus:
  - China is the #1 country by repo count (> United States)
  - Despite internet restrictions, 68.2% of Chinese agentic repos use Western tools only
  - Chinese-made agents (Trae/MarsCode, Qwen Code, Kimi Code) represent only 2.2%
  - The "VPN paradox": GitHub's Chinese developer community uses Claude/Cursor/Copilot

No GitHub API calls needed — all data is in stage2 + stage3 outputs.

Output
------
  data/stage5/china_analysis.csv      per-repo analysis table
  data/stage5/china_country_stats.csv aggregated per-country stats
"""

import pandas as pd
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
GEO     = ROOT / "data" / "stage2" / "owner_locations_all.csv"
CORPUS  = ROOT / "data" / "stage3" / "corpus_detected_full.csv"
OUT_DIR = ROOT / "data" / "stage5"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CHINESE_TOOLS  = ["Trae / MarsCode", "Qwen Code", "Kimi Code"]
WESTERN_TOOLS  = ["Claude Code", "Cursor", "GitHub Copilot", "OpenAI Codex",
                  "Gemini CLI", "Amp", "OpenCode", "Kiro", "Aider", "Windsurf",
                  "Cline / Roo Code", "Roo Code", "Devin", "Replit", "Junie",
                  "Amazon Q", "CodeRabbit", "PR-Agent", "Sourcery", "Sweep",
                  "Codeium", "Continue", "Augment Code", "Goose"]


def classify_tool_category(agents_str: str) -> str:
    """Classify a repo's tool mix into one of four categories."""
    if pd.isna(agents_str) or agents_str == "":
        return "none"
    has_cn  = any(t in agents_str for t in CHINESE_TOOLS)
    has_w   = any(t in agents_str for t in WESTERN_TOOLS)
    has_gen = "Generic" in agents_str
    if has_cn and has_w:
        return "mixed_cn_western"
    if has_cn:
        return "chinese_only"
    if has_w:
        return "western_only"
    if has_gen:
        return "generic_only"
    return "other"


def main():
    print("Stage 5n — Chinese Developer Agent Adoption Analysis")
    print("=" * 55)

    geo    = pd.read_csv(GEO)
    corpus = pd.read_csv(CORPUS)
    df     = corpus.merge(geo[["owner_login", "inferred_country"]],
                          on="owner_login", how="left")

    # ── Per-repo flags ─────────────────────────────────────────────────────────
    df["uses_chinese_tool"] = df["agents_found"].apply(
        lambda s: any(t in str(s) for t in CHINESE_TOOLS) if pd.notna(s) else False
    )
    df["uses_western_tool"] = df["agents_found"].apply(
        lambda s: any(t in str(s) for t in WESTERN_TOOLS) if pd.notna(s) else False
    )
    for tool in CHINESE_TOOLS + ["Claude Code", "Cursor", "GitHub Copilot",
                                  "OpenAI Codex", "Gemini CLI", "Generic"]:
        col = tool.lower().replace(" ", "_").replace("/", "_").replace("-", "_")
        df[f"uses_{col}"] = df["agents_found"].apply(
            lambda s, t=tool: t in str(s) if pd.notna(s) else False
        )
    df["tool_category"] = df["agents_found"].apply(classify_tool_category)

    # ── Save per-repo table ────────────────────────────────────────────────────
    out_cols = [
        "full_name", "owner_login", "inferred_country", "adoption_label",
        "primary_language", "agents_found", "tool_category",
        "uses_chinese_tool", "uses_western_tool",
    ]
    df[out_cols].to_csv(OUT_DIR / "china_analysis.csv", index=False)
    print(f"Saved per-repo table: {OUT_DIR / 'china_analysis.csv'}")

    # ── Country-level aggregation ──────────────────────────────────────────────
    valid = df[df["inferred_country"].notna() & (df["inferred_country"] != "not_specified")]
    top25 = valid["inferred_country"].value_counts().head(25).index.tolist()

    rows = []
    for country in top25:
        sub  = valid[valid["inferred_country"] == country]
        agen = sub[sub["adoption_label"] == "agentic"]
        n    = len(sub)
        na   = len(agen)
        row  = {
            "country":      country,
            "total_repos":  n,
            "agentic_repos": na,
            "agentic_rate": na / n * 100 if n else 0,
        }
        for tool in CHINESE_TOOLS + ["Claude Code", "Cursor", "GitHub Copilot",
                                      "OpenAI Codex", "Gemini CLI"]:
            col = tool.lower().replace(" ", "_").replace("/", "_").replace("-", "_")
            cnt = agen["agents_found"].apply(
                lambda s, t=tool: t in str(s) if pd.notna(s) else False
            ).sum()
            row[f"n_{col}"]    = cnt
            row[f"pct_{col}"]  = cnt / na * 100 if na else 0
        row["n_chinese_any"] = agen["uses_chinese_tool"].sum()
        row["pct_chinese_any"] = agen["uses_chinese_tool"].mean() * 100 if na else 0
        rows.append(row)

    country_df = pd.DataFrame(rows)
    country_df.to_csv(OUT_DIR / "china_country_stats.csv", index=False)
    print(f"Saved country stats:  {OUT_DIR / 'china_country_stats.csv'}")

    # ── Print summary ──────────────────────────────────────────────────────────
    china  = df[df["inferred_country"] == "China"]
    china_a = china[china["adoption_label"] == "agentic"]
    global_a = df[df["adoption_label"] == "agentic"]
    global_rate = (df["adoption_label"] == "agentic").mean() * 100

    print(f"\n{'='*55}")
    print(f"CORPUS OVERVIEW")
    print(f"{'='*55}")
    print(f"  Total repos            : {len(df):,}")
    print(f"  Global agentic rate    : {global_rate:.1f}%")
    print(f"  Repos with geo data    : {len(valid):,}")
    print(f"  #1 country             : China ({len(china):,} repos)")

    print(f"\n{'='*55}")
    print(f"CHINA BREAKDOWN (n={len(china):,})")
    print(f"{'='*55}")
    for label in ["agentic", "ai_assisted", "none"]:
        n = (china["adoption_label"] == label).sum()
        print(f"  {label:<15} {n:>5,}  ({n/len(china)*100:.1f}%)")

    print(f"\n{'='*55}")
    print(f"TOOL MIX — Chinese agentic repos (n={len(china_a):,})")
    print(f"{'='*55}")
    tools_to_show = ["Claude Code", "Generic", "OpenAI Codex", "Cursor",
                     "GitHub Copilot", "Gemini CLI",
                     "Trae / MarsCode", "Qwen Code", "Kimi Code"]
    print(f"  {'Tool':<22} {'China%':>8}  {'Global%':>8}")
    print(f"  {'-'*42}")
    for tool in tools_to_show:
        cn = china_a["agents_found"].apply(
            lambda s, t=tool: t in str(s) if pd.notna(s) else False
        ).mean() * 100
        gl = global_a["agents_found"].apply(
            lambda s, t=tool: t in str(s) if pd.notna(s) else False
        ).mean() * 100
        marker = " ◀ Chinese" if tool in CHINESE_TOOLS else ""
        print(f"  {tool:<22} {cn:>7.1f}%  {gl:>7.1f}%{marker}")

    print(f"\n{'='*55}")
    print(f"TOOL CATEGORY BREAKDOWN — Chinese agentic repos")
    print(f"{'='*55}")
    cats = china_a["tool_category"].value_counts()
    for cat, n in cats.items():
        print(f"  {cat:<25} {n:>5,}  ({n/len(china_a)*100:.1f}%)")

    print(f"\n{'='*55}")
    print(f"CHINESE TOOLS — WHERE IN THE WORLD")
    print(f"{'='*55}")
    for tool in CHINESE_TOOLS:
        users = df[(df["adoption_label"] == "agentic") &
                   df["agents_found"].apply(lambda s, t=tool: t in str(s) if pd.notna(s) else False)]
        print(f"\n{tool} (n={len(users):,}):")
        top_countries = users["inferred_country"].value_counts().head(6)
        for c, n in top_countries.items():
            print(f"  {c:<20} {n:>4,}")

    print(f"\nDone.")


if __name__ == "__main__":
    main()

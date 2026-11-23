# Agentic Coding Adoption on GitHub (JavaScript/TypeScript): Methodology and Results

**Project:** gitcorpus — live-only GitHub repository discovery for evidence-backed research corpora
**Measurement date:** 2026-11-19 (corpus freeze); dashboard version 2026-11-21
**Detection pack:** `packs/2026-11-15.json` (schema v2, 91 catalogued agents, 521 detection rules)
**Pricing codebook:** `AI Coding Agent Cost Codebook.xlsx` (90 tools, operator-maintained)

---

## 1. Research question and scope

This document records the methodology and results of an empirical study of *agentic* AI coding-tool adoption on public JavaScript/TypeScript GitHub repositories. The research question has three parts:

1. **How widespread is agentic AI adoption in the JS/TS ecosystem?** — What fraction of active JS/TS repositories carry evidence of an AI coding agent, broken down by depth of use and tool identity.
2. **How does adoption distribute geographically and economically?** — Does adoption vary by country, World Bank income group, or world region? If so, by how much, and how reliably can we measure it given the weakness of GitHub owner-location metadata?
3. **Does pricing gate access?** — Among adopters, does the mix of free-path vs paid-path tools differ with country income? This is the operator's most important downstream question: are free agentic tools reaching developers in lower-income economies?

The study corpus:

| Stack | Rows (repos) | Filter origin |
|---|---:|---|
| JavaScript / TypeScript | 60,129 | `language:javascript,typescript` with freshness & activity gates |

---

## 2. System overview

The tool is a research prototype called **gitcorpus**. Its design principle is *live-only*: a run measures GitHub as it is at a single moment (`ran_at`), captures the raw upstream evidence, and freezes everything into a replayable bundle. There are no background crawlers, no stale indexes, and nothing to keep alive between measurements.

The pipeline runs in nine stages:

```
filters.json → Validate → Live search → Thin matches → Hydrate → Virtual filters
             → Enrich → Geo resolve → Merge + cache → Display → Bundle/export
```

- **Validate** rejects typos (`updated:>2024` is invalid — the correct qualifier is `pushed:` — and GitHub would silently return unfiltered results) *before* any network call.
- **Live search** uses GraphQL `search` with recursive `created:` bisection to work around GitHub's 1,000-result-per-query ceiling. Discovery concurrency is 32 workers by default.
- **Hydrate** fetches each surviving match's full current record, batched (≤20 repos per GraphQL request). Unchanged repos revalidate via ETag → 304, which GitHub documents as not counting against the primary limit.
- **Virtual filters** apply post-hydration (e.g., `has_dockerfile`, `min_commits`, `owner_country`). These are the filters GitHub never built.
- **Geo resolve** validates flag emojis, folds Latin accents, separates country / subdivision / city evidence, resolves exact city names via a curated table + offline GeoNames gazetteer, and requires that country / city / subdivision / ccTLD / timezone signals agree. An honest unknown beats a confident wrong answer.
- **Merge** keys by immutable repo `id` (not `owner/name`, which changes on rename or transfer).
- **Bundle/export** persists `ran_at`, filter hash, API version, and raw upstream JSON for byte-identical replay.

Downstream of the run, a second system — the **detection pipeline** — scans each surviving repository for evidence of coding-agent use and labels the repo with `adoption_label`, `adoption_level`, `primary_agent`, `agents_found`, `commit_ratio`, and supporting evidence columns. These labels, merged with the geo-resolved owner country and the World Bank income group, form the analysis dataset consumed by the analysis dashboard.

Source references:

- Project README: [`README.md`](../../README.md)
- Detection code: `src/detect/` (pack loader, channels, attribution)
- Enrichment code: `src/enrich/` (geo resolver, cost planner)
- Serving + dashboard: `src/serve/` (FastAPI routes, Jinja templates, `static/compare.js`)

---

## 3. Agentic detection methodology

### 3.1 Pack-based detection

The detection pipeline is driven by a declarative, versioned *pack*. The pack catalogues known coding agents, lists the forensic *rules* that identify each one, and encodes rejection patterns that suppress false positives.

**Pack: `2026-11-15` (schema v2) — catalogue counters:**

| Counter | Value |
|---|---:|
| Total catalogued families | 108 |
| Active agents (`category = "active"`) | 78 |
| Adjacent frameworks (`category = "adjacent"`) | 12 |
| Pseudo (generic fallback) | 1 |
| **Reported total of agents considered ("the 91")** | **91** |
| Legacy-only families | 6 |
| Watch list | 5 |
| Normalized incumbents | 47 |
| Additions in this pack | 25 |
| v2-activated | 6 |
| Rules | 521 |
| Rejections | 107 |
| Rules by cohort | `2026-11-14`: 200 · `agentic-much-baseline`: 293 · `extended`: 28 |

The "91 agents" that appear throughout this report correspond to the sum of **active + adjacent + pseudo** — the full set of families the pack is willing to attribute signals to.

### 3.2 Detection channels

Each rule binds a family to a **channel** — a specific place in a repository or its Git history where that agent leaves a trace. The pack ships 521 rules across 13 channels:

| Channel | Rules | Example trace |
|---|---:|---|
| `file` | 150 | `.aider/`, `.cursor/`, `.claude/`, `AGENTS.md` |
| `author` | 84 | Commit `Author` matches a known bot identity |
| `committer` | 81 | Commit `Committer` matches a known bot identity |
| `co_author` | 76 | `Co-authored-by:` trailer |
| `branch` | 29 | Branch name pattern (e.g., `copilot/*`) |
| `pr_author` | 28 | Pull request opened by an agent account |
| `pr_commenter` | 24 | Agent commented on a PR |
| `issue_commenter` | 22 | Agent commented on an issue |
| `hidden_ref` | 8 | Hidden Git ref created by agent (e.g., `refs/copilot/*`) |
| `custom_trailer` | 7 | Agent-specific commit trailer |
| `workflow` | 4 | GitHub Actions workflow file |
| `label` | 4 | Repository label set by agent |
| `pr_reviewer` | 4 | Agent set as PR reviewer |

A rule carries a `match` block (e.g., path regex, author regex), a `lineage` block (aliases, predecessors, successors, rollup family), and a `lifecycle` block (`status`, `valid_from`, `valid_until`, `uncertainty`). Lifecycle windows let the pack retire rules that no longer identify a live agent and introduce new rules the moment a fresh agent surfaces.

### 3.3 Attribution and adoption-level classification

A commit is attributed to an agent when at least one rule fires on one of its identity or payload fields. Attribution is dedup'd per (repo, agent) and aggregated per repo as:

- **`commit_ratio`** — the fraction of the repo's commits attributed to any agent. Bounded in [0, 1].
- **`agent_count`** — distinct agents fired in the repo.
- **`channels_fired`** — distinct channels fired in the repo.
- **`agents_found`** — pipe-separated list of distinct agent names fired in the repo.
- **`primary_agent`** — the single agent with the highest attribution weight.

The repo is then placed into an **adoption level** derived purely from `commit_ratio` (from `src/detect/attribution.py::adoption_level`):

| `adoption_level` | Condition |
|---|---|
| `none` | `commit_ratio == 0` (or null) |
| `experimental` | `0 < commit_ratio < 0.01` (<1%) |
| `limited` | `0.01 ≤ commit_ratio < 0.05` (1–5%) |
| `consistent` | `0.05 ≤ commit_ratio < 0.20` (5–20%) |
| `pervasive` | `commit_ratio ≥ 0.20` (≥20%) |

The 20% pervasive threshold is a reporting convention; changing it shifts the shape of the distribution but is documented in-tool so readers can re-normalize.

An **`adoption_label`** summarises the level as a coarse binary for cross-tab reporting: `agentic` (level ≥ experimental) vs `none`. The dashboard's "adopted" flag includes `agentic` and, optionally, `ai_assisted` depending on the current scope filter.

### 3.4 Rejection patterns and noise suppression

The pack ships 107 **rejection patterns** and a `generic_weights` table (`{"AGENTS.md": 0.3}`) that down-weights evidence too ambiguous to attribute confidently. A repo containing only an `AGENTS.md` without other signals will not cross the threshold on that file alone; it must be corroborated by at least one specific channel.

Commits whose message matches the project's `is_noise_commit` patterns (merge-only, tag-only, etc.) are dropped before attribution.

---

## 4. Corpus construction

### 4.1 The study corpus

The study corpus was discovered with freshness and activity gates. All filters (minimum commits, archived handling, license screens) are documented alongside the frozen bundle.

| Stack | CSV filename | Rows | First-signal months observed | Repo-created months observed |
|---|---|---:|---|---|
| JavaScript / TypeScript | `corpus_integrated_js-ts_run4_20261119_170535.csv` | 60,129 | 2024-04 → 2026-11 (27 months) | 2024-04 → 2026-11 (27 months) |

The CSV carries 56 columns.

### 4.2 Key corpus columns used in this report

- **Adoption:** `adoption_label`, `adoption_level`, `primary_agent`, `agents_found`, `agent_count`, `channels_fired`, `channels_count`, `commit_ratio` (also surfaced as `ai_density`), `first_signal_at`, `first_signal_days_ago`, `evidence_semantics`
- **Identity:** `owner_country`, `country`, `inferred_country`, `geo_confidence`
- **Framing:** `income_group` (World Bank classification), `repo_created_at`, `created_at`, `oldest_scanned_commit_at`
- **Agent lineage:** `current_agents`, `configured_agents`, `framework_hints`

---

## 5. Analytical dimensions

The dashboard renders the dataset along the following dimensions:

| Dimension | Field(s) | Purpose |
|---|---|---|
| Adoption rate | `adoption_label` | Headline "what % use AI agents" |
| Adoption depth | `adoption_level` | Distribution across experimental → pervasive |
| AI density | `commit_ratio` | Continuous share of commits authored by agents |
| Primary agent | `primary_agent` | Tool concentration / market structure |
| Agent fanout | `agent_count`, `channels_fired` | How many distinct agents per adopter |
| Country | `country` (resolved via §6) | Geographic distribution |
| World region | `country → region_map` | Regional roll-up |
| Income group | `income_group` | World Bank classification |
| Pricing tier | `agents_found × AGENT_CATEGORY` | Free-path vs paid-path adoption |
| Recency | `first_signal_days_ago` | Weeks since first agent evidence |
| Signal vintage | `first_signal_at` | Timeline of emergence |

---

## 6. Geographic resolution methodology

### 6.1 Resolver confidence vocabulary

The geo resolver emits *resolution-method tags* that identify which rule produced each match:

| Tag | Meaning |
|---|---|
| `name` | Country name string matched directly |
| `exact-iso` | Exact ISO-2 / ISO-3 code match |
| `gazetteer-city` | Known city in a single country |
| `geocoder` | Offline geocoder resolution |
| `region` | Only a subdivision or regional hint was usable |
| `weak` | Last-resort inference from ccTLD / timezone / flag emoji |
| `unmatched` | No country determinable |

To report comparably across resolver versions, the vocabulary is folded into a 4-tier scheme:

| Unified tier | Source tags | Interpretation |
|---|---|---|
| **strong** | `name`, `exact-iso`, `gazetteer-city`, `geocoder` | Direct name / ISO code / known city match |
| **medium** | `region` | Regional hint only (country inferred from subdivision/region) |
| **weak** | `weak` | Fuzzy / last-resort evidence (ccTLD, timezone, flag emoji) |
| **unresolved** | `unmatched`, empty | No country determinable |

### 6.2 Observed tier distribution

| Tier | Repos | Share |
|---|---:|---:|
| strong | 21,016 | 35.0% |
| medium | 2,461 | 4.1% |
| weak | 10,338 | 17.2% |
| unresolved | 26,314 | 43.8% |
| **Total** | **60,129** | **100%** |

**Roughly 44% of repositories have no determinable owner country** — a direct consequence of GitHub's `location` field being optional, free-form, and frequently unused or sarcastic. All country-conditional statistics in §8 are computed on the resolved subset and should be read as "among resolved owners," never "among all owners." Weak-tier evidence is included for coarse analyses (regional / income-group) but excluded from any country-level claim where a single-country attribution is required.

### 6.3 Country-code normalisation

Two ISO-2 codes leak through the resolver in rare cases: `TW` (Taiwan) in 326 rows, and `VA` (Vatican) in 3 rows. Both are aliased to their canonical country names in the dashboard.

A fuller alias table also normalises common World Bank / GeoNames spellings (`Korea, Rep.` → `South Korea`, `Russian Federation` → `Russia`, `Viet Nam` → `Vietnam`, `Türkiye` → `Turkey`, etc.).

---

## 7. Agent pricing classification

### 7.1 Source: the Cost Codebook

A separate operator-maintained spreadsheet (`AI Coding Agent Cost Codebook.xlsx`) assigns each of the 91 catalogued agents (minus one X-excluded framework = 90 rows) to a pricing category, with evidence. Each row carries:

- `tool` — the family id (matches the pack's `families[*].id`)
- `category_cheapest` — the cheapest path a motivated developer could use
- **`category_default`** — the path *most* developers actually take (used throughout this report)
- `confidence` — H / M / L
- `oss`, `local_models`, `free_tier`, `free_public_repos`, `free_students`, `card_for_free`, `cheapest_paid_usd_mo`, `byo_key`, `pricing_changes`, `notes`, `evidence_url`, `date_checked`

### 7.2 Category key

| Code | Meaning |
|---|---|
| **C0** | $0 forever via local/open models (OSS harness, no cloud dependence) |
| **C1** | Vendor free tier, capped, no expiry |
| **C1-P** | Free only for public / OSS repositories |
| **C2** | Free only for students or verified OSS maintainers |
| **C3** | Metered — pay only API tokens / credits, no subscription |
| **C4** | Paid subscription required |
| **C5** | Enterprise / sales-only / discontinued |
| **X** | Not a coding agent (framework / registry); excluded |
| **Unknown** | Could not verify |

### 7.3 Binary rule used by the dashboard

The Key sheet defines a binary rule used to collapse the seven real categories into free-path vs paid-path:

| Bucket | Categories |
|---|---|
| **Free-path** | C0, C1, C1-P, C2 |
| **Paid-path** | C3, C4, C5 |
| **Excluded from both lines** | X (frameworks), Unknown |

### 7.4 Category distribution over the codebook (default-path column)

| Category | Tools |
|---|---:|
| C1 (vendor free tier) | 23 |
| C1-P (free for OSS only) | 2 |
| C2 (students / OSS only) | 1 |
| C3 (metered) | 22 |
| C4 (paid subscription) | 27 |
| C5 (enterprise / discontinued) | 1 |
| X (framework, excluded) | 13 |
| Unknown | 1 |
| **Total** | **90** |

For comparison, the cheapest-path classification (what a resourceful developer *could* use) has 29 tools in C0 (truly $0) — meaning there is a sizable gap between "cheapest path possible" and "path most developers actually take." Claude Code is the canonical example: cheapest = C3 (BYOK against the Anthropic API), default = C4 (the Pro subscription most users pay for).

### 7.5 Notable reclassifications vs. earlier hand-drafted lists

An initial hand-drafted paid/free list, written against the top agent names in the corpus before the codebook existed, miscategorised several widely-used tools. The codebook reclassifies them as follows:

- **Claude Code → C4 (paid).** Default path is Claude Pro / API — there is no true free Claude Code tier.
- **Aider, Cline, Goose, OpenHands → C3 (metered, paid).** OSS harnesses; the user pays for API tokens at their own cost.
- **Qwen Coder, Mistral Vibe, Kimi Code CLI, Xiaomi MiMo Code → C4 (paid).** Free tiers were withdrawn by the vendor during 2026 (Qwen on 2026-04-15, MiMo Auto on 2026-07-26, Mistral API on 2026-01-15, Qodo trial on 2026-06-30). Their `pricing_changes` cells in the codebook document the dates.

The `pricing_changes` column is itself a research artefact: it records *when* a category changed, so the dashboard can later overlay these as "pricing cliff" events on the adoption timeline.

---

## 8. Results

All percentages below are computed on the 2026-11-19 corpus freeze and reproduced from the raw CSV.

### 8.1 Headline adoption

| Metric | JS/TS |
|---|---:|
| Repos measured | 60,129 |
| Agentic (any AI evidence) | 26,216 (**43.6%**) |
| No AI | 33,913 (56.4%) |

Nearly half of all active JS/TS repositories measured carry evidence of at least one AI coding agent.

### 8.2 Adoption depth

| Level | Repos | Share |
|---|---:|---:|
| none | 33,913 | 56.4% |
| experimental | 0 | 0.0% |
| limited | 5,653 | 9.4% |
| consistent | 5,719 | 9.5% |
| **pervasive** | **14,844** | **24.7%** |

The most important finding here is that **of all adopters, more than half are in the *pervasive* band** — i.e., ≥20% of their commits are attributed to agents. The distribution is not a long low-engagement tail: when a repo adopts an agent at all, it tends to adopt heavily. The `experimental` band (0 < commit_ratio < 0.01) is empty, which reflects both the attribution threshold and the pack's rejection patterns pushing noisy sub-1% signals below the floor.

### 8.3 Primary agent concentration

| Rank | Primary agent | Repos |
|---:|---|---:|
| 1 | claude code | 26,946 |
| 2 | codex | 4,309 |
| 3 | copilot | 2,840 |
| 4 | coderabbit | 2,772 |
| 5 | cursor | 2,568 |
| 6 | google antigravity / gemini code assist | 476 |
| 7 | opencode | 444 |
| 8 | devin / devin desktop | 299 |
| 9 | jules | 290 |
| 10 | lovable | 249 |
| 11 | pi | 246 |
| 12 | amp | 153 |
| 13 | trae | 148 |
| 14 | sourcery | 118 |
| 15 | kiro | 110 |

**Claude Code dominates.** It accounts for ~61% of named primary-agent attributions (26,946 / 44,030). This concentration is the single most consequential finding for downstream analysis: any aggregate about "agentic adoption" is, in practice, overwhelmingly a statement about Claude Code use. CodeRabbit (code review), Cursor (IDE), and Codex (CLI) are the other major players; together the top five account for over 90% of named primary-agent attributions.

### 8.4 Geographic distribution

**Top 15 countries (resolved subset):**

| Rank | Country | Repos |
|---:|---|---:|
| 1 | China | 6,764 |
| 2 | United States | 4,926 |
| 3 | India | 4,710 |
| 4 | Germany | 1,199 |
| 5 | United Kingdom | 1,023 |
| 6 | Japan | 950 |
| 7 | Brazil | 942 |
| 8 | Canada | 842 |
| 9 | France | 811 |
| 10 | South Korea | 786 |
| 11 | Australia | 637 |
| 12 | Indonesia | 519 |
| 13 | Turkey | 509 |
| 14 | Vietnam | 469 |
| 15 | Spain | 460 |

China leads by volume, followed by the US and India — a three-country block that dwarfs the rest. Note again that these counts are on the **resolved subset** — roughly 44% of all repos have no determinable owner country (§6).

**By World Bank world region (resolved subset, adoption rate):**

| Region | Total | Agentic | Rate |
|---|---:|---:|---:|
| North America | 5,866 | 3,047 | **51.9%** |
| Europe & Central Asia | 5,426 | 2,535 | 46.7% |
| Latin America & Caribbean | 1,190 | 486 | 40.8% |
| East Asia & Pacific | 11,076 | 4,389 | 39.6% |
| Middle East & North Africa | 688 | 250 | 36.3% |
| South Asia | 5,293 | 1,501 | 28.4% |
| Sub-Saharan Africa | 487 | 129 | 26.5% |

North America leads adoption at 51.9%. Sub-Saharan Africa (26.5%) and South Asia (28.4%) are the laggards — nearly 25 percentage points behind the leader. The regional gradient is strong and stable across sample sizes.

### 8.5 Adoption × income group

| Income group | Total | Agentic | Rate |
|---|---:|---:|---:|
| High income | 15,786 | 7,904 | **50.1%** |
| Upper middle income | 11,089 | 4,011 | 36.2% |
| Lower middle income | 6,387 | 1,756 | 27.5% |
| Low income | 224 | 42 | 18.8% |

The **monotone gradient is clean**: adoption rate falls from 50.1% in High-income countries to 18.8% in Low-income countries — a 31-point gap. Each step down the income ladder reduces adoption by roughly 10–15 points. Even the Low-income bucket (n = 224) is above the sample-size floor (§9) and produces a stable rate estimate.

### 8.6 Pricing × income

Using `category_default` from the Cost Codebook, binary-collapsed (§7.3). Each cell reports what fraction of *agentic* repos in that income group use *at least one* tool in the respective bucket (a repo can appear in both columns if it uses both a free-path and a paid-path tool).

| Income group | Agentic n | Any-free tool | Any-paid tool |
|---|---:|---:|---:|
| High income | 7,904 | 56.1% | **91.7%** |
| Upper middle | 4,011 | 59.2% | 89.0% |
| Lower middle | 1,756 | **65.3%** | 74.8% |
| Low income | 42 | *57.1%* | *69.0%* |

Two patterns emerge:

1. **Paid-path adoption is the dominant mode** across the ladder. Over 74% of agentic repos use at least one paid-path tool in every income group above the sample floor. This is Claude Code's shadow: the default-path classification puts Claude Code in C4.
2. **Free-path adoption rises as income falls** (56.1% → 59.2% → 65.3% from High to Lower-middle), and **paid-path adoption falls** (91.7% → 89.0% → 74.8%). This is the signature pattern one would expect if price gates access. The gap between free- and paid-path shares narrows sharply as income drops — in High-income countries paid tools are 35 points ahead, but in Lower-middle they are only 9 points ahead.

The Low-income cell (n = 42 agentic) sits below the n=30 reporting floor for the pricing lines (which require the narrower agentic subset — §9). The italicised figures are *shown* in the dashboard with a small-sample flag but should be read as indicative only.

### 8.7 Recency (time since first AI signal)

| Bucket | Repos |
|---|---:|
| 0–7 days | 411 |
| 8–30 days | 2,258 |
| 31–90 days | 6,269 |
| 91–180 days | 9,197 |
| 180+ days | 14,762 |
| unknown | 27,232 |

Among repos with any first-signal date (54.7% of all repos), the 180+-day bucket is the largest (14,762). This indicates a **mature adopter base** — most agentic repos have had agent evidence for over six months. The 0–7 day bucket is small in absolute terms but important as a leading indicator: these are repos where an agent landed in the last week.

### 8.8 Agent fanout

**Number of distinct agents attributed per repo (top of distribution):**

| `agent_count` | Repos |
|---:|---:|
| 0 | 15,703 |
| 1 | 17,025 |
| 2 | 13,019 |
| 3 | 7,835 |
| 4 | 3,691 |
| 5 | 1,513 |
| 6 | 648 |
| 7 | 301 |
| 8+ | 394 |

A substantial fraction of adopting repos use more than one agent — **63.8% of agentic repos have ≥ 2 distinct agents attributed**. This supports an interpretation of the market as additive rather than substitutive at the repo level: teams layer agents (one in the IDE, one in the CI review path, one for scaffolding) rather than consolidating on a single tool. The per-repo mix is what makes the "any-free / any-paid" bucketing in §8.6 the right lens, rather than a single-agent primary attribution.

### 8.9 AI density (commit-share distribution)

| Density bucket | Repos |
|---|---:|
| Config-only (0%) | 33,913 |
| Low (<10%) | 8,388 |
| Medium (10–40%) | 6,397 |
| High (40–80%) | 5,469 |
| Full (≥80%) | 5,962 |

Among adopters, the density distribution has a strong **"high end"**: 5,962 repositories — nearly 10% of the whole corpus and 22.7% of agentic repos — have at least 80% of their commits attributed to AI agents. This is consistent with the pervasive-band concentration seen in §8.2 and suggests a non-trivial population of repositories that are substantially AI-authored, not just AI-assisted.

---

## 9. Statistical caveats

1. **Geo-resolution ceiling.** 43.8% of owners have no determinable country. Country-conditional statistics are computed on the resolved subset and should be presented that way. Within the resolved subset, the four tiers (strong / medium / weak / unresolved) have meaningfully different error profiles; the dashboard exposes them but reports aggregates on the union.
2. **Sample-size floor.** Income-group cells with fewer than 30 repos are flagged in the dashboard. The adoption-rate bar renders at any n ≥ 1 but carries a `⚠ small sample` tooltip when n < 30. The Paid / Free lines compute on the narrower agentic subset and are suppressed entirely when that subset is below 30 — the Low-income agentic subset (n = 42) sits above the floor on the total column (n = 224) but marginal on the agentic subset, so pricing-line figures for that cell are shown with a caveat.
3. **Pricing classification confidence.** The codebook flags each tool with H / M / L confidence. 14 tools carry L-confidence or `Unknown`; headlines that depend heavily on these should carry a caveat.
4. **Primary-agent dominance.** Claude Code dominates attribution (61% of named primary-agent rows). Any statement about "agentic adoption" is, in practice, dominated by Claude Code behaviour. Cross-agent comparisons should be read with this skew in mind.
5. **Live-only measurement.** gitcorpus takes a point-in-time snapshot. Re-running the same filter at a later date will produce a slightly different set — repos vanish, rename, or lose activity. The bundle records exactly what was measured; the numbers in this document are the 2026-11-19 bundle's answer.
6. **Rule generation effects.** The 521 rules in the active pack originate from three cohorts (`agentic-much-baseline`: 293, `2026-11-14`: 200, `extended`: 28). Rule coverage per family is non-uniform — some families have many narrow rules, others one broad rule. A repo's attribution probability is partly a function of which family it carries, not only of how heavily it uses that family.

---

## 10. Limitations

- **Detection is evidence-based, not usage-based.** A repository with no visible agent trace may still have been written with heavy AI help from a tool that leaves no forensic trace (e.g., a developer who manually pastes code from ChatGPT with no attribution trailer). The lower bound this method provides is tight; the upper bound is open.
- **Private repositories are out of scope.** Only public GitHub is measured. Enterprise / Server / internal GitLab / Bitbucket are not.
- **Owner-country is owner-location, not developer-location.** GitHub exposes the account owner's self-declared location. For organisational repos this is the org's HQ, which may differ from the contributor's actual country. The World Bank income group is derived from this proxy; it is the best available but not direct.
- **Pack coverage lags the real world by weeks.** New agents that have not yet entered the pack produce `primary_agent: generic` or no detection. The 2026-11-15 pack catalogued 91 agents, but at any given moment the universe of agents is larger. "Watch" families (5 in this pack) are the queue for incorporation.
- **Codebook default-path is a judgement call.** `category_default` encodes the most common path. A developer in a low-income country with access to free API credits can route a C3 tool through C0 behaviour; the dashboard will still count the tool as C3. The codebook offers `category_cheapest` for the opposite assumption, but this document uses `category_default` throughout for consistency.
- **Low-income representation is thin.** Only 224 repos (0.4% of all measured repos) sit in the Low-income bucket. Any inference about Low-income access to specific tools is bounded by this sample size.

---

## 11. Reproducibility

### 11.1 How to regenerate every number in §8

1. Check out the project at the commit named in this document's header.
2. Run `./start.sh` to launch the dashboard locally (requires `.env` with GitHub tokens, Postgres on port 5433, Redis on port 6379).
3. The input CSV at `integrated_datasets/corpus_integrated_js-ts_run4_20261119_170535.csv` is the frozen artefact of the 2026-11-19 run.
4. The pack used for detection is `packs/2026-11-15.json`; the pricing codebook is `AI Coding Agent Cost Codebook.xlsx` at the project root.
5. Every statistic in §8 is produced client-side in `src/serve/static/compare.js` from these three artefacts. No server-side analytics step is needed.

### 11.2 Key file locations

| Artefact | Path |
|---|---|
| JS/TS corpus CSV | `integrated_datasets/corpus_integrated_js-ts_run4_20261119_170535.csv` |
| Detection pack | `packs/2026-11-15.json` |
| Pricing codebook | `AI Coding Agent Cost Codebook.xlsx` |
| Dashboard template | `src/serve/templates/compare.html` |
| Dashboard JS (all chart logic) | `src/serve/static/compare.js` |
| Dashboard routes | `src/serve/compare.py` |
| App entrypoint | `src/serve/app.py` |
| Run management | `src/serve/runs.py` |
| Detection pipeline | `src/detect/` (pack loader, channels, attribution, orchestrator) |
| Enrichment (geo, cost planning) | `src/enrich/` |
| Startup script | `start.sh` |

### 11.3 Verifying attribution for a specific repo

Each row in the CSV carries the complete attribution trail: `agents_found`, `channels_fired`, `evidence_semantics`, `first_signal_at`, `agent_count`, `commit_ratio`, and `primary_agent`. These fields are populated directly from `src/detect/orchestrator.py`'s serialisation step and preserve the exact signal path that led to the label. For deeper evidence (which specific commits, which files), the run bundle under `runs/<run_id>/` carries the raw detection JSON.

---

## 12. Glossary

- **Adoption label** — binary flag (`agentic` / `none`) derived from `adoption_level`. A repo is `agentic` if `adoption_level ≥ experimental`.
- **Adoption level** — five-band classification from `commit_ratio`: none < experimental (<1%) < limited (<5%) < consistent (<20%) < pervasive (≥20%).
- **Agent** — a named coding assistant (Claude Code, Copilot, Cursor, Aider, …) tracked by a family record in the pack.
- **Agentic** — adjective for a repo whose commit history shows evidence of at least one agent above the detection threshold.
- **Channel** — one of 13 trace types a rule can key on (`file`, `author`, `committer`, `co_author`, `branch`, `pr_author`, `pr_commenter`, `issue_commenter`, `hidden_ref`, `custom_trailer`, `workflow`, `label`, `pr_reviewer`).
- **Commit ratio** — fraction of a repo's commits attributed to any agent.
- **Default path** (codebook) — the pricing path most developers actually take for a given tool, as judged by the operator.
- **Family** — a pack-level identity record for one agent, including aliases, predecessors, successors, and rollup target.
- **Pack** — the declarative, versioned artefact that describes which agents exist and how to detect them.
- **Pervasive** — adoption level with `commit_ratio ≥ 0.20`; the heaviest band.
- **Primary agent** — the single agent in a repo with the highest attribution weight.
- **Resolved / unresolved** — whether the owner country could be determined from the account's `location` field.
- **Rule** — one pack entry binding a family to a channel + match criterion (e.g., regex on path, regex on author email).
- **Strong / medium / weak** (geo tier) — unified confidence vocabulary folding the underlying resolver's values (§6).

---

*Document generated against gitcorpus @ 2026-11-21, corpus freeze 2026-11-19, pack 2026-11-15.*

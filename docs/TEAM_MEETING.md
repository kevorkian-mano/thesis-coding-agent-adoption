# Team Meeting — Shared Corpus Discussion
**Date:** 2026-09-27  
**Topic 2 representative:** Manuel Youssef Haik Kevorkian (JavaScript / TypeScript / npm)  
**Purpose:** Align on shared corpus methodology, compare progress across topics, and resolve open decisions before we diverge further.

---

## My Status Update (bring these numbers to the meeting)

Stages 1–3 are complete for Topic 2. Here is what I can share with the team:

| Item | Number |
|---|---|
| Base corpus (global JS/TS repos) | 4,372 repos |
| Egyptian seed accounts (Stage 2a) | 1,876 accounts |
| Accounts after snowball expansion (Stage 2b) | 21,223 accounts |
| Egyptian developer repos (Stage 2c) | 72,946 repos |
| **Unified corpus (after merge)** | **77,315 repos** |
| Repos in both corpora (overlap) | 3 repos |
| JavaScript repos | 46,973 (60.8%) |
| TypeScript repos | 30,342 (39.2%) |
| Small stratum (0–50 stars) | 74,162 (95.9%) |
| Medium stratum (51–500 stars) | 1,522 (2.0%) |
| Large stratum (>500 stars) | 1,631 (2.1%) |

Stage 4 (detection) script is written and ready to run.

---

## Things to Report to the Team

### 1. The Egypt corpus is overwhelmingly small repos
99.8% of Egyptian developer repos have 0–50 stars. This is a structural finding — Egyptian developers predominantly work on personal, academic, and small-scale projects. The team should know this because it affects how cross-topic comparisons are interpreted if other topics see the same pattern.

**Question for the team:** Does anyone's ecosystem show a different distribution? (e.g. Python topics may have more visible Egyptian repos because of data science work)

### 2. Snowball expansion did not converge in 3 rounds
Round 1: 5,267 new accounts → Round 2: 8,653 → Round 3: 5,427. It accelerated in round 2 rather than shrinking, suggesting a dense sub-network not reachable from the initial seeds. A 4th round would likely find more accounts.

**Question for the team:** Did other topics run snowball expansion? Did it converge for them?

### 3. Near-zero overlap between global and Egyptian corpora
Only 3 of 77,315 repos appeared in both the global base corpus and the Egyptian developer corpus. Egyptian developers are essentially working in a completely separate segment of GitHub from the globally-popular repos. This is a substantive finding, not a bug.

**Implication for the team:** The Egypt vs. global comparison is between genuinely separate populations — which is actually good for RQ2 validity.

### 4. Arabic location terms are essential
A significant portion of Egyptian developers on GitHub use Arabic-script location strings (مصر، القاهرة، الإسكندرية). Studies using only English terms systematically undercount Egyptian developers.

**Check with team:** Did everyone include Arabic-script location terms in their Stage 2a seed discovery? If not, their Egyptian seed list may be undercounting.

---

## Decisions We Need to Make Together

### Decision 1 — Stratum thresholds: are we all using the same?
The shared methodology says:
- Small: 0–50 stars
- Medium: 51–500 stars  
- Large: > 500 stars

**Problem:** My Egypt corpus is 95.9% small-stratum because there is no star minimum filter. Other topics that filtered differently may have very different distributions. If we report stratum-level adoption rates, they are only comparable if thresholds are identical.

**Action needed:** Everyone confirms they are using these exact thresholds. If anyone changed them, we need to know now before Stage 4.

---

### Decision 2 — Shared detection signals: which are common to all topics?

The Stage 4 detection script for Topic 2 checks these signal types:

| Signal type | Example | Shared or Topic 2 specific? |
|---|---|---|
| Config file — `CLAUDE.md` | File exists at root | **Shared — all topics** |
| Config file — `AGENTS.md` | File exists at root | **Shared — all topics** |
| Config file — `.cursorrules` | File exists at root | **Shared — all topics** |
| Config file — `.github/copilot-instructions.md` | File exists | **Shared — all topics** |
| Commit trailer | `Co-authored-by: claude <noreply@anthropic.com>` | **Shared — all topics** |
| Bot author login | `github-copilot[bot]` | **Shared — all topics** |
| Author email | `noreply@anthropic.com` | **Shared — all topics** |
| PR body marker | `Generated with Claude Code` | **Shared — all topics** |
| PR branch prefix | `codex/`, `copilot/`, `cursor/` | **Shared — all topics** |
| npm dependency | `@anthropic-ai/sdk` in package.json | **Topic 2 only** |

**Questions for the team:**
- Are you all checking the same config files in Pass 1?
- Are you all scanning the same commit trailer patterns?
- What ecosystem-specific signals does each topic add? (pip packages for Python, gems for Ruby, etc.)

---

### Decision 3 — Egypt corpus commit detection: how is each topic handling it?

**The problem:** 72,000+ repos is too many to scan commit-by-commit via REST API in a reasonable time.

**Topic 2 approach:** Two-pass design:
- Pass 1: GraphQL config file check → ALL repos (~3-4 hours)
- Pass 2: REST commit/PR scan → base corpus only (4,372 repos, ~2 days)
- Egypt corpus gets config file detection only

**Alternative considered:** BigQuery + GH Archive for Egypt commit scan (rejected due to $50 card hold requirement for this topic)

**Questions for the team:**
- How are you handling Egypt corpus commit detection?
- Is anyone using BigQuery?
- Should we standardize this decision across topics so results are comparable?

---

### Decision 4 — Single-signal vs multi-signal as primary adoption metric

Topic 2 produces three adoption columns for RQ1:
- `agent_adopted_single` — commit trailers only (what a naive study would find)
- `agent_adopted_multi` — any signal type found
- `agent_adopted` — canonical label (same as multi)

The difference between single and multi rate is the **undercounting gap** that RQ1 asks about.

**Questions for the team:**
- Are you all producing both single and multi adoption labels?
- Are we reporting the same "primary" adoption rate in our theses so cross-topic comparison makes sense?
- What is the team's agreed definition of `agent_adopted = True`? (Suggestion: multi-signal union)

---

### Decision 5 — Output schema: are our CSV columns compatible?

For the cluster's results to be aggregated and compared, the key columns must be identical across all topics. The shared methodology specifies these for `unified_corpus_detected.csv`:

```
repo_id, full_name, primary_language, stars, corpus_source,
stratum, agent_adopted, agent_adopted_single, agent_adopted_multi,
first_detected_at, agent_name, adoption_month
```

**Action needed:** Everyone checks their output schema against this list. If columns are named differently or missing, we need to agree on a standard now — not after Stage 4 is run.

---

### Decision 6 — Study snapshot date: are we all using 2026-09-01?

The shared methodology specifies `STUDY_SNAPSHOT_DATE = 2026-09-01`. This means:
- No commits or PRs after this date are counted
- All corpus pulls are bounded by this date
- All metrics are computed as of this date

**Action needed:** Every topic confirms this date is hardcoded in their Stage 4 script.

---

## Questions I Want to Ask the Team

1. **What is your base corpus size?** Topic 2 has 4,372. Is this comparable to other topics or significantly different?

2. **What is your Egyptian developer corpus size?** Topic 2 has 72,946. Did any topic end up with very few Egyptian repos (triggering the "widen to MENA" contingency)?

3. **Did everyone implement the I-4 (≥10 commits) and I-5 (≥2 authors) filters?** These require fetching commit count and contributor count from the API. Topic 2 skipped these in the GraphQL pull due to rate limit cost (they trigger full history traversal). If other topics applied them differently our filtering is inconsistent.

4. **What manifest file does each topic check for?** Topic 2 checks `package.json`. This is how we confirm a repo actually uses npm. Do all topics have an equivalent check?

5. **How is each topic handling the `package.json` / manifest check at scale?** Topic 2 removed this from the bulk GraphQL query because it caused 502 timeout errors and used `primaryLanguage` as a proxy instead.

6. **Is anyone ahead on Stage 4 or Stage 5?** Topic 2 hasn't run Stage 4 yet. If someone else has, we should compare signal counts before finalizing the detection scripts.

7. **How will the cluster's combined results be presented?** Will there be a shared paper/report at the end, or is each thesis standalone with cross-references?

---

## Things to Watch Out For in the Discussion

- **Don't assume corpus sizes are comparable across topics.** Some ecosystems (Python, JavaScript) have far more GitHub repos than others (Rust, Haskell). The base corpus sizes will differ significantly.

- **The Egypt corpus size mismatch is expected.** Topic 2 has 72,946 Egypt repos vs. 4,372 global repos. This ratio will differ by topic. It's not a methodology error.

- **Star stratification will look very different across topics.** For Topic 2, the Egyptian corpus is 95.9% small. This is ecosystem-specific — course assignments and portfolios dominate JS/TS on GitHub. Python might look different due to more data science academic repos.

- **The 3-repo overlap is a finding worth sharing.** It shows the Egyptian developer community works in a genuinely separate segment of the GitHub ecosystem. Other topics should check their own overlap count — if they see the same pattern, that's a cross-ecosystem finding worth noting in the cluster's shared report.

- **Don't agree to change Stages 1–3 retroactively.** Stages 1–3 are complete for Topic 2 and the data is collected. Any "we should have done X" discussion is only useful for future work or to note as a limitation — not as a reason to re-run.

---

## Suggested Meeting Agenda (propose this to the team)

| Time | Item |
|---|---|
| 10 min | Each topic: status update (which stages are complete, corpus sizes) |
| 15 min | Decision 1 & 2: stratum thresholds + detection signals alignment |
| 10 min | Decision 3: Egypt corpus commit detection approach |
| 10 min | Decision 4 & 5: adoption metric definition + output schema |
| 5 min | Decision 6: snapshot date confirmation |
| 10 min | Open questions and cross-topic findings |
| 5 min | Action items and next sync date |

---

## My Action Items After the Meeting

- [ ] Record agreed signal list and compare against Topic 2's `AGENT_CONFIG_FILES` dict
- [ ] Confirm output schema columns with the team's agreed standard
- [ ] Share `stage4_detection.py` with the team if they want to adapt it
- [ ] Note any topics that are ahead in the pipeline so I can check their detection outputs
- [ ] Update `SHARED_CORPUS_METHODOLOGY.md` with any decisions made in the meeting

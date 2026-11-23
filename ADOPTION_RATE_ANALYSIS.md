# Agentic Adoption Rate — Methodology & Numbers

Analysis of **detect run 4** corpus. All numbers computed directly from
`bundle.json` + `detections.csv` under
`runs/157a81585a78245133f25fd4e7304c7ea9cfa8f1a1be96554007ddfd0b2a8a72/4/`.

- **Corpus size:** 60,129 repositories
- **Evidence rows processed:** 2,109,626 (after excluding `rejected_noise`)

---

## TL;DR — Two Definitions, Two Numbers

| Definition | Repos | Rate |
|---|---:|---:|
| **Activity-based** — repo has AI-authored commits (`adoption_level ≠ none`) | 26,216 | **43.6%** |
| Activity + AGENTS.md convention file | 28,201 | 46.9% |
| **Presence-based** — repo has any named-agent fingerprint | 42,489 | **70.7%** |
| Presence + AGENTS.md generic marker | 44,474 | 74.0% |

The 43.6% figure is what the dashboard reports today. The ~70% figure matches
earlier script-based analyses and reflects presence of configuration/evidence,
not commit-level activity.

---

## 1. What the Dashboard Reports (43.6%)

**Rule:** a repo is agentic iff its `adoption_level ∈ {experimental, limited,
consistent, pervasive}`.

**How `adoption_level` is computed** (`src/detect/attribution.py:391`):

```python
ratio = AI-authored commits / total commits
if ratio == 0:       level = "none"
elif ratio < 0.01:   level = "experimental"
elif ratio < 0.05:   level = "limited"
elif ratio < 0.20:   level = "consistent"
else:                level = "pervasive"
```

A repo with strong config evidence (e.g. a `.cursor/` folder) but **zero
AI-authored commits** ends up at `none` — it is excluded from the 43.6%.

Distribution of levels in the corpus:

| Level | Repos |
|---|---:|
| none | 33,913 |
| limited | 5,653 |
| consistent | 5,719 |
| pervasive | 14,844 |
| experimental | 0 |

---

## 2. Presence-Based View (70.7%)

**Rule:** a repo is agentic if it has **any named-agent fingerprint** — i.e.,
at least one row in `detections.csv` where:

- `family_name ≠ "Generic"` (excludes AGENTS.md, AI-Assistant alias, ai-generated label)
- `channel ≠ "content"` (excludes the AGENTS.md content classifier fallback)
- `evidence_semantics ≠ "rejected_noise"`

Channels that qualify:

- `file` — product-owned config paths (`.cursor/`, `.claude/`, `.aider.conf.yml`, …)
- `author` / `commit_trailer` / `pr_metadata` — commit/PR identities naming an agent
- `branch` — agent-named branches (`cursor/*`, `claude/*`, …)
- `label` / `bot` / `issue` — PR labels, bot identities, issue metadata

**Result:** 42,489 repos (70.7%).

This is the number comparable to the earlier script-based detection.

---

## 3. The Gap — Why 43.6% and Not 70.7%?

The two definitions disagree on **16,273 repos (27.1% of the corpus)**. These
are repos with named-agent fingerprint evidence but a commit ratio of 0.

Likely causes:

1. Developer squashes/rebases commits, dropping agent trailers.
2. Agent is used in IDE/chat mode without the commit-level integration.
3. Agent authored on another fork/branch we don't scan.
4. Config is dormant (set up once, never actively used).

This gap is itself a finding: ~half of the repos that configure an agent are
not producing commit-level AI evidence.

---

## 4. AGENTS.md — A Shared Convention, Not a Product

`AGENTS.md` is the shared agents.md spec — any agent can consume it. It is not
a product fingerprint, so the detector treats it as the pseudo-agent `Generic`
and **does not score it toward adoption** on its own (see
`src/detect/content_attribution.py`).

### Three nested slices

| Slice | Repos | % of corpus |
|---|---:|---:|
| Has an `AGENTS.md` file | 20,253 | 33.7% |
| &nbsp;&nbsp;↳ of those, **not** currently agentic | 9,453 | 15.7% |
| &nbsp;&nbsp;&nbsp;&nbsp;↳ of those, no other named-agent signal at all (**pure AGENTS.md-only**) | 1,985 | 3.3% |

### What each slice means

- **20,253 — has AGENTS.md:** one in three repos has adopted the convention,
  regardless of which tool (if any) is in use.
- **9,453 — AGENTS.md + not agentic:** convention file present but no
  AI-authored commits. Either the fingerprints are all config-only, or
  AGENTS.md is the only signal.
- **1,985 — pure AGENTS.md-only:** no product-owned paths, no agent-named
  branches/authors, no commit trailers. The only signal is the convention
  file. These are the repos most impacted by the AGENTS.md attribution bug
  listed in `TODO_NOTES.md` — if the content classifier (`agents-md-v1`) ran
  correctly against these files, some fraction would gain a direct product
  attribution.

### Why the detector excludes AGENTS.md from scoring

Design rationale in `src/detect/content_attribution.py`:

- 42% of sampled AGENTS.md files never name any product.
- Bare mentions give false-positive rates of 12–98% depending on the product
  (e.g. "move the cursor" → Cursor).
- The content classifier attributes an agent **only** when the file explicitly
  addresses one ("you are Claude Code", "# Claude Code Guidelines"). Everything
  else is logged as a Generic marker and never scored.

This is a precision-first policy. The 1,985-repo residue is the direct cost of
that policy. Whether that cost is acceptable depends on the research question.

### Impact of relaxing the exclusion

Treating AGENTS.md presence as scoring evidence (on top of activity-based):

- 26,216 → **28,201 repos → 46.9%** (+1,985, +3.3 pp)

---

## 5. Legacy Rules — Negligible Impact

Rules marked `rule_lifecycle = "legacy"` in the detection packs are older
detection patterns kept for backward compatibility.

| Slice | Repos |
|---|---:|
| Repos with any legacy-rule fingerprint | 905 |
| Repos whose **only** product evidence is a legacy rule | 4 |
| Of those, not currently agentic | 4 |

**Bottom line:** removing legacy rules entirely would change the headline
number by ~0 repos. The "legacy agent" cleanup is a code-hygiene task, not a
statistics-moving one.

---

## 6. Content Classifier — Zero Attributions in This Run

The AGENTS.md content classifier (channel = `content`) produced **0 named
attributions** in detect run 4. All AGENTS.md effects reported above come from
file presence alone, not content-based classification.

This is consistent with the `AGENTS.md attribution bug` noted in
`TODO_NOTES.md` — the classifier is either not running or failing to match.

---

## 7. Full Signal-Class Matrix

| Signal class | Repos | % |
|---|---:|---:|
| Any direct named-agent evidence (fingerprint) | 42,479 | 70.6% |
| AGENTS.md file present | 20,253 | 33.7% |
| Any Generic marker (AGENTS.md, AI Assistant, ai label) | 20,284 | 33.7% |
| Legacy-rule fingerprints | 905 | 1.5% |
| AGENTS.md content classifier attributions | 0 | 0.0% |

Union of all positive signal classes: **44,474 repos (74.0%)**.

---

## 8. Recommendations for the Paper

1. **Report both numbers side-by-side.** Activity-based (43.6%) and
   presence-based (70.7%) are both defensible and measure different things.
   The gap itself is a methodological contribution.

2. **Keep AGENTS.md broken out separately.** It is a convention, not a
   product. Reporting it as a third category (presence of convention vs.
   presence of product vs. commit-level activity) makes the ecosystem story
   clearer.

3. **Fix the AGENTS.md content classifier before final numbers.** 0
   attributions out of ~20k AGENTS.md files is implausibly low. Expect the
   agentic rate to shift upward once that pipeline is repaired, particularly
   in the 1,985 pure-AGENTS.md-only subset.

4. **Legacy rules can be pruned at any time** — moving 4 repos won't affect
   any reported number.

---

*Generated 2026-11-19 from detect run 4 bundle & detections CSV.*
*Reproducer: `/tmp/adoption_breakdown2.py`.*

# Stage 2 — Owner Identity Analysis
**Goal:** For every repository in the global random sample (4,500 repos), determine whether its owner is an Egyptian developer.

---

## Why Stage 2 exists

The global random sample (Stage 1c) was drawn proportionally from all GitHub JS/TS repos created after 2025-02-24. Egyptian developers represent a tiny fraction of the global GitHub population. Stage 2 answers a critical question: **of those 4,500 randomly selected repos, how many are owned by Egyptians?**

This number:
- Quantifies Egyptian developer representation in the global JS/TS ecosystem
- Is an unbiased data point (randomly sampled, not targeted)
- Justifies why Stage 3 was needed (result was only 10 repos — too few for statistical analysis)

---

## How it works — 4 scripts, 9 signals

Stage 2 processes 4,374 unique owners across four scripts. Signals are applied cheapest-first — once an owner reaches score ≥ 10 (confirmed), no further signals are checked.

### Signal table

| Signal | What it checks | Points | Script |
|--------|---------------|--------|--------|
| S1 | Profile location field = Egypt / Cairo / Alexandria / مصر / etc. | **10** | 2a |
| S2 | Bio contains Arabic text or Egyptian university/keyword | **5** | 2a |
| S3 | Company field has Egyptian org name or .eg domain | **5** | 2a |
| S4 | Email has .eg TLD or Egyptian university domain | **8** | 2a |
| S5 | Member of a GitHub org with Egyptian location | **7** | 2b |
| S6 | ≥40% of followers/following are confirmed Egyptian | **5** | 2b |
| S7 | ≥40% of repo contributors have confirmed Egyptian location | **7** | 2c |
| S8 | README or CONTRIBUTING has >10% Arabic characters | **3** | 2c |
| S9 | Code/README contains Egyptian patterns (phone: 010/011/012/015, +20, EGP, NID) | **4** | 2c |

**Hard negative rule:** If S1 fires but the location is a non-Egyptian country (e.g. "Ukraine", "Germany") → immediately mark `not_egyptian`, skip all remaining signals. This affected **1,720 owners** and saved significant API quota.

---

## Step-by-step walkthrough

### Stage 2a — Profile signals (S1–S4)
- Input: `data/stage1/sample_corpus.csv` → extract 4,374 unique owner logins
- Batch-fetch GitHub profiles via GraphQL (50 owners per request, ~90 requests total)
- Apply S1, S2, S3, S4 to each profile
- S1 hard negative → immediately mark `not_egyptian`
- Output: `data/stage2/owner_signals.csv`

**Result after 2a:**
- 1,720 owners marked `not_egyptian` (hard negative on S1)
- 6 owners already `egyptian_confirmed` (score ≥ 10 — no further signals needed)
- 2,648 owners passed forward to Stage 2b (`needs_more = True`)

---

### Stage 2b — Social signals (S5–S6)
- Input: `data/stage2/owner_signals.csv` — only the 2,648 owners with `needs_more = True`
- S5: fetch each user's GitHub organizations, check org location fields
- S6: fetch followers + following (top 50 each), count Egyptian locations
- Output: `data/stage2/owner_signals.csv` (updated with s5, s6 scores)

**Result after 2b:**
- S5 fired: 1 owner
- S6 fired: 2 owners
- New Egyptian owners found via social signals: 3

---

### Stage 2c — Repo-level signals (S7–S9)
- Input: owners with `needs_more = True` after 2b (2,648 owners)
- S7: fetch top-20 contributors per repo via REST, check their locations via GraphQL
- S8: fetch README.md + CONTRIBUTING.md, count Arabic Unicode characters (U+0600–U+06FF)
- S9: scan README + CONTRIBUTING for Egyptian-specific patterns
- Output: `data/stage2/owner_signals_full.csv`

**Result after 2c:**
- S7 fired: 2 owners
- S8 fired: 5 owners
- S9 fired: 13 owners (most fired signal after S1)

---

### Stage 2d — Final classification
- Input: `data/stage2/owner_signals_full.csv` + `data/stage1/sample_corpus.csv`
- Sum all 9 signal scores per owner
- Apply classification thresholds
- No API calls — runs in seconds

**Classification thresholds:**

| Score | Condition | Label | In Egypt corpus? |
|-------|-----------|-------|-----------------|
| ≥ 10 | any | `egyptian_confirmed` | ✅ Yes |
| 5–9 | any | `egyptian_probable` | ✅ Yes |
| 1–4 | ≥ 2 signals fired | `egyptian_probable` | ✅ Yes |
| 1–4 | 1 signal only | `unconfirmed` | ❌ No — weak single signal |
| 0 | 0 signals | `unclassified` | ❌ No — no evidence |
| S1 hard negative | — | `not_egyptian` | ❌ No |

---

## Final numbers

| Classification | Owners | % of 4,374 |
|---------------|--------|-----------|
| `not_egyptian` | 1,720 | 39.3% |
| `unclassified` | 2,626 | 60.0% |
| `unconfirmed` | 18 | 0.4% |
| `egyptian_confirmed` | 6 | 0.1% |
| `egyptian_probable` | 4 | 0.1% |
| **Total** | **4,374** | **100%** |

**Egyptian repos found in global sample: 10** (6 confirmed + 4 probable owners)

---

## Signal firing counts (across all 4,374 owners)

| Signal | Times fired |
|--------|------------|
| S1 (location field) | 5 |
| S2 (bio/Arabic) | 2 |
| S3 (company/.eg) | 2 |
| S4 (email) | **0** |
| S5 (org membership) | 1 |
| S6 (network) | 2 |
| S7 (contributors) | 2 |
| S8 (Arabic README) | 5 |
| S9 (Egyptian patterns) | **13** |

S9 was the most fired signal after S1, meaning Egyptian-specific text patterns in README files (phone numbers, EGP, +20) were more discoverable than email domains or org memberships.

---

## How the 10 Egyptian repos were found

| Repo | Classification | Score | Location source |
|------|---------------|-------|----------------|
| seif-a096/Prodexa_FrontEnd | confirmed | 15 | direct (S1) |
| atefdiabmohamed/Laravel12_course | confirmed | 10 | direct (S1) |
| D-engahmed/ancient | confirmed | 15 | direct (S1) |
| Boghdady/nestjs-airbnb-clone-api | confirmed | 10 | direct (S1) |
| Mazen-Haytham/PetAdoption | confirmed | 10 | direct (S1) |
| Esraa-Dev/Al-Shifa-Clinic | confirmed | 15 | direct (S1) |
| shekohex/opencode-pty | probable | 7 | social/repo signals |
| raven-swe/frontend | probable | 7 | social/repo signals |
| OmarNaru1110/byto | probable | 5 | social/repo signals |
| mnemosyne-systems/billetsys | probable | 7 | social/repo signals |

---

## Why 60% were unclassified — and what this means

**2,626 out of 4,374 owners (60%) ended up `unclassified` — meaning after running all 9 signals, we found zero evidence about their nationality.**

This is not a failure of the methodology. It reveals a real characteristic of GitHub: **the majority of developers share no location information at all.**

- No location in profile field
- No Arabic in bio or README
- No .eg email
- No Egyptian org membership
- No Egyptian contributors
- No Egyptian phone/currency patterns in their code

This 60% represents developers who are anonymous by default. They could be from Egypt, but there is no signal to confirm it. From a thesis perspective, this is important because:

1. **It proves the necessity of the targeted corpus (Stage 3).** If 60% of owners are invisible even to a 9-signal pipeline, a random sample will always undercount Egyptian developers by a large margin.

2. **It means the 10 repos found are almost certainly an undercount.** Some of those 2,626 `unclassified` owners may be Egyptian developers who simply do not disclose their location anywhere on GitHub.

3. **It shows that Egyptian developer presence in global open source is systematically harder to measure** than for developers in countries like the US or Germany, who more commonly fill in location fields with recognizable names.

---

## Outputs

| File | Location | Description |
|------|----------|-------------|
| `owner_signals.csv` | `data/stage2/` | S1–S6 scores (intermediate) |
| `owner_signals_full.csv` | `data/stage2/` | All 9 signal scores per owner |
| `owners_final.csv` | `data/stage2/` | Final classification for all 4,374 owners |
| `egypt_corpus.csv` | `data/stage2/` | The 10 Egyptian repos found in the global sample |
| `coverage_stats.csv` | `data/stage2/` | Signal contribution breakdown for thesis table |

---

## What Stage 2 feeds into

- **RQ3** — The 10 Egyptian repos from Stage 2 represent Egyptian developers in the *random* global sample. This unbiased proportion (~0.2%) is compared against the targeted Stage 3 corpus adoption rate.
- **Undercounting narrative** — The 60% unclassified rate is cited as evidence that Egyptian developer identification is inherently difficult, motivating the need for a separate targeted Egyptian corpus.
- **Stage 3 justification** — 10 repos is insufficient for Fisher's exact test or Mann-Whitney U. Stage 3 was built specifically because Stage 2 confirmed the random sample cannot yield a sufficient Egyptian sub-sample.

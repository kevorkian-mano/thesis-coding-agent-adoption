# New Methodology Support

Reference document for the Stage 3 rewrite. Return to this when the teammate provides the agent list and signal document.

---

## 5. Binary Classification — No AI-Assisted Label, No Signal Tiers

The rewrite drops the three-label system (`agentic` / `ai_assisted` / `none`) and the STRONG / MEDIUM / WEAK tier framework. Classification becomes binary: a repo is either **agentic** or **none**. There are no partial or uncertain labels. Signal types are still collected (config file, commit trailer, bot author, PR branch prefix, CI action, .gitignore entry, PR label/topic, PR body keyword) but they are not weighted or tiered — any confirmed signal makes the repo agentic.

---

## 1. Stage 3 Must Align with the "Agentic Much?" Paper

The current Stage 3 implementation (3a config files, 3b commit trailers, 3c deep scan) diverges from the detection methodology used in Robbes et al. (2025) *"Agentic Much? Adoption of Coding Agents on GitHub"*. The rewrite must follow the paper's signal approach as its base, then extend it with additional agents not present in the paper (new tools released since publication).

---

## 2. Timestamps Collected During the Same Scan

The rewrite must collect the **first AI signal timestamp per repo during Stage 3 itself** — not as a separate post-hoc pass. This avoids the situation we ran into with Stage 5i (config timestamps), 5j (trailer timestamps), and 5k, which were only necessary because timestamps were not captured during the original Stage 3 run. Any commit or PR signal found must record its `committedDate` / `createdAt` at detection time.

---

## 3. All Passes Must Run on All Repos — Full Agent Accumulation

Currently, once a repo is marked `agentic` in Pass 1 (e.g. via a config file), Pass 2 and Pass 3 skip it. This means a repo detected via Claude Code config in Pass 1 may also have Aider commit trailers in Pass 2 that never get recorded. The rewrite must:
- Run all signal checks on every repo regardless of early detection
- Accumulate **all** detected agents per repo (not just the first one found)
- Assign the final `adoption_label` only after all passes are complete

---

## 4. Wait for Teammate's Agent + Signal Document

Do not write any new Stage 3 code until the teammate provides the document listing:
- All agents to detect (including those not in the paper)
- Signal types and patterns per agent (config paths, trailer patterns, bot accounts, branch prefixes, CI actions, etc.)
- Any agreed-upon tier classifications (STRONG / MEDIUM / WEAK or equivalent)

The rewrite should be a single unified script based on that document, not an incremental patch to the existing 3a/3b/3c structure.

---

## 6. Fetch Maximum Useful Data During Detection — No Post-Hoc Passes

When scanning a repo during Stage 3, collect every field that could be useful in any downstream analysis — do not limit fetching to what is strictly needed for classification. Anything retrievable from the same GraphQL query costs nothing extra. Fields to capture at detection time include but are not limited to:

- First AI signal date (commit `committedDate`, PR `createdAt`)
- All detected agents (not just the first)
- Signal type(s) that triggered detection (config file, trailer, bot, branch, CI, etc.)
- Commit trailer count and total commit count (for density metric)
- PR count, issue count if available
- Repo creation date, star count, fork count, primary language, topics
- Owner location if available from profile

The lesson from Stage 5i/5j/5k is that going back to re-fetch data is expensive (hours of API time). **Fetch once, fetch everything.**

---

## 7. JS/TS-Specific Analysis — Ideas to Develop Later

The JS/TS stack has unique ecosystem signals that other stacks do not. The following analysis ideas are specific to this stack and should be revisited when designing Stage 5 for JS/TS:

- **Package manager as proxy for project modernity**: pnpm/bun repos show higher adoption than yarn/vanilla — explore whether this is a confound or a genuine signal of developer profile
- **Framework-level adoption rates**: which JS frameworks (React, Next.js, Hono, Astro, etc.) correlate most strongly with AI adoption and why — explore if framework choice predicts agent choice
- **npm dependency analysis**: do agentic repos have more dependencies, newer dependency versions, or different dependency categories than non-agentic repos
- **TypeScript vs JavaScript split**: TS repos show 78.5% adoption vs JS 62.0% — analyse whether this gap holds within frameworks and income groups
- **MCP (Model Context Protocol) repos**: a subset of repos may expose MCP servers — this is JS/TS-heavy and worth tagging as a sub-category
- **Claude Code + npm combination**: Claude Code is dominant; are there patterns in which npm packages or scripts get added to `package.json` in Claude Code repos
- **Monorepo detection**: large repos with workspaces may behave differently from single-package repos in terms of adoption timing and tool choice

# Open Items & Research Notes

A running list of outstanding engineering fixes, open questions, and research-paper logistics.

---

## 1. Fix the `AGENTS.md` detection issue
The current detector has a bug around how `AGENTS.md` files are recognised and attributed. We need to audit the matcher, confirm which repos are being missed (or mis-classified), and tighten the rule so that `AGENTS.md` evidence is captured consistently across the corpus.

## 2. Rework the legacy "agentic signals" path
The older agentic-signal logic still lingers in parts of the pipeline and is producing inconsistent output. We need to trace every call site, decide what to keep vs. retire, and align the legacy signals with the current lifecycle model (`ever_observed` → `current_activity` → `currently_configured`).

## 3. Clarify what the "Fast mode" feature does
Document, end-to-end, what Fast mode actually changes at runtime: which steps it skips, which heuristics it relaxes, and what the trade-off is in terms of recall vs. speed. Right now the behaviour is implicit — we need an explicit spec.

## 4. GitHub Pro — do we get extra credits / tokens?
Check whether a GitHub Pro subscription raises the API rate limits, Copilot token budget, or any other quota that would be material for this project. If yes, decide whether upgrading is worth the cost given the scraping / detection volume.

## 5. Normalize cross-stack graphs for better visualisation
The cross-stack comparison charts currently mix absolute counts with percentages depending on the panel, which makes them hard to read side-by-side. Pick a consistent normalisation (per-stack share, per-repo rate, 95% Wilson CI, etc.) and apply it uniformly so stacks are directly comparable.

## 6. Explore 3D visualisations
Consider whether a small number of 3D views (e.g., stack × country × adoption-depth, or stack × time × agent-family) would add genuine insight — or whether they will just add visual noise. Prototype one or two and evaluate honestly before committing.

## 7. Evaluate competing / inspiration tools
Look at how these tools present similar data and decide what, if anything, to adopt:
- **Ponytail**
- **Graphically**
- **Caveman**
- **Omnirouter**

Focus on the visual grammar and interaction model, not the backend.

## 8. Paper template
The research paper will be written using the **Elsevier (ELS) article template** on Overleaf. Set up the Overleaf project with that template before the writing phase begins so that formatting choices don't block content work later.

## 9. Finalise the paper sections
The following sections need a full pass — polish the wording, tighten the arguments, and make sure the narrative flows from one into the next:
- Introduction
- Literature Review
- Methodology
- Implementation
- Results
- Discussion

The goal here is rephrasing and cohesion, not rewriting from scratch.

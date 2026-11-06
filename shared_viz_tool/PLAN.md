# Shared Visualization Tool — Feasibility Plan

## What it does

A single Python dashboard that loads the final output CSVs from all 6 team
members and renders side-by-side comparative charts across language stacks
(Python, Java, JavaScript, Rust, C#, C++ or whichever stacks the team covers).

Every member runs the same shared_methodology pipeline, so the output schemas
are identical — one tool reads all of them without modification.

---

## What each member submits

Each member produces one file at the end of their pipeline and drops it into a
shared folder (e.g. a shared Google Drive or the repo itself):

| File | Produced by | Key columns |
|---|---|---|
| `final_corpus.csv` | Stage 3 merge | full_name, adoption_label, agents_found, signal_source |
| `stage4_summary.csv` | Stage 4 | country_code, continent, n_repos, n_agentic, agentic_pct |
| `stage5_summary.csv` | Stage 5 | metric, value (one row per extended-analysis result) |

The file must include a `stack` column (e.g. `"Python"`) so the tool knows
which member it came from. This is added in one line before submitting:

```python
df["stack"] = "Python"   # each member sets their own stack name
df.to_csv("final_corpus.csv", index=False)
```

---

## Concrete example — TypeScript/JavaScript stack (Mano's pipeline)

This shows exactly what the preparation step looks like for a real pipeline.

### Files available after Stage 5 completes

```
data/stage3/pass1_results.csv        → repos caught by config files
data/stage3/pass2_results.csv        → repos caught by commit trailers
data/stage3/pass3_results.csv        → repos caught/missed by deep scan
data/stage1/global_corpus.csv        → all 60,129 repos with metadata
data/stage2/owner_locations_all.csv  → country/continent per owner
```

### Merge script (run once, ~30 seconds)

```python
import pandas as pd

# load the three detection passes
p1 = pd.read_csv("data/stage3/pass1_results.csv")
p2 = pd.read_csv("data/stage3/pass2_results.csv")
p3 = pd.read_csv("data/stage3/pass3_results.csv")

# load corpus and location data
corpus   = pd.read_csv("data/stage1/global_corpus.csv")
location = pd.read_csv("data/stage2/owner_locations_all.csv")

# merge all three passes into one flat table
detection = pd.concat([p1, p2, p3], ignore_index=True)
detection = detection.drop_duplicates("full_name")

# join everything together
final = corpus.merge(
    detection[["full_name", "adoption_label", "agents_found", "signal_source"]],
    on="full_name", how="left"
)
final = final.merge(
    location[["owner_login", "inferred_country", "continent"]],
    on="owner_login", how="left"
)

# tag the stack — this is the only line that differs per team member
final["stack"] = "TypeScript/JavaScript"

final.to_csv("shared_viz_tool/data/ts_js_final_corpus.csv", index=False)
print(f"Saved {len(final):,} repos")
```

### What the output looks like

| full_name | stars | primary_language | adoption_label | agents_found | inferred_country | stack |
|---|---|---|---|---|---|---|
| vercel/next.js | 125000 | TypeScript | agentic | Claude Code\|Copilot | US | TypeScript/JavaScript |
| facebook/react | 220000 | JavaScript | unclassified | | US | TypeScript/JavaScript |
| sindresorhus/got | 14000 | TypeScript | agentic | Aider | NO | TypeScript/JavaScript |

60,129 rows total — one per repo.

### What the Java member's file looks like

Identical structure, different repos, `stack = "Java"`. The visualization tool
stacks all members' files on top of each other and groups by `stack` to compare.

---

## Technology choice

**Streamlit** — recommended.

- Pure Python, same language the whole team already uses
- An interactive app in ~200 lines
- Runs locally: `streamlit run app.py`
- No server needed; each person can run it on their own machine once they have
  all 6 CSV files

Alternative: a plain matplotlib script (`compare.py`) that saves static PNG
figures. Much simpler (50 lines), no browser, no extra dependency. Good enough
for a thesis appendix.

**Recommendation**: build the matplotlib version first (1 day of work), then
optionally wrap it in Streamlit if the supervisor wants an interactive demo.

---

## Charts to produce

### Cross-stack adoption comparison
- Bar chart: agentic adoption rate (%) per stack
- Bar chart: top 5 agents per stack (grouped bars)
- Table: total repos, agentic repos, unclassified repos per stack

### Geographic analysis
- Choropleth or bar chart: top 10 countries per stack overlaid
- Bar chart: continent distribution per stack
- Heatmap: stack × continent adoption rate

### Extended analysis (Stage 5)
- Bar chart: agent diversity (single-agent vs multi-agent) per stack
- Bar chart: AI commit density buckets per stack
- Bar chart: top world regions per stack

### Statistical comparison
- 95% Wilson CI error bars on all adoption rates
- Note where sample sizes are too small to compare

---

## Architecture

```
shared_viz_tool/
  PLAN.md                  ← this file
  app.py                   ← Streamlit app (built after all members finish)
  compare.py               ← static matplotlib version (built first)
  data/                    ← each member drops their CSVs here
    python_final_corpus.csv
    java_final_corpus.csv
    javascript_final_corpus.csv
    ...
  figures/                 ← output PNGs saved here
  requirements.txt
```

---

## Run order

```bash
# static version (no extra setup beyond the existing venv)
python3 compare.py

# interactive version
pip install streamlit
streamlit run app.py
```

---

## Effort estimate

| Task | Who | Time |
|---|---|---|
| Agree on submission format (stack column, file names) | Whole team | 30 min meeting |
| Build `compare.py` (static charts) | One person | 1 day |
| Wrap in Streamlit (`app.py`) | One person | 1 extra day |
| Each member prepares and submits their CSVs | Each member | 15 min |
| Final review / export for thesis | One person | 2 hours |

**Total**: 2–3 days of actual coding, done by one person after everyone has
their final numbers. The rest of the team only needs 15 minutes to prepare
their submission files.

---

## Prerequisites

- All 6 members must have finished Stage 3 (minimum) before the tool is useful
- Stage 4 and Stage 5 outputs are needed for the full chart set
- One person volunteers to build the tool (or Mano builds it since the pipeline
  is already here)

---

## Open questions to settle with the supervisor

1. Which stacks are the 6 members covering?
2. Should the tool be interactive (Streamlit) or static figures (matplotlib)?
3. Does the final submission include the tool itself, or only the exported figures?
4. Is there a shared repository where members will submit their CSVs?

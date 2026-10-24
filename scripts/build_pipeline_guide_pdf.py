#!/usr/bin/env python3
"""
Build pipeline_scripts_guide.pdf using ReportLab.
Output: /pipeline_scripts_guide.pdf  (project root)
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.platypus.flowables import Flowable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT  = ROOT / "pipeline_scripts_guide.pdf"

# ── colours ──────────────────────────────────────────────────────────────────
BLUE_DARK   = HexColor("#1E3A5F")
BLUE_MED    = HexColor("#2563EB")
BLUE_LIGHT  = HexColor("#EFF6FF")
GREEN       = HexColor("#16A34A")
GREEN_LIGHT = HexColor("#F0FDF4")
AMBER       = HexColor("#D97706")
AMBER_LIGHT = HexColor("#FFFBEB")
PURPLE      = HexColor("#7C3AED")
GRAY        = HexColor("#6B7280")
GRAY_LIGHT  = HexColor("#F3F4F6")
RED         = HexColor("#DC2626")
W, H = A4

# ── styles ───────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

def S(name, **kw):
    base = styles.get(name, styles["Normal"])
    return ParagraphStyle(name + str(id(kw)), parent=base, **kw)

title_style    = S("Normal", fontSize=20, textColor=BLUE_DARK, fontName="Helvetica-Bold",
                   spaceAfter=4, alignment=TA_CENTER)
subtitle_style = S("Normal", fontSize=12, textColor=GRAY, spaceAfter=2, alignment=TA_CENTER)
author_style   = S("Normal", fontSize=10, textColor=GRAY, spaceAfter=16, alignment=TA_CENTER)
intro_style    = S("Normal", fontSize=9.5, textColor=black, leading=14, spaceAfter=8)
section_style  = S("Normal", fontSize=13, textColor=white, fontName="Helvetica-Bold",
                   spaceAfter=6, leftIndent=6)
script_style   = S("Normal", fontSize=11, textColor=BLUE_MED, fontName="Helvetica-Bold",
                   spaceAfter=4)
body_style     = S("Normal", fontSize=9, textColor=black, leading=13, spaceAfter=5)
bullet_style   = S("Normal", fontSize=9, textColor=black, leading=13,
                   leftIndent=14, firstLineIndent=-10, spaceAfter=2)
bold_style     = S("Normal", fontSize=9, fontName="Helvetica-Bold", textColor=BLUE_DARK,
                   spaceAfter=3)
small_style    = S("Normal", fontSize=8, textColor=GRAY, leading=11)
toc_style      = S("Normal", fontSize=9, leading=13)

def b(text):  return f"<b>{text}</b>"
def bl(text): return f"<font color='#2563EB'>{text}</font>"
def code(t):  return f"<font face='Courier' size='8.5'>{t}</font>"

# ── helper flowables ─────────────────────────────────────────────────────────

class SectionHeader(Flowable):
    def __init__(self, title, color=BLUE_DARK):
        Flowable.__init__(self)
        self.title = title
        self.color = color
        self.height = 24

    def draw(self):
        c = self.canv
        c.setFillColor(self.color)
        c.rect(0, 0, self._availableWidth, self.height, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(8, 7, self.title)

    def wrap(self, aw, ah):
        self._availableWidth = aw
        return aw, self.height


class InfoBox(Flowable):
    def __init__(self, text, bg=BLUE_LIGHT, border=BLUE_MED, width=None):
        Flowable.__init__(self)
        self.text   = text
        self.bg     = bg
        self.border = border
        self._width = width

    def wrap(self, aw, ah):
        self._aw = aw
        return aw, 0

    def draw(self):
        pass


def coloured_para(text, bg, border, w):
    t = Table([[Paragraph(text, body_style)]], colWidths=[w])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), bg),
        ("BOX",        (0,0), (-1,-1), 0.8, border),
        ("LEFTPADDING",  (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING",   (0,0), (-1,-1), 6),
        ("BOTTOMPADDING",(0,0), (-1,-1), 6),
    ]))
    return t


def numbers_table(rows, w):
    """rows = list of (label, value) tuples"""
    data = [[Paragraph(b(l), body_style), Paragraph(v, body_style)] for l, v in rows]
    t = Table(data, colWidths=[w*0.45, w*0.55])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), AMBER_LIGHT),
        ("BOX",        (0,0), (-1,-1), 0.8, AMBER),
        ("GRID",       (0,0), (-1,-1), 0.3, HexColor("#FDE68A")),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING",   (0,0), (-1,-1), 3),
        ("BOTTOMPADDING",(0,0), (-1,-1), 3),
        ("FONTSIZE",     (0,0), (-1,-1), 8.5),
    ]))
    return t


def contribution_box(text, w):
    return coloured_para(text, GREEN_LIGHT, GREEN, w)


def sp(n=6): return Spacer(1, n)

# ── page header/footer ───────────────────────────────────────────────────────
def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(GRAY)
    canvas.drawString(2*cm, 1.0*cm,
        "Pipeline Scripts Guide — AI Coding Agent Adoption Study")
    canvas.drawRightString(W - 2*cm, 1.0*cm,
        f"Manuel Youssef Haik Kevorkian  ·  Page {doc.page}")
    canvas.setStrokeColor(HexColor("#E5E7EB"))
    canvas.setLineWidth(0.4)
    canvas.line(2*cm, 1.3*cm, W - 2*cm, 1.3*cm)
    canvas.restoreState()

# ── document ─────────────────────────────────────────────────────────────────
doc = SimpleDocTemplate(
    str(OUT), pagesize=A4,
    leftMargin=2*cm, rightMargin=2*cm,
    topMargin=2*cm, bottomMargin=2*cm,
)
W_TEXT = W - 4*cm
story  = []

# ══════════════════════════════════════════════════════════════════════════════
# COVER PAGE
# ══════════════════════════════════════════════════════════════════════════════
story += [
    Spacer(1, 2*cm),
    Paragraph("Pipeline Scripts Guide", title_style),
    sp(4),
    Paragraph("Coding Agent Adoption in JavaScript / TypeScript / npm Repositories on GitHub",
              subtitle_style),
    sp(2),
    Paragraph("Manuel Youssef Haik Kevorkian  ·  October 2026  ·  DRAFT",
              author_style),
    HRFlowable(width="100%", thickness=1.2, color=BLUE_DARK, spaceAfter=12),
    Paragraph(
        "This document describes every pipeline script across the four stages of the study. "
        "Each page covers one script: what it does, what it reads, what it produces, "
        "the key numbers it generated from real data, and how it contributes to answering "
        "the three research questions. Scripts are presented in execution order. "
        "The pipeline has <b>13 scripts</b> organised into 4 stages and produces "
        "a final corpus of <b>60,129 repositories</b> with complete adoption labels "
        "and geographic metadata.",
        intro_style),
    sp(12),
]

# ToC table
toc_data = [
    [Paragraph(b("Stage"), toc_style), Paragraph(b("Script"), toc_style),
     Paragraph(b("Purpose"), toc_style), Paragraph(b("Key output"), toc_style)],
    ["1a", code("stage1a_collect_repos.py"),
     "GitHub API collection", "60,129 repos"],
    ["1b", code("stage1b_categorize_ecosystem.py"),
     "Lockfile detection", "ecosystem labels"],
    ["2a", code("stage2a_location_fast.py"),
     "Location field lookup", "13,625 owners located"],
    ["2b", code("stage2b_location_deep.py"),
     "Bio / TLD / network scan", "8,323 more located"],
    ["3a", code("stage3a_config_files.py"),
     "Config file existence check", "25,010 agentic"],
    ["3b", code("stage3b_commit_trailers.py"),
     "Commit trailer scan", "9,618 agentic + 3,846 ai-assisted"],
    ["3c", code("stage3c_deep_scan.py"),
     "Full GraphQL deep scan", "764 agentic + 4,657 ai-assisted"],
    ["3d", code("stage3d_reclassify.py"),
     "Reclassification (Pass 4)", "258 upgraded to agentic"],
    ["4a", code("stage4a_geographic_analysis.py"),
     "Country join + ranking", "65-country table"],
    ["4b", code("stage4b_statistical_tests.py"),
     "RQ1 / RQ2 / RQ3 tests", "3 statistical tests"],
    ["4c", code("stage4c_breakdowns.py"),
     "Ecosystem + tool analysis", "breakdown CSVs"],
    ["4d", code("stage4d_size_analysis.py"),
     "Repo-size analysis", "3-approach size table"],
    ["4e", code("stage4e_mena_analysis.py"),
     "MENA regional deep-dive", "MENA ranking + stats"],
]
def to_para(c):
    if isinstance(c, str):
        return Paragraph(c, toc_style)
    return c  # already a Paragraph

toc_data = [[to_para(c) for c in row] for row in toc_data]

toc_table = Table(toc_data, colWidths=[1*cm, 4.5*cm, 6.5*cm, 4.5*cm])
toc_table.setStyle(TableStyle([
    ("BACKGROUND",   (0,0), (-1,0),  BLUE_DARK),
    ("TEXTCOLOR",    (0,0), (-1,0),  white),
    ("FONTNAME",     (0,0), (-1,0),  "Helvetica-Bold"),
    ("FONTSIZE",     (0,0), (-1,-1), 8.5),
    ("ROWBACKGROUNDS",(0,1),(-1,-1), [GRAY_LIGHT, white]),
    ("GRID",         (0,0), (-1,-1), 0.3, HexColor("#E5E7EB")),
    ("LEFTPADDING",  (0,0), (-1,-1), 5),
    ("RIGHTPADDING", (0,0), (-1,-1), 5),
    ("TOPPADDING",   (0,0), (-1,-1), 4),
    ("BOTTOMPADDING",(0,0), (-1,-1), 4),
    ("VALIGN",       (0,0), (-1,-1), "TOP"),
]))
story += [toc_table, PageBreak()]


# ══════════════════════════════════════════════════════════════════════════════
def script_page(stage_label, stage_title, script_name, purpose,
                method_paras, numbers_rows, input_text, output_text,
                contribution_text, stage_color=BLUE_DARK):
    s = []
    s += [SectionHeader(f"Stage {stage_label} — {stage_title}", stage_color), sp(6)]
    s += [Paragraph(code(script_name), script_style), sp(2)]
    s += [coloured_para(f"<b>Purpose:</b> {purpose}", BLUE_LIGHT, BLUE_MED, W_TEXT), sp(6)]

    s += [Paragraph("<b>Method.</b>", bold_style)]
    for p in method_paras:
        s += [Paragraph(p, body_style)]
    s += [sp(4)]

    s += [Paragraph("<b>Key Numbers Generated</b>", bold_style)]
    s += [numbers_table(numbers_rows, W_TEXT), sp(6)]

    s += [Paragraph(f"<b>Input:</b> {input_text}", body_style)]
    s += [Paragraph(f"<b>Output:</b> {output_text}", body_style), sp(4)]

    s += [coloured_para(f"<b>Thesis Contribution.</b> {contribution_text}",
                        GREEN_LIGHT, GREEN, W_TEXT)]
    s += [PageBreak()]
    return s


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 1
# ══════════════════════════════════════════════════════════════════════════════
story += script_page(
    "1", "Corpus Construction", "stage1a_collect_repos.py",
    "Queries the GitHub GraphQL Search API to collect all JavaScript and TypeScript "
    "repositories meeting the corpus inclusion criteria. Produces the raw population "
    "for all subsequent analyses. No sampling is performed — the output is a complete census.",
    [
        "Two separate search queries (JS and TS separately — the API does not support "
        "combined language filters) use rolling 5-day creation date windows from "
        "24 February 2025 to October 2026. Windows hitting the 1,000-result API cap "
        "are recursively split into 2-day sub-windows.",
        "Inclusion filters: Created ≥ 24 Feb 2025 · Stars ≥ 4 · Commits ≥ 50 · "
        "Not a fork · JS+TS bytes ≥ 175,000.",
    ],
    [
        ("Total repos after all filters",     "60,129"),
        ("TypeScript repos",                  "45,314  (75.4%)"),
        ("JavaScript repos",                  "14,815  (24.6%)"),
        ("Stars range (median)",              "4 – 391,443  (median: 10)"),
        ("Commits range (median)",            "50 – 1,003,888  (median: 177)"),
        ("JS+TS bytes median",                "837 KB"),
    ],
    "GitHub GraphQL Search API (live)",
    f"{code('data/stage1/global_corpus.csv')} — 60,129 rows, 13 columns: "
    "full_name, stars, forks, commits, lang_bytes, url, owner_login, repo_name, "
    "primary_language, size_stratum, created_at, ecosystem_type, corpus_source.",
    "This script defines the study population. The 24 Feb 2025 threshold ensures every "
    "repository was created during the agentic era. The 60,129 repositories constitute "
    "the denominator for all adoption rate calculations, including RQ1's 73.0% global figure.",
)

story += script_page(
    "1", "Corpus Construction", "stage1b_categorize_ecosystem.py",
    "Classifies each of the 60,129 repositories into a package manager ecosystem "
    "by detecting lockfiles at the repository root via the GitHub GraphQL API.",
    [
        "A single GraphQL query per repository checks for lockfiles in priority order: "
        "bun.lockb (Bun) → deno.lock (Deno) → pnpm-lock.yaml (pnpm) → yarn.lock (Yarn) → "
        "package-lock.json (npm). If package.json exists without any lockfile → npm_no_lock. "
        "If no package.json → vanilla.",
    ],
    [
        ("npm",          "28,248  (47.0%)"),
        ("pnpm",         "12,229  (20.3%)"),
        ("vanilla",      "10,177  (16.9%)"),
        ("npm_no_lock",  " 7,979  (13.3%)"),
        ("yarn",         " 1,091   (1.8%)"),
        ("deno",         "   250   (0.4%)"),
        ("bun",          "   107   (0.2%)"),
    ],
    f"{code('data/stage1/global_corpus.csv')} (60,129 rows)",
    "Ecosystem label written back into global_corpus.csv as the ecosystem_type column.",
    "Ecosystem classification reveals adoption is not uniform: pnpm leads at 82.5%, "
    "npm at 73.7%, vanilla at 57.5%. Discussed in the Results chapter as evidence "
    "that engineering-focused package manager choices correlate with higher AI adoption.",
)

# ══════════════════════════════════════════════════════════════════════════════
# STAGE 2
# ══════════════════════════════════════════════════════════════════════════════
story += script_page(
    "2", "Owner Location Inference", "stage2a_location_fast.py",
    "Infers the country of each repository owner by reading the location field of "
    "their GitHub profile. This is the cheapest and most accurate signal.",
    [
        "The 60,129 repositories have 50,002 unique owners. For each owner the script "
        "queries the GitHub REST API for the profile location string and normalises it "
        "against a country name and alias dictionary. Empty, fake (e.g. 'Earth'), or "
        "ambiguous strings are marked not_specified and passed to Stage 2b.",
    ],
    [
        ("Unique owners queried",         "50,002"),
        ("Located via location field",    "13,625  (27.2% of owners)"),
        ("Passed to Stage 2b",            "36,377  (72.8%)"),
        ("Top country — China",           "1,521 owners"),
        ("Top country — United States",   "1,491 owners"),
        ("Top country — India",           "1,650 owners"),
    ],
    f"{code('data/stage1/global_corpus.csv')} (owner_login column)",
    f"{code('data/stage2/owner_locations_fast.csv')} — 50,002 rows: "
    "owner_login, location_raw, inferred_country, confidence, source.",
    "The location field is the only self-reported unambiguous location signal on GitHub. "
    "It locates 27.2% of owners with high confidence. The 72.8% unresolved motivates "
    "Stage 2b and is the root cause of the 56.1% unresolved owners reported as a validity threat.",
    stage_color=BLUE_MED,
)

story += script_page(
    "2", "Owner Location Inference", "stage2b_location_deep.py",
    "Attempts to infer the country of the 36,377 owners unresolved by Pass 1, "
    "using six additional signals from the GitHub profile and the owner's social graph.",
    [
        "Six signals are tried in priority order: (1) Bio text — scans biography for "
        "country/city names. (2) Company name — maps to headquarters country. "
        "(3) Email TLD — e.g. .de → Germany. (4) Website TLD. "
        "(5) Organisation location — uses the org's location field. "
        "(6) Network majority — follows up to 20 mutual followers and takes the "
        "majority country of those already resolved.",
    ],
    [
        ("Located by bio text",             "232"),
        ("Located by company name",         "144"),
        ("Located by email TLD",            "263"),
        ("Located by website TLD",          "439"),
        ("Located by org location",         "892"),
        ("Located by network majority",     "6,333"),
        ("Total resolved — Pass 2",         "8,323  owners"),
        ("Still not specified after Pass 2","28,054  (56.1% of all owners)"),
    ],
    "Owners marked not_specified in owner_locations_fast.csv (36,377 rows)",
    f"{code('data/stage2/owner_locations_deep.csv')} and "
    f"{code('owner_locations_all.csv')} (merged, 50,002 rows) and "
    f"{code('not_specified_owners.csv')} (28,054 rows).",
    "Pass 2 increases located owners from 13,625 to 21,948 (+61%), enabling Stage 4a "
    "to build a 65-country ranking covering 26,586 repositories (44.2% of corpus). "
    "The 56.1% remaining unresolved is reported as a key validity threat.",
    stage_color=BLUE_MED,
)

# ══════════════════════════════════════════════════════════════════════════════
# STAGE 3
# ══════════════════════════════════════════════════════════════════════════════
story += script_page(
    "3", "AI Adoption Detection", "stage3a_config_files.py",
    "Detects AI coding agent configuration files at the repository root for all "
    "60,129 repositories. File existence only — no content reading. "
    "Repositories classified here are not re-examined by any later pass.",
    [
        "A single batched GraphQL query per repository checks for known agent config "
        "filenames: CLAUDE.md, AGENTS.md, .github/copilot-instructions.md, "
        ".cursorrules, .cursorignore, GEMINI.md, .windsurfrules, .roomodes, and others. "
        "A positive match immediately classifies the repository as agentic "
        "(MEDIUM signal: config_file).",
    ],
    [
        ("Input",                           "60,129 repositories"),
        ("Classified agentic",              "25,010  (41.6%)"),
        ("Passed to Pass 2",                "35,119  (58.4%)"),
        ("CLAUDE.md",                       "15,152  (60.6% of Pass 1 agentic)"),
        ("AGENTS.md",                       " 8,705  (34.8%)"),
        (".github/copilot-instructions.md", "   715   (2.9%)"),
        ("GEMINI.md",                       "   106   (0.4%)"),
    ],
    f"{code('data/stage1/global_corpus.csv')}",
    f"{code('data/stage3/pass1_results.csv')} (60,129 rows) and "
    f"{code('pass1_unclassified.csv')} (35,119 rows for Pass 2).",
    "Pass 1 single-handedly detects 41.6% of the corpus as agentic. "
    "CLAUDE.md dominance (60.6% of hits) is one of the study's key findings. "
    "This pass is central to RQ2: comparing Pass 1-only (41.6%) with the full "
    "pipeline (73.0%) gives the +31.4 pp undercounting gap.",
    stage_color=PURPLE,
)

story += script_page(
    "3", "AI Adoption Detection", "stage3b_commit_trailers.py",
    "Scans the commit history and pull request branch names of the 35,119 "
    "repositories that Pass 1 did not classify. Commit trailers are STRONG signals — "
    "they confirm an agent performed work, not merely that it was configured.",
    [
        "Fetches the most recent 100 commits per repository via the GitHub REST API "
        "and scans commit messages for agent-specific trailer patterns (Co-authored-by:, "
        "Generated by:, Committed by:) and PR branch prefixes (copilot/, codex/, "
        "devin/, claude/, jules-).",
        "Classification rule: ≥3 AI commits or trailers from 2+ distinct agents → "
        "agentic. 1–2 AI commits from 1 agent → ai-assisted. No match → Pass 3.",
    ],
    [
        ("Input",                             "35,119 repositories"),
        ("Classified agentic",                " 9,618  (27.4% of input)"),
        ("Classified ai-assisted",            " 3,846  (10.9%)"),
        ("Passed to Pass 3",                  "21,655  (61.7%)"),
        ("Claude Code in trailers",           " 8,224 repos"),
        ("GitHub Copilot in trailers",        " 1,637 repos"),
        ("OpenAI Codex in trailers",          " 1,577 repos"),
    ],
    f"{code('data/stage3/pass1_unclassified.csv')} (35,119 rows)",
    f"{code('data/stage3/pass2_results.csv')} and "
    f"{code('pass2_unclassified.csv')} (21,655 rows for Pass 3).",
    "Pass 2 adds 9,618 agentic repos missed by config-file-only detection. "
    "Commit trailers prove the agent authored commits. The 3,846 ai-assisted repos "
    "from this pass are all later upgraded in Stage 3d (Pass 4), because a single "
    "commit trailer is a STRONG signal.",
    stage_color=PURPLE,
)

story += script_page(
    "3", "AI Adoption Detection", "stage3c_deep_scan.py",
    "Performs the most thorough examination of the 21,655 repositories still "
    "unclassified after Passes 1 and 2. Uses batched GraphQL queries to fetch "
    "commit history, pull requests, and CI workflows, then applies the full "
    "three-tier signal hierarchy.",
    [
        "Repositories are batched in groups of 5 per GraphQL query (4–5× faster). "
        "Each repository: 150 commits + 50 pull requests.",
        "Signal families — STRONG (any 1 alone → agentic): agent_attribution "
        "(commit trailers/author email), pr_branch (agent-prefixed PR branches), "
        "bot_author. MEDIUM (≥2 families → agentic; 1 alone → ai-assisted): "
        "pr_label, tool_configuration. WEAK (→ ai-assisted): pr_body, gitignore_mixed.",
    ],
    [
        ("Input",                   "21,655 repositories"),
        ("Classified agentic",      "   764   (3.5% of input)"),
        ("Classified ai-assisted",  " 4,657  (21.5%)"),
        ("Classified none",         "16,234  (75.0%) — final none label"),
        ("Top STRONG — pr_branch",  "   704 repos"),
        ("Top STRONG — bot_author", "    45 repos"),
    ],
    f"{code('data/stage3/pass2_unclassified.csv')} (21,655 rows)",
    f"{code('data/stage3/pass3_results.csv')} and "
    f"{code('corpus_detected_full.csv')} (merged Passes 1–3).",
    "Pass 3 is the most expensive pass (~3–4 hours runtime) but essential for completeness. "
    "The 16,234 none labels are the definitive 'no evidence found' classification — "
    "these repos passed three increasingly thorough checks and showed no AI signal.",
    stage_color=PURPLE,
)

story += script_page(
    "3", "AI Adoption Detection", "stage3d_reclassify.py  (Pass 4)",
    "Takes every ai-assisted repository produced by Passes 2 and 3 (8,503 total) "
    "and applies two phases of deeper analysis to upgrade as many as possible to agentic. "
    "Its output is the definitive adoption label for all 60,129 repositories.",
    [
        "Phase 1 (no API calls): Re-applies the strict tiered rule to the 3,846 "
        "ai-assisted repos from Pass 2. A single commit trailer is a STRONG signal "
        "→ immediately agentic. All 3,846 are upgraded.",
        "Phase 2 (deep API): Runs five new check families on the 4,657 ai-assisted "
        "repos from Pass 3: extended config files in subdirectories (.claude/settings.json), "
        "bot account authorship in 300 commits, expanded PR branch prefixes, "
        "CI workflow files (.github/workflows/*.yml), PR labels and body patterns.",
    ],
    [
        ("Input total ai-assisted",          " 8,503 repositories"),
        ("Phase 1 upgraded to agentic",      " 3,846  (100% of Pass 2 ai-assisted)"),
        ("Phase 2 input",                    " 4,657 repositories"),
        ("Phase 2 upgraded to agentic",      "   258"),
        ("Remain ai-assisted (final)",        " 4,399"),
        ("New signal — .mcp.json",           "    63 repos"),
        ("New signal — .claude/settings.json","   35 repos"),
    ],
    f"{code('data/stage3/corpus_detected_full.csv')} (all ai-assisted rows)",
    f"{code('data/stage3/reclassification_results.csv')} and "
    f"{code('corpus_detected_full_v2.csv')} — final labels for all 60,129 repos.",
    "Pass 4 adds the final 4,104 agentic repositories. The definitive classification is: "
    "39,496 agentic (65.7%), 4,399 ai-assisted (7.3%), 16,234 none (27.0%). "
    "Combined, 43,895 repos (73.0%) show AI adoption — the answer to RQ1.",
    stage_color=PURPLE,
)

# ══════════════════════════════════════════════════════════════════════════════
# STAGE 4
# ══════════════════════════════════════════════════════════════════════════════
story += script_page(
    "4", "Geographic & Statistical Analysis", "stage4a_geographic_analysis.py",
    "Joins the final adoption labels from Stage 3 with owner locations from Stage 2 "
    "to produce a per-country adoption ranking. Answers the geographic dimension of RQ3.",
    [
        "Each repository's owner is looked up in owner_locations_all.csv. "
        "Countries with fewer than 30 repositories are excluded (MIN_REPOS threshold). "
        "For each eligible country: total repos, agentic count, ai-assisted count, "
        "adoption rate, and Wilson 95% confidence interval.",
    ],
    [
        ("Repos with country (joined)",      "26,586  (44.2% of corpus)"),
        ("Repos without country",            "33,543  (55.8%)"),
        ("Countries with ≥30 repos",         "65"),
        ("Countries below threshold",        "44  (excluded from ranking)"),
        ("Top country — Belgium",            "89 repos, 89.9%"),
        ("Bottom country — Rwanda",          "49 repos, 22.4%"),
        ("Largest corpus — United States",   "3,608 repos, 82.5%"),
    ],
    f"{code('corpus_detected_full_v2.csv')} + {code('owner_locations_all.csv')}",
    f"{code('data/stage4/corpus_with_country.csv')} (60,129 rows) and "
    f"{code('country_adoption.csv')} (65-row ranking table).",
    "Produces the 65-country ranking that is the centrepiece of the geographic analysis. "
    "The 67.5 pp spread (89.9% Belgium to 22.4% Rwanda) is the primary evidence for RQ3. "
    "It also reveals the major corpus countries: US (3,608), China (4,196, 77.2%), "
    "India (3,447, 51.2%), Germany (1,155, 78.2%).",
    stage_color=HexColor("#7C3AED"),
)

story += script_page(
    "4", "Geographic & Statistical Analysis", "stage4b_statistical_tests.py",
    "Runs the three formal statistical tests — one per research question — and produces "
    "the numerical evidence for each RQ's conclusion.",
    [
        "RQ1: One-sided binomial test against H₀: p ≤ 5% (incidental one-time use).",
        "RQ2: McNemar's paired test comparing Pass 1-only vs. full four-pass pipeline "
        "detection outcomes per repository. Continuity-corrected.",
        "RQ3: Chi-squared test of independence across all 65 countries, followed by "
        "65 pairwise Fisher's exact tests (each country vs. rest-of-world) with "
        "Benjamini-Hochberg FDR correction at α = 0.05.",
    ],
    [
        ("RQ1 — adoption rate",     "73.0%  (43,895 / 60,129)"),
        ("RQ1 — Wilson 95% CI",     "[72.65%, 73.35%]"),
        ("RQ1 — binomial p",        "< 10⁻³⁰⁰  → REJECT H₀"),
        ("RQ2 — single-signal",     "41.6%  →  full pipeline 73.0%"),
        ("RQ2 — delta",             "+31.41 pp  (b=18,885, c=0)"),
        ("RQ2 — McNemar p",         "< 10⁻³⁰⁰  → REJECT H₀"),
        ("RQ3 — χ²",                "2,234.55  df=64  p < 10⁻³⁰⁰  → REJECT H₀"),
        ("RQ3 — significant countries","41 of 65 after BH FDR correction"),
    ],
    f"{code('data/stage4/corpus_with_country.csv')} (60,129 rows)",
    f"{code('data/stage4/statistical_tests.txt')} and "
    f"{code('pairwise_fisher.csv')} (per-country Fisher results with BH correction).",
    "This script directly answers all three research questions. c = 0 in the McNemar "
    "table means there is not a single repository the full pipeline missed but Pass 1 "
    "found — every additional detection is a genuine new discovery.",
    stage_color=HexColor("#7C3AED"),
)

story += script_page(
    "4", "Geographic & Statistical Analysis", "stage4c_breakdowns.py",
    "Produces adoption breakdowns by ecosystem, primary language, repository size, "
    "and AI coding tool. Also analyses tool co-adoption.",
    [
        "For each grouping variable: total repos, agentic count, ai-assisted count, "
        "adoption rate, Wilson 95% CI, and agentic-only rate.",
        "For the tool breakdown: parses agents_found across all passes, splits "
        "multi-agent strings (e.g. 'Claude Code|Cursor'), counts unique tools per "
        "repository, and generates all unordered tool pairs for co-adoption analysis.",
    ],
    [
        ("TypeScript adoption",           "77.1%"),
        ("JavaScript adoption",           "60.5%"),
        ("pnpm adoption",                 "82.5%"),
        ("npm adoption",                  "73.7%"),
        ("vanilla adoption",              "57.5%"),
        ("Claude Code (corpus share)",    "26,854 repos  (44.7%)"),
        ("GitHub Copilot",                " 2,976 repos   (4.9%)"),
        ("1-tool loyalty",                "40,532 adopters  (95.4%)"),
        ("Top pair — Claude Code+Cursor", "628 repos  (1.0% of corpus)"),
    ],
    f"{code('data/stage4/corpus_with_country.csv')}",
    f"{code('breakdown_ecosystem.csv')}, {code('breakdown_language.csv')}, "
    f"{code('coadoption_tool_counts.csv')}, {code('coadoption_tool_pairs.csv')}, "
    f"{code('coadoption_per_repo.csv')}.",
    "Provides data for several Discussion chapter arguments: the TS/JS gap (77.1% vs 60.5%) "
    "supports the argument that typed codebases benefit more from AI. "
    "Claude Code's 44.7% corpus share establishes its dominance in the npm ecosystem. "
    "The 95.4% single-tool loyalty shows developers overwhelmingly commit to one agent.",
    stage_color=HexColor("#7C3AED"),
)

story += script_page(
    "4", "Geographic & Statistical Analysis", "stage4d_size_analysis.py",
    "Tests whether larger repositories have higher AI coding agent adoption rates. "
    "Uses three independent operationalisations of 'size' to rule out artefacts "
    "of any single metric.",
    [
        "Approach A — Stars (popularity): fixed thresholds ≤50 / 51–500 / >500. "
        "Approach B — Commits (activity): corpus tertiles P33=114, P66=286. "
        "Approach C — Code volume (lang_bytes): corpus tertiles P33=0.50 MB, P66=1.45 MB. "
        "B and C use tertiles for balanced ~33% strata. A uses fixed thresholds "
        "because the star distribution is extremely skewed (82.4% have ≤50 stars).",
    ],
    [
        ("A — Stars: small (n=49,562)",  "70.5%"),
        ("A — Stars: medium (n=8,375)",  "82.7%"),
        ("A — Stars: large (n=2,192)",   "91.7%  (+21.2 pp range)"),
        ("B — Commits: small (n=19,891)","64.8%"),
        ("B — Commits: large (n=20,375)","80.6%  (+15.8 pp range)"),
        ("C — Code vol: small (n=19,843)","59.7%"),
        ("C — Code vol: large (n=20,444)","85.6%  (+26.0 pp range)"),
    ],
    f"{code('data/stage4/corpus_with_country.csv')}",
    f"{code('size_stars.csv')}, {code('size_commits.csv')}, "
    f"{code('size_langbytes.csv')}, {code('size_comparison.csv')}.",
    "All three approaches confirm the same monotonic pattern. "
    "The +26.0 pp range for code volume (the largest gap) suggests developers with "
    "substantial codebases benefit most from AI agents. This robustness across "
    "three independent metrics rules out measurement artefacts.",
    stage_color=HexColor("#7C3AED"),
)

story += script_page(
    "4", "Geographic & Statistical Analysis", "stage4e_mena_analysis.py",
    "Applies the same statistical pipeline to the MENA (Middle East and North Africa) "
    "region, enabling a focused examination of within-region variation and comparison "
    "against the global benchmark.",
    [
        "MENA defined as 19 countries across 5 sub-regions: Gulf (UAE, Saudi Arabia, "
        "Kuwait, Qatar, Bahrain, Oman), Levant (Israel, Jordan, Lebanon, Syria, Iraq), "
        "North Africa (Egypt, Morocco, Algeria, Tunisia, Libya), Turkey, Iran.",
        "Same MIN_REPOS=30 threshold. Tests: Fisher exact (MENA vs global 73.0%), "
        "chi-squared within MENA, pairwise Fisher per country vs MENA mean with BH FDR.",
    ],
    [
        ("Total MENA repos",               "1,446  (2.4% corpus, 5.4% of located)"),
        ("Eligible countries",             "9 of 19"),
        ("MENA overall adoption",          "65.1%  [62.6%, 67.5%]"),
        ("vs. global (Fisher)",            "p < 10⁻¹⁰,  OR = 0.68"),
        ("Within-MENA χ²",                 "147.52, df=8, p ≈ 10⁻²⁸"),
        ("Gulf sub-region",                "85.0%  (n=173)"),
        ("North Africa sub-region",        "50.1%  (n=355)"),
        ("Iran",                           "44.8%  (n=223)"),
        ("Claude Code loyalty (MENA)",     "58.6%  (global: 59.2%)"),
    ],
    f"{code('data/stage4/corpus_with_country.csv')}",
    f"{code('data/stage4/mena/')} directory — mena_country_ranking.csv, "
    "mena_subregion_breakdown.csv, mena_statistical_tests.txt, "
    "mena_size_breakdown.csv, mena_tool_breakdown.csv.",
    "Shows that the global geographic variation (RQ3) replicates within a single region: "
    "a 46.4 pp spread exists within MENA alone (Israel 85.6% to Morocco 39.2%). "
    "Identical Claude Code loyalty (58.6% vs 59.2% globally) shows tool preferences "
    "do not drive the regional gap — structural factors are more likely explanations.",
    stage_color=HexColor("#7C3AED"),
)

# ── build ─────────────────────────────────────────────────────────────────────
doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
print(f"Saved: {OUT}")

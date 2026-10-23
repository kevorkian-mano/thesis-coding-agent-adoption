#!/usr/bin/env python3
"""
Build a single PDF containing all thesis figures.
Outputs to: /figures_preview.pdf  (project root)
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.backends.backend_pdf import PdfPages
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
FIG_DIR = ROOT / "bachelor_thesis" / "figures"
OUT     = ROOT / "figures_preview.pdf"

# Ordered list: (filename, section label)
FIGURES = [
    ("fig_pipeline_flow.png",        "Detection Pipeline",             "Stage 3 — Detection Pipeline Flow"),
    ("fig_pass_contributions.png",   "Pass Contributions",             "Per-Pass Contribution to Final Agentic Count"),
    ("fig_ecosystem_stacked.png",    "Ecosystem Breakdown",            "Adoption Rate by Package Ecosystem"),
    ("fig_tool_distribution.png",    "Tool Distribution",              "AI Coding Tool Usage Among Adopters"),
    ("fig_tool_loyalty.png",         "Tool Loyalty",                   "Tool Loyalty and Top Tool Pairs"),
    ("fig_choropleth.png",           "Geographic Map",                 "World Choropleth — Adoption Rate by Country"),
    ("fig_top_bottom_countries.png", "Top / Bottom Countries",         "Top 10 and Bottom 10 Countries"),
    ("fig_country_bubble.png",       "Country Scatter",                "Repository Count vs Adoption Rate (Bubble Chart)"),
    ("fig_size_grouped_bar.png",     "Repository Size Analysis",       "Adoption Rate by Repository Size — Three Operationalisations"),
    ("fig_mena_bar.png",             "MENA Regional Analysis",         "MENA Region — Adoption Rate by Country"),
]

with PdfPages(OUT) as pdf:

    # ── Cover page ────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(11.69, 8.27))   # A4 landscape
    fig.patch.set_facecolor("#1E3A5F")
    ax.axis("off")

    ax.text(0.5, 0.62,
            "Coding Agent Adoption in JavaScript/TypeScript/npm\nRepositories on GitHub",
            ha="center", va="center", fontsize=22, fontweight="bold",
            color="white", transform=ax.transAxes, linespacing=1.5)

    ax.text(0.5, 0.44,
            "Figures Preview",
            ha="center", va="center", fontsize=15,
            color="#93C5FD", transform=ax.transAxes)

    ax.text(0.5, 0.34,
            "Manuel Youssef Haik Kevorkian  ·  October 2026",
            ha="center", va="center", fontsize=11,
            color="#CBD5E1", transform=ax.transAxes)

    ax.text(0.5, 0.20,
            f"{len(FIGURES)} figures",
            ha="center", va="center", fontsize=10,
            color="#94A3B8", transform=ax.transAxes)

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)

    # ── One figure per page ───────────────────────────────────────────────────
    for i, (fname, section, caption) in enumerate(FIGURES, 1):
        path = FIG_DIR / fname
        if not path.exists():
            print(f"  WARNING: {fname} not found, skipping")
            continue

        img = mpimg.imread(str(path))
        h, w = img.shape[:2]
        aspect = w / h

        # A4 landscape: 11.69 × 8.27 in
        page_w, page_h = 11.69, 8.27
        # Reserve top for header, bottom for caption
        avail_h = page_h - 1.1
        avail_w = page_w - 0.6

        fig_w = min(avail_w, avail_h * aspect)
        fig_h = fig_w / aspect

        fig = plt.figure(figsize=(page_w, page_h))
        fig.patch.set_facecolor("white")

        # Header bar
        header_ax = fig.add_axes([0, 0.91, 1, 0.09])
        header_ax.set_facecolor("#1E3A5F")
        header_ax.axis("off")
        header_ax.text(0.02, 0.5, f"Figure {i}  ·  {section}",
                       ha="left", va="center", fontsize=10,
                       fontweight="bold", color="white",
                       transform=header_ax.transAxes)
        header_ax.text(0.98, 0.5, "Coding Agent Adoption — Figures Preview",
                       ha="right", va="center", fontsize=8.5,
                       color="#93C5FD", transform=header_ax.transAxes)

        # Image
        left   = (page_w - fig_w) / 2 / page_w
        bottom = 0.10
        width  = fig_w / page_w
        height = fig_h / page_h

        img_ax = fig.add_axes([left, bottom, width, height])
        img_ax.imshow(img)
        img_ax.axis("off")

        # Caption
        cap_ax = fig.add_axes([0.05, 0.01, 0.90, 0.08])
        cap_ax.axis("off")
        cap_ax.text(0.5, 0.5, caption,
                    ha="center", va="center", fontsize=9.5,
                    color="#374151", style="italic",
                    transform=cap_ax.transAxes)

        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        print(f"  Added page {i}: {fname}")

    # ── PDF metadata ─────────────────────────────────────────────────────────
    d = pdf.infodict()
    d["Title"]   = "Figures Preview — Coding Agent Adoption in JS/TS/npm Repositories"
    d["Author"]  = "Manuel Youssef Haik Kevorkian"
    d["Subject"] = "Bachelor Thesis Figures"

print(f"\nSaved: {OUT}")

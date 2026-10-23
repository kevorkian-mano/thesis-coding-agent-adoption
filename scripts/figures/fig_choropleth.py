#!/usr/bin/env python3
"""
Figure: World Choropleth — AI Coding Agent Adoption Rate by Country
====================================================================
Produces a world choropleth map where each country is coloured by its
adoption rate (% of repos using at least one AI coding agent).
Only the 65 countries with ≥30 repos are coloured; the rest are grey.

Output
------
  bachelor_thesis/figures/fig_choropleth.pdf
  bachelor_thesis/figures/fig_choropleth.png

Usage
-----
  python3 scripts/figures/fig_choropleth.py
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
DATA    = ROOT / "data" / "stage4" / "country_adoption.csv"
OUT_DIR = ROOT / "bachelor_thesis" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── country name → ISO-3 mapping (needed by plotly choropleth) ────────────────
NAME_TO_ISO3 = {
    "Afghanistan": "AFG", "Albania": "ALB", "Algeria": "DZA",
    "Argentina": "ARG", "Australia": "AUS", "Austria": "AUT",
    "Azerbaijan": "AZE", "Bangladesh": "BGD", "Belarus": "BLR",
    "Belgium": "BEL", "Bolivia": "BOL", "Bosnia and Herzegovina": "BIH",
    "Brazil": "BRA", "Bulgaria": "BGR", "Cambodia": "KHM",
    "Canada": "CAN", "Chile": "CHL", "China": "CHN",
    "Colombia": "COL", "Croatia": "HRV", "Czech Republic": "CZE",
    "Denmark": "DNK", "Ecuador": "ECU", "Egypt": "EGY",
    "Estonia": "EST", "Ethiopia": "ETH", "Finland": "FIN",
    "France": "FRA", "Germany": "DEU", "Ghana": "GHA",
    "Greece": "GRC", "Hungary": "HUN", "India": "IND",
    "Indonesia": "IDN", "Iran": "IRN", "Iraq": "IRQ",
    "Ireland": "IRL", "Israel": "ISR", "Italy": "ITA",
    "Japan": "JPN", "Jordan": "JOR", "Kazakhstan": "KAZ",
    "Kenya": "KEN", "Latvia": "LVA", "Lithuania": "LTU",
    "Malaysia": "MYS", "Mexico": "MEX", "Morocco": "MAR",
    "Nepal": "NPL", "Netherlands": "NLD", "New Zealand": "NZL",
    "Nigeria": "NGA", "Norway": "NOR", "Pakistan": "PAK",
    "Peru": "PER", "Philippines": "PHL", "Poland": "POL",
    "Portugal": "PRT", "Romania": "ROU", "Russia": "RUS",
    "Rwanda": "RWA", "Saudi Arabia": "SAU", "Serbia": "SRB",
    "Singapore": "SGP", "Slovakia": "SVK", "South Africa": "ZAF",
    "South Korea": "KOR", "Spain": "ESP", "Sri Lanka": "LKA",
    "Sweden": "SWE", "Switzerland": "CHE", "Taiwan": "TWN",
    "Thailand": "THA", "Tunisia": "TUN", "Turkey": "TUR",
    "Ukraine": "UKR", "United Arab Emirates": "ARE",
    "United Kingdom": "GBR", "United States": "USA",
    "Uruguay": "URY", "Uzbekistan": "UZB", "Venezuela": "VEN",
    "Vietnam": "VNM", "Belgium": "BEL", "Israel": "ISR",
}

# ── load data ─────────────────────────────────────────────────────────────────
df = pd.read_csv(DATA)
df["iso3"] = df["country"].map(NAME_TO_ISO3)

missing = df[df["iso3"].isna()]["country"].tolist()
if missing:
    print(f"Warning: no ISO3 mapping for: {missing}")

df = df.dropna(subset=["iso3"])

# ── build figure ──────────────────────────────────────────────────────────────
fig = px.choropleth(
    df,
    locations="iso3",
    color="adoption_rate",
    hover_name="country",
    hover_data={
        "iso3": False,
        "adoption_rate": ":.1f",
        "total_repos": True,
    },
    color_continuous_scale=[
        [0.0,  "#FEF3C7"],
        [0.25, "#FCD34D"],
        [0.5,  "#F59E0B"],
        [0.75, "#2563EB"],
        [1.0,  "#1E3A5F"],
    ],
    range_color=[20, 92],
    labels={"adoption_rate": "Adoption rate (%)"},
)

fig.update_layout(
    title={
        "text": "AI Coding Agent Adoption Rate by Country<br>"
                "<sup>65 countries with ≥30 JS/TS/npm repositories (n = 26,586)</sup>",
        "x": 0.5,
        "xanchor": "center",
        "font": {"size": 16, "family": "Arial", "color": "#111827"},
    },
    geo=dict(
        showframe=False,
        showcoastlines=True,
        coastlinecolor="#D1D5DB",
        showland=True,
        landcolor="#F3F4F6",
        showocean=True,
        oceancolor="#EFF6FF",
        showlakes=False,
        showcountries=True,
        countrycolor="#E5E7EB",
        projection_type="natural earth",
    ),
    coloraxis_colorbar=dict(
        title="Adoption<br>rate (%)",
        tickvals=[20, 30, 40, 50, 60, 70, 80, 90],
        ticktext=["20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%"],
        len=0.6,
        thickness=16,
        x=1.01,
    ),
    margin=dict(l=0, r=10, t=70, b=0),
    paper_bgcolor="white",
    font=dict(family="Arial", color="#374151"),
    width=1100,
    height=600,
)

# ── annotate top/bottom countries ─────────────────────────────────────────────
top3    = df.nlargest(3, "adoption_rate")[["country", "adoption_rate"]]
bottom3 = df.nsmallest(3, "adoption_rate")[["country", "adoption_rate"]]

annotation_text = (
    "<b>Highest:</b> " +
    " · ".join(f"{r.country} {r.adoption_rate:.0f}%" for _, r in top3.iterrows()) +
    "<br><b>Lowest:</b> " +
    " · ".join(f"{r.country} {r.adoption_rate:.0f}%" for _, r in bottom3.iterrows())
)

fig.add_annotation(
    text=annotation_text,
    xref="paper", yref="paper",
    x=0.01, y=0.03,
    showarrow=False,
    font=dict(size=10, color="#374151"),
    bgcolor="rgba(255,255,255,0.85)",
    bordercolor="#D1D5DB",
    borderwidth=1,
    borderpad=6,
    align="left",
)

# ── save ─────────────────────────────────────────────────────────────────────
fig.write_image(str(OUT_DIR / "fig_choropleth.pdf"), format="pdf",
                width=1100, height=600)
fig.write_image(str(OUT_DIR / "fig_choropleth.png"), format="png",
                width=1100, height=600, scale=2)
print("Saved: fig_choropleth.pdf / .png")

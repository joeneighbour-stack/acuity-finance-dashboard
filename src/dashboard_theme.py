"""Central presentation tokens for the Acuity finance dashboard."""

from __future__ import annotations


STEEL_GREY = "#333333"
ALERT_ORANGE = "#FF8F14"
NEUTRAL_GREY = "#999999"
PAGE_BACKGROUND = "#F6F6F4"
WHITE = "#FFFFFF"
POSITIVE = "#247A5A"
NEGATIVE = "#B33A3A"


def altair_theme():
    return {
        "config": {
            "background": WHITE,
            "view": {"stroke": None},
            "axis": {
                "domainColor": "#D8D8D4",
                "gridColor": "#E8E8E4",
                "labelColor": "#555555",
                "titleColor": STEEL_GREY,
                "labelFont": "Soleil, Inter, Avenir Next, Helvetica Neue, Arial",
                "titleFont": "Soleil, Inter, Avenir Next, Helvetica Neue, Arial",
            },
            "legend": {
                "labelColor": "#555555",
                "titleColor": STEEL_GREY,
                "labelFont": "Soleil, Inter, Avenir Next, Helvetica Neue, Arial",
                "titleFont": "Soleil, Inter, Avenir Next, Helvetica Neue, Arial",
            },
            "range": {
                "category": [STEEL_GREY, ALERT_ORANGE, "#777777", "#B5B5B0", "#555555"]
            },
        }
    }


THEME_CSS = """
<style>
  :root {
    --steel-grey: #333333;
    --alert-orange: #FF8F14;
    --neutral-grey: #999999;
    --page-background: #F6F6F4;
    --surface: #FFFFFF;
    --border-subtle: #E3E3DF;
    --text-primary: #333333;
    --text-secondary: #5F5F5B;
    --text-muted-accessible: #767676;
    --positive: #247A5A;
    --negative: #B33A3A;
    --comparison-neutral: #5F5F5B;
    --display-font: "DM Serif Text", Georgia, "Times New Roman", serif;
    --ui-font: "Soleil", "Inter", "Avenir Next", "Helvetica Neue", Arial, sans-serif;
    --space-1: .35rem;
    --space-2: .65rem;
    --space-3: 1rem;
    --space-4: 1.5rem;
    --space-5: 2.25rem;
    --radius: 4px;
    --shadow-subtle: 0 1px 2px rgba(51, 51, 51, .06);
  }

  html, body, [class*="css"] { font-family: var(--ui-font); color: var(--text-primary); }
  .stApp { background: var(--page-background); }
  .block-container { padding: var(--space-4) var(--space-5) var(--space-5); max-width: 1280px; }
  h1, h2 { font-family: var(--display-font); color: var(--steel-grey); letter-spacing: -.015em; }
  h1 { font-size: clamp(2rem, 3vw, 2.8rem); margin-bottom: var(--space-1); }
  h2 { font-size: 1.7rem; }
  h3 { color: var(--steel-grey); font-family: var(--ui-font); font-size: 1.08rem; }

  [data-testid="stSidebar"] { background: var(--steel-grey); }
  [data-testid="stSidebar"] * { color: var(--surface); }
  [data-testid="stSidebar"] .stRadio label { padding: .18rem 0; }
  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { line-height: 1.45; }
  [data-testid="stSidebar"] button { border-radius: var(--radius); }
  [data-testid="stSidebar"] .stButton button,
  [data-testid="stSidebar"] .stButton button * { color: var(--steel-grey) !important; }
  [data-testid="stSidebar"] .stButton button { background: var(--surface); border-color: var(--surface); }
  [data-testid="stSidebar"] .stButton button:hover { border-color: var(--alert-orange); }
  [data-testid="stSidebar"] .stButton button:disabled,
  [data-testid="stSidebar"] .stButton button:disabled * { color: #5F5F5B !important; opacity: 1; }
  [data-testid="stSidebar"] [data-testid="stImage"] { margin: .5rem 0 .75rem; }
  [data-testid="stSidebar"] [data-testid="stImage"] img { height: auto; max-width: 220px; width: 100%; }
  .sidebar-subtitle { color: #D7D7D2 !important; font-size: .82rem; margin-bottom: 1.7rem; }
  .sidebar-section { color: #D7D7D2 !important; font-size: .68rem; font-weight: 700;
    letter-spacing: .11em; margin: 1.15rem 0 .35rem; text-transform: uppercase; }

  [data-testid="stMetric"], .comparison-card { background: var(--surface);
    border: 1px solid var(--border-subtle); border-radius: var(--radius); box-shadow: var(--shadow-subtle); }
  [data-testid="stMetric"] { min-height: 132px; padding: 1.15rem 1.2rem; }
  [data-testid="stMetricLabel"], .comparison-label { color: var(--text-secondary); font-size: .82rem; }
  [data-testid="stMetricValue"], .comparison-value { color: var(--steel-grey); font-family: var(--ui-font);
    font-variant-numeric: tabular-nums; font-weight: 600; }
  .comparison-card { min-height: 142px; padding: 1.15rem 1.2rem; }
  .comparison-label { margin-bottom: var(--space-1); }
  .comparison-value { font-size: clamp(1.55rem, 2.2vw, 2rem); letter-spacing: -.025em;
    line-height: 1.2; white-space: nowrap; }
  .comparison-delta { font-size: .83rem; font-weight: 600; margin-top: .5rem; }
  .comparison-delta.favourable { color: var(--positive); }
  .comparison-delta.unfavourable { color: var(--negative); }
  .comparison-delta.neutral { color: var(--comparison-neutral); }
  .comparison-baseline { color: var(--text-secondary); font-size: .76rem; margin-top: .2rem; }

  .reporting-context { align-items: center; border-bottom: 1px solid var(--border-subtle);
    display: flex; flex-wrap: wrap; gap: .55rem 1rem; justify-content: space-between;
    margin-bottom: var(--space-4); padding-bottom: var(--space-2); }
  .reporting-entity { color: var(--steel-grey); font-size: .78rem; font-weight: 700;
    letter-spacing: .1em; text-transform: uppercase; }
  .reporting-period { color: var(--text-secondary); font-size: .8rem; }
  .eyebrow { color: var(--alert-orange); font-size: .7rem; font-weight: 700;
    letter-spacing: .11em; margin-bottom: -.35rem; text-transform: uppercase; }
  .muted { color: var(--text-secondary); font-size: .88rem; max-width: 70ch; }
  div[data-testid="stDataFrame"] { background: var(--surface); border: 1px solid var(--border-subtle);
    border-radius: var(--radius); box-shadow: none; }
  div[data-testid="stAlert"] { border-radius: var(--radius); }
  hr { border-color: var(--border-subtle); }

  @media (max-width: 1100px) {
    .block-container { padding-left: 1.35rem; padding-right: 1.35rem; }
    .comparison-card { padding: 1rem; }
    .comparison-value { font-size: 1.45rem; }
  }
</style>
"""

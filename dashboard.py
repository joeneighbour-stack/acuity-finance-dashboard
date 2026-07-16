"""Acuity finance dashboard UI.

All source-specific parsing remains in finance_adapter and hubspot_adapter.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import altair as alt
import pandas as pd
import streamlit as st

from src.finance_adapter import (
    FinanceSnapshot, GoogleSheetsReader, MarketReaderSnapshot, finance_snapshot,
    marketreader_snapshot,
)
from src.hubspot_adapter import HubSpotSnapshot, hubspot_snapshot
from src.snapshots import get_monthly_snapshots, initialize_database, save_monthly_snapshot


st.set_page_config(page_title="Acuity Finance", page_icon="◈", layout="wide")

initialize_database()

st.markdown("""
<style>
  .stApp { background: #f5f6f8; color: #17212b; }
  [data-testid="stSidebar"] { background: #101c2c; }
  [data-testid="stSidebar"] * { color: #f5f7fa !important; }
  [data-testid="stMetric"] { background: white; border: 1px solid #e4e8ed;
    border-radius: 12px; padding: 18px 20px; box-shadow: 0 2px 8px rgba(16,28,44,.04); }
  [data-testid="stMetricLabel"] { color: #667586; }
  [data-testid="stMetricValue"] { color: #101c2c; }
  .block-container { padding-top: 2rem; max-width: 1500px; }
  h1, h2, h3 { color: #101c2c; letter-spacing: -.02em; }
  .eyebrow { color: #16a085; font-weight: 700; font-size: .76rem;
    letter-spacing: .12em; text-transform: uppercase; margin-bottom: -.5rem; }
  .muted { color: #758393; font-size: .9rem; }
  div[data-testid="stDataFrame"] { background: white; border-radius: 12px; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300, show_spinner=False)
def load_finance_data() -> FinanceSnapshot:
    return finance_snapshot(GoogleSheetsReader.from_environment())


@st.cache_data(ttl=300, show_spinner=False)
def load_marketreader_data() -> MarketReaderSnapshot:
    return marketreader_snapshot(GoogleSheetsReader.from_environment())


@st.cache_data(ttl=300, show_spinner=False)
def load_hubspot_data() -> HubSpotSnapshot:
    return hubspot_snapshot()


def money(value: Decimal, compact: bool = False) -> str:
    number = float(value)
    if compact and abs(number) >= 1_000_000:
        return "£{:.1f}m".format(number / 1_000_000)
    if compact and abs(number) >= 1_000:
        return "£{:.1f}k".format(number / 1_000)
    return "£{:,.0f}".format(number)


def dollars(value: Decimal, compact: bool = False) -> str:
    number = float(value)
    if compact and abs(number) >= 1_000_000:
        return "${:.1f}m".format(number / 1_000_000)
    if compact and abs(number) >= 1_000:
        return "${:.1f}k".format(number / 1_000)
    return "${:,.0f}".format(number)


def percent(value: Decimal | None) -> str:
    return "Not available" if value is None else "{:.0f}%".format(float(value))


def heading(kicker: str, title: str, description: str) -> None:
    st.markdown('<div class="eyebrow">{}</div>'.format(kicker), unsafe_allow_html=True)
    st.title(title)
    st.markdown('<div class="muted">{}</div>'.format(description), unsafe_allow_html=True)
    st.write("")


def points_frame(points) -> pd.DataFrame:
    return pd.DataFrame({"Category": [p.label.strip() for p in points], "GBP": [float(p.value) for p in points]}).set_index("Category")


def donut_chart(points):
    short_labels = {
        "Acuity Trading Limited (UK)": "Acuity Trading UK",
        "Acuity Trading Sl": "Acuity Trading SL",
        "Acuity Research Ltd": "Acuity Research",
    }
    values = [float(p.value) for p in points]
    total = sum(values)
    frame = pd.DataFrame({
        "Category": [short_labels.get(p.label.strip(), p.label.strip()) for p in points],
        "Full category": [p.label.strip() for p in points],
        "GBP": values,
        "Value label": ["£{:.0f}k".format(value / 1000) if abs(value) >= 1000 else "£{:,.0f}".format(value) for value in values],
        "Share label": ["{:.0f}%".format(value / total * 100) if total else "0%" for value in values],
    })
    theta = alt.Theta("GBP:Q", stack=True)
    base = alt.Chart(frame).encode(
        theta=theta,
        color=alt.Color("Category:N", legend=alt.Legend(
            title=None, orient="bottom", columns=1, labelLimit=260,
            symbolType="circle", symbolSize=90,
        )),
        tooltip=[
            alt.Tooltip("Full category:N", title="Category"),
            alt.Tooltip("GBP:Q", title="GBP", format=",.0f"),
        ],
    )
    arcs = base.mark_arc(innerRadius=70, outerRadius=128, stroke="white", strokeWidth=2)
    label_base = alt.Chart(frame).encode(theta=theta)
    values_text = label_base.mark_text(radius=98, color="white", fontSize=12, fontWeight="bold").encode(
        text=alt.Text("Value label:N")
    )
    shares_text = label_base.mark_text(radius=115, color="white", fontSize=10).encode(
        text=alt.Text("Share label:N")
    )
    return (arcs + values_text + shares_text).properties(height=390)


def financial_year_label(today: date | None = None) -> str:
    today = today or date.today()
    start_year = today.year if today.month >= 2 else today.year - 1
    return "Feb {}–Jan {}".format(start_year, start_year + 1)


def executive(finance: FinanceSnapshot, hubspot: HubSpotSnapshot) -> None:
    heading("Company overview", "Executive Summary", "Live commercial position across finance and HubSpot")
    cols = st.columns(5)
    cols[0].metric("Active clients", "{:,}".format(finance.active_clients))
    cols[1].metric("Active contracts", "{:,}".format(finance.active_contracts))
    cols[2].metric("Current MRR", money(finance.current_mrr, True))
    cols[3].metric("Current ARR", money(finance.current_arr, True))
    cols[4].metric("Future contracted MRR", money(finance.future_contracted_mrr, True))
    st.write("")
    left, right = st.columns((3, 2))
    with left:
        st.subheader("Billing by entity")
        st.altair_chart(donut_chart(finance.billing_by_entity), use_container_width=True)
    with right:
        st.subheader("Billing by currency")
        st.altair_chart(donut_chart(finance.billing_by_currency), use_container_width=True)
    cols = st.columns(4)
    cols[0].metric("NRR (Quarterly)", percent(finance.nrr_quarterly))
    cols[1].metric("GRR (Quarterly)", percent(finance.grr_quarterly))
    cols[2].metric("Weighted pipeline", money(hubspot.weighted_pipeline, True))
    cols[3].metric("Renewals in next 90 days", len(hubspot.upcoming_renewals))
    st.caption("Updated quarterly from the Finance Google Sheet.")


def revenue_contracts(finance: FinanceSnapshot) -> None:
    heading("Commercial base", "Revenue & Contracts", "Contract economics and recurring revenue composition")
    cols = st.columns(3)
    cols[0].metric("Average client MRR", money(finance.average_client_mrr))
    cols[1].metric("Customer lifetime value", money(finance.clv, True))
    cols[2].metric("New contracts this FY", "{:,}".format(finance.new_contracts))
    cols[2].caption(financial_year_label())
    st.write("")
    st.subheader("Contract profile")
    cols = st.columns(2)
    cols[0].metric("Average current contract", "{:.1f} months".format(float(finance.average_contract_length)))
    cols[1].metric("Average contract — all time", "{:.1f} months".format(float(finance.average_contract_length_all_time)))
    st.write("")
    st.info("Entity and currency revenue breakdowns are available on the Executive Summary.")


def renewals(finance: FinanceSnapshot, hubspot: HubSpotSnapshot) -> None:
    heading("Customer durability", "Renewals & Retention", "Churn history and upcoming renewal workload")
    retention_cols = st.columns(2)
    retention_cols[0].metric("NRR (Quarterly)", percent(finance.nrr_quarterly))
    retention_cols[1].metric("GRR (Quarterly)", percent(finance.grr_quarterly))
    st.caption("Updated quarterly from the Finance Google Sheet.")
    st.write("")
    cols = st.columns(4)
    cols[0].metric("Churned clients YTD", finance.churned_clients_ytd)
    cols[1].metric("Churned MRR YTD", money(finance.churned_mrr_ytd))
    cols[2].metric("Churned clients last year", finance.churned_clients_last_year)
    cols[3].metric("Churned MRR last year", money(finance.churned_mrr_last_year))
    st.write("")
    left, right = st.columns((2, 3))
    with left:
        st.subheader("Renewal timing")
        frame = pd.DataFrame({"Window": [p.label for p in hubspot.renewal_stages], "Deals": [p.count for p in hubspot.renewal_stages]}).set_index("Window")
        st.bar_chart(frame, height=350)
    with right:
        st.subheader("Upcoming renewals — next 90 days")
        rows = [{"Renewal": r.name, "Date": r.close_date.strftime("%d %b %Y"), "Days": r.days_remaining, "Stage": r.stage, "ARR": money(r.arr)} for r in hubspot.upcoming_renewals]
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No renewals are currently due in the next 90 days.")
    st.write("")
    st.subheader("Cancellation received")
    st.caption("Active Acuity renewals carrying the Cancellation Received flag/tag")
    cancellation_rows = [{
        "Client": item.name,
        "Renewal date": item.renewal_date.strftime("%d %b %Y") if item.renewal_date else "—",
        "Cancellation received": item.cancellation_date.strftime("%d %b %Y") if item.cancellation_date else "Yes",
        "Renewal stage": item.stage,
        "ARR": money(item.arr),
    } for item in hubspot.cancellation_risks]
    if cancellation_rows:
        st.dataframe(pd.DataFrame(cancellation_rows), use_container_width=True, hide_index=True)
    else:
        st.success("No cancellation notices are currently flagged in the active renewal stages.")


def sales(hubspot: HubSpotSnapshot) -> None:
    heading("Growth engine", "Sales Performance", "Retail Pipeline performance from HubSpot · {} financial year".format(financial_year_label()))
    cols = st.columns(4)
    cols[0].metric("Opportunities created this FY", "{:,}".format(hubspot.opportunities_created))
    cols[1].metric("Closed won this FY", "{:,}".format(hubspot.closed_won))
    cols[2].metric("Open pipeline value", money(hubspot.pipeline_value, True))
    cols[3].metric("Weighted pipeline", money(hubspot.weighted_pipeline, True))
    st.write("")
    st.subheader("Pipeline by stage")
    stage_rows = [{
        "Stage": item.label,
        "Deal count": item.deal_count,
        "Pipeline value": float(item.pipeline_value),
        "Weighted value": float(item.weighted_value),
    } for item in hubspot.pipeline_stages]
    stage_frame = pd.DataFrame(stage_rows)
    display_frame = stage_frame.copy()
    display_frame["Pipeline value"] = display_frame["Pipeline value"].map(lambda value: money(Decimal(str(value))))
    display_frame["Weighted value"] = display_frame["Weighted value"].map(lambda value: money(Decimal(str(value))))
    st.dataframe(display_frame, use_container_width=True, hide_index=True)
    st.bar_chart(stage_frame.set_index("Stage")[["Pipeline value", "Weighted value"]], height=320)


def financial(finance: FinanceSnapshot) -> None:
    heading("Management accounts", "Financial Performance", "Latest period from the Syft MI Dashboard feed")
    cols = st.columns(4)
    cols[0].metric("Revenue", money(finance.revenue, True))
    cols[1].metric("Gross profit", money(finance.gross_profit, True))
    cols[2].metric("Net profit", money(finance.net_profit, True))
    cols[3].metric("EBITDA", money(finance.ebitda, True))
    cols = st.columns(4)
    cols[0].metric("EBITDA margin", percent(finance.ebitda_margin))
    cols[1].metric("Rule of 40", percent(finance.rule_of_40))
    cols[2].metric("Cash", money(finance.cash, True))
    cols[3].metric("Working capital", "Live")
    st.write("")
    left, right = st.columns((2, 1))
    with left:
        st.subheader("Profit bridge")
        frame = pd.DataFrame({"Metric": ["Revenue", "Gross profit", "Net profit", "EBITDA"], "GBP": [float(finance.revenue), float(finance.gross_profit), float(finance.net_profit), float(finance.ebitda)]}).set_index("Metric")
        st.bar_chart(frame, height=350)
    with right:
        st.subheader("Working capital")
        st.metric("Debtor days", "{:.1f}".format(float(finance.debtor_days)))
        st.metric("Creditor days", "{:.1f}".format(float(finance.creditor_days)))


def historical_trends(entity: str) -> None:
    heading("Monthly history", "Historical Trends", "Finance-approved monthly snapshots for {}".format(entity))
    rows = get_monthly_snapshots(entity)
    if not rows:
        st.info("No monthly snapshots have been saved for {} yet.".format(entity))
        return
    frame = pd.DataFrame(rows)
    frame["Month"] = pd.to_datetime(frame["snapshot_month"] + "-01")
    metrics = [
        ("Active Clients", "active_clients"), ("Active Contracts", "active_contracts"),
        ("Current MRR", "current_mrr"), ("Current ARR", "current_arr"),
        ("NRR", "nrr_quarterly"), ("GRR", "grr_quarterly"),
        ("EBITDA", "ebitda"), ("Cash", "cash"),
    ]
    if len(frame) == 1:
        st.info("More monthly snapshots are required to show a meaningful trend.")
    for offset in range(0, len(metrics), 2):
        columns = st.columns(2)
        for column, (label, field) in zip(columns, metrics[offset:offset + 2]):
            with column:
                st.subheader(label)
                data = frame[["Month", field]].dropna().set_index("Month")
                if data.empty:
                    st.caption("No data available")
                else:
                    st.line_chart(data, height=220)


def marketreader_view(data: MarketReaderSnapshot) -> None:
    heading("MarketReader", "Billing Overview", "Available MarketReader contract and billing data · USD")
    cols = st.columns(3)
    cols[0].metric("Active clients", "{:,}".format(data.active_clients))
    cols[1].metric("Active contracts", "{:,}".format(data.active_contracts))
    cols[2].metric("Average client MRR", dollars(data.average_client_mrr))
    cols = st.columns(3)
    cols[0].metric("Current MRR", dollars(data.current_mrr, True))
    cols[1].metric("Current ARR", dollars(data.current_arr, True))
    cols[2].metric("Future contracted MRR", dollars(data.future_contracted_mrr, True))
    st.write("")
    st.info("MarketReader currently has billing and contract totals only. Acuity finance, churn, Syft and HubSpot metrics are intentionally not shown in this entity view.")


with st.sidebar:
    st.markdown("## ◈ ACUITY")
    st.caption("Finance & Commercial Intelligence")
    st.write("")
    st.caption("ENTITY")
    entity = st.radio("Entity", ["Acuity", "MarketReader"], label_visibility="collapsed")
    st.write("")
    pages = ["Executive Summary", "Revenue & Contracts", "Renewals & Retention", "Sales Performance", "Financial Performance", "Historical Trends"] if entity == "Acuity" else ["Billing Overview", "Historical Trends"]
    page = st.radio("Navigate", pages, label_visibility="collapsed")
    st.write("")
    if st.button("↻ Refresh live data", use_container_width=True):
        st.cache_data.clear()
        st.experimental_rerun()
    if st.button("Save Monthly Snapshot", use_container_width=True):
        acuity_snapshot = load_finance_data()
        marketreader_snapshot_data = load_marketreader_data()
        saved_month = save_monthly_snapshot("Acuity", acuity_snapshot, acuity_snapshot)
        save_monthly_snapshot("MarketReader", marketreader_snapshot_data, None)
        st.success("Saved Acuity and MarketReader snapshots for {}.".format(saved_month))
    st.caption("Sources refresh every 5 minutes")

try:
    with st.spinner("Loading live finance and CRM data…"):
        if entity == "Acuity":
            finance_data = load_finance_data()
            hubspot_data = load_hubspot_data()
        else:
            marketreader_data = load_marketreader_data()
except Exception as exc:
    st.error("Could not load dashboard data: {}".format(exc))
    st.stop()

if page == "Historical Trends": historical_trends(entity)
elif entity == "MarketReader": marketreader_view(marketreader_data)
elif page == "Executive Summary": executive(finance_data, hubspot_data)
elif page == "Revenue & Contracts": revenue_contracts(finance_data)
elif page == "Renewals & Retention": renewals(finance_data, hubspot_data)
elif page == "Sales Performance": sales(hubspot_data)
else: financial(finance_data)

st.divider()
if entity == "Acuity":
    st.caption("Acuity · Live data · Google Sheets: LIVE Totals · HubSpot: Retail Pipeline & Renewal Pipeline")
else:
    st.caption("MarketReader · Live billing data · Google Sheets: LIVE Totals")

# Acuity Finance Dashboard Handover

This document explains what has been built, how it works, what the dashboard shows, and what a new owner needs in order to continue the project safely.

## Current State

The repository contains a Streamlit finance and commercial dashboard for Acuity. It combines:

- Finance metrics from the Google Sheets `LIVE Totals` worksheet.
- Commercial pipeline and renewal metrics from HubSpot.
- Monthly snapshot storage for historical comparisons.
- A Railway-ready app entry point and monthly snapshot job.

The canonical repository is:

```text
https://github.com/joeneighbour-stack/acuity-finance-dashboard.git
```

The local canonical clone used during the latest work was:

```text
C:\Users\JoeN\acuity-finance-dashboard-git
```

Do not treat `C:\Users\JoeN\acuity-finance-dashboard` as the canonical source unless it has been intentionally reconciled with Git. It has previously contained local exploratory work and credentials.

## Repository Layout

```text
app/dashboard.py                  Railway/Streamlit entry point; runs root dashboard.py
dashboard.py                      Main Streamlit UI
src/finance_adapter.py            Google Sheets reader and typed finance metric mapping
src/hubspot_adapter.py            HubSpot API reader and commercial metric mapping
src/snapshots.py                  SQLite/PostgreSQL monthly snapshot storage
src/kpi_comparisons.py            Prior-month and prior-FY comparison formatting
src/dashboard_theme.py            Shared CSS and Altair theme
src/finance_metrics.py            Pandas compatibility helpers for currency-position tests
scripts/capture_monthly_snapshot.py Monthly snapshot capture job
migrations/001_create_monthly_snapshots.sql PostgreSQL schema reference
tests/                            Unit tests for adapters, snapshots, dashboard theme, and currency position
docs/design-audit.md              Design notes
docs/handover.md                  This handover
```

## How It Is Built

The app is a Python Streamlit application. It is deliberately split into three layers:

- Data adapters read and normalize external systems.
- Typed snapshot objects carry data into the UI.
- `dashboard.py` renders pages, cards, charts, tables, and comparisons.

This is the important dependency direction:

```text
Google Sheets LIVE Totals -> src/finance_adapter.py -> dashboard.py
HubSpot CRM API           -> src/hubspot_adapter.py  -> dashboard.py
PostgreSQL/SQLite         -> src/snapshots.py        -> dashboard.py
```

The dashboard should not parse Google Sheet cells or HubSpot JSON directly. Keep source-specific rules in the adapter modules.

## Data Sources

### Google Sheets

Finance data is read from the `LIVE Totals` worksheet.

Authentication is via a Google service account. The service account must have read access to the workbook.

Supported environment variables:

```text
GOOGLE_SHEETS_ID
GOOGLE_SERVICE_ACCOUNT_JSON_B64
GOOGLE_SERVICE_ACCOUNT_JSON
GOOGLE_SERVICE_ACCOUNT_FILE
```

Recommended production setup is `GOOGLE_SERVICE_ACCOUNT_JSON_B64`, containing the Base64-encoded full service-account JSON.

The finance adapter uses label and section matching rather than hard-coded row numbers where possible. The key sections currently mapped are:

- `Current Billing`
- `Contracts after cancellations`
- `Contracts incl future ups/downs`
- `Finance Metrics`
- `Syft MI Dashboard`
- `Billing split per entity`
- `Billing split per currency`

### HubSpot

HubSpot is read through `src/hubspot_adapter.py` using:

```text
HUBSPOT_ACCESS_TOKEN
```

The adapter reads CRM deals, pipelines, stages, and relevant deal properties. It builds sales, pipeline, renewals, and cancellation-risk views.

### Snapshot Database

Historical comparisons use `src/snapshots.py`.

In local development, if `DATABASE_URL` is absent, the app falls back to:

```text
data/dashboard.db
```

In Railway, `DATABASE_URL` should point to PostgreSQL. `initialize_database()` creates the table at app startup, and the SQL reference migration is in `migrations/001_create_monthly_snapshots.sql`.

Snapshots are stored separately for:

- `Acuity`
- `MarketReader`

## What The Dashboard Shows

### Entity Selector

The sidebar lets users choose:

- `Acuity`
- `MarketReader`

Acuity has the full dashboard. MarketReader currently has billing and historical views only.

### Executive Summary

For Acuity, this shows:

- Active clients
- Active contracts
- Current MRR
- Current ARR
- Future contracted MRR
- Billing by entity
- Billing by currency
- Quarterly NRR and GRR
- Weighted pipeline
- Renewals due in the next 90 days

Finance KPIs are sourced from Google Sheets. Sales and renewals are sourced from HubSpot.

### Revenue & Contracts

This page shows contract economics:

- Average client MRR
- Customer lifetime value
- New contracts this financial year
- Average current contract length
- Average contract length all time

It also shows billing and treasury views:

- Billing by currency: native billing, GBP equivalent, and percentage of total billing.
- Currency Position: monthly customer billing compared with expected monthly payments in the same currency.

Currency Position is deliberately not summed across currencies. A USD surplus and EUR surplus are not combined, and they are not treated as directly offsetting a GBP shortage without explicit FX conversion.

Currency position fields are:

```text
currency
monthly_billing
billing_gbp_equivalent
percentage_of_total
monthly_requirements
net_position
```

The source is the `Billing split per currency` section in `LIVE Totals`. Columns B-D hold billing information; columns F-G hold monthly requirements and shortage/excess.

### Renewals & Retention

This page shows:

- NRR and GRR
- Churned clients YTD
- Churned MRR YTD
- Churned clients last year
- Churned MRR last year
- Renewal stage distribution from HubSpot
- Upcoming renewals
- Cancellation-risk detail

The finance churn KPIs come from Google Sheets. Operational renewals and cancellation-risk records come from HubSpot.

### Sales Performance

This page shows HubSpot retail pipeline performance:

- Opportunities created
- Closed won deals
- Open pipeline value
- Weighted pipeline value
- Pipeline by stage
- Methodology disclosure

Retail pipeline rules currently use:

```text
Retail Pipeline ID: 40364427
Weighted open stages:
85248585 = Negotiation = 50%
85248583 = Verbally Agreed = 60%
85248584 = Contract Out = 70%
```

Closed won/lost deals are excluded from open pipeline value.

### Financial Performance

This page shows Syft/finance-management account metrics as currently exposed through the Google Sheet:

- Revenue
- Gross profit
- Gross margin
- Net profit
- EBITDA
- EBITDA margin
- Rule of 40
- Cash
- Debtor days
- Creditor days
- Profit bridge

Despite the page wording, these values currently come through the Google Sheets `LIVE Totals` mapping, not a direct Syft API integration.

### Historical Trends

Historical Trends reads monthly snapshots from SQLite/PostgreSQL. It does not query HubSpot or Google Sheets for historical data directly.

Snapshots are created by `scripts/capture_monthly_snapshot.py`, not by normal dashboard viewing.

## Important Business Rules

Current rules embedded in the code include:

- Financial year starts on 1 February.
- HubSpot Retail Pipeline ID is `40364427`.
- Acuity Renewal Pipeline ID is `85559454`.
- MarketReader Renewal Pipeline ID is `907190335`.
- Acuity renewal active stages:
  - `247553603` = >6 Months Until Renewal
  - `247553604` = 6-4 Months Until Renewal
  - `247553605` = <4 Months Until Renewal
  - `247553606` = <30 Days Until Renewal
- Cancellation-received HubSpot tag ID is `19599895`.
- Retail weighted pipeline currently includes Negotiation, Verbally Agreed, and Contract Out only.
- Currency Position must preserve native currencies and must not produce a combined cross-currency surplus/shortage.

## Running Locally

Install dependencies:

```text
python -m pip install -r requirements.txt
```

Create `.env` locally. Do not commit it.

Minimum local `.env` values:

```text
GOOGLE_SHEETS_ID=...
GOOGLE_SERVICE_ACCOUNT_FILE=credentials.json
HUBSPOT_ACCESS_TOKEN=...
```

Run the dashboard:

```text
streamlit run dashboard.py
```

Run all tests:

```text
python -B -m unittest discover -s tests
```

If snapshot tests fail locally with SQLite temp-file errors, check that Python can create temporary directories and that the project has a writable `data/` folder.

## Deployment

The Streamlit app entry point for Railway is:

```text
streamlit run app/dashboard.py --server.address 0.0.0.0 --server.port $PORT
```

Railway should have:

- A PostgreSQL service.
- A dashboard web service.
- A scheduled monthly snapshot service.

Required production variables:

```text
DATABASE_URL
GOOGLE_SHEETS_ID
GOOGLE_SERVICE_ACCOUNT_JSON_B64
HUBSPOT_ACCESS_TOKEN
```

Monthly snapshot command:

```text
python scripts/capture_monthly_snapshot.py
```

Schedule this after month end. Use `--force` only for an intentional overwrite/upsert.

## Continuity Checklist

To pick this up without the original builder:

1. Clone the canonical GitHub repository.
2. Confirm the active branch is `main`.
3. Obtain access to the Google Sheet and verify the service account can read `LIVE Totals`.
4. Obtain a HubSpot private app token with read access to deals, pipelines, stages, and needed deal properties.
5. Obtain Railway access and confirm app, database, and scheduled job environment variables.
6. Run `python -B -m unittest discover -s tests`.
7. Run `streamlit run dashboard.py` locally with real credentials.
8. Compare Executive Summary, Revenue & Contracts, Renewals, Sales, and Financial Performance against the source systems.
9. Before changing Google Sheet mappings, update or add tests in `tests/test_finance_adapter.py` or `tests/test_finance_currency_position.py`.
10. Before changing HubSpot rules, update or add tests in `tests/test_hubspot_adapter.py`.
11. Keep credentials out of Git and logs.
12. Commit small, named changes and push to the canonical repository.

## Known Caveats

- The Google Sheet is a formatted report, not a clean database table. Label matching is used to reduce row-number fragility, but major layout changes can still break mappings.
- Some text in the current app output contains encoding artifacts such as `Â£` in older strings. New currency-position formatting uses explicit Unicode names for pound and euro symbols, but a future cleanup pass should normalize the whole codebase to UTF-8 display text.
- MarketReader currently has a smaller metric set than Acuity.
- Syft is not integrated directly yet; financial performance values are read from the Google Sheet.
- Currency Position is live only and is intentionally not included in monthly snapshots yet.
- Pipeline history for open weighted pipeline is limited; live pipeline values should not be treated as fully reconstructed historical pipeline snapshots.
- The older non-canonical folder may contain local files and credentials. Do not copy from it wholesale.

## Safe Change Pattern

For finance metric changes:

1. Update `_METRICS`, `_CHARTS`, or parsing helpers in `src/finance_adapter.py`.
2. Add a focused fake-sheet test.
3. Update `dashboard.py` only after the typed finance object exposes the new value.
4. Run the full unittest suite.

For HubSpot metric changes:

1. Update constants and mapping logic in `src/hubspot_adapter.py`.
2. Add tests with fake deals/pipelines.
3. Keep pipeline IDs and stage IDs explicit.
4. Do not use fuzzy stage names for business-critical filters.

For presentation changes:

1. Prefer `src/dashboard_theme.py` for shared visual changes.
2. Keep page-specific rendering in `dashboard.py`.
3. Check desktop and narrow layouts if changing cards, grids, or tables.

## Latest Notable Changes

- Added Currency Position to Revenue & Contracts.
- Added native-currency monthly billing, requirements, and net position mapping from `Billing split per currency`.
- Added tests for GBP, USD, EUR requirement and surplus/shortage handling.
- Standardized dashboard KPI/comparison card sizing to avoid misaligned boxes.

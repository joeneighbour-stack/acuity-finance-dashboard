# Acuity Finance Dashboard

Streamlit dashboard using finance data from the Google Sheets `LIVE Totals` tab, commercial data from HubSpot, and monthly historical snapshots.

## Local development

1. Create a virtual environment and install `requirements.txt`.
2. Copy `.env.example` to `.env` and provide the Google Sheet, service-account file, and HubSpot values.
3. Run `streamlit run dashboard.py`.

If `DATABASE_URL` is absent, snapshots use `data/dashboard.db` as a local SQLite fallback. Credentials, JSON keys, local databases, caches, and virtual environments are ignored by Git.

## Railway deployment

Create one Railway project containing:

1. A PostgreSQL service.
2. A dashboard service built from this repository.
3. A scheduled snapshot service built from this repository.

Set these variables on both application services:

- `DATABASE_URL` — use a Railway variable reference to the PostgreSQL service.
- `GOOGLE_SHEETS_ID` — the finance workbook ID.
- `GOOGLE_SERVICE_ACCOUNT_JSON_B64` — Base64 encoding of the complete service-account JSON file. This is the recommended Railway configuration.
- `GOOGLE_SERVICE_ACCOUNT_JSON` — raw service-account JSON fallback.
- `GOOGLE_SERVICE_ACCOUNT_FILE` — optional local-development fallback containing a path to the JSON file.

Set `HUBSPOT_ACCESS_TOKEN` on the dashboard service. Never paste credential contents into the repository or build logs.

The dashboard start command is:

```text
streamlit run app/dashboard.py --server.address 0.0.0.0 --server.port $PORT
```

The snapshot job command is:

```text
python scripts/capture_monthly_snapshot.py
```

Schedule the snapshot service monthly, after the month has ended. It records the previous calendar month and safely skips records that already exist. Use `--force` only when an intentional re-capture is needed.

`initialize_database()` creates the table automatically at application startup. The equivalent explicit PostgreSQL migration is in `migrations/001_create_monthly_snapshots.sql`.

## Snapshot behaviour

Snapshots are stored as separate `Acuity` and `MarketReader` rows. PostgreSQL uses an atomic `ON CONFLICT (snapshot_month, entity) DO UPDATE` operation. Historical Trends calls the same data-access module and therefore reads PostgreSQL whenever `DATABASE_URL` is set.

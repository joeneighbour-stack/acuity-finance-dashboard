"""Monthly SQLite snapshots of finance-approved Google Sheet values."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional


DATABASE_PATH = Path(__file__).resolve().parent.parent / "data" / "dashboard.db"

VALUE_COLUMNS = (
    "active_clients", "active_contracts", "current_mrr", "current_arr",
    "future_mrr", "future_arr", "average_client_mrr", "average_contract_length",
    "average_contract_length_all_time", "clv", "churned_clients_ytd",
    "churned_mrr_ytd", "churned_clients_last_year", "churned_mrr_last_year",
    "new_contracts", "nrr_quarterly", "grr_quarterly", "cac", "total_income",
    "gross_profit", "gross_margin", "net_profit", "net_profit_margin", "ebitda",
    "ebitda_margin", "rule_of_40", "cash", "debtor_days", "creditor_days",
)

ATTRIBUTE_MAP = {
    "future_mrr": "future_contracted_mrr",
    "future_arr": "future_contracted_arr",
    "total_income": "revenue",
}


def _connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(DATABASE_PATH))
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with _connect() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS monthly_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_month TEXT NOT NULL,
                snapshot_date TEXT NOT NULL,
                entity TEXT NOT NULL,
                active_clients INTEGER,
                active_contracts INTEGER,
                current_mrr REAL,
                current_arr REAL,
                future_mrr REAL,
                future_arr REAL,
                average_client_mrr REAL,
                average_contract_length REAL,
                average_contract_length_all_time REAL,
                clv REAL,
                churned_clients_ytd INTEGER,
                churned_mrr_ytd REAL,
                churned_clients_last_year INTEGER,
                churned_mrr_last_year REAL,
                new_contracts INTEGER,
                nrr_quarterly REAL,
                grr_quarterly REAL,
                cac REAL,
                total_income REAL,
                gross_profit REAL,
                gross_margin REAL,
                net_profit REAL,
                net_profit_margin REAL,
                ebitda REAL,
                ebitda_margin REAL,
                rule_of_40 REAL,
                cash REAL,
                debtor_days REAL,
                creditor_days REAL,
                created_at TEXT NOT NULL,
                UNIQUE(snapshot_month, entity)
            )
        """)


def _number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return value
    return float(value)


def _source_value(column: str, finance_kpis: Any, syft_kpis: Any) -> Optional[float]:
    attribute = ATTRIBUTE_MAP.get(column, column)
    for source in (finance_kpis, syft_kpis):
        if source is not None and hasattr(source, attribute):
            return _number(getattr(source, attribute))
    return None


def save_monthly_snapshot(entity: str, finance_kpis: Any, syft_kpis: Any = None) -> str:
    if entity not in {"Acuity", "MarketReader"}:
        raise ValueError("entity must be Acuity or MarketReader")
    initialize_database()
    today = date.today()
    values = {column: _source_value(column, finance_kpis, syft_kpis) for column in VALUE_COLUMNS}
    row = {
        "snapshot_month": today.strftime("%Y-%m"),
        "snapshot_date": today.isoformat(),
        "entity": entity,
        **values,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    columns = tuple(row)
    assignments = ", ".join("{0}=excluded.{0}".format(column) for column in columns if column not in {"snapshot_month", "entity"})
    sql = """INSERT INTO monthly_snapshots ({columns}) VALUES ({placeholders})
             ON CONFLICT(snapshot_month, entity) DO UPDATE SET {assignments}""".format(
        columns=", ".join(columns), placeholders=", ".join("?" for _ in columns), assignments=assignments
    )
    with _connect() as connection:
        connection.execute(sql, [row[column] for column in columns])
    return row["snapshot_month"]


def get_monthly_snapshots(entity: Optional[str] = None) -> List[Dict[str, Any]]:
    initialize_database()
    sql = "SELECT * FROM monthly_snapshots"
    params = []
    if entity is not None:
        sql += " WHERE entity = ?"
        params.append(entity)
    sql += " ORDER BY snapshot_month, entity"
    with _connect() as connection:
        return [dict(row) for row in connection.execute(sql, params).fetchall()]


def snapshot_exists(snapshot_month: str, entity: str) -> bool:
    initialize_database()
    with _connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM monthly_snapshots WHERE snapshot_month = ? AND entity = ?",
            (snapshot_month, entity),
        ).fetchone()
    return row is not None


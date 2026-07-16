"""Monthly finance snapshots backed by Railway PostgreSQL or local SQLite."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from sqlalchemy import BigInteger, Column, Date, DateTime, Integer, MetaData, Numeric, String, Table, UniqueConstraint, create_engine, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.engine import Engine
from sqlalchemy.sql import func

DATABASE_PATH = Path(__file__).resolve().parent.parent / "data" / "dashboard.db"
VALUE_COLUMNS = (
    "active_clients", "active_contracts", "current_mrr", "current_arr", "future_mrr", "future_arr",
    "average_client_mrr", "average_contract_length", "average_contract_length_all_time", "clv",
    "churned_clients_ytd", "churned_mrr_ytd", "churned_clients_last_year", "churned_mrr_last_year",
    "new_contracts", "nrr_quarterly", "grr_quarterly", "cac", "total_income", "gross_profit",
    "gross_margin", "net_profit", "net_profit_margin", "ebitda", "ebitda_margin", "rule_of_40",
    "cash", "debtor_days", "creditor_days",
)
INTEGER_COLUMNS = {"active_clients", "active_contracts", "churned_clients_ytd", "churned_clients_last_year", "new_contracts"}
ATTRIBUTE_MAP = {"future_mrr": "future_contracted_mrr", "future_arr": "future_contracted_arr", "total_income": "revenue"}

metadata = MetaData()
monthly_snapshots = Table(
    "monthly_snapshots", metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("snapshot_month", String(7), nullable=False),
    Column("snapshot_date", Date, nullable=False),
    Column("entity", String(50), nullable=False),
    *[Column(name, Integer if name in INTEGER_COLUMNS else Numeric, nullable=True) for name in VALUE_COLUMNS],
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("snapshot_month", "entity", name="uq_monthly_snapshots_month_entity"),
)

_engine: Optional[Engine] = None
_engine_key: Optional[str] = None


def _database_url() -> str:
    value = os.environ.get("DATABASE_URL", "").strip()
    if value.startswith("postgres://"):
        value = "postgresql+psycopg://" + value[len("postgres://"):]
    elif value.startswith("postgresql://"):
        value = "postgresql+psycopg://" + value[len("postgresql://"):]
    return value or "sqlite:///{}".format(DATABASE_PATH.as_posix())


def get_engine() -> Engine:
    global _engine, _engine_key
    url = _database_url()
    if _engine is None or _engine_key != url:
        if url.startswith("sqlite"):
            DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(url, pool_pre_ping=True)
        _engine_key = url
    return _engine


def initialize_database() -> None:
    metadata.create_all(get_engine(), tables=[monthly_snapshots])


def _number(value: Any) -> Optional[Decimal | int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _source_value(column: str, finance_kpis: Any, syft_kpis: Any) -> Optional[Decimal | int]:
    attribute = ATTRIBUTE_MAP.get(column, column)
    for source in (finance_kpis, syft_kpis):
        if source is not None and hasattr(source, attribute):
            return _number(getattr(source, attribute))
    return None


def build_snapshot_payload(entity: str, finance_kpis: Any, syft_kpis: Any = None, *, snapshot_month: Optional[str] = None, snapshot_date: Optional[date] = None) -> Dict[str, Any]:
    """Build a database payload without opening a connection."""
    if entity not in {"Acuity", "MarketReader"}:
        raise ValueError("entity must be Acuity or MarketReader")
    effective_date = snapshot_date or date.today()
    month = snapshot_month or effective_date.strftime("%Y-%m")
    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError as exc:
        raise ValueError("snapshot_month must use YYYY-MM format") from exc
    return {
        "snapshot_month": month, "snapshot_date": effective_date, "entity": entity,
        **{column: _source_value(column, finance_kpis, syft_kpis) for column in VALUE_COLUMNS},
    }


def _upsert_statement(engine: Engine, payload: Mapping[str, Any]):
    """Build an atomic ON CONFLICT upsert for PostgreSQL or SQLite."""
    if engine.dialect.name == "postgresql":
        statement = postgresql_insert(monthly_snapshots).values(**payload)
    else:
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        statement = sqlite_insert(monthly_snapshots).values(**payload)
    updates = {column: getattr(statement.excluded, column) for column in payload if column not in {"snapshot_month", "entity"}}
    return statement.on_conflict_do_update(
        index_elements=[monthly_snapshots.c.snapshot_month, monthly_snapshots.c.entity], set_=updates,
    )


def save_monthly_snapshot(entity: str, finance_kpis: Any, syft_kpis: Any = None, *, snapshot_month: Optional[str] = None, snapshot_date: Optional[date] = None) -> str:
    initialize_database()
    payload = build_snapshot_payload(entity, finance_kpis, syft_kpis, snapshot_month=snapshot_month, snapshot_date=snapshot_date)
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(_upsert_statement(engine, payload))
    return str(payload["snapshot_month"])


def get_monthly_snapshots(entity: Optional[str] = None) -> List[Dict[str, Any]]:
    initialize_database()
    statement = select(monthly_snapshots)
    if entity is not None:
        statement = statement.where(monthly_snapshots.c.entity == entity)
    statement = statement.order_by(monthly_snapshots.c.snapshot_month, monthly_snapshots.c.entity)
    with get_engine().connect() as connection:
        return [dict(row) for row in connection.execute(statement).mappings().all()]


def snapshot_exists(snapshot_month: str, entity: str) -> bool:
    initialize_database()
    statement = select(monthly_snapshots.c.id).where(
        monthly_snapshots.c.snapshot_month == snapshot_month,
        monthly_snapshots.c.entity == entity,
    ).limit(1)
    with get_engine().connect() as connection:
        return connection.execute(statement).first() is not None


def reset_engine_for_tests() -> None:
    global _engine, _engine_key
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _engine_key = None

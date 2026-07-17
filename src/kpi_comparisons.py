"""Read-only helpers for comparing live KPIs with completed snapshots."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, NamedTuple, Optional

from src.snapshots import get_monthly_snapshots


class Variance(NamedTuple):
    absolute_change: Optional[Decimal]
    percentage_change: Optional[Decimal]


def _decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, bool):
        return Decimal(int(value))
    try:
        return value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def get_latest_completed_snapshot(
    entity: str, *, today: Optional[date] = None
) -> Optional[Dict[str, Any]]:
    """Return the entity's latest snapshot before the current calendar month."""
    current_month = (today or date.today()).strftime("%Y-%m")
    completed = [
        row for row in get_monthly_snapshots(entity)
        if row.get("snapshot_month") and str(row["snapshot_month"]) < current_month
    ]
    return max(completed, key=lambda row: str(row["snapshot_month"])) if completed else None


def calculate_variance(current_value: Any, previous_value: Any) -> Variance:
    """Calculate absolute and percentage movement without coercing missing data."""
    current = _decimal(current_value)
    previous = _decimal(previous_value)
    if current is None or previous is None:
        return Variance(None, None)
    absolute_change = current - previous
    percentage_change = None if previous == 0 else absolute_change / abs(previous) * Decimal("100")
    return Variance(absolute_change, percentage_change)


def format_variance(current_value: Any, previous_value: Any, metric_type: str) -> str:
    """Format movement for currency, count, percentage-point, or day metrics."""
    variance = calculate_variance(current_value, previous_value)
    change = variance.absolute_change
    if change is None:
        return "No prior-month comparison"

    indicator = "▲" if change > 0 else "▼" if change < 0 else "—"
    sign = "+" if change > 0 else "-" if change < 0 else ""
    if metric_type in {"currency", "dollars"}:
        symbol = "£" if metric_type == "currency" else "$"
        movement = "{}{}{:,.0f}".format(sign, symbol, abs(change))
    elif metric_type == "count":
        movement = "{}{:,}".format(sign, abs(int(change)))
    elif metric_type == "percentage":
        movement = "{}{:.1f} percentage points".format(sign, abs(change))
        return "{} {}".format(indicator, movement)
    elif metric_type == "days":
        movement = "{}{:.1f} days".format(sign, abs(change))
        if change == change.to_integral_value():
            movement = "{}{:,} days".format(sign, abs(int(change)))
        return "{} {}".format(indicator, movement)
    else:
        raise ValueError("metric_type must be currency, dollars, count, percentage, or days")

    percentage = variance.percentage_change
    if percentage is None:
        percentage_text = ""
    else:
        percentage_sign = "+" if percentage > 0 else "-" if percentage < 0 else ""
        percentage_text = " ({}{:.1f}%)".format(percentage_sign, abs(percentage))
    return "{} {}{}".format(indicator, movement, percentage_text)


def format_snapshot_month(snapshot_month: Any) -> str:
    """Format YYYY-MM as an abbreviated executive-friendly month label."""
    if snapshot_month is None:
        return ""
    try:
        return datetime.strptime(str(snapshot_month), "%Y-%m").strftime("%b %Y")
    except (TypeError, ValueError):
        return str(snapshot_month)

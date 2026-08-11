"""Compatibility helpers for finance-sheet currency funding metrics.

The production dashboard uses :mod:`src.finance_adapter`.  These helpers keep
the currency-position parsing easy to unit test from a pandas DataFrame.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

import pandas as pd


METRIC_COLUMN = "finance metrics - Google Docs"
CURRENCIES = ("GBP", "USD", "EUR")


def _normalise(value) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _numeric(value):
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = re.sub(r"[^\d.\-]", "", text)
    if text in {"", "-"}:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return -number if negative else number


def _first_column(df: pd.DataFrame) -> str:
    if METRIC_COLUMN in df.columns:
        return METRIC_COLUMN
    return str(df.columns[0])


def _billing_split_currency_rows(df: pd.DataFrame) -> pd.DataFrame:
    label_column = _first_column(df)
    section = df[label_column].astype(str).map(_normalise).eq(_normalise("Billing split per currency"))
    if not section.any():
        raise ValueError("Could not find 'Billing split per currency' section")

    start = int(section[section].index[0]) + 1
    rows = []
    for _, row in df.iloc[start:].iterrows():
        currency = str(row.get(label_column, "") or "").strip().upper()
        if not currency:
            break
        if currency not in CURRENCIES:
            continue
        rows.append({
            "currency": currency,
            "monthly_billing": _numeric(row.get("Column 2")),
            "billing_gbp_equivalent": _numeric(row.get("Column 3")),
            "percentage_of_total": _numeric(row.get("Column 4")),
            "monthly_requirements": _numeric(row.get("Column 6")),
            "net_position": _numeric(row.get("Column 7")),
        })

    return pd.DataFrame(rows, columns=[
        "currency",
        "monthly_billing",
        "billing_gbp_equivalent",
        "percentage_of_total",
        "monthly_requirements",
        "net_position",
    ])


def billing_by_currency(df: pd.DataFrame) -> pd.DataFrame:
    return _billing_split_currency_rows(df)


def currency_position(df: pd.DataFrame) -> pd.DataFrame:
    return _billing_split_currency_rows(df)[[
        "currency",
        "monthly_billing",
        "monthly_requirements",
        "net_position",
    ]]


def format_native_currency(value, currency: str, compact: bool = False) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    number = float(value)
    symbols = {"GBP": "\N{POUND SIGN}", "USD": "$", "EUR": "\N{EURO SIGN}"}
    symbol = symbols.get(currency.upper(), f"{currency.upper()} ")
    if compact and abs(number) >= 1_000_000:
        return f"{symbol}{number / 1_000_000:.1f}m"
    if compact and abs(number) >= 1_000:
        return f"{symbol}{number / 1_000:.1f}k"
    return f"{symbol}{number:,.0f}"


def position_label(value) -> str:
    if value is None or pd.isna(value):
        return "Not available"
    if value > 0:
        return "Surplus"
    if value < 0:
        return "Shortage"
    return "Balanced"

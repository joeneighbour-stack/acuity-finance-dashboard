"""Typed, label-driven access to finance data stored in Google Sheets.

This is the only module that knows how the finance workbook is laid out.  The
dashboard consumes the public functions at the bottom of this file and never
indexes cells or matches spreadsheet labels itself.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import re
from typing import Mapping, Sequence, Union


Cell = Union[str, int, float, bool, None]
Row = Sequence[Cell]
LIVE_TOTALS_WORKSHEET = "LIVE Totals"
GOOGLE_SHEETS_SCOPES = ("https://www.googleapis.com/auth/spreadsheets.readonly",)
GOOGLE_CREDENTIALS_ERROR = "Google service-account credentials are not configured correctly."


def _load_dotenv() -> None:
    """Load the project .env file without overwriting real environment values."""
    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


class FinanceDataError(RuntimeError):
    """Base class for finance integration failures."""


class LabelNotFoundError(FinanceDataError):
    """Raised when a mapped section or row cannot be found."""


class ValueParseError(FinanceDataError):
    """Raised when a mapped value cannot be converted to its declared type."""


def load_google_credentials(scopes: Sequence[str] = GOOGLE_SHEETS_SCOPES):
    """Load Base64 Railway credentials, then raw JSON, then a local file."""
    try:
        from google.oauth2 import service_account
    except ImportError as exc:
        raise FinanceDataError(
            "Install google-auth to authenticate with Google Sheets"
        ) from exc

    def credentials_from_info(credentials_info):
        if not isinstance(credentials_info, dict):
            raise ValueError("credentials must be a JSON object")
        private_key = credentials_info.get("private_key")
        if isinstance(private_key, str):
            credentials_info["private_key"] = private_key.replace("\\n", "\n")
        return service_account.Credentials.from_service_account_info(
            credentials_info, scopes=scopes
        )

    credentials_b64 = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_B64", "").strip()
    if credentials_b64:
        try:
            decoded_json = base64.b64decode(credentials_b64, validate=True).decode("utf-8")
            return credentials_from_info(json.loads(decoded_json))
        except Exception as exc:
            raise FinanceDataError(GOOGLE_CREDENTIALS_ERROR) from exc

    credentials_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if credentials_json:
        try:
            return credentials_from_info(json.loads(credentials_json))
        except Exception as exc:
            raise FinanceDataError(GOOGLE_CREDENTIALS_ERROR) from exc

    credentials_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    if credentials_file:
        try:
            return service_account.Credentials.from_service_account_file(
                credentials_file, scopes=scopes
            )
        except Exception as exc:
            raise FinanceDataError(GOOGLE_CREDENTIALS_ERROR) from exc

    raise FinanceDataError(GOOGLE_CREDENTIALS_ERROR)


class SheetReader:
    """Minimal boundary implemented by GoogleSheetsReader and test doubles."""

    def worksheets(self) -> Mapping[str, Sequence[Row]]:
        raise NotImplementedError


@dataclass(frozen=True)
class ChartPoint:
    label: str
    value: Decimal


@dataclass(frozen=True)
class FinanceSnapshot:
    active_clients: int
    active_contracts: int
    current_mrr: Decimal
    current_arr: Decimal
    future_contracted_mrr: Decimal
    future_contracted_arr: Decimal
    nrr_quarterly: Decimal | None
    grr_quarterly: Decimal | None
    billing_by_entity: tuple[ChartPoint, ...]
    billing_by_currency: tuple[ChartPoint, ...]
    average_client_mrr: Decimal
    average_contract_length: Decimal
    average_contract_length_all_time: Decimal
    clv: Decimal
    new_contracts: int
    cac: Decimal | None
    churned_clients_ytd: int
    churned_mrr_ytd: Decimal
    churned_clients_last_year: int
    churned_mrr_last_year: Decimal
    revenue: Decimal
    gross_profit: Decimal
    gross_margin: Decimal | None
    net_profit: Decimal
    net_profit_margin: Decimal | None
    ebitda: Decimal
    ebitda_margin: Decimal
    rule_of_40: Decimal
    cash: Decimal
    debtor_days: Decimal
    creditor_days: Decimal


@dataclass(frozen=True)
class MarketReaderSnapshot:
    active_clients: int
    active_contracts: int
    current_mrr: Decimal
    current_arr: Decimal
    future_contracted_mrr: Decimal
    future_contracted_arr: Decimal
    average_client_mrr: Decimal


@dataclass(frozen=True)
class _Metric:
    section: str
    label: str


_METRICS: dict[str, _Metric] = {
    "active_clients": _Metric("Current Billing", "Client count (Current)"),
    "active_contracts": _Metric("Current Billing", "Contract count (Current)"),
    "current_mrr": _Metric("Current Billing", "Current Monthly Billing"),
    "current_arr": _Metric("Contracts after cancellations", "ARR (GBP) after cancelled revenue"),
    "future_contracted_mrr": _Metric("Contracts incl future ups/downs", "MRR (GBP) incl future ramp ups"),
    "future_contracted_arr": _Metric("Contracts incl future ups/downs", "ARR (GBP) incl future ramp ups"),
    "nrr_quarterly": _Metric("Finance Metrics", "NRR (Net Revenue Retention) % Q"),
    "grr_quarterly": _Metric("Finance Metrics", "GRR (Gross Revenue Retention) % Q"),
    "average_client_mrr": _Metric("Current Billing", "Current Client Ave MRR"),
    "average_contract_length": _Metric("Finance Metrics", "Contract Ave length (months)"),
    "average_contract_length_all_time": _Metric("Finance Metrics", "Contract Ave all time"),
    "clv": _Metric("Finance Metrics", "CLV (Customer Lifetime Value)"),
    "new_contracts": _Metric("Finance Metrics", "New contracts since Feb 2026"),
    "cac": _Metric("Finance Metrics", "CAC"),
    "churned_clients_ytd": _Metric("Finance Metrics", "Churned Clients YTD"),
    "churned_mrr_ytd": _Metric("Finance Metrics", "Churned Clients YTD (MRR)"),
    "churned_clients_last_year": _Metric("Finance Metrics", "Churned Clients Last Year"),
    "churned_mrr_last_year": _Metric("Finance Metrics", "Churned Clients Last Year (MRR)"),
    "revenue": _Metric("Syft MI Dashboard", "Total income"),
    "gross_profit": _Metric("Syft MI Dashboard", "Gross profit"),
    "gross_margin": _Metric("Syft MI Dashboard", "Gross profit margin"),
    "net_profit": _Metric("Syft MI Dashboard", "Net profit"),
    "net_profit_margin": _Metric("Syft MI Dashboard", "Net profit margin"),
    # The live source currently spells these labels "EBIDTA".
    "ebitda": _Metric("Syft MI Dashboard", "EBIDTA"),
    "ebitda_margin": _Metric("Syft MI Dashboard", "EBIDTA Margin"),
    "rule_of_40": _Metric("Syft MI Dashboard", "Rule of 40"),
    "cash": _Metric("Syft MI Dashboard", "Cash"),
    "debtor_days": _Metric("Syft MI Dashboard", "Debtors days"),
    "creditor_days": _Metric("Syft MI Dashboard", "Creditors days"),
}

_CHARTS = {
    "billing_by_entity": ("Billing split per entity", "Entity table"),
    "billing_by_currency": ("Billing split per currency", "Currency table"),
}


def _normalise(value: Cell) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _decimal(value: Cell) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueParseError(f"Expected a number, got {value!r}")
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    text = str(value).strip()
    negative = text.startswith("(") and text.endswith(")")
    text = re.sub(r"(?i)\bdays?\b", "", text)
    text = re.sub(r"[£$€,%\s]", "", text.strip("()"))
    if text in {"", "-", "—", "n/a", "N/A"}:
        raise ValueParseError(f"Expected a number, got {value!r}")
    multiplier = Decimal(1)
    if text[-1:].casefold() in {"k", "m"}:
        multiplier = Decimal(1_000 if text[-1].casefold() == "k" else 1_000_000)
        text = text[:-1]
    try:
        result = Decimal(text.replace(",", "")) * multiplier
    except InvalidOperation as exc:
        raise ValueParseError(f"Expected a number, got {value!r}") from exc
    return -result if negative else result


def _all_rows(reader: SheetReader) -> list[tuple[str, int, Row]]:
    return [
        (worksheet, row_number, row)
        for worksheet, rows in reader.worksheets().items()
        for row_number, row in enumerate(rows, start=1)
    ]


def _section_ranges(reader: SheetReader, section: str) -> list[tuple[str, list[tuple[int, Row]]]]:
    wanted = _normalise(section)
    result: list[tuple[str, list[tuple[int, Row]]]] = []
    for worksheet, rows in reader.worksheets().items():
        starts = [i for i, row in enumerate(rows) if any(_normalise(c) == wanted for c in row)]
        for start in starts:
            # A blank row conventionally ends a block; cap the search to avoid a
            # same-named metric in a distant section being selected accidentally.
            block: list[tuple[int, Row]] = []
            for i in range(start, min(start + 100, len(rows))):
                row = rows[i]
                if i > start and not any(str(c or "").strip() for c in row):
                    break
                block.append((i + 1, row))
            result.append((worksheet, block))
    return result


def _mapped_rows(reader: SheetReader, metric: _Metric) -> list[tuple[str, int, Row, int]]:
    wanted = _normalise(metric.label)
    matches: list[tuple[str, int, Row, int]] = []
    matched_cells = set()
    blocks = _section_ranges(reader, metric.section)
    search = blocks or [
        (name, [(number, row) for sheet, number, row in _all_rows(reader) if sheet == name])
        for name in reader.worksheets()
    ]
    for worksheet, rows in search:
        for number, row in rows:
            for column, cell in enumerate(row):
                if _normalise(cell) == wanted:
                    location = (worksheet, number, column)
                    if location not in matched_cells:
                        matched_cells.add(location)
                        matches.append((worksheet, number, row, column))
    if not matches:
        raise LabelNotFoundError(f"Could not find {metric.label!r} in section {metric.section!r}")
    return matches


def _value(reader: SheetReader, name: str, marketreader: bool = False) -> Decimal:
    values: list[Decimal] = []
    for _, number, row, label_column in _mapped_rows(reader, _METRICS[name]):
        if marketreader != (label_column >= 4):
            continue
        value = None
        for cell in row[label_column + 1 :]:
            try:
                value = _decimal(cell)
                break
            except ValueParseError:
                pass
        if value is None:
            continue
        values.append(value)
    if not values:
        raise ValueParseError(f"No numeric value follows {_METRICS[name].label!r}")
    return sum(values, Decimal(0))


def _count(reader: SheetReader, name: str, marketreader: bool = False) -> int:
    value = _value(reader, name, marketreader)
    if value != value.to_integral_value():
        raise ValueParseError(f"{_METRICS[name].label!r} is not a whole number: {value}")
    return int(value)


def _chart(reader: SheetReader, name: str) -> tuple[ChartPoint, ...]:
    section, _ = _CHARTS[name]
    blocks = _section_ranges(reader, section)
    if not blocks:
        raise LabelNotFoundError(f"Could not find chart section {section!r}")
    points: list[ChartPoint] = []
    for _, rows in blocks:
        section_seen = False
        for _, row in rows:
            normalised = [_normalise(c) for c in row]
            if _normalise(section) in normalised:
                section_seen = True
                continue
            if not section_seen:
                continue
            if not row or not str(row[0] or "").strip():
                continue
            label = str(row[0]).strip()
            if _normalise(label) in {"entity", "currency", "total"}:
                continue
            value_column = 1 if name == "billing_by_entity" else 2
            if len(row) <= value_column:
                continue
            try:
                points.append(ChartPoint(label=label, value=_decimal(row[value_column])))
            except ValueParseError:
                continue
    if not points:
        raise ValueParseError(f"No chart rows found for {section!r}")
    return tuple(points)


def active_clients(reader: SheetReader) -> int: return _count(reader, "active_clients")
def active_contracts(reader: SheetReader) -> int: return _count(reader, "active_contracts")
def current_mrr(reader: SheetReader) -> Decimal: return _value(reader, "current_mrr")
def current_arr(reader: SheetReader) -> Decimal: return _value(reader, "current_arr")
def future_contracted_mrr(reader: SheetReader) -> Decimal: return _value(reader, "future_contracted_mrr")
def future_contracted_arr(reader: SheetReader) -> Decimal: return _value(reader, "future_contracted_arr")


def _optional_value(reader: SheetReader, name: str) -> Decimal | None:
    try:
        return _value(reader, name)
    except (LabelNotFoundError, ValueParseError):
        return None


def nrr_quarterly(reader: SheetReader) -> Decimal | None: return _optional_value(reader, "nrr_quarterly")
def grr_quarterly(reader: SheetReader) -> Decimal | None: return _optional_value(reader, "grr_quarterly")


def billing_by_entity(reader: SheetReader) -> tuple[ChartPoint, ...]: return _chart(reader, "billing_by_entity")
def billing_by_currency(reader: SheetReader) -> tuple[ChartPoint, ...]: return _chart(reader, "billing_by_currency")
# The mapping names the same underlying datasets differently on the Revenue page.
def revenue_by_entity(reader: SheetReader) -> tuple[ChartPoint, ...]: return billing_by_entity(reader)
def revenue_by_currency(reader: SheetReader) -> tuple[ChartPoint, ...]: return billing_by_currency(reader)
def average_client_mrr(reader: SheetReader) -> Decimal:
    clients = active_clients(reader)
    return current_mrr(reader) / Decimal(clients) if clients else Decimal(0)
def average_contract_length(reader: SheetReader) -> Decimal: return _value(reader, "average_contract_length")
def average_contract_length_all_time(reader: SheetReader) -> Decimal: return _value(reader, "average_contract_length_all_time")
def clv(reader: SheetReader) -> Decimal: return _value(reader, "clv")
def new_contracts(reader: SheetReader) -> int: return _count(reader, "new_contracts")
def cac(reader: SheetReader) -> Decimal | None: return _optional_value(reader, "cac")
def churned_clients_ytd(reader: SheetReader) -> int: return _count(reader, "churned_clients_ytd")
def churned_mrr_ytd(reader: SheetReader) -> Decimal: return _value(reader, "churned_mrr_ytd")
def churned_clients_last_year(reader: SheetReader) -> int: return _count(reader, "churned_clients_last_year")
def churned_mrr_last_year(reader: SheetReader) -> Decimal: return _value(reader, "churned_mrr_last_year")
def revenue(reader: SheetReader) -> Decimal: return _value(reader, "revenue")
def gross_profit(reader: SheetReader) -> Decimal: return _value(reader, "gross_profit")
def gross_margin(reader: SheetReader) -> Decimal | None: return _optional_value(reader, "gross_margin")
def net_profit(reader: SheetReader) -> Decimal: return _value(reader, "net_profit")
def net_profit_margin(reader: SheetReader) -> Decimal | None: return _optional_value(reader, "net_profit_margin")
def ebitda(reader: SheetReader) -> Decimal: return _value(reader, "ebitda")
def ebitda_margin(reader: SheetReader) -> Decimal: return _value(reader, "ebitda_margin")
def rule_of_40(reader: SheetReader) -> Decimal: return _value(reader, "rule_of_40")
def cash(reader: SheetReader) -> Decimal: return _value(reader, "cash")
def debtor_days(reader: SheetReader) -> Decimal: return _value(reader, "debtor_days")
def creditor_days(reader: SheetReader) -> Decimal: return _value(reader, "creditor_days")


def finance_snapshot(reader: SheetReader) -> FinanceSnapshot:
    """Load Acuity's Google Sheets KPIs and charts."""
    return FinanceSnapshot(
        active_clients=active_clients(reader), active_contracts=active_contracts(reader),
        current_mrr=current_mrr(reader), current_arr=current_arr(reader),
        future_contracted_mrr=future_contracted_mrr(reader),
        future_contracted_arr=future_contracted_arr(reader),
        nrr_quarterly=nrr_quarterly(reader), grr_quarterly=grr_quarterly(reader),
        billing_by_entity=billing_by_entity(reader), billing_by_currency=billing_by_currency(reader),
        average_client_mrr=average_client_mrr(reader),
        average_contract_length=average_contract_length(reader),
        average_contract_length_all_time=average_contract_length_all_time(reader), clv=clv(reader),
        new_contracts=new_contracts(reader), cac=cac(reader),
        churned_clients_ytd=churned_clients_ytd(reader),
        churned_mrr_ytd=churned_mrr_ytd(reader),
        churned_clients_last_year=churned_clients_last_year(reader),
        churned_mrr_last_year=churned_mrr_last_year(reader), revenue=revenue(reader),
        gross_profit=gross_profit(reader), gross_margin=gross_margin(reader),
        net_profit=net_profit(reader), net_profit_margin=net_profit_margin(reader), ebitda=ebitda(reader),
        ebitda_margin=ebitda_margin(reader), rule_of_40=rule_of_40(reader), cash=cash(reader),
        debtor_days=debtor_days(reader), creditor_days=creditor_days(reader),
    )


def marketreader_snapshot(reader: SheetReader) -> MarketReaderSnapshot:
    """Load only the MarketReader metrics available in its USD billing blocks."""
    clients = _count(reader, "active_clients", True)
    mrr = _value(reader, "current_mrr", True)
    return MarketReaderSnapshot(
        active_clients=clients,
        active_contracts=_count(reader, "active_contracts", True),
        current_mrr=mrr,
        current_arr=_value(reader, "current_arr", True),
        future_contracted_mrr=_value(reader, "future_contracted_mrr", True),
        future_contracted_arr=_value(reader, "future_contracted_arr", True),
        average_client_mrr=mrr / Decimal(clients) if clients else Decimal(0),
    )


def load_finance_kpis(reader: SheetReader) -> FinanceSnapshot:
    """Compatibility name for loading the complete Acuity finance KPI set."""
    return finance_snapshot(reader)


class GoogleSheetsReader:
    """Google Sheets API implementation of :class:`SheetReader`.

    Imports are intentionally lazy so parsing and unit tests have no Google SDK
    dependency. Credentials are loaded from the Railway JSON environment
    variable, with a local credential-file fallback.
    """

    def __init__(
        self,
        spreadsheet_id: str,
        service_account_file: str | None = None,
        worksheet: str = LIVE_TOTALS_WORKSHEET,
    ) -> None:
        self.spreadsheet_id = spreadsheet_id
        self.service_account_file = service_account_file
        self.worksheet = worksheet
        self._worksheet_cache = None

    @classmethod
    def from_environment(cls) -> "GoogleSheetsReader":
        _load_dotenv()
        spreadsheet_id = os.environ.get("GOOGLE_SHEETS_ID")
        if not spreadsheet_id:
            raise FinanceDataError("Set GOOGLE_SHEETS_ID")
        return cls(spreadsheet_id)

    def worksheets(self) -> Mapping[str, Sequence[Row]]:
        if self._worksheet_cache is not None:
            return self._worksheet_cache
        try:
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise FinanceDataError(
                "Install google-api-python-client and google-auth to read Google Sheets"
            ) from exc
        if (
            self.service_account_file
            and not os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_B64")
            and not os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        ):
            os.environ.setdefault("GOOGLE_SERVICE_ACCOUNT_FILE", self.service_account_file)
        credentials = load_google_credentials()
        service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        escaped_title = self.worksheet.replace("'", "''")
        result = service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=f"'{escaped_title}'",
        ).execute()
        self._worksheet_cache = {self.worksheet: result.get("values", [])}
        return self._worksheet_cache

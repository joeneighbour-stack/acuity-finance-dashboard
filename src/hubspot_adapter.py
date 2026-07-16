"""Typed HubSpot deal and pipeline integration for the finance dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class HubSpotDataError(RuntimeError):
    pass


@dataclass(frozen=True)
class Deal:
    id: str
    name: str
    pipeline_id: str
    stage_id: str
    stage: str
    billing_entity: str
    tag_ids: Tuple[str, ...]
    cancellation_received: bool
    cancellation_date: Optional[date]
    arr: Decimal
    close_date: Optional[date]
    created_date: Optional[date]
    closed_won: bool


@dataclass(frozen=True)
class StagePoint:
    label: str
    count: int


@dataclass(frozen=True)
class PipelineStagePoint:
    label: str
    deal_count: int
    pipeline_value: Decimal
    weighted_value: Decimal


@dataclass(frozen=True)
class UpcomingRenewal:
    name: str
    close_date: date
    days_remaining: int
    stage: str
    arr: Decimal


@dataclass(frozen=True)
class CancellationRisk:
    name: str
    renewal_date: Optional[date]
    cancellation_date: Optional[date]
    stage: str
    arr: Decimal


@dataclass(frozen=True)
class HubSpotSnapshot:
    opportunities_created: int
    closed_won: int
    pipeline_value: Decimal
    weighted_pipeline: Decimal
    pipeline_stages: Tuple[PipelineStagePoint, ...]
    renewal_stages: Tuple[StagePoint, ...]
    upcoming_renewals: Tuple[UpcomingRenewal, ...]
    cancellation_risks: Tuple[CancellationRisk, ...]


RETAIL_PIPELINE_ID = "40364427"
RETAIL_WEIGHTED_STAGES = {
    "85248585": ("Negotiation", Decimal("0.50")),
    "85248583": ("Verbally Agreed", Decimal("0.60")),
    "85248584": ("Contract Out", Decimal("0.70")),
}

# Account-specific pipeline IDs. Keeping these explicit prevents similarly
# named entity pipelines from ever being selected by fuzzy/user-facing labels.
ACUITY_RENEWAL_PIPELINE_ID = "85559454"       # Renewal Pipeline
MARKETREADER_RENEWAL_PIPELINE_ID = "907190335"  # MR-Renewal-Pipeline
ACUITY_RENEWAL_STAGE_IDS = (
    "247553603",  # >6 Months Until Renewal
    "247553604",  # 6-4 Months Until Renewal
    "247553605",  # <4 Months Until Renewal
    "247553606",  # <30 Days Until Renewal
)
CANCELLATION_RECEIVED_TAG_ID = "19599895"


def _stage_weight(label: str) -> Decimal:
    normalised = label.casefold().split("(", 1)[0].strip()
    for stage, weight in (item for item in RETAIL_WEIGHTED_STAGES.values()):
        if normalised == stage.casefold():
            return weight
    return Decimal(0)


def _weighted_retail_deals(deals: Sequence[Deal]) -> List[Deal]:
    return [
        deal for deal in deals
        if deal.pipeline_id == RETAIL_PIPELINE_ID and deal.stage_id in RETAIL_WEIGHTED_STAGES
    ]


def _is_marketreader(deal: Deal) -> bool:
    """Identify MarketReader records even when stored in a shared pipeline."""
    entity = deal.billing_entity.casefold().replace(" ", "")
    return entity == "marketreader" or "marketreader" in deal.name.casefold()


def _load_dotenv() -> None:
    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value or "0").replace(",", ""))
    except InvalidOperation:
        return Decimal(0)


def _date(value: object) -> Optional[date]:
    if not value:
        return None
    text = str(value)
    try:
        if text.isdigit():
            return datetime.fromtimestamp(int(text) / 1000, tz=timezone.utc).date()
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except (ValueError, OSError):
        return None


def _financial_year_bounds(today: date) -> Tuple[date, date]:
    """Return the inclusive start and exclusive end of the Feb–Jan FY."""
    start_year = today.year if today.month >= 2 else today.year - 1
    return date(start_year, 2, 1), date(start_year + 1, 2, 1)


class HubSpotReader:
    base_url = "https://api.hubapi.com"

    def __init__(self, access_token: str) -> None:
        self.access_token = access_token
        self._pipelines = None
        self._deals = None

    @classmethod
    def from_environment(cls) -> "HubSpotReader":
        _load_dotenv()
        token = os.environ.get("HUBSPOT_ACCESS_TOKEN")
        if not token:
            raise HubSpotDataError("Set HUBSPOT_ACCESS_TOKEN in .env")
        return cls(token)

    def _get(self, path: str, params: Optional[Mapping[str, object]] = None) -> dict:
        url = self.base_url + path
        if params:
            url += "?" + urlencode(params, doseq=True)
        request = Request(url, headers={
            "Authorization": "Bearer " + self.access_token,
            "Accept": "application/json",
        })
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                message = json.loads(body).get("message", body)
            except ValueError:
                message = body
            raise HubSpotDataError("HubSpot API error {0}: {1}".format(exc.code, message))
        except URLError as exc:
            raise HubSpotDataError("Could not connect to HubSpot: {0}".format(exc.reason))

    def pipelines(self) -> Mapping[str, dict]:
        if self._pipelines is None:
            data = self._get("/crm/v3/pipelines/deals")
            self._pipelines = {item["id"]: item for item in data.get("results", [])}
        return self._pipelines

    def _pipeline_id(self, label: str) -> str:
        wanted = label.casefold().strip()
        matches = [pid for pid, item in self.pipelines().items() if item.get("label", "").casefold().strip() == wanted]
        if not matches:
            available = ", ".join(sorted(item.get("label", pid) for pid, item in self.pipelines().items()))
            raise HubSpotDataError("Pipeline {0!r} not found. Available: {1}".format(label, available))
        return matches[0]

    def deals(self) -> Tuple[Deal, ...]:
        if self._deals is not None:
            return self._deals
        stage_names: Dict[Tuple[str, str], str] = {}
        won_stages = set()
        for pipeline_id, pipeline in self.pipelines().items():
            for stage in pipeline.get("stages", []):
                stage_names[(pipeline_id, stage["id"])] = stage.get("label", stage["id"])
                if stage.get("metadata", {}).get("isClosed") == "true" and "won" in stage.get("label", "").casefold():
                    won_stages.add((pipeline_id, stage["id"]))
        results: List[Deal] = []
        after = None
        properties = [
            "dealname", "pipeline", "dealstage", "acuity_billing_entity",
            "hs_tag_ids", "cancellation_received_", "cancellation_date",
            "amount", "hs_arr", "renewal_date", "closedate", "createdate",
        ]
        while True:
            params = {"limit": 100, "properties": properties, "archived": "false"}
            if after:
                params["after"] = after
            page = self._get("/crm/v3/objects/deals", params)
            for item in page.get("results", []):
                props = item.get("properties", {})
                pipeline_id = props.get("pipeline", "")
                stage_id = props.get("dealstage", "")
                results.append(Deal(
                    id=item["id"], name=props.get("dealname") or "Unnamed deal",
                    pipeline_id=pipeline_id, stage_id=stage_id,
                    stage=stage_names.get((pipeline_id, stage_id), stage_id),
                    billing_entity=props.get("acuity_billing_entity") or "",
                    tag_ids=tuple(filter(None, (props.get("hs_tag_ids") or "").split(";"))),
                    cancellation_received=(props.get("cancellation_received_") == "Yes"),
                    cancellation_date=_date(props.get("cancellation_date")),
                    arr=_decimal(props.get("hs_arr") or props.get("amount")),
                    # Renewal Pipeline reporting uses its dedicated date field.
                    # closedate remains a fallback for older/other deals.
                    close_date=_date(props.get("renewal_date") or props.get("closedate")),
                    created_date=_date(props.get("createdate")),
                    closed_won=(pipeline_id, stage_id) in won_stages,
                ))
            after = page.get("paging", {}).get("next", {}).get("after")
            if not after:
                break
        self._deals = tuple(results)
        return self._deals

    def snapshot(self, today: Optional[date] = None) -> HubSpotSnapshot:
        today = today or date.today()
        financial_year_start, financial_year_end = _financial_year_bounds(today)
        retail_id = RETAIL_PIPELINE_ID
        if retail_id not in self.pipelines():
            raise HubSpotDataError("Retail Pipeline (40364427) is unavailable")
        renewal_id = ACUITY_RENEWAL_PIPELINE_ID
        renewal_pipeline = self.pipelines().get(renewal_id)
        if not renewal_pipeline or renewal_pipeline.get("label") != "Renewal Pipeline":
            raise HubSpotDataError("Acuity Renewal Pipeline (85559454) is unavailable or was renamed")
        retail = [deal for deal in self.deals() if deal.pipeline_id == retail_id]
        renewals = [
            deal for deal in self.deals()
            if deal.pipeline_id == renewal_id
            and deal.pipeline_id != MARKETREADER_RENEWAL_PIPELINE_ID
            and deal.stage_id in ACUITY_RENEWAL_STAGE_IDS
            and not _is_marketreader(deal)
        ]
        open_retail = _weighted_retail_deals(retail)
        pipeline_stages = []
        for stage_id, (label, weight) in RETAIL_WEIGHTED_STAGES.items():
            stage_deals = [deal for deal in open_retail if deal.stage_id == stage_id]
            value = sum((deal.arr for deal in stage_deals), Decimal(0))
            pipeline_stages.append(PipelineStagePoint(label, len(stage_deals), value, value * weight))
        weighted = sum((stage.weighted_value for stage in pipeline_stages), Decimal(0))
        upcoming: List[UpcomingRenewal] = []
        stage_labels = {
            "247553603": "> 6 months", "247553604": "4–6 months",
            "247553605": "30 days–4 months", "247553606": "< 30 days",
        }
        buckets = {label: 0 for label in stage_labels.values()}
        for deal in renewals:
            buckets[stage_labels[deal.stage_id]] += 1
            if not deal.close_date:
                continue
            days = (deal.close_date - today).days
            if days < 0:
                continue
            if days <= 90:
                upcoming.append(UpcomingRenewal(deal.name, deal.close_date, days, deal.stage, deal.arr))
        cancellation_risks = tuple(
            CancellationRisk(deal.name, deal.close_date, deal.cancellation_date, deal.stage, deal.arr)
            for deal in renewals
            if deal.cancellation_received or CANCELLATION_RECEIVED_TAG_ID in deal.tag_ids
        )
        return HubSpotSnapshot(
            opportunities_created=sum(
                1 for deal in retail
                if deal.created_date and financial_year_start <= deal.created_date < financial_year_end
            ),
            closed_won=sum(
                1 for deal in retail
                if deal.closed_won and deal.close_date
                and financial_year_start <= deal.close_date < financial_year_end
            ),
            pipeline_value=sum((deal.arr for deal in open_retail), Decimal(0)),
            weighted_pipeline=weighted,
            pipeline_stages=tuple(pipeline_stages),
            renewal_stages=tuple(StagePoint(label, count) for label, count in buckets.items()),
            upcoming_renewals=tuple(sorted(upcoming, key=lambda item: item.close_date)),
            cancellation_risks=tuple(sorted(cancellation_risks, key=lambda item: item.renewal_date or date.max)),
        )


def hubspot_snapshot(reader: Optional[HubSpotReader] = None) -> HubSpotSnapshot:
    return (reader or HubSpotReader.from_environment()).snapshot()

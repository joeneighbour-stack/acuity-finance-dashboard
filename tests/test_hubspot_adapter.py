from decimal import Decimal
from datetime import date
import unittest

from src.hubspot_adapter import (
    ACUITY_RENEWAL_PIPELINE_ID, MARKETREADER_RENEWAL_PIPELINE_ID, Deal,
    ACUITY_RENEWAL_STAGE_IDS, CANCELLATION_RECEIVED_TAG_ID,
    HubSpotDataError, HubSpotReader, RETAIL_PIPELINE_ID, _date,
    _financial_year_bounds, _historical_comparison_values, _is_marketreader,
    _live_pipeline_values, _open_retail_deals, _same_point_prior_fy_period,
    _stage_weight, _weighted_retail_deals,
)


class SearchReader(HubSpotReader):
    def __init__(self, responses):
        super().__init__("test-token")
        self._pipelines = {
            RETAIL_PIPELINE_ID: {
                "id": RETAIL_PIPELINE_ID,
                "label": "Retail Pipeline",
                "stages": [
                    {"id": "won", "label": "Customer", "metadata": {"isClosed": "true", "probability": "1.0"}},
                    {"id": "lost", "label": "Closed lost", "metadata": {"isClosed": "true", "probability": "0.0"}},
                    {"id": "open", "label": "Negotiation", "metadata": {"isClosed": "false", "probability": "0.5"}},
                ],
            }
        }
        self.responses = list(responses)
        self.search_payloads = []

    def _post(self, path, payload):
        self.assert_search_path = path
        self.search_payloads.append(payload)
        return self.responses.pop(0)


class HubSpotAdapterTests(unittest.TestCase):
    @staticmethod
    def pipeline_deal(
        identifier, pipeline_id=RETAIL_PIPELINE_ID, closed=False,
        probability="0.5", amount="100", stage_id="85248585",
    ):
        return Deal(
            id=identifier, name="Deal " + identifier, pipeline_id=pipeline_id,
            stage_id=stage_id, stage="Stage", billing_entity="Acuity", tag_ids=(),
            cancellation_received=False, cancellation_date=None, arr=Decimal(amount),
            close_date=None, created_date=None, closed_won=False, closed=closed,
            stage_probability=Decimal(probability),
        )

    def test_live_stage_label_probabilities(self):
        self.assertEqual(_stage_weight("Trial (10%)"), Decimal("0"))
        self.assertEqual(_stage_weight("Trial Extension (20%)"), Decimal("0"))
        self.assertEqual(_stage_weight("Evaluation (30%)"), Decimal("0"))
        self.assertEqual(_stage_weight("Verbally Agreed (60%)"), Decimal("0.60"))
        self.assertEqual(_stage_weight("Closed Lost (0%)"), Decimal(0))

    def test_entity_renewal_pipelines_are_distinct(self):
        self.assertEqual(ACUITY_RENEWAL_PIPELINE_ID, "85559454")
        self.assertEqual(MARKETREADER_RENEWAL_PIPELINE_ID, "907190335")
        self.assertNotEqual(ACUITY_RENEWAL_PIPELINE_ID, MARKETREADER_RENEWAL_PIPELINE_ID)

    def test_marketreader_deals_are_excluded_inside_shared_pipeline(self):
        common = dict(id="1", pipeline_id=ACUITY_RENEWAL_PIPELINE_ID, stage_id="stage",
                      stage="Renewal", tag_ids=(), cancellation_received=False,
                      cancellation_date=None, arr=Decimal("100"), close_date=None,
                      created_date=None, closed_won=False)
        self.assertTrue(_is_marketreader(Deal(name="Real Vision", billing_entity="MarketReader", **common)))
        self.assertTrue(_is_marketreader(Deal(name="Client - MarketReader", billing_entity="", **common)))
        self.assertFalse(_is_marketreader(Deal(name="Acuity Client", billing_entity="Acuity Trading", **common)))

    def test_renewal_scope_is_limited_to_requested_stages(self):
        self.assertEqual(ACUITY_RENEWAL_STAGE_IDS, (
            "247553603", "247553604", "247553605", "247553606",
        ))
        self.assertEqual(CANCELLATION_RECEIVED_TAG_ID, "19599895")

    def test_financial_year_runs_february_to_january(self):
        self.assertEqual(_financial_year_bounds(date(2026, 7, 10)),
                         (date(2026, 2, 1), date(2027, 2, 1)))
        self.assertEqual(_financial_year_bounds(date(2027, 1, 15)),
                         (date(2026, 2, 1), date(2027, 2, 1)))

    def test_hubspot_iso_dates_are_parsed(self):
        self.assertEqual(_date("2026-07-10T12:30:00.000Z"), date(2026, 7, 10))

    def test_weighted_pipeline_uses_only_three_requested_stages(self):
        def deal(stage_id):
            return Deal(id=stage_id, name="Deal", pipeline_id=RETAIL_PIPELINE_ID,
                        stage_id=stage_id, stage="Stage", billing_entity="Acuity",
                        tag_ids=(), cancellation_received=False, cancellation_date=None,
                        arr=Decimal("100"), close_date=None, created_date=None, closed_won=False)
        deals = [deal(stage) for stage in ("85248585", "85248583", "85248584", "trial", "evaluation")]
        self.assertEqual([item.stage_id for item in _weighted_retail_deals(deals)],
                         ["85248585", "85248583", "85248584"])

    def test_retail_pipeline_filter_excludes_every_other_pipeline(self):
        reader = SearchReader([{"results": [{"id": "retail-deal"}]}])
        self.assertEqual(reader.count_retail_deals("createdate", date(2026, 2, 1), date(2026, 7, 18)), 1)
        filters = reader.search_payloads[0]["filterGroups"][0]["filters"]
        pipeline_filter = next(item for item in filters if item["propertyName"] == "pipeline")
        self.assertEqual(pipeline_filter, {"propertyName": "pipeline", "operator": "EQ", "value": RETAIL_PIPELINE_ID})

    def test_retail_pipeline_results_are_included(self):
        reader = SearchReader([{"results": [{"id": "1"}, {"id": "2"}]}])
        self.assertEqual(reader.count_retail_deals("createdate", date(2026, 2, 1), date(2026, 7, 18)), 2)

    def test_created_date_filter_is_utc_and_end_exclusive(self):
        reader = SearchReader([{"results": []}])
        reader.count_retail_deals("createdate", date(2026, 2, 1), date(2026, 7, 18))
        filters = reader.search_payloads[0]["filterGroups"][0]["filters"]
        self.assertIn({"propertyName": "createdate", "operator": "GTE", "value": "1769904000000"}, filters)
        self.assertIn({"propertyName": "createdate", "operator": "LT", "value": "1784332800000"}, filters)

    def test_close_date_and_closed_won_stage_filters(self):
        reader = SearchReader([{"results": []}])
        won_stages = reader.retail_closed_won_stage_ids(RETAIL_PIPELINE_ID)
        self.assertEqual(won_stages, ("won",))
        reader.count_retail_deals(
            "closedate", date(2026, 2, 1), date(2026, 7, 18),
            closed_won_stage_ids=won_stages,
        )
        filters = reader.search_payloads[0]["filterGroups"][0]["filters"]
        self.assertTrue(any(item["propertyName"] == "closedate" for item in filters))
        self.assertIn({"propertyName": "dealstage", "operator": "IN", "values": ["won"]}, filters)

    def test_same_point_prior_fy_ranges(self):
        period = _same_point_prior_fy_period(date(2026, 7, 17))
        self.assertEqual((period.current_start, period.current_end), (date(2026, 2, 1), date(2026, 7, 17)))
        self.assertEqual((period.prior_start, period.prior_end), (date(2025, 2, 1), date(2025, 7, 17)))

    def test_financial_year_crossing_calendar_year(self):
        period = _same_point_prior_fy_period(date(2027, 1, 15))
        self.assertEqual(period.current_start, date(2026, 2, 1))
        self.assertEqual(period.current_end, date(2027, 1, 15))
        self.assertEqual(period.prior_start, date(2025, 2, 1))
        self.assertEqual(period.prior_end, date(2026, 1, 15))

    def test_leap_year_preserves_elapsed_calendar_days(self):
        period = _same_point_prior_fy_period(date(2024, 2, 29))
        self.assertEqual((period.current_end - period.current_start).days, 28)
        self.assertEqual((period.prior_end - period.prior_start).days, 28)
        self.assertEqual(period.prior_end, date(2023, 3, 1))

    def test_prior_period_zero_is_a_valid_count(self):
        reader = SearchReader([{"results": []}])
        self.assertEqual(reader.count_retail_deals("createdate", date(2025, 2, 1), date(2025, 7, 18)), 0)

    def test_missing_comparison_results_are_an_error(self):
        reader = SearchReader([{}])
        with self.assertRaisesRegex(HubSpotDataError, "no results collection"):
            reader.count_retail_deals("createdate", date(2025, 2, 1), date(2025, 7, 18))

    def test_search_pagination_is_fully_consumed(self):
        reader = SearchReader([
            {"results": [{"id": "1"}, {"id": "2"}], "paging": {"next": {"after": "next-page"}}},
            {"results": [{"id": "3"}]},
        ])
        self.assertEqual(reader.count_retail_deals("createdate", date(2026, 2, 1), date(2026, 7, 18)), 3)
        self.assertEqual(reader.search_payloads[1]["after"], "next-page")

    def test_open_pipeline_excludes_closed_and_non_retail_deals(self):
        deals = [
            self.pipeline_deal("open"),
            self.pipeline_deal("won", closed=True, probability="1"),
            self.pipeline_deal("lost", closed=True, probability="0"),
            self.pipeline_deal("other", pipeline_id="another-pipeline"),
            self.pipeline_deal("untracked-stage", stage_id="trial"),
        ]
        self.assertEqual([deal.id for deal in _open_retail_deals(deals)], ["open"])

    def test_open_pipeline_value_uses_all_open_retail_deals(self):
        deals = [
            self.pipeline_deal("one", amount="100"),
            self.pipeline_deal("two", amount="250"),
            self.pipeline_deal("closed", closed=True, amount="999"),
        ]
        pipeline_value, _ = _live_pipeline_values(deals)
        self.assertEqual(pipeline_value, Decimal("350"))

    def test_weighted_pipeline_uses_current_stage_probabilities(self):
        deals = [
            self.pipeline_deal("one", amount="100", probability="0.25"),
            self.pipeline_deal("two", amount="200", probability="0.6"),
            self.pipeline_deal("closed", closed=True, amount="999", probability="1"),
        ]
        _, weighted_value = _live_pipeline_values(deals)
        self.assertEqual(weighted_value, Decimal("145.00"))

    def test_historical_reconstruction_path_accepts_complete_values(self):
        result = _historical_comparison_values((Decimal("500"), Decimal("250")))
        self.assertEqual(result, (Decimal("500"), Decimal("250"), True))

    def test_historical_comparison_unavailable_without_complete_history(self):
        self.assertEqual(_historical_comparison_values(None), (None, None, False))


if __name__ == "__main__": unittest.main()

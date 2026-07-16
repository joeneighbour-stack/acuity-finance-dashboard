from decimal import Decimal
from datetime import date
import unittest

from src.hubspot_adapter import (
    ACUITY_RENEWAL_PIPELINE_ID, MARKETREADER_RENEWAL_PIPELINE_ID, Deal,
    ACUITY_RENEWAL_STAGE_IDS, CANCELLATION_RECEIVED_TAG_ID,
    RETAIL_PIPELINE_ID, _date, _financial_year_bounds, _is_marketreader,
    _stage_weight, _weighted_retail_deals,
)


class HubSpotAdapterTests(unittest.TestCase):
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


if __name__ == "__main__": unittest.main()

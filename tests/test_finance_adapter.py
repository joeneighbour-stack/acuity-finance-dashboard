from decimal import Decimal
import unittest

from src.finance_adapter import (
    LIVE_TOTALS_WORKSHEET, ChartPoint, GoogleSheetsReader, active_clients,
    billing_by_entity, current_mrr, grr_quarterly, marketreader_snapshot,
    nrr_quarterly,
)


class FakeReader:
    def worksheets(self):
        return {"Finance": [
            ["Current Billing"], ["Client count (Current)", "12"],
            ["Current Monthly Billing", "£10,250.50"], [],
            ["Billing split per entity"], ["Entity table"],
            ["Entity", "GBP equivalent"], ["Acuity", "£8,000"],
            ["MarketReader", "£2,250.50"],
        ]}


class FinanceAdapterTests(unittest.TestCase):
    def setUp(self): self.reader = FakeReader()

    def test_typed_kpis(self):
        self.assertEqual(active_clients(self.reader), 12)
        self.assertEqual(current_mrr(self.reader), Decimal("10250.50"))

    def test_chart_dataset(self):
        self.assertEqual(billing_by_entity(self.reader), (
            ChartPoint("Acuity", Decimal("8000")),
            ChartPoint("MarketReader", Decimal("2250.50")),
        ))

    def test_quarterly_retention_percentages(self):
        class RetentionReader:
            def worksheets(self):
                return {"LIVE Totals": [
                    ["NRR (Net Revenue Retention) % Q", "94%"],
                    ["GRR (Gross Revenue Retention) % Q", "92%"],
                ]}
        self.assertEqual(nrr_quarterly(RetentionReader()), Decimal("94"))
        self.assertEqual(grr_quarterly(RetentionReader()), Decimal("92"))

    def test_missing_quarterly_retention_is_none(self):
        self.assertIsNone(nrr_quarterly(self.reader))
        self.assertIsNone(grr_quarterly(self.reader))

    def test_google_reader_defaults_to_live_totals_only(self):
        reader = GoogleSheetsReader("sheet-id", "credentials.json")
        self.assertEqual(reader.worksheet, LIVE_TOTALS_WORKSHEET)

    def test_marketreader_is_not_merged_with_acuity(self):
        class PairedReader:
            def worksheets(self):
                return {"LIVE Totals": [
                    ["Current Billing"],
                    ["Client count (Current)", "10", "", "", "Client count (Current)", "3"],
                    ["Contract count (Current)", "11", "", "", "Contract count (Current)", "4"],
                    ["Current Monthly Billing", "1000", "", "", "Current Monthly Billing", "600"],
                    ["ARR (GBP) after cancelled revenue", "12000", "", "", "ARR (GBP) after cancelled revenue", "7200"],
                    ["MRR (GBP) incl future ramp ups", "1100", "", "", "MRR (GBP) incl future ramp ups", "650"],
                    ["ARR (GBP) incl future ramp ups", "13200", "", "", "ARR (GBP) incl future ramp ups", "7800"],
                ]}
        reader = PairedReader()
        self.assertEqual(active_clients(reader), 10)
        self.assertEqual(current_mrr(reader), Decimal("1000"))
        marketreader = marketreader_snapshot(reader)
        self.assertEqual(marketreader.active_clients, 3)
        self.assertEqual(marketreader.current_mrr, Decimal("600"))


if __name__ == "__main__": unittest.main()

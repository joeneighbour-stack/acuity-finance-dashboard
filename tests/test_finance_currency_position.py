from __future__ import annotations

import unittest
from decimal import Decimal

import pandas as pd

from src import finance_metrics


def sample_live_totals() -> pd.DataFrame:
    return pd.DataFrame({
        finance_metrics.METRIC_COLUMN: [
            "Billing split per currency",
            "GBP",
            "USD",
            "EUR",
            "",
        ],
        "Column 2": [
            "MRR (Currency)",
            "75,750",
            "140,739",
            "147,631",
            "",
        ],
        "Column 3": [
            "MRR (GBP)",
            "75,750",
            "104,237",
            "122,482",
            "",
        ],
        "Column 4": ["", "25%", "34%", "40%", ""],
        "Column 5": ["", "", "", "", ""],
        "Column 6": [
            "Current cost requirements",
            "210,530",
            "52,452",
            "102,824",
            "",
        ],
        "Column 7": [
            "Currency Shortage/Excess",
            "-134,780",
            "88,287",
            "44,807",
            "",
        ],
    })


class FinanceCurrencyPositionTests(unittest.TestCase):
    def test_currency_requirement_mapping(self) -> None:
        rows = finance_metrics._billing_split_currency_rows(sample_live_totals())
        requirements = dict(zip(rows["currency"], rows["monthly_requirements"]))

        self.assertEqual(requirements["GBP"], Decimal("210530"))
        self.assertEqual(requirements["USD"], Decimal("52452"))
        self.assertEqual(requirements["EUR"], Decimal("102824"))

    def test_currency_position_mapping(self) -> None:
        rows = finance_metrics._billing_split_currency_rows(sample_live_totals())
        positions = dict(zip(rows["currency"], rows["net_position"]))

        self.assertEqual(positions["GBP"], Decimal("-134780"))
        self.assertEqual(positions["USD"], Decimal("88287"))
        self.assertEqual(positions["EUR"], Decimal("44807"))

    def test_currency_symbol_formatting(self) -> None:
        self.assertEqual(finance_metrics.format_native_currency(123456, "GBP"), "\N{POUND SIGN}123,456")
        self.assertEqual(finance_metrics.format_native_currency(123456, "USD"), "$123,456")
        self.assertEqual(finance_metrics.format_native_currency(123456, "EUR"), "\N{EURO SIGN}123,456")

    def test_position_label(self) -> None:
        self.assertEqual(finance_metrics.position_label(100), "Surplus")
        self.assertEqual(finance_metrics.position_label(-100), "Shortage")
        self.assertEqual(finance_metrics.position_label(0), "Balanced")

    def test_missing_values_are_safe(self) -> None:
        data = sample_live_totals()
        data.loc[1, "Column 6"] = ""
        data.loc[1, "Column 7"] = ""

        rows = finance_metrics._billing_split_currency_rows(data)
        gbp_row = rows.loc[rows["currency"].eq("GBP")].iloc[0]

        self.assertTrue(pd.isna(gbp_row["monthly_requirements"]))
        self.assertTrue(pd.isna(gbp_row["net_position"]))
        self.assertEqual(finance_metrics.format_native_currency(None, "GBP"), "N/A")


if __name__ == "__main__":
    unittest.main()

from datetime import date
from decimal import Decimal
import unittest
from unittest.mock import patch

from src.kpi_comparisons import (
    calculate_variance,
    format_snapshot_month,
    format_variance,
    get_kpi_comparison_config,
    get_latest_completed_snapshot,
)


class KPIComparisonTests(unittest.TestCase):
    def test_positive_movement(self):
        variance = calculate_variance(Decimal("108"), Decimal("100"))
        self.assertEqual(variance.absolute_change, Decimal("8"))
        self.assertEqual(variance.percentage_change, Decimal("8"))
        self.assertEqual(format_variance(108, 100, "currency"), "▲ +£8 (+8.0%)")

    def test_negative_movement(self):
        variance = calculate_variance(90.0, 100)
        self.assertEqual(variance.absolute_change, Decimal("-10.0"))
        self.assertEqual(variance.percentage_change, Decimal("-10.0"))
        self.assertEqual(format_variance(90, 100, "count"), "▼ -10 (-10.0%)")

    def test_no_movement(self):
        self.assertEqual(format_variance(10, 10, "count"), "— 0 (0.0%)")

    def test_previous_value_zero_has_no_percentage_change(self):
        variance = calculate_variance(5, 0)
        self.assertEqual(variance.absolute_change, Decimal("5"))
        self.assertIsNone(variance.percentage_change)
        self.assertEqual(format_variance(5, 0, "count"), "▲ +5")
        self.assertEqual(format_variance(Decimal("125.4"), 0, "currency"), "▲ +£125")

    def test_missing_current_value(self):
        self.assertEqual(calculate_variance(None, 10), (None, None))
        self.assertEqual(format_variance(None, 10, "currency"), "No prior-month comparison")

    def test_missing_previous_value(self):
        self.assertEqual(calculate_variance(10, None), (None, None))
        self.assertEqual(format_variance(10, None, "currency"), "No prior-month comparison")

    def test_percentage_point_metric(self):
        self.assertEqual(
            format_variance(Decimal("72.4"), Decimal("73.6"), "percentage"),
            "▼ -1.2 percentage points",
        )

    @patch("src.kpi_comparisons.get_monthly_snapshots")
    def test_latest_completed_snapshot_selection(self, read_snapshots):
        read_snapshots.return_value = [
            {"snapshot_month": "2026-04", "entity": "Acuity"},
            {"snapshot_month": "2026-06", "entity": "Acuity"},
            {"snapshot_month": "2026-05", "entity": "Acuity"},
        ]
        result = get_latest_completed_snapshot("Acuity", today=date(2026, 7, 17))
        self.assertEqual(result["snapshot_month"], "2026-06")
        read_snapshots.assert_called_once_with("Acuity")

    @patch("src.kpi_comparisons.get_monthly_snapshots")
    def test_current_month_snapshot_is_excluded(self, read_snapshots):
        read_snapshots.return_value = [
            {"snapshot_month": "2026-06", "entity": "MarketReader"},
            {"snapshot_month": "2026-07", "entity": "MarketReader"},
        ]
        result = get_latest_completed_snapshot("MarketReader", today=date(2026, 7, 17))
        self.assertEqual(result["snapshot_month"], "2026-06")

    @patch("src.kpi_comparisons.get_monthly_snapshots", return_value=[])
    def test_no_completed_snapshot(self, _read_snapshots):
        self.assertIsNone(get_latest_completed_snapshot("Acuity", today=date(2026, 7, 17)))

    def test_snapshot_month_format(self):
        self.assertEqual(format_snapshot_month("2026-06"), "Jun 2026")

    def test_comparison_frequency_metadata(self):
        self.assertEqual(get_kpi_comparison_config("current_mrr").comparison_frequency, "monthly")
        self.assertEqual(get_kpi_comparison_config("nrr_quarterly").comparison_frequency, "quarterly")
        self.assertEqual(get_kpi_comparison_config("weighted_pipeline").comparison_frequency, "none")
        self.assertEqual(get_kpi_comparison_config("unregistered_operational_kpi").comparison_frequency, "none")

    def test_monthly_metadata_contains_snapshot_mapping(self):
        future_mrr = get_kpi_comparison_config("future_contracted_mrr")
        revenue = get_kpi_comparison_config("revenue")
        self.assertEqual(future_mrr.snapshot_field, "future_mrr")
        self.assertEqual(revenue.snapshot_field, "total_income")


if __name__ == "__main__":
    unittest.main()

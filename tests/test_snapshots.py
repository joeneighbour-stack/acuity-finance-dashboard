from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

import src.snapshots as snapshots


@dataclass
class KPIs:
    active_clients: int
    active_contracts: int = 2
    current_mrr: Decimal = Decimal("100")
    current_arr: Decimal = Decimal("1200")
    future_contracted_mrr: Decimal = Decimal("110")
    future_contracted_arr: Decimal = Decimal("1320")
    nrr_quarterly: Decimal = Decimal("94")
    grr_quarterly: Decimal = Decimal("92")


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_path = snapshots.DATABASE_PATH
        snapshots.DATABASE_PATH = Path(self.temp.name) / "dashboard.db"
        snapshots.initialize_database()

    def tearDown(self):
        snapshots.DATABASE_PATH = self.original_path
        self.temp.cleanup()

    def test_insert_and_update_same_month(self):
        month = snapshots.save_monthly_snapshot("Acuity", KPIs(10))
        self.assertTrue(snapshots.snapshot_exists(month, "Acuity"))
        snapshots.save_monthly_snapshot("Acuity", KPIs(15))
        rows = snapshots.get_monthly_snapshots("Acuity")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["active_clients"], 15)

    def test_entities_are_stored_separately(self):
        snapshots.save_monthly_snapshot("Acuity", KPIs(10))
        snapshots.save_monthly_snapshot("MarketReader", KPIs(3))
        self.assertEqual(len(snapshots.get_monthly_snapshots()), 2)
        self.assertEqual(snapshots.get_monthly_snapshots("MarketReader")[0]["active_clients"], 3)


if __name__ == "__main__": unittest.main()

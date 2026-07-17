from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import os
from pathlib import Path
import tempfile
import unittest

from sqlalchemy import create_mock_engine
from sqlalchemy.dialects import postgresql

import src.snapshots as snapshots
from scripts.capture_monthly_snapshot import previous_month


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
        self.original_url = os.environ.pop("DATABASE_URL", None)
        self.original_railway_environment = os.environ.pop("RAILWAY_ENVIRONMENT", None)
        snapshots.DATABASE_PATH = Path(self.temp.name) / "dashboard.db"
        snapshots.reset_engine_for_tests()
        snapshots.initialize_database()

    def tearDown(self):
        snapshots.reset_engine_for_tests()
        snapshots.DATABASE_PATH = self.original_path
        os.environ.pop("RAILWAY_ENVIRONMENT", None)
        if self.original_url is not None:
            os.environ["DATABASE_URL"] = self.original_url
        if self.original_railway_environment is not None:
            os.environ["RAILWAY_ENVIRONMENT"] = self.original_railway_environment
        self.temp.cleanup()

    def test_postgresql_payload_generation(self):
        payload = snapshots.build_snapshot_payload(
            "Acuity", KPIs(10), snapshot_month="2026-06", snapshot_date=date(2026, 7, 1)
        )
        self.assertEqual(payload["snapshot_month"], "2026-06")
        self.assertEqual(payload["entity"], "Acuity")
        self.assertEqual(payload["future_mrr"], Decimal("110"))
        self.assertEqual(payload["current_arr"], Decimal("1200"))

    def test_postgresql_upsert_uses_month_and_entity_conflict_key(self):
        payload = snapshots.build_snapshot_payload("Acuity", KPIs(10), snapshot_month="2026-06")
        engine = create_mock_engine("postgresql+psycopg://", lambda *args, **kwargs: None)
        sql = str(snapshots._upsert_statement(engine, payload).compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": False}
        ))
        self.assertIn("ON CONFLICT (snapshot_month, entity) DO UPDATE", sql)

    def test_upsert_updates_same_month(self):
        snapshots.save_monthly_snapshot("Acuity", KPIs(10), snapshot_month="2026-06")
        snapshots.save_monthly_snapshot("Acuity", KPIs(15), snapshot_month="2026-06")
        rows = snapshots.get_monthly_snapshots("Acuity")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["active_clients"], 15)

    def test_entities_are_stored_separately(self):
        snapshots.save_monthly_snapshot("Acuity", KPIs(10), snapshot_month="2026-06")
        snapshots.save_monthly_snapshot("MarketReader", KPIs(3), snapshot_month="2026-06")
        self.assertEqual(len(snapshots.get_monthly_snapshots()), 2)
        self.assertEqual(snapshots.get_monthly_snapshots("MarketReader")[0]["active_clients"], 3)

    def test_empty_historical_results(self):
        self.assertEqual(snapshots.get_monthly_snapshots("Acuity"), [])

    def test_previous_month_naming(self):
        self.assertEqual(previous_month(date(2026, 1, 10)), "2025-12")
        self.assertEqual(previous_month(date(2026, 7, 16)), "2026-06")

    def test_railway_requires_database_url(self):
        os.environ["RAILWAY_ENVIRONMENT"] = "production"
        with self.assertRaisesRegex(RuntimeError, "DATABASE_URL"):
            snapshots._database_url()


if __name__ == "__main__":
    unittest.main()

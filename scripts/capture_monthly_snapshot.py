"""Capture separate Acuity and MarketReader snapshots for the previous month."""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.finance_adapter import GoogleSheetsReader, finance_snapshot, marketreader_snapshot
from src.snapshots import save_monthly_snapshot, snapshot_exists


def previous_month(today: date | None = None) -> str:
    today = today or date.today()
    return (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")


def capture(force: bool = False) -> int:
    month = previous_month()
    entities = ("Acuity", "MarketReader")
    if not force and all(snapshot_exists(month, entity) for entity in entities):
        print("Snapshots already exist for {}. Nothing to do.".format(month))
        return 0

    print("Loading LIVE Totals metrics for {}...".format(month))
    reader = GoogleSheetsReader.from_environment()
    acuity = finance_snapshot(reader)
    marketreader = marketreader_snapshot(reader)
    for entity, metrics, syft in (
        ("Acuity", acuity, acuity),
        ("MarketReader", marketreader, None),
    ):
        if not force and snapshot_exists(month, entity):
            print("Skipping {}: snapshot already exists.".format(entity))
            continue
        save_monthly_snapshot(entity, metrics, syft, snapshot_month=month)
        print("Saved {} snapshot for {}.".format(entity, month))
    print("Snapshot capture complete.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Upsert snapshots even when they already exist")
    return capture(force=parser.parse_args().force)


if __name__ == "__main__":
    raise SystemExit(main())

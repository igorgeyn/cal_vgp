"""Read-only production gate for registrar identity compatibility.

This script replays the immutable San Bernardino production snapshots and
compares the selected snapshot's IDs with the reviewed IDs already loaded in
the database.  It never opens the database and never writes to R2.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SCRAPER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRAPER_ROOT))

from src.scrapers.registrar.parser import parse_election  # noqa: E402
from src.scrapers.registrar.storage import make_store  # noqa: E402


COUNTY = "sb"
ELECTION_DATE = "2026-11-03"
REQUIRED_SNAPSHOT_COUNT = 5
EXPECTED_IDS_PATH = (
    SCRAPER_ROOT
    / "tests"
    / "fixtures"
    / "registrar"
    / "sb"
    / "production_measure_ids_20260828.json"
)


def main() -> int:
    expected_ids = sorted(json.loads(EXPECTED_IDS_PATH.read_text(encoding="utf-8")))
    if len(expected_ids) != 20 or len(set(expected_ids)) != 20:
        raise RuntimeError("identity fixture must contain exactly 20 unique IDs")

    store = make_store(env="prod")
    snapshots = store.list_snapshots(county=COUNTY, election_date=ELECTION_DATE)
    if len(snapshots) < REQUIRED_SNAPSHOT_COUNT:
        raise RuntimeError(
            f"expected at least {REQUIRED_SNAPSHOT_COUNT} production snapshots, "
            f"found {len(snapshots)}: {snapshots}"
        )
    required_snapshots = snapshots[:REQUIRED_SNAPSHOT_COUNT]

    with tempfile.TemporaryDirectory(prefix="registrar-identity-") as temp_dir:
        report = parse_election(
            store,
            county=COUNTY,
            election_date=ELECTION_DATE,
            snapshot_id=required_snapshots[-1],
            output_path=Path(temp_dir) / "normalized.jsonl",
        )

    actual_ids = sorted(record["measure"]["measure_id"] for record in report.records)
    if actual_ids != expected_ids:
        missing = sorted(set(expected_ids) - set(actual_ids))
        unexpected = sorted(set(actual_ids) - set(expected_ids))
        raise RuntimeError(
            "production registrar identity drift: "
            f"missing={missing}, unexpected={unexpected}"
        )
    if report.snapshots_replayed != REQUIRED_SNAPSHOT_COUNT:
        raise RuntimeError(
            f"parser replayed {report.snapshots_replayed} snapshots, expected "
            f"{REQUIRED_SNAPSHOT_COUNT}"
        )

    print(
        json.dumps(
            {
                "county": COUNTY,
                "election_date": ELECTION_DATE,
                "snapshot_ids": required_snapshots,
                "production_snapshot_count": len(snapshots),
                "snapshots_replayed": report.snapshots_replayed,
                "measure_ids": actual_ids,
                "status": "byte-identical",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

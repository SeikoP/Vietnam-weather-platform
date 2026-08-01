"""Backfill hourly wind direction through the existing ETL pipeline.

Examples:
    poetry run python scripts/backfill_wind_direction.py
    poetry run python scripts/backfill_wind_direction.py \
        --start-date 2026-07-01 --end-date 2026-07-31
    poetry run python scripts/backfill_wind_direction.py --district-id 1 --district-id 3
    poetry run python scripts/backfill_wind_direction.py --publish-r2
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

HISTORICAL_START_DATE = date(2023, 6, 1)
VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


@dataclass(frozen=True)
class BackfillOptions:
    start_date: date
    end_date: date
    district_ids: tuple[int, ...]
    max_districts: int | None
    request_delay_seconds: float
    publish_r2: bool


def parse_args(argv: list[str] | None = None) -> BackfillOptions:
    parser = argparse.ArgumentParser(description="Backfill Open-Meteo hourly wind direction")
    parser.add_argument("--start-date", type=date.fromisoformat, default=HISTORICAL_START_DATE)
    parser.add_argument(
        "--end-date",
        type=date.fromisoformat,
        default=datetime.now(VIETNAM_TZ).date() - timedelta(days=1),
    )
    parser.add_argument("--district-id", action="append", type=int, default=[])
    parser.add_argument("--max-districts", type=int)
    parser.add_argument("--request-delay-seconds", type=float, default=10.0)
    parser.add_argument(
        "--publish-r2",
        action="store_true",
        help="Force-republish the repaired date range to R2 after the database backfill",
    )
    args = parser.parse_args(argv)
    if args.start_date > args.end_date:
        parser.error("--start-date must be before or equal to --end-date")
    if args.max_districts is not None and args.max_districts < 1:
        parser.error("--max-districts must be greater than 0")
    if args.request_delay_seconds < 0:
        parser.error("--request-delay-seconds must be 0 or greater")
    return BackfillOptions(
        start_date=args.start_date,
        end_date=args.end_date,
        district_ids=tuple(args.district_id),
        max_districts=args.max_districts,
        request_delay_seconds=args.request_delay_seconds,
        publish_r2=args.publish_r2,
    )


def build_commands(
    options: BackfillOptions,
    *,
    python_executable: str = sys.executable,
) -> list[list[str]]:
    commands = [[python_executable, "-m", "alembic", "upgrade", "head"]]
    etl_command = [
        python_executable,
        "-m",
        "src.etl.cli",
        "--run-type",
        "historical-hourly",
        "--start-date",
        options.start_date.isoformat(),
        "--end-date",
        options.end_date.isoformat(),
        "--request-delay-seconds",
        str(options.request_delay_seconds),
    ]
    for district_id in options.district_ids:
        etl_command.extend(("--district-id", str(district_id)))
    if options.max_districts is not None:
        etl_command.extend(("--max-districts", str(options.max_districts)))
    commands.append(etl_command)

    if options.publish_r2:
        commands.append(
            [
                python_executable,
                "scripts/publish_r2_release.py",
                "--start-date",
                options.start_date.isoformat(),
                "--end-date",
                options.end_date.isoformat(),
                "--force-republish",
            ]
        )
    return commands


def main(argv: list[str] | None = None) -> int:
    options = parse_args(argv)
    for command in build_commands(options):
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

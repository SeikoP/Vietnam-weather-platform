import subprocess
import sys
from datetime import date

from scripts.backfill_wind_direction import BackfillOptions, build_commands


def test_build_commands_reuses_hourly_etl_and_can_republish_repaired_r2_range() -> None:
    commands = build_commands(
        BackfillOptions(
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 2),
            district_ids=(1, 3),
            max_districts=None,
            request_delay_seconds=7.0,
            publish_r2=True,
        ),
        python_executable="python",
    )

    assert commands == [
        ["python", "-m", "alembic", "upgrade", "head"],
        [
            "python",
            "-m",
            "src.etl.cli",
            "--run-type",
            "historical-hourly",
            "--start-date",
            "2026-07-01",
            "--end-date",
            "2026-07-02",
            "--request-delay-seconds",
            "7.0",
            "--district-id",
            "1",
            "--district-id",
            "3",
        ],
        [
            "python",
            "scripts/publish_r2_release.py",
            "--start-date",
            "2026-07-01",
            "--end-date",
            "2026-07-02",
            "--force-republish",
        ],
    ]


def test_build_commands_can_limit_districts_without_publishing_r2() -> None:
    commands = build_commands(
        BackfillOptions(
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 1),
            district_ids=(),
            max_districts=2,
            request_delay_seconds=0.0,
            publish_r2=False,
        ),
        python_executable="python",
    )

    assert commands[-1][-2:] == ["--max-districts", "2"]
    assert len(commands) == 2


def test_etl_module_entrypoint_invokes_cli_parser() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "src.etl.cli", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "historical-hourly" in result.stdout

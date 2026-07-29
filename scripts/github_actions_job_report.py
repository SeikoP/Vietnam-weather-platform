"""Write one credential-safe timing report for a GitHub Actions job."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def build_job_report(
    *,
    job_id: str,
    display_name: str,
    status: str,
    started_at: datetime,
    finished_at: datetime,
) -> dict[str, object]:
    start_utc = started_at.astimezone(UTC)
    finish_utc = finished_at.astimezone(UTC)
    return {
        "job_id": job_id,
        "display_name": display_name,
        "status": status,
        "started_at_utc": start_utc.isoformat(),
        "finished_at_utc": finish_utc.isoformat(),
        "started_at_vietnam": _display_vietnam(start_utc),
        "finished_at_vietnam": _display_vietnam(finish_utc),
        "duration_seconds": max(0, int((finish_utc - start_utc).total_seconds())),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write GitHub Actions job timing report")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--status", required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    report = build_job_report(
        job_id=args.job_id,
        display_name=args.display_name,
        status=args.status,
        started_at=_parse_datetime(args.started_at),
        finished_at=datetime.now(UTC),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return 0


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _display_vietnam(value: datetime) -> str:
    return value.astimezone(VIETNAM_TZ).strftime("%d/%m/%Y %H:%M:%S (UTC+7)")


if __name__ == "__main__":
    raise SystemExit(main())


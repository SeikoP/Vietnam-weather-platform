from datetime import UTC, datetime

from scripts.github_actions_job_report import build_job_report


def test_job_report_calculates_duration_and_vietnam_times() -> None:
    report = build_job_report(
        job_id="collect-daily",
        display_name="Thu thập thời tiết daily",
        status="success",
        started_at=datetime(2026, 7, 29, 18, 0, tzinfo=UTC),
        finished_at=datetime(2026, 7, 29, 18, 1, 35, tzinfo=UTC),
    )

    assert report["duration_seconds"] == 95
    assert report["started_at_vietnam"] == "30/07/2026 01:00:00 (UTC+7)"
    assert report["finished_at_vietnam"] == "30/07/2026 01:01:35 (UTC+7)"


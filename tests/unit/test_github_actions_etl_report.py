from datetime import UTC, datetime

from scripts.github_actions_etl_report import _manual_catchup, _render_markdown


def test_scheduled_failure_includes_manual_catchup_commands(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")

    catchup = _manual_catchup(
        job_status="failure",
        started_at=datetime(2026, 7, 9, 19, 15, tzinfo=UTC),
        rows=[],
        error=None,
    )

    assert catchup is not None
    assert catchup["date"] == "2026-07-09"
    assert catchup["commands"] == [
        ".\\scripts\\run_manual_catchup.ps1 -StartDate 2026-07-09 -EndDate 2026-07-09"
    ]


def test_manual_dispatch_does_not_request_manual_catchup(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")

    catchup = _manual_catchup(
        job_status="failure",
        started_at=datetime(2026, 7, 9, 19, 15, tzinfo=UTC),
        rows=[],
        error=None,
    )

    assert catchup is None


def test_render_markdown_shows_manual_catchup_section(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    catchup = _manual_catchup(
        job_status="failure",
        started_at=datetime(2026, 7, 9, 19, 15, tzinfo=UTC),
        rows=[],
        error=None,
    )

    markdown = _render_markdown(
        job_status="failure",
        started_at=datetime(2026, 7, 9, 19, 15, tzinfo=UTC),
        rows=[],
        warehouse={},
        error=None,
        manual_catchup=catchup,
    )

    assert "Manual catch-up required" in markdown
    assert "Missing date: `2026-07-09`" in markdown
    assert ".\\scripts\\run_manual_catchup.ps1" in markdown

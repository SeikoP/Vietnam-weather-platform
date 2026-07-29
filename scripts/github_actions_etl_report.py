"""Build GitHub Actions ETL summary and optional Discord notification."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
from sqlalchemy import text

from src.database.session import SessionLocal

VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
SCHEDULED_RUN_TYPES = (
    "incremental-daily",
    "incremental-hourly",
    "incremental-aqi-hourly",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Report ETL workflow status")
    parser.add_argument("--job-status", default=os.getenv("JOB_STATUS", "unknown"))
    parser.add_argument("--notify-discord", action="store_true")
    parser.add_argument("--job-reports-dir", type=Path)
    parser.add_argument("--r2-result", type=Path)
    args = parser.parse_args()

    summary = _build_summary(
        args.job_status,
        job_reports=_load_job_reports(args.job_reports_dir),
        r2_result=_load_json(args.r2_result),
    )
    _append_step_summary(summary["markdown"])

    if args.notify_discord:
        _notify_discord(summary, args.job_status)

    return 0


def _build_summary(
    job_status: str,
    *,
    job_reports: list[dict[str, Any]] | None = None,
    r2_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    started_at = _workflow_started_at()
    if job_reports:
        started_at = min(
            datetime.fromisoformat(report["started_at_utc"]) for report in job_reports
        )
    rows: list[dict[str, Any]] = []
    warehouse: dict[str, dict[str, Any]] = {}
    error: str | None = None

    try:
        with SessionLocal() as session:
            rows = _recent_etl_runs(session, started_at)
            warehouse = _warehouse_snapshot(session)
    except Exception as exc:
        error = _safe_error(exc)

    manual_catchup = _manual_catchup(job_status, started_at, rows, error)
    markdown = _render_markdown(
        job_status=job_status,
        started_at=started_at,
        rows=rows,
        warehouse=warehouse,
        error=error,
        manual_catchup=manual_catchup,
        job_reports=job_reports,
        r2_result=r2_result,
    )
    return {
        "job_status": job_status,
        "started_at": started_at,
        "rows": rows,
        "warehouse": warehouse,
        "error": error,
        "manual_catchup": manual_catchup,
        "job_reports": job_reports or [],
        "r2_result": r2_result,
        "markdown": markdown,
    }


def _workflow_started_at() -> datetime:
    raw = os.getenv("WORKFLOW_STARTED_AT")
    if not raw:
        return datetime.now(UTC) - timedelta(hours=6)
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC) - timedelta(hours=6)


def _recent_etl_runs(session, started_at: datetime) -> list[dict[str, Any]]:
    result = session.execute(
        text(
            """
            select
                etl_run_id,
                run_type,
                status,
                started_at,
                finished_at,
                rows_inserted,
                rows_updated,
                rows_skipped,
                error_summary
            from monitoring.etl_runs
            where started_at >= :started_at
            order by etl_run_id
            """
        ),
        {"started_at": started_at},
    )
    return [dict(row._mapping) for row in result]


def _warehouse_snapshot(session) -> dict[str, dict[str, Any]]:
    queries = {
        "Daily weather": """
            select count(*) as total_rows, max(observed_date)::text as latest_value
            from analyst.fact_weather_daily
        """,
        "Hourly weather": """
            select count(*) as total_rows, max(hour.observed_at)::text as latest_value
            from analyst.fact_weather_hourly fact
            join analyst.dim_hour hour on hour.hour_key = fact.hour_key
        """,
        "Hourly AQI": """
            select count(*) as total_rows, max(hour.observed_at)::text as latest_value
            from analyst.fact_aqi_hourly fact
            join analyst.dim_hour hour on hour.hour_key = fact.hour_key
        """,
    }
    snapshot: dict[str, dict[str, Any]] = {}
    for label, query in queries.items():
        row = session.execute(text(query)).mappings().one()
        snapshot[label] = {
            "total_rows": row["total_rows"],
            "latest_value": row["latest_value"] or "-",
        }
    return snapshot


def _render_markdown(
    job_status: str,
    started_at: datetime,
    rows: list[dict[str, Any]],
    warehouse: dict[str, dict[str, Any]],
    error: str | None,
    manual_catchup: dict[str, Any] | None = None,
    job_reports: list[dict[str, Any]] | None = None,
    r2_result: dict[str, Any] | None = None,
) -> str:
    lines = [
        "# Báo cáo ETL thời tiết hằng ngày",
        "",
        f"- Trạng thái workflow: `{job_status}`",
        f"- Bắt đầu: `{_display_dt(started_at)}`",
        f"- Sự kiện: `{os.getenv('GITHUB_EVENT_NAME', '-')}`",
        f"- Nhánh: `{os.getenv('GITHUB_REF_NAME', '-')}`",
        f"- Người chạy: `{os.getenv('GITHUB_ACTOR', '-')}`",
        "",
    ]

    if job_reports:
        lines.extend(
            [
                "## Thời gian từng phần",
                "",
                "| Bước | Trạng thái | Bắt đầu | Kết thúc | Thời lượng |",
                "| --- | --- | --- | --- | ---: |",
            ]
        )
        for report in job_reports:
            lines.append(
                "| {display_name} | `{status}` | {started_at_vietnam} | "
                "{finished_at_vietnam} | {duration_seconds}s |".format(**report)
            )
        lines.append("")

    if error:
        lines.extend(
            [
                "### Verification error",
                "",
                f"`{error}`",
                "",
            ]
        )
        if manual_catchup:
            lines.extend(_render_manual_catchup_markdown(manual_catchup))
        return "\n".join(lines)

    lines.extend(
        [
            "### ETL runs created by this workflow",
            "",
            "| Run ID | Run type | Status | Rows upserted | Skipped | Started | Finished |",
            "| --- | --- | --- | ---: | ---: | --- | --- |",
        ]
    )
    if rows:
        for row in rows:
            lines.append(
                "| {etl_run_id} | `{run_type}` | `{status}` | {rows_inserted} | "
                "{rows_skipped} | {started_at} | {finished_at} |".format(
                    etl_run_id=row["etl_run_id"],
                    run_type=row["run_type"],
                    status=row["status"],
                    rows_inserted=row["rows_inserted"],
                    rows_skipped=row["rows_skipped"],
                    started_at=_display_dt(row["started_at"]),
                    finished_at=_display_dt(row["finished_at"]),
                )
            )
    else:
        lines.append("| - | - | No ETL run found for this workflow window | - | - | - | - |")

    zero_rows = [
        row for row in rows if row["status"] == "completed" and row["rows_inserted"] == 0
    ]
    failed_rows = [row for row in rows if row["status"] != "completed"]
    if zero_rows or failed_rows:
        lines.extend(["", "### Attention"])
        if zero_rows:
            names = ", ".join(f"`{row['run_type']}`" for row in zero_rows)
            lines.append(f"- Completed with zero upserted rows: {names}")
        if failed_rows:
            names = ", ".join(f"`{row['run_type']}`" for row in failed_rows)
            lines.append(f"- Non-completed ETL runs: {names}")

    if manual_catchup:
        lines.extend([""])
        lines.extend(_render_manual_catchup_markdown(manual_catchup))

    lines.extend(
        [
            "",
            "### Warehouse snapshot after workflow",
            "",
            "| Table | Total rows | Latest date/time |",
            "| --- | ---: | --- |",
        ]
    )
    for label, data in warehouse.items():
        lines.append(f"| {label} | {data['total_rows']} | `{data['latest_value']}` |")

    if r2_result:
        lines.extend(
            [
                "",
                "### Release Cloudflare R2",
                "",
                f"- Trạng thái: `{r2_result.get('status', '-')}`",
                f"- Bucket: `{r2_result.get('bucket', '-')}`",
                f"- Release: `{r2_result.get('release_id', '-')}`",
                f"- Thời gian Việt Nam: `{r2_result.get('generated_at_vietnam', '-')}`",
            ]
        )

    lines.append("")
    return "\n".join(lines)


def _manual_catchup(
    job_status: str,
    started_at: datetime,
    rows: list[dict[str, Any]],
    error: str | None,
) -> dict[str, Any] | None:
    event_name = os.getenv("GITHUB_EVENT_NAME", "")
    if event_name != "schedule":
        return None

    failed_rows = [row for row in rows if row["status"] != "completed"]
    needs_catchup = job_status != "success" or bool(error) or bool(failed_rows) or not rows
    if not needs_catchup:
        return None

    target_date = _catchup_date(started_at)
    return {
        "date": target_date,
        "run_types": SCHEDULED_RUN_TYPES,
        "commands": _manual_catchup_commands(target_date),
    }


def _catchup_date(started_at: datetime) -> str:
    local_started_at = started_at.astimezone(VIETNAM_TZ)
    return (local_started_at.date() - timedelta(days=1)).isoformat()


def _manual_catchup_commands(target_date: str) -> list[str]:
    return [
        (
            ".\\scripts\\run_manual_catchup.ps1 "
            f"-StartDate {target_date} -EndDate {target_date}"
        )
    ]


def _render_manual_catchup_markdown(manual_catchup: dict[str, Any]) -> list[str]:
    lines = [
        "### Manual catch-up required",
        "",
        (
            "Scheduled ETL did not complete. Run the following command from a local "
            "PowerShell terminal at the repository root to fill the missing date."
        ),
        "",
        f"- Missing date: `{manual_catchup['date']}`",
        "",
        "```powershell",
    ]
    lines.extend(manual_catchup["commands"])
    lines.extend(["```", ""])
    return lines


def _display_dt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, datetime):
        return value.astimezone(VIETNAM_TZ).strftime("%d/%m/%Y %H:%M:%S (UTC+7)")
    return str(value)


def _load_job_reports(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    reports = []
    for file_path in path.rglob("*.json"):
        payload = _load_json(file_path)
        if payload and "job_id" in payload:
            reports.append(payload)
    return sorted(reports, key=lambda item: item["started_at_utc"])


def _load_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_error(exc: Exception) -> str:
    return type(exc).__name__


def _append_step_summary(markdown: str) -> None:
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        print(markdown)
        return
    with Path(summary_path).open("a", encoding="utf-8") as file:
        file.write(markdown)
        file.write("\n")


def _notify_discord(summary: dict[str, Any], job_status: str) -> None:
    enabled = os.getenv("DISCORD_NOTIFICATIONS_ENABLED", "false").lower() == "true"
    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if not enabled or not webhook:
        return

    repo = os.getenv("GITHUB_REPOSITORY", "repository")
    run_id = os.getenv("GITHUB_RUN_ID", "")
    run_url = f"https://github.com/{repo}/actions/runs/{run_id}" if run_id else "-"
    status_label = "[OK]" if job_status == "success" else "[FAILED]"
    rows = summary["rows"]
    total_rows = sum(row["rows_inserted"] for row in rows)
    run_types = ", ".join(row["run_type"] for row in rows) or "No ETL run recorded"

    content = (
        f"{status_label} **VWDP ETL workflow: {job_status}**\n"
        f"Run types: `{run_types}`\n"
        f"Rows upserted: `{total_rows}`\n"
        f"Workflow: {run_url}"
    )
    if summary["error"]:
        content += f"\nVerification error: `{summary['error']}`"
    manual_catchup = summary.get("manual_catchup")
    if manual_catchup:
        commands = "\n".join(manual_catchup["commands"])
        content += (
            f"\n\nManual catch-up required for `{manual_catchup['date']}`. "
            "Run locally from repo root:\n"
            f"```powershell\n{commands}\n```"
        )

    response = requests.post(webhook, json={"content": content}, timeout=10)
    response.raise_for_status()


if __name__ == "__main__":
    raise SystemExit(main())

"""Build GitHub Actions ETL summary and optional Discord notification."""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from sqlalchemy import text

from src.database.session import SessionLocal


def main() -> int:
    parser = argparse.ArgumentParser(description="Report ETL workflow status")
    parser.add_argument("--job-status", default=os.getenv("JOB_STATUS", "unknown"))
    parser.add_argument("--notify-discord", action="store_true")
    args = parser.parse_args()

    summary = _build_summary(args.job_status)
    _append_step_summary(summary["markdown"])

    if args.notify_discord:
        _notify_discord(summary, args.job_status)

    return 0


def _build_summary(job_status: str) -> dict[str, Any]:
    started_at = _workflow_started_at()
    rows: list[dict[str, Any]] = []
    warehouse: dict[str, dict[str, Any]] = {}
    error: str | None = None

    try:
        with SessionLocal() as session:
            rows = _recent_etl_runs(session, started_at)
            warehouse = _warehouse_snapshot(session)
    except Exception as exc:
        error = str(exc)

    markdown = _render_markdown(
        job_status=job_status,
        started_at=started_at,
        rows=rows,
        warehouse=warehouse,
        error=error,
    )
    return {
        "job_status": job_status,
        "started_at": started_at,
        "rows": rows,
        "warehouse": warehouse,
        "error": error,
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
) -> str:
    lines = [
        "## ETL run summary",
        "",
        f"- Workflow status: `{job_status}`",
        f"- Workflow started at: `{started_at.isoformat()}`",
        f"- Event: `{os.getenv('GITHUB_EVENT_NAME', '-')}`",
        f"- Ref: `{os.getenv('GITHUB_REF_NAME', '-')}`",
        f"- Actor: `{os.getenv('GITHUB_ACTOR', '-')}`",
        "",
    ]

    if error:
        lines.extend(
            [
                "### Verification error",
                "",
                f"`{error}`",
                "",
            ]
        )
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

    lines.append("")
    return "\n".join(lines)


def _display_dt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


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

    response = requests.post(webhook, json={"content": content}, timeout=10)
    response.raise_for_status()


if __name__ == "__main__":
    raise SystemExit(main())

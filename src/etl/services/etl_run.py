"""ETL Run tracking service."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.database.models import EtlLog, EtlRun, ValidationError


class EtlRunService:
    """Manages ETL run lifecycle and logging."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def start_run(
        self,
        run_type: str,
    ) -> int:
        """Start a new ETL run and return its ID."""
        etl_run = EtlRun(
            run_type=run_type,
            status="running",
            started_at=datetime.now(timezone.utc),
            rows_inserted=0,
            rows_updated=0,
            rows_skipped=0,
        )
        self._session.add(etl_run)
        self._session.flush()
        return etl_run.etl_run_id

    def complete_run(
        self,
        etl_run_id: int,
        status: str,
        rows_inserted: int,
        rows_updated: int,
        rows_skipped: int,
        error_summary: str | None = None,
    ) -> None:
        """Mark an ETL run as complete."""
        etl_run = self._session.query(EtlRun).filter_by(etl_run_id=etl_run_id).first()
        if etl_run:
            etl_run.status = status
            etl_run.finished_at = datetime.now(timezone.utc)
            etl_run.rows_inserted = rows_inserted
            etl_run.rows_updated = rows_updated
            etl_run.rows_skipped = rows_skipped
            etl_run.error_summary = error_summary

    def log(
        self,
        etl_run_id: int,
        level: str,
        event_name: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Log an event for an ETL run."""
        etl_log = EtlLog(
            etl_run_id=etl_run_id,
            level=level,
            event_name=event_name,
            message=message,
            context=context or {},
        )
        self._session.add(etl_log)

    def store_validation_error(
        self,
        etl_run_id: int,
        source_table: str,
        province_id: int | None,
        field_name: str,
        invalid_value: str | None,
        reason: str,
        severity: str,
    ) -> None:
        """Store a validation error for tracking."""
        validation_error = ValidationError(
            etl_run_id=etl_run_id,
            source_table=source_table,
            province_id=province_id,
            field_name=field_name,
            invalid_value=invalid_value,
            reason=reason,
            severity=severity,
        )
        self._session.add(validation_error)

"""ETL Run tracking service."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.database.models import EtlLog, EtlRun, ValidationError


class EtlRunService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def start_run(self, run_type: str) -> int:
        etl_run = EtlRun(
            run_type=run_type,
            status="running",
            started_at=datetime.now(UTC),
            rows_inserted=0,
            rows_updated=0,
            rows_skipped=0,
        )
        self._session.add(etl_run)
        self._session.flush()
        return etl_run.etl_run_id

    def complete_run(
        self, etl_run_id, status, rows_inserted, rows_updated, rows_skipped, error_summary=None
    ):
        etl_run = self._session.query(EtlRun).filter_by(etl_run_id=etl_run_id).first()
        if etl_run:
            etl_run.status = status
            etl_run.finished_at = datetime.now(UTC)
            etl_run.rows_inserted = rows_inserted
            etl_run.rows_updated = rows_updated
            etl_run.rows_skipped = rows_skipped
            etl_run.error_summary = error_summary

    def log(self, etl_run_id, level, event_name, message, context=None):
        self._session.add(
            EtlLog(
                etl_run_id=etl_run_id,
                level=level,
                event_name=event_name,
                message=message,
                context=context or {},
            )
        )

    def store_validation_error(
        self, etl_run_id, source_table, district_id, field_name, invalid_value, reason, severity
    ):
        self._session.add(
            ValidationError(
                etl_run_id=etl_run_id,
                source_table=source_table,
                district_id=district_id,
                field_name=field_name,
                invalid_value=invalid_value,
                reason=reason,
                severity=severity,
            )
        )

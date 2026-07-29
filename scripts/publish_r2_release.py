"""Publish missing or explicitly repaired Supabase data as an R2 release."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine

from src.r2.config import R2Config
from src.r2.models import ReleaseManifest
from src.r2.publisher import R2Publisher, create_r2_client
from src.r2.service import WarehouseReleaseService

VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def default_target_date(now: datetime | None = None) -> date:
    value = datetime.now(UTC) if now is None else now
    return value.astimezone(VIETNAM_TZ).date() - timedelta(days=1)


def create_service(
    database_url: str,
    config: R2Config,
    batch_size: int,
) -> tuple[WarehouseReleaseService, R2Publisher, Any]:
    engine = create_engine(database_url, pool_pre_ping=True)
    publisher = R2Publisher(create_r2_client(config), config.bucket_name)
    return (
        WarehouseReleaseService(engine, publisher, batch_size=batch_size),
        publisher,
        engine,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish a Supabase warehouse release to R2")
    parser.add_argument("--target-date", type=date.fromisoformat)
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--force-republish", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--batch-size", type=int, default=5_000)
    parser.add_argument("--result-json", type=Path)
    args = parser.parse_args(argv)

    stage = "configuration"
    engine: Any | None = None
    try:
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            raise ValueError("DATABASE_URL is required")
        config = R2Config.from_env()
        service, publisher, engine = create_service(database_url, config, args.batch_size)
        stage = "bucket verification"
        publisher.verify_bucket()

        if args.verify_only:
            stage = "release verification"
            _, manifest, _ = publisher.read_latest()
            publisher.verify_release(manifest)
            result = _result("verified", config.bucket_name, manifest)
        else:
            stage = "incremental publish"
            target = args.target_date or args.end_date or default_target_date()
            manifest = service.publish_incremental(
                target_date=target,
                start_date=args.start_date,
                end_date=args.end_date,
                force_republish=args.force_republish,
            )
            result = (
                {"status": "noop", "bucket": config.bucket_name, "target_date": target.isoformat()}
                if manifest is None
                else _result("published", config.bucket_name, manifest)
            )

        _write_result(args.result_json, result)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(
            f"R2 publish failed at {stage}: {type(exc).__name__}",
            file=sys.stderr,
        )
        if stage == "configuration" and isinstance(exc, ValueError):
            print(str(exc), file=sys.stderr)
        return 1
    finally:
        if engine is not None and hasattr(engine, "dispose"):
            engine.dispose()


def _result(status: str, bucket: str, manifest: ReleaseManifest) -> dict[str, object]:
    return {
        "status": status,
        "bucket": bucket,
        "release_id": manifest.release_id,
        "generated_at_vietnam": manifest.generated_at_vietnam,
        "tables": {
            name: {
                "rows": table.row_count,
                "bytes": table.parquet_bytes + table.csv_bytes,
                "max_date": table.max_date,
            }
            for name, table in manifest.tables.items()
        },
    }


def _write_result(path: Path | None, result: dict[str, object]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())


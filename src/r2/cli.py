from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine

from src.r2.config import R2Config
from src.r2.models import ReleaseManifest
from src.r2.publisher import R2Publisher, create_r2_client
from src.r2.service import WarehouseReleaseService


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


def release_result(
    status: str,
    bucket: str,
    manifest: ReleaseManifest,
) -> dict[str, object]:
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


def write_result(path: Path | None, result: dict[str, object]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

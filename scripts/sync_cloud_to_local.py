"""Run a manual Supabase-to-local PostgreSQL synchronization."""

import argparse
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from sqlalchemy import create_engine

from src.sync.cloud_to_local import (
    CloudToLocalSync,
    SyncOptions,
    validate_distinct_databases,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Incrementally synchronize Supabase into local PostgreSQL."
    )
    parser.add_argument("--lookback-days", type=non_negative_int, default=3)
    parser.add_argument("--batch-size", type=positive_int, default=1000)
    parser.add_argument("--full", action="store_true")
    return parser.parse_args(argv)


def load_database_urls(environ: Mapping[str, str]) -> tuple[str, str]:
    cloud_url = environ.get("CLOUD_DATABASE_URL", "").strip()
    local_url = environ.get("LOCAL_DATABASE_URL", "").strip()
    if not cloud_url:
        raise ValueError("CLOUD_DATABASE_URL is required")
    if not local_url:
        raise ValueError("LOCAL_DATABASE_URL is required")
    return cloud_url, local_url


def run_local_migrations(local_url: str) -> None:
    child_environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"CLOUD_DATABASE_URL", "LOCAL_DATABASE_URL"}
    }
    child_environment["DATABASE_URL"] = local_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        cwd=REPOSITORY_ROOT,
        env=child_environment,
    )


def main(
    argv: Sequence[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> int:
    args = parse_args(argv)
    environment = os.environ if environ is None else environ
    cloud_engine = None
    local_engine = None

    try:
        cloud_url, local_url = load_database_urls(environment)
        validate_distinct_databases(cloud_url, local_url)
        run_local_migrations(local_url)

        cloud_engine = create_engine(cloud_url, pool_pre_ping=True)
        local_engine = create_engine(local_url, pool_pre_ping=True)
        service = CloudToLocalSync(
            cloud_engine=cloud_engine,
            local_engine=local_engine,
            options=SyncOptions(
                lookback_days=args.lookback_days,
                batch_size=args.batch_size,
                full=args.full,
            ),
        )
        results = service.run()
        for result in results:
            print(
                f"{result.table_name}: read={result.rows_read}, "
                f"upserted={result.rows_upserted}"
            )
        print(
            f"Total: read={sum(result.rows_read for result in results)}, "
            f"upserted={sum(result.rows_upserted for result in results)}"
        )
        return 0
    except Exception as exc:
        print(f"Synchronization failed ({type(exc).__name__}).", file=sys.stderr)
        return 1
    finally:
        if local_engine is not None:
            local_engine.dispose()
        if cloud_engine is not None:
            cloud_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())

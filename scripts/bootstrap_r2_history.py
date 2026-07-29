"""Bootstrap the complete local Hanoi warehouse into an immutable R2 release."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from src.r2.cli import create_service, release_result, write_result
from src.r2.config import R2Config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap local PostgreSQL history to R2")
    parser.add_argument("--batch-size", type=int, default=5_000)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--result-json", type=Path)
    args = parser.parse_args(argv)

    stage = "configuration"
    engine: Any | None = None
    try:
        database_url = os.getenv("LOCAL_DATABASE_URL", "").strip()
        if not database_url:
            raise ValueError("LOCAL_DATABASE_URL is required")
        config = R2Config.from_env()
        service, publisher, engine = create_service(database_url, config, args.batch_size)
        stage = "bucket verification"
        publisher.verify_bucket()

        if args.verify_only:
            stage = "release verification"
            _, manifest, _ = publisher.read_latest()
            publisher.verify_release(manifest)
            status = "verified"
        else:
            stage = "history bootstrap"
            manifest = service.bootstrap()
            status = "published"

        result = release_result(status, config.bucket_name, manifest)
        write_result(args.result_json, result)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(
            f"R2 bootstrap failed at {stage}: {type(exc).__name__}",
            file=sys.stderr,
        )
        if stage == "configuration" and isinstance(exc, ValueError):
            print(str(exc), file=sys.stderr)
        return 1
    finally:
        if engine is not None and hasattr(engine, "dispose"):
            engine.dispose()

if __name__ == "__main__":
    raise SystemExit(main())


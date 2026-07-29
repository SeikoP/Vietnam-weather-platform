from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import boto3

from src.r2.config import R2Config
from src.r2.exporter import ExportedTable
from src.r2.models import LatestPointer, ReleaseManifest, TableManifest

RELEASE_ID_PATTERN = re.compile(r"\d{8}T\d{6}Z\Z")


def _release_id_from_key(key: str) -> str | None:
    parts = key.split("/")
    if (
        len(parts) < 4
        or parts[0] != "v1"
        or parts[1] != "releases"
        or RELEASE_ID_PATTERN.fullmatch(parts[2]) is None
    ):
        return None
    return parts[2]


def create_r2_client(config: R2Config) -> Any:
    return boto3.client(
        service_name="s3",
        endpoint_url=config.endpoint_url,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
        region_name="auto",
    )


class R2Publisher:
    def __init__(self, client: Any, bucket_name: str) -> None:
        self.client = client
        self.bucket_name = bucket_name

    def verify_bucket(self) -> None:
        self.client.head_bucket(Bucket=self.bucket_name)

    def publish_release(
        self,
        *,
        release_id: str,
        source: str,
        generated_at: datetime,
        tables: dict[str, ExportedTable],
        expected_latest_etag: str | None,
    ) -> ReleaseManifest:
        prefix = f"v1/releases/{release_id}"
        table_manifests: dict[str, TableManifest] = {}
        for name, table in tables.items():
            parquet_key = f"{prefix}/analyst/{name}.parquet"
            csv_key = f"{prefix}/analyst/{name}.csv"
            self._upload_and_verify(
                table.parquet_path,
                parquet_key,
                table.parquet_bytes,
                table.parquet_sha256,
                "application/vnd.apache.parquet",
            )
            self._upload_and_verify(
                table.csv_path,
                csv_key,
                table.csv_bytes,
                table.csv_sha256,
                "text/csv; charset=utf-8",
            )
            table_manifests[name] = TableManifest(
                name=name,
                row_count=table.row_count,
                parquet_key=parquet_key,
                parquet_bytes=table.parquet_bytes,
                parquet_sha256=table.parquet_sha256,
                csv_key=csv_key,
                csv_bytes=table.csv_bytes,
                csv_sha256=table.csv_sha256,
                min_date=table.min_date,
                max_date=table.max_date,
            )

        manifest = ReleaseManifest.create(
            release_id=release_id,
            source=source,
            generated_at=generated_at,
            tables=table_manifests,
        )
        manifest_key = f"{prefix}/manifest.json"
        manifest_body = manifest.to_json().encode("utf-8")
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=manifest_key,
            Body=manifest_body,
            ContentType="application/json; charset=utf-8",
        )
        manifest_head = self.client.head_object(Bucket=self.bucket_name, Key=manifest_key)
        if manifest_head["ContentLength"] != len(manifest_body):
            raise RuntimeError("R2 manifest verification failed")

        self.publish_current_aliases(manifest)

        pointer = LatestPointer.create(release_id=release_id, generated_at=generated_at)
        pointer_kwargs: dict[str, str] = (
            {"IfMatch": expected_latest_etag}
            if expected_latest_etag is not None
            else {"IfNoneMatch": "*"}
        )
        self.client.put_object(
            Bucket=self.bucket_name,
            Key="v1/latest.json",
            Body=pointer.to_json().encode("utf-8"),
            ContentType="application/json; charset=utf-8",
            CacheControl="no-cache",
            **pointer_kwargs,
        )
        self.prune_releases(active_release_id=release_id, keep=3)
        return manifest

    def publish_current_aliases(self, manifest: ReleaseManifest) -> None:
        for table in manifest.tables.values():
            current_key = f"v1/current/analyst/{table.name}.csv"
            self.client.copy_object(
                Bucket=self.bucket_name,
                Key=current_key,
                CopySource={
                    "Bucket": self.bucket_name,
                    "Key": table.csv_key,
                },
                MetadataDirective="REPLACE",
                Metadata={
                    "release-id": manifest.release_id,
                    "sha256": table.csv_sha256,
                },
                ContentType="text/csv; charset=utf-8",
                CacheControl="no-cache",
            )
        self.verify_current_aliases(manifest)

    def verify_current_aliases(self, manifest: ReleaseManifest) -> None:
        for table in manifest.tables.values():
            current_key = f"v1/current/analyst/{table.name}.csv"
            head = self.client.head_object(Bucket=self.bucket_name, Key=current_key)
            if (
                head["ContentLength"] != table.csv_bytes
                or head.get("Metadata", {}).get("release-id") != manifest.release_id
                or head.get("Metadata", {}).get("sha256") != table.csv_sha256
            ):
                raise RuntimeError(f"R2 current CSV verification failed for {table.name}")

    def read_latest(self) -> tuple[LatestPointer, ReleaseManifest, str]:
        latest_object = self.client.get_object(Bucket=self.bucket_name, Key="v1/latest.json")
        pointer = LatestPointer.from_json(latest_object["Body"].read())
        manifest_object = self.client.get_object(
            Bucket=self.bucket_name,
            Key=pointer.manifest_key,
        )
        manifest = ReleaseManifest.from_json(manifest_object["Body"].read())
        return pointer, manifest, latest_object["ETag"]

    def download_parquet(self, table: TableManifest, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(
            self.bucket_name,
            table.parquet_key,
            str(destination),
        )

    def verify_release(self, manifest: ReleaseManifest) -> None:
        for table in manifest.tables.values():
            for key, expected_bytes, expected_sha256 in (
                (table.parquet_key, table.parquet_bytes, table.parquet_sha256),
                (table.csv_key, table.csv_bytes, table.csv_sha256),
            ):
                head = self.client.head_object(Bucket=self.bucket_name, Key=key)
                if (
                    head["ContentLength"] != expected_bytes
                    or head.get("Metadata", {}).get("sha256") != expected_sha256
                ):
                    raise RuntimeError(f"R2 object verification failed for {key}")
        self.verify_current_aliases(manifest)

    def prune_releases(self, *, active_release_id: str, keep: int = 3) -> None:
        if keep < 1:
            raise ValueError("keep must be positive")
        keys: list[str] = []
        continuation_token: str | None = None
        while True:
            kwargs: dict[str, Any] = {
                "Bucket": self.bucket_name,
                "Prefix": "v1/releases/",
            }
            if continuation_token is not None:
                kwargs["ContinuationToken"] = continuation_token
            page = self.client.list_objects_v2(**kwargs)
            keys.extend(item["Key"] for item in page.get("Contents", []))
            if not page.get("IsTruncated"):
                break
            continuation_token = page["NextContinuationToken"]

        keys_by_release: dict[str, list[str]] = {}
        for key in keys:
            release_id = _release_id_from_key(key)
            if release_id is not None:
                keys_by_release.setdefault(release_id, []).append(key)

        release_ids = sorted(keys_by_release, reverse=True)
        eligible = [release_id for release_id in release_ids if release_id <= active_release_id]
        retained = set(eligible[:keep])
        retained.add(active_release_id)
        deletable = set(eligible) - retained
        delete_keys = [
            key
            for release_id in deletable
            for key in keys_by_release[release_id]
        ]
        for offset in range(0, len(delete_keys), 1_000):
            batch = delete_keys[offset : offset + 1_000]
            self.client.delete_objects(
                Bucket=self.bucket_name,
                Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True},
            )

    def _upload_and_verify(
        self,
        path: Path,
        key: str,
        expected_bytes: int,
        expected_sha256: str,
        content_type: str,
    ) -> None:
        self.client.upload_file(
            str(path),
            self.bucket_name,
            key,
            ExtraArgs={
                "ContentType": content_type,
                "Metadata": {"sha256": expected_sha256},
            },
        )
        head = self.client.head_object(Bucket=self.bucket_name, Key=key)
        if (
            head["ContentLength"] != expected_bytes
            or head.get("Metadata", {}).get("sha256") != expected_sha256
        ):
            raise RuntimeError(f"R2 object verification failed for {key}")

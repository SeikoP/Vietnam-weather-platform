from __future__ import annotations

import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.r2.exporter import ExportedTable
from src.r2.publisher import R2Publisher


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.metadata: dict[str, dict[str, str]] = {}
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def upload_file(
        self,
        filename: str,
        bucket: str,
        key: str,
        ExtraArgs: dict[str, object] | None = None,
    ) -> None:
        self.objects[key] = Path(filename).read_bytes()
        self.metadata[key] = dict((ExtraArgs or {}).get("Metadata", {}))
        self.calls.append(("upload_file", key, ExtraArgs or {}))

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, **kwargs: object) -> dict:
        self.objects[Key] = Body
        self.metadata[Key] = dict(kwargs.get("Metadata", {}))
        self.calls.append(("put_object", Key, kwargs))
        return {"ETag": f'"etag-{len(self.calls)}"'}

    def head_object(self, *, Bucket: str, Key: str) -> dict:
        body = self.objects[Key]
        return {
            "ContentLength": len(body),
            "Metadata": self.metadata.get(Key, {}),
            "ETag": '"etag"',
        }

    def get_object(self, *, Bucket: str, Key: str) -> dict:
        return {"Body": io.BytesIO(self.objects[Key]), "ETag": '"etag"'}

    def copy_object(
        self,
        *,
        Bucket: str,
        Key: str,
        CopySource: dict[str, str],
        **kwargs: object,
    ) -> dict:
        source_key = CopySource["Key"]
        self.objects[Key] = self.objects[source_key]
        self.metadata[Key] = dict(kwargs.get("Metadata", {}))
        self.calls.append(("copy_object", Key, kwargs))
        return {"CopyObjectResult": {"ETag": '"etag"'}}

    def list_objects_v2(self, *, Bucket: str, Prefix: str, **kwargs: object) -> dict:
        return {
            "Contents": [
                {"Key": key}
                for key in sorted(self.objects)
                if key.startswith(Prefix)
            ],
            "IsTruncated": False,
        }

    def delete_objects(self, *, Bucket: str, Delete: dict) -> dict:
        for item in Delete["Objects"]:
            self.objects.pop(item["Key"], None)
        return {}


def _exported_table(tmp_path: Path, name: str) -> ExportedTable:
    parquet = tmp_path / f"{name}.parquet"
    csv = tmp_path / f"{name}.csv"
    parquet.write_bytes(b"parquet")
    csv.write_bytes(b"id\n1\n")
    return ExportedTable(
        name=name,
        parquet_path=parquet,
        csv_path=csv,
        row_count=1,
        parquet_bytes=parquet.stat().st_size,
        parquet_sha256=hashlib.sha256(parquet.read_bytes()).hexdigest(),
        csv_bytes=csv.stat().st_size,
        csv_sha256=hashlib.sha256(csv.read_bytes()).hexdigest(),
        min_date="2026-07-29",
        max_date="2026-07-29",
    )


def test_publisher_activates_latest_pointer_after_verified_release(tmp_path: Path) -> None:
    fake = FakeS3()
    publisher = R2Publisher(fake, "weather")
    table = _exported_table(tmp_path, "fact_weather_daily")

    manifest = publisher.publish_release(
        release_id="20260729T181500Z",
        source="local-postgres",
        generated_at=datetime(2026, 7, 29, 18, 15, tzinfo=UTC),
        tables={"fact_weather_daily": table},
        expected_latest_etag=None,
    )

    keys = [key for _, key, _ in fake.calls]
    assert keys == [
        "v1/releases/20260729T181500Z/analyst/fact_weather_daily.parquet",
        "v1/releases/20260729T181500Z/analyst/fact_weather_daily.csv",
        "v1/releases/20260729T181500Z/manifest.json",
        "v1/current/analyst/fact_weather_daily.csv",
        "v1/latest.json",
    ]
    assert manifest.tables["fact_weather_daily"].row_count == 1
    assert (
        fake.objects["v1/current/analyst/fact_weather_daily.csv"]
        == fake.objects[
            "v1/releases/20260729T181500Z/analyst/fact_weather_daily.csv"
        ]
    )
    assert fake.metadata["v1/current/analyst/fact_weather_daily.csv"] == {
        "release-id": "20260729T181500Z",
        "sha256": manifest.tables["fact_weather_daily"].csv_sha256,
    }
    latest_kwargs = fake.calls[-1][2]
    assert latest_kwargs["IfNoneMatch"] == "*"
    assert json.loads(fake.objects["v1/latest.json"])["release_id"] == "20260729T181500Z"


def test_publisher_prunes_old_releases_after_activating_latest(tmp_path: Path) -> None:
    fake = FakeS3()
    for release_id in (
        "20260725T181500Z",
        "20260726T181500Z",
        "20260727T181500Z",
        "20260728T181500Z",
    ):
        fake.objects[f"v1/releases/{release_id}/manifest.json"] = b"{}"
    publisher = R2Publisher(fake, "weather")

    publisher.publish_release(
        release_id="20260729T181500Z",
        source="supabase",
        generated_at=datetime(2026, 7, 29, 18, 15, tzinfo=UTC),
        tables={"fact_weather_daily": _exported_table(tmp_path, "fact_weather_daily")},
        expected_latest_etag=None,
    )

    assert "v1/releases/20260725T181500Z/manifest.json" not in fake.objects
    assert "v1/releases/20260726T181500Z/manifest.json" not in fake.objects
    assert "v1/releases/20260727T181500Z/manifest.json" in fake.objects
    assert "v1/releases/20260728T181500Z/manifest.json" in fake.objects
    assert "v1/releases/20260729T181500Z/manifest.json" in fake.objects


def test_publisher_uses_latest_etag_when_replacing_pointer(tmp_path: Path) -> None:
    fake = FakeS3()
    publisher = R2Publisher(fake, "weather")

    publisher.publish_release(
        release_id="20260730T181500Z",
        source="supabase",
        generated_at=datetime(2026, 7, 30, 18, 15, tzinfo=UTC),
        tables={"fact_weather_daily": _exported_table(tmp_path, "fact_weather_daily")},
        expected_latest_etag='"old-etag"',
    )

    assert fake.calls[-1][2]["IfMatch"] == '"old-etag"'


def test_read_latest_returns_pointer_manifest_and_etag(tmp_path: Path) -> None:
    fake = FakeS3()
    publisher = R2Publisher(fake, "weather")
    publisher.publish_release(
        release_id="20260729T181500Z",
        source="local-postgres",
        generated_at=datetime(2026, 7, 29, 18, 15, tzinfo=UTC),
        tables={"fact_weather_daily": _exported_table(tmp_path, "fact_weather_daily")},
        expected_latest_etag=None,
    )

    pointer, manifest, etag = publisher.read_latest()

    assert pointer.release_id == manifest.release_id == "20260729T181500Z"
    assert etag == '"etag"'


def test_verify_release_rejects_stale_current_csv(tmp_path: Path) -> None:
    fake = FakeS3()
    publisher = R2Publisher(fake, "weather")
    manifest = publisher.publish_release(
        release_id="20260729T181500Z",
        source="local-postgres",
        generated_at=datetime(2026, 7, 29, 18, 15, tzinfo=UTC),
        tables={"fact_weather_daily": _exported_table(tmp_path, "fact_weather_daily")},
        expected_latest_etag=None,
    )
    fake.objects["v1/current/analyst/fact_weather_daily.csv"] = b"stale-content"

    with pytest.raises(RuntimeError, match="current CSV verification failed"):
        publisher.verify_release(manifest)


def test_prune_releases_keeps_active_and_two_previous() -> None:
    fake = FakeS3()
    for release_id in (
        "20260726T181500Z",
        "20260727T181500Z",
        "20260728T181500Z",
        "20260729T181500Z",
    ):
        fake.objects[f"v1/releases/{release_id}/manifest.json"] = b"{}"
    publisher = R2Publisher(fake, "weather")

    publisher.prune_releases(active_release_id="20260729T181500Z", keep=3)

    assert "v1/releases/20260726T181500Z/manifest.json" not in fake.objects
    assert "v1/releases/20260727T181500Z/manifest.json" in fake.objects
    assert "v1/releases/20260728T181500Z/manifest.json" in fake.objects
    assert "v1/releases/20260729T181500Z/manifest.json" in fake.objects


def test_prune_releases_does_not_delete_newer_unactivated_release() -> None:
    fake = FakeS3()
    for release_id in (
        "20260726T181500Z",
        "20260727T181500Z",
        "20260728T181500Z",
        "20260729T181500Z",
        "20260730T181500Z",
    ):
        fake.objects[f"v1/releases/{release_id}/manifest.json"] = b"{}"
    publisher = R2Publisher(fake, "weather")

    publisher.prune_releases(active_release_id="20260729T181500Z", keep=3)

    assert "v1/releases/20260726T181500Z/manifest.json" not in fake.objects
    assert "v1/releases/20260730T181500Z/manifest.json" in fake.objects


def test_prune_releases_ignores_malformed_release_keys() -> None:
    fake = FakeS3()
    valid_release_ids = (
        "20260726T181500Z",
        "20260727T181500Z",
        "20260728T181500Z",
        "20260729T181500Z",
    )
    for release_id in valid_release_ids:
        fake.objects[f"v1/releases/{release_id}/manifest.json"] = b"{}"
    malformed_keys = (
        "v1/releases//manifest.json",
        "v1/releases/0000/manifest.json",
        "v1/releases/20260725T181500Z",
    )
    for key in malformed_keys:
        fake.objects[key] = b"keep"
    publisher = R2Publisher(fake, "weather")

    publisher.prune_releases(active_release_id="20260729T181500Z", keep=3)

    assert "v1/releases/20260726T181500Z/manifest.json" not in fake.objects
    assert all(fake.objects[key] == b"keep" for key in malformed_keys)

import pytest

from scripts import sync_cloud_to_local
from scripts.sync_cloud_to_local import (
    load_database_urls,
    main,
    parse_args,
    run_local_migrations,
)
from src.sync.cloud_to_local import SyncTableResult


def test_load_database_urls_requires_both_values() -> None:
    with pytest.raises(ValueError, match="CLOUD_DATABASE_URL"):
        load_database_urls({"LOCAL_DATABASE_URL": "postgresql+psycopg://local/db"})

    with pytest.raises(ValueError, match="LOCAL_DATABASE_URL"):
        load_database_urls({"CLOUD_DATABASE_URL": "postgresql+psycopg://cloud/db"})


def test_parse_args_uses_safe_defaults() -> None:
    args = parse_args([])

    assert args.lookback_days == 0
    assert args.batch_size == 1000
    assert args.full is False


@pytest.mark.parametrize(
    ("arguments", "expected_code"),
    [
        (["--lookback-days", "-1"], 2),
        (["--batch-size", "0"], 2),
    ],
)
def test_parse_args_rejects_invalid_numbers(arguments: list[str], expected_code: int) -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(arguments)

    assert exc_info.value.code == expected_code


def test_run_local_migrations_passes_only_local_url_as_database_url(monkeypatch) -> None:
    captured = {}

    def fake_run(command, *, check, env, cwd, shell):
        captured.update(command=command, check=check, env=env, cwd=cwd, shell=shell)

    monkeypatch.setattr(sync_cloud_to_local.subprocess, "run", fake_run)

    run_local_migrations("postgresql+psycopg://vwdp:secret@localhost:5433/vwdp")

    assert captured["command"][-3:] == ["alembic", "upgrade", "head"]
    assert captured["check"] is True
    assert captured["shell"] is False
    assert captured["env"]["DATABASE_URL"].endswith("@localhost:5433/vwdp")
    assert "CLOUD_DATABASE_URL" not in captured["env"]
    assert "LOCAL_DATABASE_URL" not in captured["env"]


def test_main_validates_migrates_syncs_and_disposes_engines(monkeypatch, capsys) -> None:
    events: list[str] = []
    cloud_url = "postgresql+psycopg://cloud:cloud-secret@cloud.example/postgres"
    local_url = "postgresql+psycopg://local:local-secret@localhost:5433/vwdp"

    class FakeEngine:
        def __init__(self, name: str) -> None:
            self.name = name

        def dispose(self) -> None:
            events.append(f"dispose:{self.name}")

    def fake_validate(cloud: str, local: str) -> None:
        assert (cloud, local) == (cloud_url, local_url)
        events.append("validate")

    def fake_migrate(url: str) -> None:
        assert url == local_url
        events.append("migrate")

    def fake_create_engine(url: str, *, pool_pre_ping: bool):
        assert pool_pre_ping is True
        name = "cloud" if url == cloud_url else "local"
        events.append(f"engine:{name}")
        return FakeEngine(name)

    class FakeSync:
        def __init__(self, *, cloud_engine, local_engine, options) -> None:
            assert cloud_engine.name == "cloud"
            assert local_engine.name == "local"
            assert options.lookback_days == 0

        def run(self) -> list[SyncTableResult]:
            events.append("sync")
            return [SyncTableResult("dim_district", 2, 2)]

    monkeypatch.setattr(sync_cloud_to_local, "validate_distinct_databases", fake_validate)
    monkeypatch.setattr(sync_cloud_to_local, "run_local_migrations", fake_migrate)
    monkeypatch.setattr(sync_cloud_to_local, "create_engine", fake_create_engine)
    monkeypatch.setattr(sync_cloud_to_local, "CloudToLocalSync", FakeSync)

    result = main(
        [],
        {
            "CLOUD_DATABASE_URL": cloud_url,
            "LOCAL_DATABASE_URL": local_url,
        },
    )

    assert result == 0
    assert events == [
        "validate",
        "migrate",
        "engine:cloud",
        "engine:local",
        "sync",
        "dispose:local",
        "dispose:cloud",
    ]
    output = capsys.readouterr().out
    assert "dim_district: read=2, upserted=2" in output
    assert "Total: read=2, upserted=2" in output


def test_main_disposes_engines_and_hides_credentials_on_failure(monkeypatch, capsys) -> None:
    disposed: list[str] = []
    cloud_url = "postgresql+psycopg://cloud:cloud-secret@cloud.example/postgres"
    local_url = "postgresql+psycopg://local:local-secret@localhost:5433/vwdp"

    class FakeEngine:
        def __init__(self, name: str) -> None:
            self.name = name

        def dispose(self) -> None:
            disposed.append(self.name)

    class FailingSync:
        def __init__(self, **_kwargs) -> None:
            pass

        def run(self):
            raise RuntimeError(f"failed with {cloud_url} and {local_url}")

    monkeypatch.setattr(sync_cloud_to_local, "validate_distinct_databases", lambda *_: None)
    monkeypatch.setattr(sync_cloud_to_local, "run_local_migrations", lambda *_: None)
    monkeypatch.setattr(
        sync_cloud_to_local,
        "create_engine",
        lambda url, **_: FakeEngine("cloud" if url == cloud_url else "local"),
    )
    monkeypatch.setattr(sync_cloud_to_local, "CloudToLocalSync", FailingSync)

    result = main(
        [],
        {
            "CLOUD_DATABASE_URL": cloud_url,
            "LOCAL_DATABASE_URL": local_url,
        },
    )

    assert result == 1
    assert disposed == ["local", "cloud"]
    error = capsys.readouterr().err
    assert "RuntimeError" in error
    assert "failed with" not in error
    assert "cloud.example" not in error
    assert "localhost:5433/vwdp" not in error
    assert "cloud-secret" not in error
    assert "local-secret" not in error

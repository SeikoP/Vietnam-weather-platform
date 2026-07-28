from collections.abc import Mapping

import pytest

from src.metabase.bootstrap import (
    MetabaseSettings,
    provision_warehouse_reader,
    validate_local_warehouse_url,
)


def valid_environment() -> dict[str, str]:
    return {
        "LOCAL_DATABASE_URL": "postgresql+psycopg://vwdp:secret@localhost:5433/vwdp",
        "METABASE_WAREHOUSE_PASSWORD": "reader-secret",
        "METABASE_ADMIN_EMAIL": "admin@example.com",
        "METABASE_ADMIN_PASSWORD": "admin-secret",
        "METABASE_ADMIN_FIRST_NAME": "VWDP",
        "METABASE_ADMIN_LAST_NAME": "Admin",
    }


def test_settings_require_named_environment_values() -> None:
    with pytest.raises(ValueError, match="LOCAL_DATABASE_URL"):
        MetabaseSettings.from_environ({})


def test_settings_parse_complete_environment() -> None:
    settings = MetabaseSettings.from_environ(valid_environment())

    assert settings.admin_email == "admin@example.com"
    assert settings.metabase_url == "http://localhost:3000"


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://vwdp:secret@db.example.com/vwdp",
        "postgresql+psycopg://vwdp:secret@10.0.0.5/vwdp",
        "postgresql+psycopg://vwdp:secret@localhost/other",
    ],
)
def test_local_guard_rejects_non_local_vwdp_database(url: str) -> None:
    with pytest.raises(ValueError, match="local vwdp"):
        validate_local_warehouse_url(url)


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1"])
def test_local_guard_accepts_loopback_hosts(host: str) -> None:
    rendered_host = f"[{host}]" if ":" in host else host
    validate_local_warehouse_url(
        f"postgresql+psycopg://vwdp:secret@{rendered_host}:5433/vwdp"
    )


class RecordingConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.parameters: list[Mapping[str, object]] = []

    def execute(self, statement, parameters=None):
        self.statements.append(str(statement))
        self.parameters.append(parameters or {})
        return None


class RecordingTransaction:
    def __init__(self, connection: RecordingConnection) -> None:
        self.connection = connection

    def __enter__(self) -> RecordingConnection:
        return self.connection

    def __exit__(self, *_args) -> None:
        return None


class RecordingEngine:
    def __init__(self) -> None:
        self.connection = RecordingConnection()

    def begin(self) -> RecordingTransaction:
        return RecordingTransaction(self.connection)


def test_reader_provisioning_grants_only_analyst_select() -> None:
    engine = RecordingEngine()

    provision_warehouse_reader(engine, "reader-secret")

    sql = "\n".join(engine.connection.statements).lower()
    assert "create role metabase_reader" in sql
    assert "alter role metabase_reader" in sql
    assert "grant usage on schema analyst" in sql
    assert "grant select on all tables in schema analyst" in sql
    assert "alter default privileges in schema analyst" in sql
    assert "grant insert" not in sql
    assert "monitoring" not in sql
    assert "reader-secret" not in sql
    assert {"password": "reader-secret"} in engine.connection.parameters

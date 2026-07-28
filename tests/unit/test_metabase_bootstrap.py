import json
from collections.abc import Mapping

import httpx
import pytest

from src.metabase import bootstrap as bootstrap_module
from src.metabase.bootstrap import (
    MetabaseClient,
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


def test_new_instance_setup_creates_admin_and_local_warehouse() -> None:
    captured_setup: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/api/session/properties":
            return httpx.Response(200, json={"setup-token": "setup-token-value"})
        if request.method == "POST" and request.url.path == "/api/setup":
            captured_setup.update(json.loads(request.content))
            return httpx.Response(200, json={"id": "session-id"})
        return httpx.Response(404)

    settings = MetabaseSettings.from_environ(valid_environment())
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = MetabaseClient("http://localhost:3000", http_client)
        client.ensure_setup(settings)

    assert captured_setup["token"] == "setup-token-value"
    assert captured_setup["database"] == {
        "engine": "postgres",
        "name": "VWDP Local Warehouse",
        "details": {
            "host": "postgres",
            "port": 5432,
            "dbname": "vwdp",
            "user": "metabase_reader",
            "password": "reader-secret",
            "ssl": False,
        },
    }
    assert captured_setup["user"]["email"] == "admin@example.com"


def test_initialized_instance_does_not_duplicate_existing_warehouse() -> None:
    requested_paths: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append((request.method, request.url.path))
        if request.url.path == "/api/session/properties":
            return httpx.Response(200, json={"setup-token": None})
        if request.url.path == "/api/session":
            return httpx.Response(200, json={"id": "session-id"})
        if request.url.path == "/api/database":
            return httpx.Response(
                200,
                json={"data": [{"id": 1, "name": "VWDP Local Warehouse"}]},
            )
        return httpx.Response(404)

    settings = MetabaseSettings.from_environ(valid_environment())
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = MetabaseClient("http://localhost:3000", http_client)
        client.ensure_setup(settings)

    assert ("POST", "/api/database") not in requested_paths


def test_health_wait_retries_until_metabase_is_healthy() -> None:
    attempts = 0
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        status = 200 if attempts == 3 else 503
        return httpx.Response(status, json={"status": "ok"} if status == 200 else {})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = MetabaseClient(
            "http://localhost:3000",
            http_client,
            sleep_fn=sleeps.append,
        )
        client.wait_until_healthy(timeout_seconds=10)

    assert attempts == 3
    assert sleeps == [1.0, 1.0]


def test_bootstrap_provisions_reader_before_metabase_setup(monkeypatch) -> None:
    events: list[str] = []
    settings = MetabaseSettings.from_environ(valid_environment())

    class FakeEngine:
        def dispose(self) -> None:
            events.append("dispose")

    class FakeHttpClient:
        def __init__(self, **_kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

    class FakeMetabaseClient:
        def __init__(self, base_url, client) -> None:
            assert base_url == "http://localhost:3000"
            assert isinstance(client, FakeHttpClient)

        def wait_until_healthy(self) -> None:
            events.append("healthy")

        def ensure_setup(self, received_settings) -> None:
            assert received_settings is settings
            events.append("setup")

    engine = FakeEngine()
    monkeypatch.setattr(bootstrap_module, "create_engine", lambda *_args, **_kwargs: engine)
    monkeypatch.setattr(
        bootstrap_module,
        "provision_warehouse_reader",
        lambda received_engine, _password: events.append(
            "reader" if received_engine is engine else "wrong-engine"
        ),
    )
    monkeypatch.setattr(bootstrap_module.httpx, "Client", FakeHttpClient)
    monkeypatch.setattr(bootstrap_module, "MetabaseClient", FakeMetabaseClient)

    bootstrap_module.bootstrap_metabase(settings)

    assert events == ["reader", "dispose", "healthy", "setup"]

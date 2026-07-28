import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url


@dataclass(frozen=True)
class MetabaseSettings:
    local_database_url: str
    warehouse_password: str
    admin_email: str
    admin_password: str
    admin_first_name: str
    admin_last_name: str
    metabase_url: str = "http://localhost:3000"

    @classmethod
    def from_environ(cls, environ: Mapping[str, str]) -> "MetabaseSettings":
        names = (
            "LOCAL_DATABASE_URL",
            "METABASE_WAREHOUSE_PASSWORD",
            "METABASE_ADMIN_EMAIL",
            "METABASE_ADMIN_PASSWORD",
            "METABASE_ADMIN_FIRST_NAME",
            "METABASE_ADMIN_LAST_NAME",
        )
        values = {name: environ.get(name, "").strip() for name in names}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ValueError(f"{missing[0]} is required")

        return cls(
            local_database_url=values["LOCAL_DATABASE_URL"],
            warehouse_password=values["METABASE_WAREHOUSE_PASSWORD"],
            admin_email=values["METABASE_ADMIN_EMAIL"],
            admin_password=values["METABASE_ADMIN_PASSWORD"],
            admin_first_name=values["METABASE_ADMIN_FIRST_NAME"],
            admin_last_name=values["METABASE_ADMIN_LAST_NAME"],
            metabase_url=environ.get("METABASE_URL", "http://localhost:3000").rstrip("/"),
        )


def validate_local_warehouse_url(url: str) -> None:
    parsed = make_url(url)
    if parsed.host not in {"localhost", "127.0.0.1", "::1"} or parsed.database != "vwdp":
        raise ValueError("LOCAL_DATABASE_URL must target the local vwdp database")


def provision_warehouse_reader(engine: Engine, password: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("SELECT set_config('vwdp.metabase_reader_password', :password, true)"),
            {"password": password},
        )
        connection.execute(
            text(
                """
                DO $block$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM pg_roles WHERE rolname = 'metabase_reader'
                    ) THEN
                        EXECUTE format(
                            'ALTER ROLE metabase_reader WITH LOGIN PASSWORD %L',
                            current_setting('vwdp.metabase_reader_password')
                        );
                    ELSE
                        EXECUTE format(
                            'CREATE ROLE metabase_reader WITH LOGIN PASSWORD %L',
                            current_setting('vwdp.metabase_reader_password')
                        );
                    END IF;
                END
                $block$;
                """
            )
        )
        connection.execute(text("GRANT CONNECT ON DATABASE vwdp TO metabase_reader"))
        connection.execute(text("GRANT USAGE ON SCHEMA analyst TO metabase_reader"))
        connection.execute(
            text("GRANT SELECT ON ALL TABLES IN SCHEMA analyst TO metabase_reader")
        )
        connection.execute(
            text(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA analyst "
                "GRANT SELECT ON TABLES TO metabase_reader"
            )
        )


class MetabaseClient:
    def __init__(
        self,
        base_url: str,
        client: httpx.Client,
        sleep_fn=time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = client
        self.sleep_fn = sleep_fn

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = self.client.request(method, f"{self.base_url}{path}", **kwargs)
        if response.is_error:
            raise RuntimeError(
                f"Metabase request failed: {method} {path} returned {response.status_code}"
            )
        return response

    @staticmethod
    def _warehouse_payload(settings: MetabaseSettings) -> dict[str, object]:
        return {
            "engine": "postgres",
            "name": "VWDP Local Warehouse",
            "details": {
                "host": "postgres",
                "port": 5432,
                "dbname": "vwdp",
                "user": "metabase_reader",
                "password": settings.warehouse_password,
                "ssl": False,
            },
        }

    def wait_until_healthy(self, timeout_seconds: int = 180) -> None:
        deadline = time.monotonic() + timeout_seconds
        while True:
            try:
                response = self.client.get(f"{self.base_url}/api/health")
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            if time.monotonic() >= deadline:
                raise TimeoutError("Metabase did not become healthy before timeout")
            self.sleep_fn(1.0)

    def ensure_setup(self, settings: MetabaseSettings) -> None:
        properties = self._request("GET", "/api/session/properties").json()
        setup_token = properties.get("setup-token")
        database = self._warehouse_payload(settings)

        if setup_token:
            self._request(
                "POST",
                "/api/setup",
                json={
                    "token": setup_token,
                    "user": {
                        "email": settings.admin_email,
                        "first_name": settings.admin_first_name,
                        "last_name": settings.admin_last_name,
                        "password": settings.admin_password,
                        "site_name": "VWDP Metabase",
                    },
                    "prefs": {
                        "site_name": "VWDP Metabase",
                        "site_locale": "en",
                        "allow_tracking": False,
                    },
                    "database": database,
                },
            )
            return

        session_id = self._request(
            "POST",
            "/api/session",
            json={
                "username": settings.admin_email,
                "password": settings.admin_password,
            },
        ).json()["id"]
        headers = {"X-Metabase-Session": session_id}
        databases_payload = self._request("GET", "/api/database", headers=headers).json()
        databases = (
            databases_payload.get("data", [])
            if isinstance(databases_payload, dict)
            else databases_payload
        )
        if not any(item.get("name") == database["name"] for item in databases):
            self._request("POST", "/api/database", headers=headers, json=database)


def bootstrap_metabase(settings: MetabaseSettings) -> None:
    validate_local_warehouse_url(settings.local_database_url)
    engine = create_engine(settings.local_database_url, pool_pre_ping=True)
    try:
        provision_warehouse_reader(engine, settings.warehouse_password)
    finally:
        engine.dispose()

    with httpx.Client(timeout=30.0) as http_client:
        client = MetabaseClient(settings.metabase_url, http_client)
        client.wait_until_healthy()
        client.ensure_setup(settings)

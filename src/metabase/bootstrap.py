from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import Engine, text
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

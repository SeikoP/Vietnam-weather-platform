import inspect

from src.database.migrations.versions import e5f6a7b8c9d0_add_dim_hour_and_drop_fact_timestamps


def test_dim_hour_downgrade_restores_daily_timestamp_defaults() -> None:
    source = inspect.getsource(e5f6a7b8c9d0_add_dim_hour_and_drop_fact_timestamps.downgrade)

    assert "add column created_at timestamptz not null default now()" in source
    assert "add column updated_at timestamptz not null default now()" in source

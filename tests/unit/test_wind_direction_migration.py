from unittest.mock import patch

from src.database.migrations.versions import f6a7b8c9d0e1_add_wind_direction_to_hourly as migration


def test_migration_adds_and_removes_nullable_hourly_wind_direction() -> None:
    with patch.object(migration.op, "add_column") as add_column:
        migration.upgrade()

    args, kwargs = add_column.call_args
    assert args[0] == "fact_weather_hourly"
    assert args[1].name == "wind_direction_10m"
    assert args[1].nullable is True
    assert kwargs == {"schema": "analyst"}

    with patch.object(migration.op, "drop_column") as drop_column:
        migration.downgrade()

    drop_column.assert_called_once_with(
        "fact_weather_hourly",
        "wind_direction_10m",
        schema="analyst",
    )

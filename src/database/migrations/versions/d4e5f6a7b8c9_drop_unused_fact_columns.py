"""Drop unused fact columns

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-08
"""

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


DAILY_NULL_COLUMNS = [
    "relative_humidity_2m_mean",
    "dew_point_2m_mean",
    "surface_pressure_mean",
    "vapour_pressure_deficit_mean",
    "cloud_cover_mean",
    "soil_moisture_0_to_7cm_mean",
]


def upgrade() -> None:
    for column_name in DAILY_NULL_COLUMNS:
        op.drop_column("fact_weather_daily", column_name, schema="analyst")

    for table_name in ["fact_weather_daily", "fact_weather_hourly", "fact_aqi_hourly"]:
        op.drop_column(table_name, "etl_run_id", schema="analyst")
        op.drop_column(table_name, "source", schema="analyst")


def downgrade() -> None:
    op.add_column(
        "fact_aqi_hourly",
        sa.Column(
            "source",
            sa.String(length=50),
            server_default="open-meteo-air-quality",
            nullable=False,
        ),
        schema="analyst",
    )
    op.add_column("fact_aqi_hourly", sa.Column("etl_run_id", sa.BigInteger()), schema="analyst")

    for table_name in ["fact_weather_hourly", "fact_weather_daily"]:
        op.add_column(
            table_name,
            sa.Column("source", sa.String(length=50), server_default="open-meteo", nullable=False),
            schema="analyst",
        )
        op.add_column(table_name, sa.Column("etl_run_id", sa.BigInteger()), schema="analyst")

    for column_name in reversed(DAILY_NULL_COLUMNS):
        op.add_column(
            "fact_weather_daily",
            sa.Column(column_name, sa.REAL()),
            schema="analyst",
        )

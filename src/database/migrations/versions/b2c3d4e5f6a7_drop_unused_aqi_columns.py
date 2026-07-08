"""Drop unused AQI columns

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-08
"""

import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("fact_aqi_hourly", "european_aqi", schema="analyst")
    op.drop_column("fact_aqi_hourly", "us_aqi", schema="analyst")
    op.drop_column("fact_aqi_hourly", "ammonia", schema="analyst")


def downgrade() -> None:
    op.add_column(
        "fact_aqi_hourly",
        sa.Column("ammonia", sa.Double(), nullable=True),
        schema="analyst",
    )
    op.add_column(
        "fact_aqi_hourly",
        sa.Column("us_aqi", sa.Double(), nullable=True),
        schema="analyst",
    )
    op.add_column(
        "fact_aqi_hourly",
        sa.Column("european_aqi", sa.Double(), nullable=True),
        schema="analyst",
    )

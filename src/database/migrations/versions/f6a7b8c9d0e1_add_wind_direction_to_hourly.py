"""Add hourly wind direction.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-01
"""

import sqlalchemy as sa
from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "fact_weather_hourly",
        sa.Column("wind_direction_10m", sa.REAL(), nullable=True),
        schema="analyst",
    )


def downgrade() -> None:
    op.drop_column(
        "fact_weather_hourly",
        "wind_direction_10m",
        schema="analyst",
    )

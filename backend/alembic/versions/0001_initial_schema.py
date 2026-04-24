"""Initial schema: season, category, event, rider, event_result, visit.

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "season",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False, unique=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False, unique=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("championship_format", sa.String(length=32), nullable=False, server_default="per_event"),
    )

    op.create_table(
        "category",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("season.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("season_id", "code", name="uq_category_season_code"),
    )

    op.create_table(
        "event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("season.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("location", sa.String(length=128), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("event_type", sa.String(length=64), nullable=True),
        sa.UniqueConstraint("season_id", "slug", name="uq_event_season_slug"),
    )

    op.create_table(
        "rider",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("season.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("category.id", ondelete="CASCADE"), nullable=False),
        sa.Column("race_number", sa.Integer(), nullable=False),
        sa.Column("first_name", sa.String(length=128), nullable=False),
        sa.Column("last_name", sa.String(length=128), nullable=False),
        sa.Column("team", sa.String(length=255), nullable=True),
        sa.Column("bike", sa.String(length=255), nullable=True),
        sa.UniqueConstraint("category_id", "race_number", name="uq_rider_category_race_number"),
    )

    op.create_table(
        "event_result",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("event.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rider_id", sa.Integer(), sa.ForeignKey("rider.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("points", sa.Numeric(6, 2), nullable=True),
        sa.Column("time_ms", sa.BigInteger(), nullable=True),
        sa.Column("start_time_ms", sa.BigInteger(), nullable=True),
        sa.Column("gps_penalty_ms", sa.BigInteger(), nullable=True),
        sa.Column("cp_count", sa.Integer(), nullable=True),
        sa.Column("laps", sa.Integer(), nullable=True),
        sa.Column("gap_ms", sa.BigInteger(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("event_id", "rider_id", name="uq_result_event_rider"),
    )
    op.create_index("ix_result_event", "event_result", ["event_id"])
    op.create_index("ix_result_rider", "event_result", ["rider_id"])

    op.create_table(
        "visit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("page", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("season_year", sa.Integer(), nullable=True),
        sa.Column("device_type", sa.String(length=16), nullable=False, server_default="unknown"),
    )
    op.create_index("ix_visit_timestamp", "visit", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_visit_timestamp", table_name="visit")
    op.drop_table("visit")
    op.drop_index("ix_result_rider", table_name="event_result")
    op.drop_index("ix_result_event", table_name="event_result")
    op.drop_table("event_result")
    op.drop_table("rider")
    op.drop_table("event")
    op.drop_table("category")
    op.drop_table("season")

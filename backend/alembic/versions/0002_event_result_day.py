"""Add `day` column to event_result for multi-day races.

Championship points for an event = sum of points across days for the same
(rider, event) pair. For existing single-day results, backfill day=1 and
replace the (event_id, rider_id) unique constraint with (event_id, rider_id, day).
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_event_result_day"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add the column with a non-null default of 1 so existing rows backfill cleanly.
    op.add_column(
        "event_result",
        sa.Column("day", sa.Integer(), nullable=False, server_default="1"),
    )

    # Replace the uniqueness constraint — now keyed by (event, rider, day).
    op.drop_constraint("uq_result_event_rider", "event_result", type_="unique")
    op.create_unique_constraint(
        "uq_result_event_rider_day",
        "event_result",
        ["event_id", "rider_id", "day"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_result_event_rider_day", "event_result", type_="unique")
    op.create_unique_constraint(
        "uq_result_event_rider",
        "event_result",
        ["event_id", "rider_id"],
    )
    op.drop_column("event_result", "day")

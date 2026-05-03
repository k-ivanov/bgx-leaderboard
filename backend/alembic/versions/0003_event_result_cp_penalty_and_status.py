"""Add `cp_penalty_ms` + `status` to event_result.

Columns capture data that the new uniform CSV format carries per row:
  - cp_penalty_ms: checkpoint penalty time in milliseconds (distinct from
    cp_count which is the number of checkpoints hit).
  - status: FIN / DNF / DNS / etc. — an explicit state instead of inferring
    DNF from a null position.
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_er_cp_penalty_status"
down_revision = "0002_event_result_day"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "event_result",
        sa.Column("cp_penalty_ms", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "event_result",
        sa.Column("status", sa.String(length=8), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("event_result", "status")
    op.drop_column("event_result", "cp_penalty_ms")

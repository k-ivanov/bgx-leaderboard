"""Plausible-style analytics: add visitor_id/session_id/slug columns + daily salt.

Adds to `visit`:
  - visitor_id / session_id: computed server-side from a daily-rotating salt
    hashed against (ip, user_agent, domain). No cookies, no client storage —
    qualifies as cookieless analytics that doesn't trigger ePrivacy consent.
  - event_slug / rider_slug: identify race-result and rider-profile page views.
  - composite index (visitor_id, timestamp) for the session-derivation lookup.

New `analytics_salt` table: one row per UTC day, salt is 32 hex chars.
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_visit_analytics_ids"
down_revision = "0003_er_cp_penalty_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analytics_salt",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("salt", sa.String(length=64), nullable=False),
    )

    op.add_column(
        "visit",
        sa.Column("visitor_id", sa.String(length=32), nullable=False, server_default=""),
    )
    op.add_column(
        "visit",
        sa.Column("session_id", sa.String(length=36), nullable=False, server_default=""),
    )
    op.add_column("visit", sa.Column("event_slug", sa.String(length=64), nullable=True))
    op.add_column("visit", sa.Column("rider_slug", sa.String(length=128), nullable=True))

    op.create_index("ix_visit_visitor_time", "visit", ["visitor_id", "timestamp"])


def downgrade() -> None:
    op.drop_index("ix_visit_visitor_time", table_name="visit")
    op.drop_column("visit", "rider_slug")
    op.drop_column("visit", "event_slug")
    op.drop_column("visit", "session_id")
    op.drop_column("visit", "visitor_id")
    op.drop_table("analytics_salt")

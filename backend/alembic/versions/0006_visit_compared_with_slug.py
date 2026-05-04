"""Add visit.compared_with_slug for compare-page tracking.

When a user lands on /compare?a=&b= we POST a Visit row with
page='compare', rider_slug=A, compared_with_slug=B (slugs sorted
alphabetically before storage so the same pair always buckets into
one stat row). Null for every other page type.
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_visit_compared_with_slug"
down_revision = "0005_import_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "visit",
        sa.Column("compared_with_slug", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("visit", "compared_with_slug")

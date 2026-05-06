"""Add event.facebook_event_url and event.description.

Two optional columns on Event so the new /races and /races/{slug} pages
can show race marketing copy + a CTA to the FB event. Edited via
SQLAdmin; never populated by the seed importer (the source CSVs don't
carry these fields).
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_event_fb_and_description"
down_revision = "0006_visit_compared_with_slug"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "event",
        sa.Column("facebook_event_url", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "event",
        sa.Column("description", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("event", "description")
    op.drop_column("event", "facebook_event_url")

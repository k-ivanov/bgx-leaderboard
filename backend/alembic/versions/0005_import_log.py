"""Track which seed_data CSVs have been imported, so seed-new can skip them.

Single table `import_log` keyed by source filename + sha256 of the file
contents. Allows incremental imports without wiping the DB.
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_import_log"
down_revision = "0004_visit_analytics_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("rows_imported", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("source_filename", "sha256", name="uq_import_log_file_sha"),
    )
    op.create_index("ix_import_log_filename", "import_log", ["source_filename"])


def downgrade() -> None:
    op.drop_index("ix_import_log_filename", table_name="import_log")
    op.drop_table("import_log")

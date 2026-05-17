"""The `core` Django app — holds the ported ORM models (F2) + admin (X3).

F1 only registers the app so ``manage.py`` / migrations / pytest-django wire
up. F2 fills ``core/models.py`` with the 8 tables pinned to the existing
Alembic schema; X3 fills ``core/admin.py``.
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    # F2: pinned to AutoField (32-bit integer), NOT BigAutoField. The real
    # production *_id_seq sequences are integer (Alembic sa.Integer() PKs);
    # an implicit BigAutoField would diverge from the adopted schema. The
    # project-wide DEFAULT_AUTO_FIELD stays BigAutoField — Django's own
    # contrib tables are created fresh and may use bigint (expected, see
    # core/MIGRATION_REHEARSAL.md). This override is scoped to `core` only.
    default_auto_field = "django.db.models.AutoField"
    name = "core"
    verbose_name = "BGX core (models, admin, importers)"

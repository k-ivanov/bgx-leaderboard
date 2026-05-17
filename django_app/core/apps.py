"""The `core` Django app — holds the ported ORM models (F2) + admin (X3).

F1 only registers the app so ``manage.py`` / migrations / pytest-django wire
up. F2 fills ``core/models.py`` with the 8 tables pinned to the existing
Alembic schema; X3 fills ``core/admin.py``.
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "BGX core (models, admin, importers)"

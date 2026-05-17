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

    def ready(self) -> None:
        """F3 hook (additive — does not alter F2's auto-field pin above).

        Pin the serialization-parity JSON renderer onto the FROZEN single
        ``NinjaAPI`` instance. ``api/__init__.py`` is FROZEN (F1, decision
        I1-arch=A) and constructs the API WITHOUT a ``renderer=`` arg, so it
        defaults to Ninja's unpinned ``JSONRenderer`` (spaces after every
        ``,``/``:`` + every Cyrillic name ``\\uXXXX``-escaped — NOT byte-equal
        to the FastAPI parity oracle). Ninja reads ``api.renderer`` LIVE per
        request, so reassigning it at app-ready time is fully effective and
        edits no frozen file. Idempotent. See
        ``api/renderers.py`` for the full pinned spec + the one documented
        Content-Type divergence.
        """
        from api.renderers import pin_parity_renderer

        pin_parity_renderer()

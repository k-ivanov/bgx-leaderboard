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
        """F3 + parity-polish hooks (additive — does not alter F2's
        auto-field pin above).

        All global ``NinjaAPI`` behavior is wired here, via the established
        app-ready idiom, because ``api/__init__.py`` + ``config/urls.py`` are
        FROZEN (F1, decision I1-arch=A) and Ninja reads these attributes LIVE
        off the singleton per request / per schema build — so reassigning
        them at app-ready time is fully effective and edits no frozen file.
        Each call is idempotent.

        1. ``pin_parity_renderer()`` (F3 + ledger #1) — pin the
           serialization-parity ``ParityJSONRenderer`` AND the bare
           ``application/json`` Content-Type onto the singleton (the API is
           constructed WITHOUT a ``renderer=`` arg, so it would otherwise use
           Ninja's unpinned ``JSONRenderer`` + a ``; charset=utf-8`` header,
           NOT byte-equal to the FastAPI oracle). See ``api/renderers.py``.
        2. ``install_parity_hooks()`` (ledger #2 + #6) — register the
           byte-exact slowapi/FastAPI ``Throttled`` 429 handler, and pin the
           FastAPI-convention operationId generator + the OpenAPI
           post-processor (422 + ``HTTPValidationError`` / ``ValidationError``
           components + ``HTTPBasic`` security + ``/health`` + canonical
           parameter order). See ``api/parity_hooks.py``.
        """
        from api.parity_hooks import install_parity_hooks
        from api.renderers import pin_parity_renderer

        pin_parity_renderer()
        install_parity_hooks()

"""Ported Django ORM models — FILLED BY F2, NOT F1.

F1 leaves this empty on purpose. F2 ports ``backend/src/db/models.py`` to
Django models for all 8 tables (``season``, ``category``, ``event``,
``rider``, ``event_result``, ``visit``, ``import_log``, ``analytics_salt``),
each pinning ``class Meta: db_table`` + exact column names to the existing
Alembic schema, then generates ``0001_initial`` for ``migrate --fake-initial``.

Empty here so the ``core`` app loads and the test/migration harness boots.
"""

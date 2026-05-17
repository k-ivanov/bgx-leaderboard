"""S2 — domain services hub (scoring + standings).

This package is the **service hub** S3/S4/S7 import after S2 merges
(``.plan/django-ninja-tasks.md`` Lane D). It is the Django-ORM port of
``backend/src/services/`` — the *algorithm bodies are reused verbatim*; only
the data-fetch layer is translated from SQLAlchemy
``select()``/``selectinload()`` to Django ORM
``filter()``/``prefetch_related()``.

Public API (consumed by S3/S4/S7 — the exact names + signatures the FastAPI
service module exposed):

* ``core.services.scoring``   — ``compute_event_scoring``,
  ``points_for_position``, ``EventScore``.
* ``core.services.standings`` — ``get_standings``, ``events_for_season``,
  ``position_from_points``, ``StandingsRow``, ``RiderEventEntry``.
"""

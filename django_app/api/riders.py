"""S4 — Riders API (career + search). F1 placeholder.

F1 pre-stubs EMPTY ``ninja.Router`` objects. The S4 slice agent (see
``.plan/django-ninja-tasks.md``) fills the body of THIS module ONLY and must
never edit ``api/__init__.py`` or ``config/urls.py`` — both are FROZEN by F1.

Two routers because the frozen FastAPI app mounts both:
  - ``router``        — per-season rider endpoints (prefix ``/api/seasons``)
  - ``career_router`` — cross-season career + search (prefix ``/api/riders``)
See ``backend/app/api/riders.py`` (``router`` + ``career_router``) and
``backend/app/main.py:111-112``.
"""

from ninja import Router

# S4 fills these. Empty placeholders so the frozen assembly imports cleanly.
router = Router()
career_router = Router()

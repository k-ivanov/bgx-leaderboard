"""S3 — Events/Races API. F1 placeholder.

F1 pre-stubs an EMPTY ``ninja.Router``. The S3 slice agent (see
``.plan/django-ninja-tasks.md``) fills the body of THIS module ONLY and must
never edit ``api/__init__.py`` or ``config/urls.py`` — both are FROZEN by F1.

Ports ``backend/app/api/events.py`` (prefix ``/api/seasons``, main.py:109).
"""

from ninja import Router

router = Router()

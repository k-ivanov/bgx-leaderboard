"""S6 — Track / analytics-write. F1 placeholder.

F1 pre-stubs an EMPTY ``ninja.Router``. The S6 slice agent (see
``.plan/django-ninja-tasks.md``) fills the body of THIS module ONLY and must
never edit ``api/__init__.py`` or ``config/urls.py`` — both are FROZEN by F1.

Ports ``backend/app/api/track.py`` (prefix ``/api``, main.py:114).
"""

from ninja import Router

router = Router()

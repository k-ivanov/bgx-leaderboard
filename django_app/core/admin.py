"""X3 — Django admin (replaces SQLAdmin). F1 placeholder.

F1 wires the ``/admin`` URL slot in the FROZEN ``config/urls.py`` in the
load-bearing order (after ``/api/*`` + ``/health``, before legacy 301s and the
static catch-all). X3 fills THIS module (ModelAdmin classes for Season /
Category / Event(Race) / Rider / EventResult(Result) / Visit, Visit read-only)
and the env-gated provisioning, and must never edit ``config/urls.py``.

The frozen FastAPI app gates the admin entirely on ``ADMIN_PASSWORD`` being
set (``backend/app/config.py:26-32``); X3 reproduces "absent/forbidden when
unconfigured" using Django auth. F1 registers nothing — no models exist until
F2.
"""

# Intentionally empty in F1. X3 adds `admin.site.register(...)` calls here
# once F2 lands the ORM models in core/models.py.

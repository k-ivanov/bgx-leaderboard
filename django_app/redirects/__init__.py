"""X1 — legacy 301 redirects + static catch-all. F1 placeholder package.

F1 only pre-stubs the URL slots (see ``config/urls.py``):
  - ``legacy_redirect_urlpatterns`` — the legacy ``/{year}/...`` 301 patterns
    (X1 ports ``backend/app/redirects.py`` here, declaration order preserved).
  - ``static_catchall`` — the catch-all view that serves the Astro ``dist/``
    (X1 ports the ``FrontendStatic`` behavior: directory-index without a
    slash redirect, real 404 status, JSON 404 for unmatched ``/api/*`` and
    ``/admin/*``, path-traversal guard).

Both are EMPTY placeholders so the FROZEN ``config/urls.py`` imports cleanly.
The X1 slice agent fills THIS package only and must never edit
``config/urls.py`` (FROZEN by F1).
"""

from django.http import HttpResponse
from django.urls import path

# X1 fills this list with the ported legacy 301 patterns. Empty for now —
# the URLconf slot exists and is wired in the load-bearing order by F1.
legacy_redirect_urlpatterns: list = []


def static_catchall(request, path: str = ""):  # noqa: D401 - placeholder
    """Placeholder catch-all. X1 replaces this with the ported FrontendStatic.

    F1 returns a minimal 404 so the URL resolves (the slot is wired) without
    pretending to serve a frontend that does not exist yet.
    """
    return HttpResponse(status=404)


# Exposed so the FROZEN urls.py can reference a stable name for the slot.
__all__ = ["legacy_redirect_urlpatterns", "static_catchall", "path"]

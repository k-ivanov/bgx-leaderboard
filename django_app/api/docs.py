"""X2 — security headers + auth-gated API docs. F1 placeholder.

F1 pre-stubs the gated-docs URL slot so ``config/urls.py`` (FROZEN) can wire
it in the load-bearing order. X2 fills THIS module + security middleware/
settings only and must never edit ``config/urls.py`` or ``api/__init__.py``.

The frozen FastAPI app serves ``/api/openapi.json`` + ``/api/docs`` behind the
stats auth gate (``backend/app/main.py:132-162``). X2 ports that here. F1's
placeholder returns 404 so the routes resolve without exposing a schema.
"""

from django.http import HttpResponse
from django.urls import path


def openapi_json(request):  # noqa: D401 - placeholder
    """Placeholder — X2 serves the gated NinjaAPI schema here."""
    return HttpResponse(status=404)


def swagger_ui(request):  # noqa: D401 - placeholder
    """Placeholder — X2 serves the gated Swagger UI here."""
    return HttpResponse(status=404)


# X2 fills this with the real (auth-gated) doc patterns. Wired by F1 in the
# /api/* band of the FROZEN urls.py, before the Ninja catch-all.
gated_docs_urlpatterns = [
    path("api/openapi.json", openapi_json, name="x2-openapi-json"),
    path("api/docs", swagger_ui, name="x2-api-docs"),
]

__all__ = ["gated_docs_urlpatterns", "openapi_json", "swagger_ui"]

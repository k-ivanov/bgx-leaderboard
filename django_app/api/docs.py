"""X2 — auth-gated ``/api/openapi.json`` + ``/api/docs``.

Byte-faithful port of ``backend/app/main.py::_mount_gated_docs`` (lines
132-162) and ``backend/app/auth.py::require_stats_auth``. The schema + Swagger
UI are deliberately kept OFF the public internet (parity with the FastAPI app
booting with ``docs_url=None / openapi_url=None``) and re-served here behind
the SAME stats auth gate as ``/api/stats``:

* ``STATS_PASSWORD`` set    → HTTP Basic required; any non-empty username +
  the configured password (username is NOT checked). Missing creds → 401
  ``{"detail": "Not authenticated"}``; wrong password → 401
  ``{"detail": "Invalid credentials"}``; both carry
  ``WWW-Authenticate: Basic realm="stats"``. Constant-time password compare.
* ``STATS_PASSWORD`` unset/empty → dev convenience: the gate is a no-op and
  the docs are openly reachable (same dev-mode pattern the stats endpoint
  uses — backend/app/auth.py:23-24).

FROZEN-FILE CONTRACT: ``config/urls.py`` does ``*gated_docs_urlpatterns`` in
the load-bearing ``/api/*`` band and ``api/__init__.py`` is the single
NinjaAPI instance. X2 fills ONLY this module — the URL paths
(``api/openapi.json``, ``api/docs``) and pattern names (``x2-openapi-json``,
``x2-api-docs``) are preserved exactly so the frozen urlconf and the F1
slot-import smoke test keep passing.
"""

from __future__ import annotations

import base64
import binascii
import secrets

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.urls import path

# The single FROZEN NinjaAPI instance (api/__init__.py). Imported by reference
# only — we never mutate it; we just read its generated OpenAPI schema, the
# same way backend/app/main.py:150-155 calls fastapi's get_openapi(routes=...).
from api import api as ninja_api

_REALM = 'Basic realm="stats"'


# ---------------------------------------------------------------------------
# Stats auth gate — port of backend/app/auth.py::require_stats_auth.
# Returns an HttpResponse (401) to short-circuit, or None to allow.
# ---------------------------------------------------------------------------

def _unauthorized(detail: str) -> JsonResponse:
    """401 with the FastAPI-identical body + WWW-Authenticate header."""
    resp = JsonResponse({"detail": detail}, status=401)
    resp["WWW-Authenticate"] = _REALM
    return resp


def _require_stats_auth(request):
    """None if the request may proceed, else a 401 HttpResponse.

    Mirrors backend/app/auth.py exactly:
      * empty STATS_PASSWORD  → dev mode, no auth (return None)
      * no Basic credentials  → 401 "Not authenticated"
      * wrong password        → 401 "Invalid credentials"
      * username is never checked; password compared in constant time.
    """
    stats_password = settings.STATS_PASSWORD
    if not stats_password:
        return None  # dev mode — no auth required (auth.py:23-24)

    header = request.META.get("HTTP_AUTHORIZATION", "")
    scheme, _, payload = header.partition(" ")
    if scheme.lower() != "basic" or not payload:
        # No (parseable) Basic credentials supplied → "Not authenticated"
        # (auth.py:26-31; fastapi's HTTPBasic(auto_error=False) yields None).
        return _unauthorized("Not authenticated")

    try:
        decoded = base64.b64decode(payload, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return _unauthorized("Not authenticated")

    _username, _, password = decoded.partition(":")

    # Constant-time compare to mitigate timing attacks (auth.py:34-37).
    password_ok = secrets.compare_digest(
        password.encode("utf-8"),
        stats_password.encode("utf-8"),
    )
    if not password_ok:
        return _unauthorized("Invalid credentials")

    return None  # authenticated


# ---------------------------------------------------------------------------
# Views — parity with backend/app/main.py::_mount_gated_docs.
# ---------------------------------------------------------------------------

def openapi_json(request):
    """GET /api/openapi.json — the gated OpenAPI schema.

    Parity with backend/app/main.py:148-155: same auth gate, returns the
    NinjaAPI-generated schema (title/version/description already match the
    FastAPI app — see api/__init__.py).
    """
    blocked = _require_stats_auth(request)
    if blocked is not None:
        return blocked
    schema = ninja_api.get_openapi_schema()
    # json_dumps=False keeps DjangoJSONEncoder off a plain dict; the schema is
    # already a JSON-safe mapping (Ninja builds it that way).
    return JsonResponse(dict(schema), json_dumps_params={"ensure_ascii": False})


# Self-contained Swagger UI shell. Equivalent to fastapi's
# get_swagger_ui_html(openapi_url="/api/openapi.json", title=...) — same CDN
# bundle Ninja itself ships (swagger-ui-dist@5), pointed at the gated schema
# URL. Kept inline (no template-dir dependency) so it renders identically
# regardless of TEMPLATES app-dir config.
_SWAGGER_HTML = """<!DOCTYPE html>
<html>
<head>
    <link type="text/css" rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
    <title>{title}</title>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        const ui = SwaggerUIBundle({{
            url: "/api/openapi.json",
            dom_id: "#swagger-ui",
            deepLinking: true,
            presets: [
                SwaggerUIBundle.presets.apis,
                SwaggerUIBundle.SwaggerUIStandalonePreset
            ],
            layout: "BaseLayout"
        }});
    </script>
</body>
</html>"""


def swagger_ui(request):
    """GET /api/docs — the gated Swagger UI.

    Parity with backend/app/main.py:157-162: same auth gate, Swagger UI
    pointed at /api/openapi.json, title == "<api title> — docs".
    """
    blocked = _require_stats_auth(request)
    if blocked is not None:
        return blocked
    html = _SWAGGER_HTML.format(title=f"{ninja_api.title} — docs")
    return HttpResponse(html, content_type="text/html; charset=utf-8")


# X2 fills this slot. FROZEN config/urls.py splats it into the /api/* band
# BEFORE the NinjaAPI mount (paths + names unchanged from the F1 placeholder).
gated_docs_urlpatterns = [
    path("api/openapi.json", openapi_json, name="x2-openapi-json"),
    path("api/docs", swagger_ui, name="x2-api-docs"),
]

__all__ = ["gated_docs_urlpatterns", "openapi_json", "swagger_ui"]

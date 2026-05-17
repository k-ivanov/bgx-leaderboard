"""
==============================================================================
  FROZEN BY F1 — DO NOT EDIT OR REORDER (decision I1-arch=A)
==============================================================================

The root URLconf resolution order is LOAD-BEARING and written ONCE here:

    1. /api/*       → NinjaAPI (S1–S7 routers) + X2 gated docs
    2. /health      → JSON health check (shape/version == frozen FastAPI app)
    3. /admin/      → X3 Django admin (env-gated; absent when unconfigured)
    4. legacy 301s  → X1 ported /{year}/... → new-shape redirects
    5. catch-all    → X1 static serving of the Astro dist/ (real 404 status)

Why the order is load-bearing (CLAUDE.md invariant #4 + the FastAPI app's
``main.py`` mount order): if the catch-all static handler is registered
before the API / redirects, ``dist/{year}/{cat}/index.html`` SHADOWS the 301
redirects and the API — total outage / SEO regression. Django resolves
``urlpatterns`` top-to-bottom, first match wins, so the catch-all MUST stay
last and the legacy 301s MUST stay between /admin and the catch-all.

This file is FROZEN: every slice agent (S1–S7, X1–X3) fills only its own
module — NO slice edits or reorders this file. X1 fills
``redirects.legacy_redirect_urlpatterns`` + ``redirects.static_catchall``;
X2 fills ``api.docs.gated_docs_urlpatterns``; X3 fills ``core/admin.py`` and
the admin gating. The SLOTS are all present and ordered here now.

``APPEND_SLASH = False`` (settings) is part of this contract — Django must
not 301 to a trailing-slash variant or it breaks the indexed legacy URLs.
"""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, re_path

from api import api as ninja_api  # FROZEN NinjaAPI instance (S1–S7 slots)
from api.docs import gated_docs_urlpatterns  # X2 slot (gated /api/docs)
from redirects import legacy_redirect_urlpatterns, static_catchall  # X1 slots

# Ported from backend/app/main.py:103-105 — identical JSON shape + version.
# settings.APP_VERSION mirrors backend/src/config.py:10 ("0.1.0").
from django.conf import settings


def health(request):
    """GET /health — byte-shape parity with backend/app/main.py::health."""
    return JsonResponse(
        {
            "status": "ok",
            "service": "bgx-dashboard-api",
            "version": settings.APP_VERSION,
        }
    )


# === FROZEN RESOLUTION ORDER — DO NOT REORDER =============================

urlpatterns = [
    # --- 1. /api/* band -------------------------------------------------
    # X2 gated docs (/api/openapi.json, /api/docs) MUST precede the NinjaAPI
    # mount so the auth-gated docs win over any catch-all behavior. Empty-safe
    # placeholders in F1.
    *gated_docs_urlpatterns,
    # The single FROZEN NinjaAPI instance — all S1–S7 router slots.
    path("api/", ninja_api.urls),

    # --- 2. /health -----------------------------------------------------
    path("health", health, name="health"),

    # --- 3. /admin/ (X3) ------------------------------------------------
    # Slot wired here in the load-bearing position (after /api + /health,
    # before legacy 301s + static). X3 makes it env-gated / absent when
    # unconfigured; F1 wires Django's default admin site so the slot exists.
    path("admin/", admin.site.urls),

    # --- 4. legacy 301 redirects (X1) -----------------------------------
    # MUST stay between /admin and the catch-all so /{year}/{cat}/... bounces
    # BEFORE dist/{year}/{cat}/index.html can be served. Empty list in F1.
    *legacy_redirect_urlpatterns,

    # --- 5. catch-all static (X1) — MUST BE LAST ------------------------
    # Serves the Astro dist/. JSON 404 for unmatched /api/* and /admin/*,
    # real 404 status for unknown frontend paths, path-traversal guard.
    # F1 placeholder returns 404; X1 ports FrontendStatic here.
    re_path(r"^(?P<path>.*)$", static_catchall),
]

# === END FROZEN RESOLUTION ORDER ==========================================


def _api_not_found(request, exception=None):
    """Unmatched routes fall through to the X1 catch-all (handles /api/* JSON
    404 itself). This handler is a defensive belt-and-suspenders for the rare
    case the catch-all is bypassed; kept JSON for API consistency."""
    return JsonResponse({"detail": "Not Found"}, status=404)


# Django uses this for genuinely unresolvable URLs (the re_path catch-all
# normally absorbs everything first — see X1).
handler404 = "config.urls._api_not_found"

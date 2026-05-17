"""Mount-order contract tests (X1 — ported parity; eng-review A-1 / N1).

Port of ``backend/tests/test_mount_order.py`` adapted to the Django test
client + the FROZEN ``config/urls.py`` resolution order:

    /api/*  →  /health  →  /admin/  →  legacy 301s  →  catch-all static

The API band MUST be matched BEFORE the catch-all static handler, or
``dist/{year}/{cat}/index.html`` would shadow the API + the 301 redirects
(CLAUDE.md invariant #4 — total-outage / SEO-regression failure mode).

Scope note: ``/api/docs`` + ``/api/openapi.json`` are X2-owned (auth-gated
docs). The X1-relevant invariant they pin here is the mount-order one (the
docs slot resolves in the /api band — never 301s, never falls through to the
motorsport 404.html / static catch-all). With X2 merged on the integration
branch the oracle's ``test_api_docs_served`` / ``test_api_openapi_served``
semantics (200 + content shape) hold too, so they are asserted as well — but
the load-bearing X1 assertion is "stays in the /api band, not a 301/static".
"""

import os
import tempfile
from pathlib import Path

from django.test import Client

client = Client()


def test_api_nonexistent_returns_json_404() -> None:
    """``/api/definitely-not-a-real-endpoint`` must NOT fall through to the
    static catch-all; it must return a JSON 404 (Ninja's own, or — for the
    no-trailing-slash edge — the catch-all's JSON guard)."""
    response = client.get("/api/definitely-not-a-real-endpoint")
    assert response.status_code == 404
    assert response.headers["Content-Type"].startswith("application/json")
    body = response.json()
    assert "detail" in body


def test_api_docs_slot_resolves_in_api_band() -> None:
    """The /api/docs slot resolves in the /api band — wired by the FROZEN
    urls.py BEFORE the legacy 301s + static catch-all, so it never 301s and
    never serves the motorsport 404.html. Port of the oracle's
    ``test_api_docs_served``: with X2 merged + STATS_PASSWORD unset (dev), it
    serves the Swagger UI HTML with 200 (parity with FastAPI get_swagger_ui).
    The load-bearing X1 assertion is the mount-order one (not a 301/static)."""
    response = client.get("/api/docs")
    assert response.status_code != 301  # X1 mount-order invariant
    assert response.status_code == 200
    assert "text/html" in response.headers["Content-Type"]


def test_api_openapi_slot_resolves_in_api_band() -> None:
    """The /api/openapi.json slot resolves in the /api band (never 301s/falls
    to static). Port of the oracle's ``test_api_openapi_served``: with X2
    merged + STATS_PASSWORD unset, it serves the schema with the title that
    matches the FastAPI app."""
    response = client.get("/api/openapi.json")
    assert response.status_code != 301  # X1 mount-order invariant
    assert response.status_code == 200
    body = response.json()
    assert body["info"]["title"] == "BGX Hard Enduro Dashboard API"


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "bgx-dashboard-api"


def test_api_routes_not_shadowed_by_static_mount() -> None:
    """Even with the frontend static dist resolvable, /api/* must still hit
    the API band (JSON), a bare path falls through to index.html, and an
    unknown path serves 404.html with a real 404 — parity with the oracle's
    Phase-4 container-layout simulation (FRONTEND_DIST → temp dist)."""
    with tempfile.TemporaryDirectory() as tmp:
        dist = Path(tmp) / "dist"
        dist.mkdir()
        (dist / "index.html").write_text(
            "<!doctype html><title>root</title>", encoding="utf-8"
        )
        (dist / "404.html").write_text(
            "<!doctype html><title>404</title>", encoding="utf-8"
        )

        old = os.environ.get("FRONTEND_DIST")
        os.environ["FRONTEND_DIST"] = str(dist)
        try:
            # /api/* still returns JSON 404 (not the static 404.html)
            r1 = client.get("/api/definitely-nonexistent")
            assert r1.status_code == 404
            assert r1.headers["Content-Type"].startswith("application/json")

            # A bare path falls through to the static mount's index.html
            r2 = client.get("/")
            assert r2.status_code == 200
            assert "text/html" in r2.headers["Content-Type"]

            # An unknown path serves 404.html with a real 404 status
            r3 = client.get("/does-not-exist")
            assert r3.status_code == 404
            assert "text/html" in r3.headers["Content-Type"]
        finally:
            if old is None:
                os.environ.pop("FRONTEND_DIST", None)
            else:
                os.environ["FRONTEND_DIST"] = old


def test_frozen_urlconf_order_is_load_bearing() -> None:
    """Resolution order: /api → /health → /admin → legacy 301s → catch-all.

    Mirrors backend/app/main.py mount order + CLAUDE.md invariant #4. The
    catch-all MUST be dead last so static never shadows API/redirects. This
    re-asserts the F1 contract from X1's side (the legacy 301 patterns now
    populate the band between /admin and the catch-all)."""
    from config import urls

    patterns = [str(getattr(p, "pattern", p)) for p in urls.urlpatterns]

    api_idx = next(i for i, p in enumerate(patterns) if p.startswith("api/"))
    health_idx = next(i for i, p in enumerate(patterns) if p == "health")
    admin_idx = next(i for i, p in enumerate(patterns) if p.startswith("admin/"))
    catchall_idx = next(
        i for i, p in enumerate(patterns) if "(?P<path>.*)" in p or p.endswith(".*)$")
    )

    # At least one legacy 301 pattern must sit between /admin and the catch-all.
    legacy_year_idx = next(
        i for i, p in enumerate(patterns) if "(?P<year>" in p
    )

    assert api_idx < health_idx < admin_idx < legacy_year_idx < catchall_idx
    # Catch-all MUST be dead last (static must never shadow API/redirects).
    assert catchall_idx == len(patterns) - 1

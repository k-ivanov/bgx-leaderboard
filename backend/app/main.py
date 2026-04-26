"""FastAPI application factory.

Mount order is load-bearing (eng-review A-1 / N1):
    1. /api/* routers          → JSON endpoints
    2. /health                 → JSON health check
    3. /admin                  → SQLAdmin panel (session auth, configurable)
    4. /* StaticFiles          → serves the Astro-built frontend dist/
                                 (404.html fallback for unknown paths)

No CORS middleware is installed — the frontend and API ship same-origin.
A test in ``tests/test_cors.py`` asserts no Access-Control-* headers leak
(eng-review SC-3 / N8).
"""

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import events as events_api
from app.api import results as results_api
from app.api import riders as riders_api
from app.api import seasons as seasons_api
from app.api import standings as standings_api
from app.api import stats as stats_api
from app.api import track as track_api
from app.config import APP_VERSION, TRACK_MAX_BYTES, TRACK_RATE_LIMIT
from app.security_headers import install as install_security_headers


class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversize request bodies on the POST /api/track endpoint.

    Acts before the Pydantic validator sees the payload, protecting against
    a single request that inflates memory during JSON parsing.
    """

    def __init__(self, app, path: str, max_bytes: int) -> None:
        super().__init__(app)
        self._path = path
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        if request.url.path == self._path and request.method == "POST":
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    if int(content_length) > self._max_bytes:
                        return JSONResponse(
                            status_code=413,
                            content={
                                "detail": f"Payload too large (max {self._max_bytes} bytes)"
                            },
                        )
                except ValueError:
                    pass  # malformed header — let the normal pipeline reject it
        return await call_next(request)


def create_app() -> FastAPI:
    # docs_url / openapi_url are intentionally None; we re-mount them
    # below behind the stats auth gate (P4 #27). This keeps the schema
    # and swagger UI off the public internet by default while still
    # being accessible to a developer who has STATS_PASSWORD.
    app = FastAPI(
        title="BGX Hard Enduro Dashboard API",
        description="Read-only JSON API for the BGX Hard Enduro Championship",
        version=APP_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # Per-IP rate limit; `track_api` decorates its route (see below).
    limiter = Limiter(key_func=get_remote_address, default_limits=[])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Payload-size guard for /api/track before body parsing.
    app.add_middleware(
        PayloadSizeLimitMiddleware,
        path="/api/track",
        max_bytes=TRACK_MAX_BYTES,
    )

    # Baseline security headers (CSP, HSTS, X-Frame-Options, …).
    install_security_headers(app)

    # Apply the slowapi decorator to the track endpoint by wrapping its router's
    # endpoint function. Simpler than refactoring the router — keeps the router
    # self-contained, limiter config in one place here.
    _apply_rate_limit_to_track(limiter)

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok", "service": "bgx-dashboard-api", "version": APP_VERSION}

    app.include_router(seasons_api.router)
    app.include_router(standings_api.router)
    app.include_router(events_api.router)
    app.include_router(results_api.router)
    app.include_router(riders_api.router)
    app.include_router(riders_api.career_router)
    app.include_router(stats_api.router)
    app.include_router(track_api.router)

    _mount_gated_docs(app)

    # Admin panel mounts at /admin BEFORE StaticFiles so it takes priority
    # over the catch-all. Opt-in via ADMIN_PASSWORD env var.
    from app.admin import setup_admin
    setup_admin(app)

    _mount_frontend_if_present(app)

    return app


def _mount_gated_docs(app: FastAPI) -> None:
    """Mount /api/docs and /api/openapi.json behind the stats auth gate.

    Same Basic auth as /api/stats: any non-empty username + STATS_PASSWORD.
    When STATS_PASSWORD is unset (dev convenience), the dependency is a
    no-op so the docs are openly accessible — same dev-mode pattern the
    stats endpoint already uses.

    P4 #27 — covers improvements.md.
    """
    from fastapi import Depends
    from fastapi.openapi.docs import get_swagger_ui_html
    from fastapi.openapi.utils import get_openapi

    from app.auth import require_stats_auth

    @app.get("/api/openapi.json", include_in_schema=False)
    def openapi_json(_: None = Depends(require_stats_auth)):
        return get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

    @app.get("/api/docs", include_in_schema=False)
    def swagger_ui(_: None = Depends(require_stats_auth)):
        return get_swagger_ui_html(
            openapi_url="/api/openapi.json",
            title=app.title + " — docs",
        )


def _mount_frontend_if_present(app: FastAPI) -> None:
    """Mount the Astro-built frontend at `/` if `FRONTEND_DIST` exists.

    MUST run AFTER all /api/* routers have been registered. The default
    `StaticFiles(html=True)` matches everything, so registering it earlier
    would shadow later routes. For 404 behavior we provide an explicit
    catch-all that returns `dist/404.html` with a real 404 status.
    """
    dist_path = _resolve_frontend_dist()
    if dist_path is None:
        return

    # Serve /_astro/* assets (hashed, long-cacheable) + /robots.txt + any
    # file that exists on disk. The `html=True` flag makes `/2026/expert`
    # resolve to `/2026/expert/index.html`.
    app.mount(
        "/",
        FrontendStatic(directory=str(dist_path), html=True, dist=dist_path),
        name="frontend",
    )


def _resolve_frontend_dist() -> Optional[Path]:
    """Find the Astro build output. Honors FRONTEND_DIST env var, else defaults
    to the sibling ``frontend_dist/`` dir co-located with the backend in the
    container. Returns None if no dist is present (dev: API-only mode)."""
    override = os.getenv("FRONTEND_DIST")
    if override:
        p = Path(override)
        return p if p.is_dir() else None

    # Production layout: /app/frontend_dist (set in Dockerfile).
    prod = Path("/app/frontend_dist")
    if prod.is_dir():
        return prod

    # Local dev convenience: ../frontend/dist relative to this file.
    local = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if local.is_dir():
        return local

    return None


class FrontendStatic(StaticFiles):
    """StaticFiles subclass that:

    - Returns a JSON 404 for any path starting with ``api/`` (eng-review A-1).
      The mount at ``/`` catches ``/api/*`` paths that no router matched,
      which would otherwise 404 as HTML. We keep the API contract JSON-only.
    - Serves directory paths (``/2026/expert``) directly as their contained
      ``index.html`` WITHOUT issuing the default 307 trailing-slash redirect.
      Preserves the current FastHTML URL shape (no trailing slash) for backward
      compatibility — important because search engines have indexed the
      trailing-slash-free URLs for months.
    - Otherwise serves the built 404.html with a real 404 status for any
      path that doesn't resolve to a file or directory (SPA-style fallback).
    """

    def __init__(self, *, dist: Path, **kwargs):
        super().__init__(**kwargs)
        self._dist = dist
        self._not_found = dist / "404.html"

    async def get_response(self, path: str, scope):  # type: ignore[override]
        # `path` comes through WITHOUT the leading slash because StaticFiles
        # is mounted at "/"; e.g. "/api/foo" becomes "api/foo".
        if path == "api" or path.startswith("api/"):
            return JSONResponse(
                status_code=404,
                content={"detail": "Not Found"},
            )
        # /admin is a sub-app; if a request reaches here it's because the
        # sub-app returned 404 itself. Return JSON to keep admin responses
        # consistent and avoid serving the motorsport 404.html for /admin paths.
        if path == "admin" or path.startswith("admin/"):
            return JSONResponse(
                status_code=404,
                content={"detail": "Not Found"},
            )

        # Directory lookup: if the resolved path is a dir and has index.html,
        # serve the index file with a 200 regardless of trailing-slash state.
        candidate = (self._dist / path).resolve()
        try:
            candidate.relative_to(self._dist.resolve())  # path traversal guard
        except ValueError:
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        if candidate.is_dir():
            index = candidate / "index.html"
            if index.is_file():
                return FileResponse(index)

        try:
            return await super().get_response(path, scope)
        except Exception:
            if self._not_found.is_file():
                return FileResponse(self._not_found, status_code=404)
            raise


def _apply_rate_limit_to_track(limiter: Limiter) -> None:
    """Attach the configured rate limit to the track endpoint.

    Done here (not inline in ``track.py``) so the limit config stays in
    ``app.config`` and the router stays free of app-level concerns.
    """
    from app.api.track import track_visit

    # slowapi's decorator expects the endpoint to have access to ``request`` —
    # our handler signature already includes it.
    decorated = limiter.limit(TRACK_RATE_LIMIT)(track_visit)

    # Replace the function registered on the router with the wrapped version.
    for route in track_api.router.routes:
        if getattr(route, "endpoint", None) is track_visit:
            route.endpoint = decorated
            route.app = decorated  # type: ignore[attr-defined]


app = create_app()

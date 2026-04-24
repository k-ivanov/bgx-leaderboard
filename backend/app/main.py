"""FastAPI application factory.

Mount order is load-bearing (eng-review A-1 / N1):
    1. /api/* routers          → JSON endpoints
    2. /health                 → JSON health check
    3. (Phase 4 will add StaticFiles at / for the Astro-built frontend)

During Phase 1, hitting any non-/api path returns a 404 from FastAPI's default
handler; this is expected until Phase 4 mounts the static frontend.

No CORS middleware is installed — the frontend and API ship same-origin in
production (Phase 4). A test in ``tests/test_cors.py`` asserts no
Access-Control-* headers leak (eng-review SC-3 / N8).
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
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
    app = FastAPI(
        title="BGX Hard Enduro Dashboard API",
        description="Read-only JSON API for the BGX Hard Enduro Championship",
        version=APP_VERSION,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
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
    app.include_router(stats_api.router)
    app.include_router(track_api.router)

    return app


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

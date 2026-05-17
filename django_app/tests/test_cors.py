"""X2 — CORS-absence contract (Django port of backend/tests/test_cors.py).

Frontend and backend ship same-origin. If a future change accidentally adds
CORS middleware (allow_origins=["*"] or Django equivalent), these tests fail.
Zero Access-Control-* headers must ever ship.
"""

from django.test import Client

client = Client()


def test_no_cors_headers_on_api_response() -> None:
    # /api/openapi.json is the X2 gated-docs view (no DB, no Postgres needed)
    # and is the closest analogue to the FastAPI-provided openapi path the
    # original test used. STATS_PASSWORD is unset under the test harness, so
    # the dev-mode gate is open and this returns 200.
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    for header in response.headers:
        assert not header.lower().startswith("access-control-"), (
            f"Unexpected CORS header leaked: {header}"
        )


def test_no_cors_headers_on_health() -> None:
    response = client.get("/health")
    for header in response.headers:
        assert not header.lower().startswith("access-control-"), (
            f"Unexpected CORS header on /health: {header}"
        )


def test_options_preflight_not_enabled() -> None:
    """A preflight OPTIONS must NOT yield a generic 'allow all origins'
    response. Django gives the default no-CORS behavior; no
    access-control-allow-origin header may appear."""
    response = client.options(
        "/api/seasons",
        HTTP_ORIGIN="https://evil.example.com",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
    )
    assert "access-control-allow-origin" not in {
        k.lower() for k in response.headers
    }

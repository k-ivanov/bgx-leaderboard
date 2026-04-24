"""CORS-absence contract (eng-review SC-3 / N8).

Frontend and backend ship same-origin. If a future change accidentally adds
``CORSMiddleware(allow_origins=["*"])``, this test fails.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_no_cors_headers_on_api_response() -> None:
    # Use /api/openapi.json (FastAPI-provided, no DB access) so the test
    # doesn't require Postgres to verify CORS absence on an /api/* path.
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
    """Preflight requests get the default 405/no-handler behavior rather than
    a generic 'allow all origins' response."""
    response = client.options(
        "/api/seasons",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in {k.lower() for k in response.headers}

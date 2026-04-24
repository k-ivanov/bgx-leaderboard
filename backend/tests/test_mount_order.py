"""Mount-order contract tests (eng-review A-1 / N1).

The API routers must be matched BEFORE any eventual catch-all static mount.
Today there is no static mount; these tests lock in the behavior so that
when Phase 4 adds ``StaticFiles(html=True)`` at ``/``, a misordered mount
makes these fail immediately.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_api_nonexistent_returns_json_404() -> None:
    """``/api/definitely-not-a-real-endpoint`` must NOT fall through to any
    static handler; it must return a JSON 404 from FastAPI."""
    response = client.get("/api/definitely-not-a-real-endpoint")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert "detail" in body


def test_api_docs_served() -> None:
    """Swagger UI is available at /api/docs."""
    response = client.get("/api/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_api_openapi_served() -> None:
    """OpenAPI schema is served at /api/openapi.json — needed by
    openapi-typescript in Phase 2."""
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    body = response.json()
    assert body["info"]["title"] == "BGX Hard Enduro Dashboard API"


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "bgx-dashboard-api"

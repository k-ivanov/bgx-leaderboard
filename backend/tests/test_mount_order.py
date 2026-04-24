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


def test_api_routes_not_shadowed_by_static_mount(tmp_path, monkeypatch) -> None:
    """Even when the frontend static dist is mounted at /, /api/* must still
    match the routers. A misordering would route /api/seasons through static
    (404 on text/plain) instead of hitting the JSON handler.

    Simulates Phase 4 container layout: a populated frontend_dist pointed at
    via FRONTEND_DIST, a fresh app created with that dist mounted.
    """
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>root</title>", encoding="utf-8")
    (dist / "404.html").write_text("<!doctype html><title>404</title>", encoding="utf-8")

    monkeypatch.setenv("FRONTEND_DIST", str(dist))

    # Create a fresh app after the env var is set.
    from importlib import reload
    import app.main as main_module
    reload(main_module)

    from fastapi.testclient import TestClient
    test_client = TestClient(main_module.app)

    # /api/* still returns JSON 404
    r1 = test_client.get("/api/definitely-nonexistent")
    assert r1.status_code == 404
    assert r1.headers["content-type"].startswith("application/json")

    # A bare path falls through to the static mount's index.html
    r2 = test_client.get("/")
    assert r2.status_code == 200
    assert "text/html" in r2.headers["content-type"]

    # An unknown path serves 404.html with 404 status
    r3 = test_client.get("/does-not-exist")
    assert r3.status_code == 404
    assert "text/html" in r3.headers["content-type"]

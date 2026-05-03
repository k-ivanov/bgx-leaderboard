"""Pin baseline security headers (improvements.md P1 #11)."""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_carries_security_headers():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in res.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in res.headers["Content-Security-Policy"]
    assert "geolocation=()" in res.headers["Permissions-Policy"]


def test_api_carries_security_headers():
    # Pick any cheap GET endpoint.
    res = client.get("/api/seasons")
    # Status may be 200 (DB seeded) or 500 (no DB) — we only care that
    # the headers were applied.
    assert "X-Frame-Options" in res.headers


def test_hsts_only_on_https():
    # TestClient defaults to http://testserver, so HSTS should NOT appear.
    res = client.get("/health")
    assert "Strict-Transport-Security" not in res.headers

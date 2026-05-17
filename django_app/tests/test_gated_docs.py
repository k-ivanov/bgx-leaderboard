"""X2 — auth-gated /api/docs + /api/openapi.json
(parity with backend/app/main.py::_mount_gated_docs + backend/app/auth.py).

Contract (identical to the FastAPI app):
  * STATS_PASSWORD set    → 401 without creds, reachable with any non-empty
                            username + the password; wrong password → 401.
  * STATS_PASSWORD unset  → dev mode: open (no auth).
401 bodies + WWW-Authenticate header byte-match backend/app/auth.py.

``STATS_PASSWORD`` is read from ``settings`` at request time, so the
pytest-django ``settings`` fixture flips the gate per-test cleanly.
"""

import base64

from django.test import Client

client = Client()


def _basic(user: str, password: str) -> str:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return f"Basic {token}"


# --- STATS_PASSWORD SET → auth required ------------------------------------

class TestGatedWhenPasswordSet:
    def test_openapi_json_401_without_creds(self, settings):
        settings.STATS_PASSWORD = "s3cret"
        res = client.get("/api/openapi.json")
        assert res.status_code == 401
        assert res.json() == {"detail": "Not authenticated"}
        assert res.headers["WWW-Authenticate"] == 'Basic realm="stats"'

    def test_docs_401_without_creds(self, settings):
        settings.STATS_PASSWORD = "s3cret"
        res = client.get("/api/docs")
        assert res.status_code == 401
        assert res.json() == {"detail": "Not authenticated"}
        assert res.headers["WWW-Authenticate"] == 'Basic realm="stats"'

    def test_openapi_json_reachable_with_creds(self, settings):
        settings.STATS_PASSWORD = "s3cret"
        res = client.get(
            "/api/openapi.json",
            HTTP_AUTHORIZATION=_basic("anyuser", "s3cret"),
        )
        assert res.status_code == 200
        body = res.json()
        assert body["openapi"].startswith("3.")
        assert body["info"]["title"] == "BGX Hard Enduro Dashboard API"
        assert body["info"]["version"] == "0.1.0"

    def test_docs_reachable_with_creds(self, settings):
        settings.STATS_PASSWORD = "s3cret"
        res = client.get(
            "/api/docs",
            HTTP_AUTHORIZATION=_basic("anyuser", "s3cret"),
        )
        assert res.status_code == 200
        assert res.headers["Content-Type"].startswith("text/html")
        body = res.content.decode()
        assert "swagger-ui" in body
        assert "/api/openapi.json" in body  # UI points at the gated schema

    def test_username_not_checked(self, settings):
        settings.STATS_PASSWORD = "s3cret"
        # Any non-empty username + correct password is accepted (auth.py).
        res = client.get(
            "/api/openapi.json",
            HTTP_AUTHORIZATION=_basic("literally-anything", "s3cret"),
        )
        assert res.status_code == 200

    def test_wrong_password_401_invalid_credentials(self, settings):
        settings.STATS_PASSWORD = "s3cret"
        res = client.get(
            "/api/openapi.json",
            HTTP_AUTHORIZATION=_basic("anyuser", "wrong"),
        )
        assert res.status_code == 401
        assert res.json() == {"detail": "Invalid credentials"}
        assert res.headers["WWW-Authenticate"] == 'Basic realm="stats"'

    def test_malformed_authorization_header_401(self, settings):
        settings.STATS_PASSWORD = "s3cret"
        res = client.get(
            "/api/openapi.json",
            HTTP_AUTHORIZATION="Basic not-valid-base64!!",
        )
        assert res.status_code == 401
        assert res.json() == {"detail": "Not authenticated"}

    def test_non_basic_scheme_401(self, settings):
        settings.STATS_PASSWORD = "s3cret"
        res = client.get(
            "/api/openapi.json",
            HTTP_AUTHORIZATION="Bearer sometoken",
        )
        assert res.status_code == 401
        assert res.json() == {"detail": "Not authenticated"}


# --- STATS_PASSWORD UNSET → dev mode, open ---------------------------------

class TestOpenWhenPasswordUnset:
    def test_openapi_json_open_in_dev(self, settings):
        settings.STATS_PASSWORD = ""
        res = client.get("/api/openapi.json")
        assert res.status_code == 200
        assert res.json()["info"]["title"] == "BGX Hard Enduro Dashboard API"

    def test_docs_open_in_dev(self, settings):
        settings.STATS_PASSWORD = ""
        res = client.get("/api/docs")
        assert res.status_code == 200
        assert "swagger-ui" in res.content.decode()


# --- Gated docs still carry the X2 security headers -------------------------

def test_401_response_still_carries_security_headers(settings):
    settings.STATS_PASSWORD = "s3cret"
    res = client.get("/api/docs")
    assert res.status_code == 401
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in res.headers["Content-Security-Policy"]

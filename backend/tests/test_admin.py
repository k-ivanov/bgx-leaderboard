"""Admin panel contract tests.

Verifies:
  - `/admin` requires authentication (redirects to /admin/login when logged out).
  - With ADMIN_PASSWORD empty, no one can log in (explicit opt-out).
  - With ADMIN_PASSWORD set, correct credentials log in; wrong ones don't.
  - Authenticated users can hit a list view.
  - The static mount returns JSON 404 (not HTML) for /admin paths the admin
    sub-app doesn't match — the mount-order contract extends to /admin.
"""

import importlib

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.usefixtures("seeded_db")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_app_with_admin_password(monkeypatch: pytest.MonkeyPatch, password: str):
    """Rebuild the FastAPI app with a specific ADMIN_PASSWORD.

    The admin sub-app reads config at module-import time in some paths, so
    we patch the config module AND reload app.admin before rebuilding.
    """
    from app import config as config_module
    monkeypatch.setattr(config_module, "ADMIN_PASSWORD", password)

    # Re-import app.admin so its top-level reads of ADMIN_PASSWORD pick up
    # the patched value.
    import app.admin as admin_module
    importlib.reload(admin_module)

    import app.main as main_module
    importlib.reload(main_module)
    return main_module.app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_admin_root_redirects_to_login_when_logged_out(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _fresh_app_with_admin_password(monkeypatch, "correct-horse")
    client = TestClient(app, follow_redirects=False)

    r = client.get("/admin/")
    # sqladmin redirects unauthenticated users to /admin/login (302 or 307).
    assert r.status_code in (302, 303, 307), f"got {r.status_code}"
    assert "/admin/login" in r.headers["location"]


def test_admin_rejects_login_when_password_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit opt-out: if ADMIN_PASSWORD is empty, no login succeeds.
    This keeps admin *off* in Railway unless an operator set the env var.
    sqladmin returns 400 Bad Request on failed login (not a redirect)."""
    app = _fresh_app_with_admin_password(monkeypatch, "")
    client = TestClient(app, follow_redirects=False)

    r = client.post("/admin/login", data={"username": "admin", "password": "anything"})
    assert r.status_code == 400


def test_admin_login_succeeds_with_correct_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _fresh_app_with_admin_password(monkeypatch, "correct-horse")
    client = TestClient(app, follow_redirects=False)

    # Wrong password — 400 Bad Request.
    bad = client.post("/admin/login", data={"username": "admin", "password": "wrong"})
    assert bad.status_code == 400

    # Correct password — redirects to /admin/ with a session cookie.
    ok = client.post("/admin/login", data={"username": "admin", "password": "correct-horse"})
    assert ok.status_code in (302, 303, 307)
    set_cookie_values = ok.headers.get_list("set-cookie")
    assert any("session" in h.lower() for h in set_cookie_values), (
        f"expected a session cookie in Set-Cookie; got: {set_cookie_values}"
    )


def test_admin_list_view_accessible_after_login(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _fresh_app_with_admin_password(monkeypatch, "correct-horse")
    client = TestClient(app, follow_redirects=False)

    # Log in
    r = client.post("/admin/login", data={"username": "admin", "password": "correct-horse"})
    assert r.status_code in (302, 303, 307)

    # Hit the seasons list
    r = client.get("/admin/season/list")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_admin_path_mount_order_stays_consistent(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """A non-existent /admin path must NOT fall through to StaticFiles
    serving the front-end 404.html. Mount-order contract extends to /admin."""
    # Build a dummy dist with a 404.html so FrontendStatic can mount.
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>shell</html>", encoding="utf-8")
    (dist / "404.html").write_text("<html>motorsport 404</html>", encoding="utf-8")
    monkeypatch.setenv("FRONTEND_DIST", str(dist))

    app = _fresh_app_with_admin_password(monkeypatch, "correct-horse")
    client = TestClient(app, follow_redirects=False)

    # /admin/definitely-nothing should NOT serve motorsport 404.html — should
    # be JSON 404 via the admin-path guard in FrontendStatic.
    r = client.get("/admin/definitely-nothing")
    # Could be 404 from sqladmin itself OR from our JSON fallback. Either way,
    # it must not be the motorsport HTML 404.
    body = r.text
    assert "motorsport 404" not in body, f"Admin path leaked to static 404.html: {body[:200]}"

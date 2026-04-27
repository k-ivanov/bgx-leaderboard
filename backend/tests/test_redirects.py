"""Legacy URL → new shape 301 redirect contract.

Pinned by frontend-restructure.md §T2. Old per-year URLs were public for
months; these redirects preserve link equity (search engines, bookmarks,
shared links) when the frontend collapses to /results + /rider/{slug}.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _get_no_redirect(path: str):
    return client.get(path, follow_redirects=False)


def test_year_landing_redirects() -> None:
    r = _get_no_redirect("/2025")
    assert r.status_code == 301
    assert r.headers["location"] == "/results?season=2025"


def test_leaderboard_redirects() -> None:
    r = _get_no_redirect("/2025/expert")
    assert r.status_code == 301
    assert r.headers["location"] == "/results?season=2025&category=expert"


def test_race_results_redirects() -> None:
    r = _get_no_redirect("/2025/expert/buhovo")
    assert r.status_code == 301
    assert r.headers["location"] == "/results?season=2025&category=expert&race=buhovo"


def test_events_list_redirects() -> None:
    r = _get_no_redirect("/2025/events")
    assert r.status_code == 301
    assert r.headers["location"] == "/results?season=2025"


def test_event_detail_redirects() -> None:
    r = _get_no_redirect("/2025/events/buhovo")
    assert r.status_code == 301
    assert r.headers["location"] == "/results?season=2025&race=buhovo"


def test_rider_profile_redirects_drops_year_and_number() -> None:
    r = _get_no_redirect("/2025/r/255/димитър-тинчев")
    assert r.status_code == 301
    # The slug is URL-encoded in the Location header (Cyrillic chars).
    assert r.headers["location"].startswith("/rider/")
    assert "%D0%B4%D0%B8%D0%BC%D0%B8%D1%82%D1%8A%D1%80" in r.headers["location"]


def test_rider_disambig_returns_404() -> None:
    r = _get_no_redirect("/2025/r/255")
    assert r.status_code == 404


def test_api_paths_not_caught_by_year_redirect() -> None:
    """The {year} pattern must not steal /api/* — registered after API routers."""
    r = client.get("/api/seasons")
    assert r.status_code == 200


def test_health_path_not_caught() -> None:
    r = client.get("/health")
    assert r.status_code == 200


def test_non_int_year_path_not_redirected() -> None:
    """Non-numeric first segment (e.g. /results, /rider) must NOT match {year}.

    FastAPI rejects ``ge=1900`` validation, returning 422 — confirming the
    redirect didn't fire. In production StaticFiles would serve /results
    from dist/ first because routes are tried in mount order.
    """
    r = _get_no_redirect("/abcd")
    # 422 from path validation OR 404 from the catch-all — anything except
    # a 301 to /results is acceptable here.
    assert r.status_code != 301

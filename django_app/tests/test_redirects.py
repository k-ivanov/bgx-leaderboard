"""Legacy URL → new shape 301 redirect contract (X1 — ported parity).

1:1 port of ``backend/tests/test_redirects.py`` (the FROZEN FastAPI oracle)
adapted to the Django test client. Old per-year URLs were public + indexed
for months; these redirects preserve link equity (search engines, bookmarks,
shared links) when the frontend collapsed to /results + /rider/{slug}.

Pinned by frontend-restructure.md §T2 and CLAUDE.md invariant #3. Every
assertion below was verified byte-identical against the live FastAPI app
(`backend/app/redirects.py`) before porting.

These tests exercise pure URL routing — no DB needed. The Django test client
does NOT follow redirects by default, so we assert the 301 + Location
directly (parity with the FastAPI ``follow_redirects=False`` helper).
"""

from django.test import Client

client = Client()


def _get(path: str):
    """GET without following redirects (Django default)."""
    return client.get(path)


def test_year_landing_redirects() -> None:
    r = _get("/2025")
    assert r.status_code == 301
    assert r.headers["Location"] == "/results?season=2025"


def test_leaderboard_redirects() -> None:
    r = _get("/2025/expert")
    assert r.status_code == 301
    assert r.headers["Location"] == "/results?season=2025&category=expert"


def test_race_results_redirects() -> None:
    r = _get("/2025/expert/buhovo")
    assert r.status_code == 301
    assert r.headers["Location"] == "/results?season=2025&category=expert&race=buhovo"


def test_events_list_redirects_to_races_calendar() -> None:
    r = _get("/2025/events")
    assert r.status_code == 301
    assert r.headers["Location"] == "/races?season=2025"


def test_event_detail_redirects_to_races_slug() -> None:
    r = _get("/2025/events/buhovo")
    assert r.status_code == 301
    # Year is dropped — /races/{slug} defaults to most recent for the slug.
    assert r.headers["Location"] == "/races/buhovo"


def test_rider_profile_redirects_drops_year_and_number() -> None:
    r = _get("/2025/r/255/димитър-тинчев")
    assert r.status_code == 301
    # The slug is URL-encoded in the Location header (Cyrillic chars) — must
    # be byte-identical to the FastAPI quote(slug, safe='') output.
    loc = r.headers["Location"]
    assert loc.startswith("/rider/")
    assert "%D0%B4%D0%B8%D0%BC%D0%B8%D1%82%D1%8A%D1%80" in loc
    # Full byte-for-byte parity with the oracle's Location header.
    assert loc == (
        "/rider/%D0%B4%D0%B8%D0%BC%D0%B8%D1%82%D1%8A%D1%80"
        "-%D1%82%D0%B8%D0%BD%D1%87%D0%B5%D0%B2"
    )


def test_rider_disambig_returns_404() -> None:
    r = _get("/2025/r/255")
    assert r.status_code == 404


def test_rider_profile_race_number_zero_redirects() -> None:
    """FastAPI Path(ge=0) accepts race_number 0 → still a 301 (parity)."""
    r = _get("/2025/r/0/x")
    assert r.status_code == 301
    assert r.headers["Location"] == "/rider/x"


def test_rider_profile_negative_race_number_not_redirected() -> None:
    """A negative race_number never matched FastAPI Path(ge=0) — 404, not 301."""
    r = _get("/2025/r/-1/x")
    assert r.status_code != 301


def test_api_paths_not_caught_by_year_redirect() -> None:
    """The {year} pattern must not steal /api/* — the FROZEN urls.py mounts
    the NinjaAPI before the legacy 301s, so /api/* never 301s to /results.

    (The oracle hit a live /api/seasons; here the S1 router is an empty F1
    stub, so the equivalent invariant is: /api/* returns the API's own JSON
    404, NOT a 301 redirect to /results.)
    """
    r = client.get("/api/seasons")
    assert r.status_code != 301
    assert r.status_code == 404
    assert r.headers["Content-Type"].startswith("application/json")


def test_health_path_not_caught() -> None:
    r = client.get("/health")
    assert r.status_code == 200


def test_non_int_year_path_not_redirected() -> None:
    """Non-numeric first segment (e.g. /results, /rider) must NOT match {year}.

    FastAPI rejected ``ge=1900`` validation (422); the Django re_path simply
    does not match and the request falls through to the static catch-all.
    Anything except a 301 to /results is acceptable here (parity with the
    oracle's ``status_code != 301`` assertion).
    """
    r = _get("/abcd")
    assert r.status_code != 301


def test_out_of_range_year_not_redirected() -> None:
    """Years outside 1900–2100 (FastAPI Path(ge=1900, le=2100)) must NOT 301.

    The oracle returned 422; the Django year regex (19xx|20xx|2100) simply
    does not match, so these fall through — never a 301 to /results.
    """
    for path in ("/1899", "/2101", "/3000"):
        r = _get(path)
        assert r.status_code != 301, f"{path} unexpectedly 301'd"


def test_trailing_slash_year_not_redirected() -> None:
    """``/2025/`` did not match FastAPI's strict ``/{year:int}`` route (no
    APPEND_SLASH). Django (APPEND_SLASH=False, frozen by F1) must likewise
    NOT 301 the trailing-slash form to /results."""
    r = _get("/2025/")
    assert r.status_code != 301

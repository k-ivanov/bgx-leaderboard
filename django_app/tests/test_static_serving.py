"""X1 static-serving acceptance tests (ported FrontendStatic behavior).

These cover the X1 acceptance criteria that have no direct
``backend/tests`` counterpart but pin the ``FrontendStatic`` behavior from
``backend/app/main.py`` (verified byte-identical against the live FastAPI
oracle before porting):

  • directory-index served WITHOUT a 307/301 trailing-slash redirect
    (preserves the indexed no-trailing-slash URL shape — the SEO contract);
  • ``robots.txt`` / ``sitemap-index.xml`` / ``404.html`` served
    byte-identical with the correct status (404.html → real 404 *as the
    fallback*; a direct GET /404.html is a real file → 200, matching the
    oracle);
  • unmatched ``/api/*`` → JSON ``{"detail": "Not Found"}`` (never HTML);
  • a path-traversal attempt → JSON 404, never escapes the dist root.

A throwaway fixture ``dist/`` is built per test (FRONTEND_DIST → temp dir);
the real Astro site is intentionally NOT built.
"""

import os
from contextlib import contextmanager

import pytest
from django.test import Client

client = Client()

ROOT_HTML = "<!doctype html><title>root</title>"
RESULTS_HTML = "<!doctype html><title>results</title>"
EXPERT_HTML = "<!doctype html><title>2026 expert</title>"
NOT_FOUND_HTML = "<!doctype html><title>404 — not found</title>"
ROBOTS_TXT = "User-agent: *\nDisallow:\nSitemap: /sitemap-index.xml\n"
SITEMAP_XML = '<?xml version="1.0" encoding="UTF-8"?><sitemapindex></sitemapindex>'


@contextmanager
def fixture_dist(tmp_path):
    """Build a minimal Astro-like dist/ and point FRONTEND_DIST at it."""
    dist = tmp_path / "dist"
    (dist / "results").mkdir(parents=True)
    (dist / "2026" / "expert").mkdir(parents=True)
    (dist / "index.html").write_text(ROOT_HTML, encoding="utf-8")
    (dist / "results" / "index.html").write_text(RESULTS_HTML, encoding="utf-8")
    (dist / "2026" / "expert" / "index.html").write_text(
        EXPERT_HTML, encoding="utf-8"
    )
    (dist / "404.html").write_text(NOT_FOUND_HTML, encoding="utf-8")
    (dist / "robots.txt").write_text(ROBOTS_TXT, encoding="utf-8")
    (dist / "sitemap-index.xml").write_text(SITEMAP_XML, encoding="utf-8")

    old = os.environ.get("FRONTEND_DIST")
    os.environ["FRONTEND_DIST"] = str(dist)
    try:
        yield dist
    finally:
        if old is None:
            os.environ.pop("FRONTEND_DIST", None)
        else:
            os.environ["FRONTEND_DIST"] = old


def _body(resp) -> bytes:
    return b"".join(resp.streaming_content) if resp.streaming else resp.content


def test_directory_index_no_slash_redirect(tmp_path) -> None:
    """A directory path WITHOUT a trailing slash serves its index.html with
    200 and issues NO 301/307 slash redirect — the SEO-critical behavior that
    preserves the months-indexed no-trailing-slash URL shape.

    NOTE on the acceptance wording '/2026/expert serves index 200': the bare
    ``/2026/expert`` matches the legacy ``/{year}/{category}`` 301 pattern
    (it 301s to /results — see test_redirects), so the directory-index
    mechanism is exercised here with ``/results`` (no slash) and the
    trailing-slash ``/2026/expert/`` form, both of which reach the catch-all.
    This is faithful to the FastAPI oracle, where the redirect router is
    likewise mounted before StaticFiles.
    """
    with fixture_dist(tmp_path):
        r = client.get("/results")
        assert r.status_code == 200, "no-slash directory must serve index, not 404"
        assert "Location" not in r.headers, "must NOT issue a slash redirect"
        assert "text/html" in r.headers["Content-Type"]
        assert _body(r) == RESULTS_HTML.encode("utf-8")

        # The /2026/expert/ trailing-slash form is NOT a legacy redirect
        # pattern, so it reaches the catch-all and serves the dir index 200.
        r2 = client.get("/2026/expert/")
        assert r2.status_code == 200
        assert "Location" not in r2.headers
        assert _body(r2) == EXPERT_HTML.encode("utf-8")


def test_bare_legacy_2026_expert_still_301s(tmp_path) -> None:
    """Faithful-to-oracle counterpart: with a dist present, ``/2026/expert``
    (no slash) still 301s via the legacy pattern — the redirect band is
    mounted BEFORE the static catch-all (CLAUDE.md invariant #4)."""
    with fixture_dist(tmp_path):
        r = client.get("/2026/expert")
        assert r.status_code == 301
        assert r.headers["Location"] == "/results?season=2026&category=expert"


def test_robots_txt_byte_identical(tmp_path) -> None:
    with fixture_dist(tmp_path):
        r = client.get("/robots.txt")
        assert r.status_code == 200
        assert r.headers["Content-Type"].startswith("text/plain")
        assert _body(r) == ROBOTS_TXT.encode("utf-8")


def test_sitemap_index_byte_identical(tmp_path) -> None:
    with fixture_dist(tmp_path):
        r = client.get("/sitemap-index.xml")
        assert r.status_code == 200
        assert "xml" in r.headers["Content-Type"]
        assert _body(r) == SITEMAP_XML.encode("utf-8")


def test_404_html_as_fallback_has_real_404_status(tmp_path) -> None:
    """An unknown path serves the 404.html *content* with a real 404 status
    (SPA-style fallback) — byte-identical to the on-disk 404.html."""
    with fixture_dist(tmp_path):
        r = client.get("/this-page-does-not-exist")
        assert r.status_code == 404
        assert "text/html" in r.headers["Content-Type"]
        assert _body(r) == NOT_FOUND_HTML.encode("utf-8")


def test_direct_get_404_html_is_200(tmp_path) -> None:
    """A direct GET /404.html is a real file on disk → 200 (parity with the
    FastAPI oracle, where StaticFiles serves the existing file as 200). The
    'real 404 status' criterion applies to the *fallback* path above."""
    with fixture_dist(tmp_path):
        r = client.get("/404.html")
        assert r.status_code == 200
        assert _body(r) == NOT_FOUND_HTML.encode("utf-8")


def test_root_serves_index(tmp_path) -> None:
    with fixture_dist(tmp_path):
        r = client.get("/")
        assert r.status_code == 200
        assert _body(r) == ROOT_HTML.encode("utf-8")


def test_unmatched_api_returns_json_not_found(tmp_path) -> None:
    """Unmatched /api/* → JSON {"detail": "Not Found"}, never HTML/404.html.

    Covers both the catch-all guard (``/api`` no-slash edge) and an
    unmatched /api/ sub-path.

    NOTE: the previous ``/api/seasons/999`` example was replaced — F3 filled
    the worked reference endpoint (``api/seasons.py``), so ``/api/seasons/999``
    is now a VALIDATED route returning 422 (year < the YearPath ge=1900
    bound — byte-parity with the FastAPI oracle, which also 422s it), NOT an
    "unmatched" path. ``/api/nope/also-missing`` is a genuinely unmatched
    /api/ sub-path and exercises the same X1 catch-all JSON-404 guard this
    test protects."""
    with fixture_dist(tmp_path):
        for path in ("/api", "/api/", "/api/nope", "/api/nope/also-missing"):
            r = client.get(path)
            assert r.status_code == 404, f"{path} should be 404"
            assert r.headers["Content-Type"].startswith(
                "application/json"
            ), f"{path} must be JSON, not HTML"
            assert r.json() == {"detail": "Not Found"}, f"{path} body parity"


def test_unmatched_admin_bare_returns_json_404(tmp_path) -> None:
    """The X1 catch-all admin guard: ``/admin`` (no trailing slash) does not
    match the FROZEN ``path("admin/", ...)`` slot, so it falls through to the
    catch-all and gets the JSON 404 guard (parity with FrontendStatic's
    ``path == "admin"`` branch). Deeper ``/admin/*`` paths are intercepted by
    the F1-wired Django admin (X3's domain), not X1's catch-all."""
    with fixture_dist(tmp_path):
        r = client.get("/admin")
        assert r.status_code == 404
        assert r.headers["Content-Type"].startswith("application/json")
        assert r.json() == {"detail": "Not Found"}


def test_path_traversal_blocked(tmp_path) -> None:
    """A path that resolves outside the dist root → JSON 404, never serves a
    file outside dist (parity with FrontendStatic's relative_to guard)."""
    with fixture_dist(tmp_path) as dist:
        secret = dist.parent / "secret.txt"
        secret.write_text("TOP SECRET — must never be served", encoding="utf-8")

        for attack in (
            "/results/../../secret.txt",
            "/../secret.txt",
            "/%2e%2e/secret.txt",
        ):
            r = client.get(attack)
            assert r.status_code == 404, f"{attack} must not 200"
            body = _body(r)
            assert b"TOP SECRET" not in body, f"{attack} leaked file outside dist"


def test_no_dist_non_api_path_404(tmp_path) -> None:
    """With no resolvable dist (FRONTEND_DIST unset / not a dir), a
    non-api/admin path 404s — the FastAPI app likewise ran API-only with no
    StaticFiles mounted."""
    old = os.environ.get("FRONTEND_DIST")
    os.environ["FRONTEND_DIST"] = str(tmp_path / "does-not-exist")
    try:
        r = client.get("/some-frontend-route")
        assert r.status_code == 404
    finally:
        if old is None:
            os.environ.pop("FRONTEND_DIST", None)
        else:
            os.environ["FRONTEND_DIST"] = old

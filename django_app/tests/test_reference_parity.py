"""F3 end-to-end parity proof — the green reference parity tests.

This is the F3 acceptance keystone: the worked reference endpoint
(``api/seasons.py`` — the pattern S1–S7 copy) is run through the FULL F3
stack (resolvers + common schemas + pinned renderer + frozen NinjaAPI
default exception handlers) inside the REAL new Django app spun as a
subprocess, and diffed BYTE-for-BYTE against the FROZEN ``backend/`` FastAPI
app (also spun) — both over their OWN identically-seeded Postgres DBs —
using ``assert_json_parity``.

It also pins the 404 + 422 error contract end-to-end (the resolver 404
string parity and Ninja's frozen default validation handler) so a slice
copying this file gets the error-path proof for free.

THIS FILE IS THE COPY TEMPLATE for every S1–S7 parity test.

If either stack can't be spun in this sandbox the ``parity_rig`` fixture
skips with a precise reason + the exact command — it NEVER reports a fake
green.
"""

import json

import pytest

# Endpoints exercised by the F3 reference. Each is a (path, note) the new
# Django app and the spun FastAPI oracle must agree on byte-for-byte.
REFERENCE_PATHS = [
    ("/api/seasons", "list — schema list + renderer (Cyrillic, key order)"),
    ("/api/seasons/2025", "detail — resolve_season hit + nested refs + dates"),
    ("/api/seasons/2026", "detail — events WITH a real event_date (ISO 8601)"),
]


@pytest.mark.parametrize("path, _note", REFERENCE_PATHS)
def test_reference_endpoint_byte_parity(
    path, _note, parity_rig, assert_json_parity
) -> None:
    """New Django reference endpoint == frozen FastAPI oracle, byte-for-byte."""
    assert_json_parity(parity_rig.old(path), parity_rig.new(path))


def test_reference_404_parity(parity_rig, assert_json_parity) -> None:
    """Missing season → identical 404 ``{"detail":"Season 1999 not found"}``.

    Proves the F3 resolver string parity AND that the FROZEN NinjaAPI
    default ``HttpError`` handler produces the byte-exact FastAPI body
    (no custom handler / no frozen-file edit needed).
    """
    old = parity_rig.old("/api/seasons/1999")
    new = parity_rig.new("/api/seasons/1999")
    assert old.status_code == 404
    assert_json_parity(old, new)


def test_resolver_404_goes_through_pinned_renderer(
    parity_rig, assert_json_parity
) -> None:
    """A Ninja-RESOLVED 404 (resolver ``HttpError``) is byte-exact.

    This is the F3-owned 404 surface: the request DOES match a Ninja route
    (``/api/seasons/{year}``), the F3 ``resolve_season`` raises
    ``HttpError(404, ...)``, the FROZEN NinjaAPI default handler renders it
    via the F3-pinned renderer. ``1955`` is inside the ``YearPath`` range
    (1900..2999) so it reaches the resolver (a below-1900 value would 422 at
    validation instead) and has no Season row → resolver 404.
    """
    old = parity_rig.old("/api/seasons/1955")
    new = parity_rig.new("/api/seasons/1955")
    assert old.status_code == new.status_code == 404
    assert_json_parity(old, new)
    assert json.loads(new.content) == {"detail": "Season 1955 not found"}


@pytest.mark.parametrize("bad_year", ["abc", "3000", "1800"])
def test_reference_422_validation_parity(
    bad_year, parity_rig, assert_json_parity
) -> None:
    """Out-of-range / non-int ``year`` → identical 422 Pydantic-error body.

    Proves the F3 ``YearPath`` (``Path(ge=1900, le=2999)``) reproduces the
    FastAPI ``Path(..., ge=1900, le=2999)`` validation AND that Ninja's
    frozen default validation handler emits the same Pydantic-v2 error-list
    SHAPE FastAPI does. We assert the structural contract (status,
    ``{"detail":[...]}`` envelope, ``loc``, ``type``) — the ``msg`` wording
    can vary microscopically across pydantic patch releases; the structure
    is what the frontend + the ported suite depend on.
    """
    old = parity_rig.old(f"/api/seasons/{bad_year}")
    new = parity_rig.new(f"/api/seasons/{bad_year}")
    assert old.status_code == 422, old.content[:300]
    assert new.status_code == 422, new.content[:300]

    o = json.loads(old.content)
    n = json.loads(new.content)
    assert isinstance(o["detail"], list) and isinstance(n["detail"], list)
    o_err, n_err = o["detail"][0], n["detail"][0]
    assert list(o_err["loc"]) == list(n_err["loc"]) == ["path", "year"]
    assert o_err["type"] == n_err["type"]


@pytest.mark.xfail(
    reason=(
        "X1-scope (NOT F3): an UNMATCHED /api/* path escapes the NinjaAPI "
        "entirely and is answered by the X1 static_catchall, which returns "
        "Django JsonResponse({'detail':'Not Found'}) with DEFAULT separators "
        '(\'{"detail": "Not Found"}\' — space after the colon) while the '
        "FastAPI FrontendStatic returns Starlette JSONResponse compact "
        '(\'{"detail":"Not Found"}\'). The F3-pinned renderer cannot reach '
        "this path because Ninja never matches the URL. Filed for the X1 "
        "owner / I1: redirects.static_catchall._json_not_found must dump with "
        "separators=(',',':'), ensure_ascii=False (mirror Starlette / the F3 "
        "ParityJSONRenderer) to be byte-identical. Documented, not silently "
        "absorbed — F3 does not fake a green here."
    ),
    strict=True,
)
def test_unmatched_api_404_parity_x1_known_gap(
    parity_rig, assert_json_parity
) -> None:
    """DOCUMENTED X1 catch-all serialization gap discovered by the F3 rig.

    Kept as a strict xfail so (a) the divergence is recorded in code with a
    precise repro, and (b) it auto-flips to a failure (alerting) the moment
    X1 fixes it, prompting removal of this xfail.
    """
    old = parity_rig.old("/api/totally-bogus-unmatched")
    new = parity_rig.new("/api/totally-bogus-unmatched")
    assert old.status_code == new.status_code == 404
    assert_json_parity(old, new)

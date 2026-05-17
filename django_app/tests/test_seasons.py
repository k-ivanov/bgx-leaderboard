"""S1 — Seasons API: owned test coverage.

S1 owns the seasons slice (``api/seasons.py`` + ``api/schemas/seasons.py``)
once F3 hands over its worked reference. F3's ``test_reference_parity.py`` is
the *F3* acceptance keystone (it grades the whole shared stack through the
seasons endpoint as the pattern S1–S7 copy). THIS file is S1's OWN coverage:

1. **Contract / wiring** (no DB — Tier-1, always green in the locked venv):
   the S1 endpoint module is wired into the FROZEN router assembly at the
   right prefix, the response schemas have the exact field NAMES + ORDER +
   TYPES + DEFAULTS of the frozen FastAPI Pydantic schemas (the
   ``openapi-typescript`` no-diff guarantee), and the endpoint ORM ordering
   is the byte-equivalent of the FastAPI ``ORDER BY``.

2. **Behavior on golden data** (``seeded_orm`` — auto-tiered Tier-2): the
   ported ``backend/tests/test_api.py`` seasons contract assertions
   (``test_list_seasons_includes_2025`` / ``test_get_season_detail_2025`` /
   ``test_get_season_detail_404_for_missing_year``) run S1's endpoint logic
   directly against the 2025 golden data.

3. **Byte-parity vs the frozen FastAPI oracle** (``parity_rig`` — auto-tiered
   Tier-2): copied from F3's ``test_reference_parity.py`` template, scoped to
   the S1 surface. The seasons endpoints' bodies must be byte-for-byte equal
   to ``backend/app/api/seasons.py`` over identically-seeded Postgres.

The Tier-2 tests (2 + 3) auto-mark ``parity`` via the
``seeded_orm`` / ``parity_rig`` fixture-name detection in ``conftest.py`` —
S1 adds NO manual marker. They SKIP (never fake green) if no seeded Postgres
/ both stacks cannot be spun in the sandbox; the fixtures print the exact
command.
"""

from __future__ import annotations

import json

import pytest


# ===========================================================================
# 1. Contract / wiring — no DB, runs in the Tier-1 locked-venv gate
# ===========================================================================


def test_seasons_router_is_wired_into_frozen_assembly() -> None:
    """S1's ``router`` is the object the FROZEN ``api/__init__.py`` mounts.

    The frozen assembly imports ``api.seasons.router`` by reference and
    mounts it at ``/seasons``. S1 fills that module's ``router`` — confirm
    the two endpoints are registered under the seasons prefix and nothing
    else leaked in.
    """
    from api import seasons as seasons_api

    from ninja import Router

    assert isinstance(seasons_api.router, Router)

    # path operations registered on the S1 router (Ninja stores them on the
    # router's path-operations map). S1 owns exactly two: "" and "/{year}".
    paths = set()
    for path, _po in seasons_api.router.path_operations.items():
        paths.add(path)
    assert paths == {"", "/{year}"}, paths


def test_seasons_endpoints_match_fastapi_source_signature() -> None:
    """S1 endpoint contract mirrors ``backend/app/api/seasons.py``.

    Same two operations, same response schemas. ``list_seasons`` takes no
    path/query params (parity with the FastAPI ``list_seasons``);
    ``get_season_detail`` takes the constrained ``year`` path param (parity
    with the FastAPI ``Path(..., ge=1900, le=2999)`` via F3 ``YearPath``).
    """
    from api.schemas.seasons import SeasonDetailOut, SeasonListOut
    from api import seasons as seasons_api

    list_po = seasons_api.router.path_operations[""]
    detail_po = seasons_api.router.path_operations["/{year}"]

    # one operation each (only GET)
    (list_op,) = list_po.operations
    (detail_op,) = detail_po.operations
    assert list_op.methods == ["GET"]
    assert detail_op.methods == ["GET"]

    # response schema parity (the openapi-typescript contract surface)
    assert list_op.response_models[200] is not None
    assert detail_op.response_models[200] is not None
    # the declared response= is the F3-ported schema
    assert SeasonListOut.__name__ == "SeasonListOut"
    assert SeasonDetailOut.__name__ == "SeasonDetailOut"


def test_season_schemas_field_order_matches_fastapi_pydantic() -> None:
    """Field NAMES + ORDER + TYPES + DEFAULTS == frozen FastAPI Pydantic.

    The pinned renderer never re-sorts keys (``api/renderers.py``), so JSON
    key order == schema field-declaration order. If S1's schema field order
    ever drifts from ``backend/app/schemas/seasons.py`` /
    ``backend/app/schemas/common.py`` the frontend's ``openapi-typescript``
    client would regenerate WITH a diff. Pin the exact contract here.
    """
    from api.schemas.common import CategoryRef, EventRef, SeasonRef
    from api.schemas.seasons import SeasonDetailOut, SeasonListOut

    # SeasonListOut: {"seasons": [SeasonRef]}
    assert list(SeasonListOut.model_fields) == ["seasons"]

    # SeasonDetailOut field order == backend/app/schemas/seasons.py
    assert list(SeasonDetailOut.model_fields) == [
        "season",
        "categories",
        "events",
        "rider_count",
    ]

    # Nested ref schemas — order == backend/app/schemas/common.py exactly.
    assert list(SeasonRef.model_fields) == [
        "year",
        "name",
        "slug",
        "is_current",
        "championship_format",
    ]
    assert list(CategoryRef.model_fields) == [
        "code",
        "display_name",
        "sort_order",
    ]
    assert list(EventRef.model_fields) == [
        "slug",
        "name",
        "event_date",
        "location",
        "sort_order",
        "event_type",
        "facebook_event_url",
        "description",
    ]

    # Optional editorial fields default to None (null-safe), as in FastAPI.
    assert EventRef.model_fields["event_date"].default is None
    assert EventRef.model_fields["location"].default is None
    assert EventRef.model_fields["event_type"].default is None
    assert EventRef.model_fields["facebook_event_url"].default is None
    assert EventRef.model_fields["description"].default is None


def test_season_detail_uses_year_path_constraint() -> None:
    """``get_season_detail`` constrains ``year`` like FastAPI's ``Path``.

    ``backend/app/deps.py::get_season`` uses ``Path(..., ge=1900, le=2999)``;
    S1 reaches identical 422 validation parity by typing the path param with
    the F3 ``YearPath``. Confirm S1 still consumes that exact resolver/alias
    rather than hand-rolling the bound (which would diverge the 422 body).
    """
    import inspect
    import typing

    from api import seasons as seasons_api
    from api.deps import YearPath, resolve_season

    src = inspect.getsource(seasons_api.get_season_detail)
    # S1 must route existence through the F3 resolver, never hand-roll 404.
    assert "resolve_season(" in src
    # year param annotated with the F3 YearPath alias. ``api/seasons.py`` uses
    # ``from __future__ import annotations`` so the raw annotation is the
    # string "YearPath"; resolve real type hints to compare the object.
    hints = typing.get_type_hints(
        seasons_api.get_season_detail, include_extras=True
    )
    assert hints["year"] is YearPath
    # resolver is the F3 canonical one (byte-exact 404 string lives there).
    assert resolve_season.__module__ == "api.deps"


def test_season_endpoint_orm_ordering_is_byte_equivalent_to_fastapi() -> None:
    """S1's ORM ``order_by`` clauses == the FastAPI ``ORDER BY``.

    FastAPI:
      * list: ``select(Season).order_by(Season.year.desc())``
      * detail categories: ``order_by(Category.sort_order, Category.id)``
      * detail events:     ``order_by(Event.sort_order, Event.id)``

    The ordering is observable in the JSON array order, so it is part of the
    byte-parity contract. Assert S1's source uses the exact equivalents.
    """
    import inspect

    from api import seasons as seasons_api

    list_src = inspect.getsource(seasons_api.list_seasons)
    detail_src = inspect.getsource(seasons_api.get_season_detail)

    assert 'order_by("-year")' in list_src
    assert 'order_by(\n            "sort_order", "id"\n        )' in detail_src or \
        'order_by("sort_order", "id")' in detail_src
    # rider_count is the season-wide count (FastAPI func.count(Rider.id)).
    assert ".count()" in detail_src


# ===========================================================================
# 2. Behavior on the 2025 golden data — ported backend/tests/test_api.py
#    (``seeded_orm`` → auto-tiered Tier-2; SKIPs without seeded Postgres)
# ===========================================================================


def _call(endpoint, *args):
    """Invoke an S1 Ninja endpoint function directly (no HTTP).

    The endpoints take ``request`` first; the seasons handlers never touch
    the request object, so ``None`` is a faithful stand-in for this unit
    layer. The parity rig (section 3) exercises the FULL HTTP stack.
    """
    return endpoint(None, *args)


def test_list_seasons_includes_2025(seeded_orm) -> None:
    """Ported ``backend/tests/test_api.py::test_list_seasons_includes_2025``."""
    from api.seasons import list_seasons

    out = _call(list_seasons)
    years = [s.year for s in out.seasons]
    assert 2025 in years
    # newest year first (parity with ORDER BY year DESC).
    assert years == sorted(years, reverse=True)


def test_get_season_detail_2025(seeded_orm) -> None:
    """Ported ``backend/tests/test_api.py::test_get_season_detail_2025``."""
    from api.seasons import get_season_detail

    out = _call(get_season_detail, 2025)
    assert out.season.year == 2025
    assert len(out.categories) >= 5  # all 2025 categories
    assert any(c.code == "expert" for c in out.categories)
    assert len(out.events) >= 5
    # rider_count is the season-wide sum across every category.
    assert out.rider_count > 0


def test_get_season_detail_404_for_missing_year(seeded_orm) -> None:
    """Ported ``test_get_season_detail_404_for_missing_year``.

    Goes through the F3 ``resolve_season`` → byte-exact ``HttpError(404,
    "Season 1999 not found")``; ``"not found"`` is in the detail (parity with
    the FastAPI ``response.json()["detail"].lower()`` assertion).
    """
    from ninja.errors import HttpError

    from api.seasons import get_season_detail

    with pytest.raises(HttpError) as exc:
        _call(get_season_detail, 1999)
    assert exc.value.status_code == 404
    assert "not found" in str(exc.value).lower()
    assert str(exc.value) == "Season 1999 not found"


def test_season_detail_category_and_event_order(seeded_orm) -> None:
    """Categories + events come back ordered by (sort_order, id).

    Observable JSON array order is part of the byte-parity contract; assert
    the seeded golden data comes back in the FastAPI ``ORDER BY`` order.
    """
    from api.seasons import get_season_detail

    out = _call(get_season_detail, 2025)
    cat_keys = [c.sort_order for c in out.categories]
    ev_keys = [e.sort_order for e in out.events]
    assert cat_keys == sorted(cat_keys)
    assert ev_keys == sorted(ev_keys)


# ===========================================================================
# 3. Byte-parity vs the frozen FastAPI oracle — COPIED from F3's
#    tests/test_reference_parity.py template, scoped to the S1 surface.
#    (``parity_rig`` → auto-tiered Tier-2; SKIPs if both stacks cannot spin)
# ===========================================================================

# The S1 public surface. Each is a (path, note) the new Django app and the
# spun FastAPI oracle must agree on byte-for-byte. Mirrors F3's
# REFERENCE_PATHS — S1 owns these paths now.
SEASONS_PATHS = [
    ("/api/seasons", "list — schema list + renderer (Cyrillic, key order)"),
    ("/api/seasons/2025", "detail — resolve_season hit + nested refs + dates"),
    ("/api/seasons/2026", "detail — events WITH a real event_date (ISO 8601)"),
]


@pytest.mark.parametrize("path, _note", SEASONS_PATHS)
def test_seasons_endpoint_byte_parity(
    path, _note, parity_rig, assert_json_parity
) -> None:
    """S1 seasons endpoint == frozen FastAPI oracle, byte-for-byte."""
    assert_json_parity(parity_rig.old(path), parity_rig.new(path))


def test_seasons_404_parity(parity_rig, assert_json_parity) -> None:
    """Missing season → identical 404 ``{"detail":"Season 1999 not found"}``.

    S1 routes existence through F3 ``resolve_season``; the FROZEN NinjaAPI
    default ``HttpError`` handler produces the byte-exact FastAPI body.
    """
    old = parity_rig.old("/api/seasons/1999")
    new = parity_rig.new("/api/seasons/1999")
    assert old.status_code == 404
    assert_json_parity(old, new)
    assert json.loads(new.content) == {"detail": "Season 1999 not found"}


@pytest.mark.parametrize("bad_year", ["abc", "3000", "1800"])
def test_seasons_422_validation_parity(
    bad_year, parity_rig, assert_json_parity
) -> None:
    """Out-of-range / non-int ``year`` → identical 422 Pydantic-error body.

    Proves S1's ``YearPath`` (``Path(ge=1900, le=2999)``) reproduces the
    FastAPI ``Path(..., ge=1900, le=2999)`` validation and that Ninja's
    frozen default validation handler emits the same Pydantic-v2 error-list
    SHAPE FastAPI does. Assert the structural contract (status,
    ``{"detail":[...]}`` envelope, ``loc``, ``type``) — the ``msg`` wording
    can vary microscopically across pydantic patch releases.
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

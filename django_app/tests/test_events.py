"""S3 — Events / Races API: owned test coverage.

S3 owns the events/races slice (``api/events.py`` + ``api/schemas/events.py``)
and consumes — never reimplements — the S2 service hub
(``core.services.standings.events_for_season``). This file mirrors S1's /
S2's three-section layout (``tests/test_seasons.py`` / ``test_standings.py``)
— the auto-tiering in ``conftest.py`` keys off the ``seeded_orm`` /
``parity_rig`` fixture NAMES, so Tier-2 marking is automatic with zero manual
annotation.

1. **Contract / wiring** (no DB — Tier-1, always green in the locked venv):
   the events module is wired into the FROZEN router assembly at the right
   path with the right ``tags``; the response schemas have the exact field
   NAMES + ORDER + TYPES + DEFAULTS of the frozen FastAPI Pydantic schemas
   (the ``openapi-typescript`` no-diff guarantee); existence is routed
   through the F3 ``resolve_season`` (never a hand-rolled season 404) and the
   race-detail 404 string is byte-identical to ``backend/app/api/events.py``;
   S3 consumes ``events_for_season`` from the S2 hub (not reimplemented); the
   editorial ``EventRef`` fields default null-safe.

2. **Behavior on the 2025 golden data** (``seeded_orm`` — auto-tiered
   Tier-2): the ported ``backend/tests/test_api.py`` race assertions
   (``test_list_races_2025`` / ``test_list_races_404_for_bad_year`` /
   ``test_get_race_detail_2025_kyrnare`` /
   ``test_get_race_detail_404_for_bad_slug``) run S3's endpoint logic
   directly against the golden data, plus the **null-safe editorial-field**
   case.

3. **Byte-parity vs the frozen FastAPI oracle** (``parity_rig`` — auto-tiered
   Tier-2): copied from F3's ``test_reference_parity.py`` template, scoped to
   the S3 race-list + race-detail surface. The bodies must be byte-for-byte
   equal to ``backend/app/api/events.py`` over identically-seeded Postgres,
   including the null-safe editorial fields.

The Tier-2 tests (2 + 3) auto-mark ``parity`` via the
``seeded_orm`` / ``parity_rig`` fixture-name detection in ``conftest.py`` —
S3 adds NO manual marker. They SKIP (never fake green) if no seeded Postgres
/ both stacks cannot be spun in the sandbox; the fixtures print the exact
command.
"""

from __future__ import annotations

import json

import pytest


# ===========================================================================
# 1. Contract / wiring — no DB, runs in the Tier-1 locked-venv gate
# ===========================================================================


def test_events_router_is_wired_into_frozen_assembly() -> None:
    """S3's ``router`` is the object the FROZEN ``api/__init__.py`` mounts.

    The frozen assembly imports ``api.events.router`` by reference and mounts
    it at ``/seasons`` with ``tags=["races"]`` (``api/__init__.py:77``,
    parity with FastAPI ``APIRouter(prefix="/api/seasons", tags=["races"])``).
    S3 fills that module's ``router`` — confirm exactly the two race
    operations are registered and nothing else leaked in.
    """
    from ninja import Router

    from api import events as events_api

    assert isinstance(events_api.router, Router)

    paths = set(events_api.router.path_operations.keys())
    assert paths == {"/{year}/events", "/{year}/events/{event_slug}"}, paths


def test_events_endpoints_match_fastapi_source_signature() -> None:
    """S3 endpoint contract mirrors ``backend/app/api/events.py``.

    Two GET operations. ``list_races`` and ``get_race_detail`` both take the
    constrained ``year`` path param (parity with the FastAPI ``get_season``
    ``Path(..., ge=1900, le=2999)`` via F3 ``YearPath``); ``get_race_detail``
    additionally takes the ``event_slug`` string path param (parity with the
    FastAPI ``event_slug: str = Path(...)``).
    """
    import typing

    from api import events as events_api
    from api.deps import YearPath
    from api.schemas.events import EventDetailOut, EventListOut

    list_po = events_api.router.path_operations["/{year}/events"]
    detail_po = events_api.router.path_operations[
        "/{year}/events/{event_slug}"
    ]

    (list_op,) = list_po.operations
    (detail_op,) = detail_po.operations
    assert list_op.methods == ["GET"]
    assert detail_op.methods == ["GET"]
    assert list_op.response_models[200] is not None
    assert detail_op.response_models[200] is not None
    assert EventListOut.__name__ == "EventListOut"
    assert EventDetailOut.__name__ == "EventDetailOut"

    list_hints = typing.get_type_hints(
        events_api.list_races, include_extras=True
    )
    detail_hints = typing.get_type_hints(
        events_api.get_race_detail, include_extras=True
    )
    assert list_hints["year"] is YearPath
    assert detail_hints["year"] is YearPath
    assert detail_hints["event_slug"] is str


def test_events_routes_existence_through_f3_resolver() -> None:
    """S3 must use F3 ``resolve_season`` — never hand-roll the season 404.

    The season-404 string lives byte-exact in F3 (``api/deps.py``). The
    race-detail 404 string is byte-identical to ``backend/app/api/events.py``
    and is raised inline as ``HttpError(404, ...)`` (the FastAPI source did
    the same with ``HTTPException(404, detail=...)``; there is no F3 resolver
    for "event-by-slug" — the FastAPI app hand-rolled it too).
    """
    import inspect

    from api import events as events_api
    from api.deps import resolve_season

    list_src = inspect.getsource(events_api.list_races)
    detail_src = inspect.getsource(events_api.get_race_detail)

    assert "resolve_season(" in list_src
    assert "resolve_season(" in detail_src
    assert resolve_season.__module__ == "api.deps"

    # The race-detail 404 string is byte-identical to the FastAPI source
    # (``backend/app/api/events.py``): f"Race '{event_slug}' not found in
    # season {season.year}". Pin the exact f-string + 404 status here so a
    # future edit that diverges the wording fails loudly (the ported parity
    # test in section 3 is the runtime proof).
    assert (
        "Race '{event_slug}' not found in season {season.year}" in detail_src
        or 'Race \'{event_slug}\' not found in season {season.year}'
        in detail_src
    )
    assert "HttpError(\n            404," in detail_src or (
        "HttpError(" in detail_src and "404" in detail_src
    )


def test_events_consumes_s2_events_for_season_not_reimplemented() -> None:
    """S3 consumes the S2 service hub — Lane D contract.

    ``events_for_season`` is owned by S2 (``core.services.standings``). S3
    imports + calls it for the race list (parity with the FastAPI source,
    which imported ``from src.services.standings import events_for_season``).
    S3 must NOT reimplement the season-events query in its own module.
    """
    import inspect

    from api import events as events_api
    from core.services import standings as svc

    src = inspect.getsource(events_api)
    assert (
        "from core.services.standings import events_for_season" in src
    )
    list_src = inspect.getsource(events_api.list_races)
    assert "events_for_season(" in list_src
    # The function S3 calls is the S2-owned one (Lane D: read-only consume).
    assert events_api.events_for_season is svc.events_for_season
    assert svc.events_for_season.__module__ == "core.services.standings"


def test_event_schemas_field_order_matches_fastapi_pydantic() -> None:
    """Field NAMES + ORDER + TYPES + DEFAULTS == frozen FastAPI Pydantic.

    The pinned renderer never re-sorts keys (``api/renderers.py``), so JSON
    key order == schema field-declaration order. If S3's schema field order
    ever drifts from ``backend/app/schemas/events.py`` /
    ``backend/app/schemas/common.py`` the frontend's ``openapi-typescript``
    client would regenerate WITH a diff. Pin the exact contract here.
    """
    from api.schemas.common import CategoryRef, EventRef, SeasonRef
    from api.schemas.events import EventDetailOut, EventListOut

    # EventListOut: {"season": SeasonRef, "events": [EventRef]} — order ==
    # backend/app/schemas/events.py::EventListOut.
    assert list(EventListOut.model_fields) == ["season", "events"]

    # EventDetailOut field order == backend/app/schemas/events.py.
    assert list(EventDetailOut.model_fields) == [
        "season",
        "event",
        "categories",
    ]

    # Nested ref schemas — order == backend/app/schemas/common.py exactly
    # (the editorial fields ride here, NOT on the S3 schemas).
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

    # Editorial fields default to None (null-safe), as in FastAPI. This is
    # the S3 acceptance criterion: facebook_event_url + description surface
    # identically AND null-safe.
    assert EventRef.model_fields["facebook_event_url"].default is None
    assert EventRef.model_fields["description"].default is None
    assert EventRef.model_fields["event_date"].default is None
    assert EventRef.model_fields["location"].default is None
    assert EventRef.model_fields["event_type"].default is None


def test_event_detail_category_ordering_is_byte_equivalent_to_fastapi() -> (
    None
):
    """S3's ORM ``order_by`` clauses == the FastAPI ``ORDER BY``.

    FastAPI ``get_race_detail``:
      * categories: ``order_by(Category.sort_order, Category.id)``

    The list endpoint's ``events`` order comes from the S2
    ``events_for_season`` (``order_by("sort_order", "id")`` — pinned in
    ``test_standings.py``). The category ordering is observable in the JSON
    array order, so it is part of the byte-parity contract. Assert S3's
    source uses the exact equivalent.
    """
    import inspect

    from api import events as events_api

    detail_src = inspect.getsource(events_api.get_race_detail)
    assert (
        'order_by(\n            "sort_order", "id"\n        )' in detail_src
        or 'order_by("sort_order", "id")' in detail_src
    )


# ===========================================================================
# 2. Behavior on the 2025 golden data — ported backend/tests/test_api.py
#    race assertions (``seeded_orm`` → auto-tiered Tier-2; SKIPs without
#    seeded Postgres)
# ===========================================================================


def _call(endpoint, *args):
    """Invoke an S3 Ninja endpoint function directly (no HTTP).

    The endpoints take ``request`` first; the events handlers never touch the
    request object, so ``None`` is a faithful stand-in for this unit layer.
    The parity rig (section 3) exercises the FULL HTTP stack.
    """
    return endpoint(None, *args)


def test_list_races_2025(seeded_orm) -> None:
    """Ported ``backend/tests/test_api.py::test_list_races_2025``."""
    from api.events import list_races

    out = _call(list_races, 2025)
    assert out.season.year == 2025
    assert len(out.events) >= 5
    slugs = [e.slug for e in out.events]
    assert "kyrnare" in slugs
    # Race-calendar order (parity with events_for_season ORDER BY
    # sort_order, id — observable in the JSON array order).
    sort_keys = [e.sort_order for e in out.events]
    assert sort_keys == sorted(sort_keys)


def test_list_races_404_for_bad_year(seeded_orm) -> None:
    """Ported ``backend/tests/test_api.py::test_list_races_404_for_bad_year``.

    Goes through the F3 ``resolve_season`` → byte-exact ``HttpError(404,
    "Season 1999 not found")``.
    """
    from ninja.errors import HttpError

    from api.events import list_races

    with pytest.raises(HttpError) as exc:
        _call(list_races, 1999)
    assert exc.value.status_code == 404
    assert str(exc.value) == "Season 1999 not found"


def test_get_race_detail_2025_kyrnare(seeded_orm) -> None:
    """Ported ``test_get_race_detail_2025_kyrnare``."""
    from api.events import get_race_detail

    out = _call(get_race_detail, 2025, "kyrnare")
    assert out.event.slug == "kyrnare"
    assert len(out.categories) >= 5
    assert out.season.year == 2025
    # Categories ordered by (sort_order, id) — observable JSON array order.
    cat_keys = [c.sort_order for c in out.categories]
    assert cat_keys == sorted(cat_keys)


def test_get_race_detail_404_for_bad_slug(seeded_orm) -> None:
    """Ported ``test_get_race_detail_404_for_bad_slug``.

    The race-detail 404 string is byte-identical to
    ``backend/app/api/events.py``:
    ``f"Race '{event_slug}' not found in season {season.year}"``.
    """
    from ninja.errors import HttpError

    from api.events import get_race_detail

    with pytest.raises(HttpError) as exc:
        _call(get_race_detail, 2025, "not-a-real-race")
    assert exc.value.status_code == 404
    assert (
        str(exc.value)
        == "Race 'not-a-real-race' not found in season 2025"
    )


def test_get_race_detail_404_for_bad_year(seeded_orm) -> None:
    """A bad year on the detail endpoint goes through F3 ``resolve_season``
    (byte-exact season 404) BEFORE the slug lookup — parity with the FastAPI
    ``Depends(get_season)`` ordering.
    """
    from ninja.errors import HttpError

    from api.events import get_race_detail

    with pytest.raises(HttpError) as exc:
        _call(get_race_detail, 1999, "kyrnare")
    assert exc.value.status_code == 404
    assert str(exc.value) == "Season 1999 not found"


def test_editorial_fields_are_null_safe_when_unset(seeded_orm) -> None:
    """S3 acceptance: ``facebook_event_url`` / ``description`` surface
    identically AND null-safe (the NULL case explicitly tested).

    The 2025 golden races are imported WITHOUT editorial copy (those are
    populated later via /admin), so the seeded events have
    ``facebook_event_url is None`` / ``description is None``. Assert the S3
    response carries them through as ``None`` (→ ``null`` in JSON via the
    pinned renderer) for EVERY race in the list and in the detail — never a
    KeyError, never a crash, never a fabricated value. This is the explicit
    null-case the acceptance criteria require.
    """
    from api.events import get_race_detail, list_races
    from core.models import Event, Season

    season = Season.objects.get(year=2025)
    seeded_events = list(
        Event.objects.filter(season_id=season.id).order_by(
            "sort_order", "id"
        )
    )
    # At least one seeded 2025 race must actually have NULL editorial fields
    # for this test to meaningfully exercise the null path.
    null_editorial = [
        e
        for e in seeded_events
        if e.facebook_event_url is None and e.description is None
    ]
    assert null_editorial, (
        "expected at least one 2025 race with NULL editorial fields "
        "(imported without /admin copy) to exercise the null-safe path"
    )

    # List endpoint: every EventRef mirrors the ORM editorial state exactly,
    # null-safe (None passes through, no fallback fabrication).
    list_out = _call(list_races, 2025)
    by_slug = {e.slug: e for e in seeded_events}
    for ref in list_out.events:
        src = by_slug[ref.slug]
        assert ref.facebook_event_url == src.facebook_event_url
        assert ref.description == src.description
    # The all-None races really do come back None (not "" / not missing).
    null_slugs = {e.slug for e in null_editorial}
    for ref in list_out.events:
        if ref.slug in null_slugs:
            assert ref.facebook_event_url is None
            assert ref.description is None

    # Detail endpoint: same null-safe passthrough on the single event.
    target = null_editorial[0]
    detail_out = _call(get_race_detail, 2025, target.slug)
    assert detail_out.event.slug == target.slug
    assert detail_out.event.facebook_event_url is None
    assert detail_out.event.description is None


# ===========================================================================
# 3. Byte-parity vs the frozen FastAPI oracle — COPIED from F3's
#    tests/test_reference_parity.py template, scoped to the S3 surface.
#    (``parity_rig`` → auto-tiered Tier-2; SKIPs if both stacks cannot spin)
# ===========================================================================

# The S3 public surface. Each is a (path, note) the new Django app and the
# spun FastAPI oracle must agree on byte-for-byte. 2025 = aggregate_2025
# season (no event_date on the 2025 imports → null-safe date refs); 2026 =
# per_event season with real ISO event dates on the EventRef.
EVENTS_PATHS = [
    (
        "/api/seasons/2025/events",
        "race list — events_for_season order, Cyrillic names, null editorial",
    ),
    (
        "/api/seasons/2025/events/kyrnare",
        "race detail — event + categories (sort_order,id), null editorial",
    ),
    (
        "/api/seasons/2026/events",
        "race list — events WITH real event_date (ISO 8601) on EventRef",
    ),
]


@pytest.mark.parametrize("path, _note", EVENTS_PATHS)
def test_events_endpoint_byte_parity(
    path, _note, parity_rig, assert_json_parity
) -> None:
    """S3 events endpoint == frozen FastAPI oracle, byte-for-byte.

    Proves the ported ``backend/app/api/events.py`` (race list consuming the
    S2 ``events_for_season`` + race detail with categories) produces a JSON
    body byte-identical to the oracle over identically-seeded Postgres —
    including the null-safe editorial ``facebook_event_url`` / ``description``
    fields (the 2025 races have them NULL; parity proves the new app emits
    the same ``null``, not ``""`` and not a missing key).
    """
    assert_json_parity(parity_rig.old(path), parity_rig.new(path))


def test_events_null_editorial_fields_byte_parity_in_response(
    parity_rig,
) -> None:
    """Explicit NULL-editorial assertion on the live parity-rig response.

    Beyond the byte compare above, pin in code that the NEW app emits
    ``facebook_event_url``/``description`` as JSON ``null`` (not ``""``, not
    absent) for the 2025 races that have no /admin copy — the exact null-safe
    contract the FastAPI ``EventRef`` (``Optional[str] = None``) gave. We
    assert on the NEW app's body so a regression that fabricates a value or
    drops the key fails here even if the oracle ever drifted.
    """
    new = parity_rig.new("/api/seasons/2025/events")
    assert new.status_code == 200
    body = json.loads(new.content)
    assert body["season"]["year"] == 2025
    assert len(body["events"]) >= 5
    saw_null = False
    for ev in body["events"]:
        # The keys MUST be present (null-safe = explicit null, not omitted).
        assert "facebook_event_url" in ev
        assert "description" in ev
        if ev["facebook_event_url"] is None and ev["description"] is None:
            saw_null = True
    assert saw_null, (
        "expected at least one 2025 race with both editorial fields null "
        "(imported without /admin copy)"
    )


def test_events_404_bad_year_parity(
    parity_rig, assert_json_parity
) -> None:
    """Missing season → identical 404 ``{"detail":"Season 1999 not found"}``.

    Ported ``backend/tests/test_api.py::test_list_races_404_for_bad_year``;
    S3 routes existence through F3 ``resolve_season``.
    """
    old = parity_rig.old("/api/seasons/1999/events")
    new = parity_rig.new("/api/seasons/1999/events")
    assert old.status_code == 404
    assert_json_parity(old, new)
    assert json.loads(new.content) == {"detail": "Season 1999 not found"}


def test_events_404_bad_slug_parity(
    parity_rig, assert_json_parity
) -> None:
    """Unknown race slug → identical 404
    ``{"detail":"Race 'not-a-real-race' not found in season 2025"}``.

    Ported ``backend/tests/test_api.py::test_get_race_detail_404_for_bad_slug``.
    The race-detail 404 string is byte-identical to
    ``backend/app/api/events.py`` (raised inline as ``HttpError``; the
    FastAPI source hand-rolled the same ``HTTPException`` string — there is
    no F3 event-by-slug resolver).
    """
    old = parity_rig.old("/api/seasons/2025/events/not-a-real-race")
    new = parity_rig.new("/api/seasons/2025/events/not-a-real-race")
    assert old.status_code == 404
    assert_json_parity(old, new)
    assert json.loads(new.content) == {
        "detail": "Race 'not-a-real-race' not found in season 2025"
    }


@pytest.mark.parametrize("bad_year", ["abc", "3000", "1800"])
def test_events_422_validation_parity(
    bad_year, parity_rig, assert_json_parity
) -> None:
    """Out-of-range / non-int ``year`` → identical 422 Pydantic-error body.

    Proves S3's ``YearPath`` reproduces the FastAPI ``get_season``
    ``Path(..., ge=1900, le=2999)`` validation. Structural contract
    (status, ``{"detail":[...]}``, ``loc``, ``type``) — ``msg`` wording can
    vary microscopically across pydantic patch releases.
    """
    old = parity_rig.old(f"/api/seasons/{bad_year}/events")
    new = parity_rig.new(f"/api/seasons/{bad_year}/events")
    assert old.status_code == 422, old.content[:300]
    assert new.status_code == 422, new.content[:300]

    o = json.loads(old.content)
    n = json.loads(new.content)
    assert isinstance(o["detail"], list) and isinstance(n["detail"], list)
    o_err, n_err = o["detail"][0], n["detail"][0]
    assert list(o_err["loc"]) == list(n_err["loc"]) == ["path", "year"]
    assert o_err["type"] == n_err["type"]


def test_race_event_slug_present_in_response(parity_rig) -> None:
    """The race-detail event slug round-trips exactly (frontend consumes it).

    Spot-check on the NEW app: the ``/results`` + race pages key off
    ``event.slug``; verify the detail endpoint echoes the requested slug
    verbatim and carries the season + categories.
    """
    new = parity_rig.new("/api/seasons/2025/events/kyrnare")
    assert new.status_code == 200
    body = json.loads(new.content)
    assert body["event"]["slug"] == "kyrnare"
    assert body["season"]["year"] == 2025
    assert len(body["categories"]) >= 5

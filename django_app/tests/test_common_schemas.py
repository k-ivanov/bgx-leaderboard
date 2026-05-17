"""F3 common-schema parity.

Acceptance criteria covered:
* common schemas validate from Django ORM instances (``model_validate`` over
  ``from_attributes`` — the Ninja ``Schema`` equivalent of the old
  ``ConfigDict(from_attributes=True)``);
* ``RiderRef.from_orm`` produces a slug from ``core.slug`` only and its JSON
  byte-matches the current API via ``assert_json_parity``;
* field NAMES + ORDER + TYPES match the FastAPI Pydantic schemas (so
  ``openapi-typescript`` regenerates with no diff).

DB-backed cases use ``seeded_orm`` (read-only against the seeded
``bgx_django``) — see ``conftest.py``. The byte-parity case also uses
``parity_rig`` to diff against the spun FastAPI oracle.
"""

import json

from api.schemas.common import (
    CategoryRef,
    EventRef,
    RiderRef,
    SeasonRef,
    build_rider_ref,
)
from core.slug import rider_slug


def test_schema_field_order_matches_backend_pydantic() -> None:
    """Field declaration order == JSON key order (renderer never re-sorts).

    Pinned against backend/app/schemas/common.py field order. A reorder here
    would change the byte stream + the openapi-typescript client.
    """
    assert list(RiderRef.model_fields) == [
        "race_number",
        "first_name",
        "last_name",
        "slug",
        "team",
        "bike",
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
    assert list(SeasonRef.model_fields) == [
        "year",
        "name",
        "slug",
        "is_current",
        "championship_format",
    ]


def test_seasonref_validates_from_django_instance(seeded_orm) -> None:
    from core.models import Season

    s = Season.objects.get(year=2025)
    ref = SeasonRef.model_validate(s)
    assert ref.year == 2025
    assert ref.name == s.name
    assert ref.slug == s.slug
    assert ref.is_current == s.is_current
    assert ref.championship_format == s.championship_format


def test_categoryref_and_eventref_validate_from_django_instances(
    seeded_orm,
) -> None:
    from core.models import Category, Event, Season

    s = Season.objects.get(year=2025)
    c = Category.objects.filter(season_id=s.id).order_by("sort_order", "id")[0]
    cref = CategoryRef.model_validate(c)
    assert (cref.code, cref.display_name, cref.sort_order) == (
        c.code,
        c.display_name,
        c.sort_order,
    )

    e = Event.objects.filter(season_id=s.id).order_by("sort_order", "id")[0]
    eref = EventRef.model_validate(e)
    assert eref.slug == e.slug
    assert eref.name == e.name
    # Editorial fields are null-safe (parity with FastAPI EventRef).
    assert eref.facebook_event_url == e.facebook_event_url
    assert eref.description == e.description


def test_riderref_from_orm_slug_uses_core_slug_only(seeded_orm) -> None:
    from core.models import Rider, Season

    s = Season.objects.get(year=2025)
    rider = Rider.objects.filter(season_id=s.id).first()
    ref = RiderRef.from_orm(rider)
    expected_slug = rider_slug(
        rider.first_name, rider.last_name, rider.race_number
    )
    assert ref.slug == expected_slug
    # build_rider_ref is the module-level alias — identical result.
    assert build_rider_ref(rider).model_dump() == ref.model_dump()


def test_riderref_from_orm_json_byte_matches_oracle(
    seeded_orm, parity_rig
) -> None:
    """``RiderRef.from_orm`` JSON byte-matches the FastAPI oracle.

    The oracle has no standalone RiderRef endpoint, so we diff a RiderRef as
    embedded by the leaderboard (``rows[].rider`` — ``StandingsRowOut``),
    which IS ``backend/app/schemas/common.py::RiderRef`` over the wire. We
    build the SAME RiderRef set from the new schema + ``core.slug`` off the
    Django ORM and assert each rider object serializes byte-identically under
    the pinned F3 serialization spec.
    """
    from tests.parity import _CANONICAL_DUMPS

    path = "/api/seasons/2025/standings/expert"
    old = parity_rig.old(path)
    assert old.status_code == 200, old.content[:300]
    old_rows = json.loads(old.content)["rows"]
    assert old_rows, "oracle returned no leaderboard rows for 2025 expert"

    from core.models import Category, Rider, Season

    s = Season.objects.get(year=2025)
    cat = Category.objects.get(season_id=s.id, code="expert")
    by_slug = {}
    for r in Rider.objects.filter(season_id=s.id, category_id=cat.id):
        ref = RiderRef.from_orm(r)
        by_slug[ref.slug] = json.dumps(ref.model_dump(), **_CANONICAL_DUMPS)

    checked = 0
    for row in old_rows:
        oracle_rider = row["rider"]
        slug = oracle_rider["slug"]
        assert slug in by_slug, (
            f"rider slug {slug!r} from the oracle leaderboard not "
            f"reproducible from core.slug — slug contract drift"
        )
        oracle_bytes = json.dumps(oracle_rider, **_CANONICAL_DUMPS)
        assert by_slug[slug] == oracle_bytes, (
            f"RiderRef byte mismatch for {slug!r}\n"
            f"  oracle: {oracle_bytes}\n"
            f"  new:    {by_slug[slug]}"
        )
        checked += 1
    assert checked > 0

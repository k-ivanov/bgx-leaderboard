"""S6 — analytics WRITE-path parity (port of ``backend/tests/test_analytics.py``).

Covers the deterministic primitives in ``core.analytics`` (S6's WRITE module,
port of ``backend/src/analytics.py``): salt rotation/atomic upsert, visitor
hash stability, and 30-minute session derivation. S5 owns the READ side
(``api/stats.py``); these two slices are disjoint and this file never imports
from ``api/stats.py``.

The pure-hash tests need no DB (Tier-1, no fixture). The salt/session tests
use ``@pytest.mark.django_db`` against pytest-django's OWN isolated test DB —
NOT ``seeded_orm`` (so they are NOT auto-tiered ``parity``; they need an
empty isolated ``analytics_salt``/``visit`` table, not the golden data,
exactly the substrate F2/scaffold model tests + S5 use). When that test DB is
Postgres (the conftest points ``DATABASE_URL`` at the dev Postgres when one
is reachable) the authoritative ``INSERT ... ON CONFLICT (day) DO NOTHING``
path runs for real; on the in-memory SQLite fallback the equivalent
``INSERT OR IGNORE`` path runs (skip-don't-fake is not needed — both paths
are exercised by ``core.analytics.get_or_create_salt`` by design).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.analytics import (
    _reset_salt_cache_for_tests,
    derive_session_id,
    get_or_create_salt,
    visitor_id_for,
)


# ---------------------------------------------------------------------------
# Pure hash primitives — no DB (Tier-1, ported one-to-one)
# ---------------------------------------------------------------------------


def test_visitor_id_is_stable_for_same_inputs() -> None:
    # Ported: test_analytics.py::test_visitor_id_is_stable_for_same_inputs
    salt = "deadbeef" * 4
    a = visitor_id_for(salt, "1.2.3.4", "Mozilla/5.0")
    b = visitor_id_for(salt, "1.2.3.4", "Mozilla/5.0")
    assert a == b
    assert len(a) == 16


def test_visitor_id_changes_when_salt_rotates() -> None:
    # Ported: test_analytics.py::test_visitor_id_changes_when_salt_rotates
    yesterday_hash = visitor_id_for("salt-one" * 4, "1.2.3.4", "UA")
    today_hash = visitor_id_for("salt-two" * 4, "1.2.3.4", "UA")
    assert yesterday_hash != today_hash


def test_visitor_id_changes_per_ip() -> None:
    # Ported: test_analytics.py::test_visitor_id_changes_per_ip
    salt = "fixed-salt" * 3
    assert visitor_id_for(salt, "1.2.3.4", "UA") != visitor_id_for(
        salt, "9.9.9.9", "UA"
    )


def test_visitor_id_byte_identical_to_oracle_formula() -> None:
    """The hash material + truncation MUST be byte-identical to the oracle.

    ``backend/src/analytics.py::visitor_id_for`` is
    ``sha256(f"{salt}|{ip}|{ua}|bgx-dashboard").hexdigest()[:16]``. Recompute
    it independently here so any drift in the material string (separator,
    field order, the ``_SITE_DOMAIN`` literal) fails loudly — this hash is
    persisted into the ``visit.visitor_id`` column the stats slice aggregates.
    """
    import hashlib

    salt, ip, ua = "abc123" * 4, "203.0.113.9", "Mozilla/5.0 (X11; Linux)"
    expected = hashlib.sha256(
        f"{salt}|{ip}|{ua}|bgx-dashboard".encode("utf-8")
    ).hexdigest()[:16]
    assert visitor_id_for(salt, ip, ua) == expected


# ---------------------------------------------------------------------------
# Salt upsert + caching — isolated test DB (Postgres ON CONFLICT or SQLite
# INSERT OR IGNORE; both exercised by get_or_create_salt by design)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_or_create_salt_persists_and_caches() -> None:
    # Ported: test_analytics.py::test_get_or_create_salt_persists_and_caches
    from core.models import AnalyticsSalt

    _reset_salt_cache_for_tests()
    today = datetime.now(timezone.utc).date()
    AnalyticsSalt.objects.filter(day=today).delete()

    first = get_or_create_salt()

    row = AnalyticsSalt.objects.get(day=today)
    assert row.salt == first

    # Second call (cache or DB) returns the same value — no new row created.
    second = get_or_create_salt()
    assert second == first
    assert AnalyticsSalt.objects.filter(day=today).count() == 1


@pytest.mark.django_db
def test_get_or_create_salt_upsert_does_not_raise_on_existing_row() -> None:
    """A pre-existing row for today must NOT raise and must be returned.

    This is the atomic-upsert contract: ``get_or_create`` would
    ``IntegrityError`` here on the second insert; the ported
    ``INSERT ... ON CONFLICT DO NOTHING`` (Postgres) / ``INSERT OR IGNORE``
    (SQLite) silently no-ops and the re-SELECT returns the existing salt.
    """
    from core.models import AnalyticsSalt

    _reset_salt_cache_for_tests()
    today = datetime.now(timezone.utc).date()
    AnalyticsSalt.objects.filter(day=today).delete()
    AnalyticsSalt.objects.create(day=today, salt="preexisting-salt-value")

    got = get_or_create_salt()
    assert got == "preexisting-salt-value"
    assert AnalyticsSalt.objects.filter(day=today).count() == 1


@pytest.mark.django_db
def test_get_or_create_salt_for_explicit_day() -> None:
    """The ``day`` arg is honored (parity with the oracle's optional param)."""
    from datetime import date

    from core.models import AnalyticsSalt

    _reset_salt_cache_for_tests()
    d = date(2031, 1, 2)
    AnalyticsSalt.objects.filter(day=d).delete()
    s = get_or_create_salt(day=d)
    assert AnalyticsSalt.objects.get(day=d).salt == s


# ---------------------------------------------------------------------------
# Session derivation — isolated test DB
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_derive_session_id_reuses_within_window() -> None:
    # Ported: test_analytics.py::test_derive_session_id_reuses_within_window
    from core.models import Visit

    vid = "testvisitor01234"
    now = datetime.now(timezone.utc)
    Visit.objects.filter(visitor_id=vid).delete()
    Visit.objects.create(
        timestamp=now - timedelta(minutes=5),
        page="home",
        visitor_id=vid,
        session_id="session-abc",
        device_type="desktop",
    )
    assert derive_session_id(vid, now=now) == "session-abc"


@pytest.mark.django_db
def test_derive_session_id_rolls_over_after_window() -> None:
    # Ported: test_analytics.py::test_derive_session_id_rolls_over_after_window
    from core.models import Visit

    vid = "testvisitor56789"
    now = datetime.now(timezone.utc)
    Visit.objects.filter(visitor_id=vid).delete()
    Visit.objects.create(
        timestamp=now - timedelta(minutes=45),
        page="home",
        visitor_id=vid,
        session_id="session-old",
        device_type="desktop",
    )
    fresh = derive_session_id(vid, now=now)
    assert fresh != "session-old"
    assert len(fresh) > 0


@pytest.mark.django_db
def test_derive_session_id_fresh_for_unknown_visitor() -> None:
    # Ported: test_analytics.py::test_derive_session_id_fresh_for_unknown_visitor
    sid = derive_session_id("neverseenbefore1")
    assert len(sid) > 0

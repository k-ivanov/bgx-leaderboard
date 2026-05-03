"""Plausible-style analytics unit tests.

Covers the deterministic primitives in ``src/analytics`` — salt rotation,
visitor hash stability, and 30-minute session derivation.
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from src.analytics import (
    _reset_salt_cache_for_tests,
    derive_session_id,
    get_or_create_salt,
    visitor_id_for,
)
from src.db import get_session
from src.db.models import AnalyticsSalt, Visit

pytestmark = pytest.mark.usefixtures("seeded_db")


def test_visitor_id_is_stable_for_same_inputs() -> None:
    salt = "deadbeef" * 4
    a = visitor_id_for(salt, "1.2.3.4", "Mozilla/5.0")
    b = visitor_id_for(salt, "1.2.3.4", "Mozilla/5.0")
    assert a == b
    assert len(a) == 16


def test_visitor_id_changes_when_salt_rotates() -> None:
    yesterday_hash = visitor_id_for("salt-one" * 4, "1.2.3.4", "UA")
    today_hash = visitor_id_for("salt-two" * 4, "1.2.3.4", "UA")
    assert yesterday_hash != today_hash


def test_visitor_id_changes_per_ip() -> None:
    salt = "fixed-salt" * 3
    assert visitor_id_for(salt, "1.2.3.4", "UA") != visitor_id_for(salt, "9.9.9.9", "UA")


def test_get_or_create_salt_persists_and_caches() -> None:
    _reset_salt_cache_for_tests()
    today = datetime.now(timezone.utc).date()
    with get_session() as s:
        s.execute(delete(AnalyticsSalt).where(AnalyticsSalt.day == today))
        s.commit()

    with get_session() as s:
        first = get_or_create_salt(s)
        s.commit()

    with get_session() as s:
        row = s.execute(
            select(AnalyticsSalt).where(AnalyticsSalt.day == today)
        ).scalar_one()
        assert row.salt == first

    # Second call (cache or DB) returns the same value — no new row created.
    with get_session() as s:
        second = get_or_create_salt(s)
        assert second == first
        count = s.execute(
            select(AnalyticsSalt).where(AnalyticsSalt.day == today)
        ).scalars().all()
        assert len(count) == 1


def test_derive_session_id_reuses_within_window() -> None:
    vid = "testvisitor01234"
    now = datetime.now(timezone.utc)

    with get_session() as s:
        s.execute(delete(Visit).where(Visit.visitor_id == vid))
        s.add(
            Visit(
                timestamp=now - timedelta(minutes=5),
                page="home",
                visitor_id=vid,
                session_id="session-abc",
                device_type="desktop",
            )
        )
        s.commit()

    with get_session() as s:
        reused = derive_session_id(s, vid, now=now)
        assert reused == "session-abc"


def test_derive_session_id_rolls_over_after_window() -> None:
    vid = "testvisitor56789"
    now = datetime.now(timezone.utc)

    with get_session() as s:
        s.execute(delete(Visit).where(Visit.visitor_id == vid))
        s.add(
            Visit(
                timestamp=now - timedelta(minutes=45),
                page="home",
                visitor_id=vid,
                session_id="session-old",
                device_type="desktop",
            )
        )
        s.commit()

    with get_session() as s:
        fresh = derive_session_id(s, vid, now=now)
        assert fresh != "session-old"
        assert len(fresh) > 0


def test_derive_session_id_fresh_for_unknown_visitor() -> None:
    with get_session() as s:
        sid = derive_session_id(s, "neverseenbefore1")
        assert len(sid) > 0

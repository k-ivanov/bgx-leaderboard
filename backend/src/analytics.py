"""Plausible-style cookieless analytics primitives.

Rationale: EU ePrivacy requires consent for any client-side storage (cookies,
localStorage, sessionStorage). Plausible / Umami avoid that by computing a
visitor identifier server-side from a daily-rotating salt hashed against IP,
User-Agent, and the site domain. Nothing lands on the user's device.

See .claude/ memory and the project design review for background.

Key properties:
  * visitor_id is stable within a UTC day for the same (ip, user_agent) pair.
  * When the salt rotates at midnight UTC, yesterday's hashes become
    unlinkable to today's — even the operator can't re-link them.
  * Domain is mixed into the hash so the same person on site A and site B
    gets different IDs (no cross-site tracking, even if we host more later).

The salt is persisted in the ``analytics_salt`` table (strict UTC-midnight
rotation, survives process restarts). A per-process cache avoids hitting the
DB on every /api/track call.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from threading import Lock
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.db.models import AnalyticsSalt, Visit


_SITE_DOMAIN = "bgx-dashboard"
_SESSION_WINDOW = timedelta(minutes=30)

_salt_cache: dict[date, str] = {}
_salt_lock = Lock()


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def get_or_create_salt(session: Session, day: Optional[date] = None) -> str:
    """Return today's salt, creating it atomically if this is its first use.

    Uses Postgres ``INSERT ... ON CONFLICT DO NOTHING`` so two concurrent
    first-of-the-day requests can't create duplicate rows. Cached in-process
    for the rest of the day to avoid a DB round-trip per track call.
    """
    today = day or _today_utc()

    cached = _salt_cache.get(today)
    if cached is not None:
        return cached

    with _salt_lock:
        cached = _salt_cache.get(today)
        if cached is not None:
            return cached

        proposed = secrets.token_hex(16)
        stmt = (
            pg_insert(AnalyticsSalt)
            .values(day=today, salt=proposed)
            .on_conflict_do_nothing(index_elements=["day"])
        )
        session.execute(stmt)
        session.flush()

        row = session.execute(
            select(AnalyticsSalt.salt).where(AnalyticsSalt.day == today)
        ).scalar_one()
        _salt_cache.clear()
        _salt_cache[today] = row
        return row


def visitor_id_for(salt: str, ip: str, user_agent: str) -> str:
    """Stable-for-a-day pseudonymous identifier. 16 hex chars (64 bits)."""
    material = f"{salt}|{ip}|{user_agent}|{_SITE_DOMAIN}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:16]


def derive_session_id(
    session: Session,
    visitor_id: str,
    now: Optional[datetime] = None,
) -> str:
    """Reuse the visitor's most recent session_id if within the 30-min window,
    else mint a fresh UUID.

    Relies on the ``ix_visit_visitor_time`` composite index for a fast lookup.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - _SESSION_WINDOW

    recent = session.execute(
        select(Visit.session_id, Visit.timestamp)
        .where(Visit.visitor_id == visitor_id)
        .order_by(Visit.timestamp.desc())
        .limit(1)
    ).first()

    if recent is not None and recent.session_id and recent.timestamp >= cutoff:
        return recent.session_id

    return str(uuid.uuid4())


def _reset_salt_cache_for_tests() -> None:
    """Clear the in-process salt cache. Used only by tests."""
    with _salt_lock:
        _salt_cache.clear()

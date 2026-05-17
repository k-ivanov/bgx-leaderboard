"""S6 — Plausible-style cookieless analytics primitives (the WRITE path).

Byte-faithful port of ``backend/src/analytics.py`` (the analytics WRITE side)
+ ``backend/app/client_ip.py`` (``real_client_ip``) + ``detect_device_type``
from ``backend/src/database.py``. This is S6's module; S5 (the READ side,
``api/stats.py``) deliberately left ``core/analytics.py`` for S6 and does NOT
import from here — the two slices are disjoint.

Rationale (carried verbatim from the FastAPI source): EU ePrivacy requires
consent for any client-side storage (cookies, localStorage, sessionStorage).
Plausible / Umami avoid that by computing a visitor identifier server-side
from a daily-rotating salt hashed against IP, User-Agent, and the site
domain. Nothing lands on the user's device.

Key properties (unchanged from the oracle):
  * visitor_id is stable within a UTC day for the same (ip, user_agent) pair.
  * When the salt rotates at midnight UTC, yesterday's hashes become
    unlinkable to today's — even the operator can't re-link them.
  * Domain is mixed into the hash so the same person on site A and site B
    gets different IDs (no cross-site tracking).

The salt is persisted in the ``analytics_salt`` table (strict UTC-midnight
rotation, survives process restarts). A per-process cache avoids hitting the
DB on every /api/track call.

ATOMICITY (decision OV3 — the load-bearing port detail)
-------------------------------------------------------
``get_or_create_salt`` MUST stay race-safe at the UTC-midnight rollover and
under burst traffic. The FastAPI oracle used Postgres
``INSERT ... ON CONFLICT (day) DO NOTHING`` followed by a re-SELECT, guarded
by an in-process ``threading.Lock`` + a per-day cache. Django's
``Model.objects.get_or_create`` is **NOT** equivalent: it does
``try: get() except DoesNotExist: create()`` in two statements with no DB-side
conflict arbitration, so two concurrent first-of-the-day requests (or a burst
straddling midnight) can both miss the ``get`` and the second ``create`` then
raises ``IntegrityError`` (PK ``day`` collision). This port therefore keeps
the EXACT oracle semantics:

  * a raw parametrized ``INSERT ... ON CONFLICT (day) DO NOTHING`` (the
    ``analytics_salt`` PK is ``day``) — at most one row per day is ever
    created, no IntegrityError under burst;
  * a re-SELECT to read whichever salt won the race (mine or a concurrent
    creator's) so every caller agrees on the day's salt;
  * the same ``threading.Lock`` + per-day cache (cleared on rotation) so a
    process serves a day's salt from memory after first use and the lock
    collapses an in-process burst to a single DB round-trip.

On SQLite (the Tier-1 locked-venv gate's in-memory test DB) Postgres'
``ON CONFLICT`` syntax is unavailable; the helper falls back to SQLite's
equivalent ``INSERT OR IGNORE`` so the unit tests still exercise the
upsert+reselect+cache path. The authoritative Postgres ``ON CONFLICT`` proof
is the concurrency test run with a Postgres ``DATABASE_URL`` (skip-don't-fake
otherwise).
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from threading import Lock
from typing import Optional

from django.db import connection

from core.models import AnalyticsSalt, Visit

# --- ported verbatim from backend/src/analytics.py -------------------------
_SITE_DOMAIN = "bgx-dashboard"
_SESSION_WINDOW = timedelta(minutes=30)

_salt_cache: dict[date, str] = {}
_salt_lock = Lock()

# --- ported verbatim from backend/src/database.py::_MOBILE_INDICATORS ------
_MOBILE_INDICATORS = (
    "mobile",
    "android",
    "iphone",
    "ipad",
    "ipod",
    "blackberry",
    "windows phone",
)


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def detect_device_type(user_agent: str) -> str:
    """Port of ``backend/src/database.py::detect_device_type`` (byte-faithful).

    Empty UA → ``"unknown"``; any mobile indicator substring → ``"mobile"``;
    else ``"desktop"``. Order of the indicator scan + the lowercasing match
    the oracle exactly so the persisted ``device_type`` is byte-identical.
    """
    if not user_agent:
        return "unknown"
    ua = user_agent.lower()
    for indicator in _MOBILE_INDICATORS:
        if indicator in ua:
            return "mobile"
    return "desktop"


def real_client_ip(request) -> str:
    """Port of ``backend/app/client_ip.py::real_client_ip`` (byte-faithful).

    ``request.client.host`` (Starlette) ⇒ ``request.META["REMOTE_ADDR"]``
    (Django). The X-Forwarded-For handling is identical: the LEFTMOST entry
    is the original client, everything after is an intermediate proxy hop;
    whitespace is stripped. Falls back to ``REMOTE_ADDR`` when no XFF.

    This is the proxy-aware identity the throttle reuses (so a Railway LB
    node IP can't defeat the per-IP quota) AND the analytics visitor-id
    keying input — exactly as in the FastAPI app.
    """
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        # Leftmost is the original client; everything after is intermediate.
        return xff.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


def get_or_create_salt(day: Optional[date] = None) -> str:
    """Return today's salt, creating it atomically if first use today.

    Byte-faithful port of ``backend/src/analytics.py::get_or_create_salt``.
    Uses an atomic upsert (Postgres ``INSERT ... ON CONFLICT (day) DO
    NOTHING``; SQLite ``INSERT OR IGNORE``) + a re-SELECT so two concurrent
    first-of-the-day requests can't create duplicate rows and every caller
    converges on the same salt. Cached in-process (lock-guarded, cleared on
    rotation) for the rest of the day to avoid a DB round-trip per track
    call. NOT ``get_or_create`` — see the module docstring for why that is
    not race-equivalent.
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
        table = AnalyticsSalt._meta.db_table  # "analytics_salt"
        day_col = AnalyticsSalt._meta.get_field("day").column  # "day"
        salt_col = AnalyticsSalt._meta.get_field("salt").column  # "salt"

        with connection.cursor() as cursor:
            if connection.vendor == "postgresql":
                # Postgres: the oracle's exact INSERT ... ON CONFLICT DO
                # NOTHING semantics — at most one row per day, no
                # IntegrityError under a burst / midnight straddle.
                cursor.execute(
                    f'INSERT INTO "{table}" ("{day_col}", "{salt_col}") '
                    f"VALUES (%s, %s) "
                    f'ON CONFLICT ("{day_col}") DO NOTHING',
                    [today, proposed],
                )
            else:
                # SQLite (Tier-1 in-memory gate): equivalent conflict-arbitrated
                # insert so the same upsert+reselect+cache path is exercised.
                cursor.execute(
                    f'INSERT OR IGNORE INTO "{table}" '
                    f'("{day_col}", "{salt_col}") VALUES (%s, %s)',
                    [today, proposed],
                )
            cursor.execute(
                f'SELECT "{salt_col}" FROM "{table}" WHERE "{day_col}" = %s',
                [today],
            )
            row = cursor.fetchone()

        salt = row[0]
        _salt_cache.clear()
        _salt_cache[today] = salt
        return salt


def visitor_id_for(salt: str, ip: str, user_agent: str) -> str:
    """Stable-for-a-day pseudonymous identifier. 16 hex chars (64 bits).

    Byte-faithful port of ``backend/src/analytics.py::visitor_id_for`` — same
    ``f"{salt}|{ip}|{user_agent}|{_SITE_DOMAIN}"`` material, same SHA-256, same
    16-hex truncation, so the persisted ``visitor_id`` is byte-identical to
    the oracle for any given (salt, ip, ua).
    """
    material = f"{salt}|{ip}|{user_agent}|{_SITE_DOMAIN}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:16]


def derive_session_id(visitor_id: str, now: Optional[datetime] = None) -> str:
    """Reuse the visitor's most recent session_id if within the 30-min
    window, else mint a fresh UUID.

    Byte-faithful port of ``backend/src/analytics.py::derive_session_id``. The
    SQLAlchemy ``select(Visit.session_id, Visit.timestamp).where(visitor_id ==
    …).order_by(timestamp.desc()).limit(1)`` becomes the Django ORM
    ``Visit.objects.filter(visitor_id=…).order_by("-timestamp").values_list(
    "session_id", "timestamp").first()`` — same composite-index
    (``ix_visit_visitor_time``) lookup, same "latest visit in the same flow"
    read. The 30-minute window + the non-empty-session guard are identical.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - _SESSION_WINDOW

    recent = (
        Visit.objects.filter(visitor_id=visitor_id)
        .order_by("-timestamp")
        .values_list("session_id", "timestamp")
        .first()
    )

    if recent is not None:
        recent_session_id, recent_timestamp = recent
        if recent_session_id and recent_timestamp >= cutoff:
            return recent_session_id

    return str(uuid.uuid4())


def _reset_salt_cache_for_tests() -> None:
    """Clear the in-process salt cache. Used only by tests.

    Port of ``backend/src/analytics.py::_reset_salt_cache_for_tests``.
    """
    with _salt_lock:
        _salt_cache.clear()

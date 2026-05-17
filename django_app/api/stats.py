"""S5 — Stats API + auth gate.

Byte-faithful port of ``backend/app/api/stats.py`` (the private analytics
endpoint, ``GET /api/stats``, mounted at the ``""`` prefix —
``backend/app/main.py:113``) **and** the stats auth gate
``backend/app/auth.py::require_stats_auth``. Built by copying the F3 worked
reference pattern in ``api/seasons.py`` / the S2 service-consumption pattern
in ``api/standings.py`` (see the PATTERN CHECKLIST in ``api/seasons.py``).

FROZEN-FILE CONTRACT (decision I1-arch=A): this module owns ONLY the body
below. ``api/__init__.py`` (the single ``NinjaAPI`` + router assembly, which
mounts ``api.stats.router`` at the ``""`` prefix — ``api/__init__.py:81``)
and ``config/urls.py`` are FROZEN — never edited. The module-level name
``router`` is kept exactly as the frozen slot pre-stubbed it. The FROZEN
``NinjaAPI`` default ``HttpError`` handler renders ``{"detail": msg}`` via the
F3-pinned renderer (``api/renderers.py``), byte-identical to the FastAPI
oracle for the 200 path.

THE AUTH GATE (byte-parity with backend/app/auth.py)
----------------------------------------------------
The FastAPI router gated EVERY ``/api/stats/*`` endpoint with
``dependencies=[Depends(require_stats_auth)]`` so a new endpoint can't
accidentally ship publicly. Django Ninja has no FastAPI ``Depends``; this is
a pattern redesign (same as F3 turned ``Depends(get_season)`` into an
explicit resolver call) — the auth check is the FIRST thing every stats
handler does, via the shared ``_require_stats_auth`` helper. The OBSERVABLE
contract is byte-identical to ``backend/app/auth.py`` (verified empirically
against the spun oracle):

  * ``STATS_PASSWORD`` unset/empty → dev mode, the gate is a NO-OP and the
    endpoint is openly reachable (auth.py:23-24).
  * No / unparseable Basic credentials → 401, body
    ``{"detail":"Not authenticated"}``, header
    ``WWW-Authenticate: Basic realm="stats"`` (auth.py:26-31; FastAPI's
    ``HTTPBasic(auto_error=False)`` yields ``None`` for a missing OR
    malformed header — both map to "Not authenticated", exactly as X2's
    ``api/docs.py`` ports it).
  * Wrong password → 401, body ``{"detail":"Invalid credentials"}``, same
    ``WWW-Authenticate`` header (auth.py:38-43). Username is NEVER checked;
    password compared in CONSTANT TIME (auth.py:34-37).

The 401 body is rendered through the FROZEN ``NinjaAPI`` singleton's
F3-pinned ``ParityJSONRenderer`` (``api.create_response`` — the ``api``
object is imported LAZILY inside ``_unauthorized`` (no import cycle with the
FROZEN ``api/__init__.py`` which imports this module at assembly time; same
discipline as ``api/renderers.py::pin_parity_renderer``) and read BY
REFERENCE only, never mutated — the same read-only use X2's ``api/docs.py``
makes of it) so the bytes are compact ``{"detail":"…"}`` — byte-identical to
Starlette's ``JSONResponse``. The only divergence is the documented,
parity-safe ``; charset=utf-8`` content-type suffix (see
``api/renderers.py``); ``assert_json_parity`` compares the media-type
prefix, not the charset param.

THE AGGREGATION (byte-parity with backend/app/api/stats.py)
-----------------------------------------------------------
The SQLAlchemy reads are translated to Django ORM line-for-line so the JSON
shape + ordering + numbers match byte-for-byte:

  * ``func.count(Visit.id)``                → ``.count()`` / ``Count("id")``
  * ``count(distinct(visitor_id))`` + where → ``.filter(...).aggregate(
                                               Count("visitor_id",
                                               distinct=True))``
  * group-by + ``order_by(count desc)``     → ``.values(...).annotate(
                                               c=Count("id")).order_by("-c")``
  * per-session duration AVG (Postgres
    ``avg(extract(epoch,max)-extract(
    epoch,min))`` over a ``GROUP BY
    session_id`` subquery, coalesced 0.0) → an equivalent ``Subquery`` +
                                             ``Avg`` + ``Coalesce`` 0.0
  * ``select(Visit).order_by(timestamp
    .desc()).limit(25)``                   → ``.order_by("-timestamp")[:25]``

The READ-side aggregation is kept INLINE here, exactly as the FastAPI oracle
keeps it (``backend/app/api/stats.py``) — there is no shared read helper to
extract (and ``core/analytics.py`` is S6's write-path module; S5 never
touches it). Pure-Python device-detection / salt / session derivation
(``backend/src/analytics.py``) is the WRITE path → S6's scope, NOT read here.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from django.db.models import Avg, Count, Max, Min
from django.db.models.functions import Coalesce, Extract
from django.http import HttpResponse

from api.schemas.stats import (
    CategoryVisitCount,
    ComparisonCount,
    DeviceCount,
    RaceVisitCount,
    RecentVisit,
    RiderVisitCount,
    StatsOut,
)
from core.models import Visit

from ninja import Router

router = Router()


_SESSION_DURATION_WINDOW_DAYS = 30
_TOP_N = 50
_REALM = 'Basic realm="stats"'


# ---------------------------------------------------------------------------
# Stats auth gate — port of backend/app/auth.py::require_stats_auth.
# Returns an HttpResponse (401) to short-circuit the handler, or None to
# allow it through. Ninja returns a handler-returned HttpResponse as-is
# (Operation._result_to_response: ``if isinstance(result, HttpResponseBase):
# return result``), so the 401 bypasses the StatsOut response schema cleanly.
# ---------------------------------------------------------------------------


def _unauthorized(request, detail: str) -> HttpResponse:
    """401 with the FastAPI-identical body + WWW-Authenticate header.

    Body is rendered through the FROZEN NinjaAPI singleton's F3-pinned
    ``ParityJSONRenderer`` so the bytes are compact ``{"detail":"…"}`` —
    byte-identical to Starlette's ``JSONResponse`` (the FastAPI oracle).

    The single FROZEN NinjaAPI instance (``api/__init__.py``) is imported
    LAZILY here — inside the function body — so this module has NO import
    cycle with ``api/__init__.py`` (which imports ``api.stats`` at assembly
    time). Same lazy-import discipline ``api/renderers.py::pin_parity_renderer``
    uses. The singleton is read BY REFERENCE only (never mutated): we just
    call ``create_response`` to render the body through the F3-pinned
    ``ParityJSONRenderer`` — the SAME read-only use X2's ``api/docs.py``
    makes of it.
    """
    from api import api as ninja_api

    resp = ninja_api.create_response(request, {"detail": detail}, status=401)
    resp["WWW-Authenticate"] = _REALM
    return resp


def _require_stats_auth(request) -> HttpResponse | None:
    """None if the request may proceed, else a 401 ``HttpResponse``.

    Mirrors ``backend/app/auth.py`` exactly:
      * empty ``STATS_PASSWORD``  → dev mode, no auth (return None)
      * no / unparseable Basic creds → 401 "Not authenticated"
      * wrong password            → 401 "Invalid credentials"
      * username is never checked; password compared in constant time.
    """
    from django.conf import settings

    stats_password = settings.STATS_PASSWORD
    if not stats_password:
        return None  # dev mode — no auth required (auth.py:23-24)

    header = request.META.get("HTTP_AUTHORIZATION", "")
    scheme, _, payload = header.partition(" ")
    if scheme.lower() != "basic" or not payload:
        # No (parseable) Basic credentials → "Not authenticated"
        # (auth.py:26-31; FastAPI HTTPBasic(auto_error=False) yields None).
        return _unauthorized(request, "Not authenticated")

    import base64
    import binascii

    try:
        decoded = base64.b64decode(payload, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return _unauthorized(request, "Not authenticated")

    _username, sep, password = decoded.partition(":")
    if not sep:
        # Malformed credential (no ':') — FastAPI's HTTPBasic also rejects
        # this as unparseable → "Not authenticated".
        return _unauthorized(request, "Not authenticated")

    # Constant-time compare to mitigate timing attacks (auth.py:34-37).
    password_ok = secrets.compare_digest(
        password.encode("utf-8"),
        stats_password.encode("utf-8"),
    )
    if not password_ok:
        return _unauthorized(request, "Invalid credentials")

    return None  # authenticated


@router.get("/stats", response=StatsOut)
def get_stats(request):
    """GET /api/stats — private analytics (HTTP Basic, eng-review SC-1 / N6).

    Port of ``backend/app/api/stats.py::get_stats``. The auth gate runs FIRST
    (router-level ``Depends(require_stats_auth)`` analogue); on rejection an
    ``HttpResponse`` is returned and Ninja short-circuits it as-is. On the
    allowed path the aggregation below is the line-for-line Django ORM
    translation of the FastAPI handler.
    """
    blocked = _require_stats_auth(request)
    if blocked is not None:
        return blocked

    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    week_cutoff = now - timedelta(days=7)
    month_cutoff = now - timedelta(days=30)
    duration_cutoff = now - timedelta(days=_SESSION_DURATION_WINDOW_DAYS)

    total = Visit.objects.count()

    unique_today = (
        Visit.objects.filter(timestamp__gte=today_start)
        .exclude(visitor_id="")
        .aggregate(c=Count("visitor_id", distinct=True))["c"]
        or 0
    )

    unique_7d = (
        Visit.objects.filter(timestamp__gte=week_cutoff)
        .exclude(visitor_id="")
        .aggregate(c=Count("visitor_id", distinct=True))["c"]
        or 0
    )

    unique_30d = (
        Visit.objects.filter(timestamp__gte=month_cutoff)
        .exclude(visitor_id="")
        .aggregate(c=Count("visitor_id", distinct=True))["c"]
        or 0
    )

    sessions_today = (
        Visit.objects.filter(timestamp__gte=today_start)
        .exclude(session_id="")
        .aggregate(c=Count("session_id", distinct=True))["c"]
        or 0
    )

    # Per-session duration (last 30 days): max(ts) - min(ts) grouped by
    # session_id, then averaged across sessions. A single-hit session
    # contributes 0s — the honest reading (we didn't observe them stay
    # longer than one event). Byte-faithful translation of the SQLAlchemy
    # subquery (SQL verified identical):
    #   SELECT coalesce(avg(cast(
    #       EXTRACT(epoch FROM max(ts)) - EXTRACT(epoch FROM min(ts))
    #       AS float)), 0.0)
    #   FROM (… WHERE ts >= cutoff AND session_id != '' GROUP BY session_id)
    # ``Extract(Max(ts),'epoch') - Extract(Min(ts),'epoch')`` reproduces the
    # per-session second-difference (extracting epoch from each aggregate
    # timestamp separately, exactly as the oracle SQL does — Postgres has no
    # native ``Extract('epoch', interval)`` via the Django ORM); the outer
    # Avg + Coalesce(0.0) reproduces the coalesced cross-session average.
    per_session = (
        Visit.objects.filter(timestamp__gte=duration_cutoff)
        .exclude(session_id="")
        .values("session_id")
        .annotate(
            seconds=Extract(Max("timestamp"), "epoch")
            - Extract(Min("timestamp"), "epoch")
        )
        .values("seconds")
    )
    avg_session_seconds = (
        per_session.aggregate(
            avg=Coalesce(Avg("seconds"), 0.0)
        )["avg"]
        or 0.0
    )

    device_rows = (
        Visit.objects.values("device_type")
        .annotate(count=Count("id"))
        .values_list("device_type", "count")
    )
    devices = [
        DeviceCount(device_type=dt, count=c) for (dt, c) in device_rows
    ]

    per_cat_rows = (
        Visit.objects.filter(page="leaderboard")
        .filter(category__isnull=False)
        .values("category", "season_year")
        .annotate(count=Count("id"))
        .order_by("-count")
        .values_list("category", "season_year", "count")
    )
    per_category = [
        CategoryVisitCount(category=cat, season_year=yr, count=cnt)
        for (cat, yr, cnt) in per_cat_rows
    ]

    per_race_rows = (
        Visit.objects.filter(page="race")
        .filter(event_slug__isnull=False)
        .values("season_year", "event_slug")
        .annotate(count=Count("id"))
        .order_by("-count")
        .values_list("season_year", "event_slug", "count")[:_TOP_N]
    )
    per_race = [
        RaceVisitCount(season_year=yr, event_slug=slug, count=cnt)
        for (yr, slug, cnt) in per_race_rows
    ]

    per_rider_rows = (
        Visit.objects.filter(page="rider")
        .filter(rider_slug__isnull=False)
        .values("season_year", "rider_slug")
        .annotate(count=Count("id"))
        .order_by("-count")
        .values_list("season_year", "rider_slug", "count")[:_TOP_N]
    )
    per_rider = [
        RiderVisitCount(season_year=yr, rider_slug=slug, count=cnt)
        for (yr, slug, cnt) in per_rider_rows
    ]

    # Top compared rider pairs. The track endpoint (S6) normalizes (A,B) and
    # (B,A) into one ordered tuple before insert, so a plain group-by
    # collapses into one row per real pair. S5 only READS whatever rows
    # exist (S6 owns the write of ``compared_with_slug``).
    top_comparisons_rows = (
        Visit.objects.filter(page="compare")
        .filter(rider_slug__isnull=False)
        .filter(compared_with_slug__isnull=False)
        .values("rider_slug", "compared_with_slug")
        .annotate(count=Count("id"))
        .order_by("-count")
        .values_list("rider_slug", "compared_with_slug", "count")[:_TOP_N]
    )
    top_comparisons = [
        ComparisonCount(slug_a=a, slug_b=b, count=cnt)
        for (a, b, cnt) in top_comparisons_rows
    ]

    recent_rows = list(Visit.objects.order_by("-timestamp")[:25])
    recent = [RecentVisit.model_validate(v) for v in recent_rows]

    return StatsOut(
        total_visits=total,
        unique_visitors_today=unique_today,
        unique_visitors_7d=unique_7d,
        unique_visitors_30d=unique_30d,
        sessions_today=sessions_today,
        avg_session_seconds=float(avg_session_seconds),
        devices=devices,
        per_category=per_category,
        per_race=per_race,
        per_rider=per_rider,
        top_comparisons=top_comparisons,
        recent=recent,
    )

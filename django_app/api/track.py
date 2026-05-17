"""S6 — Track / analytics-write.

Byte-faithful port of ``backend/app/api/track.py`` (``POST /api/track``,
mounted at the ``""`` prefix — ``backend/app/main.py:114`` /
``api/__init__.py:82``). Built by copying the F3 worked reference pattern
(``api/seasons.py``) and the S5 disjoint-write discipline: S5 owns the READ
side (``api/stats.py``); S6 owns the WRITE side (``core/analytics.py`` +
this module + the schema + the guards). The two never touch each other.

FROZEN-FILE CONTRACT (decision I1-arch=A): this module owns ONLY the body
below. ``api/__init__.py`` (the single ``NinjaAPI`` + router assembly, which
mounts ``api.track.router`` at the ``""`` prefix — ``api/__init__.py:82``)
and ``config/urls.py`` are FROZEN — never edited. The module-level name
``router`` is kept exactly as the frozen slot pre-stubbed it. Throttling is
wired via Ninja's per-operation ``throttle=`` arg on THIS route (NOT a
``NinjaAPI``-instance edit), which is the FROZEN-file-safe wiring point.

WHAT THIS PORTS
---------------
  * Cookieless visitor-id + daily-salt + 30-min session derivation
    (``core.analytics`` — port of ``backend/src/analytics.py``, atomic
    upsert + in-process cache preserved; see that module's docstring).
  * Proxy-aware client IP (``core.analytics.real_client_ip`` — port of
    ``backend/app/client_ip.py``), reused both as the analytics key and the
    throttle bucket key.
  * Device detection (``core.analytics.detect_device_type`` — port of
    ``backend/src/database.py::detect_device_type``).
  * Compare-page pair normalization: when ``page == "compare"`` and both
    slugs are present, the pair is sorted alphabetically before insert so
    ``(A,B)`` and ``(B,A)`` collapse into ONE stat row — this is the
    ``compared_with_slug`` column S5's ``top_comparisons`` reads (review
    OV3). The normalization is byte-identical to the oracle
    (``backend/app/api/track.py:47-58``).
  * The exact ``Visit`` row shape the oracle wrote (every column, same
    ``timestamp=datetime.now(timezone.utc)`` app-side stamp — F2 did NOT use
    ``auto_now_add``, the write path sets it, mirroring the oracle).
  * The ``{"ok":true}`` 200 response (``TrackOut`` — byte-identical via the
    F3-pinned renderer).

DEFENSES (wired without editing any FROZEN file)
------------------------------------------------
  * 413 pre-parse payload guard:
    ``core.track_guards.TrackPayloadSizeLimitMiddleware`` (registered via the
    additive ``# === S6 ===`` block in ``config/settings.py``, using the X2
    list-mutation discipline — the FROZEN ``api/__init__.py`` is untouched).
  * Per-IP 429 throttle: ``core.track_guards.TrackRateThrottle`` attached via
    the per-operation ``throttle=`` arg below (same 10/minute limit slowapi
    enforced, same ``real_client_ip`` keying).
"""

from __future__ import annotations

from datetime import datetime, timezone

from ninja import Router

from api.schemas.track import TrackIn, TrackOut
from core.analytics import (
    derive_session_id,
    detect_device_type,
    get_or_create_salt,
    real_client_ip,
    visitor_id_for,
)
from core.models import Visit
from core.track_guards import TrackRateThrottle

router = Router()


@router.post("/track", response=TrackOut, throttle=[TrackRateThrottle()])
def track_visit(request, payload: TrackIn) -> TrackOut:
    """POST /api/track — one cookieless page-view (port of the FastAPI handler).

    Line-for-line behavioral mirror of ``backend/app/api/track.py::
    track_visit``. The SQLAlchemy ``session.add(Visit(...))`` becomes
    ``Visit.objects.create(...)`` (same columns, same app-side
    ``timestamp``). The per-operation ``throttle=`` runs BEFORE this body
    (Ninja ``Operation.run`` → ``_check_throttles``); the pre-parse 413 guard
    runs even earlier (settings-registered middleware) so an oversize body
    never reaches the Ninja JSON parser.
    """
    ua = request.META.get("HTTP_USER_AGENT", "") or ""
    ip = real_client_ip(request)

    salt = get_or_create_salt()
    visitor_id = visitor_id_for(salt, ip, ua)
    session_id = derive_session_id(visitor_id)

    # Normalize compare-page pairs alphabetically so (A,B) and (B,A)
    # collapse into one stat row. Anything that's not a comparison
    # passes through unchanged. Byte-identical to backend/app/api/track.py.
    rider_slug = payload.rider_slug
    compared_with_slug = payload.compared_with_slug
    if (
        payload.page == "compare"
        and rider_slug is not None
        and compared_with_slug is not None
        and rider_slug > compared_with_slug
    ):
        rider_slug, compared_with_slug = compared_with_slug, rider_slug

    Visit.objects.create(
        timestamp=datetime.now(timezone.utc),
        page=payload.page,
        category=payload.category,
        season_year=payload.season_year,
        event_slug=payload.event_slug,
        rider_slug=rider_slug,
        compared_with_slug=compared_with_slug,
        device_type=detect_device_type(ua),
        visitor_id=visitor_id,
        session_id=session_id,
    )
    return TrackOut(ok=True)

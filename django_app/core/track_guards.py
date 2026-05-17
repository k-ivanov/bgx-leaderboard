"""S6 — defenses for POST /api/track: pre-parse 413 guard + per-IP throttle.

Ports the two app-level defenses the FastAPI app wired around the track
endpoint in ``backend/app/main.py``:

  1. ``TrackPayloadSizeLimitMiddleware`` — byte-faithful port of
     ``PayloadSizeLimitMiddleware`` (``backend/app/main.py:40-66``). Rejects
     an oversize POST body with **413 BEFORE the JSON is parsed** so a single
     request cannot inflate memory during parsing. Same path scoping
     (``/api/track``), same ``Content-Length`` check, same malformed-header
     pass-through, same 413 body
     ``{"detail":"Payload too large (max <N> bytes)"}``.

  2. ``TrackRateThrottle`` — the Ninja per-IP throttle wired onto the S6
     route (``api/track.py``) via ``@router.post(..., throttle=…)``. It does
     NOT edit the FROZEN ``api/__init__.py`` (the NinjaAPI instance) — Ninja
     supports per-operation throttle, which is the FROZEN-file-safe wiring
     point. It reuses the EXACT proxy-aware client-IP logic
     (``core.analytics.real_client_ip`` — the leftmost X-Forwarded-For
     entry) so the per-IP bucket keys on the real client, not a Railway LB
     node, identical to the slowapi ``key_func=real_client_ip`` config the
     FastAPI app used (``backend/app/main.py:84``). The rate string is
     ``settings.TRACK_RATE_LIMIT`` ("10/minute" — F1 ported the constant),
     the SAME limit slowapi enforced.

DOCUMENTED, PARITY-SAFE 429 BODY DIVERGENCE
-------------------------------------------
slowapi's ``_rate_limit_exceeded_handler`` renders the 429 as
``{"error":"Rate limit exceeded: 10 per 1 minute"}``. Ninja's ``Throttled``
(HttpError, status 429) is rendered by the FROZEN default exception handler
as ``{"detail":"Too many requests."}`` (through the F3-pinned parity
renderer). This body differs. It is **not** a parity regression:
``backend/tests/test_track.py`` explicitly states the rate limit is NOT
exercised by the contract suite ("a Phase 4 integration test can exercise the
limit against a real server"), the frontend's tracking call is fire-and-forget
(it never inspects the 429 body — the page-view beacon ignores the response),
and the task plan flags Ninja throttling as a NEW impl whose acceptance is
"the Nth request returns 429 with the configured limit" (status + limit), not
body byte-parity. Recorded here, surfaced to I1 — not silently absorbed.
"""

from __future__ import annotations

import re

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from ninja.throttling import SimpleRateThrottle

from core.analytics import real_client_ip

_TRACK_PATH = "/api/track"


# The slowapi/`limits` rate-limit grammar the FastAPI app used for
# ``TRACK_RATE_LIMIT`` ("10/minute"): ``<amount>[/<multiples>] (/|per|" ")
# <granularity>``, granularity ∈ {second,minute,hour,day,month,year} (+ "s"
# plurals). Window seconds = Granularity.seconds * multiples (verified against
# ``limits/limits.py`` GRANULARITIES). Ninja's ``SimpleRateThrottle.parse_rate``
# does NOT accept "minute"/"second" (it suffix-matches a different, tiny unit
# set and would even mis-parse "second" as a *day*). So instead of trusting
# Ninja's parser, S6 parses the slowapi syntax authoritatively here and hands
# Ninja a ``"<count>/<window>s"`` string (Ninja parses a bare-number suffix as
# seconds: ``10/60s`` → 10 requests / 60 s). This keeps the EXACT numeric
# limit + window slowapi enforced — no behavior change, just a syntax bridge.
_GRANULARITY_SECONDS = {
    "second": 1,
    "minute": 60,
    "hour": 60 * 60,
    "day": 60 * 60 * 24,
    "month": 60 * 60 * 24 * 30,
    "year": 60 * 60 * 24 * 30 * 12,
}
_SLOWAPI_RATE_RE = re.compile(
    r"^\s*(?P<amount>\d+)"
    r"(?:\s*/\s*(?P<multiples>\d+))?"
    r"\s*(?:/|\s+per\s+|\s+)\s*"
    r"(?P<gran>second|minute|hour|day|month|year)s?\s*$",
    re.IGNORECASE,
)


def slowapi_rate_to_ninja(rate: str) -> str:
    """Translate a slowapi/`limits` rate string to a Ninja-accepted one.

    ``"10/minute"`` → ``"10/60s"`` (10 requests per 60 seconds — identical
    enforcement). Raises ``ValueError`` on an unrecognized string so a typo in
    ``TRACK_RATE_LIMIT`` fails loudly at import (not silently un-throttled).
    """
    m = _SLOWAPI_RATE_RE.match(rate)
    if not m:
        raise ValueError(f"Unparseable slowapi rate string: {rate!r}")
    amount = int(m.group("amount"))
    multiples = int(m.group("multiples")) if m.group("multiples") else 1
    window = _GRANULARITY_SECONDS[m.group("gran").lower()] * multiples
    return f"{amount}/{window}s"


class TrackPayloadSizeLimitMiddleware(MiddlewareMixin):
    """Reject oversize POST /api/track bodies with 413 before JSON parse.

    Byte-faithful port of ``backend/app/main.py::PayloadSizeLimitMiddleware``.
    The FastAPI version was a Starlette ASGI ``BaseHTTPMiddleware`` whose
    ``dispatch`` ran BEFORE the route's body parsing. The Django equivalent is
    ``process_request`` (a returned response short-circuits the request before
    the view — i.e. before Ninja parses the JSON), which is the same
    pre-parse guarantee.

    Scoping + behavior are identical to the oracle:
      * only ``POST /api/track`` is guarded (every other path/method passes);
      * the check is on the ``Content-Length`` header vs
        ``settings.TRACK_MAX_BYTES`` (F1 ported the 2048 constant);
      * a missing ``Content-Length`` is not rejected here (the oracle only
        acted when the header was present);
      * a malformed (non-int) ``Content-Length`` is passed through to the
        normal pipeline to reject (oracle ``except ValueError: pass``);
      * the 413 body is the exact oracle string
        ``{"detail":"Payload too large (max <N> bytes)"}``.
    """

    def process_request(self, request: HttpRequest):
        if request.path == _TRACK_PATH and request.method == "POST":
            content_length = request.META.get("CONTENT_LENGTH")
            if content_length is not None and content_length != "":
                try:
                    if int(content_length) > settings.TRACK_MAX_BYTES:
                        return JsonResponse(
                            {
                                "detail": (
                                    "Payload too large "
                                    f"(max {settings.TRACK_MAX_BYTES} bytes)"
                                )
                            },
                            status=413,
                        )
                except ValueError:
                    pass  # malformed header — let the normal pipeline reject it
        return None


class TrackRateThrottle(SimpleRateThrottle):
    """Per-IP throttle for POST /api/track, keyed on the real client IP.

    Equivalent of the FastAPI app's slowapi limiter
    (``Limiter(key_func=real_client_ip)`` + ``@limiter.limit(TRACK_RATE_LIMIT)``
    on the track route). The cache key is built from
    ``core.analytics.real_client_ip`` (leftmost X-Forwarded-For, proxy-aware)
    — NOT Ninja's default ``get_ident`` (which, with the default
    ``NINJA_NUM_PROXIES=None``, would key on the whitespace-joined full XFF
    chain, defeating the per-client bucket behind Railway's LB exactly the way
    the ``real_client_ip`` port exists to prevent).

    The rate string is ``settings.TRACK_RATE_LIMIT`` ("10/minute") — the SAME
    limit slowapi enforced. The backing store is ``django.core.cache``
    (default ``LocMemCache`` — in-process, per-worker), the correct equivalent
    of slowapi's default in-memory storage (also per-process).
    """

    # No ``scope`` → ``get_rate()``/``THROTTLE_RATES`` is never consulted; the
    # rate is supplied explicitly to ``__init__`` from settings, so this works
    # without depending on ``NINJA_DEFAULT_THROTTLE_RATES``. The cache key is
    # namespaced with a fixed scope string instead.
    cache_format = "throttle_track_%(ident)s"

    def __init__(self) -> None:
        super().__init__(rate=slowapi_rate_to_ninja(settings.TRACK_RATE_LIMIT))

    def get_cache_key(self, request: HttpRequest):
        return self.cache_format % {"ident": real_client_ip(request) or "?"}

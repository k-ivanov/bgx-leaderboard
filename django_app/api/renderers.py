"""Pinned JSON renderer — serialization parity (F3 / decision I5-cq=A).

THE PROBLEM
-----------
Django Ninja's default ``JSONRenderer`` does
``json.dumps(data, cls=NinjaJSONEncoder)`` with **no params**, i.e. Python's
``json.dumps`` defaults:

    separators=(", ", ": ")   # spaces after every comma + colon
    ensure_ascii=True         # non-ASCII escaped to \\uXXXX
    sort_keys=False

The frozen FastAPI app it must byte-replace renders every JSON response via
Starlette's ``JSONResponse.render``:

    json.dumps(content, ensure_ascii=False, allow_nan=False,
               indent=None, separators=(",", ":"))

So out of the box the new app's bytes would DIFFER from the parity oracle on
**every** response (whitespace + every Cyrillic name escaped). The dashboard
is full of Cyrillic ("ПРОФИ", "Иван ИВАНОВ", …) and the frontend's
``openapi-typescript`` client + the ported contract suite assume the exact
current bytes. F3 therefore PINS the renderer.

THE SERIALIZATION SPEC (pinned, byte-exact vs the FastAPI oracle)
-----------------------------------------------------------------
``ParityJSONRenderer`` reproduces Starlette's ``json.dumps`` call EXACTLY:

  * ``separators=(",", ":")``  — compact, no whitespace. (Oracle verified:
    ``{"seasons":[{"year":2026,...}]}`` — zero spaces.)
  * ``ensure_ascii=False``     — non-ASCII emitted as raw UTF-8.
    (Oracle verified: ``"display_name":"ПРОФИ"`` — not ``\\u041f…``.)
  * ``allow_nan=False``        — same as Starlette; ``NaN``/``Infinity`` are
    a hard error, never the non-standard ``NaN`` token. (The dataset has no
    NaN; this only matters as a defensive invariant.)
  * ``indent=None``            — single line (Starlette passes this
    explicitly; it is also ``json.dumps``'s default — kept for exactness).
  * key order = field declaration order. ``sort_keys`` is left default
    (``False``) — Pydantic ``model_dump`` preserves field-definition order
    and the renderer never re-sorts. The common schemas
    (``api/schemas/common.py``) declare fields in the SAME order as the
    Pydantic schemas in ``backend/app/schemas/`` so the key order is
    byte-identical.
  * ``cls=NinjaJSONEncoder`` is RETAINED (Ninja's encoder, a
    ``DjangoJSONEncoder`` subclass). It governs the non-JSON-native types:
      - ``datetime.date``  → ``"YYYY-MM-DD"`` ISO 8601. Matches the oracle
        (Pydantic v2 serializes ``date`` to ISO ``YYYY-MM-DD`` — oracle
        verified: ``"event_date":"2026-03-28"``).
      - ``datetime``       → ISO 8601 (used by S5/S6 ``Visit.timestamp``).
      - ``Decimal``        → Django's ``DjangoJSONEncoder`` would emit a
        Decimal as a JSON **string**. This is NEVER reached for the public
        API: every schema that surfaces ``event_result.points``
        (``numeric(6,2)``) types the field as ``float`` (see
        ``backend/app/schemas/standings.py`` — ``points: float``,
        ``total_points: float``). Pydantic coerces the ORM ``Decimal`` to a
        Python ``float`` during response validation, so by the time the
        renderer runs the value is already a ``float`` and is emitted as a
        JSON number (oracle verified: ``"total_points":137.0`` — a number
        with a trailing ``.0``, NOT a quoted string, NOT a bare int). The
        Decimal→string path is documented + asserted-against in
        ``tests/parity.py::assert_json_parity`` purely as a guard so a
        future slice that forgets the ``float`` annotation FAILS LOUDLY
        instead of silently shipping ``"137.00"``.

KNOWN, ACCEPTED, PARITY-SAFE DIVERGENCE (documented for I1)
-----------------------------------------------------------
The response **body bytes** are byte-identical to the oracle. The
``Content-Type`` header is NOT: the frozen ``NinjaAPI.create_response``
builds it from ``f"{renderer.media_type}; charset={renderer.charset}"``, so
Ninja emits ``application/json; charset=utf-8`` while Starlette emits bare
``application/json``. This is:
  * RFC 9110 §8.3 equivalent (``charset`` is advisory for ``application/json``,
    which is always UTF-8);
  * tolerated by every existing consumer — the ported suite asserts
    ``content-type.startswith("application/json")`` (passes), and the Astro
    frontend / its ``openapi-typescript`` client never assert the response
    ``Content-Type`` (they only SET it on requests);
  * not fixable from F3 without editing the FROZEN ``api/__init__.py`` /
    Ninja's ``create_response`` (out of scope, decision I1-arch=A).
``media_type`` is kept exactly ``"application/json"`` so the prefix matches.
``assert_json_parity`` therefore compares JSON BODIES (the F3 contract), and
the header delta is recorded here + surfaced to I1, not silently absorbed.

WIRING (no FROZEN-file edit)
----------------------------
``api/__init__.py`` is FROZEN (F1, decision I1-arch=A) and constructs the
single ``NinjaAPI`` WITHOUT a ``renderer=`` arg, so it defaults to the
unpinned ``JSONRenderer``. ``NinjaAPI`` stores the renderer as a plain
attribute (``self.renderer = renderer or JSONRenderer()``) and reads it LIVE
per request inside ``create_response`` (``self.renderer.render(...)`` +
``self.get_content_type()``) — it is NOT bound at route-registration time.
F3 therefore pins it by REASSIGNING ``api.renderer`` on the singleton at
Django app-ready time (``core.apps.CoreConfig.ready`` →
``api.renderers.pin_parity_renderer``). This touches no frozen file and is
idempotent. ``install()`` is also safe to call directly in tests.
"""

from __future__ import annotations

import json
from typing import Any

from django.http import HttpRequest
from ninja.renderers import BaseRenderer
from ninja.responses import NinjaJSONEncoder


class ParityJSONRenderer(BaseRenderer):
    """``json.dumps`` params byte-identical to Starlette ``JSONResponse``.

    See the module docstring for the full pinned spec + the one documented
    Content-Type divergence.
    """

    media_type = "application/json"
    # NinjaAPI.get_content_type() => f"{media_type}; charset={charset}".
    # Starlette emits bare "application/json"; the "; charset=utf-8" suffix
    # is the documented, parity-safe divergence (see module docstring).
    charset = "utf-8"

    def render(self, request: HttpRequest, data: Any, *, response_status: int) -> Any:
        return json.dumps(
            data,
            cls=NinjaJSONEncoder,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        )


def install(api) -> None:
    """Pin ``ParityJSONRenderer`` onto a ``NinjaAPI`` instance (idempotent).

    Reassigns the live ``api.renderer`` attribute — effective immediately and
    per-request because Ninja reads it live in ``create_response``. No frozen
    file is edited.
    """
    if not isinstance(api.renderer, ParityJSONRenderer):
        api.renderer = ParityJSONRenderer()


def pin_parity_renderer() -> None:
    """App-ready hook: import the FROZEN singleton and pin the renderer.

    Imported lazily (inside the function body) so this module has no import
    cycle with ``api/__init__.py`` and is safe to import from
    ``core.apps.CoreConfig.ready``.
    """
    from api import api as ninja_api

    install(ninja_api)


__all__ = ["ParityJSONRenderer", "install", "pin_parity_renderer"]

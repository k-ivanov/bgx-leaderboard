"""Strict parity polish for the FROZEN ``NinjaAPI`` singleton — ledger #2 + #6.

This module is the parity-polish slice's NON-frozen home for the two global
``NinjaAPI`` behaviors that cannot live in a per-endpoint slice module and
must NOT edit the FROZEN ``api/__init__.py`` / ``config/urls.py``:

  * ledger #2 — register a ``Throttled`` exception handler that returns the
    slowapi/FastAPI 429 body byte-for-byte.
  * ledger #6 — make the generated OpenAPI byte-match the FastAPI oracle for
    the frontend-relevant surface: FastAPI-convention operationIds, the
    auto-injected ``422`` response + ``HTTPValidationError`` / ``ValidationError``
    component schemas, ``HTTPBasic`` security scheme, the ``/health`` path,
    canonical parameter order, and the ``"Successful Response"`` 200 wording.

WIRING (no FROZEN-file edit) — same idiom F3 pinned the renderer with
---------------------------------------------------------------------
``api/__init__.py`` + ``config/urls.py`` are FROZEN (F1, decision I1-arch=A).
Ninja reads ``api._exception_handlers``, ``api.get_openapi_operation_id`` and
``api.get_openapi_schema`` LIVE off the singleton instance, so reassigning /
extending them at Django app-ready time is fully effective and edits no
frozen file — exactly the live-attribute mechanism
``api.renderers.pin_parity_renderer`` already exploits. ``install_parity_hooks``
is invoked additively from ``core.apps.CoreConfig.ready`` (right after
``pin_parity_renderer()``), is idempotent, and is safe to call directly in
tests.
"""

from __future__ import annotations

import re
from types import MethodType
from typing import Any, Dict

from django.conf import settings

# ---------------------------------------------------------------------------
# ledger #2 — Throttled 429 body byte-parity with slowapi / FastAPI
# ---------------------------------------------------------------------------
#
# The FastAPI oracle rate-limits POST /api/track via slowapi. slowapi's
# ``_rate_limit_exceeded_handler`` renders the 429 as a Starlette
# ``JSONResponse({"error": f"Rate limit exceeded: {exc.detail}"}, 429)`` with
# NO rate-limit headers (the oracle builds ``Limiter(... )`` with the default
# ``headers_enabled=False`` and ``default_limits=[]``, so ``_inject_headers``
# is a no-op — verified against backend/.venv slowapi 0.x extension.py:80-86 +
# _inject_headers L380 ``self._headers_enabled`` gate).
#
# ``exc.detail`` is ``str(limit.limit)`` (slowapi/errors.py:17-27, no custom
# ``error_message``), and ``limits.RateLimitItem.__repr__`` (used as ``str``;
# no ``__str__`` defined) is exactly:
#     f"{amount} per {multiples} {granularity_name}"   # granularity ALWAYS
#                                                       # singular, even >1
# For TRACK_RATE_LIMIT == "10/minute" → detail == "10 per 1 minute" → body
# bytes ``{"error":"Rate limit exceeded: 10 per 1 minute"}``.
#
# Ninja's default ``Throttled`` (HttpError, 429) is rendered by the FROZEN
# default ``HttpError`` handler as ``{"detail":"Too many requests."}``. We
# register a MORE-SPECIFIC handler for ``Throttled`` (Ninja's
# ``_lookup_exception_handler`` walks ``type(exc).__mro__`` so a ``Throttled``
# entry wins over the ``HttpError`` entry) that reproduces slowapi's body
# byte-for-byte and routes it through ``api.create_response`` so it gets the
# F3-pinned ``ParityJSONRenderer`` + the ledger-#1 bare ``application/json``
# content-type — identical bytes AND identical header to the Starlette oracle.

# The slowapi / ``limits`` rate grammar — the SAME grammar the S6
# ``core.track_guards`` module documents/parses. Re-derived here (not imported)
# so this parity hook stays self-contained and the four targeted source fixes
# remain the only edited slice files (no behavior change to track_guards).
_SLOWAPI_RATE_RE = re.compile(
    r"^\s*(?P<amount>\d+)"
    r"(?:\s*/\s*(?P<multiples>\d+))?"
    r"\s*(?:/|\s+per\s+|\s+)\s*"
    r"(?P<gran>second|minute|hour|day|month|year)s?\s*$",
    re.IGNORECASE,
)


def slowapi_rate_detail(rate: str) -> str:
    """``"10/minute"`` → ``"10 per 1 minute"`` — byte-identical to slowapi.

    Reproduces ``str(limits.parse(rate))`` (``RateLimitItem.__repr__``) for the
    slowapi rate strings this app uses, WITHOUT importing ``limits`` (it lives
    only in the frozen ``backend/.venv``, not the Django runtime). Raises
    ``ValueError`` on an unparseable string so a typo in ``TRACK_RATE_LIMIT``
    fails loudly rather than silently shipping a wrong 429 body.
    """
    m = _SLOWAPI_RATE_RE.match(rate)
    if not m:
        raise ValueError(f"Unparseable slowapi rate string: {rate!r}")
    amount = int(m.group("amount"))
    multiples = int(m.group("multiples")) if m.group("multiples") else 1
    granularity = m.group("gran").lower()  # limits emits the SINGULAR name
    return f"{amount} per {multiples} {granularity}"


def _throttled_handler(request, exc, *, api):
    """``Throttled`` → byte-exact slowapi/FastAPI 429.

    Body == ``{"error":"Rate limit exceeded: <slowapi detail>"}``; status 429;
    no rate-limit headers (oracle's slowapi limiter ran with
    ``headers_enabled=False``). Routed through ``api.create_response`` so the
    pinned renderer + bare content-type apply — identical to the Starlette
    ``JSONResponse`` the oracle emits.
    """
    detail = slowapi_rate_detail(settings.TRACK_RATE_LIMIT)
    return api.create_response(
        request,
        {"error": f"Rate limit exceeded: {detail}"},
        status=429,
    )


# ---------------------------------------------------------------------------
# ledger #6 — OpenAPI byte-parity with the FastAPI oracle
# ---------------------------------------------------------------------------
#
# Two coordinated, additive overrides on the singleton (no frozen edit):
#
#   1. ``api.get_openapi_operation_id`` → FastAPI's ``generate_unique_id``
#      convention (fastapi/utils.py:95-99):
#          op_id = re.sub(r"\W", "_", f"{func.__name__}{path}")
#          op_id = f"{op_id}_{method.lower()}"
#      The hook only receives the ``Operation`` (router-relative path, no
#      prefix), so it returns the bare ``func.__name__`` (== FastAPI's
#      ``route.name``); the post-processor — which DOES have the full path as
#      the schema dict key — finalizes the exact FastAPI transform. ``\W→_``
#      on an already-valid identifier is a no-op, so name-then-path-then-method
#      reproduces FastAPI's whole-string substitution byte-for-byte.
#
#   2. ``api.get_openapi_schema`` → call Ninja's generator, then mutate the
#      dict so paths + component schemas + operationId + 422 + security match
#      the oracle. This is the ONE post-processor (a single schema-dict
#      mutation) the task asked for — NOT per-endpoint decorators across slice
#      modules.

# FastAPI auto-emits these two components verbatim (HTTPException 422 model).
# Captured byte-exact from the spun oracle's SERVED get_openapi() output —
# key + property ORDER preserved exactly (Pydantic field-definition order, NOT
# alphabetical), because the served schema dict is JSON-dumped WITHOUT
# sort_keys and openapi-typescript preserves member order. Do NOT reorder
# these dict literals.
_HTTP_VALIDATION_ERROR_SCHEMA: Dict[str, Any] = {
    "properties": {
        "detail": {
            "items": {"$ref": "#/components/schemas/ValidationError"},
            "type": "array",
            "title": "Detail",
        }
    },
    "type": "object",
    "title": "HTTPValidationError",
}
_VALIDATION_ERROR_SCHEMA: Dict[str, Any] = {
    "properties": {
        "loc": {
            "items": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
            "type": "array",
            "title": "Location",
        },
        "msg": {"type": "string", "title": "Message"},
        "type": {"type": "string", "title": "Error Type"},
        "input": {"title": "Input"},
        "ctx": {"type": "object", "title": "Context"},
    },
    "type": "object",
    "required": ["loc", "msg", "type"],
    "title": "ValidationError",
}
_SECURITY_SCHEME_HTTPBASIC: Dict[str, Any] = {
    "HTTPBasic": {"scheme": "basic", "type": "http"}
}
_VALIDATION_422_RESPONSE: Dict[str, Any] = {
    "description": "Validation Error",
    "content": {
        "application/json": {
            "schema": {"$ref": "#/components/schemas/HTTPValidationError"}
        }
    },
}

# FastAPI's ``/health`` operation (it lives on the FastAPI app, not the
# Ninja router-band; the committed frontend client expects it). Captured
# byte-exact from the oracle.
_HEALTH_PATH_ITEM: Dict[str, Any] = {
    "get": {
        "operationId": "health_health_get",
        "responses": {
            "200": {
                "content": {
                    "application/json": {
                        "schema": {
                            "additionalProperties": True,
                            "title": "Response Health Health Get",
                            "type": "object",
                        }
                    }
                },
                "description": "Successful Response",
            }
        },
        "summary": "Health",
        "tags": ["meta"],
    }
}

# Canonical parameter order, keyed by (openapi-path, method) — the FastAPI
# oracle's exact ``parameters`` ordering (its dependency-tree traversal order,
# which is NOT URL order and is sourced from the frozen backend signatures).
# The public surface is frozen by F1, so this mapping is fixed; an operation
# absent here keeps Ninja's order (single-/no-param ops already match).
_ORACLE_PARAM_ORDER: Dict[tuple, list] = {
    ("/api/riders/career", "get"): [("slug", "query")],
    ("/api/riders/search", "get"): [("q", "query"), ("limit", "query")],
    ("/api/seasons/{year}", "get"): [("year", "path")],
    (
        "/api/seasons/{year}/categories/{category_code}/events/{event_slug}",
        "get",
    ): [("event_slug", "path"), ("category_code", "path"), ("year", "path")],
    ("/api/seasons/{year}/events", "get"): [("year", "path")],
    ("/api/seasons/{year}/events/{event_slug}", "get"): [
        ("event_slug", "path"),
        ("year", "path"),
    ],
    ("/api/seasons/{year}/riders/search", "get"): [
        ("year", "path"),
        ("q", "query"),
        ("limit", "query"),
    ],
    ("/api/seasons/{year}/riders/{race_number}", "get"): [
        ("race_number", "path"),
        ("year", "path"),
    ],
    ("/api/seasons/{year}/riders/{race_number}/{slug}", "get"): [
        ("race_number", "path"),
        ("slug", "path"),
        ("year", "path"),
    ],
    ("/api/seasons/{year}/standings/{category_code}", "get"): [
        ("category_code", "path"),
        ("year", "path"),
    ],
}

# Operations whose oracle 200 carries security (HTTP Basic gate). The Ninja
# new app gates /api/stats via a custom router-level auth that does not surface
# as a Ninja security scheme; FastAPI's ``Depends(require_stats_auth)`` does.
_ORACLE_SECURITY: Dict[tuple, list] = {
    ("/api/stats", "get"): [{"HTTPBasic": []}],
}

# Canonical path *order* — the exact order the spun FastAPI oracle serves
# ``/api/openapi.json`` in (== the order the committed
# ``frontend/src/lib/api.openapi.ts`` was generated from). FastAPI iterates
# ``app.routes`` (route-registration order); Ninja iterates its router-add
# order, which differs. openapi-typescript preserves ``paths`` insertion
# order, so reordering here makes the served schema byte-identical (and the
# regenerated client diff-empty on path order). The public surface is frozen
# by F1, so this list is fixed; any path not listed keeps its relative
# position appended at the end (defensive — never hit for the frozen surface).
_ORACLE_PATH_ORDER = [
    "/health",
    "/api/seasons",
    "/api/seasons/{year}",
    "/api/seasons/{year}/standings/{category_code}",
    "/api/seasons/{year}/events",
    "/api/seasons/{year}/events/{event_slug}",
    "/api/seasons/{year}/categories/{category_code}/events/{event_slug}",
    "/api/seasons/{year}/riders/search",
    "/api/seasons/{year}/riders/{race_number}",
    "/api/seasons/{year}/riders/{race_number}/{slug}",
    "/api/riders/career",
    "/api/riders/search",
    "/api/stats",
    "/api/track",
]

_NON_METHOD_KEYS = {"parameters", "summary", "description", "servers"}


def _fastapi_operation_id(func_name: str, openapi_path: str, method: str) -> str:
    """FastAPI ``generate_unique_id`` (utils.py:95-99), byte-for-byte."""
    op_id = re.sub(r"\W", "_", f"{func_name}{openapi_path}")
    return f"{op_id}_{method.lower()}"


def _reorder_parameters(params: list, order: list) -> list:
    """Reorder ``params`` to match the oracle's ``[(name, in), ...]`` order.

    Stable: any param not named in ``order`` (should not happen for the frozen
    surface) is appended preserving its relative position.
    """
    index = {(p.get("name"), p.get("in")): p for p in params}
    ordered = [index.pop(key) for key in order if key in index]
    ordered.extend(p for p in params if (p.get("name"), p.get("in")) in
                   {(q.get("name"), q.get("in")) for q in index.values()})
    return ordered


def _post_process_openapi(schema: dict) -> dict:
    """Mutate Ninja's generated OpenAPI dict to byte-match the FastAPI oracle.

    Idempotent (re-applying the same transforms is a no-op). Operates on the
    schema dict only — no per-endpoint decorators, no slice-module edits.
    """
    schema = dict(schema)

    # -- top-level: drop Ninja's empty ``servers`` (oracle has no such key) --
    if schema.get("servers") in ([], None):
        schema.pop("servers", None)

    paths = schema.setdefault("paths", {})

    for path, path_item in list(paths.items()):
        for method, op in list(path_item.items()):
            if method in _NON_METHOD_KEYS or not isinstance(op, dict):
                continue

            # 1. operationId → FastAPI convention. Ninja's
            #    get_openapi_operation_id (overridden below) put the bare
            #    func name in ``operationId``; finalize with the full path.
            func_name = op.get("operationId", "")
            op["operationId"] = _fastapi_operation_id(func_name, path, method)

            # 2. canonical parameter order.
            order = _ORACLE_PARAM_ORDER.get((path, method))
            if order and isinstance(op.get("parameters"), list):
                op["parameters"] = _reorder_parameters(op["parameters"], order)
            # FastAPI omits an empty ``parameters`` list entirely.
            if op.get("parameters") == []:
                op.pop("parameters")

            responses = op.setdefault("responses", {})

            # 3. 200 description wording == FastAPI's "Successful Response".
            if "200" in responses and isinstance(responses["200"], dict):
                responses["200"]["description"] = "Successful Response"

            # 4. inject the 422 the FastAPI oracle auto-emits. FastAPI's rule
            #    (verified across all 14 oracle ops): an operation gets a 422
            #    iff it has >=1 parameter OR a request body (validation can
            #    fail). No params + no body → no 422.
            has_params = bool(op.get("parameters"))
            has_body = "requestBody" in op
            if (has_params or has_body) and "422" not in responses:
                responses["422"] = dict(_VALIDATION_422_RESPONSE)

            # 5. security (HTTP Basic gate) where the oracle has it.
            sec = _ORACLE_SECURITY.get((path, method))
            if sec is not None:
                op["security"] = [dict(s) for s in sec]

    # 6. ``/health`` — served by Django outside the Ninja band; the frozen
    #    FastAPI app surfaces it in the schema and the committed frontend
    #    client expects it. Inject byte-exact, THEN reorder all paths to the
    #    oracle's served order (FastAPI route-registration order; Ninja's
    #    router-add order differs and openapi-typescript preserves insertion
    #    order, so this is required for a path-order-clean regenerated client).
    if "/health" not in paths:
        paths["/health"] = dict(_HEALTH_PATH_ITEM)
    ordered_paths = {
        p: paths[p] for p in _ORACLE_PATH_ORDER if p in paths
    }
    # append any path not in the canonical list (never hit for frozen surface)
    for p, item in paths.items():
        if p not in ordered_paths:
            ordered_paths[p] = item
    schema["paths"] = ordered_paths

    # 7. component schemas + security scheme the oracle auto-emits, then sort
    #    ``components.schemas`` ALPHABETICALLY. FastAPI's ``get_openapi``
    #    emits component schemas alphabetically by name; Ninja emits them in
    #    reference-discovery order. openapi-typescript preserves
    #    ``components.schemas`` insertion order, so sorting here makes the
    #    served schema + the regenerated client byte-identical on schema
    #    declaration order (verified: the committed client's schema block is
    #    strictly alphabetical).
    components = schema.setdefault("components", {})
    comp_schemas = components.setdefault("schemas", {})
    comp_schemas.setdefault("HTTPValidationError", dict(_HTTP_VALIDATION_ERROR_SCHEMA))
    comp_schemas.setdefault("ValidationError", dict(_VALIDATION_ERROR_SCHEMA))
    components["schemas"] = {
        name: comp_schemas[name] for name in sorted(comp_schemas)
    }
    sec_schemes = components.setdefault("securitySchemes", {})
    for name, body in _SECURITY_SCHEME_HTTPBASIC.items():
        sec_schemes.setdefault(name, dict(body))

    return schema


def install_parity_hooks() -> None:
    """App-ready hook: pin ledger #2 + #6 onto the FROZEN ``NinjaAPI``.

    Imported lazily so this module has no import cycle with
    ``api/__init__.py`` and is safe to import from
    ``core.apps.CoreConfig.ready``. Idempotent.
    """
    from api import api as ninja_api
    from ninja.errors import Throttled

    # -- ledger #2: more-specific Throttled handler (wins over HttpError) --
    ninja_api.add_exception_handler(
        Throttled,
        lambda request, exc: _throttled_handler(request, exc, api=ninja_api),
    )

    # -- ledger #6a: FastAPI-convention operationId base (bare func name) --
    def _operation_id(self, operation) -> str:  # noqa: ANN001
        # FastAPI's route.name == the endpoint function __name__. The
        # post-processor appends ``_<path>_<method>`` with the \W→_ transform.
        return operation.view_func.__name__

    ninja_api.get_openapi_operation_id = MethodType(_operation_id, ninja_api)

    # -- ledger #6b: OpenAPI post-processor on the singleton ---------------
    if getattr(
        ninja_api.get_openapi_schema, "__bgx_parity_wrapped__", False
    ):
        return  # already wrapped — idempotent
    _orig_get_openapi_schema = ninja_api.get_openapi_schema

    def _wrapped_get_openapi_schema(self, **kwargs):  # noqa: ANN001
        return _post_process_openapi(_orig_get_openapi_schema(**kwargs))

    bound = MethodType(_wrapped_get_openapi_schema, ninja_api)
    bound.__func__.__bgx_parity_wrapped__ = True  # type: ignore[attr-defined]
    ninja_api.get_openapi_schema = bound


__all__ = [
    "install_parity_hooks",
    "slowapi_rate_detail",
]

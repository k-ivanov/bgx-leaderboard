"""S6 — ``real_client_ip`` parity (port of ``backend/tests/test_client_ip.py``).

Pins the behavior of ``core.analytics.real_client_ip`` — the function that
fixes the "one user looks like 16 visitors behind Railway" bug AND keys the
per-IP throttle bucket. The FastAPI source read ``request.headers`` /
``request.client`` (Starlette); the Django port reads
``request.META["HTTP_X_FORWARDED_FOR"]`` / ``["REMOTE_ADDR"]``. Each oracle
assertion is ported one-to-one so the leftmost-XFF + whitespace-strip +
REMOTE_ADDR-fallback + empty-string behavior is byte-identical.

No DB, no Postgres — pure function. Runs in the Tier-1 ``-m "not parity"``
gate (no ``seeded_orm``/``parity_rig`` fixture → not auto-tiered).
"""

from __future__ import annotations

from django.test import RequestFactory

from core.analytics import real_client_ip


def _req(remote_addr: str | None, xff: str | None):
    rf = RequestFactory()
    extra = {}
    if xff is not None:
        extra["HTTP_X_FORWARDED_FOR"] = xff
    request = rf.get("/", **extra)
    if remote_addr is None:
        request.META.pop("REMOTE_ADDR", None)
    else:
        request.META["REMOTE_ADDR"] = remote_addr
    return request


def test_uses_xff_first_entry_when_present():
    # Ported: backend/tests/test_client_ip.py::test_uses_xff_first_entry_when_present
    req = _req("10.0.0.1", "203.0.113.5, 10.0.0.1")  # 10.0.0.1 = Railway node
    assert real_client_ip(req) == "203.0.113.5"


def test_strips_whitespace_around_xff_value():
    # Ported: backend/tests/test_client_ip.py::test_strips_whitespace_around_xff_value
    req = _req("10.0.0.1", "  198.51.100.7  ,  10.0.0.1  ")
    assert real_client_ip(req) == "198.51.100.7"


def test_falls_back_to_client_host_when_no_xff():
    # Ported: backend/tests/test_client_ip.py::test_falls_back_to_client_host_when_no_xff
    req = _req("192.168.1.50", None)
    assert real_client_ip(req) == "192.168.1.50"


def test_empty_string_when_no_signal():
    # Ported: backend/tests/test_client_ip.py::test_empty_string_when_no_signal
    req = _req(None, None)
    assert real_client_ip(req) == ""

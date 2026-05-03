"""Pin behavior of real_client_ip — the function that fixes the
'one user looks like 16 visitors behind Railway' bug."""

from starlette.requests import Request

from app.client_ip import real_client_ip


def _make_request(client_host: str | None, headers: list[tuple[bytes, bytes]]) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers,
        "client": (client_host, 0) if client_host else None,
    }
    return Request(scope)


def test_uses_xff_first_entry_when_present():
    req = _make_request(
        "10.0.0.1",  # would be Railway proxy node
        [(b"x-forwarded-for", b"203.0.113.5, 10.0.0.1")],
    )
    assert real_client_ip(req) == "203.0.113.5"


def test_strips_whitespace_around_xff_value():
    req = _make_request(
        "10.0.0.1",
        [(b"x-forwarded-for", b"  198.51.100.7  ,  10.0.0.1  ")],
    )
    assert real_client_ip(req) == "198.51.100.7"


def test_falls_back_to_client_host_when_no_xff():
    req = _make_request("192.168.1.50", headers=[])
    assert real_client_ip(req) == "192.168.1.50"


def test_empty_string_when_no_signal():
    req = _make_request(None, headers=[])
    assert real_client_ip(req) == ""

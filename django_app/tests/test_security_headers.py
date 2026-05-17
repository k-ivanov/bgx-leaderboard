"""X2 — pin baseline security headers (Django port of
backend/tests/test_security_headers.py).

Every assertion mirrors the FastAPI test 1:1, plus the review-OV3 addition:
HSTS MUST be emitted for a Railway-forwarded-HTTPS request (proxy header
honored), not only for a directly-TLS request. The exact header VALUES are
asserted against backend/app/security_headers.py.
"""

from django.test import Client

client = Client()


def test_health_carries_security_headers():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in res.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in res.headers["Content-Security-Policy"]
    assert "geolocation=()" in res.headers["Permissions-Policy"]


def test_api_carries_security_headers():
    # A genuinely UNMATCHED /api/* path: the Ninja API 404s it WITHOUT a DB
    # hit, so this stays a Tier-1 (no-DB) check. (Previously hit /api/seasons,
    # which F3 made a live DB-querying endpoint — un-staled, same pattern F3
    # applied to the X1 routing tests.) Intent unchanged: security headers
    # must be applied to an /api/* response regardless of status.
    res = client.get("/api/no-such-endpoint")
    assert "X-Frame-Options" in res.headers


def test_hsts_only_on_https():
    # Default test client request is plain http → HSTS must NOT appear
    # (dev http localhost is not pinned). Parity with the FastAPI test.
    res = client.get("/health")
    assert "Strict-Transport-Security" not in res.headers


def test_csp_allows_cloudflare_web_analytics():
    csp = client.get("/health").headers["Content-Security-Policy"]
    assert "https://static.cloudflareinsights.com" in csp
    assert "https://cloudflareinsights.com" in csp


# --- Exact-value parity with backend/app/security_headers.py ----------------

_EXPECTED_CSP = (
    "default-src 'self'; "
    "img-src 'self' data: https://maps.googleapis.com https://maps.gstatic.com https://*.googleapis.com https://*.gstatic.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "script-src 'self' 'unsafe-inline' https://static.cloudflareinsights.com https://maps.googleapis.com https://maps.gstatic.com; "
    "connect-src 'self' https://cloudflareinsights.com https://maps.googleapis.com https://*.googleapis.com; "
    "font-src 'self' data: https://fonts.gstatic.com; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


def test_header_values_byte_identical_to_fastapi_oracle():
    res = client.get("/health")
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert res.headers["Content-Security-Policy"] == _EXPECTED_CSP
    assert (
        res.headers["Permissions-Policy"]
        == "geolocation=(), microphone=(), camera=(), payment=()"
    )


def test_no_referrer_policy_drift_from_django_default():
    # Regression guard: Django's SecurityMiddleware default is "same-origin".
    # The parity value MUST win — never Django's default.
    res = client.get("/health")
    assert res.headers["Referrer-Policy"] != "same-origin"
    assert res.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


# --- review OV3: HSTS behind the Railway proxy ------------------------------

def test_hsts_emitted_for_direct_tls_request():
    res = client.get("/health", secure=True)
    assert (
        res.headers["Strict-Transport-Security"]
        == "max-age=63072000; includeSubDomains"
    )


def test_hsts_emitted_for_forwarded_https_request():
    """The X2 failure mode: a Railway-forwarded request arrives on a plain
    HTTP socket with X-Forwarded-Proto: https. SECURE_PROXY_SSL_HEADER must
    make Django treat it as secure so HSTS is still emitted (not just on
    direct TLS). SECURE_* flags alone would NOT achieve this."""
    res = client.get("/health", HTTP_X_FORWARDED_PROTO="https")
    assert res.status_code == 200
    assert (
        res.headers["Strict-Transport-Security"]
        == "max-age=63072000; includeSubDomains"
    ), "HSTS must be emitted for a forwarded-HTTPS request (proxy honored)"


def test_no_hsts_for_forwarded_http_request():
    # Forwarded-proto explicitly http (or a stray header value) must NOT
    # trigger HSTS — only a genuine https forward does.
    res = client.get("/health", HTTP_X_FORWARDED_PROTO="http")
    assert "Strict-Transport-Security" not in res.headers

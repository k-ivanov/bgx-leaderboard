"""X2 — baseline security-headers middleware (Django port).

Byte-for-byte port of ``backend/app/security_headers.py`` (the frozen FastAPI
parity oracle). Every header NAME and VALUE emitted here is identical to that
module — this is a behavioral mirror, not a re-design.

Why a hand-written middleware instead of django-csp / Django's own
``SecurityMiddleware`` knobs:

* ``django-csp`` is not a declared dependency and would only re-derive the
  exact same static CSP string we already have verbatim — extra surface for
  zero parity benefit.
* Django's ``SecurityMiddleware`` *does* emit ``X-Content-Type-Options``,
  ``Referrer-Policy`` and (when ``SECURE_HSTS_SECONDS``) HSTS, but its
  ``SECURE_REFERRER_POLICY`` default is ``same-origin`` whereas the FastAPI
  app emits ``strict-origin-when-cross-origin``. Owning every header in ONE
  place removes any ordering ambiguity and guarantees the byte-identical set.

This middleware is registered FIRST in ``MIDDLEWARE`` (settings, X2 block) so
its ``process_response`` runs LAST in the response phase and is the final
writer for every header it owns. ``HttpResponse.headers`` is a single-value,
case-insensitive mapping, so assigning a header replaces (never duplicates)
any value an inner middleware set.

HSTS is scheme-sensitive exactly like the FastAPI version
(``request.url.scheme == "https"``). The Django equivalent is
``request.is_secure()``, which — once ``SECURE_PROXY_SSL_HEADER`` is set
(X2 settings block) — correctly returns True for a Railway-forwarded
``X-Forwarded-Proto: https`` request. ``SECURE_*`` flags alone are
insufficient (review OV3): without the proxy header config, Django would see
the forwarded request as plain HTTP and silently drop HSTS.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Header VALUES — copied verbatim from backend/app/security_headers.py.
# Do NOT "improve" these strings: parity with the frozen FastAPI app is the
# contract (ported test_security_headers.py pins them).
# ---------------------------------------------------------------------------

# Third-party origin allowlist (see backend/app/security_headers.py:20-29):
#   - static.cloudflareinsights.com  → Cloudflare Web Analytics beacon JS
#   - cloudflareinsights.com         → Cloudflare beacon POST endpoint
#   - maps.googleapis.com            → Google Maps JS API loader + tile fetches
#   - maps.gstatic.com               → Google Maps assets (sprites, icons)
#   - fonts.googleapis.com           → Google Maps embeds Roboto via @import
#   - fonts.gstatic.com              → Google Fonts woff2 binaries
#   - data: in img-src               → SVG marker icons embedded as data URIs
# 'unsafe-inline' on style-src + script-src is needed for the BaseLayout's
# is:inline blocks (theme init, define:vars) and Google Maps' inline styles.
_CSP = (
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

_PERMISSIONS_POLICY = "geolocation=(), microphone=(), camera=(), payment=()"

_HSTS = "max-age=63072000; includeSubDomains"


class SecurityHeadersMiddleware:
    """Emit the same baseline security headers as the FastAPI app.

    New-style Django middleware (callable). One instance per process; the
    ``get_response`` chain is the inner stack.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Always-on hardening. The FastAPI module uses ``setdefault`` against a
        # fresh Starlette response; here we assign on Django's single-value
        # header mapping, which is the equivalent end state (no duplicates,
        # this middleware is the last writer — see module docstring). Values
        # are byte-identical to backend/app/security_headers.py:48-55.
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = _CSP
        response.headers["Permissions-Policy"] = _PERMISSIONS_POLICY

        # HSTS only on https — don't pin dev http localhost. Mirrors
        # ``request.url.scheme == "https"``; ``request.is_secure()`` honors
        # SECURE_PROXY_SSL_HEADER so a Railway-forwarded HTTPS request (plain
        # HTTP socket + X-Forwarded-Proto: https) is correctly treated as
        # secure and DOES get HSTS (review OV3).
        if request.is_secure():
            response.headers["Strict-Transport-Security"] = _HSTS

        return response


__all__ = ["SecurityHeadersMiddleware"]

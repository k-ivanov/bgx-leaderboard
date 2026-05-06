"""Security headers middleware (improvements.md P1 #11).

Sets baseline security headers on every response. CSP allows
'unsafe-inline' for scripts and styles because the BaseLayout ships
`is:inline` blocks (theme init, visit tracking, define:vars JSON) — a
nonce strategy would require dynamic HTML rendering, which conflicts
with the SSG architecture.

HSTS is only emitted when the request was served over https; localhost
http traffic stays unaffected so dev tooling doesn't get pinned.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp


# Third-party origin allowlist:
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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Always-on hardening.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Content-Security-Policy", _CSP)
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=()",
        )

        # HSTS only on https (don't pin dev http localhost).
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains",
            )

        return response


def install(app: ASGIApp) -> None:
    """Idempotent installer used by app.main.create_app."""
    # Starlette's `add_middleware` is idempotent only if you don't double-call
    # it — the responsibility is the caller's. create_app calls this exactly
    # once per app instance.
    app.add_middleware(SecurityHeadersMiddleware)

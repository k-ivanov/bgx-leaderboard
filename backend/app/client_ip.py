"""Resolve the real client IP when running behind a reverse proxy.

``request.client.host`` is the immediate TCP peer. In a Railway deploy the
peer is Railway's load balancer, and the LB node varies request-to-request
— so the same human looks like a different IP on every hit. That breaks
two things:

  - analytics: ``visitor_id_for(salt, ip, ua)`` returns a different hash
    per request, so a single user shows up as many "unique visitors" in
    /stats.
  - rate limiting: slowapi's per-IP buckets get keyed on the LB node IP,
    so quotas are effectively meaningless.

Railway (and every reasonable reverse proxy) sets ``X-Forwarded-For``
with the original client first, comma-separated through any further
hops. We trust it because the only hop in front of us is Railway. If
the app ever ends up behind a different/no proxy, the fallback to
``request.client.host`` keeps it honest.
"""

from __future__ import annotations

from starlette.requests import Request


def real_client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        # Leftmost is the original client; everything after is intermediate.
        return xff.split(",", 1)[0].strip()
    return request.client.host if request.client else ""

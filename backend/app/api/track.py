"""POST /api/track — visit tracking endpoint (eng-review N7).

Called by the inline script in BaseLayout on every page load. Writes a
``Visit`` row with a pseudonymous visitor_id and a derived session_id
(30-min inactivity window). See ``src/analytics.py`` for the hashing model.

Defenses:
  - ``extra="forbid"`` rejects unknown fields.
  - Request body size is capped at ``TRACK_MAX_BYTES`` (2 KB) via the ASGI
    middleware configured in ``app.main`` — anything larger 413s before
    hitting the handler.
  - Per-IP rate limit applied via slowapi in ``app.main``.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.client_ip import real_client_ip
from app.deps import get_session
from app.schemas.track import TrackIn, TrackOut
from src.analytics import (
    derive_session_id,
    get_or_create_salt,
    visitor_id_for,
)
from src.database import detect_device_type
from src.db.models import Visit

router = APIRouter(prefix="/api", tags=["track"])


@router.post("/track", response_model=TrackOut)
def track_visit(
    payload: TrackIn,
    request: Request,
    session: Session = Depends(get_session),
) -> TrackOut:
    ua = request.headers.get("user-agent", "") or ""
    ip = real_client_ip(request)

    salt = get_or_create_salt(session)
    visitor_id = visitor_id_for(salt, ip, ua)
    session_id = derive_session_id(session, visitor_id)

    session.add(
        Visit(
            timestamp=datetime.now(timezone.utc),
            page=payload.page,
            category=payload.category,
            season_year=payload.season_year,
            event_slug=payload.event_slug,
            rider_slug=payload.rider_slug,
            device_type=detect_device_type(ua),
            visitor_id=visitor_id,
            session_id=session_id,
        )
    )
    return TrackOut(ok=True)

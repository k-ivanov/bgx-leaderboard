"""POST /api/track — visit tracking endpoint (eng-review N7).

Called by the frontend router's afterEach hook. Writes a Visit row.
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

from app.deps import get_session
from app.schemas.track import TrackIn, TrackOut
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
    session.add(
        Visit(
            timestamp=datetime.now(timezone.utc),
            page=payload.page,
            category=payload.category,
            season_year=payload.season_year,
            device_type=detect_device_type(ua),
        )
    )
    return TrackOut(ok=True)

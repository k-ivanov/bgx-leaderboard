"""Visit tracking backed by Postgres/SQLAlchemy."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from .db import get_session
from .db.models import Visit


_MOBILE_INDICATORS = (
    "mobile",
    "android",
    "iphone",
    "ipad",
    "ipod",
    "blackberry",
    "windows phone",
)


def detect_device_type(user_agent: str) -> str:
    if not user_agent:
        return "unknown"
    ua = user_agent.lower()
    for indicator in _MOBILE_INDICATORS:
        if indicator in ua:
            return "mobile"
    return "desktop"


def track_visit(
    page: str,
    category: str = "",
    user_agent: str = "",
    season_year: Optional[int] = None,
) -> None:
    device_type = detect_device_type(user_agent)
    with get_session() as session:
        session.add(
            Visit(
                timestamp=datetime.now(timezone.utc),
                page=page,
                category=category or None,
                season_year=season_year,
                device_type=device_type,
            )
        )


def all_visits() -> list[Visit]:
    with get_session() as session:
        rows = session.execute(select(Visit).order_by(Visit.timestamp.desc())).scalars().all()
        session.expunge_all()
        return list(rows)

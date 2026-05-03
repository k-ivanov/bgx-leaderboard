"""POST /api/track contract (eng-review N7).

Validates:
  - Happy path writes a Visit row.
  - Rejects payloads missing required fields.
  - Rejects oversize payloads (413 from the size middleware).
  - Rejects unknown fields (``extra="forbid"`` on TrackIn).

Rate-limiting (10/minute per IP) is exercised separately — TestClient does not
easily spoof distinct client IPs, and slowapi's behavior in test contexts is
opinionated. Locking the rate-limit config in ``app.config.TRACK_RATE_LIMIT``
is considered sufficient; a Phase 4 integration test can exercise the limit
against a real server.
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from src.db import get_session
from src.db.models import Visit

pytestmark = pytest.mark.usefixtures("seeded_db")

client = TestClient(app)


def test_track_happy_path_creates_visit_row() -> None:
    response = client.post(
        "/api/track",
        json={"page": "leaderboard", "category": "expert", "season_year": 2026},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}

    with get_session() as session:
        latest = session.execute(
            select(Visit).order_by(Visit.timestamp.desc()).limit(1)
        ).scalar_one_or_none()
        assert latest is not None
        assert latest.page == "leaderboard"
        assert latest.category == "expert"
        assert latest.season_year == 2026


def test_track_detects_mobile_from_user_agent() -> None:
    response = client.post(
        "/api/track",
        json={"page": "rider", "category": None, "season_year": None},
        headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)"},
    )
    assert response.status_code == 200

    with get_session() as session:
        latest = session.execute(
            select(Visit).order_by(Visit.timestamp.desc()).limit(1)
        ).scalar_one()
        assert latest.device_type == "mobile"


def test_track_rejects_missing_page() -> None:
    response = client.post("/api/track", json={"category": "expert"})
    assert response.status_code == 422


def test_track_rejects_extra_fields() -> None:
    response = client.post(
        "/api/track",
        json={"page": "leaderboard", "evil_field": "drop table visits;"},
    )
    assert response.status_code == 422


def test_track_stamps_visitor_and_session_ids() -> None:
    """Every Visit row gets a non-empty visitor_id + session_id."""
    from src.analytics import _reset_salt_cache_for_tests
    _reset_salt_cache_for_tests()

    response = client.post(
        "/api/track",
        json={"page": "leaderboard", "season_year": 2026},
        headers={"User-Agent": "Mozilla/5.0 (X11; Linux) Chrome/120"},
    )
    assert response.status_code == 200

    with get_session() as session:
        latest = session.execute(
            select(Visit).order_by(Visit.timestamp.desc()).limit(1)
        ).scalar_one()
        assert latest.visitor_id != ""
        assert len(latest.visitor_id) == 16
        assert latest.session_id != ""


def test_track_reuses_session_for_repeat_visitor() -> None:
    """Same (IP, UA) within 30 min → same session_id."""
    from src.analytics import _reset_salt_cache_for_tests
    _reset_salt_cache_for_tests()

    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux) Chrome/120"}
    r1 = client.post("/api/track", json={"page": "home"}, headers=headers)
    r2 = client.post("/api/track", json={"page": "leaderboard"}, headers=headers)
    assert r1.status_code == r2.status_code == 200

    with get_session() as session:
        rows = list(
            session.execute(
                select(Visit).order_by(Visit.timestamp.desc()).limit(2)
            ).scalars()
        )
        assert rows[0].visitor_id == rows[1].visitor_id
        assert rows[0].session_id == rows[1].session_id


def test_track_persists_event_and_rider_slugs() -> None:
    response = client.post(
        "/api/track",
        json={
            "page": "race",
            "season_year": 2026,
            "event_slug": "kyrnare",
        },
    )
    assert response.status_code == 200

    rider_response = client.post(
        "/api/track",
        json={
            "page": "rider",
            "season_year": 2026,
            "rider_slug": "42-ivan-ivanov",
        },
    )
    assert rider_response.status_code == 200

    with get_session() as session:
        rider_row = session.execute(
            select(Visit).where(Visit.page == "rider").order_by(Visit.timestamp.desc()).limit(1)
        ).scalar_one()
        assert rider_row.rider_slug == "42-ivan-ivanov"

        race_row = session.execute(
            select(Visit).where(Visit.page == "race").order_by(Visit.timestamp.desc()).limit(1)
        ).scalar_one()
        assert race_row.event_slug == "kyrnare"


@pytest.mark.parametrize(
    "bad_payload",
    [
        {"page": ""},                                      # min_length
        {"page": "x" * 65},                                # max_length
        {"page": "ok", "season_year": 42},                 # below ge
        {"page": "ok", "season_year": 3500},               # above le
    ],
)
def test_track_rejects_out_of_bounds(bad_payload: dict) -> None:
    response = client.post("/api/track", json=bad_payload)
    assert response.status_code == 422


def test_track_rejects_oversize_payload() -> None:
    # Inflate a legal field past the 2 KB cap using a long `category` value
    # plus padding the page field. Build the raw body with correct content-length.
    payload = {"page": "leaderboard", "category": "x" * 3000}
    body = json.dumps(payload).encode("utf-8")
    response = client.post(
        "/api/track",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        },
    )
    assert response.status_code == 413
    assert "too large" in response.json()["detail"].lower()

"""Contract tests for the JSON API (eng-review N5).

Exercises each endpoint with:
  - a positive path against the DB seeded from ``seed_data/``
  - a negative path (404, bad category, bad slug)
  - disambiguation when multiple riders share a race number

The DB is seeded once per session by the ``seeded_db`` fixture; this module
opts in via ``pytestmark``.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.slug import rider_slug
from src.db import get_session
from src.db.models import Category, Rider, Season

pytestmark = pytest.mark.usefixtures("seeded_db")

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_rider_in_2025_expert() -> tuple[int, str, str]:
    """Pick a rider from the 2025 Expert class for rider-endpoint tests."""
    with get_session() as session:
        season = session.execute(select(Season).where(Season.year == 2025)).scalar_one()
        category = session.execute(
            select(Category).where(
                Category.season_id == season.id, Category.code == "expert"
            )
        ).scalar_one()
        rider = session.execute(
            select(Rider).where(Rider.category_id == category.id).limit(1)
        ).scalar_one()
        return rider.race_number, rider.first_name, rider.last_name


# ---------------------------------------------------------------------------
# /api/seasons
# ---------------------------------------------------------------------------

def test_list_seasons_includes_2025() -> None:
    response = client.get("/api/seasons")
    assert response.status_code == 200
    body = response.json()
    years = [s["year"] for s in body["seasons"]]
    assert 2025 in years


def test_get_season_detail_2025() -> None:
    response = client.get("/api/seasons/2025")
    assert response.status_code == 200
    body = response.json()
    assert body["season"]["year"] == 2025
    assert len(body["categories"]) >= 5  # expect all 2025 categories
    assert any(c["code"] == "expert" for c in body["categories"])
    assert len(body["events"]) >= 5
    # rider_count is the season-wide sum across every category.
    assert body["rider_count"] > 0


def test_get_season_detail_404_for_missing_year() -> None:
    response = client.get("/api/seasons/1999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# /api/seasons/{year}/standings/{category} (Leaderboard)
# ---------------------------------------------------------------------------

def test_leaderboard_expert_2025_has_rows() -> None:
    response = client.get("/api/seasons/2025/standings/expert")
    assert response.status_code == 200
    body = response.json()
    assert body["category"]["code"] == "expert"
    assert body["season"]["year"] == 2025
    assert len(body["rows"]) > 0

    # RiderRef is embedded and has slug (eng-review N3)
    first_row = body["rows"][0]
    assert "slug" in first_row["rider"]
    assert "race_number" in first_row["rider"]
    assert first_row["final_position"] == 1


def test_leaderboard_rider_slug_matches_backend_algorithm() -> None:
    """Frontend consumes RiderRef.slug verbatim (eng-review HC-5 / N3).
    Verify the slug in the response is exactly what ``rider_slug()`` produces."""
    response = client.get("/api/seasons/2025/standings/expert")
    body = response.json()
    for row in body["rows"]:
        expected = rider_slug(
            row["rider"]["first_name"],
            row["rider"]["last_name"],
            row["rider"]["race_number"],
        )
        assert row["rider"]["slug"] == expected


def test_leaderboard_404_for_bad_category() -> None:
    response = client.get("/api/seasons/2025/standings/not-a-real-category")
    assert response.status_code == 404


def test_leaderboard_404_for_bad_year() -> None:
    response = client.get("/api/seasons/1999/standings/expert")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# /api/seasons/{year}/events (Races)
# ---------------------------------------------------------------------------

def test_list_races_2025() -> None:
    response = client.get("/api/seasons/2025/events")
    assert response.status_code == 200
    body = response.json()
    assert body["season"]["year"] == 2025
    assert len(body["events"]) >= 5
    slugs = [e["slug"] for e in body["events"]]
    assert "kyrnare" in slugs


def test_list_races_404_for_bad_year() -> None:
    response = client.get("/api/seasons/1999/events")
    assert response.status_code == 404


def test_get_race_detail_2025_kyrnare() -> None:
    response = client.get("/api/seasons/2025/events/kyrnare")
    assert response.status_code == 200
    body = response.json()
    assert body["event"]["slug"] == "kyrnare"
    assert len(body["categories"]) >= 5


def test_get_race_detail_404_for_bad_slug() -> None:
    response = client.get("/api/seasons/2025/events/not-a-real-race")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# /api/seasons/{year}/categories/{cat}/events/{slug} (Race Results)
# ---------------------------------------------------------------------------

def test_race_results_expert_kyrnare_2025() -> None:
    response = client.get("/api/seasons/2025/categories/expert/events/kyrnare")
    assert response.status_code == 200
    body = response.json()
    assert body["category"]["code"] == "expert"
    assert body["event"]["slug"] == "kyrnare"
    # Rows may be empty for some 2025 aggregate data, but the shape must be right.
    assert isinstance(body["rows"], list)


def test_race_results_404_for_bad_category() -> None:
    response = client.get("/api/seasons/2025/categories/bogus/events/kyrnare")
    assert response.status_code == 404


def test_race_results_404_for_bad_event() -> None:
    response = client.get("/api/seasons/2025/categories/expert/events/bogus-race")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# /api/seasons/{year}/riders/{n} + /{slug} (Rider + disambiguation)
# ---------------------------------------------------------------------------

def test_rider_disambig_lists_candidates_for_existing_number() -> None:
    race_number, _first, _last = _first_rider_in_2025_expert()
    response = client.get(f"/api/seasons/2025/riders/{race_number}")
    assert response.status_code == 200
    body = response.json()
    assert body["race_number"] == race_number
    assert body["season"]["year"] == 2025
    assert len(body["candidates"]) >= 1


def test_rider_disambig_404_for_unused_number() -> None:
    response = client.get("/api/seasons/2025/riders/99999")
    assert response.status_code == 404


def test_rider_profile_resolves_by_slug() -> None:
    race_number, first, last = _first_rider_in_2025_expert()
    slug = rider_slug(first, last, race_number)
    response = client.get(f"/api/seasons/2025/riders/{race_number}/{slug}")
    assert response.status_code == 200
    body = response.json()
    assert body["rider"]["race_number"] == race_number
    assert body["rider"]["first_name"] == first
    assert body["rider"]["last_name"] == last
    assert body["rider"]["slug"] == slug
    assert body["total_events"] >= 1


def test_rider_profile_404_for_mismatched_slug() -> None:
    race_number, _first, _last = _first_rider_in_2025_expert()
    response = client.get(
        f"/api/seasons/2025/riders/{race_number}/definitely-not-this-person"
    )
    assert response.status_code == 404


def test_rider_profile_404_for_unused_number() -> None:
    response = client.get("/api/seasons/2025/riders/99999/anyone")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# /api/stats (private, eng-review SC-1)
# ---------------------------------------------------------------------------

def test_stats_is_accessible_in_dev_mode() -> None:
    """STATS_PASSWORD is empty in tests (no env var set) — endpoint responds."""
    response = client.get("/api/stats")
    assert response.status_code == 200
    body = response.json()
    assert "total_visits" in body
    assert "unique_visitors_today" in body
    assert "sessions_today" in body
    assert "avg_session_seconds" in body
    assert isinstance(body["devices"], list)
    assert isinstance(body["per_race"], list)
    assert isinstance(body["per_rider"], list)
    assert isinstance(body["recent"], list)


def test_stats_requires_auth_when_password_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """When STATS_PASSWORD is non-empty, unauthenticated requests get 401."""
    # Patch the module-level config constant that auth.require_stats_auth reads.
    from app import auth as auth_module
    monkeypatch.setattr(auth_module, "STATS_PASSWORD", "correct-horse-battery-staple")

    unauth = client.get("/api/stats")
    assert unauth.status_code == 401
    # httpx Headers is case-insensitive; double-check via the dict view too.
    assert "www-authenticate" in unauth.headers
    assert unauth.headers["www-authenticate"].lower().startswith("basic")

    ok = client.get(
        "/api/stats",
        auth=("anyone", "correct-horse-battery-staple"),
    )
    assert ok.status_code == 200

    bad = client.get("/api/stats", auth=("anyone", "wrong-password"))
    assert bad.status_code == 401

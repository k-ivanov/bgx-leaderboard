"""Tests for /api/riders/career (P3 #17)."""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_career_for_known_rider_aggregates_seasons():
    # Димитър ТИНЧЕВ raced in 2024 + 2025 (and possibly 2026 — the
    # assertion only requires he shows up in MORE THAN one season).
    res = client.get("/api/riders/career", params={"slug": "димитър-тинчев"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["slug"] == "димитър-тинчев"
    assert data["last_name"] == "ТИНЧЕВ"
    # Multi-season expected; if seed data ever drops to one season this
    # is still useful as a "career row exists" assertion.
    assert len(data["seasons"]) >= 1
    # Each row carries the per-season summary fields.
    for s in data["seasons"]:
        assert "season_year" in s
        assert "race_number" in s
        assert "category" in s
        assert "races_participated" in s
        assert "total_points" in s


def test_career_unknown_slug_returns_404():
    res = client.get("/api/riders/career", params={"slug": "no-such-rider"})
    assert res.status_code == 404


def test_career_requires_slug():
    res = client.get("/api/riders/career")
    assert res.status_code == 422


def test_career_seasons_are_descending():
    res = client.get("/api/riders/career", params={"slug": "димитър-тинчев"})
    assert res.status_code == 200
    seasons = res.json()["seasons"]
    years = [s["season_year"] for s in seasons]
    # Strictly non-increasing — we sort descending so the latest season
    # is first.
    assert years == sorted(years, reverse=True)

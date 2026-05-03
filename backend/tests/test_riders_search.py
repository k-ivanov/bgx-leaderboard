"""Tests for /api/seasons/{year}/riders/search (P3 #16)."""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_search_by_partial_last_name():
    # The 2025 expert leader is Димитър ТИНЧЕВ (#255) — match by 'тинч'.
    res = client.get("/api/seasons/2025/riders/search", params={"q": "тинч"})
    assert res.status_code == 200
    data = res.json()
    assert data["query"] == "тинч"
    assert any(r["rider"]["race_number"] == 255 for r in data["results"])


def test_search_by_race_number():
    res = client.get("/api/seasons/2025/riders/search", params={"q": "255"})
    assert res.status_code == 200
    data = res.json()
    # 255 should rank first (exact race_number match).
    assert data["results"]
    assert data["results"][0]["rider"]["race_number"] == 255


def test_search_respects_limit():
    res = client.get(
        "/api/seasons/2025/riders/search", params={"q": "и", "limit": 3}
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["results"]) <= 3


def test_search_unknown_query_returns_empty_list():
    res = client.get(
        "/api/seasons/2025/riders/search", params={"q": "xxxxxnotarealrider"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["results"] == []


def test_search_requires_q():
    res = client.get("/api/seasons/2025/riders/search")
    assert res.status_code == 422  # missing required query param

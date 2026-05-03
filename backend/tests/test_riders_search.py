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


def test_search_multi_token_first_and_last_name():
    # "Илиян Кръстев" (race #169) is in 2025 seniors_40. A naive ILIKE %q% on
    # each field independently would never match a query that spans first +
    # last name, since the space lives between two columns. Tokenization must
    # AND across tokens for this to work.
    res = client.get(
        "/api/seasons/2025/riders/search", params={"q": "Илиян Кръстев"}
    )
    assert res.status_code == 200
    matches = [
        r for r in res.json()["results"]
        if r["rider"]["race_number"] == 169
        and r["rider"]["last_name"].lower() == "кръстев"
    ]
    assert matches, "expected to find Илиян Кръстев #169 in 2025"


def test_search_multi_token_mixed_number_and_name():
    # Mixed token search "169 Кръстев" should still resolve to the same
    # rider — each token ORs across (first_name, last_name, race_number).
    res = client.get(
        "/api/seasons/2025/riders/search", params={"q": "169 Кръстев"}
    )
    assert res.status_code == 200
    results = res.json()["results"]
    assert results, "expected at least one match for '169 Кръстев'"
    assert results[0]["rider"]["race_number"] == 169


def test_global_search_finds_rider_outside_default_year():
    # Илиян Кръстев #169 only races in 2024 + 2025, not 2026. The cross-
    # season endpoint must surface him regardless of which season the
    # caller is currently viewing.
    res = client.get("/api/riders/search", params={"q": "Илиян Кръстев"})
    assert res.status_code == 200
    body = res.json()
    matches = [
        r for r in body["results"]
        if r["rider"]["race_number"] == 169
        and r["rider"]["last_name"].lower() == "кръстев"
    ]
    assert matches, "global search should find Илиян Кръстев across years"
    # Dedup: only one entry per slug.
    slugs = [r["rider"]["slug"] for r in body["results"]]
    assert len(slugs) == len(set(slugs))


def test_global_search_dedup_picks_most_recent_year():
    # When a rider raced in multiple seasons, the dedup'd row should be
    # the most recent one. Илиян Кръстев is 2024 + 2025 → expect 2025.
    res = client.get("/api/riders/search", params={"q": "Илиян Кръстев"})
    matches = [
        r for r in res.json()["results"]
        if r["rider"]["race_number"] == 169
        and r["rider"]["last_name"].lower() == "кръстев"
    ]
    assert matches and matches[0]["season_year"] == 2025

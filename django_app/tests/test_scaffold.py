"""F1 scaffold smoke tests.

Not the parity suite (that is F3). These only assert the F1 contract:
the project boots, /health is shape/version-identical to the frozen FastAPI
app, and the FROZEN router/URL assembly has every slot in the load-bearing
order. Real endpoint/parity tests arrive with F3 + the slices.
"""

import pytest
from django.test import Client


@pytest.mark.django_db
def test_health_shape_and_version():
    """GET /health must byte-match backend/app/main.py::health."""
    resp = Client().get("/health")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"].startswith("application/json")
    assert resp.json() == {
        "status": "ok",
        "service": "bgx-dashboard-api",
        "version": "0.1.0",
    }


def test_all_router_slots_present_in_frozen_assembly():
    """Every S1–S7 Ninja router slot must be pre-stubbed in the FROZEN api/."""
    from api import (
        events as events_api,
        results as results_api,
        riders as riders_api,
        seasons as seasons_api,
        standings as standings_api,
        stats as stats_api,
        track as track_api,
    )
    from ninja import Router

    slots = {
        "S1 seasons": seasons_api.router,
        "S2 standings": standings_api.router,
        "S3 events": events_api.router,
        "S7 results": results_api.router,
        "S4 riders": riders_api.router,
        "S4 riders-career": riders_api.career_router,
        "S5 stats": stats_api.router,
        "S6 track": track_api.router,
    }
    for name, r in slots.items():
        assert isinstance(r, Router), f"{name} is not a ninja.Router"


def test_frozen_urlconf_order_is_load_bearing():
    """URL resolution order: /api → /health → /admin → legacy 301s → catch-all.

    Mirrors backend/app/main.py mount order + CLAUDE.md invariant #4. A bad
    merge that moved the catch-all up would fail here.
    """
    from config import urls

    patterns = [str(getattr(p, "pattern", p)) for p in urls.urlpatterns]

    api_idx = next(i for i, p in enumerate(patterns) if p.startswith("api/"))
    health_idx = next(i for i, p in enumerate(patterns) if p == "health")
    admin_idx = next(i for i, p in enumerate(patterns) if p.startswith("admin/"))
    catchall_idx = next(
        i for i, p in enumerate(patterns) if "(?P<path>.*)" in p or p.endswith(".*)$")
    )

    assert api_idx < health_idx < admin_idx < catchall_idx
    # Catch-all MUST be dead last (static must never shadow API/redirects).
    assert catchall_idx == len(patterns) - 1


def test_x_slot_modules_importable():
    """X1/X2/X3 placeholder slots exist and import cleanly."""
    from api.docs import gated_docs_urlpatterns
    from redirects import legacy_redirect_urlpatterns, static_catchall

    assert isinstance(gated_docs_urlpatterns, list)
    assert isinstance(legacy_redirect_urlpatterns, list)
    assert callable(static_catchall)

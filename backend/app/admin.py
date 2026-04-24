"""SQLAdmin panel mounted at ``/admin``.

A Django-admin-style UI over the existing SQLAlchemy models. Covers the
day-to-day operator tasks that don't fit the CSV importer flow:

  - Toggle ``is_current`` on a season (front-of-site now points here).
  - Fix rider name / team / bike typos.
  - Edit event date or location after a scheduling change.
  - Delete a mistakenly-imported result.
  - Audit visits (read-only).

Bulk race-result imports stay on the ``scripts/import_event.py`` CLI — that's
the right tool for a 60-row CSV.

Auth: session-based (cookie signed by ``ADMIN_SESSION_SECRET``). Empty
``ADMIN_PASSWORD`` disables admin entirely (explicit opt-in; this endpoint
writes to the DB so there is no silent dev bypass).
"""

from __future__ import annotations

import secrets

from fastapi import FastAPI
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.config import (
    ADMIN_PASSWORD,
    ADMIN_SESSION_SECRET,
    ADMIN_USERNAME,
)
from src.db.models import Category, Event, EventResult, Rider, Season, Visit
from src.db.session import engine


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class AdminAuth(AuthenticationBackend):
    """Simple username + password auth with a signed session cookie."""

    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = str(form.get("username", ""))
        password = str(form.get("password", ""))
        if not ADMIN_PASSWORD:
            return False  # explicit: empty password == admin disabled
        if username != ADMIN_USERNAME:
            return False
        # Constant-time compare to mitigate timing attacks.
        if not secrets.compare_digest(password.encode(), ADMIN_PASSWORD.encode()):
            return False
        request.session.update({"admin_ok": True})
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool | RedirectResponse:
        if not ADMIN_PASSWORD:
            # Hard deny when admin isn't configured. The view won't be reachable;
            # sqladmin redirects to its login page which will also reject the form
            # (see ``login`` above).
            return False
        return request.session.get("admin_ok") is True


# ---------------------------------------------------------------------------
# Model views — mirror design-review §14 vocabulary where it's user-facing.
# Internal (/admin) can keep the DB-accurate names (Event, etc.).
# ---------------------------------------------------------------------------

class SeasonAdmin(ModelView, model=Season):
    name = "Season"
    name_plural = "Seasons"
    icon = "fa-solid fa-calendar"
    column_list = [
        Season.year,
        Season.name,
        Season.slug,
        Season.is_current,
        Season.championship_format,
    ]
    column_sortable_list = [Season.year, Season.is_current]
    column_searchable_list = [Season.name, Season.slug]
    column_default_sort = ("year", True)
    form_excluded_columns = [Season.categories, Season.events, Season.riders]


class CategoryAdmin(ModelView, model=Category):
    name = "Category"
    name_plural = "Categories"
    icon = "fa-solid fa-layer-group"
    column_list = [
        Category.id,
        Category.season,
        Category.code,
        Category.display_name,
        Category.sort_order,
    ]
    column_sortable_list = [Category.code, Category.sort_order]
    column_searchable_list = [Category.code, Category.display_name]
    form_excluded_columns = [Category.riders]


class EventAdmin(ModelView, model=Event):
    name = "Race"
    name_plural = "Races"
    icon = "fa-solid fa-flag-checkered"
    column_list = [
        Event.id,
        Event.season,
        Event.slug,
        Event.name,
        Event.event_date,
        Event.location,
        Event.sort_order,
    ]
    column_sortable_list = [Event.event_date, Event.sort_order]
    column_searchable_list = [Event.name, Event.slug, Event.location]
    form_excluded_columns = [Event.results]


class RiderAdmin(ModelView, model=Rider):
    name = "Rider"
    name_plural = "Riders"
    icon = "fa-solid fa-user"
    column_list = [
        Rider.id,
        Rider.season,
        Rider.category,
        Rider.race_number,
        Rider.first_name,
        Rider.last_name,
        Rider.team,
        Rider.bike,
    ]
    column_sortable_list = [Rider.race_number, Rider.last_name]
    column_searchable_list = [
        Rider.first_name,
        Rider.last_name,
        Rider.team,
        Rider.bike,
    ]
    form_excluded_columns = [Rider.results]


class EventResultAdmin(ModelView, model=EventResult):
    name = "Result"
    name_plural = "Results"
    icon = "fa-solid fa-ranking-star"
    column_list = [
        EventResult.id,
        EventResult.event,
        EventResult.rider,
        EventResult.position,
        EventResult.points,
        EventResult.time_ms,
        EventResult.gps_penalty_ms,
        EventResult.laps,
        EventResult.notes,
    ]
    column_sortable_list = [EventResult.position]


class VisitAdmin(ModelView, model=Visit):
    """Visit analytics — read-only. The audit log should not be editable."""
    name = "Visit"
    name_plural = "Visits"
    icon = "fa-solid fa-chart-simple"
    column_list = [
        Visit.id,
        Visit.timestamp,
        Visit.page,
        Visit.category,
        Visit.season_year,
        Visit.device_type,
    ]
    column_default_sort = ("timestamp", True)
    column_sortable_list = [Visit.timestamp]
    column_searchable_list = [Visit.page, Visit.category, Visit.device_type]
    can_create = False
    can_edit = False
    can_delete = False


# ---------------------------------------------------------------------------
# Wire-up
# ---------------------------------------------------------------------------

def setup_admin(app: FastAPI) -> Admin:
    """Mount the admin panel at /admin.

    Call from ``app.main::create_app`` AFTER ``/api/*`` routers are
    registered but BEFORE the static mount — /admin is itself a sub-app
    and needs priority over the StaticFiles catch-all.

    sqladmin installs its own ``SessionMiddleware`` internally using the
    ``AuthenticationBackend.secret_key`` — no need to add one ourselves.
    """
    admin = Admin(
        app,
        engine,
        title="BGX Admin",
        authentication_backend=AdminAuth(secret_key=ADMIN_SESSION_SECRET),
        base_url="/admin",
    )
    admin.add_view(SeasonAdmin)
    admin.add_view(CategoryAdmin)
    admin.add_view(EventAdmin)
    admin.add_view(RiderAdmin)
    admin.add_view(EventResultAdmin)
    admin.add_view(VisitAdmin)
    return admin

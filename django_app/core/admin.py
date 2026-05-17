"""X3 — Django admin ModelAdmins + registration (replaces SQLAdmin).

This module is imported by ``BGXAdminConfig.ready() ->
admin.autodiscover()`` (django.contrib.admin), i.e. AFTER the app
registry is fully populated — so importing ``core.models`` at top level
here is safe. The gated :class:`~core.admin_site.BGXAdminSite`, the
:class:`~core.admin_site.BGXAdminConfig` and the
:func:`~core.admin_site.is_admin_configured` opt-in gate live in the
import-light ``core/admin_site.py`` (loaded early via ``INSTALLED_APPS``;
must stay model-free to avoid ``AppRegistryNotReady``).

This file is the Django-native re-implementation of
``backend/app/admin.py`` (the frozen FastAPI/SQLAdmin parity oracle):

* 6 ``ModelAdmin`` classes — Season / Category / Event("Race") /
  Rider / EventResult("Result") / Visit — mirroring the SQLAdmin
  ``column_list`` / ``column_searchable_list`` / ``column_sortable_list``
  / ``form_excluded_columns`` and the strictly read-only Visit audit log.
* Race / Result vocabulary (design-review §14) applied as an
  admin-presentation concern (runtime ``_meta`` verbose-name override)
  WITHOUT editing F2's frozen ``core/models.py`` or any db_table.
* Registration onto the gated default site (``admin.site`` is the lazy
  global proxy the FROZEN ``config/urls.py`` mounted; ``BGXAdminConfig``
  pointed it at ``BGXAdminSite``).

Auth-model migration (in scope, explicit — review OV3 + I2-arch): the
old model was env-gated shared credentials + a signed session cookie;
Django admin uses Django auth (``auth_user`` rows, ``is_staff`` /
``is_superuser``, the session framework). Credentials are provisioned by
the env-driven ``bootstrap_admin`` management command (NO plaintext in
the image/repo); the disable-when-unset opt-in is enforced by
``BGXAdminSite``. Full rationale + the Railway runbook:
``core/ADMIN_BOOTSTRAP.md``.
"""

from __future__ import annotations

from django.contrib import admin

from core.models import (
    Category,
    Event,
    EventResult,
    Rider,
    Season,
    Visit,
)

# Re-export the gate/site/config so ``core.admin`` stays the canonical
# X3 entrypoint for callers/tests, while the import-light definitions
# live in core/admin_site.py (loaded early via INSTALLED_APPS).
from core.admin_site import (  # noqa: F401
    BGXAdminConfig,
    BGXAdminSite,
    is_admin_configured,
)

# ---------------------------------------------------------------------------
# Model views — mirror backend/app/admin.py 1:1.
#
# SQLAdmin's column_list / column_searchable_list / column_sortable_list /
# form_excluded_columns map to Django's list_display / search_fields /
# sortable_by / exclude. Relationship-only SQLAdmin form exclusions
# (Season.categories/events/riders, Category.riders, Event.results,
# Rider.results) have no Django form field by default (reverse relations
# are not on the ModelForm), so they need no `exclude` — documented per
# class. UI labels follow design-review §14 vocabulary (Race / Result).
# ---------------------------------------------------------------------------


class SeasonAdmin(admin.ModelAdmin):
    # backend/app/admin.py:78-92
    list_display = ("year", "name", "slug", "is_current", "championship_format")
    list_filter = ("is_current",)
    search_fields = ("name", "slug")
    # column_sortable_list = [year, is_current]
    sortable_by = ("year", "is_current")
    # column_default_sort = ("year", True)  → DESC by year
    ordering = ("-year",)
    # SQLAdmin form_excluded_columns were the reverse relations
    # (categories/events/riders) — not present on the Django ModelForm.


class CategoryAdmin(admin.ModelAdmin):
    # backend/app/admin.py:95-108
    list_display = ("id", "season", "code", "display_name", "sort_order")
    search_fields = ("code", "display_name")
    sortable_by = ("code", "sort_order")
    list_select_related = ("season",)
    # Rider.results reverse relation excluded in SQLAdmin — not on the form.


class EventAdmin(admin.ModelAdmin):
    """UI label: "Race" / "Races" (design-review §14; DB table stays
    ``event``). Mirrors backend/app/admin.py:111-131."""

    list_display = (
        "id",
        "season",
        "slug",
        "name",
        "event_date",
        "location",
        "sort_order",
        # Editorial — visible in the changelist so the operator can see
        # at a glance which races still need their FB URL filled in.
        "facebook_event_url",
    )
    search_fields = ("name", "slug", "location")
    sortable_by = ("event_date", "sort_order")
    list_select_related = ("season",)
    # `description` is editable on the form (prose) but kept out of the
    # changelist, exactly like SQLAdmin. `results` reverse relation is
    # managed via the importer and is not a form field.


class RiderAdmin(admin.ModelAdmin):
    # backend/app/admin.py:134-155
    list_display = (
        "id",
        "season",
        "category",
        "race_number",
        "first_name",
        "last_name",
        "team",
        "bike",
    )
    search_fields = ("first_name", "last_name", "team", "bike")
    sortable_by = ("race_number", "last_name")
    list_select_related = ("season", "category")


class EventResultAdmin(admin.ModelAdmin):
    """UI label: "Result" / "Results" (design-review §14). Mirrors
    backend/app/admin.py:158-173."""

    list_display = (
        "id",
        "event",
        "rider",
        "position",
        "points",
        "time_ms",
        "gps_penalty_ms",
        "laps",
        "notes",
    )
    # SQLAdmin: column_sortable_list = [position]
    sortable_by = ("position",)
    list_select_related = ("event", "rider")


class VisitAdmin(admin.ModelAdmin):
    """Visit analytics — strictly READ-ONLY (the audit log must not be
    editable). Mirrors backend/app/admin.py:176-194
    (can_create/can_edit/can_delete = False)."""

    list_display = (
        "id",
        "timestamp",
        "page",
        "category",
        "season_year",
        "device_type",
    )
    search_fields = ("page", "category", "device_type")
    sortable_by = ("timestamp",)
    # column_default_sort = ("timestamp", True) → DESC
    ordering = ("-timestamp",)

    # --- Read-only enforcement (parity with SQLAdmin can_*=False) ------
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        # Belt-and-suspenders: if a detail view is ever reached, every
        # field is rendered read-only.
        return [f.name for f in self.model._meta.fields]


# ---------------------------------------------------------------------------
# Vocabulary (design-review §14): the SQLAdmin panel renamed Event→"Race"
# and EventResult→"Result" in the UI while the DB tables stay `event` /
# `event_result` (CLAUDE.md vocabulary note). Django admin derives every
# user-facing label (app index, changelist title, breadcrumbs, "Add …"
# button) from ``Model._meta.verbose_name`` / ``verbose_name_plural``.
# F2's ``core/models.py`` is frozen for X3, so the rename is applied HERE
# as an admin-presentation concern by overriding the runtime ``_meta``
# labels — no model field / db_table / migration is touched
# (``Meta.db_table`` still pins the real table name; verified
# schema-irrelevant).
# ---------------------------------------------------------------------------

Event._meta.verbose_name = "Race"
Event._meta.verbose_name_plural = "Races"
EventResult._meta.verbose_name = "Result"
EventResult._meta.verbose_name_plural = "Results"


# ---------------------------------------------------------------------------
# Registration — on the gated default site (BGXAdminSite via BGXAdminConfig).
# ``admin.site`` is the lazy global proxy the FROZEN config/urls.py mounted;
# BGXAdminConfig.default_site points it at BGXAdminSite, so these register on
# the gated site without touching the frozen URL wiring.
# ---------------------------------------------------------------------------

admin.site.register(Season, SeasonAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Event, EventAdmin)  # UI: "Race"
admin.site.register(Rider, RiderAdmin)
admin.site.register(EventResult, EventResultAdmin)  # UI: "Result"
admin.site.register(Visit, VisitAdmin)

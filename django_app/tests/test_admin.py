"""X3 — Django admin parity + opt-in gate tests.

These lock the X3 contract in code:

* all 6 model views registered with column/search/sort equivalents of the
  frozen ``backend/app/admin.py`` (SQLAdmin) parity oracle;
* ``Visit`` is strictly read-only (add/change/delete perms all False);
* the Race / Result vocabulary (design-review §14) is applied as admin
  labels WITHOUT touching F2's db_table pins;
* the disable-when-unset opt-in: admin is *absent* (every admin view,
  incl. login, raises Http404) when not configured, and reachable when
  provisioned — the Django-native parity of the old ``ADMIN_PASSWORD``
  empty-disables-admin gate;
* the additive settings wiring points the global ``admin.site`` at the
  gated ``BGXAdminSite`` (so the FROZEN ``config/urls.py`` mount needs no
  change).

NOTE ON LOCAL ENV: importing ``config.urls`` here is intentionally
avoided. The pinned Django-6 deps are not installed in the agent sandbox
(django-ninja vs pydantic-v2 ``ModelField`` ImportError) and ANY import of
the Ninja ``api`` package — which ``config.urls`` does — fails there. That
is a pre-existing environment limitation that breaks the F1 scaffold
tests too; it is unrelated to X3. So the gate is exercised at the layer
DIRECTLY BELOW the URL resolver (``BGXAdminSite.get_urls()`` /
``has_permission`` / the wrapped view callables), which is exactly the
mechanism the FROZEN ``admin.site.urls`` include resolves to in prod. The
behaviour is identical; only the test entrypoint differs.
"""

from __future__ import annotations

import os

import pytest
from django.contrib import admin
from django.http import Http404

from core.admin import (
    CategoryAdmin,
    EventAdmin,
    EventResultAdmin,
    RiderAdmin,
    SeasonAdmin,
    VisitAdmin,
)
from core.admin_site import BGXAdminSite, is_admin_configured
from core.models import (
    Category,
    Event,
    EventResult,
    Rider,
    Season,
    Visit,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolved_site():
    """Resolve the lazy ``admin.site`` proxy to the concrete instance."""
    site = admin.site
    return getattr(site, "_wrapped", None) or site


@pytest.fixture(autouse=True)
def _clean_admin_enabled_env():
    """Each test controls ADMIN_ENABLED explicitly; restore afterwards."""
    saved = os.environ.get("ADMIN_ENABLED")
    yield
    if saved is None:
        os.environ.pop("ADMIN_ENABLED", None)
    else:
        os.environ["ADMIN_ENABLED"] = saved


# ---------------------------------------------------------------------------
# 1. All 6 model views registered on the gated site
# ---------------------------------------------------------------------------


def test_all_six_models_registered_on_gated_site():
    site = _resolved_site()
    assert isinstance(site, BGXAdminSite)
    for model in (Season, Category, Event, Rider, EventResult, Visit):
        assert model in site._registry, f"{model.__name__} not registered"


def test_admin_classes_paired_with_models():
    site = _resolved_site()
    assert isinstance(site._registry[Season], SeasonAdmin)
    assert isinstance(site._registry[Category], CategoryAdmin)
    assert isinstance(site._registry[Event], EventAdmin)
    assert isinstance(site._registry[Rider], RiderAdmin)
    assert isinstance(site._registry[EventResult], EventResultAdmin)
    assert isinstance(site._registry[Visit], VisitAdmin)


# ---------------------------------------------------------------------------
# 2. Column / search / sort parity with backend/app/admin.py (SQLAdmin)
# ---------------------------------------------------------------------------


def test_season_admin_columns_match_sqladmin():
    # backend/app/admin.py:82-92
    assert SeasonAdmin.list_display == (
        "year",
        "name",
        "slug",
        "is_current",
        "championship_format",
    )
    assert SeasonAdmin.search_fields == ("name", "slug")
    assert SeasonAdmin.sortable_by == ("year", "is_current")
    # column_default_sort = ("year", True) → DESC
    assert SeasonAdmin.ordering == ("-year",)


def test_category_admin_columns_match_sqladmin():
    # backend/app/admin.py:99-108
    assert CategoryAdmin.list_display == (
        "id",
        "season",
        "code",
        "display_name",
        "sort_order",
    )
    assert CategoryAdmin.search_fields == ("code", "display_name")
    assert CategoryAdmin.sortable_by == ("code", "sort_order")


def test_event_admin_columns_match_sqladmin():
    # backend/app/admin.py:115-131
    assert EventAdmin.list_display == (
        "id",
        "season",
        "slug",
        "name",
        "event_date",
        "location",
        "sort_order",
        "facebook_event_url",
    )
    assert EventAdmin.search_fields == ("name", "slug", "location")
    assert EventAdmin.sortable_by == ("event_date", "sort_order")


def test_rider_admin_columns_match_sqladmin():
    # backend/app/admin.py:138-155
    assert RiderAdmin.list_display == (
        "id",
        "season",
        "category",
        "race_number",
        "first_name",
        "last_name",
        "team",
        "bike",
    )
    assert RiderAdmin.search_fields == (
        "first_name",
        "last_name",
        "team",
        "bike",
    )
    assert RiderAdmin.sortable_by == ("race_number", "last_name")


def test_event_result_admin_columns_match_sqladmin():
    # backend/app/admin.py:162-173
    assert EventResultAdmin.list_display == (
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
    assert EventResultAdmin.sortable_by == ("position",)


def test_visit_admin_columns_match_sqladmin():
    # backend/app/admin.py:181-191
    assert VisitAdmin.list_display == (
        "id",
        "timestamp",
        "page",
        "category",
        "season_year",
        "device_type",
    )
    assert VisitAdmin.search_fields == ("page", "category", "device_type")
    assert VisitAdmin.sortable_by == ("timestamp",)
    # column_default_sort = ("timestamp", True) → DESC
    assert VisitAdmin.ordering == ("-timestamp",)


# ---------------------------------------------------------------------------
# 3. Visit strictly read-only (SQLAdmin can_create/can_edit/can_delete=False)
# ---------------------------------------------------------------------------


def test_visit_admin_is_strictly_read_only():
    va = VisitAdmin(Visit, _resolved_site())
    assert va.has_add_permission(request=None) is False
    assert va.has_change_permission(request=None) is False
    assert va.has_change_permission(request=None, obj=object()) is False
    assert va.has_delete_permission(request=None) is False
    assert va.has_delete_permission(request=None, obj=object()) is False


def test_visit_admin_all_fields_readonly():
    va = VisitAdmin(Visit, _resolved_site())
    ro = set(va.get_readonly_fields(request=None))
    model_fields = {f.name for f in Visit._meta.fields}
    assert ro == model_fields, "every Visit field must be read-only"


def test_non_visit_admins_are_not_force_readonly():
    """Parity: Season/Category/Event/Rider/EventResult stay editable
    (only Visit was can_*=False in SQLAdmin)."""
    site = _resolved_site()
    for adm_cls, model in (
        (SeasonAdmin, Season),
        (CategoryAdmin, Category),
        (EventAdmin, Event),
        (RiderAdmin, Rider),
        (EventResultAdmin, EventResult),
    ):
        a = adm_cls(model, site)
        assert a.has_add_permission(request=_StaffRequest()) is True
        assert a.has_change_permission(request=_StaffRequest()) is True
        assert a.has_delete_permission(request=_StaffRequest()) is True


class _StaffRequest:
    """Minimal request stand-in: default ModelAdmin perm methods only
    consult ``request`` for non-Visit admins via the default-True path
    (they don't touch ``request`` unless object-level perms are on)."""

    class _U:
        is_active = True
        is_staff = True
        is_superuser = True

        def has_perm(self, *a, **k):
            return True

        def has_module_perms(self, *a, **k):
            return True

    user = _U()


# ---------------------------------------------------------------------------
# 4. Race / Result vocabulary (design-review §14) — labels only, no schema
# ---------------------------------------------------------------------------


def test_event_labelled_race_db_table_unchanged():
    assert str(Event._meta.verbose_name) == "Race"
    assert str(Event._meta.verbose_name_plural) == "Races"
    # The db_table pin (F2) MUST be untouched by the label override.
    assert Event._meta.db_table == "event"


def test_event_result_labelled_result_db_table_unchanged():
    assert str(EventResult._meta.verbose_name) == "Result"
    assert str(EventResult._meta.verbose_name_plural) == "Results"
    assert EventResult._meta.db_table == "event_result"


def test_other_models_keep_their_natural_labels():
    # Only Event/EventResult are renamed per §14; the rest are unchanged.
    assert Season._meta.db_table == "season"
    assert Category._meta.db_table == "category"
    assert Rider._meta.db_table == "rider"
    assert Visit._meta.db_table == "visit"


# ---------------------------------------------------------------------------
# 5. Opt-in gate — disable-when-unset parity with old ADMIN_PASSWORD
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("token", ["", "0", "false", "no", "off", "FALSE", "Off"])
def test_admin_disabled_when_admin_enabled_falsey(token):
    os.environ["ADMIN_ENABLED"] = token
    assert is_admin_configured() is False


@pytest.mark.parametrize("token", ["1", "true", "yes", "on", "TRUE", "On", "enabled"])
def test_admin_enabled_when_admin_enabled_truthy(token):
    os.environ["ADMIN_ENABLED"] = token
    assert is_admin_configured() is True


@pytest.mark.django_db
def test_unconfigured_when_unset_and_no_superuser():
    """ADMIN_ENABLED unset + no staff user provisioned ⇒ admin OFF.

    Byte-for-byte the old behaviour: an unset credential disabled the
    panel entirely with no silent dev bypass."""
    os.environ.pop("ADMIN_ENABLED", None)
    from django.contrib.auth import get_user_model

    get_user_model().objects.all().delete()
    assert is_admin_configured() is False


@pytest.mark.django_db
def test_configured_when_superuser_provisioned():
    """ADMIN_ENABLED unset + a staff user exists (bootstrap_admin ran)
    ⇒ admin ON (provisioning signal)."""
    os.environ.pop("ADMIN_ENABLED", None)
    from django.contrib.auth import get_user_model

    User = get_user_model()
    User.objects.create_user(
        username="op", password="x", is_staff=True, is_superuser=True
    )
    assert is_admin_configured() is True


# ---------------------------------------------------------------------------
# 6. Gate is enforced at the URL layer the FROZEN config/urls.py resolves
#    (admin.site.urls) WITHOUT importing config.urls.
# ---------------------------------------------------------------------------


def _admin_url_entries():
    """Resolve admin.site.urls's gated URL patterns (the exact object
    `path("admin/", admin.site.urls)` mounts in the FROZEN urls.py)."""
    site = _resolved_site()
    # admin.site.urls -> (patterns, app_namespace, instance_namespace)
    patterns = site.urls[0]
    return patterns


def test_admin_views_404_when_unconfigured():
    """Every admin view raises Http404 when admin is disabled — the
    /admin/* surface is *absent*, not a 403 login wall (parity with the
    old ADMIN_PASSWORD-empty hard-deny)."""
    os.environ["ADMIN_ENABLED"] = "0"
    entries = _admin_url_entries()
    checked = 0
    for entry in entries:
        cb = getattr(entry, "callback", None)
        if cb is None:
            continue
        with pytest.raises(Http404):
            cb(_StaffRequest())
        checked += 1
    assert checked > 0, "no admin view callbacks found to assert against"


def test_admin_login_view_also_404s_when_unconfigured():
    """Specifically the login page must be absent too (no reachable form
    to brute-force) — matches backend/app/admin.py:64-70.

    Asserted against the gated `login/` URL callback (the exact object
    the FROZEN admin.site.urls include resolves), via RequestFactory."""
    from django.test import RequestFactory

    os.environ["ADMIN_ENABLED"] = "0"
    entries = _admin_url_entries()
    login_entry = next(e for e in entries if getattr(e, "name", "") == "login")
    req = RequestFactory().get("/admin/login/")
    with pytest.raises(Http404):
        login_entry.callback(req)


def test_has_permission_false_when_unconfigured():
    os.environ["ADMIN_ENABLED"] = "0"
    site = _resolved_site()
    assert site.has_permission(_StaffRequest()) is False


def test_has_permission_consults_staff_when_configured():
    os.environ["ADMIN_ENABLED"] = "1"
    site = _resolved_site()
    # Configured ⇒ delegates to the standard staff check.
    assert site.has_permission(_StaffRequest()) is True

    class _Anon:
        class _U:
            is_active = False
            is_staff = False

        user = _U()

    assert site.has_permission(_Anon()) is False


def test_gate_is_transparent_when_configured():
    """When configured the gate must NOT raise its Http404 — it delegates
    to the wrapped admin view.

    Asserted on a fresh BGXAdminSite whose ``login`` view is a sentinel
    set BEFORE ``get_urls()`` runs. The admin ``login/`` URL is bound
    RAW (``path("login/", self.login, ...)`` — NOT through
    ``self.admin_view``), so our gate wrapper is the ONLY thing between
    the URL and the sentinel: no ``has_permission`` / ``reverse()`` /
    root-URLconf load is triggered. This proves "reachable when
    configured" (gate passes the call through) AND "absent when
    unconfigured" (same callback raises Http404) at the exact object the
    FROZEN ``admin.site.urls`` resolves — fully independent of the
    broken-in-sandbox config.urls/Ninja import chain."""
    from django.test import RequestFactory

    os.environ["ADMIN_ENABLED"] = "1"

    site = BGXAdminSite(name="probe")
    sentinel = object()
    site.login = lambda request, *a, **k: sentinel  # raw-bound, un-wrapped

    entries = site.get_urls()
    login = next(e for e in entries if getattr(e, "name", "") == "login")
    req = RequestFactory().get("/admin/login/")

    # Configured ⇒ gate transparent ⇒ sentinel returned (no Http404).
    assert login.callback(req) is sentinel

    # Same gated callback, admin flipped off ⇒ Http404 (absent: no
    # reachable login form to brute-force — old ADMIN_PASSWORD parity).
    os.environ["ADMIN_ENABLED"] = "0"
    with pytest.raises(Http404):
        login.callback(req)


# ---------------------------------------------------------------------------
# 7. Additive settings wiring (no FROZEN urls.py edit)
# ---------------------------------------------------------------------------


def test_installed_apps_swapped_to_gated_admin_config():
    from django.conf import settings

    assert "core.admin_site.BGXAdminConfig" in settings.INSTALLED_APPS
    assert "django.contrib.admin" not in settings.INSTALLED_APPS


def test_frozen_urls_file_untouched_by_x3():
    """config/urls.py must remain the FROZEN F1 file: the /admin slot is
    still admin.site.urls and X3 added no env-gate there.

    The file is read from disk (NOT imported) on purpose — importing
    config.urls pulls the Ninja api package which ImportErrors in the
    agent sandbox (pre-existing env limitation; see module docstring).
    """
    from pathlib import Path

    urls_path = Path(__file__).resolve().parent.parent / "config" / "urls.py"
    src = urls_path.read_text(encoding="utf-8")
    assert "FROZEN BY F1 — DO NOT EDIT OR REORDER" in src
    assert 'path("admin/", admin.site.urls)' in src
    # X3 must NOT have introduced an env-gate / conditional include here.
    assert "ADMIN_ENABLED" not in src
    assert "is_admin_configured" not in src

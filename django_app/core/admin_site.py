"""X3 — gated admin site + AdminConfig (import-light, model-free).

This module is split out from ``core/admin.py`` on purpose. Django loads
``INSTALLED_APPS`` entries during ``apps.populate()`` *before* model
classes are registered. ``config/settings.py`` (additive X3 block) points
``INSTALLED_APPS`` at :class:`BGXAdminConfig` here, so this module is
imported very early — it must NOT import ``core.models`` at top level or
Django raises ``AppRegistryNotReady``.

The actual ``ModelAdmin`` classes + registration + the Race/Result
vocabulary live in ``core/admin.py``, which Django imports later via
``AdminConfig.ready() -> admin.autodiscover()`` (apps fully ready by then).

What this module owns:

* :func:`is_admin_configured` — the Django-native equivalent of the old
  ``ADMIN_PASSWORD`` opt-in gate (``backend/app/admin.py:50-70``).
* :class:`BGXAdminSite` — an ``AdminSite`` whose entire ``/admin/*``
  surface (incl. the login page) raises ``Http404`` when admin is not
  configured: *absent*, exactly like the old app, no silent dev bypass.
* :class:`BGXAdminConfig` — wired via ``INSTALLED_APPS`` so the global
  ``django.contrib.admin.site`` (the lazy proxy the FROZEN
  ``config/urls.py`` already mounted at ``/admin/``) resolves to
  :class:`BGXAdminSite`. The frozen URL wiring is never touched.

Full auth-model migration rationale + the Railway provisioning runbook:
``core/ADMIN_BOOTSTRAP.md``.
"""

from __future__ import annotations

import os

from django.contrib.admin.apps import AdminConfig
from django.contrib.admin.sites import AdminSite
from django.http import Http404


def is_admin_configured() -> bool:
    """Return True iff the admin panel is explicitly enabled.

    Mirrors ``backend/app/admin.py``'s ``if not ADMIN_PASSWORD: return
    False`` opt-in: the old app disabled admin ENTIRELY when its
    credential env var was unset. This is the Django-native switch.

    Resolution (first decisive wins):

    1. ``ADMIN_ENABLED`` is a falsey token (``0``/``false``/``no``/
       ``off``/empty) → **disabled**, unconditionally — the explicit
       "no admin in this environment" kill switch, honoured even if a
       superuser row exists.
    2. ``ADMIN_ENABLED`` is a truthy token → **enabled**.
    3. ``ADMIN_ENABLED`` unset → infer from *provisioning*: enabled iff
       at least one active staff user exists (``bootstrap_admin`` has
       run). With no superuser and no env opt-in, admin is OFF —
       byte-for-byte the old "unconfigured ⇒ disabled, no silent dev
       bypass" behaviour.

    Read at request time (not import time) so a freshly bootstrapped
    container or a test flips without a process restart.
    """
    raw = os.getenv("ADMIN_ENABLED")
    if raw is not None:
        token = raw.strip().lower()
        if token in {"", "0", "false", "no", "off"}:
            return False
        if token in {"1", "true", "yes", "on"}:
            return True
        # Any other explicit non-empty value ⇒ "on" (permissive on the
        # positive side, strict on the negative side).
        return True

    # No explicit env decision → infer from provisioning. Imported here
    # to keep the module import side-effect-free / DB-free at app-load.
    try:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        return User.objects.filter(is_active=True, is_staff=True).exists()
    except Exception:
        # DB unreachable / not migrated yet → treat as NOT configured
        # (safe default: admin absent rather than half-open).
        return False


class BGXAdminSite(AdminSite):
    """The project admin site, gated on :func:`is_admin_configured`.

    When admin is NOT configured the entire ``/admin/*`` surface — the
    index, every model view, AND the login page — raises ``Http404``.
    That reproduces the old SQLAdmin behaviour where an unset
    ``ADMIN_PASSWORD`` made the panel hard-deny with no reachable login
    form (``backend/app/admin.py:64-70``). 404 (not 403) is deliberate:
    an unconfigured deployment looks like the route was never wired,
    giving an attacker zero signal and matching the FROZEN
    ``config/urls.py`` contract comment ("absent when unconfigured").
    """

    site_header = "BGX Admin"
    site_title = "BGX Admin"
    index_title = "BGX Hard Enduro — administration"

    def has_permission(self, request):
        # Gate first: an unconfigured admin grants permission to nobody,
        # even an authenticated staff user (defence in depth behind the
        # URL-layer 404 below).
        if not is_admin_configured():
            return False
        return super().has_permission(request)

    def get_urls(self):
        """Wrap every admin URL so it 404s when admin is disabled.

        The ``path("admin/", admin.site.urls)`` line in
        ``config/urls.py`` is FROZEN and cannot be env-gated. Instead
        each resolved admin view is wrapped: when admin is off the view
        raises ``Http404`` *before* any auth/login logic runs, so
        ``/admin``, ``/admin/login/`` and every model page are uniformly
        absent — not a 403 login wall.
        """
        urlpatterns = super().get_urls()

        for entry in urlpatterns:
            original_callback = getattr(entry, "callback", None)
            if original_callback is None:
                continue

            def make_gated(view):
                def gated(request, *args, **kwargs):
                    if not is_admin_configured():
                        raise Http404(
                            "Admin is not configured for this deployment."
                        )
                    return view(request, *args, **kwargs)

                gated.__name__ = getattr(view, "__name__", "gated")
                gated.__module__ = getattr(view, "__module__", __name__)
                return gated

            entry.callback = make_gated(original_callback)

        return urlpatterns


class BGXAdminConfig(AdminConfig):
    """Make ``django.contrib.admin.site`` resolve to :class:`BGXAdminSite`.

    Wired by swapping the ``"django.contrib.admin"`` entry in
    ``INSTALLED_APPS`` for ``"core.admin_site.BGXAdminConfig"`` inside
    the additive ``# === X3: admin ===`` block of ``config/settings.py``.
    Django reads ``default_site`` here and points the global
    ``admin.site`` lazy proxy (the one the FROZEN ``config/urls.py``
    already mounted) at the gated site — the frozen URL wiring needs no
    change. ``ready()`` (inherited) still runs ``admin.autodiscover()``
    which imports ``core/admin.py`` (the ModelAdmin/registration module)
    once apps are ready.
    """

    default_site = "core.admin_site.BGXAdminSite"

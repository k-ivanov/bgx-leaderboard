"""X3 — env-driven admin superuser bootstrap (no plaintext creds in image).

This is the Django-native *replacement* for the old env-gated shared
``ADMIN_PASSWORD`` credential (``backend/app/admin.py`` /
``backend/app/config.py:21-32``). The old stack compared a request
password against the ``ADMIN_PASSWORD`` env var at login time. Django
admin instead authenticates against a hashed password on an
``auth_user`` row, so a superuser must be *provisioned* once.

Design constraints (X3 acceptance criteria):

* **No plaintext credentials in the image or the repo.** This command
  reads the password from an environment variable that is injected by
  the platform's secret store at *runtime* (Railway variables / a
  Railway secret) — it is never a build arg, never committed, never
  echoed.
* **Idempotent.** Safe to run on every deploy (e.g. from the container
  entrypoint right after ``migrate``). If the user already exists it
  updates the password/flags in place instead of erroring.
* **Opt-in parity.** If no bootstrap env vars are provided the command
  no-ops and exits 0 (admin simply stays absent — see
  ``core/admin.is_admin_configured``). It NEVER invents a default
  password (that would be a silent dev bypass — the exact thing the old
  ``ADMIN_PASSWORD``-empty gate prevented).

Environment variables (all read at runtime, never baked in):

| Var | Default | Meaning |
|-----|---------|---------|
| ``ADMIN_BOOTSTRAP_PASSWORD`` | — (unset ⇒ no-op) | Superuser password. Injected from the platform secret store. |
| ``ADMIN_USERNAME``           | ``admin``         | Superuser username (reuses the old var name for operator familiarity; the *password* var is intentionally new so nobody mistakes it for the deprecated ``ADMIN_PASSWORD`` plaintext-compare gate). |
| ``ADMIN_BOOTSTRAP_EMAIL``    | ``""``            | Optional superuser email. |

See ``core/ADMIN_BOOTSTRAP.md`` for the full Railway runbook.
"""

from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Provision/refresh the admin superuser from runtime env vars "
        "(replaces the old ADMIN_PASSWORD gate). Idempotent; no-ops when "
        "ADMIN_BOOTSTRAP_PASSWORD is unset (opt-in parity)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default=None,
            help="Override $ADMIN_USERNAME (default: admin).",
        )

    def handle(self, *args, **options):
        password = os.getenv("ADMIN_BOOTSTRAP_PASSWORD")
        if not password:
            # Opt-in parity: no credential provided ⇒ admin stays absent.
            # NOT an error — this is the expected state for a deployment
            # that deliberately runs without admin (mirrors old
            # ADMIN_PASSWORD="" disabling the panel entirely).
            self.stdout.write(
                self.style.WARNING(
                    "ADMIN_BOOTSTRAP_PASSWORD not set — admin left "
                    "unprovisioned (opt-in parity, no-op). Set "
                    "ADMIN_ENABLED + ADMIN_BOOTSTRAP_PASSWORD to enable."
                )
            )
            return

        username = (
            options.get("username")
            or os.getenv("ADMIN_USERNAME")
            or "admin"
        )
        email = os.getenv("ADMIN_BOOTSTRAP_EMAIL", "")

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email},
        )
        # Idempotent: always (re)assert the intended state so a password
        # rotation is just a redeploy with a new secret value.
        user.email = email or user.email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()

        verb = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} admin superuser '{username}'. Admin is now "
                f"reachable (ensure ADMIN_ENABLED is truthy or rely on "
                f"the provisioning-signal default)."
            )
        )

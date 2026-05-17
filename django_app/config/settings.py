"""Django settings for the BGX Hard Enduro Dashboard (Django 6 + Ninja rewrite).

F1 scaffold. This module ports EVERY environment variable / constant read by
the frozen FastAPI app so the new project is a behavioral mirror.

OLD → DJANGO SETTING MAPPING
============================
The new project must read the exact same env vars as the FastAPI app it
replaces. Source of truth: ``backend/app/config.py`` + ``backend/src/config.py``
(+ a couple of process-level vars used by the Dockerfile / start.sh).

| Old (env var / constant)        | Old location              | Django setting (this file)        | Notes |
|---------------------------------|---------------------------|-----------------------------------|-------|
| ``DATABASE_URL``                | src/config.py             | ``DATABASES['default']``          | Same var. ``postgres://`` / ``postgresql://`` normalized; Django uses psycopg3 (engine ``django.db.backends.postgresql``) — the SQLAlchemy ``+psycopg2`` suffix is stripped, not added. Required (raises if unset, matching ``get_database_url``). |
| ``DEFAULT_SEASON_YEAR`` (=2026) | src/config.py             | ``DEFAULT_SEASON_YEAR``           | Same var, same default 2026, cast to int. |
| ``APP_VERSION`` (="0.1.0")      | src/config.py (constant)  | ``APP_VERSION``                   | Not an env var; ported constant. Used by ``/health``. |
| ``STATS_PASSWORD`` (="")        | app/config.py             | ``STATS_PASSWORD``                | Same var, same "" default (empty = no auth, dev). Consumed by S5/X2. |
| ``ADMIN_USERNAME`` (="admin")   | app/config.py             | ``ADMIN_USERNAME``                | Same var/default. Consumed by X3 (admin bootstrap). |
| ``ADMIN_PASSWORD`` (="")        | app/config.py             | ``ADMIN_PASSWORD``                | Same var/default. Empty = admin disabled (opt-in). Consumed by X3. |
| ``ADMIN_SESSION_SECRET``        | app/config.py             | ``SECRET_KEY`` + ``ADMIN_SESSION_SECRET`` | Same var. Drives Django ``SECRET_KEY`` (session/cookie signing — the Django-native equivalent of the old itsdangerous session secret) and is also kept verbatim for X3. Same dev-only fallback string. |
| ``FRONTEND_DIST``               | app/main.py               | ``FRONTEND_DIST``                 | Same var. Static catch-all (X1) resolves the Astro ``dist/`` from it; same resolution order (env → /app/frontend_dist → ../frontend/dist). |
| ``PORT`` (=5001)                | Dockerfile / start.sh     | ``SERVER_PORT``                   | Process-level; gunicorn binds it (Dockerfile.django CMD). Mirrored here for reference/parity tests. |
| ``HOST`` (=0.0.0.0)             | Dockerfile / start.sh     | ``SERVER_HOST``                   | Process-level; gunicorn binds it. Mirrored here. |
| ``TRACK_MAX_BYTES`` (=2048)     | app/config.py (constant)  | ``TRACK_MAX_BYTES``               | Ported constant. Consumed by S6 payload guard. |
| ``TRACK_RATE_LIMIT`` (="10/minute") | app/config.py (constant) | ``TRACK_RATE_LIMIT`` + ``NINJA_DEFAULT_THROTTLE_RATES`` | Ported constant. S6 wires Ninja throttling from this. |
| ``DJANGO_SECRET_KEY``           | (new, Django-only)        | ``SECRET_KEY`` (override)         | New optional var: lets ops set a dedicated Django secret distinct from the admin session secret. Falls back to ``ADMIN_SESSION_SECRET``. |
| ``DJANGO_DEBUG``                | (new, Django-only)        | ``DEBUG``                         | New. Defaults False (prod-safe). The old app had no debug mode. |
| ``DJANGO_ALLOWED_HOSTS``        | (new, Django-only)        | ``ALLOWED_HOSTS``                 | New, required by Django's host header validation (no FastAPI equivalent). Defaults permissive ("*") so the scaffold boots; X2 hardens this for Railway proxy/TLS. |

Anything not in this table is NOT read by the old app and is intentionally
absent. Cross-cutting concerns (security headers, CSP, proxy/TLS, gated docs)
are deliberately deferred to X2 per the task plan — F1 only scaffolds.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env (parity with backend/src/config.py:8 `load_dotenv()`).
# Probe the django_app dir and the repo root so either location works.
BASE_DIR = Path(__file__).resolve().parent.parent  # …/django_app
REPO_ROOT = BASE_DIR.parent
for _env in (BASE_DIR / ".env", REPO_ROOT / ".env"):
    if _env.is_file():
        load_dotenv(_env)
        break
else:
    load_dotenv()  # fall back to default CWD-based discovery


# ---------------------------------------------------------------------------
# Ported constants (not env vars in the old app — keep the literals identical)
# ---------------------------------------------------------------------------

# backend/src/config.py:10
APP_VERSION = "0.1.0"

# backend/app/config.py:18-19
TRACK_MAX_BYTES = 2048
TRACK_RATE_LIMIT = "10/minute"


# ---------------------------------------------------------------------------
# Ported env vars (same names + defaults as the FastAPI app)
# ---------------------------------------------------------------------------

# backend/src/config.py:37
DEFAULT_SEASON_YEAR = int(os.getenv("DEFAULT_SEASON_YEAR", "2026"))

# backend/app/config.py:15
STATS_PASSWORD = os.getenv("STATS_PASSWORD", "")

# backend/app/config.py:26-32
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_SESSION_SECRET = os.getenv(
    "ADMIN_SESSION_SECRET",
    # Dev-only fallback — identical literal to backend/app/config.py:30.
    "dev-only-insecure-please-override-in-production",
)

# backend/app/main.py:191 — resolved by the X1 static catch-all later.
FRONTEND_DIST = os.getenv("FRONTEND_DIST", "")

# Process-level (Dockerfile / start.sh). Mirrored for reference + parity tests.
SERVER_HOST = os.getenv("HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("PORT", "5001"))


# ---------------------------------------------------------------------------
# Django core
# ---------------------------------------------------------------------------

# SECRET_KEY: the old app signed admin sessions with ADMIN_SESSION_SECRET via
# itsdangerous. Django's native equivalent is SECRET_KEY. Allow a dedicated
# DJANGO_SECRET_KEY override; otherwise reuse the admin session secret so
# there is exactly one signing key with the same provisioning path.
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", ADMIN_SESSION_SECRET)

# Old app had no debug mode; default off (prod-safe). New var, Django-only.
DEBUG = os.getenv("DJANGO_DEBUG", "").lower() in {"1", "true", "yes", "on"}

# Django requires explicit host validation (no FastAPI equivalent). Scaffold
# default is permissive so `runserver` boots out of the box; X2 tightens this
# for the Railway proxy (ALLOWED_HOSTS / CSRF_TRUSTED_ORIGINS / proxy SSL).
ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")
    if h.strip()
] or ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Project apps. `core` holds the ported ORM models (filled in F2).
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # NOTE: security headers / CSP / proxy-TLS middleware is X2's job, not F1.
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# ---------------------------------------------------------------------------
# Database — DATABASE_URL parity with backend/src/config.py
# ---------------------------------------------------------------------------

def _normalize_database_url(url: str) -> str:
    """Mirror backend/src/config.py::_normalize_database_url, but for Django.

    The old code rewrote the URL to the SQLAlchemy ``postgresql+psycopg2://``
    dialect. Django's psycopg3 backend wants a plain ``postgres://`` /
    ``postgresql://`` URL, so we instead STRIP any SQLAlchemy driver suffix
    and normalize the scheme. Same env var, same accepted inputs (Railway's
    bare ``postgres://`` included).
    """
    if url.startswith("postgresql+psycopg2://"):
        url = "postgresql://" + url[len("postgresql+psycopg2://"):]
    elif url.startswith("postgresql+psycopg://"):
        url = "postgresql://" + url[len("postgresql+psycopg://"):]
    elif url.startswith("postgres+psycopg2://"):
        url = "postgres://" + url[len("postgres+psycopg2://"):]
    return url


def _database_config() -> dict:
    """Build DATABASES['default'] from DATABASE_URL.

    Matches backend/src/config.py::get_database_url contract: missing var is a
    hard error with the same guidance message.
    """
    raw = os.getenv("DATABASE_URL")
    if not raw:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env for local dev, "
            "or attach a Postgres plugin on Railway."
        )
    import dj_database_url

    cfg = dj_database_url.parse(
        _normalize_database_url(raw),
        conn_max_age=600,
    )
    cfg["ENGINE"] = "django.db.backends.postgresql"  # psycopg3
    return cfg


# `runserver` / gunicorn require a live Postgres and MUST hard-fail with the
# same message as backend/src/config.py::get_database_url when DATABASE_URL is
# unset (parity). Two narrow escape hatches keep the F1 scaffold runnable
# without Postgres:
#   • Running under pytest (the F1 harness must exit 0 with zero PG — the real
#     parity rig + prod-clone DB fixture is F3's job, not F1's).
#   • DJANGO_ALLOW_NO_DB=1 (explicit opt-in for `manage.py check` smoke runs /
#     CI without PG).
# When DATABASE_URL IS set, the real Postgres config is always used.
_NO_DB_OK = bool(os.getenv("PYTEST_CURRENT_TEST")) or "pytest" in os.path.basename(
    os.environ.get("_", "")
) or os.getenv("DJANGO_ALLOW_NO_DB") == "1" or any(
    "pytest" in a for a in __import__("sys").argv
)

try:
    DATABASES = {"default": _database_config()}
except RuntimeError:
    if _NO_DB_OK:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        }
    else:
        raise


# ---------------------------------------------------------------------------
# Passwords / i18n / static — Django boilerplate (no old-app equivalent)
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CLAUDE.md invariant: legacy URLs keep their no-trailing-slash shape.
# Django must NOT auto-append a slash and 301 — that would break the X1
# redirect contract + the indexed static URLs.
APPEND_SLASH = False


# === X2: security/proxy/TLS ================================================
# Owned by X2 (task plan §X2). ADDITIVE-ONLY block — appended at the end so
# F2/X3 can edit this file concurrently without conflict. It only AUGMENTS
# existing keys (MIDDLEWARE/ALLOWED_HOSTS) via list mutation and adds new
# SECURE_*/CSRF settings; it never reorders or rewrites the F1 definitions
# above. Source of truth: backend/app/security_headers.py + main.py gated docs
# + review OV3 (proxy/TLS). Same-origin is preserved: NO CORS middleware is
# added here and none exists elsewhere — zero Access-Control-* headers ship.

# --- Baseline security-headers middleware (port of FastAPI parity oracle) ---
# Registered FIRST (outermost) so its process_response runs LAST and is the
# final writer for every header it owns — guarantees the byte-identical
# header set even though Django's SecurityMiddleware also touches some of
# them. HttpResponse.headers is single-value + case-insensitive, so this
# replaces (never duplicates) any value an inner middleware set.
if "core.security_headers.SecurityHeadersMiddleware" not in MIDDLEWARE:
    MIDDLEWARE = ["core.security_headers.SecurityHeadersMiddleware", *MIDDLEWARE]

# --- Proxy / TLS (review OV3) ----------------------------------------------
# Railway terminates TLS at the edge and forwards plain HTTP to the app with
# X-Forwarded-Proto: https. Without this, request.is_secure() is False for a
# forwarded request and HSTS is silently dropped (the documented X2 failure
# mode). SECURE_* flags alone are insufficient — the proxy header binding is
# what makes Django treat the forwarded request as HTTPS.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Host-header validation. The FastAPI app had NO host validation, so the F1
# scaffold default stays permissive ("*") unless ops sets DJANGO_ALLOWED_HOSTS
# (already parsed into ALLOWED_HOSTS by the F1 block above). This block only
# adds the canonical Railway host when one is provided, without dropping the
# operator's explicit list (additive — never narrows an explicit config).
_railway_host = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
if _railway_host and "*" not in ALLOWED_HOSTS and _railway_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS = [*ALLOWED_HOSTS, _railway_host]

# CSRF trusted origins MUST be scheme-qualified (Django requirement) for any
# cross-origin POST behind the proxy (e.g. the X3 admin login form over the
# forwarded-HTTPS origin). The read-only public API is same-origin and unaffected.
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]
if _railway_host:
    _railway_origin = f"https://{_railway_host}"
    if _railway_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS = [*CSRF_TRUSTED_ORIGINS, _railway_origin]

# --- Align Django's own SECURE_* so it can't emit a DIVERGENT header --------
# Django's SecurityMiddleware default SECURE_REFERRER_POLICY is "same-origin",
# but the FastAPI parity oracle emits "strict-origin-when-cross-origin".
# Pin Django's value to the parity value so even if ordering ever changed,
# the byte-identical Referrer-Policy is the only possible outcome. Our X2
# middleware still owns the authoritative write.
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
# X2's middleware is the sole HSTS authority (exact "max-age=63072000;
# includeSubDomains", scheme+proxy-sensitive). Keep Django's HSTS OFF so it
# can't emit a second/divergent Strict-Transport-Security.
SECURE_HSTS_SECONDS = 0
# Behavior parity: the FastAPI app never force-redirected http→https
# (TLS is terminated at the Railway edge). Do not introduce a redirect.
SECURE_SSL_REDIRECT = False
# Mark session/CSRF cookies secure only when actually behind TLS in prod;
# DEBUG (dev http) keeps them usable. Parity-neutral hardening that depends
# on the same forwarded-proto detection configured above.
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
# === END X2: security/proxy/TLS ============================================

# === F2: models/db ===
# Additive-only block (F2 owns models + the fake-initial adoption). Nothing
# above is reordered or rewritten. `core` is already in INSTALLED_APPS and the
# real DATABASES config is already built (both added by F1) — F2 does not
# duplicate them. The two F2-relevant facts pinned here:
#
#  1. The 8 domain tables (season, category, event, rider, event_result,
#     visit, import_log, analytics_salt) are ADOPTED with ZERO schema change
#     via `manage.py migrate --fake-initial` (decision I2-arch=A). Django's
#     own auth/admin/sessions/contenttypes tables ARE created fresh — that is
#     expected. Full proof: core/MIGRATION_PARITY.md. HITL prod-clone
#     rehearsal runbook: core/MIGRATION_REHEARSAL.md.
#
#  2. The project-wide DEFAULT_AUTO_FIELD stays BigAutoField (untouched
#     above — it governs Django's freshly-created contrib tables). The `core`
#     app overrides it to AutoField in core/apps.py because the real
#     production *_id_seq sequences are 32-bit `integer` (Alembic
#     sa.Integer() PKs); a BigAutoField id would be schema drift on the
#     adopted tables. The override is intentionally scoped to `core` only.
#
# No new settings keys are required for F2 — this block is documentation of
# the adoption contract so parallel agents editing this file do not "fix" the
# AutoField/BigAutoField split or re-add a core/DATABASES entry.
# === end F2: models/db ===

# === F3: foundation/test ===
# Additive-only block (decision I4/I5/I7). Appended AFTER the X2 + F2 blocks
# per the file's concurrency contract — nothing above is reordered or
# rewritten. Like the F2 block, F3 needs NO new functional settings keys; the
# serialization-parity renderer is pinned WITHOUT touching this file or the
# FROZEN api/__init__.py. This block documents the F3 contract so parallel
# agents editing settings.py don't "fix" or duplicate F3's wiring:
#
#  1. RENDERER PIN (decision I5-cq=A). The byte-parity JSON renderer
#     (api.renderers.ParityJSONRenderer — Starlette-exact json.dumps params)
#     is pinned onto the single FROZEN NinjaAPI instance at Django app-ready
#     time via core.apps.CoreConfig.ready -> api.renderers.pin_parity_renderer
#     (additive ready() hook; reads api.renderer LIVE per request). It is
#     deliberately NOT a Django setting and NOT an edit to api/__init__.py
#     (FROZEN, decision I1-arch=A). Do not add a NINJA renderer setting or a
#     second pin path — there is exactly one, idempotent.
#
#  2. TEST DB / PARITY RIG (decision I7-test=A). pytest-django's DEFAULT test
#     DB behaviour (isolated test_<DATABASE_URL-db>, real 0001_initial) is
#     left UNTOUCHED so F2's @pytest.mark.django_db model tests keep clean
#     isolation. The old<->new parity rig (tests/parity.py) instead spins the
#     FROZEN backend/ FastAPI app AND the new Django app as SUBPROCESSES
#     against two dedicated, identically-seeded DBs. These are configured by
#     ENV VARS consumed only by the test harness — intentionally NOT Django
#     settings (they must not affect the prod/runtime DB):
#       ORACLE_DATABASE_URL   default postgresql://bgx:bgx@localhost:5432/bgx_oracle
#       NEW_DATABASE_URL      default postgresql://bgx:bgx@localhost:5432/bgx_django
#       BGX_MAIN_REPO / BGX_BACKEND_DIR / BGX_BACKEND_PYTHON / F3_DJANGO_PYTHON
#                             — locate the shared frozen backend/ + venvs when
#                               the suite runs from a linked git worktree.
#     The runtime DATABASES config (built by F1, documented by F2) is the
#     single source of truth for the deployed app and is NOT modified here.
#
# No new settings keys are required for F3 — this block is documentation only.
# === end F3: foundation/test ===

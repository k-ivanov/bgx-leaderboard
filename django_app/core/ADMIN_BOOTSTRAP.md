# X3 — Admin auth bootstrap + disable-when-unset opt-in (runbook)

> Owner: X3. This documents the **explicit, not-silent** auth-model
> migration off the old `ADMIN_PASSWORD` shared-credential gate and onto
> Django auth, plus the exact Railway provisioning + opt-in procedure.
> Source of truth being replaced: `backend/app/admin.py` +
> `backend/app/config.py:21-32` (the frozen FastAPI/SQLAdmin parity
> oracle). Carried note from F2: `MIGRATION_REHEARSAL.md §0` ("X3 owns
> the migration of the operator off `ADMIN_PASSWORD`").

---

## 0. TL;DR for the operator

| Old (FastAPI / SQLAdmin) | New (Django admin) |
|---|---|
| `ADMIN_PASSWORD` set ⇒ admin on; empty ⇒ admin **entirely absent** | `ADMIN_ENABLED` truthy **and** a superuser provisioned ⇒ admin on; otherwise **entirely absent (404)** |
| Login: `ADMIN_USERNAME` + `ADMIN_PASSWORD` compared at request time (constant-time) | Login: Django auth — username + a **hashed** password on an `auth_user` row |
| Session: itsdangerous cookie signed by `ADMIN_SESSION_SECRET` | Session: Django sessions, signed by `SECRET_KEY` (F1 maps `SECRET_KEY` ← `DJANGO_SECRET_KEY` or `ADMIN_SESSION_SECRET`) |
| Credential lived in an env var, compared in plaintext | Credential is a Django password **hash** in the DB; the plaintext is injected once at deploy from the platform secret store and never stored/echoed |

**`ADMIN_PASSWORD` is no longer read by the new stack.** It is not a
credential anymore. `ADMIN_USERNAME` is still read — only as the default
*username* for the provisioned superuser.

To turn admin **ON** in a deployment, set BOTH:

```
ADMIN_ENABLED=1
ADMIN_BOOTSTRAP_PASSWORD=<injected from Railway secret — never committed>
```

To keep admin **OFF** (the safe default — byte-for-byte the old
"`ADMIN_PASSWORD` empty disables admin"): set neither, or set
`ADMIN_ENABLED=0`. `/admin/*` then returns **404** (absent), with no
reachable login form and no silent dev bypass.

---

## 1. Why the auth model had to change (and why that is in scope)

Django admin authenticates against Django's auth system (`auth_user`
rows, `is_staff` / `is_superuser`, the session framework). It cannot
reuse the old "compare the request password to the `ADMIN_PASSWORD` env
var" scheme. So a superuser must be **provisioned once** with a hashed
password. This is a real, deliberate auth-model change — documented here,
not done silently. F2's migration rehearsal already creates Django's
`auth_*` tables fresh (`MIGRATION_REHEARSAL.md §0`); this runbook is the
step that puts a credential into them.

The opt-in semantics are preserved exactly:

* The old panel **wrote/deleted data**, so an unset credential disabled
  it *entirely* — no silent dev bypass. The new gate
  (`core/admin_site.py::is_admin_configured`) keeps that: unconfigured ⇒
  every `/admin/*` URL (including the login page) returns **404**.
* 404 (not 403) is intentional: an unconfigured deployment looks like the
  route was never wired — zero signal to an attacker, and consistent with
  the FROZEN `config/urls.py` contract comment ("absent when
  unconfigured").

---

## 2. The opt-in gate — `is_admin_configured()`

Resolved at **request time** (so a freshly bootstrapped container flips
without a restart). First decisive rule wins:

1. `ADMIN_ENABLED` is a falsey token (`0` / `false` / `no` / `off` /
   empty) → **disabled**, unconditionally. Explicit kill switch; honoured
   even if a superuser row exists.
2. `ADMIN_ENABLED` is a truthy token (`1` / `true` / `yes` / `on` / any
   other non-empty value) → **enabled**.
3. `ADMIN_ENABLED` **unset** → infer from provisioning: enabled iff at
   least one active `is_staff` user exists (i.e. `bootstrap_admin` ran).
   No superuser + no env opt-in ⇒ **OFF** (the old default).

`BGXAdminSite` (a gated `AdminSite`) enforces this two ways:

* `has_permission()` returns `False` when not configured (nobody, not
  even an authenticated staff user, gets in);
* `get_urls()` wraps **every** admin view callback so it raises `Http404`
  *before* any auth/login logic — so `/admin`, `/admin/login/` and every
  model page are uniformly **absent** when unconfigured.

`BGXAdminConfig` (an `AdminConfig` subclass, wired via `INSTALLED_APPS` in
the additive `# === X3: admin ===` settings block) points the global
`django.contrib.admin.site` proxy — the one the **FROZEN**
`config/urls.py` already mounted at `/admin/` — at `BGXAdminSite`. This
is how disable-when-unset is achieved **without editing the frozen
`config/urls.py`** (which still just does `path("admin/",
admin.site.urls)`).

---

## 3. Railway provisioning — no plaintext in the image or the repo

### 3.1 One-time: store the password as a Railway secret

In the Railway service → **Variables**, add (these are stored in
Railway's secret store, injected as env vars at **runtime**, never baked
into the Docker image, never committed):

| Variable | Value | Notes |
|---|---|---|
| `ADMIN_ENABLED` | `1` | Turns the gate on. Omit / set `0` to keep admin absent. |
| `ADMIN_BOOTSTRAP_PASSWORD` | *(a long random string)* | The superuser password. **Secret.** Generate with `python -c "import secrets;print(secrets.token_urlsafe(32))"`. Rotating it = change this value + redeploy. |
| `ADMIN_USERNAME` | `admin` (default) | Reused from the old stack for operator familiarity. Optional. |
| `ADMIN_BOOTSTRAP_EMAIL` | *(optional)* | Superuser email. |
| `DJANGO_SECRET_KEY` | *(a long random string)* | Session signing. Already wired by F1 (falls back to `ADMIN_SESSION_SECRET`); set a dedicated one in prod. |

Never put `ADMIN_BOOTSTRAP_PASSWORD` in `.env`, `Dockerfile`,
`railway.json`, any committed file, or a build arg. It is a runtime
secret only.

### 3.2 Provision on deploy — idempotent management command

After `manage.py migrate` (F2's adoption migration), run the X3
bootstrap command. It is **idempotent** (safe every deploy) and a
**no-op** when `ADMIN_BOOTSTRAP_PASSWORD` is unset (opt-in parity — it
never invents a default password):

```bash
python manage.py migrate --fake-initial      # F2 — adopt the 8 tables, create contrib tables
python manage.py bootstrap_admin             # X3 — provision/refresh the superuser from env
```

Wire it into the container start sequence (the I1 cutover task owns the
final Dockerfile/Railway command; X3 only specifies the step). The
command:

* reads `ADMIN_BOOTSTRAP_PASSWORD` from the runtime env (never logs it);
* `get_or_create`s the `auth_user` row for `$ADMIN_USERNAME`;
* sets `is_staff = is_superuser = is_active = True` and
  `set_password(...)` (Django hashes it — only the hash is stored);
* re-asserts that state every run, so a password rotation is just "change
  the Railway secret + redeploy".

### 3.3 Verify

* `ADMIN_ENABLED` unset / `0`, no superuser → `GET /admin/` and
  `GET /admin/login/` both return **404** (absent).
* `ADMIN_ENABLED=1` + `bootstrap_admin` ran → `GET /admin/login/` serves
  the Django login form; logging in with `$ADMIN_USERNAME` +
  the bootstrap password reaches the panel; the 6 model views
  (Season / Category / **Race** / Rider / **Result** / Visit) are
  present; **Visit is read-only** (no add/change/delete).

---

## 4. Local development

Admin is **off by default** locally too (no silent dev bypass — matches
the old behaviour where an empty `ADMIN_PASSWORD` disabled it). To use it
locally:

```bash
cd django_app
export ADMIN_ENABLED=1
export ADMIN_BOOTSTRAP_PASSWORD='dev-only-change-me'
python manage.py migrate            # against your local Postgres
python manage.py bootstrap_admin
python manage.py runserver          # /admin/ now reachable
```

Or, for an interactive one-off, the stock `python manage.py
createsuperuser` also works (it writes the same `auth_user` row that the
gate's provisioning-signal default detects) — but `bootstrap_admin` is
the deploy-friendly, non-interactive, idempotent path.

---

## 5. Decommissioning `ADMIN_PASSWORD`

Once the new stack is live (I1 cutover):

* Remove `ADMIN_PASSWORD` from Railway — it is dead in the new app
  (nothing reads it). Leaving it set is harmless but misleading; delete
  it to avoid the impression it still gates anything.
* Keep `ADMIN_USERNAME` (still used as the bootstrap username default).
* Ensure `ADMIN_ENABLED` + `ADMIN_BOOTSTRAP_PASSWORD` + a dedicated
  `DJANGO_SECRET_KEY` are set if admin is wanted in prod; otherwise the
  panel stays absent by design.

This decommissioning is an operator action at the I1 cutover, listed here
so it is not forgotten — the code change (no longer reading
`ADMIN_PASSWORD`) is already done in X3.

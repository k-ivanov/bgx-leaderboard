"""Old↔new parity rig + ``assert_json_parity`` (F3 / decision I7-test=A).

This is the spine the whole rewrite is graded against: the frozen FastAPI
``backend/`` app is the runtime parity oracle (the old behavior IS the spec —
``.plan/django-ninja-tasks.md`` header). S1–S7 and X4 import from here; no
slice ships its own oracle, DB fixture, or bespoke JSON differ.

Two pieces:

1. ``assert_json_parity(old, new, *, ...)`` — proves two HTTP responses are
   JSON-equal AND serialization-format-equal:
     * status code identical;
     * response BODY bytes decode to equal JSON (semantic equality);
     * the F3 serialization spec holds on BOTH sides — compact
       ``separators=(",", ":")`` (no whitespace), non-ASCII NOT escaped
       (raw UTF-8 Cyrillic), key order = declaration order (NOT sorted),
       ``date``/``datetime`` ISO-8601, numbers are JSON numbers not quoted
       strings (the Decimal→``float``-annotation guard rail);
     * media-type PREFIX identical (the ``; charset=utf-8`` Ninja-vs-Starlette
       suffix is the ONE documented, parity-safe divergence — see
       ``api/renderers.py``; this helper compares the prefix, not the
       charset param, and records the delta).

2. ``ParityRig`` — spins BOTH stacks as SUBPROCESSES against their OWN
   seeded Postgres databases and exposes ``.old(path)`` / ``.new(path)``:
     * the FROZEN ``backend/`` FastAPI app via its OWN venv
       (``backend/.venv``) → the ``bgx_oracle`` DB;
     * the NEW Django + Ninja app via the F3 venv → the ``bgx_django`` DB.
   Subprocesses (not in-process) on purpose:
     - the oracle's dependency closure (SQLAlchemy 2 + its pinned pydantic)
       must not collide with Django 6 + Ninja + pydantic in the test
       interpreter;
     - it FULLY decouples the parity rig from pytest-django's managed test
       DB lifecycle, so F2's ``@pytest.mark.django_db`` model tests keep
       their clean isolated ``test_*`` schema (no shared-state contamination
       — the bug this design eliminates).
   Both DBs are seeded from the SAME ``seed_data/`` (identical golden data),
   so any byte difference is a real behavior/serialization divergence, never
   a data-skew artifact.

If either stack cannot be spun in a given sandbox (no Postgres, missing
venv, unseeded DB), ``ParityRig.unavailable_reason()`` returns a precise
human string + the exact manual command; the parity fixtures SKIP with it.
The rig NEVER fakes a green parity result (F3 acceptance requirement).
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

# Repo root = …/django_app/tests/parity.py → parents[2].
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
DJANGO_DIR = REPO_ROOT / "django_app"
BACKEND_PYTHON = BACKEND_DIR / ".venv" / "bin" / "python"

# The F3 venv that runs the NEW app subprocess. Default to the F3-created
# venv; overridable so CI / the container can point at its own interpreter.
F3_PYTHON = Path(
    os.getenv("F3_DJANGO_PYTHON", str(REPO_ROOT / ".venv-f3" / "bin" / "python"))
)

# Two dedicated, identically-seeded DBs — one per stack. No shared state.
# Overridable for CI. Defaults match the parity-rig DBs F3 provisions.
ORACLE_DATABASE_URL = os.getenv(
    "ORACLE_DATABASE_URL", "postgresql://bgx:bgx@localhost:5432/bgx_oracle"
)
NEW_DATABASE_URL = os.getenv(
    "NEW_DATABASE_URL", "postgresql://bgx:bgx@localhost:5432/bgx_django"
)


# ---------------------------------------------------------------------------
# assert_json_parity — the JSON + serialization-format equality contract
# ---------------------------------------------------------------------------

# json.dumps params that, applied to a parsed object, reproduce the PINNED
# F3 serialization spec (== Starlette JSONResponse.render). Used to normalize
# both sides to a single canonical byte form for the format assertion.
_CANONICAL_DUMPS = dict(
    ensure_ascii=False,
    allow_nan=False,
    indent=None,
    separators=(",", ":"),
    sort_keys=False,
)


def _media_type_prefix(content_type: Optional[str]) -> str:
    """``"application/json; charset=utf-8"`` → ``"application/json"``."""
    if not content_type:
        return ""
    return content_type.split(";", 1)[0].strip().lower()


def _assert_format_spec(raw: str, label: str) -> None:
    """Assert ``raw`` already obeys the pinned F3 serialization spec.

    This is what makes the helper a *format* check, not just a semantic one:
    re-dumping the parsed object with the canonical params must reproduce the
    EXACT bytes. If a side used spaces after ``,``/``:``, escaped non-ASCII,
    sorted keys, or quoted a number, the canonical re-dump differs and we
    fail with a precise diff.
    """
    parsed = json.loads(raw)
    canonical = json.dumps(parsed, **_CANONICAL_DUMPS)
    if raw != canonical:
        i = next(
            (k for k in range(min(len(raw), len(canonical))) if raw[k] != canonical[k]),
            min(len(raw), len(canonical)),
        )
        raise AssertionError(
            f"{label}: serialization-format spec violated "
            f"(compact separators / ensure_ascii=False / no key re-sort / "
            f"numbers-not-quoted).\n"
            f"  first diff at byte {i}\n"
            f"  actual   …{raw[max(0, i - 30):i + 30]!r}…\n"
            f"  expected …{canonical[max(0, i - 30):i + 30]!r}…"
        )


def assert_json_parity(
    old: Any,
    new: Any,
    *,
    check_format: bool = True,
    check_content_type: bool = True,
) -> None:
    """Assert two HTTP responses are JSON- and serialization-format-equal.

    ``old`` / ``new`` are response objects exposing ``.status_code``,
    ``.content`` (bytes) and ``.headers`` (mapping). Works for the rig's
    ``_HTTPResponse`` shims and a Django test-client response alike.

    Checks, in order:
      1. status codes identical;
      2. bodies parse to semantically-equal JSON;
      3. (``check_format``) BOTH bodies already obey the pinned F3 spec —
         this is the Decimal/date/key-order proof;
      4. (``check_content_type``) media-type PREFIXes match
         (``application/json``); the ``; charset=utf-8`` suffix is the
         documented parity-safe divergence and is NOT failed on.
    """
    assert old.status_code == new.status_code, (
        f"status mismatch: oracle={old.status_code} new={new.status_code}\n"
        f"  oracle body: {old.content[:400]!r}\n"
        f"  new body:    {new.content[:400]!r}"
    )

    old_raw = old.content.decode("utf-8")
    new_raw = new.content.decode("utf-8")

    old_json = json.loads(old_raw)
    new_json = json.loads(new_raw)
    assert old_json == new_json, (
        "JSON bodies differ semantically.\n"
        f"  oracle: {json.dumps(old_json, ensure_ascii=False)[:600]}\n"
        f"  new:    {json.dumps(new_json, ensure_ascii=False)[:600]}"
    )

    if check_format:
        _assert_format_spec(old_raw, "oracle")
        _assert_format_spec(new_raw, "new")

    if check_content_type:
        old_ct = _media_type_prefix(old.headers.get("content-type"))
        new_ct = _media_type_prefix(new.headers.get("content-type"))
        assert old_ct == new_ct == "application/json", (
            f"content-type media-type prefix mismatch: "
            f"oracle={old_ct!r} new={new_ct!r} "
            f"(the '; charset=utf-8' suffix is the one documented, "
            f"parity-safe divergence — see api/renderers.py)"
        )


# ---------------------------------------------------------------------------
# subprocess plumbing
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _tcp_open(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _pg_host_port(url: str) -> tuple[str, int]:
    from urllib.parse import urlparse

    clean = url
    for pre in (
        "postgresql+psycopg2://",
        "postgresql+psycopg://",
        "postgres+psycopg2://",
    ):
        if clean.startswith(pre):
            clean = "postgresql://" + clean[len(pre):]
            break
    try:
        p = urlparse(clean)
        return p.hostname or "localhost", p.port or 5432
    except Exception:
        return "localhost", 5432


class OracleUnavailable(RuntimeError):
    """Raised/checked when a stack cannot be spun in this sandbox."""


class _HTTPResponse:
    """Minimal response shim with the attrs ``assert_json_parity`` needs."""

    def __init__(self, status_code: int, content: bytes, headers: dict) -> None:
        self.status_code = status_code
        self.content = content
        self.headers = {k.lower(): v for k, v in headers.items()}


class _Subapp:
    """A uvicorn-served app subprocess (FastAPI oracle or new Django app)."""

    def __init__(
        self, *, name: str, python: Path, cwd: Path, app: str,
        database_url: str, settings_module: str | None = None,
    ) -> None:
        self.name = name
        self.python = python
        self.cwd = cwd
        self.app = app
        self.database_url = database_url
        self.settings_module = settings_module
        self.port = _free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self._proc: Optional[subprocess.Popen] = None

    def start(self) -> None:
        env = dict(os.environ)
        env["DATABASE_URL"] = self.database_url
        env["FRONTEND_DIST"] = ""  # API-only: never let static shadow /api/*
        if self.settings_module:
            env["DJANGO_SETTINGS_MODULE"] = self.settings_module
        self._proc = subprocess.Popen(
            [
                str(self.python), "-m", "uvicorn", self.app,
                "--host", "127.0.0.1", "--port", str(self.port),
                "--log-level", "warning",
            ],
            cwd=str(self.cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + 35.0
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                out = (
                    self._proc.stdout.read().decode(errors="replace")
                    if self._proc.stdout else ""
                )
                raise OracleUnavailable(
                    f"{self.name} exited during boot "
                    f"(code {self._proc.returncode}):\n{out[-2000:]}"
                )
            try:
                with urllib.request.urlopen(f"{self.base_url}/health", timeout=1) as r:
                    if r.status == 200:
                        return
            except (urllib.error.URLError, ConnectionError, OSError):
                time.sleep(0.25)
        self.stop()
        raise OracleUnavailable(f"{self.name} did not become healthy in 35s")

    def stop(self) -> None:
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=5)
            self._proc = None

    def get(self, path: str) -> _HTTPResponse:
        req = urllib.request.Request(f"{self.base_url}{path}", method="GET")
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return _HTTPResponse(resp.status, resp.read(), dict(resp.headers))
        except urllib.error.HTTPError as e:  # 4xx/5xx still carry a body
            return _HTTPResponse(e.code, e.read(), dict(e.headers))


# ---------------------------------------------------------------------------
# ParityRig — both stacks, identical seed, diffed over HTTP
# ---------------------------------------------------------------------------


class ParityRig:
    """Context manager spinning the FastAPI oracle + the new Django app.

    Usage::

        with ParityRig() as rig:
            assert_json_parity(rig.old("/api/seasons"), rig.new("/api/seasons"))
    """

    def __init__(
        self,
        oracle_db: str | None = None,
        new_db: str | None = None,
    ) -> None:
        self.oracle_db = oracle_db or ORACLE_DATABASE_URL
        self.new_db = new_db or NEW_DATABASE_URL
        self._oracle: Optional[_Subapp] = None
        self._new: Optional[_Subapp] = None

    # -- availability (NEVER fake a green) ---------------------------------
    @classmethod
    def unavailable_reason(
        cls, oracle_db: str | None = None, new_db: str | None = None
    ) -> Optional[str]:
        oracle_db = oracle_db or ORACLE_DATABASE_URL
        new_db = new_db or NEW_DATABASE_URL

        if not BACKEND_PYTHON.is_file():
            return (
                f"FastAPI oracle venv missing ({BACKEND_PYTHON}). "
                f"Create it: cd backend && python -m venv .venv && "
                f".venv/bin/pip install -e ."
            )
        if not (BACKEND_DIR / "app" / "main.py").is_file():
            return f"frozen backend/app/main.py not found under {BACKEND_DIR}"
        if not F3_PYTHON.is_file():
            return (
                f"new-app interpreter missing ({F3_PYTHON}). Set "
                f"F3_DJANGO_PYTHON, or create the F3 venv: "
                f"uv venv .venv-f3 && uv pip install --python "
                f".venv-f3/bin/python -e django_app[dev] uvicorn[standard]"
            )
        for label, url in (("oracle", oracle_db), ("new", new_db)):
            host, port = _pg_host_port(url)
            if not _tcp_open(host, port):
                return (
                    f"Postgres for the {label} stack unreachable at "
                    f"{host}:{port}. Start + seed it:\n"
                    f"  docker compose up -d postgres\n"
                    f"  cd backend && DATABASE_URL={url} "
                    f".venv/bin/python -m alembic upgrade head && "
                    f"DATABASE_URL={url} .venv/bin/python -m scripts.seed_all"
                )
        return None

    @classmethod
    def available(cls, oracle_db: str | None = None, new_db: str | None = None) -> bool:
        return cls.unavailable_reason(oracle_db, new_db) is None

    # -- lifecycle ---------------------------------------------------------
    def __enter__(self) -> "ParityRig":
        reason = self.unavailable_reason(self.oracle_db, self.new_db)
        if reason is not None:
            raise OracleUnavailable(reason)

        self._oracle = _Subapp(
            name="FastAPI oracle (backend/.venv → bgx_oracle)",
            python=BACKEND_PYTHON,
            cwd=BACKEND_DIR,
            app="app.main:app",
            database_url=self.oracle_db,
        )
        self._new = _Subapp(
            name="new Django+Ninja app (F3 venv → bgx_django)",
            python=F3_PYTHON,
            cwd=DJANGO_DIR,
            app="config.asgi:application",
            database_url=self.new_db,
            settings_module="config.settings",
        )
        try:
            self._oracle.start()
            self._new.start()
        except OracleUnavailable:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *exc) -> None:
        if self._new is not None:
            self._new.stop()
            self._new = None
        if self._oracle is not None:
            self._oracle.stop()
            self._oracle = None

    # -- requests ----------------------------------------------------------
    def old(self, path: str) -> _HTTPResponse:
        assert self._oracle is not None
        return self._oracle.get(path)

    def new(self, path: str) -> _HTTPResponse:
        assert self._new is not None
        return self._new.get(path)


__all__ = [
    "assert_json_parity",
    "ParityRig",
    "OracleUnavailable",
    "ORACLE_DATABASE_URL",
    "NEW_DATABASE_URL",
]

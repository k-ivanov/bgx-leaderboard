"""HTTP Basic auth gate for `/api/stats` (eng-review SC-1 / N6)."""

import secrets
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .config import STATS_PASSWORD

_security = HTTPBasic(auto_error=False)


def require_stats_auth(
    credentials: Optional[HTTPBasicCredentials] = Depends(_security),
) -> None:
    """Raise 401 unless the caller supplies the configured STATS_PASSWORD.

    Dev-friendly: if ``STATS_PASSWORD`` env var is empty, auth is disabled.
    The username is not checked — any non-empty username with the correct
    password is accepted.
    """
    if not STATS_PASSWORD:
        return  # dev mode — no auth required

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": 'Basic realm="stats"'},
        )

    # Constant-time compare to mitigate timing attacks.
    password_ok = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        STATS_PASSWORD.encode("utf-8"),
    )
    if not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": 'Basic realm="stats"'},
        )

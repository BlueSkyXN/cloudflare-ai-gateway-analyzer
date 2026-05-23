"""Bearer-token authentication dependency.

When ``settings.control.auth_token`` is non-empty, every ``/api/v1/*`` route
plus ``/docs`` / ``/redoc`` / ``/openapi.json`` require ``Authorization:
Bearer <token>`` regardless of HTTP method. Loopback requests with an empty
token configured pass through unauthenticated.
"""

from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cf_aigw_analyzer.control.deps import get_settings

bearer_scheme = HTTPBearer(auto_error=False)


def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings=Depends(get_settings),
) -> None:
    """Enforce bearer authentication per :data:`config.control.auth_token`."""

    token = settings.control.auth_token
    if token is None or not token.get_secret_value():
        return

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Constant-time comparison — documented contract in docs/security-and-privacy.md.
    if not secrets.compare_digest(credentials.credentials, token.get_secret_value()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid bearer token",
        )
    _ = request  # available for future per-request audit hooks

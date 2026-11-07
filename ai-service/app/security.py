"""Internal service authentication for the FastAPI service.

The AI service is an internal dependency of the Express backend. It must not
be reachable as an unauthenticated public API. Every API router is mounted with
the dependency in this module, and the Express gateway forwards a shared secret
in the ``X-Internal-Service-Token`` header.

This is service-to-service authentication, not end-user authentication. End
users continue to authenticate against the Express API with JWTs.
"""

from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Header, HTTPException

from app.config import settings

SERVICE_TOKEN_HEADER = "X-Internal-Service-Token"


def _unauthorized(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={"error": {"code": code, "message": message, "details": {}}},
        headers={"WWW-Authenticate": "ServiceToken"},
    )


async def require_service_token(
    x_internal_service_token: Optional[str] = Header(
        default=None, alias=SERVICE_TOKEN_HEADER
    ),
) -> None:
    """Reject requests that do not present the configured service token."""

    expected = (settings.SERVICE_AUTH_TOKEN or "").strip()
    if not expected:
        # Failing closed is safer than silently exposing prediction and data
        # endpoints when the deployment forgot to configure authentication.
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "service_auth_not_configured",
                    "message": (
                        "Internal service authentication is not configured; "
                        "the API is unavailable"
                    ),
                    "details": {},
                }
            },
        )

    provided = (x_internal_service_token or "").strip()
    if not provided or not secrets.compare_digest(provided, expected):
        raise _unauthorized(
            "invalid_service_token",
            "A valid internal service token is required",
        )

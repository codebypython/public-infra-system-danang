"""Audit middleware — record mutating requests + actor."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger
from app.core.security import decode_token

logger = get_logger(__name__)

MUTATING = {"POST", "PATCH", "PUT", "DELETE"}
SKIP_PATHS = {"/api/v1/auth/login", "/api/v1/auth/refresh", "/health", "/metrics"}


class AuditMiddleware(BaseHTTPMiddleware):
    """Lightweight access audit; deep audit is per-action via ActivityLog rows."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if request.method in MUTATING and request.url.path not in SKIP_PATHS:
            user_id: UUID | None = None
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer "):
                try:
                    p = decode_token(auth.removeprefix("Bearer "))
                    user_id = UUID(p["sub"])
                except Exception:  # noqa: BLE001
                    pass
            logger.info(
                "audit.access",
                method=request.method,
                path=request.url.path,
                user_id=str(user_id) if user_id else None,
                status_code=response.status_code,
                ts=datetime.now(UTC).isoformat(),
            )
        return response

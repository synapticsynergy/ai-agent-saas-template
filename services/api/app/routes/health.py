"""Health and readiness."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.config import settings
from app.persistence.postgres import check_database
from app.persistence.s3 import check_storage
from app.schemas.common import HealthResponse
from app.version import VERSION

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness probe. Always cheap, never touches dependencies."""
    return HealthResponse(status="ok", app_env=settings.app_env, version=VERSION)


@router.get("/health/ready", response_model=HealthResponse)
async def ready(response: Response) -> HealthResponse:
    """Readiness probe. Reports each dependency separately.

    Returns 503 when a dependency is down so a load balancer or deploy gate can
    act on it, while still returning the per-check detail in the body.
    """
    checks = {"database": await check_database(), "storage": check_storage()}
    healthy = all(checks.values())

    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="ok" if healthy else "degraded",
        app_env=settings.app_env,
        version=VERSION,
        checks=checks,
    )

"""Shared response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Uniform error envelope for every mapped failure."""

    code: str = Field(description="Stable machine-readable error code.")
    message: str = Field(description="Human-readable explanation.")
    detail: dict[str, object] = Field(default_factory=dict)
    request_id: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    app_env: str
    version: str
    checks: dict[str, bool] = Field(default_factory=dict)


class CurrentUserResponse(BaseModel):
    user_id: str
    organization_id: str
    email: str
    role: str
    permissions: list[str]

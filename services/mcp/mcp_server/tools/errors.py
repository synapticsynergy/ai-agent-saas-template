"""Uniform tool error mapping.

Every tool returns either a typed result or a ``ToolError`` with a stable code.
The agent can then react to the *category* of failure — retry a timeout, give up
on a permission denial, replan on empty results — without parsing prose.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from mcp_server.api_client import ApiError
from mcp_server.context import MissingIdentity
from mcp_server.providers.base import ProviderTimeout, ProviderUnavailable


class ToolError(BaseModel):
    """A tool failure the agent is expected to handle."""

    error: str
    code: str
    retryable: bool = False
    detail: dict[str, Any] = {}


def map_exception(exc: Exception) -> ToolError:
    """Translate an exception into a typed, agent-legible tool error."""
    if isinstance(exc, ProviderTimeout):
        return ToolError(
            error="The upstream provider timed out.",
            code="provider_timeout",
            retryable=True,
        )
    if isinstance(exc, ProviderUnavailable):
        return ToolError(
            error=f"The upstream provider failed: {exc}",
            code="provider_error",
            retryable=False,
        )
    if isinstance(exc, MissingIdentity):
        return ToolError(error=str(exc), code="not_authenticated", retryable=False)
    if isinstance(exc, ApiError):
        return ToolError(
            error=exc.message,
            code=exc.code,
            # 5xx may succeed on retry; a 403 never will.
            retryable=exc.status_code >= 500,
            detail={"status_code": exc.status_code},
        )
    if isinstance(exc, ValueError):
        return ToolError(error=str(exc), code="invalid_arguments", retryable=False)

    return ToolError(error="An unexpected tool error occurred.", code="internal_error")

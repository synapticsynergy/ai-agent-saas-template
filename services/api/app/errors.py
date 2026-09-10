"""Domain exceptions.

Services raise these; the HTTP layer maps them to status codes in one place
(``app.main``). Keeping services free of ``HTTPException`` means the same
service code is reusable from the MCP tool layer and from tests.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for expected, mapped application failures."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, detail: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or {}


class NotAuthenticated(AppError):
    status_code = 401
    code = "not_authenticated"


class PermissionDenied(AppError):
    status_code = 403
    code = "permission_denied"


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_failed"


class ProviderTimeout(AppError):
    """An upstream provider did not answer in time. Retryable."""

    status_code = 504
    code = "provider_timeout"


class ProviderError(AppError):
    """An upstream provider failed in a way that is not worth retrying."""

    status_code = 502
    code = "provider_error"

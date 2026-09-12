"""Structured logging with request/run correlation.

Correlation IDs (request_id, run_id, trace_id, organization_id, user_id) are
bound to a context variable so every log line emitted while handling a request
carries them without being threaded through function signatures.
"""

from __future__ import annotations

import logging
from collections.abc import MutableMapping
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.config import settings

_SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "password",
        "secret",
        "service_token",
        "token",
        "workos_api_key",
        "x-service-token",
    }
)


def _redact(
    _logger: Any, _name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Drop values whose key suggests a credential.

    Cheap defence in depth: logs are the easiest place to leak a secret by
    accident, and the cost of over-redacting a debug field is low.
    """
    for key in list(event_dict):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "[redacted]"
    return event_dict


def configure_logging() -> None:
    renderer: structlog.typing.Processor = (
        structlog.dev.ConsoleRenderer()
        if settings.is_local
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping().get(settings.log_level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]


__all__ = ["bind_contextvars", "clear_contextvars", "configure_logging", "get_logger"]

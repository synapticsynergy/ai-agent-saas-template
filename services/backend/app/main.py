"""The deterministic application API.

This module owns CRUD, persistence, tenancy and authorization, and nothing
else. It is mounted — along with the agent and the MCP server — by ``asgi.py``,
which is the process entry point. Import it directly only in tests.

It still does not proxy the agent stream. Sharing a process is a deployment
decision; the responsibilities stayed separate. See ADR-009.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.errors import AppError
from app.logging import bind_contextvars, clear_contextvars, configure_logging, get_logger
from app.persistence.postgres import dispose_engine
from app.routes import agent_runs, health, plans, users
from app.schemas.common import ErrorResponse
from app.version import VERSION

configure_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    log.info("api.startup", app_env=settings.app_env, version=VERSION)
    if settings.is_local and settings.auth_dev_fixture:
        log.warning(
            "api.dev_fixture_auth_enabled",
            message="Requests without a bearer token resolve to the local fixture identity.",
        )
    yield
    await dispose_engine()
    log.info("api.shutdown")


app = FastAPI(
    title="AI Agent SaaS API",
    version=VERSION,
    description="Deterministic application API: persistence, tenancy and authorization.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[JSONResponse]]
) -> JSONResponse:
    """Bind correlation IDs for the duration of the request.

    ``x-request-id`` is honoured when a caller supplies one so a single id can
    follow a user action across web → agent → MCP → API.
    """
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    clear_contextvars()
    bind_contextvars(
        request_id=request_id,
        run_id=request.headers.get("x-run-id"),
        trace_id=request.headers.get("x-trace-id"),
        path=request.url.path,
        method=request.method,
    )
    request.state.request_id = request_id

    try:
        response = await call_next(request)
    finally:
        clear_contextvars()

    response.headers["x-request-id"] = request_id
    return response


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    detail: dict[str, object] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            code=code,
            message=message,
            detail=detail or {},
            request_id=getattr(request.state, "request_id", None),
        ).model_dump(),
    )


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    """Map domain exceptions to HTTP once, centrally.

    Services raise ``PermissionDenied``/``NotFound``; they never import
    ``HTTPException``. That keeps the same service code usable from MCP tools
    and from tests without an HTTP layer.
    """
    log.info(
        "api.error",
        code=exc.code,
        status_code=exc.status_code,
        message=exc.message,
    )
    return _error_response(request, exc.status_code, exc.code, exc.message, exc.detail)


def _serializable_errors(exc: RequestValidationError) -> list[dict[str, object]]:
    """Reduce Pydantic errors to a JSON-safe, client-appropriate shape.

    ``exc.errors()`` embeds the original exception object in ``ctx`` for
    validator-raised errors, which is not JSON serializable and would leak
    internals. Only location, message and type are useful to a caller.
    """
    return [
        {
            "loc": [str(part) for part in error.get("loc", ())],
            "msg": str(error.get("msg", "")),
            "type": str(error.get("type", "")),
        }
        for error in exc.errors()
    ]


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _error_response(
        request,
        422,
        "validation_failed",
        "Request payload failed validation.",
        {"errors": _serializable_errors(exc)},
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    log.exception("api.unhandled_error", error=str(exc))
    return _error_response(request, 500, "internal_error", "An unexpected error occurred.")


app.include_router(health.router)
app.include_router(users.router)
app.include_router(plans.router)
app.include_router(agent_runs.router)

"""The agent, as a mountable ASGI application.

  POST /invocations  — run the agent, streaming AG-UI events as SSE
  GET  /ping         — health probe

``POST /`` is the same handler, so CopilotKit's HttpAgent can point at the
mount root without a path rewrite.

Mounted at ``/agent`` by ``asgi.py``, which is the process entry point; set the
web app's ``AGENT_BASE_URL`` to that prefix. Nothing here assumes the mount
point, so moving it — or splitting this back into its own service — is
configuration rather than a code change.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import structlog
from ag_ui.core import BaseEvent, RunAgentInput
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from agent_app.config import settings
from agent_app.runner import context_from_input, latest_user_message, run
from agent_app.streaming import to_sse

logging.basicConfig(level=settings.log_level.upper())
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.dev.ConsoleRenderer()
        if settings.is_local
        else structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger(__name__)

app = FastAPI(title="Plan My Evening Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_local else [],
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


def _bearer_token(request: Request) -> str | None:
    """Extract the caller's identity assertion.

    The agent forwards this to its tools unchanged and never mints one of its
    own. If it is absent, discovery still works and anything touching tenant
    data is refused downstream — by the API, not here.
    """
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    return token if scheme.lower() == "bearer" and token else None


async def _events(payload: RunAgentInput, access_token: str | None) -> AsyncIterator[BaseEvent]:
    context = context_from_input(payload, access_token)
    message = latest_user_message(payload)

    structlog.contextvars.bind_contextvars(run_id=context.run_id, thread_id=context.thread_id)
    log.info(
        "agent.run_started",
        has_identity=access_token is not None,
        interpreter=context.interpreter.name,
    )

    async for event in run(message, context):
        yield event


@app.post("/invocations")
@app.post("/")
async def invocations(request: Request) -> Any:
    """Run the agent, streaming AG-UI events back as SSE."""
    body = await request.json()

    try:
        payload = RunAgentInput.model_validate(body)
    except Exception as exc:
        log.warning("agent.invalid_input", error=str(exc))
        return JSONResponse(
            status_code=422,
            content={"code": "invalid_input", "message": "Request is not a valid AG-UI input."},
        )

    return EventSourceResponse(
        to_sse(_events(payload, _bearer_token(request))),
        # LF separators, not the CRLF sse-starlette defaults to. Both are valid
        # SSE, but the AG-UI client splits frames on "\n\n", so CRLF frames
        # never split and the whole stream arrives as one unparseable blob.
        sep="\n",
        # Keep-alive comments would arrive mid-run; the agent's own events are
        # frequent enough that the connection never idles long enough to matter.
        ping=15,
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/ping")
@app.get("/health")
async def ping() -> dict[str, str]:
    """Health probe."""
    return {
        "status": "Healthy",
        "agent": settings.agent_name,
        "model_provider": settings.agent_model_provider,
    }


def main() -> None:  # pragma: no cover - process entry point
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.agent_port)  # noqa: S104


if __name__ == "__main__":  # pragma: no cover
    main()

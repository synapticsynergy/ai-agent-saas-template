"""Composed ASGI application: the API, the agent and the MCP server in one process.

Run with ``uvicorn asgi:app`` (or ``make backend-dev``).

    /plans, /agent-runs, /users/me, /health   the deterministic application API
    /agent/invocations                        the agent, streaming AG-UI over SSE
    /mcp                                      the MCP server, streamable HTTP

These were three separately deployed services. They are still three independent
packages — ``app``, ``agent_app`` and ``mcp_server`` — and none imports another
except through HTTP or the shared contracts. Splitting them apart again is a
deployment change, not a refactor. See ADR-009, which supersedes ADR-001.

Why one process: the agent streams SSE, which wants a long-lived connection
rather than a Lambda invocation, and the MCP server has to be reachable at a
stable public URL for any MCP client to connect. Once something is running
continuously, a second and third ASGI app on it are free.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from mcp.server.transport_security import TransportSecuritySettings

from agent_app.asgi import app as agent_app
from app.main import app
from mcp_server.config import settings as mcp_settings
from mcp_server.server import server

# The MCP app owns a session manager that is started by its own lifespan. A
# mounted sub-application's lifespan is never run by the parent, so the parent
# has to run it explicitly — without this, every MCP request fails with the
# session manager reporting it was never initialised.
# `streamable_http_path="/"` because this app is mounted, not served at the
# root. The default is "/mcp", which under a "/mcp" mount would serve the
# endpoint at "/mcp/mcp" — reachable, but not the URL anyone would configure.
mcp_app = server.streamable_http_app(
    streamable_http_path="/",
    # DNS-rebinding protection stays on; the deployment names its own hostname.
    # Left at the default (an empty allow-list) every request is answered 421.
    transport_security=TransportSecuritySettings(allowed_hosts=mcp_settings.allowed_hosts),
)

app.mount("/mcp", mcp_app)
app.mount("/agent", agent_app)

_api_lifespan = app.router.lifespan_context


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with _api_lifespan(_app):
        async with mcp_app.router.lifespan_context(mcp_app):
            yield


app.router.lifespan_context = _lifespan

__all__ = ["app"]

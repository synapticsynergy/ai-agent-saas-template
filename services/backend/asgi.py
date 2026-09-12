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
from mcp.server.streamable_http_manager import StreamableHTTPASGIApp
from mcp.server.transport_security import TransportSecuritySettings
from starlette.routing import Route

from agent_app.asgi import app as agent_app
from app.main import app
from mcp_server.config import settings as mcp_settings
from mcp_server.server import server

# The MCP server's session manager is started by the MCP app's own lifespan. A
# sub-application's lifespan is never run by its parent, so the parent has to
# run it explicitly — without this, every MCP request fails with the session
# manager reporting it was never initialised.
mcp_app = server.streamable_http_app(
    # DNS-rebinding protection stays on; the deployment names its own hostname.
    # With the default empty allow-list, every request is answered 421.
    transport_security=TransportSecuritySettings(allowed_hosts=mcp_settings.allowed_hosts),
)

# Registered as a plain route rather than `app.mount("/mcp", mcp_app)`, because
# a Starlette mount redirects the bare "/mcp" to "/mcp/" with a 307. That is
# the exact URL people paste into an MCP client config, and a redirect there is
# at best untidy and at worst unfollowed. The MCP SDK registers its own ASGI
# app the same way — around the same session manager — so this mirrors it
# rather than working around it.
#
# It is easy to miss: TestClient follows redirects by default, so this looked
# correct under test and only showed up against a real HTTP client.
app.router.routes.append(
    Route(
        "/mcp",
        endpoint=StreamableHTTPASGIApp(server.session_manager),
        methods=["GET", "POST", "DELETE"],
    )
)

app.mount("/agent", agent_app)

_api_lifespan = app.router.lifespan_context


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with _api_lifespan(_app):
        async with mcp_app.router.lifespan_context(mcp_app):
            yield


app.router.lifespan_context = _lifespan

__all__ = ["app"]

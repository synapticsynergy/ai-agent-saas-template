"""AWS Lambda entry point for the MCP server.

Lambda gives no session affinity across invocations, so the streamable-HTTP
transport runs stateless: each request carries everything the server needs and
no MCP session state is retained between invocations.
"""

from __future__ import annotations

from mangum import Mangum

from mcp_server.server import server

app = server.streamable_http_app(stateless_http=True, json_response=True)
handler = Mangum(app, lifespan="off")

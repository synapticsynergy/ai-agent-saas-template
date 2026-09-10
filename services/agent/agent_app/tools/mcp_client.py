"""MCP client for the agent's tool layer.

The agent reaches its tools over MCP, through AgentCore Gateway when one is
configured and the MCP server directly otherwise (``settings.tools_url``).

The caller's bearer assertion is forwarded on every call. The agent does not
hold a credential of its own for tenant operations — it acts strictly on behalf
of the authenticated user, and the API re-verifies that assertion.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
import structlog
from saas_contracts.tools import Event, Place, Route

from agent_app.config import settings

log = structlog.get_logger(__name__)

PROTOCOL_VERSION = "2025-06-18"


class ToolCallError(Exception):
    """A tool returned an error, or the transport failed."""

    def __init__(self, message: str, *, code: str = "tool_error", retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class McpToolClient:
    """Minimal streamable-HTTP MCP client.

    Deliberately small: the agent needs ``initialize`` and ``tools/call``, and a
    hand-rolled client keeps the request/response path — and the header
    forwarding that carries identity — explicit and easy to test.
    """

    def __init__(
        self, url: str | None = None, access_token: str | None = None, run_id: str | None = None
    ) -> None:
        self._url = url or settings.tools_url
        self._access_token = access_token
        self._run_id = run_id
        self._session_id: str | None = None
        self._next_id = 0

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        if self._run_id:
            headers["x-run-id"] = self._run_id
        if self._session_id:
            headers["mcp-session-id"] = self._session_id
        return headers

    async def __aenter__(self) -> McpToolClient:
        self._client = httpx.AsyncClient(timeout=settings.tool_timeout_seconds)
        await self._initialize()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._client.aclose()

    async def _initialize(self) -> None:
        response = await self._post(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": settings.agent_name, "version": "0.1.0"},
            },
        )
        self._session_id = response.headers.get("mcp-session-id")
        await self._notify("notifications/initialized")

    async def _post(self, method: str, params: dict[str, Any]) -> httpx.Response:
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params}
        try:
            return await self._client.post(self._url, json=payload, headers=self._headers())
        except httpx.TimeoutException as exc:
            raise ToolCallError(
                f"MCP call {method} timed out.", code="tool_timeout", retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise ToolCallError(
                f"MCP transport error: {exc}", code="tool_unreachable", retryable=True
            ) from exc

    async def _notify(self, method: str) -> None:
        await self._client.post(
            self._url,
            json={"jsonrpc": "2.0", "method": method},
            headers=self._headers(),
        )

    async def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Invoke a tool and return its structured content."""
        response = await self._post("tools/call", {"name": name, "arguments": arguments})
        message = _parse_jsonrpc(response.text)

        if "error" in message:
            error = message["error"]
            raise ToolCallError(
                str(error.get("message", "Tool call failed.")),
                code=str(error.get("code", "tool_error")),
            )

        result = message.get("result", {})
        structured = _unwrap(result.get("structuredContent") or {})

        # A tool that returns a ToolError reports it as structured content, not
        # as a JSON-RPC error, so the agent can react to the category.
        if "code" in structured and "error" in structured:
            raise ToolCallError(
                str(structured["error"]),
                code=str(structured["code"]),
                retryable=bool(structured.get("retryable", False)),
            )

        if result.get("isError"):
            raise ToolCallError(_text_content(result) or "Tool call failed.")

        return structured

    # --- typed convenience wrappers ---------------------------------------

    async def search_places(self, **kwargs: Any) -> list[Place]:
        data = await self.call("search_places", _clean(kwargs))
        return [Place.model_validate(item) for item in data.get("items", [])]

    async def search_events(self, **kwargs: Any) -> list[Event]:
        payload = _clean(kwargs)
        for key in ("start_after", "start_before"):
            if isinstance(payload.get(key), datetime):
                payload[key] = payload[key].isoformat()
        data = await self.call("search_events", payload)
        return [Event.model_validate(item) for item in data.get("items", [])]

    async def build_route(self, **kwargs: Any) -> Route:
        return Route.model_validate(await self.call("build_route", _clean(kwargs)))

    async def save_plan(
        self, itinerary: dict[str, Any], idempotency_key: str | None
    ) -> dict[str, Any]:
        return await self.call(
            "save_plan", _clean({"itinerary": itinerary, "idempotency_key": idempotency_key})
        )


def _unwrap(structured: dict[str, Any]) -> dict[str, Any]:
    """Unwrap the MCP structured-content envelope.

    The SDK wraps a tool's return value under a single ``result`` key when the
    declared output type is not an open object. Unwrapping here keeps that
    detail out of every call site.
    """
    if set(structured) == {"result"} and isinstance(structured["result"], dict):
        inner: dict[str, Any] = structured["result"]
        return inner
    return structured


def _clean(kwargs: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in kwargs.items() if value is not None}


def _parse_jsonrpc(body: str) -> dict[str, Any]:
    """Read a JSON-RPC message from a plain JSON or SSE response body."""
    import json

    text = body.strip()
    if text.startswith("{"):
        return json.loads(text)  # type: ignore[no-any-return]

    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())  # type: ignore[no-any-return]

    raise ToolCallError("MCP response contained no JSON-RPC message.")


def _text_content(result: dict[str, Any]) -> str:
    parts = [item.get("text", "") for item in result.get("content", []) if isinstance(item, dict)]
    return " ".join(part for part in parts if part)

"""MCP server integration.

Exercises the real streamable-HTTP transport against a live server, rather than
calling the tool functions directly (which the contract tests already do). What
is under test here is the protocol boundary: session handshake, structured
content shape, and that an unauthenticated caller cannot write tenant data.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_VERSION = "2025-06-18"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def mcp_url() -> Iterator[str]:
    """Start the real MCP server on a free port for the duration of the module."""
    port = _free_port()
    env = {
        **os.environ,
        "APP_ENV": "local",
        "MCP_HOST": "127.0.0.1",
        "MCP_PORT": str(port),
        "PLACES_PROVIDER": "fixture",
        "EVENTS_PROVIDER": "fixture",
    }
    # The outer suite runs in the API's virtualenv; uv must not inherit it.
    env.pop("VIRTUAL_ENV", None)

    # Launched through uv in the MCP server's own project: it is a separate
    # deployable with its own dependency set (the Strands SDK pins mcp<2.2
    # while this server needs mcp>=2.2), so it cannot share this interpreter.
    process = subprocess.Popen(
        [
            "uv",
            "run",
            "--project",
            str(REPO_ROOT / "services" / "mcp"),
            "python",
            "server.py",
        ],
        cwd=REPO_ROOT / "services" / "mcp",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    url = f"http://127.0.0.1:{port}/mcp"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read().decode() if process.stdout else ""
            raise RuntimeError(f"MCP server exited during startup:\n{output}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.3)
    else:
        process.kill()
        raise RuntimeError("MCP server did not start within 30s")

    try:
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


class McpClient:
    """The smallest client that exercises the real transport."""

    def __init__(self, url: str, token: str | None = None) -> None:
        self.url = url
        self.token = token
        self.session_id: str | None = None
        self._id = 0
        self._http = httpx.Client(timeout=20)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        return headers

    def initialize(self) -> dict[str, Any]:
        response = self._post(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "integration-test", "version": "1"},
            },
        )
        self.session_id = response.headers.get("mcp-session-id")
        self._http.post(
            self.url,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers=self._headers(),
        )
        return _message(response.text)["result"]

    def _post(self, method: str, params: dict[str, Any]) -> httpx.Response:
        self._id += 1
        return self._http.post(
            self.url,
            json={"jsonrpc": "2.0", "id": self._id, "method": method, "params": params},
            headers=self._headers(),
        )

    def list_tools(self) -> list[dict[str, Any]]:
        return _message(self._post("tools/list", {}).text)["result"]["tools"]

    def list_resources(self) -> list[dict[str, Any]]:
        return _message(self._post("resources/list", {}).text)["result"]["resources"]

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = _message(
            self._post("tools/call", {"name": name, "arguments": arguments}).text
        )["result"]
        structured = result.get("structuredContent") or {}
        if set(structured) == {"result"} and isinstance(structured["result"], dict):
            return structured["result"]
        return structured

    def close(self) -> None:
        self._http.close()


def _message(body: str) -> dict[str, Any]:
    text = body.strip()
    if text.startswith("{"):
        return json.loads(text)
    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    raise AssertionError(f"No JSON-RPC message in response: {body[:200]}")


@pytest.fixture
def client(mcp_url: str) -> Iterator[McpClient]:
    mcp = McpClient(mcp_url)
    mcp.initialize()
    yield mcp
    mcp.close()


class TestHandshake:
    def test_the_server_advertises_itself(self, mcp_url: str) -> None:
        mcp = McpClient(mcp_url)
        result = mcp.initialize()

        assert result["serverInfo"]["name"] == "plan-my-evening"
        assert result["protocolVersion"]
        assert mcp.session_id
        mcp.close()


class TestToolDiscovery:
    def test_every_reference_tool_is_exposed(self, client: McpClient) -> None:
        names = {tool["name"] for tool in client.list_tools()}
        assert {
            "search_places",
            "search_events",
            "get_place_details",
            "build_route",
            "save_plan",
        } <= names

    def test_tool_schemas_are_flat(self, client: McpClient) -> None:
        """A model picks arguments far more reliably from a flat schema."""
        search = next(t for t in client.list_tools() if t["name"] == "search_places")
        properties = set(search["inputSchema"]["properties"])

        assert {"latitude", "longitude", "category"} <= properties
        assert "payload" not in properties

    def test_the_mcp_app_resource_is_published(self, client: McpClient) -> None:
        resources = {str(r["uri"]): r for r in client.list_resources()}

        assert "ui://itinerary/map" in resources
        assert resources["ui://itinerary/map"]["mimeType"].startswith("text/html")


class TestToolsOverTheWire:
    def test_search_places_returns_structured_content(self, client: McpClient) -> None:
        result = client.call(
            "search_places",
            {"latitude": 45.5231, "longitude": -122.6765, "category": "dinner"},
        )

        assert result["total"] > 0
        assert result["provider"] == "fixture"
        assert all("latitude" in item for item in result["items"])

    def test_search_events_respects_the_time_window(self, client: McpClient) -> None:
        start = datetime(2030, 6, 1, 18, 0, tzinfo=UTC)
        result = client.call(
            "search_events",
            {
                "latitude": 45.5231,
                "longitude": -122.6765,
                "start_after": start.isoformat(),
                "start_before": (start + timedelta(hours=6)).isoformat(),
            },
        )

        assert result["total"] > 0

    def test_build_route_measures_the_walk(self, client: McpClient) -> None:
        result = client.call(
            "build_route",
            {
                "stops": [
                    {"latitude": 45.5219, "longitude": -122.6820},
                    {"latitude": 45.5245, "longitude": -122.6791},
                ],
                "names": ["Dinner", "Music"],
            },
        )

        assert result["total_distance_km"] > 0
        assert len(result["legs"]) == 1


class TestAuthorizationOverTheWire:
    def test_save_plan_is_refused_without_an_identity(self, client: McpClient) -> None:
        """No bearer token means no tenant write, whatever the agent decided."""
        start = datetime(2030, 6, 1, 19, 0, tzinfo=UTC)
        result = client.call(
            "save_plan",
            {
                "itinerary": {
                    "title": "Unauthenticated evening",
                    "start_time": start.isoformat(),
                    "estimated_cost": 40.0,
                    "stops": [
                        {
                            "name": "Dinner",
                            "category": "dinner",
                            "start_time": start.isoformat(),
                            "end_time": (start + timedelta(hours=1)).isoformat(),
                            "latitude": 45.52,
                            "longitude": -122.68,
                            "estimated_cost": 40.0,
                            "reason": "test",
                        }
                    ],
                }
            },
        )

        assert result["code"] == "not_authenticated"
        assert result["retryable"] is False

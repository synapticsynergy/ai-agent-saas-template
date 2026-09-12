"""Client for the deterministic application API.

Tools that touch tenant data go through here rather than reaching into a
database. That keeps one implementation of authorization, tenant scoping and
validation — the API's — and means an MCP tool cannot accidentally acquire
wider access than a normal user of the product has.
"""

from __future__ import annotations

from typing import Any

import httpx
from saas_contracts.plan import PlanCreate, PlanRead

from mcp_server.config import settings
from mcp_server.context import CallerIdentity


class ApiError(Exception):
    """A mapped failure from the application API."""

    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


async def _request(
    method: str, path: str, identity: CallerIdentity, *, json: dict[str, Any] | None = None
) -> dict[str, Any]:
    async with httpx.AsyncClient(
        base_url=settings.api_base_url, timeout=settings.provider_timeout_seconds
    ) as client:
        try:
            response = await client.request(
                method, path, json=json, headers=identity.forward_headers
            )
        except httpx.TimeoutException as exc:
            raise ApiError("api_timeout", "The application API timed out.", 504) from exc
        except httpx.HTTPError as exc:
            raise ApiError(
                "api_unreachable", f"The application API is unreachable: {exc}", 502
            ) from exc

    if response.is_success:
        data: dict[str, Any] = response.json() if response.content else {}
        return data

    # The API returns a uniform error envelope; surface its code so the agent
    # can distinguish "you are not allowed" from "the service is down".
    try:
        body = response.json()
        code = str(body.get("code", "api_error"))
        message = str(body.get("message", response.text))
    except ValueError:
        code, message = "api_error", response.text

    raise ApiError(code, message, response.status_code)


async def create_plan(identity: CallerIdentity, payload: PlanCreate) -> PlanRead:
    data = await _request(
        "POST", "/plans", identity, json=payload.model_dump(mode="json", exclude_none=True)
    )
    return PlanRead.model_validate(data)


async def get_plan(identity: CallerIdentity, plan_id: str) -> PlanRead:
    data = await _request("GET", f"/plans/{plan_id}", identity)
    return PlanRead.model_validate(data)

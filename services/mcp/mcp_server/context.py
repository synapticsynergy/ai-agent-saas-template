"""Caller identity for MCP tool invocations.

Identity reaches the MCP server as an ``Authorization: Bearer <jwt>`` header on
the streamable-HTTP request, forwarded from the agent, which received it from
the Next.js server, which got it from the verified WorkOS session.

This module does **not** decide authorization. It extracts the assertion and
passes it on to the deterministic API, which verifies the signature and applies
the permission check. That is deliberate: the MCP server is a capability
surface, not a security boundary, and duplicating the decision here would create
two places that could disagree.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

TOKEN_HEADER = "authorization"  # noqa: S105 - header name, not a credential
RUN_ID_HEADER = "x-run-id"
REQUEST_ID_HEADER = "x-request-id"


class MissingIdentity(Exception):
    """No caller identity was supplied for a tool that requires one."""

    code = "not_authenticated"


@dataclass(frozen=True, slots=True)
class CallerIdentity:
    access_token: str
    run_id: str | None = None
    request_id: str | None = None

    @property
    def forward_headers(self) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.access_token}"}
        if self.run_id:
            headers[RUN_ID_HEADER] = self.run_id
        if self.request_id:
            headers[REQUEST_ID_HEADER] = self.request_id
        return headers


def identity_from_headers(headers: dict[str, Any] | None) -> CallerIdentity | None:
    """Extract the caller's bearer assertion, or None when absent.

    Discovery tools (searching places, building a route) do not need identity —
    they touch no tenant data and have no side effects. Tools that read or write
    tenant data call :func:`require_identity` instead.
    """
    if not headers:
        return None

    lowered = {str(k).lower(): v for k, v in headers.items()}
    raw = str(lowered.get(TOKEN_HEADER, ""))
    scheme, _, token = raw.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    return CallerIdentity(
        access_token=token,
        run_id=_first(lowered.get(RUN_ID_HEADER)),
        request_id=_first(lowered.get(REQUEST_ID_HEADER)),
    )


def require_identity(headers: dict[str, Any] | None) -> CallerIdentity:
    identity = identity_from_headers(headers)
    if identity is None:
        raise MissingIdentity(
            "This tool acts on tenant data and requires an authenticated caller. "
            "No bearer token was forwarded with the MCP request."
        )
    return identity


def _first(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list | tuple):
        return str(value[0]) if value else None
    return str(value)

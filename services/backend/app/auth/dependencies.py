"""FastAPI dependencies for identity and authorization."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.params import Depends as DependsMarker

from app.auth.permissions import Permission, Principal, require_permission
from app.auth.workos import dev_fixture_principal, principal_from_access_token
from app.config import settings
from app.errors import NotAuthenticated


async def get_principal(request: Request) -> Principal:
    """Resolve the authenticated principal for the current request."""
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")

    if scheme.lower() == "bearer" and token:
        # The fixture token is only ever accepted when both guards hold; the
        # check lives in dev_fixture_principal() so it cannot drift from here.
        if settings.auth_dev_fixture and token == settings.auth_dev_fixture_token:
            return dev_fixture_principal()
        return principal_from_access_token(token)

    if settings.is_local and settings.auth_dev_fixture:
        return dev_fixture_principal()

    raise NotAuthenticated("Missing bearer token.")


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


def requires(permission: Permission) -> DependsMarker:
    """Route dependency enforcing a single permission.

    Usage::

        @router.post("/plans", dependencies=[requires(PLANS_WRITE)])

    The service layer re-checks the same permission. That duplication is
    deliberate: the route guard gives an early, cheap 403, and the service guard
    means a caller that reaches the service another way (an MCP tool, a
    background job, a test) cannot bypass it.
    """

    async def _dependency(principal: CurrentPrincipal) -> None:
        require_permission(principal, permission)

    marker: DependsMarker = Depends(_dependency)
    return marker

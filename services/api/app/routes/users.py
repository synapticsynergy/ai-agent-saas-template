"""Identity introspection.

The web app calls this to render the current organization and to decide which
actions to offer. The UI hiding a button is a usability choice, not a security
control — the API enforces the same permissions regardless.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.auth.dependencies import CurrentPrincipal
from app.schemas.common import CurrentUserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=CurrentUserResponse)
async def me(principal: CurrentPrincipal) -> CurrentUserResponse:
    return CurrentUserResponse(
        user_id=principal.user_id,
        organization_id=principal.organization_id,
        email=principal.email,
        role=principal.role,
        permissions=sorted(principal.permissions),
    )

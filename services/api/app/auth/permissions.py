"""Permission model and the authenticated principal.

Application code authorizes on *permission slugs*, never on role names. Roles
exist only as a convenient way for an administrator to assign a permission set
in WorkOS; adding a role must never require touching authorization logic.

Nothing in this module trusts model output. A ``Principal`` is only ever
constructed from a verified WorkOS session (or, locally, from the explicitly
isolated development fixture).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from app.errors import PermissionDenied

# ---------------------------------------------------------------------------
# Permission catalogue
# ---------------------------------------------------------------------------

Permission = str

PLANS_READ: Final[Permission] = "plans:read"
PLANS_WRITE: Final[Permission] = "plans:write"
PLANS_DELETE: Final[Permission] = "plans:delete"
AGENTS_RUN: Final[Permission] = "agents:run"
PREFERENCES_READ: Final[Permission] = "preferences:read"
PREFERENCES_WRITE: Final[Permission] = "preferences:write"
ORG_MANAGE: Final[Permission] = "org:manage"

ALL_PERMISSIONS: Final[frozenset[Permission]] = frozenset(
    {
        PLANS_READ,
        PLANS_WRITE,
        PLANS_DELETE,
        AGENTS_RUN,
        PREFERENCES_READ,
        PREFERENCES_WRITE,
        ORG_MANAGE,
    }
)

# Default role → permission mapping. In a WorkOS-configured environment the
# permissions come from the session itself; this mapping is the fallback used
# for local development, seeds and tests, and documents the intended defaults.
ROLE_PERMISSIONS: Final[dict[str, frozenset[Permission]]] = {
    "viewer": frozenset({PLANS_READ, PREFERENCES_READ}),
    "member": frozenset(
        {
            PLANS_READ,
            PLANS_WRITE,
            AGENTS_RUN,
            PREFERENCES_READ,
            PREFERENCES_WRITE,
        }
    ),
    "admin": ALL_PERMISSIONS,
}


def permissions_for_role(role: str) -> frozenset[Permission]:
    """Default permissions for a role. Unknown roles get nothing."""
    return ROLE_PERMISSIONS.get(role, frozenset())


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Principal:
    """The authenticated actor for one request.

    ``organization_id`` is the tenant boundary. Every tenant-scoped query in the
    service layer takes it from here and never from request or model input.
    """

    user_id: str
    organization_id: str
    email: str = ""
    role: str = ""
    permissions: frozenset[Permission] = field(default_factory=frozenset)

    def has(self, permission: Permission) -> bool:
        return permission in self.permissions

    def require(self, permission: Permission) -> None:
        require_permission(self, permission)


def has_permission(principal: Principal, permission: Permission) -> bool:
    return principal.has(permission)


def require_permission(principal: Principal, permission: Permission) -> None:
    """Raise :class:`PermissionDenied` unless the principal holds ``permission``.

    This is the single authorization primitive. HTTP routes, service methods and
    MCP tools all funnel through it, so authorization can be tested without an
    HTTP client and without a model.
    """
    if permission not in ALL_PERMISSIONS:
        raise ValueError(f"Unknown permission: {permission!r}")

    if permission not in principal.permissions:
        raise PermissionDenied(
            f"Missing required permission: {permission}",
            detail={"required_permission": permission},
        )

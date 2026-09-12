"""Permission helper tests.

These run without a database, an HTTP client or a model. Authorization must be
verifiable in isolation.
"""

from __future__ import annotations

import pytest

from app.auth.permissions import (
    AGENTS_RUN,
    ALL_PERMISSIONS,
    ORG_MANAGE,
    PLANS_DELETE,
    PLANS_READ,
    PLANS_WRITE,
    ROLE_PERMISSIONS,
    has_permission,
    permissions_for_role,
    require_permission,
)
from app.errors import PermissionDenied
from tests.api.conftest import make_principal


class TestRoleDefaults:
    def test_viewer_can_read_but_not_write(self) -> None:
        viewer = make_principal(role="viewer")
        assert has_permission(viewer, PLANS_READ)
        assert not has_permission(viewer, PLANS_WRITE)
        assert not has_permission(viewer, AGENTS_RUN)

    def test_member_can_write_and_run_agents(self) -> None:
        member = make_principal(role="member")
        assert has_permission(member, PLANS_READ)
        assert has_permission(member, PLANS_WRITE)
        assert has_permission(member, AGENTS_RUN)

    def test_member_cannot_manage_the_organization(self) -> None:
        assert not has_permission(make_principal(role="member"), ORG_MANAGE)

    def test_admin_holds_every_permission(self) -> None:
        assert make_principal(role="admin").permissions == ALL_PERMISSIONS

    def test_unknown_role_grants_nothing(self) -> None:
        assert permissions_for_role("superuser") == frozenset()
        assert make_principal(role="superuser").permissions == frozenset()

    def test_role_defaults_only_reference_known_permissions(self) -> None:
        for role, permissions in ROLE_PERMISSIONS.items():
            unknown = permissions - ALL_PERMISSIONS
            assert not unknown, f"role {role} references unknown permissions: {unknown}"


class TestRequirePermission:
    def test_allows_when_permission_present(self) -> None:
        require_permission(make_principal(role="member"), PLANS_WRITE)

    def test_denies_when_permission_absent(self) -> None:
        with pytest.raises(PermissionDenied) as exc:
            require_permission(make_principal(role="viewer"), PLANS_WRITE)
        assert exc.value.detail["required_permission"] == PLANS_WRITE
        assert exc.value.status_code == 403

    def test_rejects_a_permission_that_does_not_exist(self) -> None:
        """A typo'd slug must fail loudly, not silently deny (or silently allow)."""
        with pytest.raises(ValueError, match="Unknown permission"):
            require_permission(make_principal(role="admin"), "plans:writ")

    def test_explicit_permission_set_overrides_role_defaults(self) -> None:
        """Permissions come from the session, so a role name cannot widen them."""
        principal = make_principal(role="admin", permissions={PLANS_READ})
        require_permission(principal, PLANS_READ)
        with pytest.raises(PermissionDenied):
            require_permission(principal, PLANS_DELETE)

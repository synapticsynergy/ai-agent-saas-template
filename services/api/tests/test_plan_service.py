"""Plan service tests: authorization and tenant isolation."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import Principal
from app.errors import NotFound, PermissionDenied
from app.schemas.plan import PlanUpdate
from app.services import plan_service
from tests.conftest import sample_plan


class TestAuthorization:
    async def test_viewer_cannot_create_a_plan(
        self, session: AsyncSession, viewer: Principal
    ) -> None:
        with pytest.raises(PermissionDenied):
            await plan_service.create_plan(session, viewer, sample_plan())

    async def test_member_can_create_a_plan(self, session: AsyncSession, member: Principal) -> None:
        plan = await plan_service.create_plan(session, member, sample_plan())
        assert plan.id
        assert plan.created_by_user_id == member.user_id
        assert len(plan.stops) == 2

    async def test_viewer_can_read_plans(
        self, session: AsyncSession, member: Principal, viewer: Principal
    ) -> None:
        await plan_service.create_plan(session, member, sample_plan())
        plans, total = await plan_service.list_plans(session, viewer)
        assert total == 1
        assert len(plans) == 1

    async def test_member_cannot_delete_a_plan(
        self, session: AsyncSession, member: Principal
    ) -> None:
        plan = await plan_service.create_plan(session, member, sample_plan())
        with pytest.raises(PermissionDenied):
            await plan_service.delete_plan(session, member, plan.id)

    async def test_admin_can_delete_a_plan(
        self, session: AsyncSession, member: Principal, admin: Principal
    ) -> None:
        plan = await plan_service.create_plan(session, member, sample_plan())
        await plan_service.delete_plan(session, admin, plan.id)
        _, total = await plan_service.list_plans(session, admin)
        assert total == 0


class TestTenantIsolation:
    async def test_plan_is_stamped_with_the_principals_organization(
        self, session: AsyncSession, member: Principal
    ) -> None:
        plan = await plan_service.create_plan(session, member, sample_plan())
        assert plan.organization_id == member.organization_id

    async def test_another_organization_cannot_read_the_plan(
        self, session: AsyncSession, member: Principal, other_org_member: Principal
    ) -> None:
        plan = await plan_service.create_plan(session, member, sample_plan())

        # NotFound rather than PermissionDenied: a 403 would confirm the id exists.
        with pytest.raises(NotFound):
            await plan_service.get_plan(session, other_org_member, plan.id)

    async def test_another_organization_sees_an_empty_list(
        self, session: AsyncSession, member: Principal, other_org_member: Principal
    ) -> None:
        await plan_service.create_plan(session, member, sample_plan())
        plans, total = await plan_service.list_plans(session, other_org_member)
        assert plans == []
        assert total == 0

    async def test_another_organization_cannot_update_the_plan(
        self, session: AsyncSession, member: Principal, other_org_member: Principal
    ) -> None:
        plan = await plan_service.create_plan(session, member, sample_plan())
        with pytest.raises(NotFound):
            await plan_service.update_plan(
                session, other_org_member, plan.id, PlanUpdate(title="Hijacked")
            )

    async def test_organization_id_in_the_payload_is_ignored(
        self, session: AsyncSession, member: Principal
    ) -> None:
        """A model that invents an organization_id cannot change the tenant.

        PlanCreate has no such field, so an extra key is dropped at validation
        and the tenant still comes from the verified principal.
        """
        from app.schemas.plan import PlanCreate

        payload = PlanCreate.model_validate(
            sample_plan().model_dump() | {"organization_id": "org_attacker"}
        )
        plan = await plan_service.create_plan(session, member, payload)
        assert plan.organization_id == member.organization_id


class TestIdempotency:
    async def test_repeated_save_with_the_same_key_returns_one_plan(
        self, session: AsyncSession, member: Principal
    ) -> None:
        payload = sample_plan()
        payload.idempotency_key = "tool_call_abc123"

        first = await plan_service.create_plan(session, member, payload)
        second = await plan_service.create_plan(session, member, payload)

        assert first.id == second.id
        _, total = await plan_service.list_plans(session, member)
        assert total == 1

    async def test_different_keys_create_separate_plans(
        self, session: AsyncSession, member: Principal
    ) -> None:
        first_payload = sample_plan("First")
        first_payload.idempotency_key = "call_1"
        second_payload = sample_plan("Second")
        second_payload.idempotency_key = "call_2"

        await plan_service.create_plan(session, member, first_payload)
        await plan_service.create_plan(session, member, second_payload)

        _, total = await plan_service.list_plans(session, member)
        assert total == 2

    async def test_idempotency_key_does_not_leak_across_organizations(
        self, session: AsyncSession, member: Principal, other_org_member: Principal
    ) -> None:
        payload = sample_plan()
        payload.idempotency_key = "shared_key"

        mine = await plan_service.create_plan(session, member, payload)
        theirs = await plan_service.create_plan(session, other_org_member, payload)

        assert mine.id != theirs.id


class TestUpdate:
    async def test_replacing_stops_recomputes_the_estimated_cost(
        self, session: AsyncSession, member: Principal
    ) -> None:
        plan = await plan_service.create_plan(session, member, sample_plan())
        cheaper = sample_plan().stops
        cheaper[0].estimated_cost = 10.0
        cheaper[1].estimated_cost = 5.0

        updated = await plan_service.update_plan(
            session, member, plan.id, PlanUpdate(stops=cheaper)
        )
        assert updated.estimated_cost == 15.0
        assert [s.position for s in updated.stops] == [0, 1]

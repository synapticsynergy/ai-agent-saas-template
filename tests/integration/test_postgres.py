"""Tenant isolation against real Postgres.

The unit suite runs these same services against SQLite. This suite re-runs the
tenancy guarantees against the database the product actually deploys on, where
index behaviour, constraint names and type coercion can differ.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.auth.permissions import Principal
from app.errors import NotFound, PermissionDenied
from app.services import plan_service
from saas_contracts.plan import PlanCreate, PlanStopCreate
from sqlalchemy.ext.asyncio import AsyncSession

START = datetime(2030, 6, 1, 19, 0, tzinfo=UTC)


def payload(title: str = "Integration evening", key: str | None = None) -> PlanCreate:
    return PlanCreate(
        title=title,
        start_time=START,
        estimated_cost=64.0,
        estimated_walk_distance_km=1.4,
        latitude=45.5231,
        longitude=-122.6765,
        idempotency_key=key,
        stops=[
            PlanStopCreate(
                name="Dinner",
                category="dinner",
                start_time=START,
                end_time=START + timedelta(hours=1, minutes=30),
                latitude=45.5219,
                longitude=-122.6820,
                estimated_cost=42.0,
                reason="Fits the budget.",
            ),
        ],
    )


class TestPersistence:
    async def test_a_plan_round_trips(
        self, session: AsyncSession, member: Principal
    ) -> None:
        created = await plan_service.create_plan(session, member, payload())
        await session.commit()

        fetched = await plan_service.get_plan(session, member, created.id)
        assert fetched.title == "Integration evening"
        assert len(fetched.stops) == 1
        assert fetched.stops[0].name == "Dinner"

    async def test_timestamps_are_populated_by_the_database(
        self, session: AsyncSession, member: Principal
    ) -> None:
        created = await plan_service.create_plan(session, member, payload())
        await session.commit()
        await session.refresh(created)

        assert created.created_at is not None
        assert created.updated_at is not None

    async def test_deleting_a_plan_cascades_to_its_stops(
        self, session: AsyncSession, member: Principal
    ) -> None:
        from app.models import PlanStop
        from sqlalchemy import func, select

        created = await plan_service.create_plan(session, member, payload())
        await session.commit()
        plan_id = created.id

        admin = Principal(
            user_id=member.user_id,
            organization_id=member.organization_id,
            role="admin",
            permissions=frozenset({"plans:read", "plans:delete"}),
        )
        await plan_service.delete_plan(session, admin, plan_id)
        await session.commit()

        remaining = await session.scalar(
            select(func.count(PlanStop.id)).where(PlanStop.plan_id == plan_id)
        )
        assert remaining == 0


class TestTenantIsolation:
    async def test_another_organization_cannot_read_the_plan(
        self, session: AsyncSession, member: Principal, other_org: Principal
    ) -> None:
        created = await plan_service.create_plan(session, member, payload())
        await session.commit()

        with pytest.raises(NotFound):
            await plan_service.get_plan(session, other_org, created.id)

    async def test_listing_is_scoped_to_the_organization(
        self, session: AsyncSession, member: Principal, other_org: Principal
    ) -> None:
        await plan_service.create_plan(session, member, payload("Org A evening"))
        await plan_service.create_plan(session, other_org, payload("Org B evening"))
        await session.commit()

        a_plans, _ = await plan_service.list_plans(session, member)
        b_plans, _ = await plan_service.list_plans(session, other_org)

        assert all(p.organization_id == member.organization_id for p in a_plans)
        assert all(p.organization_id == other_org.organization_id for p in b_plans)
        assert {p.id for p in a_plans}.isdisjoint({p.id for p in b_plans})

    async def test_an_idempotency_key_does_not_cross_organizations(
        self, session: AsyncSession, member: Principal, other_org: Principal
    ) -> None:
        mine = await plan_service.create_plan(session, member, payload(key="shared"))
        theirs = await plan_service.create_plan(
            session, other_org, payload(key="shared")
        )
        await session.commit()

        assert mine.id != theirs.id


class TestAuthorization:
    async def test_a_viewer_cannot_write(
        self, session: AsyncSession, viewer: Principal
    ) -> None:
        with pytest.raises(PermissionDenied):
            await plan_service.create_plan(session, viewer, payload())

    async def test_a_viewer_can_read(
        self, session: AsyncSession, member: Principal, viewer: Principal
    ) -> None:
        await plan_service.create_plan(session, member, payload())
        await session.commit()

        plans, total = await plan_service.list_plans(session, viewer)
        assert total >= 1
        assert plans

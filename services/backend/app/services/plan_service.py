"""Plan domain service.

Every function takes a :class:`Principal` as its first argument and derives the
tenant from it. There is no code path that accepts an ``organization_id``
parameter from a caller — that is what makes "the model cannot forge a tenant"
a structural property rather than a convention.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import (
    PLANS_DELETE,
    PLANS_READ,
    PLANS_WRITE,
    Principal,
    require_permission,
)
from app.errors import NotFound
from app.logging import get_logger
from app.models import Plan, PlanStop
from app.schemas.plan import PlanCreate, PlanUpdate

log = get_logger(__name__)

MAX_PAGE_SIZE = 100


async def list_plans(
    session: AsyncSession,
    principal: Principal,
    *,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
) -> tuple[list[Plan], int]:
    require_permission(principal, PLANS_READ)

    limit = min(max(limit, 1), MAX_PAGE_SIZE)
    offset = max(offset, 0)

    conditions = [Plan.organization_id == principal.organization_id]
    if status:
        conditions.append(Plan.status == status)

    total = await session.scalar(select(func.count(Plan.id)).where(*conditions)) or 0
    result = await session.scalars(
        select(Plan).where(*conditions).order_by(Plan.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result), total


async def get_plan(session: AsyncSession, principal: Principal, plan_id: str) -> Plan:
    """Fetch one plan within the caller's organization.

    A plan belonging to another organization raises :class:`NotFound`, not
    ``PermissionDenied`` — a 403 would confirm the id exists and leak the shape
    of another tenant's data.
    """
    require_permission(principal, PLANS_READ)

    plan = await session.scalar(
        select(Plan).where(
            Plan.id == plan_id,
            Plan.organization_id == principal.organization_id,
        )
    )
    if plan is None:
        raise NotFound(f"Plan {plan_id} was not found.", detail={"plan_id": plan_id})
    return plan


async def create_plan(session: AsyncSession, principal: Principal, payload: PlanCreate) -> Plan:
    require_permission(principal, PLANS_WRITE)

    if payload.idempotency_key:
        existing = await _find_by_idempotency_key(session, principal, payload.idempotency_key)
        if existing is not None:
            log.info(
                "plan.create.idempotent_hit",
                plan_id=existing.id,
                idempotency_key=payload.idempotency_key,
            )
            return existing

    plan = Plan(
        organization_id=principal.organization_id,
        created_by_user_id=principal.user_id,
        title=payload.title,
        status=payload.status,
        start_time=payload.start_time,
        estimated_cost=payload.estimated_cost,
        estimated_walk_distance_km=payload.estimated_walk_distance_km,
        latitude=payload.latitude,
        longitude=payload.longitude,
        notes=payload.notes,
        agent_run_id=payload.agent_run_id or payload.idempotency_key,
        stops=[
            PlanStop(position=index, **stop.model_dump())
            for index, stop in enumerate(payload.stops)
        ],
    )

    session.add(plan)
    await session.flush()

    log.info(
        "plan.created",
        plan_id=plan.id,
        organization_id=plan.organization_id,
        user_id=principal.user_id,
        stop_count=len(plan.stops),
        estimated_cost=plan.estimated_cost,
    )
    return plan


async def update_plan(
    session: AsyncSession, principal: Principal, plan_id: str, payload: PlanUpdate
) -> Plan:
    require_permission(principal, PLANS_WRITE)

    plan = await get_plan(session, principal, plan_id)

    if payload.title is not None:
        plan.title = payload.title
    if payload.status is not None:
        plan.status = payload.status
    if payload.notes is not None:
        plan.notes = payload.notes
    if payload.stops is not None:
        plan.stops = [
            PlanStop(position=index, **stop.model_dump())
            for index, stop in enumerate(payload.stops)
        ]
        plan.estimated_cost = sum(stop.estimated_cost for stop in payload.stops)

    await session.flush()
    log.info("plan.updated", plan_id=plan.id, organization_id=plan.organization_id)
    return plan


async def delete_plan(session: AsyncSession, principal: Principal, plan_id: str) -> None:
    require_permission(principal, PLANS_DELETE)

    plan = await get_plan(session, principal, plan_id)
    await session.delete(plan)
    log.info("plan.deleted", plan_id=plan_id, organization_id=principal.organization_id)


async def _find_by_idempotency_key(
    session: AsyncSession, principal: Principal, key: str
) -> Plan | None:
    result: Plan | None = await session.scalar(
        select(Plan).where(
            Plan.organization_id == principal.organization_id,
            Plan.agent_run_id == key,
        )
    )
    return result

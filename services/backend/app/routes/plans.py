"""Plan routes.

Route-level dependencies give a fast 403 before any database work. The service
layer checks the same permission again, so the guarantee does not depend on a
route decorator being remembered.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.auth.dependencies import CurrentPrincipal, requires
from app.auth.permissions import PLANS_DELETE, PLANS_READ, PLANS_WRITE
from app.persistence.postgres import DbSession
from app.schemas.plan import PlanCreate, PlanList, PlanRead, PlanUpdate
from app.services import plan_service

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=PlanList, dependencies=[requires(PLANS_READ)])
async def list_plans(
    session: DbSession,
    principal: CurrentPrincipal,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    plan_status: Annotated[str | None, Query(alias="status")] = None,
) -> PlanList:
    plans, total = await plan_service.list_plans(
        session, principal, limit=limit, offset=offset, status=plan_status
    )
    return PlanList(items=[PlanRead.model_validate(p) for p in plans], total=total)


@router.get("/{plan_id}", response_model=PlanRead, dependencies=[requires(PLANS_READ)])
async def get_plan(session: DbSession, principal: CurrentPrincipal, plan_id: str) -> PlanRead:
    plan = await plan_service.get_plan(session, principal, plan_id)
    return PlanRead.model_validate(plan)


@router.post(
    "",
    response_model=PlanRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[requires(PLANS_WRITE)],
)
async def create_plan(
    session: DbSession, principal: CurrentPrincipal, payload: PlanCreate
) -> PlanRead:
    plan = await plan_service.create_plan(session, principal, payload)
    return PlanRead.model_validate(plan)


@router.patch("/{plan_id}", response_model=PlanRead, dependencies=[requires(PLANS_WRITE)])
async def update_plan(
    session: DbSession, principal: CurrentPrincipal, plan_id: str, payload: PlanUpdate
) -> PlanRead:
    plan = await plan_service.update_plan(session, principal, plan_id, payload)
    return PlanRead.model_validate(plan)


@router.delete(
    "/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[requires(PLANS_DELETE)],
)
async def delete_plan(session: DbSession, principal: CurrentPrincipal, plan_id: str) -> None:
    await plan_service.delete_plan(session, principal, plan_id)

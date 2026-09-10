"""Agent run observability routes."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.auth.dependencies import CurrentPrincipal, requires
from app.auth.permissions import AGENTS_RUN, PLANS_READ
from app.persistence.postgres import DbSession
from app.schemas.agent_run import AgentRunComplete, AgentRunCreate, AgentRunRead
from app.services import agent_run_service

router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


@router.post(
    "",
    response_model=AgentRunRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[requires(AGENTS_RUN)],
)
async def start_run(
    session: DbSession, principal: CurrentPrincipal, payload: AgentRunCreate
) -> AgentRunRead:
    run = await agent_run_service.start_run(session, principal, payload)
    return AgentRunRead.model_validate(run)


@router.post("/{run_id}/complete", response_model=AgentRunRead, dependencies=[requires(AGENTS_RUN)])
async def complete_run(
    session: DbSession, principal: CurrentPrincipal, run_id: str, payload: AgentRunComplete
) -> AgentRunRead:
    run = await agent_run_service.complete_run(session, principal, run_id, payload)
    return AgentRunRead.model_validate(run)


@router.get("/{run_id}", response_model=AgentRunRead, dependencies=[requires(PLANS_READ)])
async def get_run(session: DbSession, principal: CurrentPrincipal, run_id: str) -> AgentRunRead:
    run = await agent_run_service.get_run(session, principal, run_id)
    return AgentRunRead.model_validate(run)

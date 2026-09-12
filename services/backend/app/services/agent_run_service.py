"""Agent run recording.

The agent runtime reports its own lifecycle here so that runs, tool calls,
latency and cost are queryable from the deterministic API — independently of
whatever tracing backend is configured.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import AGENTS_RUN, PLANS_READ, Principal, require_permission
from app.errors import NotFound
from app.logging import get_logger
from app.models import AgentRun
from app.schemas.agent_run import AgentRunComplete, AgentRunCreate

log = get_logger(__name__)


async def start_run(
    session: AsyncSession, principal: Principal, payload: AgentRunCreate
) -> AgentRun:
    require_permission(principal, AGENTS_RUN)

    existing = await session.get(AgentRun, payload.id)
    if existing is not None:
        # Runs are reported at-least-once; a repeated start is not an error.
        return existing

    run = AgentRun(
        id=payload.id,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        agent_name=payload.agent_name,
        model=payload.model,
        status="running",
        started_at=payload.started_at,
        trace_id=payload.trace_id,
    )
    session.add(run)
    await session.flush()
    log.info("agent_run.started", run_id=run.id, agent=run.agent_name, model=run.model)
    return run


async def complete_run(
    session: AsyncSession, principal: Principal, run_id: str, payload: AgentRunComplete
) -> AgentRun:
    require_permission(principal, AGENTS_RUN)

    run = await _get_scoped(session, principal, run_id)
    run.status = payload.status
    run.completed_at = payload.completed_at
    run.latency_ms = payload.latency_ms
    run.input_tokens = payload.input_tokens
    run.output_tokens = payload.output_tokens
    run.estimated_cost = payload.estimated_cost
    run.error = payload.error

    await session.flush()
    log.info(
        "agent_run.completed",
        run_id=run.id,
        status=run.status,
        latency_ms=run.latency_ms,
        estimated_cost=run.estimated_cost,
    )
    return run


async def get_run(session: AsyncSession, principal: Principal, run_id: str) -> AgentRun:
    require_permission(principal, PLANS_READ)
    return await _get_scoped(session, principal, run_id)


async def _get_scoped(session: AsyncSession, principal: Principal, run_id: str) -> AgentRun:
    run = await session.scalar(
        select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.organization_id == principal.organization_id,
        )
    )
    if run is None:
        raise NotFound(f"Agent run {run_id} was not found.", detail={"run_id": run_id})
    return run

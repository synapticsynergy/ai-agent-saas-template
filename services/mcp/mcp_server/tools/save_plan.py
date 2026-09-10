"""save_plan — persist an itinerary through the application API.

This is the one consequential tool in the reference set, and it is the clearest
demonstration of the template's security model:

  * the agent decides it *wants* to save,
  * the UI may ask the user to approve,
  * neither of those authorizes anything,
  * the API verifies the caller's token and requires ``plans:write`` before a
    row is written, scoped to the organization in that verified token.

A viewer's agent can call this tool all day and never write a plan.
"""

from __future__ import annotations

from saas_contracts.plan import Itinerary
from saas_contracts.tools import SavePlanOutput

from mcp_server import api_client
from mcp_server.context import CallerIdentity


async def save_plan(
    itinerary: Itinerary,
    identity: CallerIdentity,
    *,
    idempotency_key: str | None = None,
) -> SavePlanOutput:
    if not itinerary.stops:
        raise ValueError("Cannot save an itinerary with no stops.")

    payload = itinerary.to_plan_create(
        # Falling back to the run id makes a retried save idempotent even when
        # the caller forgets to supply a key.
        idempotency_key=idempotency_key or identity.run_id
    )

    plan = await api_client.create_plan(identity, payload)

    return SavePlanOutput(
        plan_id=plan.id,
        status=plan.status,
        title=plan.title,
        estimated_cost=plan.estimated_cost,
        stop_count=len(plan.stops),
    )

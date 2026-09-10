"""Plan schemas.

Re-exported from ``packages/contracts`` so the API, the agent, the MCP tools and
the web app all validate against one definition. Anything genuinely
API-specific belongs in ``app.schemas.common``, not here.
"""

from saas_contracts.plan import (
    MAX_STOPS,
    Itinerary,
    Latitude,
    Longitude,
    Money,
    PlanBase,
    PlanCreate,
    PlanList,
    PlanRead,
    PlanStatus,
    PlanStopBase,
    PlanStopCreate,
    PlanStopRead,
    PlanUpdate,
    StopCategory,
)

__all__ = [
    "MAX_STOPS",
    "Itinerary",
    "Latitude",
    "Longitude",
    "Money",
    "PlanBase",
    "PlanCreate",
    "PlanList",
    "PlanRead",
    "PlanStatus",
    "PlanStopBase",
    "PlanStopCreate",
    "PlanStopRead",
    "PlanUpdate",
    "StopCategory",
]

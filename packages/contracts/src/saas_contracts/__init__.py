"""Shared domain contracts.

Imported by services/api, services/agent and services/mcp as a path dependency,
and exported to TypeScript for apps/web via ``make contracts``.
"""

from saas_contracts.agent_run import (
    AgentRunComplete,
    AgentRunCreate,
    AgentRunRead,
    AgentToolCallRead,
    RunStatus,
    ToolCallStatus,
)
from saas_contracts.plan import (
    MAX_STOPS,
    Itinerary,
    PlanCreate,
    PlanList,
    PlanRead,
    PlanStatus,
    PlanStopCreate,
    PlanStopRead,
    PlanUpdate,
    StopCategory,
)
from saas_contracts.streaming import AgentEvent, ProgressStage
from saas_contracts.tools import (
    BuildRouteInput,
    Event,
    GeoPoint,
    GetPlaceDetailsInput,
    Place,
    PlaceDetails,
    Route,
    RouteLeg,
    SavePlanOutput,
    SearchEventsInput,
    SearchEventsOutput,
    SearchPlacesInput,
    SearchPlacesOutput,
)

__all__ = [
    "MAX_STOPS",
    "AgentEvent",
    "AgentRunComplete",
    "AgentRunCreate",
    "AgentRunRead",
    "AgentToolCallRead",
    "BuildRouteInput",
    "Event",
    "GeoPoint",
    "GetPlaceDetailsInput",
    "Itinerary",
    "Place",
    "PlaceDetails",
    "PlanCreate",
    "PlanList",
    "PlanRead",
    "PlanStatus",
    "PlanStopCreate",
    "PlanStopRead",
    "PlanUpdate",
    "ProgressStage",
    "Route",
    "RouteLeg",
    "RunStatus",
    "SavePlanOutput",
    "SearchEventsInput",
    "SearchEventsOutput",
    "SearchPlacesInput",
    "SearchPlacesOutput",
    "StopCategory",
    "ToolCallStatus",
]

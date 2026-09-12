"""MCP server exposing the reference application's agent-facing capabilities.

Transport is streamable HTTP, so the agent (and AgentCore Gateway) can reach it
over the network and forward the caller's identity as request headers.

Only capabilities that earn the protocol boundary live here (ADR-003):
reusable, independently deployable, and useful to more than one agent. Internal
helpers — scoring, geometry, formatting — stay ordinary Python.

Tool signatures are flat rather than taking a nested payload object: a model
picks arguments far more reliably from a flat schema, and the typed contracts in
``saas_contracts.tools`` still do the validating.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Any

import structlog
from mcp.server.apps import Apps
from mcp.server.mcpserver import Context, MCPServer
from pydantic import Field
from saas_contracts.plan import Itinerary, StopCategory
from saas_contracts.tools import (
    BuildRouteInput,
    GeoPoint,
    GetPlaceDetailsInput,
    PlaceDetails,
    Route,
    SavePlanOutput,
    SearchEventsInput,
    SearchEventsOutput,
    SearchPlacesInput,
    SearchPlacesOutput,
)

from mcp_server import tools
from mcp_server.config import settings
from mcp_server.context import require_identity
from mcp_server.resources.itinerary_map import ITINERARY_MAP_HTML, ITINERARY_MAP_URI
from mcp_server.tools.errors import ToolError, map_exception

log = structlog.get_logger(__name__)

INSTRUCTIONS = """\
Capabilities for planning an evening out: discovering places and live events \
near a location, estimating walking routes between stops, and saving a \
finished itinerary.

Search and route tools are read-only and safe to call freely. save_plan writes \
tenant data and requires an authenticated caller; the application API enforces \
the caller's permissions regardless of what this server is asked to do.\
"""

# ---------------------------------------------------------------------------
# MCP App: interactive itinerary map.
#
# The extension must be fully populated before MCPServer is constructed —
# bindings are collected at attach time, not lazily.
# ---------------------------------------------------------------------------

apps = Apps()

apps.add_html_resource(
    ITINERARY_MAP_URI,
    ITINERARY_MAP_HTML,
    name="itinerary_map",
    title="Itinerary map",
    description="Interactive map and stop list for an evening itinerary.",
)


@apps.tool(
    resource_uri=ITINERARY_MAP_URI,
    name="render_itinerary",
    title="Render the itinerary",
    description=(
        "Display an itinerary as an interactive map with a stop list. Call this "
        "after building or revising an itinerary so the user can see it."
    ),
)
async def render_itinerary(
    itinerary: Annotated[Itinerary, Field(description="The itinerary to display.")],
) -> dict[str, Any]:
    """Return the itinerary as structured content for the MCP App to render.

    Hosts without MCP Apps support still receive usable structured output, so
    this degrades to "returns the itinerary" rather than failing outright.
    """
    return {"itinerary": itinerary.model_dump(mode="json")}


server = MCPServer(
    name="plan-my-evening",
    title="Plan My Evening",
    version="0.1.0",
    instructions=INSTRUCTIONS,
    extensions=[apps],
    log_level="DEBUG" if settings.is_local else "INFO",
)


# ---------------------------------------------------------------------------
# Discovery tools — read-only, no tenant data, no identity required.
# ---------------------------------------------------------------------------


@server.tool(
    name="search_places",
    title="Search places",
    description=(
        "Find venues of one category near a coordinate, sorted by rating. "
        "Set max_price_level to respect a budget before ranking."
    ),
)
async def search_places(
    latitude: Annotated[float, Field(ge=-90, le=90, description="Search centre latitude.")],
    longitude: Annotated[float, Field(ge=-180, le=180, description="Search centre longitude.")],
    category: Annotated[StopCategory, Field(description="Kind of venue to find.")],
    radius_km: Annotated[float, Field(gt=0, le=25, description="Search radius.")] = 2.0,
    max_price_level: Annotated[int, Field(ge=1, le=4, description="1 cheapest, 4 priciest.")] = 4,
    limit: Annotated[int, Field(ge=1, le=25)] = 10,
    tags: Annotated[
        list[str] | None, Field(description='Optional tags, e.g. ["vegan", "patio"].')
    ] = None,
) -> SearchPlacesOutput | ToolError:
    try:
        payload = SearchPlacesInput(
            latitude=latitude,
            longitude=longitude,
            category=category,
            radius_km=radius_km,
            max_price_level=max_price_level,  # type: ignore[arg-type]
            limit=limit,
            tags=tags or [],
        )
        result = await tools.search_places(payload)
    except Exception as exc:
        log.warning("tool.search_places.failed", error=str(exc))
        return map_exception(exc)

    log.info("tool.search_places", category=category, results=result.total)
    return result


@server.tool(
    name="search_events",
    title="Search live events",
    description=(
        "Find live events starting inside a time window near a coordinate. "
        "Filter by genre and maximum ticket price."
    ),
)
async def search_events(
    latitude: Annotated[float, Field(ge=-90, le=90)],
    longitude: Annotated[float, Field(ge=-180, le=180)],
    start_after: Annotated[datetime, Field(description="Earliest event start (ISO 8601).")],
    start_before: Annotated[datetime, Field(description="Latest event start (ISO 8601).")],
    radius_km: Annotated[float, Field(gt=0, le=25)] = 2.0,
    genre: Annotated[str, Field(description='e.g. "jazz"; empty for any genre.')] = "",
    max_ticket_price: Annotated[float | None, Field(ge=0)] = None,
    limit: Annotated[int, Field(ge=1, le=25)] = 10,
) -> SearchEventsOutput | ToolError:
    try:
        payload = SearchEventsInput(
            latitude=latitude,
            longitude=longitude,
            start_after=start_after,
            start_before=start_before,
            radius_km=radius_km,
            genre=genre,
            max_ticket_price=max_ticket_price,
            limit=limit,
        )
        result = await tools.search_events(payload)
    except Exception as exc:
        log.warning("tool.search_events.failed", error=str(exc))
        return map_exception(exc)

    log.info("tool.search_events", genre=genre or "any", results=result.total)
    return result


@server.tool(
    name="get_place_details",
    title="Get place details",
    description="Full record for one place, including hours and whether it takes reservations.",
)
async def get_place_details(
    place_id: Annotated[str, Field(min_length=1, description="Place id from search_places.")],
) -> PlaceDetails | ToolError:
    try:
        return await tools.get_place_details(GetPlaceDetailsInput(place_id=place_id))
    except Exception as exc:
        return map_exception(exc)


@server.tool(
    name="build_route",
    title="Build a route",
    description=(
        "Distance and travel time between ordered stops. Use this to check an "
        "itinerary is actually walkable before proposing it."
    ),
)
async def build_route(
    stops: Annotated[
        list[GeoPoint], Field(min_length=2, description="Stop coordinates, in visit order.")
    ],
    mode: Annotated[str, Field(description='"walk", "transit" or "drive".')] = "walk",
    names: Annotated[list[str] | None, Field(description="Stop names, same order.")] = None,
) -> Route | ToolError:
    try:
        payload = BuildRouteInput(stops=stops, mode=mode, names=names or [])  # type: ignore[arg-type]
        return await tools.build_route(payload)
    except Exception as exc:
        return map_exception(exc)


# ---------------------------------------------------------------------------
# Consequential tool — writes tenant data.
# ---------------------------------------------------------------------------


@server.tool(
    name="save_plan",
    title="Save the itinerary",
    description=(
        "Persist the itinerary to the user's organization. Requires the "
        "plans:write permission, which the application API enforces. Ask the "
        "user before calling it — but note their approval expresses intent, it "
        "does not grant permission."
    ),
)
async def save_plan(
    context: Context,
    itinerary: Annotated[Itinerary, Field(description="The itinerary to persist.")],
    idempotency_key: Annotated[
        str | None, Field(description="Repeat the same key to make a retry a no-op.")
    ] = None,
) -> SavePlanOutput | ToolError:
    try:
        identity = require_identity(dict(context.headers or {}))
        result = await tools.save_plan(itinerary, identity, idempotency_key=idempotency_key)
    except Exception as exc:
        error = map_exception(exc)
        log.warning("tool.save_plan.rejected", code=error.code)
        return error

    log.info("tool.save_plan", plan_id=result.plan_id, stops=result.stop_count)
    return result


def main() -> None:
    logging.basicConfig(level=settings.log_level.upper())
    log.info(
        "mcp.starting",
        host=settings.mcp_host,
        port=settings.mcp_port,
        places_provider=settings.places_provider,
        events_provider=settings.events_provider,
    )
    # Host and port are transport options in MCP 2.x, not server settings.
    server.run(
        transport="streamable-http",
        host=settings.mcp_host,
        port=settings.mcp_port,
    )


if __name__ == "__main__":
    main()

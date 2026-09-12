"""build_route — distance and duration between ordered stops.

Deterministic geometry, so the agent can compare candidate itineraries on
walkability without guessing at distances from coordinates.
"""

from __future__ import annotations

from saas_contracts.tools import BuildRouteInput, Route

from mcp_server.providers import registry


async def build_route(payload: BuildRouteInput) -> Route:
    points = [(stop.latitude, stop.longitude) for stop in payload.stops]
    return await registry.route_provider().build(
        points=points, names=payload.names, mode=payload.mode
    )

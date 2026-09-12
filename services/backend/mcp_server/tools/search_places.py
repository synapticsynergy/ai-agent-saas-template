"""search_places — discover venues near a point.

Read-only discovery: no tenant data, no side effects, so no approval and no
identity requirement.
"""

from __future__ import annotations

from saas_contracts.tools import SearchPlacesInput, SearchPlacesOutput

from mcp_server.providers import registry


async def search_places(payload: SearchPlacesInput) -> SearchPlacesOutput:
    provider = registry.places_provider()
    items = await provider.search(
        latitude=payload.latitude,
        longitude=payload.longitude,
        category=payload.category,
        radius_km=payload.radius_km,
        max_price_level=payload.max_price_level,
        limit=payload.limit,
        tags=payload.tags,
    )
    return SearchPlacesOutput(items=items, total=len(items), provider=provider.name)

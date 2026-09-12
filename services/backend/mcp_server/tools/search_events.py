"""search_events — find live events in a time window near a point."""

from __future__ import annotations

from saas_contracts.tools import SearchEventsInput, SearchEventsOutput

from mcp_server.providers import registry


async def search_events(payload: SearchEventsInput) -> SearchEventsOutput:
    if payload.start_before <= payload.start_after:
        raise ValueError("start_before must be after start_after")

    provider = registry.events_provider()
    items = await provider.search(
        latitude=payload.latitude,
        longitude=payload.longitude,
        start_after=payload.start_after,
        start_before=payload.start_before,
        radius_km=payload.radius_km,
        genre=payload.genre,
        max_ticket_price=payload.max_ticket_price,
        limit=payload.limit,
    )
    return SearchEventsOutput(items=items, total=len(items), provider=provider.name)

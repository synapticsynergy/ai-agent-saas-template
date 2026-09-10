"""get_place_details — full record for a single place."""

from __future__ import annotations

from saas_contracts.tools import GetPlaceDetailsInput, PlaceDetails

from mcp_server.providers import registry


async def get_place_details(payload: GetPlaceDetailsInput) -> PlaceDetails:
    details = await registry.places_provider().details(payload.place_id)
    if details is None:
        raise ValueError(f"No place with id {payload.place_id!r}.")
    return details

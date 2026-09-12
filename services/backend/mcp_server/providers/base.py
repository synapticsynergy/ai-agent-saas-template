"""Provider interfaces.

Vendor SDKs stay behind these Protocols. Domain code and tool handlers depend
on the interface, so swapping a places provider is a registry change rather
than a rewrite (docs/DESIGN_PRINCIPLES.md, "Prefer replaceable adapters").
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from saas_contracts.tools import Event, Place, PlaceDetails, Route


class ProviderTimeout(Exception):
    """Upstream did not answer in time. Retryable."""

    code = "provider_timeout"


class ProviderUnavailable(Exception):
    """Upstream failed in a way that is not worth retrying."""

    code = "provider_error"


class PlacesProvider(Protocol):
    name: str

    async def search(
        self,
        *,
        latitude: float,
        longitude: float,
        category: str,
        radius_km: float,
        max_price_level: int,
        limit: int,
        tags: list[str],
    ) -> list[Place]: ...

    async def details(self, place_id: str) -> PlaceDetails | None: ...


class EventsProvider(Protocol):
    name: str

    async def search(
        self,
        *,
        latitude: float,
        longitude: float,
        start_after: datetime,
        start_before: datetime,
        radius_km: float,
        genre: str,
        max_ticket_price: float | None,
        limit: int,
    ) -> list[Event]: ...


class RouteProvider(Protocol):
    name: str

    async def build(
        self,
        *,
        points: list[tuple[float, float]],
        names: list[str],
        mode: str,
    ) -> Route: ...

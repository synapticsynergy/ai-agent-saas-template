"""HTTP provider adapters for real places/events APIs.

Kept intentionally thin: the vendor's response shape is translated into the
template's contracts here and nowhere else, so replacing the vendor touches one
file. Timeouts and error codes are normalised to ``ProviderTimeout`` /
``ProviderUnavailable`` so the tool layer maps failures uniformly regardless of
which vendor is configured.

Field mappings below assume a conventional ``{"results": [...]}`` payload.
Adjust ``_to_place`` / ``_to_event`` for your provider.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import httpx
from saas_contracts.tools import Event, Place, PlaceDetails, PriceLevel

from mcp_server.config import settings
from mcp_server.providers.base import ProviderTimeout, ProviderUnavailable


class _HttpProvider:
    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        try:
            async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
                response = await client.get(
                    f"{self._base_url}{path}", params=params, headers=headers
                )
                response.raise_for_status()
                return response.json()  # type: ignore[no-any-return]
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(f"{self._base_url}{path} timed out") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise ProviderTimeout("Provider rate limit reached; retry shortly.") from exc
            raise ProviderUnavailable(f"Provider returned {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(str(exc)) from exc


class HttpPlacesProvider(_HttpProvider):
    name = "http"

    def __init__(self) -> None:
        super().__init__(settings.places_api_url, settings.places_api_key)

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
    ) -> list[Place]:
        payload = await self._get(
            "/places/search",
            {
                "lat": latitude,
                "lon": longitude,
                "category": category,
                "radius_m": int(radius_km * 1000),
                "max_price_level": max_price_level,
                "limit": limit,
                "tags": ",".join(tags),
            },
        )
        return [_to_place(item) for item in payload.get("results", [])]

    async def details(self, place_id: str) -> PlaceDetails | None:
        payload = await self._get(f"/places/{place_id}", {})
        result = payload.get("result")
        return (
            PlaceDetails(**_to_place(result).model_dump(), **_details_extras(result))
            if result
            else None
        )


class HttpEventsProvider(_HttpProvider):
    name = "http"

    def __init__(self) -> None:
        super().__init__(settings.events_api_url, settings.events_api_key)

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
    ) -> list[Event]:
        payload = await self._get(
            "/events/search",
            {
                "lat": latitude,
                "lon": longitude,
                "start_after": start_after.isoformat(),
                "start_before": start_before.isoformat(),
                "radius_m": int(radius_km * 1000),
                "genre": genre,
                "max_price": max_ticket_price,
                "limit": limit,
            },
        )
        return [_to_event(item) for item in payload.get("results", [])]


def _to_place(item: dict[str, Any]) -> Place:
    return Place(
        id=str(item["id"]),
        name=item["name"],
        category=item.get("category", "activity"),
        latitude=float(item["latitude"]),
        longitude=float(item["longitude"]),
        price_level=_price_level(item.get("price_level", 2)),
        typical_cost_per_person=float(item.get("typical_cost", 0.0)),
        rating=float(item.get("rating", 0.0)),
        address=item.get("address", ""),
        tags=list(item.get("tags", [])),
        opens_at=item.get("opens_at", ""),
        closes_at=item.get("closes_at", ""),
    )


def _price_level(value: Any) -> PriceLevel:
    """Clamp a provider's price level into the 1-4 range the contract allows."""
    level = max(1, min(4, int(value or 2)))
    return cast(PriceLevel, level)


def _details_extras(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "description": item.get("description", ""),
        "phone": item.get("phone", ""),
        "website": item.get("website", ""),
        "reservation_required": bool(item.get("reservation_required", False)),
    }


def _to_event(item: dict[str, Any]) -> Event:
    return Event(
        id=str(item["id"]),
        name=item["name"],
        genre=item.get("genre", ""),
        venue_name=item.get("venue_name", ""),
        venue_place_id=item.get("venue_place_id"),
        latitude=float(item["latitude"]),
        longitude=float(item["longitude"]),
        start_time=datetime.fromisoformat(item["start_time"]),
        end_time=datetime.fromisoformat(item["end_time"]),
        ticket_price=float(item.get("ticket_price", 0.0)),
        ticketed=bool(item.get("ticketed", False)),
        tags=list(item.get("tags", [])),
    )

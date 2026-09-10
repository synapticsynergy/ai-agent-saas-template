"""Deterministic fixture providers.

Used for local development and by every automated test. "Deterministic" is the
point: results are a pure function of the query, so a test can assert on exact
places, prices and ordering. Nothing here uses randomness or the wall clock
except through the explicit ``start_after`` window the caller supplies.

The dataset is a small fictional city centre. It is *not* Portland-specific —
coordinates are supplied by the caller and the fixture translates its dataset
to sit around whatever origin is requested, so the reference app works anywhere.
"""

from __future__ import annotations

import json
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from saas_contracts.tools import Event, Place, PlaceDetails, Route, RouteLeg

from mcp_server.geo import haversine_km, travel_minutes

_FIXTURE_PATH = Path(__file__).parent / "fixtures.json"

# The dataset's own centre. Records are re-anchored relative to this point so
# a request for any city gets a plausible, walkable local layout.
_DATASET_ORIGIN = (45.5231, -122.6765)


@lru_cache
def _raw() -> dict[str, Any]:
    return json.loads(_FIXTURE_PATH.read_text())  # type: ignore[no-any-return]


def _reanchor(lat: float, lon: float, origin_lat: float, origin_lon: float) -> tuple[float, float]:
    """Shift a fixture coordinate so the dataset centres on the requested origin."""
    return (
        round(lat - _DATASET_ORIGIN[0] + origin_lat, 6),
        round(lon - _DATASET_ORIGIN[1] + origin_lon, 6),
    )


class FixturePlacesProvider:
    name = "fixture"

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
        wanted_tags = {tag.lower() for tag in tags}
        results: list[Place] = []

        for record in _raw()["places"]:
            if record["category"] != category:
                continue
            if record["price_level"] > max_price_level:
                continue
            if wanted_tags and not wanted_tags & {t.lower() for t in record["tags"]}:
                continue

            lat, lon = _reanchor(record["latitude"], record["longitude"], latitude, longitude)
            if haversine_km(lat, lon, latitude, longitude) > radius_km:
                continue

            results.append(Place(**{**_place_fields(record), "latitude": lat, "longitude": lon}))

        # Stable ordering: best rated first, ties broken by id so results never
        # shuffle between identical calls.
        results.sort(key=lambda p: (-p.rating, p.id))
        return results[:limit]

    async def details(self, place_id: str) -> PlaceDetails | None:
        for record in _raw()["places"]:
            if record["id"] == place_id:
                return PlaceDetails(**record)
        return None


class FixtureEventsProvider:
    name = "fixture"

    async def search(
        self,
        *,
        latitude: float,
        longitude: float,
        start_after: Any,
        start_before: Any,
        radius_km: float,
        genre: str,
        max_ticket_price: float | None,
        limit: int,
    ) -> list[Event]:
        results: list[Event] = []

        for record in _raw()["events"]:
            if genre and record["genre"].lower() != genre.lower():
                continue
            if max_ticket_price is not None and record["ticket_price"] > max_ticket_price:
                continue

            # Event times are expressed as an offset from the requested window
            # start, so the fixture always returns events inside the window the
            # caller asked about rather than fixed dates that go stale.
            start = start_after + timedelta(minutes=record["start_offset_minutes"])
            if start > start_before:
                continue

            lat, lon = _reanchor(record["latitude"], record["longitude"], latitude, longitude)
            if haversine_km(lat, lon, latitude, longitude) > radius_km:
                continue

            results.append(
                Event(
                    id=record["id"],
                    name=record["name"],
                    genre=record["genre"],
                    venue_name=record["venue_name"],
                    venue_place_id=record["venue_place_id"],
                    latitude=lat,
                    longitude=lon,
                    start_time=start,
                    end_time=start + timedelta(minutes=record["duration_minutes"]),
                    ticket_price=record["ticket_price"],
                    ticketed=record["ticketed"],
                    tags=record["tags"],
                )
            )

        results.sort(key=lambda e: (e.start_time, e.id))
        return results[:limit]


class FixtureRouteProvider:
    """Straight-line routing with a street-distance correction.

    Good enough to rank itineraries by walkability. A real routing provider
    (Mapbox, Valhalla, OSRM) drops in behind the same interface.
    """

    name = "fixture"

    async def build(
        self,
        *,
        points: list[tuple[float, float]],
        names: list[str],
        mode: str,
    ) -> Route:
        legs: list[RouteLeg] = []
        total_km = 0.0
        total_minutes = 0.0

        for index in range(len(points) - 1):
            (lat1, lon1), (lat2, lon2) = points[index], points[index + 1]
            distance = round(haversine_km(lat1, lon1, lat2, lon2), 3)
            minutes = round(travel_minutes(distance, mode), 1)

            legs.append(
                RouteLeg(
                    from_name=names[index] if index < len(names) else f"Stop {index + 1}",
                    to_name=names[index + 1] if index + 1 < len(names) else f"Stop {index + 2}",
                    distance_km=distance,
                    duration_minutes=minutes,
                    mode=mode,  # type: ignore[arg-type]
                )
            )
            total_km += distance
            total_minutes += minutes

        return Route(
            legs=legs,
            total_distance_km=round(total_km, 3),
            total_duration_minutes=round(total_minutes, 1),
            mode=mode,  # type: ignore[arg-type]
        )


def _place_fields(record: dict[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in Place.model_fields if key in record}

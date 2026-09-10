"""Agent test fixtures.

The planner is exercised against in-process stub tools returning a fixed
dataset. That keeps these tests fast and deterministic, and — more importantly —
means the planning logic is verified independently of MCP transport, the model
and the network.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

os.environ.setdefault("APP_ENV", "local")
os.environ.setdefault("AGENT_MODEL_PROVIDER", "scripted")

import pytest
from saas_contracts.tools import Event, Place, Route, RouteLeg

from agent_app.workflows.geo import distance_km
from agent_app.workflows.planner import PlannerTools
from agent_app.workflows.request import PlanningRequest

TONIGHT = datetime(2030, 6, 1, 19, 0, tzinfo=UTC)
LAT, LON = 45.5231, -122.6765


def place(
    id: str,
    name: str,
    category: str,
    cost: float,
    rating: float,
    *,
    lat: float = LAT,
    lon: float = LON,
    tags: list[str] | None = None,
    price_level: int = 2,
) -> Place:
    return Place(
        id=id,
        name=name,
        category=category,  # type: ignore[arg-type]
        latitude=lat,
        longitude=lon,
        price_level=price_level,  # type: ignore[arg-type]
        typical_cost_per_person=cost,
        rating=rating,
        address=f"{id} street",
        tags=tags or [],
    )


PLACES: dict[str, list[Place]] = {
    "dinner": [
        place("d_cheap", "Saltbox Diner", "dinner", 18.0, 4.1, lat=LAT + 0.002, price_level=1),
        place("d_mid", "Verdant", "dinner", 29.0, 4.4, lat=LAT + 0.003, tags=["vegan"]),
        place("d_posh", "Harborlight", "dinner", 78.0, 4.7, lat=LAT + 0.02, price_level=4),
    ],
    "music": [
        place("m_cheap", "Basement Sessions", "music", 10.0, 4.2, lat=LAT - 0.002),
        place("m_mid", "The Lantern Room", "music", 22.0, 4.5, lat=LAT + 0.001),
    ],
    "drinks": [
        place("b_cheap", "Alder Taproom", "drinks", 9.0, 4.0, lat=LAT - 0.001, price_level=1),
        place("b_mid", "Nightjar", "drinks", 16.0, 4.4, lat=LAT + 0.0015),
    ],
    "dessert": [place("s_1", "Sugarhouse", "dessert", 8.0, 4.5)],
    "coffee": [place("c_1", "Meridian Coffee", "coffee", 5.0, 4.3)],
    "activity": [place("a_1", "Arcadia Arcade", "activity", 14.0, 4.2)],
}

EVENTS: list[Event] = [
    Event(
        id="e_jazz_free",
        name="Ida Vance Trio",
        genre="jazz",
        venue_name="Basement Sessions",
        venue_place_id="m_cheap",
        latitude=LAT - 0.002,
        longitude=LON,
        start_time=TONIGHT + timedelta(hours=1, minutes=45),
        end_time=TONIGHT + timedelta(hours=3),
        ticket_price=0.0,
        ticketed=False,
        tags=["jazz"],
    ),
    Event(
        id="e_jazz_paid",
        name="The Marlow Quartet",
        genre="jazz",
        venue_name="The Lantern Room",
        venue_place_id="m_mid",
        latitude=LAT + 0.001,
        longitude=LON,
        start_time=TONIGHT + timedelta(hours=2),
        end_time=TONIGHT + timedelta(hours=3, minutes=30),
        ticket_price=22.0,
        ticketed=True,
        tags=["jazz"],
    ),
    Event(
        id="e_rock",
        name="Northline",
        genre="rock",
        venue_name="Ironworks Hall",
        venue_place_id="m_rock",
        latitude=LAT + 0.004,
        longitude=LON,
        start_time=TONIGHT + timedelta(hours=2, minutes=15),
        end_time=TONIGHT + timedelta(hours=4),
        ticket_price=38.0,
        ticketed=True,
        tags=["rock"],
    ),
]


class StubTools:
    """Records every call so tests can assert on tool usage, not just output."""

    def __init__(
        self,
        *,
        places: dict[str, list[Place]] | None = None,
        events: list[Event] | None = None,
    ) -> None:
        self.places = PLACES if places is None else places
        self.events = EVENTS if events is None else events
        self.calls: list[tuple[str, dict]] = []

    async def search_places(self, **kwargs) -> list[Place]:
        self.calls.append(("search_places", kwargs))
        candidates = self.places.get(kwargs["category"], [])
        radius = kwargs.get("radius_km", 2.5)
        return [
            p
            for p in candidates
            if distance_km(kwargs["latitude"], kwargs["longitude"], p.latitude, p.longitude)
            <= radius
        ]

    async def search_events(self, **kwargs) -> list[Event]:
        self.calls.append(("search_events", kwargs))
        results = [
            e
            for e in self.events
            if kwargs["start_after"] <= e.start_time <= kwargs["start_before"]
        ]
        if kwargs.get("genre"):
            results = [e for e in results if e.genre == kwargs["genre"]]
        cap = kwargs.get("max_ticket_price")
        if cap is not None:
            results = [e for e in results if e.ticket_price <= cap]
        return results

    async def build_route(self, **kwargs) -> Route:
        self.calls.append(("build_route", kwargs))
        stops = kwargs["stops"]
        legs = []
        total = 0.0
        for i in range(len(stops) - 1):
            a, b = stops[i], stops[i + 1]
            d = round(distance_km(a["latitude"], a["longitude"], b["latitude"], b["longitude"]), 3)
            legs.append(
                RouteLeg(
                    from_name=f"Stop {i + 1}",
                    to_name=f"Stop {i + 2}",
                    distance_km=d,
                    duration_minutes=round(d * 13.3, 1),
                )
            )
            total += d
        return Route(
            legs=legs,
            total_distance_km=round(total, 3),
            total_duration_minutes=round(total * 13.3, 1),
        )

    def called(self, name: str) -> bool:
        return any(call == name for call, _ in self.calls)

    def call_count(self, name: str) -> int:
        return sum(1 for call, _ in self.calls if call == name)

    @property
    def planner_tools(self) -> PlannerTools:
        return PlannerTools(self.search_places, self.search_events, self.build_route)


@pytest.fixture
def tools() -> StubTools:
    return StubTools()


@pytest.fixture
def base_request() -> PlanningRequest:
    return PlanningRequest(latitude=LAT, longitude=LON, start_time=TONIGHT)

"""MCP tool input/output contracts.

Narrow, typed and independent of any model. Every tool here can be called and
asserted on directly from a test — see docs/TESTING.md ("Tool Contract Tests").
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from saas_contracts.plan import Latitude, Longitude, Money, StopCategory

PriceLevel = Literal[1, 2, 3, 4]


class GeoPoint(BaseModel):
    latitude: Latitude
    longitude: Longitude


class Place(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    category: StopCategory
    latitude: Latitude
    longitude: Longitude
    price_level: PriceLevel = 2
    typical_cost_per_person: Money = 0.0
    rating: Annotated[float, Field(ge=0, le=5)] = 0.0
    address: str = ""
    tags: list[str] = Field(default_factory=list)
    opens_at: str = Field(default="", description="Local time, HH:MM.")
    closes_at: str = Field(default="", description="Local time, HH:MM.")


class PlaceDetails(Place):
    description: str = ""
    phone: str = ""
    website: str = ""
    reservation_required: bool = False


class Event(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    genre: str = ""
    venue_name: str = ""
    venue_place_id: str | None = None
    latitude: Latitude
    longitude: Longitude
    start_time: datetime
    end_time: datetime
    ticket_price: Money = 0.0
    ticketed: bool = False
    tags: list[str] = Field(default_factory=list)


class RouteLeg(BaseModel):
    from_name: str
    to_name: str
    distance_km: Annotated[float, Field(ge=0)]
    duration_minutes: Annotated[float, Field(ge=0)]
    mode: Literal["walk", "transit", "drive"] = "walk"


class Route(BaseModel):
    legs: list[RouteLeg] = Field(default_factory=list)
    total_distance_km: Annotated[float, Field(ge=0)] = 0.0
    total_duration_minutes: Annotated[float, Field(ge=0)] = 0.0
    mode: Literal["walk", "transit", "drive"] = "walk"


# --- tool inputs -----------------------------------------------------------


class SearchPlacesInput(BaseModel):
    latitude: Latitude
    longitude: Longitude
    category: StopCategory
    radius_km: Annotated[float, Field(gt=0, le=25)] = 2.0
    max_price_level: PriceLevel = 4
    limit: Annotated[int, Field(ge=1, le=25)] = 10
    tags: list[str] = Field(default_factory=list, max_length=10)


class SearchEventsInput(BaseModel):
    latitude: Latitude
    longitude: Longitude
    start_after: datetime
    start_before: datetime
    radius_km: Annotated[float, Field(gt=0, le=25)] = 2.0
    genre: str = ""
    max_ticket_price: Money | None = None
    limit: Annotated[int, Field(ge=1, le=25)] = 10


class GetPlaceDetailsInput(BaseModel):
    place_id: str = Field(min_length=1, max_length=128)


class BuildRouteInput(BaseModel):
    stops: list[GeoPoint] = Field(min_length=2, max_length=20)
    mode: Literal["walk", "transit", "drive"] = "walk"
    names: list[str] = Field(default_factory=list, max_length=20)


# --- tool outputs ----------------------------------------------------------


class SearchPlacesOutput(BaseModel):
    items: list[Place] = Field(default_factory=list)
    total: int = 0
    provider: str = "fixture"


class SearchEventsOutput(BaseModel):
    items: list[Event] = Field(default_factory=list)
    total: int = 0
    provider: str = "fixture"


class SavePlanOutput(BaseModel):
    plan_id: str
    status: str
    title: str
    estimated_cost: Money
    stop_count: int

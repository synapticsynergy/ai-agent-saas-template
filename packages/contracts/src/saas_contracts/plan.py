"""Plan and itinerary contract.

This is the single definition of the itinerary shape. The API persists it, the
agent produces it as streamed state, the MCP ``save_plan`` tool submits it, and
the web app renders it. TypeScript definitions are generated from these models
(``make contracts``), so a change here is a change everywhere.

Note what is *absent*: ``organization_id`` and ``created_by_user_id`` appear on
read models but on no create/update model. Tenancy is derived from the verified
principal at the service boundary, so there is nowhere for a caller — or a
model — to put a forged tenant.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PlanStatus = Literal["draft", "saved", "archived"]
StopCategory = Literal["dinner", "music", "drinks", "activity", "dessert", "coffee"]

Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]
Money = Annotated[float, Field(ge=0)]

MAX_STOPS = 20


class PlanStopBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(min_length=1, max_length=200)
    category: StopCategory
    start_time: datetime
    end_time: datetime
    latitude: Latitude
    longitude: Longitude
    estimated_cost: Money = 0.0
    reason: str = Field(default="", max_length=2000, description="Why the agent chose this stop.")
    external_id: str | None = Field(default=None, max_length=128)
    address: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _end_after_start(self) -> PlanStopBase:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class PlanStopCreate(PlanStopBase):
    pass


class PlanStopRead(PlanStopBase):
    id: str
    position: int


class PlanBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str = Field(min_length=1, max_length=200)
    start_time: datetime
    estimated_cost: Money = 0.0
    estimated_walk_distance_km: Annotated[float, Field(ge=0)] = 0.0
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    notes: str | None = Field(default=None, max_length=4000)


class PlanCreate(PlanBase):
    status: PlanStatus = "saved"
    stops: list[PlanStopCreate] = Field(default_factory=list, max_length=MAX_STOPS)
    agent_run_id: str | None = Field(default=None, max_length=64)
    idempotency_key: str | None = Field(
        default=None,
        max_length=128,
        description="Makes a repeated save of the same tool call a no-op.",
    )


class PlanUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    status: PlanStatus | None = None
    notes: str | None = Field(default=None, max_length=4000)
    stops: list[PlanStopCreate] | None = Field(default=None, max_length=MAX_STOPS)


class PlanRead(PlanBase):
    id: str
    organization_id: str
    created_by_user_id: str
    status: PlanStatus
    agent_run_id: str | None = None
    created_at: datetime
    updated_at: datetime
    stops: list[PlanStopRead] = Field(default_factory=list)


class PlanList(BaseModel):
    items: list[PlanRead]
    total: int


class Itinerary(BaseModel):
    """The agent's working itinerary — shared UI/agent state.

    Distinct from ``PlanRead``: an itinerary exists only in the running agent
    session and has no id or tenant until the user saves it. Modelling the
    in-progress plan separately keeps "draft the agent is editing" and "record
    the database owns" from blurring together.
    """

    plan_id: str | None = Field(
        default=None, description="Set once the itinerary has been saved through the API."
    )
    title: str = ""
    start_time: datetime | None = None
    estimated_cost: Money = 0.0
    estimated_walk_distance_km: Annotated[float, Field(ge=0)] = 0.0
    currency: str = "USD"
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    stops: list[PlanStopCreate] = Field(default_factory=list, max_length=MAX_STOPS)
    saved: bool = False

    def to_plan_create(self, *, idempotency_key: str | None = None) -> PlanCreate:
        if self.start_time is None:
            raise ValueError("Itinerary has no start_time and cannot be saved.")
        return PlanCreate(
            title=self.title or "Evening plan",
            start_time=self.start_time,
            estimated_cost=self.estimated_cost,
            estimated_walk_distance_km=self.estimated_walk_distance_km,
            latitude=self.latitude,
            longitude=self.longitude,
            stops=list(self.stops),
            idempotency_key=idempotency_key,
        )

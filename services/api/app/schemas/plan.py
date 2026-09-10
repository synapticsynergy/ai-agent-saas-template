"""Plan API schemas.

These models are the source of truth for the itinerary contract. They are
exported to JSON Schema and to TypeScript in ``packages/contracts`` so the web
app, the agent and the MCP tools all agree on one shape.
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


class PlanStopBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(min_length=1, max_length=200)
    category: StopCategory
    start_time: datetime
    end_time: datetime
    latitude: Latitude
    longitude: Longitude
    estimated_cost: Money = 0.0
    reason: str = Field(default="", max_length=2000)
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
    """Payload for creating a plan.

    ``organization_id`` and ``created_by_user_id`` are deliberately absent: they
    come from the verified principal, never from the request body. A client (or
    a model) that tries to set them is ignored, because there is nowhere to put
    them.
    """

    status: PlanStatus = "saved"
    stops: list[PlanStopCreate] = Field(default_factory=list, max_length=20)
    agent_run_id: str | None = Field(default=None, max_length=64)
    # Optional client-supplied key that makes a repeated save idempotent.
    idempotency_key: str | None = Field(default=None, max_length=128)


class PlanUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    status: PlanStatus | None = None
    notes: str | None = Field(default=None, max_length=4000)
    stops: list[PlanStopCreate] | None = Field(default=None, max_length=20)


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

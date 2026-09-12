"""Planning constraints extracted from a user's request.

The model's job is to turn free text into this structure. Everything downstream
operates on the structure, not on prose — which is what makes the planner
testable and the agent's behaviour auditable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field
from saas_contracts.plan import StopCategory

DEFAULT_CATEGORIES: list[StopCategory] = ["dinner", "music", "drinks"]


class PlanningRequest(BaseModel):
    """Structured constraints for one planning run."""

    latitude: Annotated[float, Field(ge=-90, le=90)]
    longitude: Annotated[float, Field(ge=-180, le=180)]
    start_time: datetime

    categories: list[StopCategory] = Field(
        default_factory=lambda: DEFAULT_CATEGORIES.copy(),
        max_length=6,
        description="Stop types to include, in visit order.",
    )
    budget: Annotated[float, Field(ge=0)] | None = Field(
        default=None, description="Total budget for one person, in the local currency."
    )
    max_walk_km: Annotated[float, Field(gt=0, le=25)] = 2.5
    music_genre: str = Field(default="", description='e.g. "jazz"; empty means any.')

    # Hard constraint: a venue that cannot accommodate a dietary need is not a
    # candidate at all, so these are passed to search as a filter.
    dietary_tags: list[str] = Field(default_factory=list, max_length=6)

    # Soft preference: "quiet", "patio", "date-night". These raise a candidate's
    # score but never exclude one — filtering on atmosphere silently discards
    # affordable options and produces plans that miss the stated budget.
    preference_tags: list[str] = Field(default_factory=list, max_length=10)
    party_size: Annotated[int, Field(ge=1, le=20)] = 2

    def with_budget(self, budget: float | None) -> PlanningRequest:
        return self.model_copy(update={"budget": budget})

    def with_genre(self, genre: str) -> PlanningRequest:
        return self.model_copy(update={"music_genre": genre})

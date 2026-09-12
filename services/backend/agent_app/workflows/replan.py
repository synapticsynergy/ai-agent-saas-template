"""Conversational revision of an existing itinerary.

Follow-ups like "make it cheaper" or "replace the music with jazz" adjust the
:class:`PlanningRequest` and rebuild, rather than asking a model to edit
structured state in place. Rebuilding from constraints keeps every invariant
the planner enforces — ordering, dwell times, walkability — instead of trusting
the model to preserve them.
"""

from __future__ import annotations

from dataclasses import dataclass

from saas_contracts.plan import Itinerary

from agent_app.workflows.planner import PlannerTools, build_itinerary
from agent_app.workflows.request import PlanningRequest

# How much cheaper "make it cheaper" should aim for.
CHEAPER_FACTOR = 0.7
MIN_BUDGET = 20.0


@dataclass(frozen=True, slots=True)
class Revision:
    """A described change to the planning constraints."""

    request: PlanningRequest
    summary: str


def make_cheaper(request: PlanningRequest, current: Itinerary) -> Revision:
    """Target a materially lower budget than the current plan actually costs.

    Anchoring on the current *cost* rather than the previous budget means a
    repeated "cheaper" keeps making progress instead of stalling against a
    budget the plan was already well under.
    """
    baseline = current.estimated_cost or request.budget or 100.0
    target = max(MIN_BUDGET, round(baseline * CHEAPER_FACTOR, 2))

    return Revision(
        request=request.with_budget(target),
        summary=f"Targeting about ${target:.0f} instead of ${baseline:.0f}.",
    )


def change_music_genre(request: PlanningRequest, genre: str) -> Revision:
    normalized = genre.strip().lower()
    if not normalized:
        raise ValueError("A genre is required.")

    updated = request.with_genre(normalized)
    if "music" not in updated.categories:
        updated = updated.model_copy(update={"categories": [*updated.categories, "music"]})

    return Revision(request=updated, summary=f"Looking for {normalized} instead.")


def set_categories(request: PlanningRequest, categories: list[str]) -> Revision:
    if not categories:
        raise ValueError("At least one category is required.")

    updated = request.model_copy(update={"categories": categories})
    return Revision(
        request=updated,
        summary="Rebuilding as " + " → ".join(categories) + ".",
    )


def tighten_walk(request: PlanningRequest, max_km: float) -> Revision:
    if max_km <= 0:
        raise ValueError("max_km must be positive.")
    return Revision(
        request=request.model_copy(update={"max_walk_km": max_km}),
        summary=f"Keeping everything within {max_km:.1f} km.",
    )


async def apply(revision: Revision, tools: PlannerTools) -> Itinerary:
    return await build_itinerary(revision.request, tools)

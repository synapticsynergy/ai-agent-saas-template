"""Deterministic itinerary construction.

This is where the reference application's actual planning happens, and it is
deliberately model-free. The model turns a sentence into a
:class:`PlanningRequest` and narrates the result; assembling stops, checking
walkability and keeping to a budget are ordinary code.

That split is the template's central principle applied to the agent itself
(docs/DESIGN_PRINCIPLES.md): the nondeterministic part stays small and the part
you would want to test, audit and reason about stays deterministic.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from saas_contracts.plan import Itinerary, PlanStopCreate, StopCategory
from saas_contracts.tools import Event, Place, Route

from agent_app.workflows.request import PlanningRequest
from agent_app.workflows.scoring import (
    allocate_budget,
    score_event,
    score_place,
    total_cost,
)

# How long people actually spend at each kind of stop.
DWELL_MINUTES: dict[str, int] = {
    "dinner": 90,
    "music": 105,
    "drinks": 75,
    "activity": 75,
    "dessert": 45,
    "coffee": 40,
}
TRANSITION_BUFFER_MINUTES = 15

SearchPlaces = Callable[..., Awaitable[list[Place]]]
SearchEvents = Callable[..., Awaitable[list[Event]]]
BuildRoute = Callable[..., Awaitable[Route]]


class PlannerTools:
    """The capability surface the planner needs.

    Passing tools in rather than importing them keeps the planner independent of
    MCP, so tests exercise the real planning logic against stubs.
    """

    def __init__(
        self, search_places: SearchPlaces, search_events: SearchEvents, build_route: BuildRoute
    ) -> None:
        self.search_places = search_places
        self.search_events = search_events
        self.build_route = build_route


async def build_itinerary(request: PlanningRequest, tools: PlannerTools) -> Itinerary:
    """Assemble an itinerary that satisfies the request as closely as possible.

    Never raises on "nothing found": a category with no candidates is skipped
    and the itinerary is built from what remains, because a partial plan the
    user can react to beats an error.
    """
    budget_per_person = request.budget / request.party_size if request.budget is not None else None
    remaining = budget_per_person

    stops: list[PlanStopCreate] = []
    cursor = request.start_time
    preferred_tags = frozenset(tag.lower() for tag in request.preference_tags)

    for index, category in enumerate(request.categories):
        # Divide what is left across the stops still to come, so the first stop
        # cannot consume the whole budget.
        allowance = (
            allocate_budget(remaining, list(request.categories[index:]))
            if remaining is not None
            else None
        )

        stop = await _choose_stop(
            category=category,
            request=request,
            tools=tools,
            at=cursor,
            remaining_budget=allowance,
            preferred_tags=preferred_tags,
        )
        if stop is None:
            continue

        stops.append(stop)
        if remaining is not None:
            remaining = max(0.0, remaining - stop.estimated_cost)
        cursor = stop.end_time + timedelta(minutes=TRANSITION_BUFFER_MINUTES)

    walk_km = 0.0
    if len(stops) >= 2:
        route = await tools.build_route(
            stops=[{"latitude": s.latitude, "longitude": s.longitude} for s in stops],
            names=[s.name for s in stops],
            mode="walk",
        )
        walk_km = route.total_distance_km

    return Itinerary(
        title=_title(stops),
        start_time=stops[0].start_time if stops else request.start_time,
        estimated_cost=total_cost([s.estimated_cost for s in stops], request.party_size),
        estimated_walk_distance_km=round(walk_km, 2),
        latitude=request.latitude,
        longitude=request.longitude,
        stops=stops,
    )


async def _choose_stop(
    *,
    category: StopCategory,
    request: PlanningRequest,
    tools: PlannerTools,
    at: datetime,
    remaining_budget: float | None,
    preferred_tags: frozenset[str],
) -> PlanStopCreate | None:
    dwell = DWELL_MINUTES.get(category, 60)

    if category == "music":
        stop = await _choose_event_stop(
            request=request, tools=tools, at=at, remaining_budget=remaining_budget
        )
        if stop is not None:
            return stop
        # No live event fits; fall through and pick a music venue instead.

    # Only dietary needs narrow the candidate set. Atmosphere preferences are
    # applied by the scorer, so a "quiet" preference cannot quietly discard
    # every venue the user can actually afford.
    places = await tools.search_places(
        latitude=request.latitude,
        longitude=request.longitude,
        category=category,
        radius_km=request.max_walk_km,
        limit=15,
        tags=list(request.dietary_tags),
    )
    if not places:
        return None

    from agent_app.workflows.geo import distance_km

    best = max(
        places,
        key=lambda place: score_place(
            place,
            distance_km=distance_km(
                request.latitude, request.longitude, place.latitude, place.longitude
            ),
            remaining_budget=remaining_budget,
            preferred_tags=preferred_tags,
        ),
    )

    return PlanStopCreate(
        name=best.name,
        category=category,
        start_time=at,
        end_time=at + timedelta(minutes=dwell),
        latitude=best.latitude,
        longitude=best.longitude,
        estimated_cost=best.typical_cost_per_person,
        reason=_place_reason(best, remaining_budget),
        external_id=best.id,
        address=best.address or None,
    )


async def _choose_event_stop(
    *,
    request: PlanningRequest,
    tools: PlannerTools,
    at: datetime,
    remaining_budget: float | None,
) -> PlanStopCreate | None:
    events = await tools.search_events(
        latitude=request.latitude,
        longitude=request.longitude,
        start_after=at,
        start_before=at + timedelta(hours=4),
        radius_km=request.max_walk_km,
        genre=request.music_genre,
        max_ticket_price=remaining_budget,
        limit=15,
    )
    if not events:
        return None

    from agent_app.workflows.geo import distance_km

    best = max(
        events,
        key=lambda event: score_event(
            event,
            distance_km=distance_km(
                request.latitude, request.longitude, event.latitude, event.longitude
            ),
            remaining_budget=remaining_budget,
            preferred_genre=request.music_genre,
        ),
    )

    return PlanStopCreate(
        name=f"{best.name} at {best.venue_name}" if best.venue_name else best.name,
        category="music",
        start_time=best.start_time,
        end_time=best.end_time,
        latitude=best.latitude,
        longitude=best.longitude,
        estimated_cost=best.ticket_price,
        reason=_event_reason(best),
        external_id=best.id,
    )


def _place_reason(place: Place, remaining_budget: float | None) -> str:
    parts = [f"Rated {place.rating:.1f}"]
    if place.typical_cost_per_person:
        parts.append(f"about ${place.typical_cost_per_person:.0f} per person")
    if remaining_budget is not None and place.typical_cost_per_person <= remaining_budget:
        parts.append("within the remaining budget")
    if place.tags:
        parts.append(", ".join(place.tags[:2]))
    return "; ".join(parts) + "."


def _event_reason(event: Event) -> str:
    when = event.start_time.strftime("%-I:%M %p")
    price = "free" if event.ticket_price == 0 else f"${event.ticket_price:.0f}"
    genre = f"{event.genre} " if event.genre else ""
    return f"Live {genre}set at {when}, {price}."


def _title(stops: list[PlanStopCreate]) -> str:
    if not stops:
        return "Evening plan"
    categories = [stop.category for stop in stops]
    if "music" in categories:
        return "Dinner and live music"
    if "drinks" in categories and "dinner" in categories:
        return "Dinner and drinks"
    return "Evening plan"

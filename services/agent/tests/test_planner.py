"""Planner tests.

The planner is the part of the agent that decides what actually ends up in an
itinerary, and it runs without a model — so it can be tested like any other
code, with exact assertions rather than "the output looks about right".
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from agent_app.workflows.planner import TRANSITION_BUFFER_MINUTES, build_itinerary
from agent_app.workflows.request import PlanningRequest
from tests.conftest import LAT, LON, TONIGHT, StubTools


class TestStructure:
    async def test_builds_a_stop_per_requested_category(
        self, tools: StubTools, base_request: PlanningRequest
    ) -> None:
        itinerary = await build_itinerary(base_request, tools.planner_tools)
        assert [stop.category for stop in itinerary.stops] == ["dinner", "music", "drinks"]

    async def test_stops_are_in_chronological_order(
        self, tools: StubTools, base_request: PlanningRequest
    ) -> None:
        itinerary = await build_itinerary(base_request, tools.planner_tools)
        starts = [stop.start_time for stop in itinerary.stops]
        assert starts == sorted(starts)

    async def test_stops_do_not_overlap(
        self, tools: StubTools, base_request: PlanningRequest
    ) -> None:
        itinerary = await build_itinerary(base_request, tools.planner_tools)
        for earlier, later in zip(itinerary.stops, itinerary.stops[1:], strict=False):
            assert later.start_time >= earlier.end_time

    async def test_a_transition_buffer_separates_place_stops(self, tools: StubTools) -> None:
        request = PlanningRequest(
            latitude=LAT, longitude=LON, start_time=TONIGHT, categories=["dinner", "drinks"]
        )
        itinerary = await build_itinerary(request, tools.planner_tools)
        gap = itinerary.stops[1].start_time - itinerary.stops[0].end_time
        assert gap == timedelta(minutes=TRANSITION_BUFFER_MINUTES)

    async def test_every_stop_explains_itself(
        self, tools: StubTools, base_request: PlanningRequest
    ) -> None:
        itinerary = await build_itinerary(base_request, tools.planner_tools)
        assert all(stop.reason for stop in itinerary.stops)

    async def test_the_first_stop_starts_when_requested(self, tools: StubTools) -> None:
        request = PlanningRequest(
            latitude=LAT, longitude=LON, start_time=TONIGHT, categories=["dinner"]
        )
        itinerary = await build_itinerary(request, tools.planner_tools)
        assert itinerary.stops[0].start_time == TONIGHT

    async def test_the_result_is_saveable(
        self, tools: StubTools, base_request: PlanningRequest
    ) -> None:
        itinerary = await build_itinerary(base_request, tools.planner_tools)
        payload = itinerary.to_plan_create(idempotency_key="run_1")
        assert payload.title
        assert len(payload.stops) == len(itinerary.stops)


class TestToolUsage:
    async def test_events_are_searched_for_a_music_stop(
        self, tools: StubTools, base_request: PlanningRequest
    ) -> None:
        await build_itinerary(base_request, tools.planner_tools)
        assert tools.called("search_events")

    async def test_places_are_searched_for_every_non_music_category(
        self, tools: StubTools, base_request: PlanningRequest
    ) -> None:
        await build_itinerary(base_request, tools.planner_tools)
        assert tools.call_count("search_places") >= 2

    async def test_a_route_is_built_for_a_multi_stop_plan(
        self, tools: StubTools, base_request: PlanningRequest
    ) -> None:
        itinerary = await build_itinerary(base_request, tools.planner_tools)
        assert tools.called("build_route")
        assert itinerary.estimated_walk_distance_km > 0

    async def test_no_route_is_built_for_a_single_stop(self, tools: StubTools) -> None:
        request = PlanningRequest(
            latitude=LAT, longitude=LON, start_time=TONIGHT, categories=["dinner"]
        )
        itinerary = await build_itinerary(request, tools.planner_tools)
        assert not tools.called("build_route")
        assert itinerary.estimated_walk_distance_km == 0.0


class TestBudget:
    async def test_a_tight_budget_selects_cheaper_venues(self, tools: StubTools) -> None:
        generous = await build_itinerary(
            PlanningRequest(latitude=LAT, longitude=LON, start_time=TONIGHT, budget=400.0),
            tools.planner_tools,
        )
        frugal = await build_itinerary(
            PlanningRequest(latitude=LAT, longitude=LON, start_time=TONIGHT, budget=60.0),
            tools.planner_tools,
        )
        assert frugal.estimated_cost < generous.estimated_cost

    async def test_a_realistic_budget_is_respected(self, tools: StubTools) -> None:
        itinerary = await build_itinerary(
            PlanningRequest(
                latitude=LAT, longitude=LON, start_time=TONIGHT, budget=100.0, party_size=1
            ),
            tools.planner_tools,
        )
        assert itinerary.estimated_cost <= 100.0

    async def test_cost_is_multiplied_by_party_size(self, tools: StubTools) -> None:
        solo = await build_itinerary(
            PlanningRequest(
                latitude=LAT, longitude=LON, start_time=TONIGHT, categories=["dinner"], party_size=1
            ),
            tools.planner_tools,
        )
        four = await build_itinerary(
            PlanningRequest(
                latitude=LAT, longitude=LON, start_time=TONIGHT, categories=["dinner"], party_size=4
            ),
            tools.planner_tools,
        )
        assert four.estimated_cost == pytest.approx(solo.estimated_cost * 4)

    async def test_an_impossible_budget_still_produces_an_honest_plan(
        self, tools: StubTools
    ) -> None:
        """Returning nothing would be useless; misreporting the cost would be worse."""
        itinerary = await build_itinerary(
            PlanningRequest(
                latitude=LAT, longitude=LON, start_time=TONIGHT, budget=1.0, party_size=1
            ),
            tools.planner_tools,
        )
        assert itinerary.stops
        assert itinerary.estimated_cost > 1.0


class TestPreferences:
    async def test_a_genre_preference_reaches_the_event_search(self, tools: StubTools) -> None:
        request = PlanningRequest(
            latitude=LAT, longitude=LON, start_time=TONIGHT, music_genre="jazz"
        )
        itinerary = await build_itinerary(request, tools.planner_tools)

        music = next(stop for stop in itinerary.stops if stop.category == "music")
        assert music.external_id in {"e_jazz_free", "e_jazz_paid"}

    async def test_a_walk_limit_excludes_distant_venues(self, tools: StubTools) -> None:
        request = PlanningRequest(
            latitude=LAT,
            longitude=LON,
            start_time=TONIGHT,
            categories=["dinner"],
            max_walk_km=0.5,
        )
        itinerary = await build_itinerary(request, tools.planner_tools)
        # The distant, expensive option is 2km away and must not be chosen.
        assert itinerary.stops[0].external_id != "d_posh"


class TestDegradedCases:
    async def test_a_category_with_no_candidates_is_skipped(self) -> None:
        tools = StubTools(places={"dinner": [], "drinks": []}, events=[])
        request = PlanningRequest(
            latitude=LAT, longitude=LON, start_time=TONIGHT, categories=["dinner", "drinks"]
        )
        itinerary = await build_itinerary(request, tools.planner_tools)
        assert itinerary.stops == []
        assert itinerary.estimated_cost == 0.0

    async def test_music_falls_back_to_a_venue_when_no_event_fits(self) -> None:
        """No live event tonight should not mean no music stop."""
        tools = StubTools(events=[])
        request = PlanningRequest(
            latitude=LAT, longitude=LON, start_time=TONIGHT, categories=["music"]
        )
        itinerary = await build_itinerary(request, tools.planner_tools)

        assert len(itinerary.stops) == 1
        assert itinerary.stops[0].category == "music"
        assert itinerary.stops[0].external_id in {"m_cheap", "m_mid"}

    async def test_a_partial_plan_is_produced_when_one_category_is_empty(self) -> None:
        tools = StubTools(places={**StubTools().places, "drinks": []})
        request = PlanningRequest(
            latitude=LAT, longitude=LON, start_time=TONIGHT, categories=["dinner", "drinks"]
        )
        itinerary = await build_itinerary(request, tools.planner_tools)
        assert [stop.category for stop in itinerary.stops] == ["dinner"]


class TestDeterminism:
    async def test_identical_requests_produce_identical_itineraries(
        self, base_request: PlanningRequest
    ) -> None:
        first = await build_itinerary(base_request, StubTools().planner_tools)
        second = await build_itinerary(base_request, StubTools().planner_tools)
        assert first.model_dump() == second.model_dump()


class TestConstraintsVersusPreferences:
    """A preference must never silently exclude affordable options.

    Regression guard: treating "somewhere quiet" as a hard filter narrowed the
    candidate set to the expensive venues that happened to carry the tag, and
    produced a plan that missed the stated budget.
    """

    async def test_an_atmosphere_preference_does_not_filter_candidates(
        self, tools: StubTools
    ) -> None:
        request = PlanningRequest(
            latitude=LAT,
            longitude=LON,
            start_time=TONIGHT,
            categories=["dinner"],
            preference_tags=["quiet"],
        )
        await build_itinerary(request, tools.planner_tools)

        call = next(kwargs for name, kwargs in tools.calls if name == "search_places")
        assert call["tags"] == []

    async def test_a_dietary_need_does_filter_candidates(self, tools: StubTools) -> None:
        request = PlanningRequest(
            latitude=LAT,
            longitude=LON,
            start_time=TONIGHT,
            categories=["dinner"],
            dietary_tags=["vegan"],
        )
        await build_itinerary(request, tools.planner_tools)

        call = next(kwargs for name, kwargs in tools.calls if name == "search_places")
        assert call["tags"] == ["vegan"]

    async def test_a_preference_still_stays_inside_the_budget(
        self, tools: StubTools
    ) -> None:
        request = PlanningRequest(
            latitude=LAT,
            longitude=LON,
            start_time=TONIGHT,
            categories=["dinner", "drinks"],
            budget=120.0,
            party_size=2,
            preference_tags=["quiet", "date-night"],
        )
        itinerary = await build_itinerary(request, tools.planner_tools)
        assert itinerary.estimated_cost <= 120.0

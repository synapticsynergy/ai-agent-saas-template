"""Tool contract tests.

Each tool is exercised directly — no LLM, no MCP transport. What is asserted is
the *contract*: valid input produces a schema-conforming result, invalid input
is rejected, and provider failures map to typed, agent-legible errors.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from saas_contracts.tools import (
    BuildRouteInput,
    GeoPoint,
    GetPlaceDetailsInput,
    SearchEventsInput,
    SearchPlacesInput,
)

from mcp_server import tools
from mcp_server.providers import registry
from mcp_server.providers.base import ProviderTimeout, ProviderUnavailable
from mcp_server.tools.errors import map_exception
from tests.conftest import CITY_CENTER, TONIGHT

LAT, LON = CITY_CENTER


class TestSearchPlaces:
    async def test_returns_places_of_the_requested_category(self) -> None:
        result = await tools.search_places(
            SearchPlacesInput(latitude=LAT, longitude=LON, category="dinner")
        )
        assert result.total > 0
        assert result.items
        assert {place.category for place in result.items} == {"dinner"}
        assert result.provider == "fixture"

    async def test_output_conforms_to_the_schema(self) -> None:
        result = await tools.search_places(
            SearchPlacesInput(latitude=LAT, longitude=LON, category="drinks")
        )
        for place in result.items:
            assert place.id and place.name
            assert -90 <= place.latitude <= 90
            assert -180 <= place.longitude <= 180
            assert place.typical_cost_per_person >= 0
            assert 1 <= place.price_level <= 4

    async def test_results_are_deterministic(self) -> None:
        """Same query, same answer — otherwise tests and evals cannot assert."""
        query = SearchPlacesInput(latitude=LAT, longitude=LON, category="dinner")
        first = await tools.search_places(query)
        second = await tools.search_places(query)
        assert [p.id for p in first.items] == [p.id for p in second.items]

    async def test_price_ceiling_is_respected(self) -> None:
        result = await tools.search_places(
            SearchPlacesInput(latitude=LAT, longitude=LON, category="dinner", max_price_level=1)
        )
        assert result.items
        assert all(place.price_level <= 1 for place in result.items)

    async def test_tag_filter_narrows_results(self) -> None:
        unfiltered = await tools.search_places(
            SearchPlacesInput(latitude=LAT, longitude=LON, category="dinner")
        )
        filtered = await tools.search_places(
            SearchPlacesInput(latitude=LAT, longitude=LON, category="dinner", tags=["vegan"])
        )
        assert 0 < filtered.total < unfiltered.total

    async def test_limit_is_honoured(self) -> None:
        result = await tools.search_places(
            SearchPlacesInput(latitude=LAT, longitude=LON, category="dinner", limit=2)
        )
        assert len(result.items) <= 2

    async def test_tiny_radius_returns_no_results_rather_than_erroring(self) -> None:
        """Zero results is a normal outcome the agent must be able to replan around."""
        result = await tools.search_places(
            SearchPlacesInput(latitude=LAT, longitude=LON, category="dinner", radius_km=0.001)
        )
        assert result.total == 0
        assert result.items == []

    async def test_results_work_away_from_the_default_city(self) -> None:
        """The fixture is not hardcoded to one metro area."""
        tokyo = await tools.search_places(
            SearchPlacesInput(latitude=35.6762, longitude=139.6503, category="dinner")
        )
        assert tokyo.total > 0
        assert all(30 < place.latitude < 40 for place in tokyo.items)

    def test_out_of_range_coordinates_are_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SearchPlacesInput(latitude=120.0, longitude=LON, category="dinner")

    def test_unknown_category_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SearchPlacesInput(latitude=LAT, longitude=LON, category="skydiving")  # type: ignore[arg-type]


class TestSearchEvents:
    async def test_returns_events_inside_the_window(self) -> None:
        result = await tools.search_events(
            SearchEventsInput(
                latitude=LAT,
                longitude=LON,
                start_after=TONIGHT,
                start_before=TONIGHT + timedelta(hours=6),
            )
        )
        assert result.total > 0
        for event in result.items:
            assert TONIGHT <= event.start_time <= TONIGHT + timedelta(hours=6)
            assert event.end_time > event.start_time

    async def test_genre_filter(self) -> None:
        result = await tools.search_events(
            SearchEventsInput(
                latitude=LAT,
                longitude=LON,
                start_after=TONIGHT,
                start_before=TONIGHT + timedelta(hours=6),
                genre="jazz",
            )
        )
        assert result.total > 0
        assert {event.genre for event in result.items} == {"jazz"}

    async def test_price_ceiling_filters_out_expensive_tickets(self) -> None:
        result = await tools.search_events(
            SearchEventsInput(
                latitude=LAT,
                longitude=LON,
                start_after=TONIGHT,
                start_before=TONIGHT + timedelta(hours=6),
                max_ticket_price=10.0,
            )
        )
        assert all(event.ticket_price <= 10.0 for event in result.items)

    async def test_narrow_window_returns_fewer_events(self) -> None:
        wide = await tools.search_events(
            SearchEventsInput(
                latitude=LAT,
                longitude=LON,
                start_after=TONIGHT,
                start_before=TONIGHT + timedelta(hours=6),
            )
        )
        narrow = await tools.search_events(
            SearchEventsInput(
                latitude=LAT,
                longitude=LON,
                start_after=TONIGHT,
                start_before=TONIGHT + timedelta(minutes=61),
            )
        )
        assert narrow.total < wide.total

    async def test_inverted_window_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="start_before"):
            await tools.search_events(
                SearchEventsInput(
                    latitude=LAT,
                    longitude=LON,
                    start_after=TONIGHT,
                    start_before=TONIGHT - timedelta(hours=1),
                )
            )


class TestGetPlaceDetails:
    async def test_returns_full_record(self) -> None:
        details = await tools.get_place_details(GetPlaceDetailsInput(place_id="place_ancora"))
        assert details.name == "Ancora Kitchen"
        assert details.reservation_required is True
        assert details.description

    async def test_unknown_id_raises(self) -> None:
        with pytest.raises(ValueError, match="No place with id"):
            await tools.get_place_details(GetPlaceDetailsInput(place_id="place_nope"))


class TestBuildRoute:
    async def test_produces_one_leg_fewer_than_stops(self) -> None:
        route = await tools.build_route(
            BuildRouteInput(
                stops=[
                    GeoPoint(latitude=45.5219, longitude=-122.6820),
                    GeoPoint(latitude=45.5245, longitude=-122.6791),
                    GeoPoint(latitude=45.5258, longitude=-122.6772),
                ],
                names=["Dinner", "Music", "Drinks"],
            )
        )
        assert len(route.legs) == 2
        assert route.legs[0].from_name == "Dinner"
        assert route.legs[1].to_name == "Drinks"

    async def test_totals_match_the_sum_of_legs(self) -> None:
        route = await tools.build_route(
            BuildRouteInput(
                stops=[
                    GeoPoint(latitude=45.5219, longitude=-122.6820),
                    GeoPoint(latitude=45.5245, longitude=-122.6791),
                    GeoPoint(latitude=45.5258, longitude=-122.6772),
                ]
            )
        )
        assert route.total_distance_km == pytest.approx(
            sum(leg.distance_km for leg in route.legs), abs=0.01
        )
        assert route.total_duration_minutes == pytest.approx(
            sum(leg.duration_minutes for leg in route.legs), abs=0.1
        )

    async def test_unnamed_stops_get_positional_labels(self) -> None:
        route = await tools.build_route(
            BuildRouteInput(
                stops=[
                    GeoPoint(latitude=45.52, longitude=-122.68),
                    GeoPoint(latitude=45.53, longitude=-122.67),
                ]
            )
        )
        assert route.legs[0].from_name == "Stop 1"

    def test_a_single_stop_is_not_a_route(self) -> None:
        with pytest.raises(ValidationError):
            BuildRouteInput(stops=[GeoPoint(latitude=45.52, longitude=-122.68)])


class TestErrorMapping:
    """Provider failures must reach the agent as typed, actionable errors."""

    def test_timeout_maps_to_a_retryable_error(self) -> None:
        error = map_exception(ProviderTimeout("upstream slow"))
        assert error.code == "provider_timeout"
        assert error.retryable is True

    def test_provider_failure_maps_to_a_non_retryable_error(self) -> None:
        error = map_exception(ProviderUnavailable("bad gateway"))
        assert error.code == "provider_error"
        assert error.retryable is False

    def test_bad_arguments_map_to_invalid_arguments(self) -> None:
        error = map_exception(ValueError("start_before must be after start_after"))
        assert error.code == "invalid_arguments"
        assert error.retryable is False

    def test_unknown_exceptions_do_not_leak_internals(self) -> None:
        error = map_exception(RuntimeError("connection string: postgres://user:secret@host"))
        assert error.code == "internal_error"
        assert "secret" not in error.error

    async def test_a_timing_out_provider_surfaces_as_a_retryable_tool_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class TimingOutProvider:
            name = "stub"

            async def search(self, **_: object) -> list[object]:
                raise ProviderTimeout("provider took too long")

            async def details(self, _place_id: str) -> None:
                return None

        monkeypatch.setattr(registry, "places_provider", lambda: TimingOutProvider())

        with pytest.raises(ProviderTimeout):
            await tools.search_places(
                SearchPlacesInput(latitude=LAT, longitude=LON, category="dinner")
            )

        # The server-side handler is what converts it for the agent.
        error = map_exception(ProviderTimeout("provider took too long"))
        assert error.retryable is True


def test_fixture_dataset_is_internally_consistent() -> None:
    """Guard against a fixture edit that breaks every downstream test."""
    import json
    from pathlib import Path

    import saas_contracts.fixtures.providers as fixtures

    data = json.loads((Path(fixtures.__file__).parent / "data.json").read_text())
    place_ids = {place["id"] for place in data["places"]}

    assert len(place_ids) == len(data["places"]), "duplicate place ids"
    for event in data["events"]:
        assert event["venue_place_id"] in place_ids, f"{event['id']} references an unknown venue"
        assert event["duration_minutes"] > 0
    assert datetime.now(UTC)  # sanity: the module imports cleanly

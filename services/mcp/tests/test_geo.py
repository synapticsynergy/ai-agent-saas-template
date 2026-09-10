"""Geospatial helper tests."""

from __future__ import annotations

import pytest

from mcp_server.geo import haversine_km, travel_minutes, within_radius


class TestHaversine:
    def test_distance_to_itself_is_zero(self) -> None:
        assert haversine_km(45.5231, -122.6765, 45.5231, -122.6765) == 0.0

    def test_known_distance(self) -> None:
        """Roughly one degree of latitude is ~111 km."""
        assert haversine_km(45.0, -122.0, 46.0, -122.0) == pytest.approx(111.2, abs=0.5)

    def test_is_symmetric(self) -> None:
        forward = haversine_km(45.52, -122.67, 45.53, -122.68)
        backward = haversine_km(45.53, -122.68, 45.52, -122.67)
        assert forward == pytest.approx(backward)

    def test_city_block_scale_is_sane(self) -> None:
        km = haversine_km(45.5219, -122.6820, 45.5245, -122.6791)
        assert 0.2 < km < 0.5


class TestTravelMinutes:
    def test_walking_is_slower_than_transit(self) -> None:
        assert travel_minutes(2.0, "walk") > travel_minutes(2.0, "transit")

    def test_scales_with_distance(self) -> None:
        assert travel_minutes(2.0) == pytest.approx(2 * travel_minutes(1.0))

    def test_a_short_walk_is_a_few_minutes(self) -> None:
        assert 4 < travel_minutes(0.4, "walk") < 10

    def test_unknown_mode_falls_back_to_walking(self) -> None:
        assert travel_minutes(1.0, "teleport") == travel_minutes(1.0, "walk")


class TestWithinRadius:
    def test_point_inside(self) -> None:
        assert within_radius(45.5240, -122.6770, 45.5231, -122.6765, 1.0)

    def test_point_outside(self) -> None:
        assert not within_radius(45.6000, -122.6765, 45.5231, -122.6765, 1.0)

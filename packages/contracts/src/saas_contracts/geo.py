"""Geospatial helpers.

Lives in the contracts package because the MCP server and the agent both need
the same distance and travel-time arithmetic, and two independent copies would
be free to drift into disagreeing about whether a plan is walkable.

Pure functions: no I/O, no configuration, no clock.
"""

from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0088

# Comfortable urban walking pace, allowing for crossings and lights.
WALKING_SPEED_KMH = 4.5
TRANSIT_SPEED_KMH = 18.0
DRIVING_SPEED_KMH = 30.0

# Straight-line distance understates real street distance.
STREET_DISTANCE_FACTOR = 1.25

_SPEEDS = {
    "walk": WALKING_SPEED_KMH,
    "transit": TRANSIT_SPEED_KMH,
    "drive": DRIVING_SPEED_KMH,
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def travel_minutes(distance_km: float, mode: str = "walk") -> float:
    """Estimate travel time.

    A deliberate approximation for the fixture provider: a real routing
    provider replaces it behind the same interface.
    """
    speed = _SPEEDS.get(mode, WALKING_SPEED_KMH)
    return (distance_km * STREET_DISTANCE_FACTOR) / speed * 60


def within_radius(
    lat: float, lon: float, center_lat: float, center_lon: float, radius_km: float
) -> bool:
    return haversine_km(lat, lon, center_lat, center_lon) <= radius_km

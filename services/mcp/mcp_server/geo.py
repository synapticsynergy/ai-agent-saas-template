"""Pure geospatial helpers.

No I/O, no configuration, no clock. Everything here is directly unit-testable,
which is why route and budget reasoning lives in this module rather than inside
a tool handler.
"""

from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0088

# Comfortable urban walking pace, allowing for crossings and lights.
WALKING_SPEED_KMH = 4.5
TRANSIT_SPEED_KMH = 18.0
DRIVING_SPEED_KMH = 30.0

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

    Straight-line distance understates real street distance, so it is inflated
    by a routing factor. This is a deliberate approximation for the fixture
    provider — a real routing provider replaces it behind the same interface.
    """
    street_factor = 1.25
    speed = _SPEEDS.get(mode, WALKING_SPEED_KMH)
    return (distance_km * street_factor) / speed * 60


def within_radius(
    lat: float, lon: float, center_lat: float, center_lon: float, radius_km: float
) -> bool:
    return haversine_km(lat, lon, center_lat, center_lon) <= radius_km

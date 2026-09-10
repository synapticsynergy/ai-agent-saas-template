"""Provider selection.

One place decides which adapter is live, driven by environment configuration.
Tools never construct a provider directly, so tests can point the whole server
at fixtures with a single override.
"""

from __future__ import annotations

from functools import lru_cache

from saas_contracts.fixtures import (
    FixtureEventsProvider,
    FixturePlacesProvider,
    FixtureRouteProvider,
)

from mcp_server.config import settings
from mcp_server.providers.base import EventsProvider, PlacesProvider, RouteProvider


@lru_cache
def places_provider() -> PlacesProvider:
    if settings.places_provider == "http":
        from mcp_server.providers.http import HttpPlacesProvider

        return HttpPlacesProvider()
    return FixturePlacesProvider()


@lru_cache
def events_provider() -> EventsProvider:
    if settings.events_provider == "http":
        from mcp_server.providers.http import HttpEventsProvider

        return HttpEventsProvider()
    return FixtureEventsProvider()


@lru_cache
def route_provider() -> RouteProvider:
    # Only the fixture router ships with the template. Add an HTTP routing
    # adapter here when a real provider is configured.
    return FixtureRouteProvider()


def reset() -> None:
    """Test hook: clear memoised providers after changing configuration."""
    places_provider.cache_clear()
    events_provider.cache_clear()
    route_provider.cache_clear()

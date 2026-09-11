"""MCP test fixtures.

Every test runs against the deterministic fixture providers — no network, no
randomness, no wall-clock dependence beyond the explicit time windows a test
passes in. See docs/TESTING.md ("Tool Contract Tests").
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

# Pin the world these tests run in. `setdefault` is wrong here: the Makefile
# exports the developer's .env, so a real provider or credential would leak
# into the suite — which made these tests call a real API and pass only
# because failures fall back silently.
os.environ["APP_ENV"] = "local"
os.environ["PLACES_PROVIDER"] = "fixture"
os.environ["EVENTS_PROVIDER"] = "fixture"

import pytest

from mcp_server.context import CallerIdentity
from mcp_server.providers import registry

# A fixed evening, so assertions on event windows never depend on "now".
TONIGHT = datetime(2030, 6, 1, 18, 0, tzinfo=UTC)
CITY_CENTER = (45.5231, -122.6765)


@pytest.fixture(autouse=True)
def _reset_providers() -> None:
    registry.reset()


@pytest.fixture
def identity() -> CallerIdentity:
    return CallerIdentity(access_token="test-token", run_id="run_test_1")


@pytest.fixture
def evening_window() -> tuple[datetime, datetime]:
    return TONIGHT, TONIGHT + timedelta(hours=6)

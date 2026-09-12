"""save_plan authorization and identity-propagation tests.

The point of these tests: an MCP tool cannot write tenant data on its own
authority. It forwards the caller's assertion to the application API, and the
API decides. A denial from the API must surface to the agent as a typed,
non-retryable error rather than being swallowed or retried forever.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx
from saas_contracts.plan import Itinerary, PlanStopCreate

from mcp_server import tools
from mcp_server.api_client import ApiError
from mcp_server.config import settings
from mcp_server.context import (
    CallerIdentity,
    MissingIdentity,
    identity_from_headers,
    require_identity,
)
from mcp_server.tools.errors import map_exception

START = datetime(2030, 6, 1, 19, 0, tzinfo=UTC)
API = settings.api_base_url


def make_itinerary(stops: int = 2) -> Itinerary:
    return Itinerary(
        title="Test evening",
        start_time=START,
        estimated_cost=64.0,
        estimated_walk_distance_km=1.4,
        latitude=45.5231,
        longitude=-122.6765,
        stops=[
            PlanStopCreate(
                name=f"Stop {i + 1}",
                category="dinner" if i == 0 else "drinks",
                start_time=START + timedelta(hours=i * 2),
                end_time=START + timedelta(hours=i * 2 + 1),
                latitude=45.52 + i * 0.001,
                longitude=-122.68 + i * 0.001,
                estimated_cost=32.0,
                reason="Fits the budget.",
            )
            for i in range(stops)
        ],
    )


def plan_response(plan_id: str = "plan_1") -> dict[str, object]:
    itinerary = make_itinerary()
    return {
        "id": plan_id,
        "organization_id": "org_alpha",
        "created_by_user_id": "user_member",
        "status": "saved",
        "title": itinerary.title,
        "start_time": START.isoformat(),
        "estimated_cost": 64.0,
        "estimated_walk_distance_km": 1.4,
        "latitude": 45.5231,
        "longitude": -122.6765,
        "created_at": START.isoformat(),
        "updated_at": START.isoformat(),
        "stops": [
            {**stop.model_dump(mode="json"), "id": f"stop_{i}", "position": i}
            for i, stop in enumerate(itinerary.stops)
        ],
    }


class TestIdentityExtraction:
    def test_bearer_token_is_extracted(self) -> None:
        identity = identity_from_headers({"Authorization": "Bearer abc.def.ghi"})
        assert identity is not None
        assert identity.access_token == "abc.def.ghi"

    def test_header_casing_does_not_matter(self) -> None:
        assert identity_from_headers({"AUTHORIZATION": "bearer tok"}) is not None

    def test_missing_header_yields_no_identity(self) -> None:
        assert identity_from_headers({}) is None
        assert identity_from_headers(None) is None

    def test_non_bearer_scheme_is_ignored(self) -> None:
        assert identity_from_headers({"Authorization": "Basic dXNlcjpwYXNz"}) is None

    def test_require_identity_raises_when_absent(self) -> None:
        with pytest.raises(MissingIdentity):
            require_identity({})

    def test_correlation_headers_are_forwarded(self) -> None:
        identity = require_identity(
            {"Authorization": "Bearer tok", "x-run-id": "run_9", "x-request-id": "req_9"}
        )
        headers = identity.forward_headers
        assert headers["Authorization"] == "Bearer tok"
        assert headers["x-run-id"] == "run_9"
        assert headers["x-request-id"] == "req_9"


class TestSavePlanAuthorization:
    @respx.mock
    async def test_member_save_succeeds(self, identity: CallerIdentity) -> None:
        route = respx.post(f"{API}/plans").mock(
            return_value=httpx.Response(201, json=plan_response())
        )

        result = await tools.save_plan(make_itinerary(), identity)

        assert result.plan_id == "plan_1"
        assert result.stop_count == 2
        assert route.called

    @respx.mock
    async def test_viewer_save_is_denied_and_not_retryable(self, identity: CallerIdentity) -> None:
        """A viewer's agent can call the tool; the API still refuses to write."""
        respx.post(f"{API}/plans").mock(
            return_value=httpx.Response(
                403,
                json={
                    "code": "permission_denied",
                    "message": "Missing required permission: plans:write",
                    "detail": {"required_permission": "plans:write"},
                },
            )
        )

        with pytest.raises(ApiError) as exc:
            await tools.save_plan(make_itinerary(), identity)

        error = map_exception(exc.value)
        assert error.code == "permission_denied"
        assert error.retryable is False

    @respx.mock
    async def test_the_callers_token_is_forwarded_verbatim(self, identity: CallerIdentity) -> None:
        """The MCP server must not mint or substitute its own credential."""
        captured: dict[str, str] = {}

        def capture(request: httpx.Request) -> httpx.Response:
            captured.update(dict(request.headers))
            return httpx.Response(201, json=plan_response())

        respx.post(f"{API}/plans").mock(side_effect=capture)
        await tools.save_plan(make_itinerary(), identity)

        assert captured["authorization"] == f"Bearer {identity.access_token}"

    @respx.mock
    async def test_the_payload_carries_no_tenant_fields(self, identity: CallerIdentity) -> None:
        """Tenancy is the API's to decide, from the verified token."""
        captured: dict[str, object] = {}

        def capture(request: httpx.Request) -> httpx.Response:
            import json

            captured.update(json.loads(request.content))
            return httpx.Response(201, json=plan_response())

        respx.post(f"{API}/plans").mock(side_effect=capture)
        await tools.save_plan(make_itinerary(), identity)

        assert "organization_id" not in captured
        assert "created_by_user_id" not in captured

    @respx.mock
    async def test_api_outage_is_retryable(self, identity: CallerIdentity) -> None:
        respx.post(f"{API}/plans").mock(
            return_value=httpx.Response(503, json={"code": "unavailable", "message": "down"})
        )

        with pytest.raises(ApiError) as exc:
            await tools.save_plan(make_itinerary(), identity)

        assert map_exception(exc.value).retryable is True

    @respx.mock
    async def test_api_timeout_is_retryable(self, identity: CallerIdentity) -> None:
        respx.post(f"{API}/plans").mock(side_effect=httpx.TimeoutException("slow"))

        with pytest.raises(ApiError) as exc:
            await tools.save_plan(make_itinerary(), identity)

        error = map_exception(exc.value)
        assert error.code == "api_timeout"
        assert error.retryable is True


class TestSavePlanValidation:
    async def test_an_empty_itinerary_cannot_be_saved(self, identity: CallerIdentity) -> None:
        with pytest.raises(ValueError, match="no stops"):
            await tools.save_plan(make_itinerary(stops=0), identity)

    async def test_an_itinerary_without_a_start_time_cannot_be_saved(
        self, identity: CallerIdentity
    ) -> None:
        itinerary = make_itinerary()
        itinerary.start_time = None
        with pytest.raises(ValueError, match="start_time"):
            await tools.save_plan(itinerary, identity)


class TestIdempotency:
    @respx.mock
    async def test_the_run_id_is_used_as_a_default_idempotency_key(
        self, identity: CallerIdentity
    ) -> None:
        """A retried save must not create a second plan."""
        captured: dict[str, object] = {}

        def capture(request: httpx.Request) -> httpx.Response:
            import json

            captured.update(json.loads(request.content))
            return httpx.Response(201, json=plan_response())

        respx.post(f"{API}/plans").mock(side_effect=capture)
        await tools.save_plan(make_itinerary(), identity)

        assert captured["idempotency_key"] == identity.run_id

    @respx.mock
    async def test_an_explicit_key_wins(self, identity: CallerIdentity) -> None:
        captured: dict[str, object] = {}

        def capture(request: httpx.Request) -> httpx.Response:
            import json

            captured.update(json.loads(request.content))
            return httpx.Response(201, json=plan_response())

        respx.post(f"{API}/plans").mock(side_effect=capture)
        await tools.save_plan(make_itinerary(), identity, idempotency_key="tool_call_77")

        assert captured["idempotency_key"] == "tool_call_77"

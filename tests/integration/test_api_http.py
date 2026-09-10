"""End-to-end HTTP behaviour of the API against real Postgres.

Runs the ASGI app in-process rather than against a separate server: the same
request path, the same database, no port juggling in CI.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.auth.dependencies import get_principal
from app.auth.permissions import Principal
from app.main import app
from conftest import ORG_B, principal
from httpx import ASGITransport, AsyncClient

START = datetime(2030, 6, 1, 19, 0, tzinfo=UTC)

PLAN_BODY = {
    "title": "HTTP integration evening",
    "start_time": START.isoformat(),
    "estimated_cost": 64.0,
    "estimated_walk_distance_km": 1.4,
    "latitude": 45.5231,
    "longitude": -122.6765,
    "stops": [
        {
            "name": "Dinner",
            "category": "dinner",
            "start_time": START.isoformat(),
            "end_time": (START + timedelta(hours=1, minutes=30)).isoformat(),
            "latitude": 45.5219,
            "longitude": -122.6820,
            "estimated_cost": 42.0,
            "reason": "Fits the budget.",
        }
    ],
}


@pytest.fixture
async def client_as():
    def build(who: Principal | None) -> AsyncClient:
        async def override() -> Principal:
            if who is None:
                from app.errors import NotAuthenticated

                raise NotAuthenticated("Missing bearer token.")
            return who

        app.dependency_overrides[get_principal] = override
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    yield build
    app.dependency_overrides.clear()


class TestHealth:
    async def test_readiness_reports_every_dependency(self, client_as) -> None:
        async with client_as(None) as client:
            response = await client.get("/health/ready")

        body = response.json()
        assert body["checks"]["database"] is True
        assert body["checks"]["storage"] is True
        assert response.status_code == 200


class TestPlansOverHttp:
    async def test_member_can_create_and_read_back(self, client_as) -> None:
        who = principal("member", user_id="http_member")

        async with client_as(who) as client:
            created = await client.post("/plans", json=PLAN_BODY)
            assert created.status_code == 201
            plan_id = created.json()["id"]

            fetched = await client.get(f"/plans/{plan_id}")
            assert fetched.status_code == 200
            assert fetched.json()["title"] == "HTTP integration evening"

    async def test_unauthenticated_is_401(self, client_as) -> None:
        async with client_as(None) as client:
            assert (await client.get("/plans")).status_code == 401

    async def test_viewer_write_is_403(self, client_as) -> None:
        async with client_as(principal("viewer", user_id="http_viewer")) as client:
            response = await client.post("/plans", json=PLAN_BODY)

        assert response.status_code == 403
        assert response.json()["detail"]["required_permission"] == "plans:write"

    async def test_another_organization_gets_404(self, client_as) -> None:
        owner = principal("member", user_id="http_owner")
        async with client_as(owner) as client:
            plan_id = (await client.post("/plans", json=PLAN_BODY)).json()["id"]

        intruder = principal("member", organization_id=ORG_B, user_id="http_intruder")
        async with client_as(intruder) as client:
            assert (await client.get(f"/plans/{plan_id}")).status_code == 404

    async def test_a_forged_organization_id_in_the_body_is_ignored(
        self, client_as
    ) -> None:
        """The model may propose a tenant; the API takes it from the token."""
        who = principal("member", user_id="http_forger")

        async with client_as(who) as client:
            response = await client.post(
                "/plans",
                json={
                    **PLAN_BODY,
                    "organization_id": "org_attacker",
                    "created_by_user_id": "root",
                },
            )

        body = response.json()
        assert response.status_code == 201
        assert body["organization_id"] == who.organization_id
        assert body["created_by_user_id"] == who.user_id

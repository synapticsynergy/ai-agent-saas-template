"""HTTP-level tests: status codes, error envelope, auth enforcement."""

from __future__ import annotations

from typing import Any

from app.auth.permissions import Principal
from tests.api.conftest import sample_plan


class TestHealth:
    async def test_health_is_public(self, client_factory: Any) -> None:
        async with client_factory(None) as client:
            response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_readiness_reports_only_the_database(self, client_factory: Any) -> None:
        async with client_factory(None) as client:
            response = await client.get("/health/ready")
        assert set(response.json()["checks"]) == {"database"}


class TestAuthentication:
    async def test_unauthenticated_plan_list_is_401(self, client_factory: Any) -> None:
        async with client_factory(None) as client:
            response = await client.get("/plans")
        assert response.status_code == 401
        assert response.json()["code"] == "not_authenticated"

    async def test_unauthenticated_plan_create_is_401(self, client_factory: Any) -> None:
        async with client_factory(None) as client:
            response = await client.post("/plans", json=sample_plan().model_dump(mode="json"))
        assert response.status_code == 401

    async def test_me_reports_the_principals_permissions(
        self, client_factory: Any, member: Principal
    ) -> None:
        async with client_factory(member) as client:
            response = await client.get("/users/me")
        body = response.json()
        assert response.status_code == 200
        assert body["organization_id"] == member.organization_id
        assert "plans:write" in body["permissions"]


class TestPlanRoutes:
    async def test_member_can_create_and_read_back(
        self, client_factory: Any, member: Principal
    ) -> None:
        async with client_factory(member) as client:
            created = await client.post("/plans", json=sample_plan().model_dump(mode="json"))
            assert created.status_code == 201
            plan_id = created.json()["id"]

            fetched = await client.get(f"/plans/{plan_id}")
            assert fetched.status_code == 200
            assert fetched.json()["title"] == "Test evening"
            assert len(fetched.json()["stops"]) == 2

    async def test_viewer_write_is_403_with_the_required_permission_named(
        self, client_factory: Any, viewer: Principal
    ) -> None:
        async with client_factory(viewer) as client:
            response = await client.post("/plans", json=sample_plan().model_dump(mode="json"))
        assert response.status_code == 403
        body = response.json()
        assert body["code"] == "permission_denied"
        assert body["detail"]["required_permission"] == "plans:write"

    async def test_missing_plan_is_404(self, client_factory: Any, member: Principal) -> None:
        async with client_factory(member) as client:
            response = await client.get("/plans/does-not-exist")
        assert response.status_code == 404
        assert response.json()["code"] == "not_found"

    async def test_invalid_payload_is_422(self, client_factory: Any, member: Principal) -> None:
        async with client_factory(member) as client:
            response = await client.post("/plans", json={"title": ""})
        assert response.status_code == 422
        assert response.json()["code"] == "validation_failed"

    async def test_stop_ending_before_it_starts_is_rejected(
        self, client_factory: Any, member: Principal
    ) -> None:
        payload = sample_plan().model_dump(mode="json")
        payload["stops"][0]["end_time"] = payload["stops"][0]["start_time"]
        async with client_factory(member) as client:
            response = await client.post("/plans", json=payload)
        assert response.status_code == 422

    async def test_every_response_carries_a_request_id(
        self, client_factory: Any, member: Principal
    ) -> None:
        async with client_factory(member) as client:
            response = await client.get("/plans")
        assert response.headers["x-request-id"]

    async def test_supplied_request_id_is_echoed_for_correlation(
        self, client_factory: Any, member: Principal
    ) -> None:
        async with client_factory(member) as client:
            response = await client.get("/plans", headers={"x-request-id": "req-from-web"})
        assert response.headers["x-request-id"] == "req-from-web"

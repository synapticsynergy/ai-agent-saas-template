"""Test fixtures.

Unit and service tests run against an in-memory SQLite database so they need no
containers and stay fast. The integration suite (``tests/integration``) exercises
the same code against real Postgres and LocalStack; see docs/TESTING.md.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

# Pin the world these tests run in. `setdefault` is wrong here: the Makefile
# exports the developer's .env, so a real provider or credential would leak
# into the suite — which made these tests call a real API and pass only
# because failures fall back silently.
os.environ["APP_ENV"] = "local"
os.environ["AUTH_DEV_FIXTURE"] = "0"

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.auth.dependencies import get_principal
from app.auth.permissions import Principal, permissions_for_role
from app.errors import NotAuthenticated
from app.main import app
from app.models import Base
from app.persistence.postgres import get_session
from app.schemas.plan import PlanCreate, PlanStopCreate

ORG_A = "org_alpha"
ORG_B = "org_beta"


def make_principal(
    *,
    role: str = "member",
    organization_id: str = ORG_A,
    user_id: str = "user_1",
    permissions: set[str] | None = None,
) -> Principal:
    """Build a principal directly.

    Authorization tests construct principals here rather than minting JWTs: the
    permission set is the thing under test, and token verification is covered
    separately in ``test_workos_auth.py``.
    """
    return Principal(
        user_id=user_id,
        organization_id=organization_id,
        email=f"{user_id}@example.com",
        role=role,
        permissions=frozenset(permissions)
        if permissions is not None
        else permissions_for_role(role),
    )


@pytest.fixture
async def engine() -> AsyncIterator[object]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine: object) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False)  # type: ignore[arg-type]
    async with factory() as session:
        yield session


@pytest.fixture
def viewer() -> Principal:
    return make_principal(role="viewer", user_id="user_viewer")


@pytest.fixture
def member() -> Principal:
    return make_principal(role="member", user_id="user_member")


@pytest.fixture
def admin() -> Principal:
    return make_principal(role="admin", user_id="user_admin")


@pytest.fixture
def other_org_member() -> Principal:
    return make_principal(role="member", organization_id=ORG_B, user_id="user_other")


def sample_plan(title: str = "Test evening") -> PlanCreate:
    start = datetime(2030, 6, 1, 19, 0, tzinfo=UTC)
    return PlanCreate(
        title=title,
        start_time=start,
        estimated_cost=64.0,
        estimated_walk_distance_km=1.4,
        latitude=45.5231,
        longitude=-122.6765,
        stops=[
            PlanStopCreate(
                name="Dinner spot",
                category="dinner",
                start_time=start,
                end_time=start + timedelta(hours=1, minutes=30),
                latitude=45.5219,
                longitude=-122.6820,
                estimated_cost=42.0,
                reason="Fits the budget.",
            ),
            PlanStopCreate(
                name="Bar",
                category="drinks",
                start_time=start + timedelta(hours=2),
                end_time=start + timedelta(hours=3),
                latitude=45.5258,
                longitude=-122.6772,
                estimated_cost=22.0,
                reason="Short walk.",
            ),
        ],
    )


@pytest.fixture
def client_factory(session: AsyncSession):
    """Build an HTTP client bound to a specific principal (or to none)."""

    def _build(principal: Principal | None) -> AsyncClient:
        async def _session_override() -> AsyncIterator[AsyncSession]:
            yield session

        async def _principal_override() -> Principal:
            if principal is None:
                raise NotAuthenticated("Missing bearer token.")
            return principal

        app.dependency_overrides[get_session] = _session_override
        app.dependency_overrides[get_principal] = _principal_override
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    yield _build
    app.dependency_overrides.clear()

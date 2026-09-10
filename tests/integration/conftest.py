"""Integration test fixtures.

These tests run against *real* local infrastructure — Postgres and LocalStack —
started by `make infra-up`. They deliberately do not skip when it is missing:
a green run must mean the boundaries were actually exercised, not that the
suite quietly decided not to look.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

os.environ.setdefault("APP_ENV", "local")

from app.auth.permissions import Principal, permissions_for_role  # noqa: E402
from app.models import Base  # noqa: E402
from app.persistence.postgres import SessionFactory, _engine, dispose_engine  # noqa: E402

ORG_A = "org_integration_a"
ORG_B = "org_integration_b"


def principal(role: str = "member", organization_id: str = ORG_A, user_id: str = "user_a") -> Principal:
    return Principal(
        user_id=user_id,
        organization_id=organization_id,
        email=f"{user_id}@example.com",
        role=role,
        permissions=permissions_for_role(role),
    )


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def _schema() -> AsyncIterator[None]:
    """Ensure the schema exists, then clean up this suite's tenants."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    from sqlalchemy import delete

    from app.models import AgentRun, Plan

    async with SessionFactory() as session:
        for model in (Plan, AgentRun):
            await session.execute(
                delete(model).where(model.organization_id.in_([ORG_A, ORG_B]))
            )
        await session.commit()

    await dispose_engine()


@pytest_asyncio.fixture(loop_scope="session")
async def session() -> AsyncIterator[object]:
    async with SessionFactory() as db:
        yield db
        await db.rollback()


@pytest.fixture
def member() -> Principal:
    return principal("member")


@pytest.fixture
def viewer() -> Principal:
    return principal("viewer", user_id="user_viewer")


@pytest.fixture
def other_org() -> Principal:
    return principal("member", organization_id=ORG_B, user_id="user_b")

"""Deterministic local seed data.

Run with ``make seed``. Every id is fixed, so E2E tests and the local demo can
assert on known values, and re-running the seed is idempotent rather than
producing a growing pile of near-duplicate rows.

Refuses to run outside APP_ENV=local: seeding a shared environment with demo
tenants is almost never what someone meant to do.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.auth.permissions import permissions_for_role
from app.config import settings
from app.models import Plan, PlanStop, UserPreference
from app.persistence.postgres import SessionFactory, dispose_engine

DEMO_ORG_ID = "org_local_demo"
DEMO_USER_ID = "user_local_demo"
DEMO_PLAN_ID = "00000000-0000-4000-8000-000000000001"


def _tonight(hour: int) -> datetime:
    base = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    return base.replace(hour=0) + timedelta(hours=hour)


async def seed() -> None:
    try:
        await _seed()
    finally:
        # Dispose inside the same event loop that created the connections.
        await dispose_engine()


async def _seed() -> None:
    if not settings.is_local:
        raise SystemExit(
            f"Refusing to seed demo data with APP_ENV={settings.app_env}. "
            "Seeding is a local-development convenience only."
        )

    async with SessionFactory() as session:
        await session.execute(delete(Plan).where(Plan.id == DEMO_PLAN_ID))

        existing_pref = await session.scalar(
            select(UserPreference).where(
                UserPreference.organization_id == DEMO_ORG_ID,
                UserPreference.user_id == DEMO_USER_ID,
            )
        )
        if existing_pref is None:
            session.add(
                UserPreference(
                    organization_id=DEMO_ORG_ID,
                    user_id=DEMO_USER_ID,
                    default_budget=100.0,
                    max_walk_distance_km=2.5,
                    dietary_notes="No shellfish",
                    preferred_categories="dinner,music,drinks",
                )
            )

        session.add(
            Plan(
                id=DEMO_PLAN_ID,
                organization_id=DEMO_ORG_ID,
                created_by_user_id=DEMO_USER_ID,
                title="Example saved evening",
                status="saved",
                start_time=_tonight(19),
                estimated_cost=84.0,
                estimated_walk_distance_km=2.1,
                latitude=45.5231,
                longitude=-122.6765,
                notes="Seeded example plan. Safe to delete.",
                stops=[
                    PlanStop(
                        position=0,
                        name="Ancora Kitchen",
                        category="dinner",
                        start_time=_tonight(19),
                        end_time=_tonight(20) + timedelta(minutes=30),
                        latitude=45.5219,
                        longitude=-122.6820,
                        estimated_cost=46.0,
                        reason="Walkable, mid-range, matches the no-shellfish note.",
                        address="120 SW Alder St",
                    ),
                    PlanStop(
                        position=1,
                        name="The Lantern Room",
                        category="music",
                        start_time=_tonight(20) + timedelta(minutes=45),
                        end_time=_tonight(22),
                        latitude=45.5245,
                        longitude=-122.6791,
                        estimated_cost=22.0,
                        reason="Live jazz set starting at 8:45.",
                        address="55 NW Couch St",
                    ),
                    PlanStop(
                        position=2,
                        name="Nightjar",
                        category="drinks",
                        start_time=_tonight(22) + timedelta(minutes=15),
                        end_time=_tonight(23) + timedelta(minutes=30),
                        latitude=45.5258,
                        longitude=-122.6772,
                        estimated_cost=16.0,
                        reason="Six-minute walk from the venue, quiet enough to talk.",
                        address="410 NW 12th Ave",
                    ),
                ],
            )
        )

        await session.commit()

    print(f"Seeded organization {DEMO_ORG_ID} with plan {DEMO_PLAN_ID}")
    print(
        f"Demo user {DEMO_USER_ID} role=member permissions={sorted(permissions_for_role('member'))}"
    )


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()

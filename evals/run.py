"""Agent evaluation runner.

    make eval
    uv run --project services/agent python -m evals.run --threshold 0.9 --json results.json

Runs every scenario in ``dataset.json`` against the agent and scores the
structured outcome. Results are deterministic under the fixture providers, so
this is safe to gate CI on.

Authorization cases run with a viewer and a member principal and assert the
boundary held — the point being that "the agent must not be able to write as a
viewer" is a test, not a hope.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, Self

from ag_ui.core import EventType
from agent_app.runner import RunContext, run
from agent_app.tools.mcp_client import ToolCallError
from saas_contracts.plan import Itinerary

from evals.evaluators import CaseResult, RunRecord, evaluate

DATASET = Path(__file__).parent / "dataset.json"

# A fixed location and time, so every run is comparable.
EVAL_LATITUDE = 45.5231
EVAL_LONGITUDE = -122.6765

# Permissions by role, mirroring services/api/app/auth/permissions.py.
ROLE_PERMISSIONS = {
    "viewer": {"plans:read"},
    "member": {"plans:read", "plans:write", "agents:run"},
    "admin": {"plans:read", "plans:write", "plans:delete", "agents:run"},
}


class EvalMcpClient:
    """In-process MCP stand-in backed by the real fixture providers.

    Evaluations exercise the agent's planning and authorization behaviour, not
    the MCP transport (which has its own contract tests). Running the same
    fixture data in-process keeps evals fast and free of flaky network setup.
    """

    def __init__(self, *, role: str = "member", empty: bool = False) -> None:
        self.role = role
        self.empty = empty
        self.calls: list[str] = []
        self.save_error_code: str | None = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def search_places(self, **kwargs: Any) -> list[Any]:
        self.calls.append("search_places")
        if self.empty:
            return []
        from saas_contracts.fixtures import FixturePlacesProvider

        return await FixturePlacesProvider().search(
            latitude=kwargs["latitude"],
            longitude=kwargs["longitude"],
            category=kwargs["category"],
            radius_km=kwargs.get("radius_km", 2.5),
            max_price_level=kwargs.get("max_price_level", 4),
            limit=kwargs.get("limit", 15),
            tags=kwargs.get("tags", []),
        )

    async def search_events(self, **kwargs: Any) -> list[Any]:
        self.calls.append("search_events")
        if self.empty:
            return []
        from saas_contracts.fixtures import FixtureEventsProvider

        return await FixtureEventsProvider().search(
            latitude=kwargs["latitude"],
            longitude=kwargs["longitude"],
            start_after=kwargs["start_after"],
            start_before=kwargs["start_before"],
            radius_km=kwargs.get("radius_km", 2.5),
            genre=kwargs.get("genre", ""),
            max_ticket_price=kwargs.get("max_ticket_price"),
            limit=kwargs.get("limit", 15),
        )

    async def build_route(self, **kwargs: Any) -> Any:
        self.calls.append("build_route")
        from saas_contracts.fixtures import FixtureRouteProvider

        return await FixtureRouteProvider().build(
            points=[(s["latitude"], s["longitude"]) for s in kwargs["stops"]],
            names=kwargs.get("names", []),
            mode=kwargs.get("mode", "walk"),
        )

    async def save_plan(
        self, itinerary: dict[str, Any], idempotency_key: str | None
    ) -> Any:
        """Apply the same permission rule the application API applies."""
        self.calls.append("save_plan")

        if "plans:write" not in ROLE_PERMISSIONS.get(self.role, set()):
            self.save_error_code = "permission_denied"
            raise ToolCallError(
                "Missing required permission: plans:write",
                code="permission_denied",
                retryable=False,
            )

        return {
            "plan_id": f"plan_eval_{idempotency_key}",
            "status": "saved",
            "title": itinerary.get("title", ""),
            "estimated_cost": itinerary.get("estimated_cost", 0.0),
            "stop_count": len(itinerary.get("stops", [])),
        }


async def run_case(
    case: dict[str, Any], cases_by_id: dict[str, dict[str, Any]]
) -> RunRecord:
    import agent_app.runner as runner_module

    role = case.get("principal_role", "member")
    client = EvalMcpClient(role=role, empty=bool(case.get("empty_providers")))

    original = runner_module.McpToolClient
    runner_module.McpToolClient = lambda **_: client  # type: ignore[assignment,misc,return-value]

    try:
        context = RunContext(
            thread_id=f"eval_{case['id']}",
            run_id=f"run_{case['id']}",
            access_token="eval-token",
            latitude=EVAL_LATITUDE,
            longitude=EVAL_LONGITUDE,
        )

        previous: Itinerary | None = None
        started = time.monotonic()
        events: list[str] = []

        # Establish prior state for a follow-up case.
        parent_id = case.get("follow_up_to")
        if parent_id:
            async for _ in run(cases_by_id[parent_id]["input"], context):
                pass
            previous = context.itinerary
            # A save follow-up needs the user's approval already given.
            context.approved = True

        async for event in run(case["input"], context):
            events.append(
                str(
                    event.type.value
                    if isinstance(event.type, EventType)
                    else event.type
                )
            )

        latency_ms = int((time.monotonic() - started) * 1000)

    finally:
        runner_module.McpToolClient = original  # type: ignore[assignment]

    save_attempted = "save_plan" in client.calls
    return RunRecord(
        case_id=case["id"],
        itinerary=context.itinerary,
        tools_called=client.calls,
        events=events,
        save_attempted=save_attempted,
        save_succeeded=save_attempted and client.save_error_code is None,
        save_error_code=client.save_error_code,
        latency_ms=latency_ms,
        previous=previous,
        music_genre=context.request.music_genre if context.request else "",
    )


async def run_all(dataset: dict[str, Any]) -> list[CaseResult]:
    cases: list[dict[str, Any]] = dataset["cases"]
    cases_by_id = {case["id"]: case for case in cases}

    results: list[CaseResult] = []
    for case in cases:
        record = await run_case(case, cases_by_id)
        results.append(evaluate(record, case["expectations"]))
    return results


def report(results: list[CaseResult], threshold: float) -> bool:
    total_scores = sum(len(result.scores) for result in results)
    passed_scores = sum(
        1 for result in results for score in result.scores if score.passed
    )
    overall = passed_scores / total_scores if total_scores else 1.0

    print("\nAgent evaluation\n" + "=" * 60)
    for result in results:
        mark = "PASS" if result.passed else "FAIL"
        print(f"\n[{mark}] {result.case_id}")
        for score in result.scores:
            symbol = "  ok  " if score.passed else "  FAIL"
            print(f"{symbol} {score.name}: {score.detail}")

    passed_cases = sum(1 for result in results if result.passed)
    print("\n" + "=" * 60)
    print(f"cases:  {passed_cases}/{len(results)} passed")
    print(f"checks: {passed_scores}/{total_scores} passed ({overall:.0%})")
    print(f"threshold: {threshold:.0%}")

    return overall >= threshold


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the agent evaluation suite.")
    parser.add_argument(
        "--threshold",
        type=float,
        default=1.0,
        help="Minimum fraction of checks that must pass (default: 1.0).",
    )
    parser.add_argument("--json", type=Path, help="Write results to this file as JSON.")
    parser.add_argument("--case", help="Run a single case by id.")
    args = parser.parse_args()

    dataset = json.loads(DATASET.read_text())
    if args.case:
        dataset = {
            **dataset,
            "cases": [
                c
                for c in dataset["cases"]
                if c["id"] == args.case
                or c["id"]
                in {
                    c2.get("follow_up_to")
                    for c2 in dataset["cases"]
                    if c2["id"] == args.case
                }
            ],
        }
        if not dataset["cases"]:
            raise SystemExit(f"No such case: {args.case}")

    results = asyncio.run(run_all(dataset))

    if args.json:
        args.json.write_text(
            json.dumps(
                [
                    {
                        "case_id": result.case_id,
                        "passed": result.passed,
                        "pass_rate": result.pass_rate,
                        "scores": [
                            {"name": s.name, "passed": s.passed, "detail": s.detail}
                            for s in result.scores
                        ],
                    }
                    for result in results
                ],
                indent=2,
            )
            + "\n"
        )

    sys.exit(0 if report(results, args.threshold) else 1)


if __name__ == "__main__":
    main()

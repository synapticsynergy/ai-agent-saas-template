"""Run orchestration and streaming tests.

The MCP client is stubbed, so these tests cover event ordering, approval
gating and error handling without a network or a model.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from ag_ui.core import BaseEvent, EventType, TextMessageContentEvent
from saas_contracts.plan import Itinerary, PlanStopCreate

from agent_app.runner import RunContext, run
from agent_app.tools.mcp_client import ToolCallError
from tests.agent.conftest import LAT, LON, TONIGHT, StubTools


class StubMcpClient(StubTools):
    """StubTools with the McpToolClient surface the runner uses."""

    def __init__(self, *, save_error: ToolCallError | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._save_error = save_error
        self.saved: dict[str, Any] | None = None

    async def __aenter__(self) -> StubMcpClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def save_plan(
        self, itinerary: dict[str, Any], idempotency_key: str | None
    ) -> dict[str, Any]:
        self.calls.append(("save_plan", {"idempotency_key": idempotency_key}))
        if self._save_error is not None:
            raise self._save_error
        self.saved = itinerary
        return {
            "plan_id": "plan_saved_1",
            "status": "saved",
            "title": itinerary.get("title", ""),
            "estimated_cost": itinerary.get("estimated_cost", 0.0),
            "stop_count": len(itinerary.get("stops", [])),
        }


@pytest.fixture
def patch_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[StubMcpClient], StubMcpClient]:
    def _install(client: StubMcpClient) -> StubMcpClient:
        import agent_app.runner as runner_module

        monkeypatch.setattr(runner_module, "McpToolClient", lambda **_: client)
        return client

    return _install


def make_context(**overrides: Any) -> RunContext:
    defaults: dict[str, Any] = {
        "thread_id": "thread_1",
        "run_id": "run_1",
        "access_token": "token",
        "latitude": LAT,
        "longitude": LON,
        "start_time": TONIGHT,
    }
    defaults.update(overrides)
    return RunContext(**defaults)


async def collect(message: str, context: RunContext) -> list[BaseEvent]:
    return [event async for event in run(message, context)]


def types_of(events: list[BaseEvent]) -> list[EventType]:
    return [event.type for event in events]


def assistant_text(events: list[BaseEvent]) -> str:
    """Reassemble the assistant's message from its streamed deltas."""
    return "".join(e.delta for e in events if isinstance(e, TextMessageContentEvent))


def saved_itinerary() -> Itinerary:
    return Itinerary(
        title="Dinner and live music",
        start_time=TONIGHT,
        estimated_cost=90.0,
        stops=[
            PlanStopCreate(
                name="Saltbox Diner",
                category="dinner",
                start_time=TONIGHT,
                end_time=TONIGHT.replace(hour=20),
                latitude=LAT,
                longitude=LON,
                estimated_cost=18.0,
                reason="Cheap and close.",
            )
        ],
    )


class TestPlanningRun:
    async def test_a_run_starts_and_finishes(self, patch_client: Any) -> None:
        patch_client(StubMcpClient())
        events = types_of(await collect("Plan my evening", make_context()))

        assert events[0] == EventType.RUN_STARTED
        assert events[-1] == EventType.RUN_FINISHED

    async def test_progress_arrives_before_the_final_event(self, patch_client: Any) -> None:
        """Streaming is only useful if the UI can show progress mid-run."""
        patch_client(StubMcpClient())
        events = types_of(await collect("Plan my evening", make_context()))

        first_step = events.index(EventType.STEP_STARTED)
        assert first_step < events.index(EventType.RUN_FINISHED)

    async def test_tool_activity_is_visible(self, patch_client: Any) -> None:
        patch_client(StubMcpClient())
        events = types_of(await collect("Plan my evening", make_context()))

        assert EventType.TOOL_CALL_START in events
        assert EventType.TOOL_CALL_RESULT in events
        assert EventType.TOOL_CALL_END in events

    async def test_the_itinerary_is_published_as_state(self, patch_client: Any) -> None:
        patch_client(StubMcpClient())
        events = await collect("Plan my evening", make_context())

        snapshot = next(e for e in events if e.type == EventType.STATE_SNAPSHOT)
        itinerary = snapshot.snapshot["itinerary"]  # type: ignore[attr-defined]
        assert itinerary["stops"]
        assert itinerary["estimated_cost"] > 0

    async def test_state_is_published_before_the_narration(self, patch_client: Any) -> None:
        """The UI renders the itinerary from state, not from the prose."""
        patch_client(StubMcpClient())
        events = types_of(await collect("Plan my evening", make_context()))

        assert events.index(EventType.STATE_SNAPSHOT) < events.index(EventType.TEXT_MESSAGE_START)

    async def test_text_deltas_are_well_formed(self, patch_client: Any) -> None:
        patch_client(StubMcpClient())
        events = types_of(await collect("Plan my evening", make_context()))

        assert events.index(EventType.TEXT_MESSAGE_START) < events.index(
            EventType.TEXT_MESSAGE_CONTENT
        )
        assert events.index(EventType.TEXT_MESSAGE_CONTENT) < events.index(
            EventType.TEXT_MESSAGE_END
        )

    async def test_the_context_retains_the_itinerary_for_follow_ups(
        self, patch_client: Any
    ) -> None:
        patch_client(StubMcpClient())
        context = make_context()
        await collect("Plan my evening", context)

        assert context.itinerary is not None
        assert context.request is not None


class TestFailureHandling:
    async def test_a_search_failure_does_not_abort_the_run(self, patch_client: Any) -> None:
        """A provider outage should degrade the plan, not kill the stream."""
        client = StubMcpClient()

        async def failing_search(**_: Any) -> list[Any]:
            raise ToolCallError("provider down", code="provider_timeout", retryable=True)

        client.search_places = failing_search  # type: ignore[method-assign]
        patch_client(client)

        events = types_of(await collect("Plan my evening", make_context()))
        assert events[-1] == EventType.RUN_FINISHED
        assert EventType.RUN_ERROR not in events

    async def test_an_unexpected_failure_ends_with_a_run_error(
        self, patch_client: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import agent_app.runner as runner_module

        def explode(**_: Any) -> None:
            raise RuntimeError("boom")

        monkeypatch.setattr(runner_module, "McpToolClient", explode)

        events = await collect("Plan my evening", make_context())
        assert events[-1].type == EventType.RUN_ERROR

    async def test_the_stream_always_terminates(
        self, patch_client: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import agent_app.runner as runner_module

        def explode(**_: Any) -> None:
            raise RuntimeError("boom")

        monkeypatch.setattr(runner_module, "McpToolClient", explode)

        events = types_of(await collect("Plan my evening", make_context()))
        assert events[-1] in {EventType.RUN_FINISHED, EventType.RUN_ERROR}


class TestSaveApproval:
    async def test_an_unapproved_save_asks_rather_than_writing(self, patch_client: Any) -> None:
        client = patch_client(StubMcpClient())
        context = make_context(itinerary=saved_itinerary(), approved=False)

        events = await collect("Save this plan.", context)

        assert any(
            e.type == EventType.CUSTOM and e.name == "approval_requested"  # type: ignore[attr-defined]
            for e in events
        )
        assert not client.called("save_plan")

    async def test_an_approved_save_persists(self, patch_client: Any) -> None:
        client = patch_client(StubMcpClient())
        context = make_context(itinerary=saved_itinerary(), approved=True)

        await collect("Save this plan.", context)

        assert client.called("save_plan")
        assert context.itinerary is not None
        assert context.itinerary.plan_id == "plan_saved_1"
        assert context.itinerary.saved is True

    async def test_a_save_is_idempotent_on_the_run_id(self, patch_client: Any) -> None:
        client = patch_client(StubMcpClient())
        await collect("Save it.", make_context(itinerary=saved_itinerary(), approved=True))

        call = next(kwargs for name, kwargs in client.calls if name == "save_plan")
        assert call["idempotency_key"] == "run_1"

    async def test_a_denied_save_is_explained_and_not_retried(self, patch_client: Any) -> None:
        """Approval is not authorization: the API can still refuse."""
        client = patch_client(
            StubMcpClient(
                save_error=ToolCallError(
                    "Missing required permission: plans:write",
                    code="permission_denied",
                    retryable=False,
                )
            )
        )
        context = make_context(itinerary=saved_itinerary(), approved=True)

        events = await collect("Save this plan.", context)
        text = assistant_text(events)

        assert "permission" in text.lower()
        assert context.itinerary is not None
        assert context.itinerary.saved is False
        assert client.call_count("save_plan") == 1

    async def test_saving_with_nothing_planned_says_so(self, patch_client: Any) -> None:
        client = patch_client(StubMcpClient())
        events = await collect("Save this plan.", make_context(approved=True))

        text = assistant_text(events)
        assert "no itinerary" in text.lower()
        assert not client.called("save_plan")

    async def test_saving_does_not_replan(self, patch_client: Any) -> None:
        """ "Save it" must persist what the user saw, not a freshly built plan."""
        client = patch_client(StubMcpClient())
        await collect("Save it.", make_context(itinerary=saved_itinerary(), approved=True))

        assert not client.called("search_places")
        assert client.saved is not None
        assert client.saved["title"] == "Dinner and live music"


class TestFollowUps:
    async def test_make_it_cheaper_lowers_the_cost(self, patch_client: Any) -> None:
        patch_client(StubMcpClient())
        context = make_context()

        await collect("Plan my evening with dinner, music and drinks", context)
        original = context.itinerary
        assert original is not None

        await collect("Make it cheaper.", context)
        assert context.itinerary is not None
        assert context.itinerary.estimated_cost < original.estimated_cost

    async def test_replacing_the_music_with_jazz_changes_the_stop(self, patch_client: Any) -> None:
        patch_client(StubMcpClient())
        context = make_context()

        await collect("Plan my evening with dinner, music and drinks", context)
        await collect("Replace the live music with jazz.", context)

        assert context.request is not None
        assert context.request.music_genre == "jazz"
        assert context.itinerary is not None
        music = next(s for s in context.itinerary.stops if s.category == "music")
        assert music.external_id in {"e_jazz_free", "e_jazz_paid"}


class TestConstraintRoundTrip:
    """A follow-up must not lose the constraints of the original request.

    Regression guard: without the planning constraints surviving between runs,
    "make it cheaper" reparsed only those three words, found no budget, and
    returned a *more* expensive plan.
    """

    async def test_the_constraints_are_published_as_state(self, patch_client: Any) -> None:
        patch_client(StubMcpClient())
        events = await collect("Plan an evening under $80", make_context())

        snapshot = next(e for e in events if e.type == EventType.STATE_SNAPSHOT)
        state = snapshot.snapshot  # type: ignore[attr-defined]
        assert "planning_request" in state
        assert state["planning_request"]["budget"] == 80.0

    async def test_a_revision_keeps_the_original_budget(self, patch_client: Any) -> None:
        patch_client(StubMcpClient())
        context = make_context()

        await collect("Plan my evening with dinner and drinks under $80", context)
        assert context.request is not None
        assert context.request.budget == 80.0

        await collect("Make it cheaper.", context)
        assert context.request is not None
        assert context.request.budget is not None
        assert context.request.budget < 80.0

    async def test_a_revision_recovers_when_state_was_not_echoed_back(
        self, patch_client: Any
    ) -> None:
        """A caller that drops planning_request still gets a sane revision."""
        patch_client(StubMcpClient())

        first = make_context()
        await collect("Plan my evening with dinner and drinks under $80", first)
        original = first.itinerary
        assert original is not None

        # A fresh context carrying only the itinerary — no planning_request.
        second = make_context(itinerary=original)
        await collect("Make it cheaper.", second)

        assert second.itinerary is not None
        assert second.itinerary.estimated_cost < original.estimated_cost

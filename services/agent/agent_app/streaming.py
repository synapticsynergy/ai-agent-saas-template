"""AG-UI event emission.

The agent speaks AG-UI directly — the protocol CopilotKit already understands —
rather than inventing a parallel event vocabulary and translating (ADR-005).

Beyond text deltas, runs emit tool lifecycle events and state snapshots, so the
UI can show a live progress checklist and render the itinerary as application
state instead of parsing it out of prose.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from ag_ui.core import (
    BaseEvent,
    CustomEvent,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StateSnapshotEvent,
    StepFinishedEvent,
    StepStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
)
from saas_contracts.plan import Itinerary
from saas_contracts.streaming import ProgressStage


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class EventStream:
    """Builds the AG-UI events for one run.

    Each method returns events rather than writing them, so the transport (SSE
    here) stays separate from the protocol and both are testable on their own.
    """

    def __init__(self, thread_id: str, run_id: str) -> None:
        self.thread_id = thread_id
        self.run_id = run_id
        self._message_id: str | None = None

    # --- run lifecycle ----------------------------------------------------

    def run_started(self) -> BaseEvent:
        return RunStartedEvent(thread_id=self.thread_id, run_id=self.run_id)

    def run_finished(self, result: dict[str, Any] | None = None) -> BaseEvent:
        return RunFinishedEvent(thread_id=self.thread_id, run_id=self.run_id, result=result)

    def run_error(self, message: str, code: str | None = None) -> BaseEvent:
        return RunErrorEvent(message=message, code=code)

    # --- progress ---------------------------------------------------------

    def step_started(self, stage: ProgressStage) -> BaseEvent:
        return StepStartedEvent(step_name=stage.value)

    def step_finished(self, stage: ProgressStage) -> BaseEvent:
        return StepFinishedEvent(step_name=stage.value)

    # --- assistant text ---------------------------------------------------

    def message_start(self) -> BaseEvent:
        self._message_id = new_id("msg")
        return TextMessageStartEvent(message_id=self._message_id, role="assistant")

    def message_delta(self, text: str) -> BaseEvent:
        if self._message_id is None:
            raise RuntimeError("message_start() must be emitted before a delta.")
        return TextMessageContentEvent(message_id=self._message_id, delta=text)

    def message_end(self) -> BaseEvent:
        if self._message_id is None:
            raise RuntimeError("message_start() must be emitted before message_end().")
        event = TextMessageEndEvent(message_id=self._message_id)
        self._message_id = None
        return event

    # --- tools ------------------------------------------------------------

    def tool_start(self, tool_call_id: str, tool_name: str) -> BaseEvent:
        return ToolCallStartEvent(tool_call_id=tool_call_id, tool_call_name=tool_name)

    def tool_args(self, tool_call_id: str, arguments: dict[str, Any]) -> BaseEvent:
        return ToolCallArgsEvent(
            tool_call_id=tool_call_id, delta=json.dumps(arguments, default=str)
        )

    def tool_end(self, tool_call_id: str) -> BaseEvent:
        return ToolCallEndEvent(tool_call_id=tool_call_id)

    def tool_result(self, tool_call_id: str, content: Any) -> BaseEvent:
        return ToolCallResultEvent(
            message_id=new_id("msg"),
            tool_call_id=tool_call_id,
            content=json.dumps(content, default=str),
            role="tool",
        )

    # --- shared state -----------------------------------------------------

    def itinerary_state(self, itinerary: Itinerary) -> BaseEvent:
        """Publish the itinerary as shared agent/UI state.

        The itinerary is application state, not a transcript artefact, so the UI
        renders it from here rather than parsing the assistant's prose.
        """
        return StateSnapshotEvent(snapshot={"itinerary": itinerary.model_dump(mode="json")})

    def approval_requested(self, action: str, detail: dict[str, Any]) -> BaseEvent:
        """Ask the user to confirm a consequential action.

        Approval expresses intent only. The deterministic service still checks
        the principal's permission before the action runs.
        """
        return CustomEvent(
            name="approval_requested",
            value={"action": action, "detail": detail, "run_id": self.run_id},
        )


async def to_sse(events: AsyncIterator[BaseEvent]) -> AsyncIterator[dict[str, str]]:
    """Adapt AG-UI events to sse-starlette's message dicts."""
    async for event in events:
        yield {"event": str(event.type.value), "data": event.model_dump_json(by_alias=True)}

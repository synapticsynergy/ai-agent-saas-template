"""Run orchestration: request in, AG-UI event stream out.

One run does four things, in order:

1. parse the request into structured constraints,
2. call tools to gather candidates,
3. build the itinerary deterministically,
4. narrate the result.

Only steps 1 and 4 use the model. Steps 2 and 3 are ordinary code — see
``agent_app.workflows.planner`` for why.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import structlog
from ag_ui.core import BaseEvent, RunAgentInput
from saas_contracts.plan import Itinerary
from saas_contracts.streaming import ProgressStage

from agent_app.config import settings
from agent_app.streaming import EventStream, new_id
from agent_app.tools.mcp_client import McpToolClient, ToolCallError
from agent_app.workflows.parse import parse_with_rules
from agent_app.workflows.planner import PlannerTools, build_itinerary
from agent_app.workflows.replan import change_music_genre, make_cheaper, tighten_walk
from agent_app.workflows.request import PlanningRequest

log = structlog.get_logger(__name__)


class RunContext:
    """Everything one run needs that is not the user's words."""

    def __init__(
        self,
        *,
        thread_id: str,
        run_id: str,
        access_token: str | None,
        latitude: float,
        longitude: float,
        start_time: datetime | None = None,
        itinerary: Itinerary | None = None,
        request: PlanningRequest | None = None,
        approved: bool = False,
    ) -> None:
        self.thread_id = thread_id
        self.run_id = run_id
        self.access_token = access_token
        self.latitude = latitude
        self.longitude = longitude
        self.start_time = start_time
        self.itinerary = itinerary
        self.request = request
        # Set by the UI once the user confirms a consequential action. Intent
        # only — the API still checks permission.
        self.approved = approved


async def run(user_message: str, context: RunContext) -> AsyncIterator[BaseEvent]:
    """Execute one planning run, yielding AG-UI events as work completes."""
    stream = EventStream(context.thread_id, context.run_id)
    started = time.monotonic()

    yield stream.run_started()

    try:
        async with McpToolClient(
            access_token=context.access_token, run_id=context.run_id
        ) as client:
            async for event in _plan(user_message, context, stream, client):
                yield event

    except ToolCallError as exc:
        log.warning("run.tool_error", code=exc.code, retryable=exc.retryable)
        yield stream.run_error(str(exc), code=exc.code)
        return
    except Exception as exc:
        log.exception("run.failed", error=str(exc))
        yield stream.run_error("The planning run failed unexpectedly.", code="internal_error")
        return

    latency_ms = int((time.monotonic() - started) * 1000)
    log.info("run.finished", run_id=context.run_id, latency_ms=latency_ms)

    yield stream.run_finished(
        {
            "itinerary": context.itinerary.model_dump(mode="json") if context.itinerary else None,
            "latency_ms": latency_ms,
        }
    )


async def _plan(
    user_message: str,
    context: RunContext,
    stream: EventStream,
    client: McpToolClient,
) -> AsyncIterator[BaseEvent]:
    intent = classify(user_message)

    if intent == "save":
        async for event in _save(context, stream, client):
            yield event
        return

    yield stream.step_started(ProgressStage.LOCATING)
    request, note = _resolve_request(user_message, context, intent)
    context.request = request
    yield stream.step_finished(ProgressStage.LOCATING)

    tools = _instrumented_tools(client, stream)

    yield stream.step_started(ProgressStage.SEARCHING_EVENTS)
    yield stream.step_started(ProgressStage.SEARCHING_PLACES)

    async for event in tools.drain():
        yield event

    itinerary = await build_itinerary(request, tools.planner_tools)

    async for event in tools.drain():
        yield event

    yield stream.step_finished(ProgressStage.SEARCHING_PLACES)
    yield stream.step_finished(ProgressStage.SEARCHING_EVENTS)

    yield stream.step_started(ProgressStage.BUILDING_ITINERARY)
    context.itinerary = itinerary
    yield stream.itinerary_state(itinerary)
    yield stream.step_finished(ProgressStage.BUILDING_ITINERARY)

    yield stream.message_start()
    for chunk in _narrate(itinerary, request, note, intent):
        yield stream.message_delta(chunk)
    yield stream.message_end()


async def _save(
    context: RunContext, stream: EventStream, client: McpToolClient
) -> AsyncIterator[BaseEvent]:
    """Persist the current itinerary, asking for confirmation first.

    Two things are deliberately separate here:

    * **Approval** — the user's intent, collected by the UI. Without it we stop
      and ask.
    * **Authorization** — whether this principal may write plans. That is
      decided by the application API when save_plan runs, and an approved run
      can still be refused.
    """
    itinerary = context.itinerary

    if itinerary is None or not itinerary.stops:
        yield stream.message_start()
        yield stream.message_delta("There is no itinerary to save yet. Ask me to plan one first.")
        yield stream.message_end()
        return

    if not context.approved:
        yield stream.approval_requested(
            "save_plan",
            {
                "title": itinerary.title,
                "estimated_cost": itinerary.estimated_cost,
                "stop_count": len(itinerary.stops),
            },
        )
        yield stream.message_start()
        yield stream.message_delta(
            f"Save “{itinerary.title}” to your organization? "
            f"{len(itinerary.stops)} stops, about ${itinerary.estimated_cost:.0f}."
        )
        yield stream.message_end()
        return

    tool_call_id = new_id("tc")
    yield stream.tool_start(tool_call_id, "save_plan")
    yield stream.tool_args(tool_call_id, {"title": itinerary.title})

    try:
        result = await client.save_plan(
            itinerary.model_dump(mode="json"), idempotency_key=context.run_id
        )
    except ToolCallError as exc:
        yield stream.tool_result(tool_call_id, {"error": str(exc), "code": exc.code})
        yield stream.tool_end(tool_call_id)
        yield stream.message_start()
        yield stream.message_delta(_denial_message(exc))
        yield stream.message_end()
        return

    yield stream.tool_result(tool_call_id, result)
    yield stream.tool_end(tool_call_id)

    saved = itinerary.model_copy(update={"plan_id": result.get("plan_id"), "saved": True})
    context.itinerary = saved
    yield stream.itinerary_state(saved)

    yield stream.message_start()
    yield stream.message_delta(f"Saved. You can find “{saved.title}” in your plans.")
    yield stream.message_end()


def _denial_message(exc: ToolCallError) -> str:
    """Explain a refused save without pretending it might work next time."""
    if exc.code == "permission_denied":
        return (
            "I was not able to save that: your account does not have permission "
            "to save plans in this organization. An administrator can grant it."
        )
    if exc.code == "not_authenticated":
        return "I was not able to save that because the session is not signed in."
    if exc.retryable:
        return "Saving failed because the service was unavailable. Try again in a moment."
    return f"Saving failed: {exc}"


# ---------------------------------------------------------------------------
# Intent
# ---------------------------------------------------------------------------

Intent = str


def classify(message: str) -> Intent:
    """Coarse intent for the reference workflow.

    Deliberately simple and deterministic: it decides which planning path runs,
    and a wrong classification should be a legible bug rather than a model mood.
    """
    lowered = message.lower()

    if any(word in lowered for word in ("save", "keep this", "book it")):
        return "save"
    if any(word in lowered for word in ("cheaper", "less expensive", "lower budget", "cheap")):
        return "cheaper"
    if any(word in lowered for word in ("replace", "instead", "swap", "change the")):
        return "revise"
    if any(word in lowered for word in ("closer", "shorter walk", "less walking")):
        return "tighten"
    return "plan"


def _resolve_request(
    user_message: str, context: RunContext, intent: Intent
) -> tuple[PlanningRequest, str]:
    """Produce the constraints for this run, plus a note explaining any change."""
    parsed = parse_with_rules(
        user_message,
        latitude=context.latitude,
        longitude=context.longitude,
        start_time=context.start_time,
    )

    previous = context.request
    if previous is None or intent == "plan":
        return parsed, ""

    if intent == "cheaper" and context.itinerary is not None:
        revision = make_cheaper(previous, context.itinerary)
        return revision.request, revision.summary

    if intent == "tighten":
        revision = tighten_walk(previous, min(previous.max_walk_km, 1.2))
        return revision.request, revision.summary

    if intent == "revise" and parsed.music_genre:
        revision = change_music_genre(previous, parsed.music_genre)
        return revision.request, revision.summary

    return parsed, ""


# ---------------------------------------------------------------------------
# Tool instrumentation
# ---------------------------------------------------------------------------


class _InstrumentedTools:
    """Wraps the MCP client so every tool call also produces AG-UI events.

    Events are queued rather than yielded inline because the planner calls the
    tools through plain awaits; ``drain`` flushes them into the stream.
    """

    def __init__(self, client: McpToolClient, stream: EventStream) -> None:
        self._client = client
        self._stream = stream
        self._pending: list[BaseEvent] = []
        self.planner_tools = PlannerTools(
            search_places=self._search_places,
            search_events=self._search_events,
            build_route=self._build_route,
        )

    async def drain(self) -> AsyncIterator[BaseEvent]:
        while self._pending:
            yield self._pending.pop(0)

    async def _call(self, name: str, method: Any, kwargs: dict[str, Any]) -> Any:
        tool_call_id = new_id("tc")
        self._pending.append(self._stream.tool_start(tool_call_id, name))
        self._pending.append(self._stream.tool_args(tool_call_id, kwargs))

        try:
            result = await method(**kwargs)
        except ToolCallError as exc:
            self._pending.append(
                self._stream.tool_result(
                    tool_call_id, {"error": str(exc), "code": exc.code, "retryable": exc.retryable}
                )
            )
            self._pending.append(self._stream.tool_end(tool_call_id))
            # Discovery failures are survivable: the planner treats an empty
            # result as "nothing found" and keeps building.
            if name in {"search_places", "search_events"}:
                return []
            raise

        self._pending.append(self._stream.tool_result(tool_call_id, _summarize(name, result)))
        self._pending.append(self._stream.tool_end(tool_call_id))
        return result

    async def _search_places(self, **kwargs: Any) -> Any:
        return await self._call("search_places", self._client.search_places, kwargs)

    async def _search_events(self, **kwargs: Any) -> Any:
        return await self._call("search_events", self._client.search_events, kwargs)

    async def _build_route(self, **kwargs: Any) -> Any:
        return await self._call("build_route", self._client.build_route, kwargs)


def _instrumented_tools(client: McpToolClient, stream: EventStream) -> _InstrumentedTools:
    return _InstrumentedTools(client, stream)


def _summarize(name: str, result: Any) -> dict[str, Any]:
    """Send the UI a compact summary, not the whole payload."""
    if isinstance(result, list):
        return {"tool": name, "count": len(result)}
    if hasattr(result, "total_distance_km"):
        return {
            "tool": name,
            "total_distance_km": result.total_distance_km,
            "total_duration_minutes": result.total_duration_minutes,
        }
    return {"tool": name, "ok": True}


# ---------------------------------------------------------------------------
# Narration
# ---------------------------------------------------------------------------


def _narrate(
    itinerary: Itinerary, request: PlanningRequest, note: str, intent: Intent
) -> list[str]:
    """Compose the assistant's reply as deltas.

    Under ``AGENT_MODEL_PROVIDER=bedrock`` the model writes this; the composed
    version below is the fallback and the deterministic path used by tests.
    """
    if not itinerary.stops:
        return [
            "I could not find anything that fits those constraints. ",
            "Widening the walking radius or raising the budget would help.",
        ]

    chunks: list[str] = []
    if note:
        chunks.append(note + " ")

    chunks.append(
        f"Here is a {len(itinerary.stops)}-stop evening for about ${itinerary.estimated_cost:.0f}"
    )
    if itinerary.estimated_walk_distance_km:
        chunks.append(f", with {itinerary.estimated_walk_distance_km:.1f} km of walking")
    chunks.append(". ")

    if request.budget is not None and itinerary.estimated_cost > request.budget:
        chunks.append(
            f"That is over your ${request.budget:.0f} budget — "
            "ask me to make it cheaper and I will find closer to it. "
        )

    if intent == "save":
        chunks.append("Ready to save it when you are.")
    else:
        chunks.append("Ask me to make it cheaper, change the music, or shorten the walking.")

    return chunks


def context_from_input(payload: RunAgentInput, access_token: str | None) -> RunContext:
    """Build a run context from an AG-UI request.

    Location and any previous itinerary arrive in AG-UI ``state``, which the web
    app owns. Identity does **not** come from here — it comes from the verified
    bearer token on the request.
    """
    state: dict[str, Any] = payload.state if isinstance(payload.state, dict) else {}
    itinerary_state = state.get("itinerary")
    forwarded: dict[str, Any] = (
        payload.forwarded_props if isinstance(payload.forwarded_props, dict) else {}
    )

    return RunContext(
        thread_id=payload.thread_id,
        run_id=payload.run_id or new_id("run"),
        access_token=access_token,
        latitude=float(state.get("latitude", settings.default_latitude)),
        longitude=float(state.get("longitude", settings.default_longitude)),
        itinerary=Itinerary.model_validate(itinerary_state) if itinerary_state else None,
        request=(
            PlanningRequest.model_validate(state["planning_request"])
            if state.get("planning_request")
            else None
        ),
        approved=bool(forwarded.get("approved") or state.get("approved")),
    )


def latest_user_message(payload: RunAgentInput) -> str:
    for message in reversed(payload.messages):
        if message.role == "user":
            content = message.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return " ".join(
                    part.text for part in content if getattr(part, "text", None)
                ).strip()
    return ""

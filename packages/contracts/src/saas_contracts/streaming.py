"""Semantic agent stream events.

The wire protocol is AG-UI: the agent emits AG-UI event types and CopilotKit
consumes them. This module names the *application-level* vocabulary that maps
onto those types, so the web app and the agent agree on names without either
one inventing a parallel protocol.

See docs/adr/ADR-005 for why AG-UI is emitted directly by the agent rather than
being re-encoded by an intermediate service.
"""

from __future__ import annotations

from enum import StrEnum


class AgentEvent(StrEnum):
    """Application event names, carried inside AG-UI custom/state events."""

    RUN_STARTED = "RUN_STARTED"
    RUN_FINISHED = "RUN_FINISHED"
    RUN_ERROR = "RUN_ERROR"

    TEXT_MESSAGE_START = "TEXT_MESSAGE_START"
    TEXT_MESSAGE_CONTENT = "TEXT_MESSAGE_CONTENT"
    TEXT_MESSAGE_END = "TEXT_MESSAGE_END"

    TOOL_CALL_START = "TOOL_CALL_START"
    TOOL_CALL_ARGS = "TOOL_CALL_ARGS"
    TOOL_CALL_END = "TOOL_CALL_END"
    TOOL_CALL_RESULT = "TOOL_CALL_RESULT"

    STATE_SNAPSHOT = "STATE_SNAPSHOT"
    STATE_DELTA = "STATE_DELTA"

    # Emitted as an AG-UI custom event; the UI renders an approval affordance.
    # Approval expresses intent. It is never authorization — the deterministic
    # service still checks the principal's permission before acting.
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"


class ProgressStage(StrEnum):
    """Coarse planning stages, surfaced as a progress checklist in the UI."""

    LOCATING = "locating"
    SEARCHING_EVENTS = "searching_events"
    SEARCHING_PLACES = "searching_places"
    OPTIMIZING_ROUTE = "optimizing_route"
    BUILDING_ITINERARY = "building_itinerary"
    DONE = "done"

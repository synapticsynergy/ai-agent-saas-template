"""Composed narration.

The reply the agent gives when no model is available — because
``AGENT_MODEL_PROVIDER=scripted``, or because a Bedrock call failed. It reads
the finished itinerary and states the facts, which is the part of a reply that
must never be wrong.
"""

from __future__ import annotations

from saas_contracts.plan import Itinerary

from agent_app.workflows.request import PlanningRequest


def compose_narration(itinerary: Itinerary, request: PlanningRequest, note: str) -> list[str]:
    """Build the assistant's reply from the itinerary, without a model.

    Used when ``AGENT_MODEL_PROVIDER=scripted``, and whenever a model call
    fails. Deterministic, so tests can assert on it.
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

    chunks.append("Ask me to make it cheaper, change the music, or shorten the walking.")

    return chunks

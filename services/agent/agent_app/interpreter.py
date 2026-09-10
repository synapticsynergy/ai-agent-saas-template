"""Request interpretation.

Turning a sentence into a :class:`PlanningRequest` is the one job in this agent
that genuinely needs a language model, so it is the only place one is used
(see docs/adr/ADR-007-deterministic-planner.md).

Two implementations behind one interface:

* :class:`BedrockInterpreter` — a Strands agent on Amazon Bedrock, asked for
  structured output.
* :class:`RuleInterpreter` — deterministic keyword extraction. Used when
  ``AGENT_MODEL_PROVIDER=scripted``, and as the fallback whenever a model call
  fails, so a Bedrock outage degrades the agent's *understanding* rather than
  taking the product down.

Both return the same structure, so nothing downstream knows or cares which ran.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

import structlog

from agent_app.config import settings
from agent_app.workflows.parse import parse_with_rules
from agent_app.workflows.request import PlanningRequest

log = structlog.get_logger(__name__)

SYSTEM_PROMPT = """\
You extract structured planning constraints from a person's request for an \
evening out.

Rules:
- categories: the kinds of stops in visit order, from dinner, music, drinks, \
activity, dessert, coffee. Default to dinner, music, drinks when unclear.
- budget: the total for the whole party, if a number is mentioned. Otherwise null.
- max_walk_km: 1.5 when they say "walkable", otherwise 2.5 unless they give a \
distance. Convert miles to kilometres.
- music_genre: only when they name one.
- party_size: default 2.
- dietary_tags: hard requirements only, such as vegan or vegetarian-friendly. \
These exclude venues that cannot accommodate them.
- preference_tags: atmosphere only, such as quiet, patio, rooftop, date-night. \
These rank venues; they never exclude one.

Do not invent constraints the person did not express.\
"""


class Interpreter(Protocol):
    name: str

    async def interpret(
        self, text: str, *, latitude: float, longitude: float, start_time: datetime | None
    ) -> PlanningRequest: ...


class RuleInterpreter:
    """Deterministic keyword extraction. No model, no network."""

    name = "rules"

    async def interpret(
        self, text: str, *, latitude: float, longitude: float, start_time: datetime | None
    ) -> PlanningRequest:
        return parse_with_rules(text, latitude=latitude, longitude=longitude, start_time=start_time)


class BedrockInterpreter:
    """A Strands agent on Bedrock, asked for a PlanningRequest directly.

    Structured output rather than free text plus parsing: the model fills a
    schema the rest of the system already validates, so a malformed answer fails
    at the boundary instead of becoming a strange itinerary.
    """

    name = "bedrock"

    def __init__(self) -> None:
        # Strands' Agent is untyped at this boundary, so the attribute is Any
        # rather than pretending to a precision the SDK does not provide.
        self._agent: Any = None

    def _build(self) -> Any:
        # Imported lazily so `AGENT_MODEL_PROVIDER=scripted` never needs boto3
        # credentials or a Bedrock-capable environment.
        from strands import Agent
        from strands.models import BedrockModel

        model = BedrockModel(
            model_id=settings.bedrock_model_id,
            region_name=settings.bedrock_region,
            max_tokens=settings.bedrock_max_tokens,
            temperature=settings.bedrock_temperature,
        )
        return Agent(model=model, system_prompt=SYSTEM_PROMPT)

    async def interpret(
        self, text: str, *, latitude: float, longitude: float, start_time: datetime | None
    ) -> PlanningRequest:
        if self._agent is None:
            self._agent = self._build()

        # The model does not choose these: location comes from the browser and
        # the clock comes from the server. Asking a model for either invites it
        # to invent one.
        defaults = parse_with_rules(
            text, latitude=latitude, longitude=longitude, start_time=start_time
        )

        try:
            extracted = await self._agent.structured_output_async(
                PlanningRequest,
                f"{text}\n\n"
                f"Use latitude {latitude}, longitude {longitude} and "
                f"start_time {defaults.start_time.isoformat()}.",
            )
        except Exception as exc:
            log.warning("interpreter.bedrock_failed", error=str(exc))
            return defaults

        # Re-pin the fields the model must not decide, whatever it returned.
        return extracted.model_copy(
            update={
                "latitude": latitude,
                "longitude": longitude,
                "start_time": defaults.start_time,
            }
        )


def get_interpreter() -> Interpreter:
    if settings.agent_model_provider == "bedrock":
        return BedrockInterpreter()
    return RuleInterpreter()

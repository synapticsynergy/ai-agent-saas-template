"""Language: interpreting the request and explaining the result.

These are the two jobs in this agent that genuinely need a language model, and
the only places one is used. Choosing venues, timing and budget is ordinary
code (see docs/adr/ADR-007-deterministic-planner.md).

Two implementations behind one interface:

* :class:`ModelInterpreter` — Claude via the Anthropic SDK, against the Claude
  API or Amazon Bedrock. Interprets via structured output, narrates via a
  streamed completion.
* :class:`RuleInterpreter` — deterministic keyword extraction and composed
  prose. Used when ``AGENT_MODEL_PROVIDER=scripted``, and as the fallback
  whenever a model call fails, so a Bedrock outage degrades how the agent reads
  and writes rather than taking the product down.

Both satisfy the same protocol, so nothing downstream knows or cares which ran.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Protocol

import structlog
from saas_contracts.plan import Itinerary

from agent_app.config import settings
from agent_app.narration import compose_narration
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

NARRATION_PROMPT = """\
You explain an evening itinerary that has already been built for someone.

The itinerary is rendered beside your message as a map and a list of cards, so \
do not restate it stop by stop. Say what is worth knowing about it: what it \
costs, how much walking it involves, why it fits what they asked for, and \
anything that does not fit.

Rules:
- Two or three sentences. No lists, no headings.
- Never invent a venue, price, time or address. Everything you say about the \
world comes from the itinerary you are given.
- If the plan exceeds the stated budget, say so plainly rather than glossing it.
- If there are no stops, say nothing was found and suggest which constraint to \
relax.
- End by inviting a revision: cheaper, a different genre, less walking, or save it.\
"""


class Interpreter(Protocol):
    name: str

    async def interpret(
        self, text: str, *, latitude: float, longitude: float, start_time: datetime | None
    ) -> PlanningRequest: ...

    def narrate(
        self, itinerary: Itinerary, request: PlanningRequest, note: str
    ) -> AsyncIterator[str]: ...


class RuleInterpreter:
    """Deterministic keyword extraction and composed prose. No model, no network."""

    name = "rules"

    async def interpret(
        self, text: str, *, latitude: float, longitude: float, start_time: datetime | None
    ) -> PlanningRequest:
        return parse_with_rules(text, latitude=latitude, longitude=longitude, start_time=start_time)

    async def narrate(
        self, itinerary: Itinerary, request: PlanningRequest, note: str
    ) -> AsyncIterator[str]:
        for chunk in compose_narration(itinerary, request, note):
            yield chunk


class ModelInterpreter:
    """Claude via the Anthropic SDK — the Claude API directly, or Amazon Bedrock.

    Structured output rather than free text plus parsing: the model fills a
    schema the rest of the system already validates, so a malformed answer fails
    at the boundary instead of becoming a strange itinerary.

    The provider is chosen by ``AGENT_MODEL_PROVIDER``. Everything above the
    model — prompts, fallbacks, re-pinning — is identical for both, so switching
    providers changes cost and setup, not behaviour.
    """

    def __init__(self) -> None:
        self.name: str = settings.agent_model_provider
        # The SDK's client is untyped at this boundary, so this is Any rather
        # than pretending to a precision the SDK does not provide.
        self._client: Any = None

    def _build_client(self) -> Any:
        """Construct the SDK client for the configured provider.

        Imported lazily so `AGENT_MODEL_PROVIDER=scripted` needs neither the
        SDK nor credentials.
        """
        if self.name == "anthropic":
            from anthropic import AsyncAnthropic

            # Pass the key only when configured. The repository .env is read
            # into settings, not into the process environment, so the SDK would
            # not otherwise see it; when it is empty the SDK resolves
            # credentials itself.
            if settings.anthropic_api_key:
                return AsyncAnthropic(api_key=settings.anthropic_api_key)
            return AsyncAnthropic()

        from anthropic import AsyncAnthropicBedrockMantle

        # The Mantle client is the Messages-API Bedrock endpoint, so the same
        # request shape works against both providers. The older
        # `AsyncAnthropicBedrock` client speaks the legacy InvokeModel path and
        # takes differently-spelled model ids.
        return AsyncAnthropicBedrockMantle(aws_region=settings.bedrock_region)

    @property
    def _model_id(self) -> str:
        if self.name == "anthropic":
            return settings.anthropic_model_id
        return settings.bedrock_model_id

    @property
    def _max_tokens(self) -> int:
        if self.name == "anthropic":
            return settings.anthropic_max_tokens
        return settings.bedrock_max_tokens

    def _sampling(self) -> dict[str, Any]:
        """Sampling parameters, which current Claude models refuse.

        Claude Opus 5 and Sonnet 5 reject `temperature`/`top_p`/`top_k` with a
        400, and `interpret` swallows a failed call as a fallback to rules — so
        sending one would quietly switch the model off rather than error. Only
        an explicitly configured value is sent, for older models that accept it.
        """
        if self.name != "anthropic" and settings.bedrock_temperature is not None:
            return {"temperature": settings.bedrock_temperature}
        return {}

    async def interpret(
        self, text: str, *, latitude: float, longitude: float, start_time: datetime | None
    ) -> PlanningRequest:
        if self._client is None:
            self._client = self._build_client()

        # The model does not choose these: location comes from the browser and
        # the clock comes from the server. Asking a model for either invites it
        # to invent one.
        defaults = parse_with_rules(
            text, latitude=latitude, longitude=longitude, start_time=start_time
        )

        try:
            # Structured output rather than free text plus parsing: the model
            # fills the schema the rest of the system already validates.
            response = await self._client.messages.parse(
                model=self._model_id,
                max_tokens=self._max_tokens,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"{text}\n\n"
                            f"Use latitude {latitude}, longitude {longitude} and "
                            f"start_time {defaults.start_time.isoformat()}."
                        ),
                    }
                ],
                output_format=PlanningRequest,
                **self._sampling(),
            )
            extracted = response.parsed_output
            if extracted is None:
                raise ValueError("model returned no parsable structured output")
        except Exception as exc:
            log.warning("interpreter.model_failed", provider=self.name, error=str(exc))
            return defaults

        # Re-pin the fields the model must not decide, whatever it returned.
        pinned: PlanningRequest = extracted.model_copy(
            update={
                "latitude": latitude,
                "longitude": longitude,
                "start_time": defaults.start_time,
            }
        )
        return pinned

    async def narrate(
        self, itinerary: Itinerary, request: PlanningRequest, note: str
    ) -> AsyncIterator[str]:
        """Stream the model's explanation of a finished itinerary.

        The model is given the plan as facts and asked to comment on it. It
        never chooses anything: the itinerary is already built, so the worst a
        bad completion can do is describe it poorly.

        Deltas are forwarded as they arrive, so the reply appears while it is
        being written rather than landing in one block.
        """
        if self._client is None:
            self._client = self._build_client()

        prompt = _narration_prompt(itinerary, request, note)
        produced = False

        try:
            async with self._client.messages.stream(
                model=self._model_id,
                max_tokens=self._max_tokens,
                system=NARRATION_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                **self._sampling(),
            ) as stream:
                async for delta in stream.text_stream:
                    if delta:
                        produced = True
                        yield delta
        except Exception as exc:
            log.warning("interpreter.narration_failed", error=str(exc))

        if not produced:
            # An empty completion is as useless as a failed one.
            for chunk in compose_narration(itinerary, request, note):
                yield chunk


def _narration_prompt(itinerary: Itinerary, request: PlanningRequest, note: str) -> str:
    """Describe the itinerary as facts for the model to comment on."""
    if not itinerary.stops:
        return (
            "No itinerary could be built. The person asked for "
            f"{', '.join(request.categories)}"
            + (f" under {request.budget:.0f}." if request.budget else ".")
            + " Tell them nothing matched and which constraint to relax."
        )

    stops = "\n".join(
        f"{index + 1}. {stop.name} ({stop.category}), "
        f"{stop.start_time:%-I:%M %p} to {stop.end_time:%-I:%M %p}, "
        f"{stop.estimated_cost:.0f} per person. {stop.reason}"
        for index, stop in enumerate(itinerary.stops)
    )

    asked = [f"categories: {', '.join(request.categories)}"]
    if request.budget is not None:
        asked.append(f"budget: {request.budget:.0f} total for {request.party_size}")
    if request.music_genre:
        asked.append(f"genre: {request.music_genre}")
    if request.preference_tags:
        asked.append(f"preferences: {', '.join(request.preference_tags)}")
    asked.append(f"max walk: {request.max_walk_km:.1f} km")

    return (
        f"They asked for — {'; '.join(asked)}.\n\n"
        + (f"What changed this time: {note}\n\n" if note else "")
        + f"The itinerary:\n{stops}\n\n"
        f"Totals: {itinerary.estimated_cost:.0f} for the party, "
        f"{itinerary.estimated_walk_distance_km:.1f} km of walking, "
        f"{len(itinerary.stops)} stops."
    )


def get_interpreter() -> Interpreter:
    if settings.agent_model_provider in ("anthropic", "bedrock"):
        return ModelInterpreter()
    return RuleInterpreter()

"""Request parsing, intent classification and conversational revision."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from saas_contracts.plan import Itinerary

from agent_app.runner import classify
from agent_app.workflows.parse import parse_with_rules
from agent_app.workflows.planner import build_itinerary
from agent_app.workflows.replan import (
    MIN_BUDGET,
    change_music_genre,
    make_cheaper,
    set_categories,
    tighten_walk,
)
from agent_app.workflows.request import PlanningRequest
from tests.agent.conftest import LAT, LON, TONIGHT, StubTools

REFERENCE_REQUEST = (
    "Plan my evening near me. I want dinner, live music, and drinks. "
    "Keep it walkable and under $100."
)


def parse(text: str) -> PlanningRequest:
    return parse_with_rules(text, latitude=LAT, longitude=LON, start_time=TONIGHT)


class FakeClient:
    """Stands in for `anthropic.AsyncAnthropic` at the two calls the agent makes.

    Only `messages.parse` and `messages.stream` are modelled, because those are
    the only SDK surfaces `ModelInterpreter` touches. `sent` captures the
    request so a test can assert what the model was actually told.
    """

    def __init__(
        self,
        *,
        parsed: PlanningRequest | None = None,
        deltas: list[str] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._parsed = parsed
        self._deltas = deltas or []
        self._error = error
        self.sent: dict[str, Any] = {}
        self.messages = self

    @property
    def prompt(self) -> str:
        """The user-turn text of the most recent call."""
        messages = self.sent.get("messages") or []
        return str(messages[0]["content"]) if messages else ""

    async def parse(self, **kwargs: Any) -> object:
        self.sent = kwargs
        if self._error is not None:
            raise self._error

        class Response:
            parsed_output = self._parsed

        return Response()

    def stream(self, **kwargs: Any) -> FakeClient:
        self.sent = kwargs
        return self

    async def __aenter__(self) -> FakeClient:
        if self._error is not None:
            raise self._error
        return self

    async def __aexit__(self, *_: object) -> bool:
        return False

    @property
    async def text_stream(self):  # type: ignore[no-untyped-def]
        for delta in self._deltas:
            yield delta


class TestParsing:
    def test_the_reference_request_parses_completely(self) -> None:
        request = parse(REFERENCE_REQUEST)
        assert request.categories == ["dinner", "music", "drinks"]
        assert request.budget == 100.0
        assert request.max_walk_km == 1.5

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("dinner and drinks", ["dinner", "drinks"]),
            ("just coffee", ["coffee"]),
            ("dinner then a show then dessert", ["dinner", "music", "dessert"]),
            ("arcade night with friends", ["activity"]),
        ],
    )
    def test_categories_are_extracted(self, text: str, expected: list[str]) -> None:
        assert parse(text).categories == expected

    def test_categories_are_ordered_sensibly_regardless_of_phrasing(self) -> None:
        assert parse("drinks after dinner").categories == ["dinner", "drinks"]

    def test_an_unrecognisable_request_falls_back_to_the_default_evening(self) -> None:
        assert parse("surprise me").categories == ["dinner", "music", "drinks"]

    @pytest.mark.parametrize(
        ("text", "expected"),
        [("under $80", 80.0), ("keep it under 60", 60.0), ("$45 max", 45.0), ("anything", None)],
    )
    def test_budget_is_extracted(self, text: str, expected: float | None) -> None:
        assert parse(text).budget == expected

    def test_walkable_tightens_the_radius(self) -> None:
        assert parse("keep it walkable").max_walk_km < parse("anywhere nearby").max_walk_km

    def test_miles_are_converted_to_kilometres(self) -> None:
        assert parse("within 2 miles").max_walk_km == pytest.approx(3.22, abs=0.01)

    def test_kilometres_are_taken_literally(self) -> None:
        assert parse("within 3 km").max_walk_km == 3.0

    def test_genre_is_extracted(self) -> None:
        assert parse("dinner and live jazz").music_genre == "jazz"
        assert parse("dinner and live music").music_genre == ""

    def test_party_size_is_extracted(self) -> None:
        assert parse("dinner for 4 people").party_size == 4
        assert parse("dinner").party_size == 2

    def test_dietary_needs_are_separated_from_atmosphere_preferences(self) -> None:
        """Dietary needs filter candidates; atmosphere only ranks them."""
        request = parse("vegan dinner somewhere quiet")
        assert request.dietary_tags == ["vegan"]
        assert "quiet" in request.preference_tags
        assert "quiet" not in request.dietary_tags

    def test_parsing_is_deterministic(self) -> None:
        assert parse(REFERENCE_REQUEST).model_dump() == parse(REFERENCE_REQUEST).model_dump()


class TestIntentClassification:
    @pytest.mark.parametrize(
        ("message", "expected"),
        [
            ("Plan my evening near me", "plan"),
            ("Make it cheaper.", "cheaper"),
            ("Can you make this less expensive?", "cheaper"),
            ("Replace the live music with jazz.", "revise"),
            ("Save this plan.", "save"),
            ("Keep it closer together", "tighten"),
        ],
    )
    def test_reference_follow_ups_classify_correctly(self, message: str, expected: str) -> None:
        assert classify(message) == expected


class TestMakeCheaper:
    def test_targets_a_lower_budget_than_the_current_cost(
        self, base_request: PlanningRequest
    ) -> None:
        current = Itinerary(title="t", start_time=TONIGHT, estimated_cost=120.0)
        revision = make_cheaper(base_request, current)
        assert revision.request.budget is not None
        assert revision.request.budget < 120.0

    def test_repeated_requests_keep_making_progress(self, base_request: PlanningRequest) -> None:
        """Anchoring on cost, not the old budget, avoids stalling."""
        current = Itinerary(title="t", start_time=TONIGHT, estimated_cost=120.0)
        first = make_cheaper(base_request, current)

        cheaper_plan = Itinerary(title="t", start_time=TONIGHT, estimated_cost=80.0)
        second = make_cheaper(first.request, cheaper_plan)

        assert second.request.budget is not None
        assert first.request.budget is not None
        assert second.request.budget < first.request.budget

    def test_never_goes_below_a_sane_floor(self, base_request: PlanningRequest) -> None:
        current = Itinerary(title="t", start_time=TONIGHT, estimated_cost=1.0)
        assert make_cheaper(base_request, current).request.budget == MIN_BUDGET

    def test_the_summary_explains_the_change(self, base_request: PlanningRequest) -> None:
        current = Itinerary(title="t", start_time=TONIGHT, estimated_cost=120.0)
        assert "$" in make_cheaper(base_request, current).summary

    async def test_replanning_actually_produces_a_cheaper_itinerary(self) -> None:
        tools = StubTools()
        request = PlanningRequest(latitude=LAT, longitude=LON, start_time=TONIGHT)

        original = await build_itinerary(request, tools.planner_tools)
        revision = make_cheaper(request, original)
        revised = await build_itinerary(revision.request, tools.planner_tools)

        assert revised.estimated_cost < original.estimated_cost


class TestChangeGenre:
    def test_sets_the_genre(self, base_request: PlanningRequest) -> None:
        assert change_music_genre(base_request, "Jazz").request.music_genre == "jazz"

    def test_adds_a_music_stop_when_there_was_none(self) -> None:
        request = PlanningRequest(
            latitude=LAT, longitude=LON, start_time=TONIGHT, categories=["dinner"]
        )
        assert "music" in change_music_genre(request, "jazz").request.categories

    def test_an_empty_genre_is_rejected(self, base_request: PlanningRequest) -> None:
        with pytest.raises(ValueError, match="genre is required"):
            change_music_genre(base_request, "   ")

    async def test_the_revised_plan_uses_the_requested_genre(self) -> None:
        tools = StubTools()
        request = PlanningRequest(latitude=LAT, longitude=LON, start_time=TONIGHT)

        revised = await build_itinerary(
            change_music_genre(request, "jazz").request, tools.planner_tools
        )
        music = next(stop for stop in revised.stops if stop.category == "music")
        assert music.external_id in {"e_jazz_free", "e_jazz_paid"}


class TestOtherRevisions:
    def test_set_categories_replaces_the_plan_shape(self, base_request: PlanningRequest) -> None:
        revision = set_categories(base_request, ["drinks", "drinks", "drinks", "drinks"])
        assert len(revision.request.categories) == 4

    def test_set_categories_rejects_an_empty_list(self, base_request: PlanningRequest) -> None:
        with pytest.raises(ValueError, match="At least one"):
            set_categories(base_request, [])

    def test_tighten_walk_reduces_the_radius(self, base_request: PlanningRequest) -> None:
        assert tighten_walk(base_request, 1.0).request.max_walk_km == 1.0

    def test_tighten_walk_rejects_a_non_positive_radius(
        self, base_request: PlanningRequest
    ) -> None:
        with pytest.raises(ValueError, match="positive"):
            tighten_walk(base_request, 0)

    def test_revisions_do_not_mutate_the_original_request(
        self, base_request: PlanningRequest
    ) -> None:
        before = base_request.model_dump()
        change_music_genre(base_request, "jazz")
        tighten_walk(base_request, 1.0)
        assert base_request.model_dump() == before


def test_default_start_time_is_in_the_future() -> None:
    request = parse_with_rules("dinner", latitude=LAT, longitude=LON)
    assert request.start_time > datetime.now(UTC)


class TestInterpreterSelection:
    """The configured provider must actually take effect.

    A configuration flag that silently does nothing is worse than no flag: it
    reads as implemented in code review and as broken in production.
    """

    def test_scripted_selects_the_rule_interpreter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from agent_app import interpreter as module
        from agent_app.config import settings

        monkeypatch.setattr(settings, "agent_model_provider", "scripted")
        assert module.get_interpreter().name == "rules"

    def test_an_unknown_provider_is_rejected_by_config(self) -> None:
        from pydantic import ValidationError

        from agent_app.config import Settings

        with pytest.raises(ValidationError):
            Settings(_env_file=None, agent_model_provider="bedrock")  # type: ignore[arg-type,call-arg]

    async def test_the_rule_interpreter_matches_direct_parsing(self) -> None:
        from agent_app.interpreter import RuleInterpreter

        result = await RuleInterpreter().interpret(
            REFERENCE_REQUEST, latitude=LAT, longitude=LON, start_time=TONIGHT
        )
        assert result.model_dump() == parse(REFERENCE_REQUEST).model_dump()

    async def test_a_model_failure_degrades_to_rules(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A model outage must cost understanding, not availability."""
        from agent_app.interpreter import ModelInterpreter

        client = FakeClient(error=RuntimeError("the provider is unavailable"))
        interpreter = ModelInterpreter()
        monkeypatch.setattr(interpreter, "_build_client", lambda: client)

        result = await interpreter.interpret(
            REFERENCE_REQUEST, latitude=LAT, longitude=LON, start_time=TONIGHT
        )
        assert result.budget == 100.0
        assert result.categories == ["dinner", "music", "drinks"]

    async def test_the_model_cannot_move_the_user(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Location and clock come from the server, whatever the model returns."""
        from agent_app.interpreter import ModelInterpreter
        from agent_app.workflows.request import PlanningRequest

        client = FakeClient(
            parsed=PlanningRequest(
                latitude=1.0,
                longitude=2.0,
                start_time=datetime(1999, 1, 1, tzinfo=UTC),
                categories=["dinner"],
            )
        )
        interpreter = ModelInterpreter()
        monkeypatch.setattr(interpreter, "_build_client", lambda: client)

        result = await interpreter.interpret(
            "dinner", latitude=LAT, longitude=LON, start_time=TONIGHT
        )
        assert result.latitude == LAT
        assert result.longitude == LON
        assert result.start_time == TONIGHT
        # What the model *is* allowed to decide survives.
        assert result.categories == ["dinner"]


class TestNarration:
    """The model explains the plan; it never decides it.

    Regression guard: selecting a model provider used to change nothing about
    the reply — the composed text was always used, while a docstring claimed
    otherwise.
    """

    async def test_the_rule_interpreter_composes_the_reply(self) -> None:
        from agent_app.interpreter import RuleInterpreter

        itinerary = await build_itinerary(
            PlanningRequest(latitude=LAT, longitude=LON, start_time=TONIGHT),
            StubTools().planner_tools,
        )

        chunks = [
            chunk
            async for chunk in RuleInterpreter().narrate(
                itinerary, PlanningRequest(latitude=LAT, longitude=LON, start_time=TONIGHT), ""
            )
        ]
        assert "".join(chunks).startswith("Here is a 3-stop evening")

    async def test_the_model_writes_the_reply_when_a_model_provider_is_selected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from agent_app.interpreter import ModelInterpreter

        narrator = FakeClient(deltas=["A short ", "walk between ", "three good stops."])
        interpreter = ModelInterpreter()
        monkeypatch.setattr(interpreter, "_build_client", lambda: narrator)

        itinerary = await build_itinerary(
            PlanningRequest(latitude=LAT, longitude=LON, start_time=TONIGHT),
            StubTools().planner_tools,
        )
        request = PlanningRequest(latitude=LAT, longitude=LON, start_time=TONIGHT, budget=100.0)

        text = "".join([chunk async for chunk in interpreter.narrate(itinerary, request, "")])

        assert text == "A short walk between three good stops."

        # The model is given the plan as facts, so it has nothing to invent:
        # every stop, and the constraints it should judge the plan against.
        for stop in itinerary.stops:
            assert stop.name in narrator.prompt
        assert "budget: 100" in narrator.prompt
        assert f"{len(itinerary.stops)} stops" in narrator.prompt

    async def test_a_narration_failure_falls_back_to_composed_text(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from agent_app.interpreter import ModelInterpreter

        interpreter = ModelInterpreter()
        monkeypatch.setattr(
            interpreter,
            "_build_client",
            lambda: FakeClient(error=RuntimeError("the provider is unavailable")),
        )

        itinerary = await build_itinerary(
            PlanningRequest(latitude=LAT, longitude=LON, start_time=TONIGHT),
            StubTools().planner_tools,
        )
        request = PlanningRequest(latitude=LAT, longitude=LON, start_time=TONIGHT)

        text = "".join([chunk async for chunk in interpreter.narrate(itinerary, request, "")])
        assert "3-stop evening" in text

    async def test_an_empty_completion_also_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A silent model is as useless as a broken one."""
        from agent_app.interpreter import ModelInterpreter

        interpreter = ModelInterpreter()
        monkeypatch.setattr(interpreter, "_build_client", lambda: FakeClient(deltas=[]))

        itinerary = await build_itinerary(
            PlanningRequest(latitude=LAT, longitude=LON, start_time=TONIGHT),
            StubTools().planner_tools,
        )
        request = PlanningRequest(latitude=LAT, longitude=LON, start_time=TONIGHT)

        text = "".join([chunk async for chunk in interpreter.narrate(itinerary, request, "")])
        assert text


class TestModelProviders:
    """Each provider builds the model it names, with parameters it accepts."""

    def test_anthropic_selects_the_model_interpreter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from agent_app import interpreter as module
        from agent_app.config import settings

        monkeypatch.setattr(settings, "agent_model_provider", "anthropic")
        assert module.get_interpreter().name == "anthropic"

    def test_the_anthropic_client_is_built_from_settings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from anthropic import AsyncAnthropic

        from agent_app.config import settings
        from agent_app.interpreter import ModelInterpreter

        monkeypatch.setattr(settings, "agent_model_provider", "anthropic")
        monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test")
        monkeypatch.setattr(settings, "anthropic_model_id", "claude-sonnet-5")

        interpreter = ModelInterpreter()
        client = interpreter._build_client()

        assert isinstance(client, AsyncAnthropic)
        # The key comes from settings, not the process environment: the
        # repository .env is read into settings, so the SDK would not see it.
        assert client.api_key == "sk-ant-test"
        assert interpreter._model_id == "claude-sonnet-5"
        # Claude Opus 5 and Sonnet 5 return a 400 for sampling parameters.
        assert interpreter._sampling() == {}

    def test_no_sampling_parameters_are_ever_sent(self) -> None:
        """Current Claude models 400 on temperature/top_p, and a failed call
        falls back to rules silently — so nothing is sent."""
        from agent_app.interpreter import ModelInterpreter

        assert ModelInterpreter()._sampling() == {}

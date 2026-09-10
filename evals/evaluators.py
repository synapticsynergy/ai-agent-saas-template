"""Objective evaluators.

None of these look at prose. They assert on structured outcomes — which tools
ran, whether the itinerary is feasible, whether it fits the budget, whether an
authorization boundary held — because those are the properties that actually
regress when a prompt, model or tool changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from itertools import pairwise
from typing import Any

from saas_contracts.plan import Itinerary


@dataclass
class RunRecord:
    """Everything one evaluated run produced."""

    case_id: str
    itinerary: Itinerary | None
    tools_called: list[str]
    events: list[str]
    save_attempted: bool = False
    save_succeeded: bool = False
    save_error_code: str | None = None
    error: str | None = None
    latency_ms: int = 0
    previous: Itinerary | None = None
    music_genre: str = ""


@dataclass
class Score:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class CaseResult:
    case_id: str
    scores: list[Score] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(score.passed for score in self.scores)

    @property
    def pass_rate(self) -> float:
        if not self.scores:
            return 1.0
        return sum(1 for s in self.scores if s.passed) / len(self.scores)


# ---------------------------------------------------------------------------
# Individual evaluators
# ---------------------------------------------------------------------------


def uses_tools(record: RunRecord, expected: list[str]) -> Score:
    missing = [tool for tool in expected if tool not in record.tools_called]
    return Score(
        "uses_tools",
        not missing,
        f"missing: {missing}"
        if missing
        else f"called: {sorted(set(record.tools_called))}",
    )


def forbidden_tools(record: RunRecord, forbidden: list[str]) -> Score:
    used = [tool for tool in forbidden if tool in record.tools_called]
    return Score(
        "forbidden_tools", not used, f"used forbidden: {used}" if used else "none used"
    )


def includes_categories(record: RunRecord, expected: list[str]) -> Score:
    present = (
        {stop.category for stop in record.itinerary.stops}
        if record.itinerary
        else set()
    )
    missing = [category for category in expected if category not in present]
    return Score(
        "includes_categories",
        not missing,
        f"missing: {missing}" if missing else f"present: {sorted(present)}",
    )


def forbidden_categories(record: RunRecord, forbidden: list[str]) -> Score:
    present = (
        {stop.category for stop in record.itinerary.stops}
        if record.itinerary
        else set()
    )
    found = [category for category in forbidden if category in present]
    return Score(
        "forbidden_categories", not found, f"found: {found}" if found else "none"
    )


def max_total_cost(record: RunRecord, limit: float) -> Score:
    cost = record.itinerary.estimated_cost if record.itinerary else 0.0
    return Score("max_total_cost", cost <= limit, f"${cost:.0f} vs limit ${limit:.0f}")


def max_walk_km(record: RunRecord, limit: float) -> Score:
    walk = record.itinerary.estimated_walk_distance_km if record.itinerary else 0.0
    return Score("max_walk_km", walk <= limit, f"{walk:.2f} km vs limit {limit:.2f} km")


def min_stops(record: RunRecord, minimum: int) -> Score:
    count = len(record.itinerary.stops) if record.itinerary else 0
    return Score("min_stops", count >= minimum, f"{count} stops (min {minimum})")


def itinerary_is_feasible(record: RunRecord, _expected: bool) -> Score:
    """A plan a person could actually follow.

    Stops must be ordered, must not overlap, and must leave enough time to get
    from one to the next. An itinerary that fails this is worse than none: it
    looks right and wastes the user's evening.
    """
    if record.itinerary is None or not record.itinerary.stops:
        return Score("itinerary_is_feasible", False, "no itinerary")

    stops = record.itinerary.stops
    problems: list[str] = []

    for stop in stops:
        if stop.end_time <= stop.start_time:
            problems.append(f"{stop.name}: ends before it starts")

    for earlier, later in pairwise(stops):
        if later.start_time < earlier.end_time:
            problems.append(f"{earlier.name} overlaps {later.name}")
        elif later.start_time - earlier.end_time > timedelta(hours=3):
            problems.append(f"{earlier.name} → {later.name}: gap over 3 hours")

    return Score(
        "itinerary_is_feasible", not problems, "; ".join(problems) or "feasible"
    )


def no_hallucinated_stops(record: RunRecord, _expected: bool) -> Score:
    """Every stop must trace back to a tool result.

    The agent is not allowed to invent a venue when search returns nothing.
    """
    if record.itinerary is None:
        return Score("no_hallucinated_stops", True, "no itinerary")

    unsourced = [stop.name for stop in record.itinerary.stops if not stop.external_id]
    return Score(
        "no_hallucinated_stops",
        not unsourced,
        f"unsourced stops: {unsourced}"
        if unsourced
        else "all stops sourced from tools",
    )


def cheaper_than_previous(record: RunRecord, _expected: bool) -> Score:
    if record.itinerary is None or record.previous is None:
        return Score("cheaper_than_previous", False, "missing itinerary for comparison")

    now, before = record.itinerary.estimated_cost, record.previous.estimated_cost
    return Score("cheaper_than_previous", now < before, f"${before:.0f} → ${now:.0f}")


def shorter_walk_than_previous(record: RunRecord, _expected: bool) -> Score:
    if record.itinerary is None or record.previous is None:
        return Score(
            "shorter_walk_than_previous", False, "missing itinerary for comparison"
        )

    now = record.itinerary.estimated_walk_distance_km
    before = record.previous.estimated_walk_distance_km
    return Score(
        "shorter_walk_than_previous", now <= before, f"{before:.2f} km → {now:.2f} km"
    )


def music_genre(record: RunRecord, expected: str) -> Score:
    return Score(
        "music_genre",
        record.music_genre.lower() == expected.lower(),
        f"requested genre: {record.music_genre or '(none)'}",
    )


def save_denied(record: RunRecord, _expected: bool) -> Score:
    """A viewer's save must be refused, and refused for the right reason."""
    denied = record.save_attempted and not record.save_succeeded
    right_reason = record.save_error_code == "permission_denied"
    return Score(
        "save_denied",
        denied and right_reason,
        f"attempted={record.save_attempted} succeeded={record.save_succeeded} "
        f"code={record.save_error_code}",
    )


def save_succeeds(record: RunRecord, _expected: bool) -> Score:
    return Score(
        "save_succeeds",
        record.save_succeeded,
        f"code={record.save_error_code}" if not record.save_succeeded else "saved",
    )


def authorization_respected(record: RunRecord, _expected: bool) -> Score:
    """The run must never claim success on a denied action."""
    if record.save_error_code == "permission_denied" and record.save_succeeded:
        return Score(
            "authorization_respected", False, "denied action reported as succeeded"
        )
    return Score("authorization_respected", True, "consistent")


def run_completes(record: RunRecord, _expected: bool) -> Score:
    return Score(
        "run_completes",
        "RUN_FINISHED" in record.events,
        f"terminal event: {record.events[-1] if record.events else '(none)'}",
    )


EVALUATORS: dict[str, Any] = {
    "uses_tools": uses_tools,
    "forbidden_tools": forbidden_tools,
    "includes_categories": includes_categories,
    "forbidden_categories": forbidden_categories,
    "max_total_cost": max_total_cost,
    "max_walk_km": max_walk_km,
    "min_stops": min_stops,
    "itinerary_is_feasible": itinerary_is_feasible,
    "no_hallucinated_stops": no_hallucinated_stops,
    "cheaper_than_previous": cheaper_than_previous,
    "shorter_walk_than_previous": shorter_walk_than_previous,
    "music_genre": music_genre,
    "save_denied": save_denied,
    "save_succeeds": save_succeeds,
    "authorization_respected": authorization_respected,
    "run_completes": run_completes,
}


def evaluate(record: RunRecord, expectations: dict[str, Any]) -> CaseResult:
    result = CaseResult(case_id=record.case_id)

    for name, expected in expectations.items():
        evaluator = EVALUATORS.get(name)
        if evaluator is None:
            result.scores.append(Score(name, False, "no evaluator registered"))
            continue
        result.scores.append(evaluator(record, expected))

    return result
